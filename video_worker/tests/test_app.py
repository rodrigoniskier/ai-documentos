import asyncio
import io
import sys
import tempfile
import time
import types
import unittest
from pathlib import Path
from unittest.mock import patch

if "capture" not in sys.modules:
    capture_stub = types.ModuleType("capture")
    capture_stub.CAPTURE_FILENAME = "capture.mp4"

    async def _capture_video(**_kwargs):
        raise AssertionError("capture_video não deveria ser chamado neste teste")

    capture_stub.capture_video = _capture_video
    capture_stub.validate_target_url = lambda value: value or "https://example.com/"
    sys.modules["capture"] = capture_stub

if "renderer" not in sys.modules:
    renderer_stub = types.ModuleType("renderer")
    renderer_stub.media_duration = lambda _path: 120.0
    renderer_stub.render_video = lambda **_kwargs: None
    renderer_stub.sanitize_job_id = lambda value: value or "job-test"
    sys.modules["renderer"] = renderer_stub

from fastapi import HTTPException, UploadFile
from fastapi.testclient import TestClient

import app


class AppStateTests(unittest.TestCase):
    def test_render_fingerprint_is_deterministic_and_input_sensitive(self):
        first = app._render_fingerprint(
            voice_sha256="a" * 64,
            screen_sha256="b" * 64,
            script="Roteiro final.",
            title="RN DocumentAI",
            subtitle="Plano de ensino",
            cta="Comece gratuitamente",
        )
        second = app._render_fingerprint(
            voice_sha256="a" * 64,
            screen_sha256="b" * 64,
            script="Roteiro final.",
            title="RN DocumentAI",
            subtitle="Plano de ensino",
            cta="Comece gratuitamente",
        )
        changed = app._render_fingerprint(
            voice_sha256="a" * 64,
            screen_sha256="b" * 64,
            script="Outro roteiro.",
            title="RN DocumentAI",
            subtitle="Plano de ensino",
            cta="Comece gratuitamente",
        )
        self.assertEqual(first, second)
        self.assertNotEqual(first, changed)

    def test_json_status_is_written_atomically_and_merged(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "status.json"
            app._update_status(path, "queued", attempt=1)
            app._update_status(path, "processing", stage="rendering")
            value = app._read_json(path)

            self.assertEqual(value["status"], "processing")
            self.assertEqual(value["attempt"], 1)
            self.assertEqual(value["stage"], "rendering")
            self.assertFalse(list(path.parent.glob(".*.tmp")))

    def test_cleanup_preserves_unacknowledged_ready_artifact(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            job_dir = root / "job-ready"
            app._write_capture_status(
                job_dir,
                "ready",
                updated_at=1,
                capture_sha256="a" * 64,
            )
            with (
                patch.object(app, "JOB_ROOT", root),
                patch.object(app, "JOB_TTL_SECONDS", 10),
            ):
                app.cleanup_expired_jobs(now=time.time() + 10_000)

            self.assertTrue(job_dir.exists())

    def test_cleanup_removes_completed_acknowledged_job(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            job_dir = root / "job-complete"
            app._update_status(
                app._publication_status_path(job_dir),
                "complete",
                video_id="abcdefghijk",
                youtube_url="https://youtu.be/abcdefghijk",
                r2_video_key="videos/final.mp4",
                r2_thumbnail_key="videos/final.jpg",
                r2_verified=True,
                public_confirmed=True,
                updated_at=1,
            )
            with (
                patch.object(app, "JOB_ROOT", root),
                patch.object(app, "COMPLETED_JOB_TTL_SECONDS", 10),
            ):
                app.cleanup_expired_jobs(now=time.time() + 10_000)

            self.assertFalse(job_dir.exists())

    def test_publication_requires_all_durable_confirmations(self):
        with tempfile.TemporaryDirectory() as directory:
            job_dir = Path(directory)
            app._update_status(
                app._publication_status_path(job_dir),
                "complete",
                video_id="abcdefghijk",
                youtube_url="https://youtu.be/abcdefghijk",
                r2_video_key="videos/final.mp4",
                r2_thumbnail_key="videos/final.jpg",
                r2_verified=True,
                public_confirmed=False,
            )
            self.assertFalse(app._publication_complete(job_dir))

            app._update_status(
                app._publication_status_path(job_dir),
                "complete",
                public_confirmed=True,
            )
            self.assertTrue(app._publication_complete(job_dir))

    def test_delete_is_blocked_until_publication_is_durably_acknowledged(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            job_dir = root / "job-test"
            job_dir.mkdir()
            headers = {"Authorization": "Bearer test-token"}
            with (
                patch.object(app, "JOB_ROOT", root),
                patch.object(app, "TOKEN", "test-token"),
                TestClient(app.app) as client,
            ):
                blocked = client.delete("/jobs/job-test", headers=headers)
                self.assertEqual(blocked.status_code, 409)
                self.assertTrue(job_dir.exists())

                acknowledged = client.post(
                    "/jobs/job-test/publication",
                    headers=headers,
                    json={
                        "video_id": "abcdefghijk",
                        "youtube_url": "https://youtu.be/abcdefghijk",
                        "r2_video_key": "videos/final.mp4",
                        "r2_thumbnail_key": "videos/final.jpg",
                        "r2_verified": True,
                        "public_confirmed": True,
                    },
                )
                self.assertEqual(acknowledged.status_code, 200)

                deleted = client.delete("/jobs/job-test", headers=headers)
                self.assertEqual(deleted.status_code, 200)
                self.assertFalse(job_dir.exists())

    def test_async_render_submission_persists_inputs_and_returns_status_url(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            capture_dir = root / "job-test"
            capture_dir.mkdir()
            capture = capture_dir / app.CAPTURE_FILENAME
            capture.write_bytes(b"s" * 10_001)
            headers = {"Authorization": "Bearer test-token"}
            with (
                patch.object(app, "JOB_ROOT", root),
                patch.object(app, "TOKEN", "test-token"),
                patch.object(app, "_spawn_render", return_value=None),
                TestClient(app.app) as client,
            ):
                response = client.post(
                    "/render",
                    headers=headers,
                    data={
                        "script": "Roteiro final",
                        "title": "RN DocumentAI",
                        "subtitle": "Plano de ensino",
                        "cta": "Comece gratuitamente",
                        "job_id": "job-test",
                        "capture_job_id": "job-test",
                        "async_mode": "true",
                    },
                    files={
                        "voiceover": (
                            "voice.mp3",
                            b"voice",
                            "audio/mpeg",
                        )
                    },
                )

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["status"], "queued")
            self.assertTrue(response.json()["status_url"].endswith("/render/status"))
            self.assertTrue((capture_dir / "voice-input").exists())
            self.assertTrue((capture_dir / app.RENDER_REQUEST_FILENAME).exists())
            app.render_in_progress.clear()


class UploadAndRecoveryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        app.capture_in_progress.clear()
        app.render_in_progress.clear()
        app.capture_tasks.clear()
        app.render_tasks.clear()
        app.progress_lock = asyncio.Lock()
        app.submission_lock = asyncio.Lock()

    async def test_upload_candidate_has_streamed_sha256_and_no_partial_leak(self):
        with tempfile.TemporaryDirectory() as directory:
            content = b"locucao-final"
            upload = UploadFile(filename="voice.mp3", file=io.BytesIO(content))
            path, size, digest = await app._save_upload_candidate(
                upload,
                Path(directory),
                "voice",
                1024,
            )

            self.assertEqual(size, len(content))
            self.assertEqual(digest, app.hashlib.sha256(content).hexdigest())
            self.assertEqual(path.read_bytes(), content)

    async def test_oversized_upload_is_removed(self):
        with tempfile.TemporaryDirectory() as directory:
            upload = UploadFile(filename="large.mp3", file=io.BytesIO(b"12345"))
            with self.assertRaises(HTTPException) as raised:
                await app._save_upload_candidate(
                    upload,
                    Path(directory),
                    "voice",
                    4,
                )

            self.assertEqual(raised.exception.status_code, 413)
            self.assertFalse(list(Path(directory).glob("*.part")))

    async def test_startup_recovery_schedules_persisted_capture_and_render(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            capture_dir = root / "capture-job"
            app._write_capture_status(
                capture_dir,
                "processing",
                stage="recording_demo",
                target_url="https://rn-document-platform.onrender.com/",
            )

            render_dir = root / "render-job"
            render_dir.mkdir(parents=True)
            (render_dir / "voice-input").write_bytes(b"voice")
            (render_dir / "screen-input").write_bytes(b"screen")
            app._write_json(
                app._render_request_path(render_dir),
                {
                    "screen_uploaded": True,
                    "capture_job_id": None,
                    "script": "Roteiro",
                    "title": "Título",
                    "subtitle": "Subtítulo",
                    "cta": "CTA",
                },
            )
            app._write_render_status(
                render_dir,
                "processing",
                stage="rendering",
            )

            with (
                patch.object(app, "JOB_ROOT", root),
                patch.object(app, "_spawn_capture") as spawn_capture,
                patch.object(app, "_spawn_render") as spawn_render,
            ):
                await app._recover_incomplete_jobs()

            spawn_capture.assert_called_once()
            spawn_render.assert_called_once()
            self.assertEqual(
                app._read_capture_status(capture_dir)["stage"],
                "resuming_after_restart",
            )
            self.assertEqual(
                app._read_render_status(render_dir)["stage"],
                "resuming_after_restart",
            )


if __name__ == "__main__":
    unittest.main()
