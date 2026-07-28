from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
import secrets
import shutil
import time
from pathlib import Path
from typing import Any

from capture import CAPTURE_FILENAME, capture_video, validate_target_url
from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from renderer import media_duration, render_video, sanitize_job_id

APP_NAME = "RN Content Lab Video Renderer"
WORKER_VERSION = "2026.07-resumable-1"
TOKEN = os.getenv("VIDEO_RENDER_TOKEN", "")
JOB_ROOT = Path(os.getenv("VIDEO_JOB_ROOT", "/tmp/rn-video-jobs"))
JOB_TTL_SECONDS = max(
    3600,
    int(os.getenv("VIDEO_JOB_TTL_SECONDS", "259200")),
)
COMPLETED_JOB_TTL_SECONDS = max(
    300,
    int(os.getenv("VIDEO_COMPLETED_JOB_TTL_SECONDS", "7200")),
)
STATUS_HEARTBEAT_SECONDS = max(
    5,
    int(os.getenv("VIDEO_STATUS_HEARTBEAT_SECONDS", "15")),
)
MAX_SCREEN_BYTES = int(os.getenv("VIDEO_MAX_SCREEN_MB", "350")) * 1024 * 1024
MAX_AUDIO_BYTES = int(os.getenv("VIDEO_MAX_AUDIO_MB", "50")) * 1024 * 1024
CAPTURE_STATUS_FILENAME = "capture-status.json"
RENDER_STATUS_FILENAME = "render-status.json"
RENDER_REQUEST_FILENAME = "render-request.json"
PUBLICATION_STATUS_FILENAME = "publication-status.json"
VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
RENDER_OUTPUT_ARTIFACTS = {
    "intro.png",
    "outro.png",
    "thumbnail-frame.jpg",
    "thumbnail.jpg",
    "intro.mp4",
    "main.mp4",
    "outro.mp4",
    "silent.mp4",
    "subtitles.srt",
    "video.mp4",
    "concat.txt",
}

app = FastAPI(
    title=APP_NAME,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)
bearer = HTTPBearer(auto_error=False)
media_slots = asyncio.Semaphore(max(1, int(os.getenv("VIDEO_RENDER_CONCURRENCY", "1"))))
render_in_progress: set[str] = set()
capture_in_progress: set[str] = set()
progress_lock = asyncio.Lock()
submission_lock = asyncio.Lock()
capture_tasks: dict[str, asyncio.Task[Any]] = {}
render_tasks: dict[str, asyncio.Task[Any]] = {}
logger = logging.getLogger(__name__)


class CaptureRequest(BaseModel):
    job_id: str | None = None
    target_url: str | None = None


class PublicationAck(BaseModel):
    video_id: str
    youtube_url: str
    r2_video_key: str
    r2_thumbnail_key: str
    r2_verified: bool
    public_confirmed: bool


def require_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> None:
    if not TOKEN:
        raise HTTPException(
            status_code=503, detail="Renderizador sem token configurado."
        )
    if (
        credentials is None
        or credentials.scheme.lower() != "bearer"
        or not secrets.compare_digest(credentials.credentials, TOKEN)
    ):
        raise HTTPException(status_code=401, detail="Não autorizado.")


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _write_json(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{secrets.token_hex(6)}.tmp")
    try:
        with temporary.open("w", encoding="utf-8") as target:
            json.dump(
                payload,
                target,
                ensure_ascii=False,
                separators=(",", ":"),
            )
            target.flush()
            os.fsync(target.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    return payload


def _update_status(
    path: Path,
    status: str,
    **values: Any,
) -> dict[str, Any]:
    previous = _read_json(path) or {}
    payload = {
        **previous,
        "status": status,
        "updated_at": int(time.time()),
        **values,
    }
    return _write_json(path, payload)


def _capture_status_path(job_dir: Path) -> Path:
    return job_dir / CAPTURE_STATUS_FILENAME


def _render_status_path(job_dir: Path) -> Path:
    return job_dir / RENDER_STATUS_FILENAME


def _render_request_path(job_dir: Path) -> Path:
    return job_dir / RENDER_REQUEST_FILENAME


def _publication_status_path(job_dir: Path) -> Path:
    return job_dir / PUBLICATION_STATUS_FILENAME


def _write_capture_status(
    job_dir: Path,
    status: str,
    **values: Any,
) -> dict[str, Any]:
    return _update_status(_capture_status_path(job_dir), status, **values)


def _read_capture_status(job_dir: Path) -> dict[str, Any] | None:
    return _read_json(_capture_status_path(job_dir))


def _write_render_status(
    job_dir: Path,
    status: str,
    **values: Any,
) -> dict[str, Any]:
    return _update_status(_render_status_path(job_dir), status, **values)


def _read_render_status(job_dir: Path) -> dict[str, Any] | None:
    return _read_json(_render_status_path(job_dir))


def _publication_complete(job_dir: Path) -> bool:
    status = _read_json(_publication_status_path(job_dir)) or {}
    return bool(
        status.get("status") == "complete"
        and status.get("video_id")
        and status.get("youtube_url")
        and status.get("r2_video_key")
        and status.get("r2_thumbnail_key")
        and status.get("r2_verified") is True
        and status.get("public_confirmed") is True
    )


def _job_last_updated(job_dir: Path) -> float:
    timestamps: list[float] = []
    for name in (
        CAPTURE_STATUS_FILENAME,
        RENDER_STATUS_FILENAME,
        PUBLICATION_STATUS_FILENAME,
    ):
        value = _read_json(job_dir / name) or {}
        updated_at = value.get("updated_at")
        if isinstance(updated_at, (int, float)):
            timestamps.append(float(updated_at))
    try:
        timestamps.append(job_dir.stat().st_mtime)
    except FileNotFoundError:
        pass
    return max(timestamps, default=time.time())


def cleanup_expired_jobs(now: float | None = None) -> None:
    JOB_ROOT.mkdir(parents=True, exist_ok=True)
    current_time = time.time() if now is None else now
    active_jobs = render_in_progress | capture_in_progress
    for path in JOB_ROOT.iterdir():
        if not path.is_dir() or path.name in active_jobs:
            continue
        age = current_time - _job_last_updated(path)
        if _publication_complete(path):
            if age >= COMPLETED_JOB_TTL_SECONDS:
                shutil.rmtree(path, ignore_errors=True)
            continue

        capture_status = _read_capture_status(path) or {}
        render_status = _read_render_status(path) or {}
        has_ready_artifact = bool(
            capture_status.get("status") == "ready"
            or render_status.get("status") == "ready"
            or (path / CAPTURE_FILENAME).exists()
            or (path / "video.mp4").exists()
        )
        terminal_or_empty = bool(
            not has_ready_artifact
            and capture_status.get("status") not in {"queued", "processing"}
            and render_status.get("status") not in {"queued", "processing"}
        )
        if terminal_or_empty and age >= JOB_TTL_SECONDS:
            shutil.rmtree(path, ignore_errors=True)


async def _save_upload_candidate(
    upload: UploadFile,
    job_dir: Path,
    label: str,
    max_bytes: int,
) -> tuple[Path, int, str]:
    job_dir.mkdir(parents=True, exist_ok=True)
    temporary = job_dir / f".{label}.{secrets.token_hex(8)}.part"
    total = 0
    digest = hashlib.sha256()
    try:
        with temporary.open("xb") as target:
            while chunk := await upload.read(1024 * 1024):
                total += len(chunk)
                if total > max_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail="Arquivo excede o limite permitido.",
                    )
                digest.update(chunk)
                target.write(chunk)
            target.flush()
            os.fsync(target.fileno())
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    finally:
        await upload.close()
    if total == 0:
        temporary.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail="Arquivo vazio.")
    return temporary, total, digest.hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _text_sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _render_fingerprint(
    *,
    voice_sha256: str,
    screen_sha256: str,
    script: str,
    title: str,
    subtitle: str,
    cta: str,
) -> str:
    value = {
        "schema_version": 1,
        "voice_sha256": voice_sha256,
        "screen_sha256": screen_sha256,
        "script_sha256": _text_sha256(script),
        "title_sha256": _text_sha256(title),
        "subtitle_sha256": _text_sha256(subtitle),
        "cta_sha256": _text_sha256(cta),
    }
    canonical = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return _text_sha256(canonical)


def _capture_result(job_dir: Path) -> dict[str, float | int | str | bool]:
    path = job_dir / CAPTURE_FILENAME
    duration = round(media_duration(path), 3)
    if duration < 90 or path.stat().st_size < 10_000:
        raise ValueError("A captura produzida não atende aos requisitos mínimos.")
    return {
        "duration_seconds": duration,
        "capture_bytes": path.stat().st_size,
        "capture_sha256": _file_sha256(path),
        "docx_download_confirmed": (
            job_dir / "Plano_Ensino_Demonstracao.docx"
        ).exists(),
    }


def _render_result(job_dir: Path) -> dict[str, float | int | str]:
    output = job_dir / "video.mp4"
    thumbnail = job_dir / "thumbnail.jpg"
    duration = round(media_duration(output), 3)
    if duration <= 0 or output.stat().st_size < 10_000:
        raise ValueError("O vídeo produzido não é válido.")
    if thumbnail.stat().st_size == 0:
        raise ValueError("A thumbnail produzida está vazia.")
    return {
        "duration_seconds": duration,
        "video_bytes": output.stat().st_size,
        "thumbnail_bytes": thumbnail.stat().st_size,
        "video_sha256": _file_sha256(output),
        "thumbnail_sha256": _file_sha256(thumbnail),
    }


def _capture_payload(
    job_id: str,
    request: Request,
    status: dict[str, Any],
) -> dict[str, Any]:
    payload = {
        **status,
        "job_id": job_id,
        "status_url": str(request.url_for("capture_status", job_id=job_id)),
    }
    if status.get("status") == "ready":
        payload["capture_url"] = str(request.url_for("download_capture", job_id=job_id))
    return payload


def _render_payload(
    job_id: str,
    request: Request,
    status: dict[str, Any],
) -> dict[str, Any]:
    payload = {
        **status,
        "job_id": job_id,
        "status_url": str(request.url_for("render_status", job_id=job_id)),
    }
    if status.get("status") == "ready":
        payload["video_url"] = str(request.url_for("download_video", job_id=job_id))
        payload["thumbnail_url"] = str(
            request.url_for("download_thumbnail", job_id=job_id)
        )
    return payload


def _cleanup_render_outputs(job_dir: Path) -> None:
    for name in RENDER_OUTPUT_ARTIFACTS:
        path = job_dir / name
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
        else:
            path.unlink(missing_ok=True)
    for path in job_dir.glob(".render-attempt-*"):
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
        else:
            path.unlink(missing_ok=True)


def _public_error(exc: Exception, stage: str) -> str:
    first_line = str(exc).splitlines()[0].strip()
    if isinstance(exc, (RuntimeError, ValueError)) and first_line:
        return first_line[:400]
    if exc.__class__.__name__.lower().endswith("timeouterror"):
        return f"Tempo esgotado durante a etapa {stage}."
    return f"Falha técnica durante a etapa {stage} ({exc.__class__.__name__})."


def _persistent_job_root_configured() -> bool:
    try:
        return not JOB_ROOT.resolve().is_relative_to(Path("/tmp").resolve())
    except (OSError, RuntimeError):
        return False


def _forget_capture_task(job_id: str, task: asyncio.Task[Any]) -> None:
    if capture_tasks.get(job_id) is task:
        capture_tasks.pop(job_id, None)


def _forget_render_task(job_id: str, task: asyncio.Task[Any]) -> None:
    if render_tasks.get(job_id) is task:
        render_tasks.pop(job_id, None)


def _spawn_capture(safe_job_id: str, target_url: str, job_dir: Path) -> None:
    task = asyncio.create_task(
        _execute_capture(safe_job_id, target_url, job_dir),
        name=f"capture-{safe_job_id}",
    )
    capture_tasks[safe_job_id] = task
    task.add_done_callback(
        lambda completed, job_id=safe_job_id: _forget_capture_task(
            job_id,
            completed,
        )
    )


def _spawn_render(safe_job_id: str, job_dir: Path) -> asyncio.Task[Any]:
    task = asyncio.create_task(
        _execute_render(safe_job_id, job_dir),
        name=f"render-{safe_job_id}",
    )
    render_tasks[safe_job_id] = task
    task.add_done_callback(
        lambda completed, job_id=safe_job_id: _forget_render_task(
            job_id,
            completed,
        )
    )
    return task


async def _execute_capture(
    safe_job_id: str,
    target_url: str,
    job_dir: Path,
) -> None:
    previous = _read_capture_status(job_dir) or {}
    attempt = int(previous.get("attempt") or 0) + 1
    try:
        async with media_slots:
            _write_capture_status(
                job_dir,
                "processing",
                stage="preparing_demo",
                target_url=target_url,
                attempt=attempt,
                retryable=True,
                error=None,
            )

            def progress(stage: str) -> None:
                _write_capture_status(
                    job_dir,
                    "processing",
                    stage=stage,
                    target_url=target_url,
                    attempt=attempt,
                    retryable=True,
                    error=None,
                )

            result = await capture_video(
                job_dir=job_dir,
                target_url=target_url,
                token=TOKEN,
                job_id=safe_job_id,
                progress=progress,
            )
            _write_capture_status(
                job_dir,
                "ready",
                stage="ready",
                target_url=target_url,
                attempt=attempt,
                retryable=False,
                error=None,
                **result.as_dict(),
            )
    except Exception as exc:
        previous_status = _read_capture_status(job_dir) or {}
        failed_stage = str(previous_status.get("stage") or "unknown")
        logger.exception(
            "Automated capture failed for job=%s stage=%s",
            safe_job_id,
            failed_stage,
        )
        _write_capture_status(
            job_dir,
            "failed",
            stage="failed",
            failed_stage=failed_stage,
            target_url=target_url,
            attempt=attempt,
            retryable=not isinstance(exc, ValueError),
            error=_public_error(exc, failed_stage),
        )
    finally:
        async with progress_lock:
            capture_in_progress.discard(safe_job_id)


async def _render_with_heartbeat(
    *,
    job_dir: Path,
    attempt_dir: Path,
    request_data: dict[str, Any],
    screen_path: Path,
    voice_path: Path,
    attempt: int,
) -> Any:
    task = asyncio.create_task(
        asyncio.to_thread(
            render_video,
            work_dir=attempt_dir,
            screen_video=screen_path,
            voiceover=voice_path,
            script=str(request_data["script"]),
            title=str(request_data["title"]),
            subtitle=str(request_data["subtitle"]),
            cta=str(request_data["cta"]),
        ),
        name=f"ffmpeg-render-{job_dir.name}",
    )
    while True:
        try:
            return await asyncio.wait_for(
                asyncio.shield(task),
                timeout=STATUS_HEARTBEAT_SECONDS,
            )
        except TimeoutError:
            _write_render_status(
                job_dir,
                "processing",
                stage="rendering",
                attempt=attempt,
                retryable=True,
                error=None,
            )


async def _execute_render(safe_job_id: str, job_dir: Path) -> None:
    status = _read_render_status(job_dir) or {}
    request_data = _read_json(_render_request_path(job_dir))
    attempt = int(status.get("attempt") or 0) + 1
    attempt_dir = job_dir / (f".render-attempt-{attempt}-{secrets.token_hex(5)}")
    try:
        if not request_data:
            raise RuntimeError(
                "Os dados persistentes da renderização não foram encontrados."
            )
        voice_path = job_dir / "voice-input"
        if not voice_path.exists():
            raise RuntimeError("A locução persistente não foi encontrada.")

        capture_job_id = request_data.get("capture_job_id")
        if request_data.get("screen_uploaded"):
            screen_path = job_dir / "screen-input"
        elif capture_job_id:
            screen_path = JOB_ROOT / str(capture_job_id) / CAPTURE_FILENAME
        else:
            raise RuntimeError("A origem da captura não foi registrada.")
        if not screen_path.exists():
            raise RuntimeError("A captura persistente não foi encontrada.")

        async with media_slots:
            attempt_dir.mkdir(parents=True, exist_ok=False)
            _write_render_status(
                job_dir,
                "processing",
                stage="rendering",
                attempt=attempt,
                retryable=True,
                error=None,
            )
            await _render_with_heartbeat(
                job_dir=job_dir,
                attempt_dir=attempt_dir,
                request_data=request_data,
                screen_path=screen_path,
                voice_path=voice_path,
                attempt=attempt,
            )
            attempt_video = attempt_dir / "video.mp4"
            attempt_thumbnail = attempt_dir / "thumbnail.jpg"
            if not attempt_video.exists() or not attempt_thumbnail.exists():
                raise RuntimeError("A renderização não produziu todos os artefatos.")

            (job_dir / "video.mp4").unlink(missing_ok=True)
            (job_dir / "thumbnail.jpg").unlink(missing_ok=True)
            attempt_video.replace(job_dir / "video.mp4")
            attempt_thumbnail.replace(job_dir / "thumbnail.jpg")
            result = _render_result(job_dir)
            _write_render_status(
                job_dir,
                "ready",
                stage="ready",
                attempt=attempt,
                retryable=False,
                error=None,
                **result,
            )
    except Exception as exc:
        previous_status = _read_render_status(job_dir) or {}
        failed_stage = str(previous_status.get("stage") or "rendering")
        logger.exception(
            "Video render failed for job=%s stage=%s",
            safe_job_id,
            failed_stage,
        )
        (job_dir / "video.mp4").unlink(missing_ok=True)
        (job_dir / "thumbnail.jpg").unlink(missing_ok=True)
        _write_render_status(
            job_dir,
            "failed",
            stage="failed",
            failed_stage=failed_stage,
            attempt=attempt,
            retryable=not isinstance(exc, ValueError),
            error=_public_error(exc, failed_stage),
        )
    finally:
        shutil.rmtree(attempt_dir, ignore_errors=True)
        async with progress_lock:
            render_in_progress.discard(safe_job_id)


async def _recover_incomplete_jobs() -> None:
    JOB_ROOT.mkdir(parents=True, exist_ok=True)
    for job_dir in JOB_ROOT.iterdir():
        if not job_dir.is_dir():
            continue
        safe_job_id = job_dir.name

        capture_path = job_dir / CAPTURE_FILENAME
        capture_status_value = _read_capture_status(job_dir) or {}
        if capture_path.exists():
            try:
                result = _capture_result(job_dir)
            except (OSError, ValueError):
                capture_path.unlink(missing_ok=True)
            else:
                _write_capture_status(
                    job_dir,
                    "ready",
                    stage="ready",
                    retryable=False,
                    error=None,
                    **result,
                )
        elif capture_status_value.get("status") in {"queued", "processing"}:
            target_url = capture_status_value.get("target_url")
            if isinstance(target_url, str) and target_url:
                async with progress_lock:
                    capture_in_progress.add(safe_job_id)
                _write_capture_status(
                    job_dir,
                    "queued",
                    stage="resuming_after_restart",
                    retryable=True,
                    error=None,
                )
                _spawn_capture(safe_job_id, target_url, job_dir)
            else:
                _write_capture_status(
                    job_dir,
                    "failed",
                    stage="failed",
                    failed_stage="service_restart",
                    retryable=True,
                    error=(
                        "O serviço reiniciou e a captura precisa ser solicitada novamente."
                    ),
                )

        output = job_dir / "video.mp4"
        thumbnail = job_dir / "thumbnail.jpg"
        render_status_value = _read_render_status(job_dir) or {}
        if output.exists() and thumbnail.exists():
            try:
                result = _render_result(job_dir)
            except (OSError, ValueError):
                output.unlink(missing_ok=True)
                thumbnail.unlink(missing_ok=True)
            else:
                _write_render_status(
                    job_dir,
                    "ready",
                    stage="ready",
                    retryable=False,
                    error=None,
                    **result,
                )
        elif render_status_value.get("status") in {"queued", "processing"}:
            request_data = _read_json(_render_request_path(job_dir))
            voice_ready = (job_dir / "voice-input").exists()
            screen_ready = bool(
                request_data
                and (
                    (
                        request_data.get("screen_uploaded")
                        and (job_dir / "screen-input").exists()
                    )
                    or (
                        request_data.get("capture_job_id")
                        and (
                            JOB_ROOT
                            / str(request_data["capture_job_id"])
                            / CAPTURE_FILENAME
                        ).exists()
                    )
                )
            )
            if request_data and voice_ready and screen_ready:
                _cleanup_render_outputs(job_dir)
                async with progress_lock:
                    render_in_progress.add(safe_job_id)
                _write_render_status(
                    job_dir,
                    "queued",
                    stage="resuming_after_restart",
                    retryable=True,
                    error=None,
                )
                _spawn_render(safe_job_id, job_dir)
            else:
                _write_render_status(
                    job_dir,
                    "failed",
                    stage="failed",
                    failed_stage="service_restart",
                    retryable=True,
                    error=(
                        "O serviço reiniciou, mas os insumos persistentes da "
                        "renderização não estão completos."
                    ),
                )
    cleanup_expired_jobs()


@app.on_event("startup")
async def startup_recovery() -> None:
    await _recover_incomplete_jobs()


@app.get("/health")
def health() -> dict[str, Any]:
    writable = False
    free_bytes = 0
    try:
        JOB_ROOT.mkdir(parents=True, exist_ok=True)
        probe = JOB_ROOT / f".health-{secrets.token_hex(4)}"
        probe.write_bytes(b"ok")
        probe.unlink(missing_ok=True)
        free_bytes = shutil.disk_usage(JOB_ROOT).free
        writable = True
    except OSError:
        logger.exception("Job storage health check failed")
    healthy = bool(TOKEN and writable)
    return {
        "status": "ok" if healthy else "degraded",
        "service": APP_NAME,
        "version": WORKER_VERSION,
        "token_configured": bool(TOKEN),
        "capture_enabled": bool(TOKEN),
        "storage_writable": writable,
        "persistent_job_root": _persistent_job_root_configured(),
        "storage_free_bytes": free_bytes,
        "capture_jobs_active": len(capture_in_progress),
        "render_jobs_active": len(render_in_progress),
    }


@app.post("/capture", dependencies=[Depends(require_token)])
async def start_capture(payload: CaptureRequest, request: Request) -> dict[str, Any]:
    cleanup_expired_jobs()
    try:
        safe_job_id = sanitize_job_id(payload.job_id)
        target_url = validate_target_url(payload.target_url)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    job_dir = JOB_ROOT / safe_job_id
    capture_path = job_dir / CAPTURE_FILENAME
    if capture_path.exists():
        try:
            status = _write_capture_status(
                job_dir,
                "ready",
                stage="ready",
                target_url=target_url,
                retryable=False,
                error=None,
                **_capture_result(job_dir),
            )
            return _capture_payload(safe_job_id, request, status)
        except (OSError, ValueError):
            capture_path.unlink(missing_ok=True)

    async with progress_lock:
        if safe_job_id in capture_in_progress:
            status = _read_capture_status(job_dir) or {
                "status": "processing",
                "stage": "queued",
            }
            return _capture_payload(safe_job_id, request, status)
        capture_in_progress.add(safe_job_id)

    status = _write_capture_status(
        job_dir,
        "queued",
        stage="queued",
        target_url=target_url,
        retryable=True,
        error=None,
    )
    _spawn_capture(safe_job_id, target_url, job_dir)
    return _capture_payload(safe_job_id, request, status)


@app.get(
    "/jobs/{job_id}/capture/status",
    name="capture_status",
    dependencies=[Depends(require_token)],
)
def capture_status(job_id: str, request: Request) -> dict[str, Any]:
    try:
        safe_job_id = sanitize_job_id(job_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Job não encontrado.") from exc
    job_dir = JOB_ROOT / safe_job_id
    capture_path = job_dir / CAPTURE_FILENAME
    status = _read_capture_status(job_dir)
    if capture_path.exists():
        try:
            status = _write_capture_status(
                job_dir,
                "ready",
                stage="ready",
                retryable=False,
                error=None,
                **_capture_result(job_dir),
            )
        except (OSError, ValueError):
            capture_path.unlink(missing_ok=True)
            status = _write_capture_status(
                job_dir,
                "failed",
                stage="failed",
                failed_stage="validating_capture",
                retryable=True,
                error="A captura produzida não é um vídeo válido.",
            )
        return _capture_payload(safe_job_id, request, status)
    if status and status.get("status") == "ready":
        status = _write_capture_status(
            job_dir,
            "failed",
            stage="failed",
            failed_stage="artifact_missing",
            retryable=True,
            error="O arquivo da captura não está mais disponível.",
        )
    if status is None:
        raise HTTPException(status_code=404, detail="Captura não encontrada.")
    return _capture_payload(safe_job_id, request, status)


@app.get(
    "/jobs/{job_id}/capture",
    name="download_capture",
    dependencies=[Depends(require_token)],
)
def download_capture(job_id: str) -> FileResponse:
    try:
        safe_job_id = sanitize_job_id(job_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Job não encontrado.") from exc
    path = JOB_ROOT / safe_job_id / CAPTURE_FILENAME
    if not path.exists():
        raise HTTPException(status_code=404, detail="Captura não encontrada.")
    return FileResponse(
        path,
        media_type="video/mp4",
        filename=f"{safe_job_id}-capture.mp4",
    )


@app.post("/render", dependencies=[Depends(require_token)])
async def render(
    request: Request,
    voiceover: UploadFile = File(...),
    script: str = Form(...),
    title: str = Form(...),
    screen_video: UploadFile | None = File(default=None),
    capture_job_id: str | None = Form(default=None),
    subtitle: str = Form(
        "Planos de Ensino personalizados, editáveis e rastreáveis com IA."
    ),
    cta: str = Form("Crie sua conta e gere seu primeiro documento gratuitamente."),
    job_id: str | None = Form(default=None),
    async_mode: bool = Form(default=False),
) -> dict[str, Any]:
    cleanup_expired_jobs()
    try:
        safe_capture_job_id = (
            sanitize_job_id(capture_job_id) if capture_job_id else None
        )
        safe_job_id = sanitize_job_id(job_id or safe_capture_job_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if screen_video is None and safe_capture_job_id is None:
        raise HTTPException(
            status_code=422,
            detail="Envie screen_video ou informe capture_job_id.",
        )

    job_dir = JOB_ROOT / safe_job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    voice_candidate: Path | None = None
    screen_candidate: Path | None = None
    task: asyncio.Task[Any] | None = None

    async with submission_lock:
        try:
            voice_candidate, _, voice_sha256 = await _save_upload_candidate(
                voiceover,
                job_dir,
                "voice-input",
                MAX_AUDIO_BYTES,
            )
            if screen_video is not None:
                screen_candidate, _, screen_sha256 = await _save_upload_candidate(
                    screen_video,
                    job_dir,
                    "screen-input",
                    MAX_SCREEN_BYTES,
                )
            else:
                capture_path = JOB_ROOT / str(safe_capture_job_id) / CAPTURE_FILENAME
                if not capture_path.exists():
                    raise HTTPException(
                        status_code=422,
                        detail="A captura automatizada ainda não está pronta.",
                    )
                screen_sha256 = _file_sha256(capture_path)

            fingerprint = _render_fingerprint(
                voice_sha256=voice_sha256,
                screen_sha256=screen_sha256,
                script=script,
                title=title,
                subtitle=subtitle,
                cta=cta,
            )
            existing_status = _read_render_status(job_dir) or {}
            existing_fingerprint = existing_status.get("input_fingerprint")
            if existing_fingerprint and existing_fingerprint != fingerprint:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "O job_id já está associado a entradas diferentes. "
                        "Use um novo job_id ou retome os insumos originais."
                    ),
                )

            output = job_dir / "video.mp4"
            thumbnail = job_dir / "thumbnail.jpg"
            if (
                existing_status.get("status") == "ready"
                and output.exists()
                and thumbnail.exists()
            ):
                status = _write_render_status(
                    job_dir,
                    "ready",
                    stage="ready",
                    input_fingerprint=fingerprint,
                    retryable=False,
                    error=None,
                    **_render_result(job_dir),
                )
                return _render_payload(safe_job_id, request, status)

            if safe_job_id in render_in_progress:
                task = render_tasks.get(safe_job_id)
                status = _read_render_status(job_dir) or {
                    "status": "processing",
                    "stage": "rendering",
                    "input_fingerprint": fingerprint,
                }
            else:
                voice_candidate.replace(job_dir / "voice-input")
                voice_candidate = None
                if screen_candidate is not None:
                    screen_candidate.replace(job_dir / "screen-input")
                    screen_candidate = None
                elif (job_dir / "screen-input").exists():
                    (job_dir / "screen-input").unlink(missing_ok=True)

                request_data = {
                    "schema_version": 1,
                    "job_id": safe_job_id,
                    "capture_job_id": safe_capture_job_id,
                    "screen_uploaded": screen_video is not None,
                    "voice_sha256": voice_sha256,
                    "screen_sha256": screen_sha256,
                    "input_fingerprint": fingerprint,
                    "script": script,
                    "title": title,
                    "subtitle": subtitle,
                    "cta": cta,
                    "created_at": int(time.time()),
                }
                _write_json(_render_request_path(job_dir), request_data)
                _cleanup_render_outputs(job_dir)
                status = _write_render_status(
                    job_dir,
                    "queued",
                    stage="queued",
                    input_fingerprint=fingerprint,
                    retryable=True,
                    error=None,
                )
                async with progress_lock:
                    render_in_progress.add(safe_job_id)
                task = _spawn_render(safe_job_id, job_dir)
        finally:
            if voice_candidate is not None:
                voice_candidate.unlink(missing_ok=True)
            if screen_candidate is not None:
                screen_candidate.unlink(missing_ok=True)

    if async_mode:
        return _render_payload(safe_job_id, request, status)

    if task is not None:
        await asyncio.shield(task)
    final_status = _read_render_status(job_dir) or {}
    if final_status.get("status") != "ready":
        detail = str(final_status.get("error") or "Falha ao renderizar o vídeo.")
        raise HTTPException(status_code=500, detail=detail)
    return _render_payload(safe_job_id, request, final_status)


@app.get(
    "/jobs/{job_id}/render/status",
    name="render_status",
    dependencies=[Depends(require_token)],
)
def render_status(job_id: str, request: Request) -> dict[str, Any]:
    try:
        safe_job_id = sanitize_job_id(job_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Job não encontrado.") from exc
    job_dir = JOB_ROOT / safe_job_id
    status = _read_render_status(job_dir)
    output = job_dir / "video.mp4"
    thumbnail = job_dir / "thumbnail.jpg"
    if output.exists() and thumbnail.exists():
        try:
            status = _write_render_status(
                job_dir,
                "ready",
                stage="ready",
                retryable=False,
                error=None,
                **_render_result(job_dir),
            )
        except (OSError, ValueError):
            output.unlink(missing_ok=True)
            thumbnail.unlink(missing_ok=True)
            status = _write_render_status(
                job_dir,
                "failed",
                stage="failed",
                failed_stage="validating_render",
                retryable=True,
                error="Os artefatos renderizados não são válidos.",
            )
    elif status and status.get("status") == "ready":
        status = _write_render_status(
            job_dir,
            "failed",
            stage="failed",
            failed_stage="artifact_missing",
            retryable=True,
            error="Os artefatos renderizados não estão mais disponíveis.",
        )
    if status is None:
        raise HTTPException(status_code=404, detail="Renderização não encontrada.")
    return _render_payload(safe_job_id, request, status)


@app.get(
    "/jobs/{job_id}/video",
    name="download_video",
    dependencies=[Depends(require_token)],
)
def download_video(job_id: str) -> FileResponse:
    try:
        safe_job_id = sanitize_job_id(job_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Job não encontrado.") from exc
    path = JOB_ROOT / safe_job_id / "video.mp4"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Vídeo não encontrado.")
    return FileResponse(path, media_type="video/mp4", filename=f"{safe_job_id}.mp4")


@app.get(
    "/jobs/{job_id}/thumbnail",
    name="download_thumbnail",
    dependencies=[Depends(require_token)],
)
def download_thumbnail(job_id: str) -> FileResponse:
    try:
        safe_job_id = sanitize_job_id(job_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Job não encontrado.") from exc
    path = JOB_ROOT / safe_job_id / "thumbnail.jpg"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Thumbnail não encontrada.")
    return FileResponse(path, media_type="image/jpeg", filename=f"{safe_job_id}.jpg")


@app.post(
    "/jobs/{job_id}/publication",
    dependencies=[Depends(require_token)],
)
def acknowledge_publication(
    job_id: str,
    payload: PublicationAck,
) -> dict[str, Any]:
    try:
        safe_job_id = sanitize_job_id(job_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Job não encontrado.") from exc
    job_dir = JOB_ROOT / safe_job_id
    if not job_dir.exists():
        raise HTTPException(status_code=404, detail="Job não encontrado.")
    if not VIDEO_ID_RE.fullmatch(payload.video_id):
        raise HTTPException(status_code=422, detail="video_id do YouTube inválido.")
    if not payload.youtube_url.startswith(
        (
            "https://www.youtube.com/watch?v=",
            "https://youtu.be/",
        )
    ):
        raise HTTPException(status_code=422, detail="URL do YouTube inválida.")
    if not payload.r2_video_key.strip() or not payload.r2_thumbnail_key.strip():
        raise HTTPException(status_code=422, detail="Chaves do R2 são obrigatórias.")
    if payload.r2_verified is not True or payload.public_confirmed is not True:
        raise HTTPException(
            status_code=409,
            detail=(
                "A publicação só pode ser confirmada após verificar o R2 "
                "e a visibilidade pública no YouTube."
            ),
        )
    status = _update_status(
        _publication_status_path(job_dir),
        "complete",
        video_id=payload.video_id,
        youtube_url=payload.youtube_url,
        r2_video_key=payload.r2_video_key,
        r2_thumbnail_key=payload.r2_thumbnail_key,
        r2_verified=True,
        public_confirmed=True,
    )
    return {"job_id": safe_job_id, **status}


@app.delete("/jobs/{job_id}", dependencies=[Depends(require_token)])
async def delete_job(job_id: str) -> dict[str, str]:
    try:
        safe_job_id = sanitize_job_id(job_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Job não encontrado.") from exc
    job_dir = JOB_ROOT / safe_job_id
    if not job_dir.exists():
        return {"status": "already_deleted", "job_id": safe_job_id}
    async with progress_lock:
        if safe_job_id in render_in_progress or safe_job_id in capture_in_progress:
            raise HTTPException(status_code=409, detail="Job ainda está em andamento.")
    if not _publication_complete(job_dir):
        raise HTTPException(
            status_code=409,
            detail=(
                "Limpeza bloqueada: confirme R2 e publicação pública "
                "em POST /jobs/{job_id}/publication."
            ),
        )
    shutil.rmtree(job_dir, ignore_errors=True)
    return {"status": "deleted", "job_id": safe_job_id}
