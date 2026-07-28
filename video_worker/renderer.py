from __future__ import annotations

import hashlib
import os
import re
import subprocess
import textwrap
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


VIDEO_WIDTH = 1920
VIDEO_HEIGHT = 1080
THUMB_WIDTH = 1280
THUMB_HEIGHT = 720
FPS = 30
FFMPEG_TIMEOUT_SECONDS = max(
    60, int(os.getenv("VIDEO_RENDER_FFMPEG_TIMEOUT_SECONDS", "600"))
)

NAVY = (7, 25, 48)
BLUE = (21, 73, 125)
YELLOW = (252, 194, 35)
WHITE = (249, 251, 255)
MUTED = (202, 215, 230)

FONT_REGULAR = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
FONT_BOLD = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")

JOB_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")


@dataclass(frozen=True)
class RenderResult:
    duration_seconds: float
    video_bytes: int
    thumbnail_bytes: int
    video_sha256: str

    def as_dict(self) -> dict[str, float | int | str]:
        return asdict(self)


def clean_text(value: str, *, max_length: int) -> str:
    cleaned = " ".join((value or "").split()).strip()
    if not cleaned:
        raise ValueError("Texto obrigatório ausente.")
    if len(cleaned) > max_length:
        raise ValueError(f"Texto excede o limite de {max_length} caracteres.")
    return cleaned


def sanitize_job_id(value: str | None) -> str:
    if not value:
        return uuid.uuid4().hex
    if not JOB_ID_RE.fullmatch(value):
        raise ValueError("job_id deve conter apenas letras, números, hífen e sublinhado.")
    return value


def _run(command: list[str], *, timeout: int = FFMPEG_TIMEOUT_SECONDS) -> None:
    if command and command[0] == "ffmpeg":
        command = [
            "ffmpeg",
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "error",
            "-filter_threads",
            "1",
            *command[1:],
        ]
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            f"FFmpeg excedeu o limite de {timeout} segundos."
        ) from exc
    if completed.returncode:
        stderr = completed.stderr[-4000:].strip()
        raise RuntimeError(f"FFmpeg falhou: {stderr}")


def media_duration(path: Path) -> float:
    completed = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if completed.returncode:
        raise ValueError(f"Arquivo de mídia inválido: {path.name}")
    try:
        duration = float(completed.stdout.strip())
    except ValueError as exc:
        raise ValueError(f"Não foi possível medir a duração de {path.name}.") from exc
    if duration <= 0:
        raise ValueError(f"Duração inválida em {path.name}.")
    return duration


def _srt_timestamp(seconds: float) -> str:
    milliseconds = max(0, round(seconds * 1000))
    hours, milliseconds = divmod(milliseconds, 3_600_000)
    minutes, milliseconds = divmod(milliseconds, 60_000)
    secs, milliseconds = divmod(milliseconds, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"


def _subtitle_segments(script: str) -> list[str]:
    paragraphs = [part.strip() for part in re.split(r"\n+", script) if part.strip()]
    sentences: list[str] = []
    for paragraph in paragraphs:
        for sentence in SENTENCE_RE.split(paragraph):
            sentence = sentence.strip()
            if not sentence:
                continue
            if len(sentence) <= 105:
                sentences.append(sentence)
                continue
            sentences.extend(
                part.strip()
                for part in textwrap.wrap(
                    sentence,
                    width=92,
                    break_long_words=False,
                    break_on_hyphens=False,
                )
                if part.strip()
            )
    return sentences or [clean_text(script, max_length=20_000)]


def build_srt(script: str, duration_seconds: float) -> str:
    segments = _subtitle_segments(script)
    weights = [max(8, len(segment)) for segment in segments]
    total_weight = sum(weights)
    cursor = 0.0
    blocks: list[str] = []

    for index, (segment, weight) in enumerate(zip(segments, weights, strict=True), start=1):
        if index == len(segments):
            end = duration_seconds
        else:
            end = cursor + (duration_seconds * weight / total_weight)
        end = max(end, cursor + 0.45)
        end = min(end, duration_seconds)
        blocks.append(
            f"{index}\n{_srt_timestamp(cursor)} --> {_srt_timestamp(end)}\n{segment}\n"
        )
        cursor = end
    return "\n".join(blocks)


def _font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont:
    path = FONT_BOLD if bold else FONT_REGULAR
    return ImageFont.truetype(str(path), size=size)


def _fit_lines(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont,
    max_width: int,
) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current: list[str] = []
    for word in words:
        candidate = " ".join([*current, word])
        if current and draw.textlength(candidate, font=font) > max_width:
            lines.append(" ".join(current))
            current = [word]
        else:
            current.append(word)
    if current:
        lines.append(" ".join(current))
    return lines


def _draw_multiline(
    draw: ImageDraw.ImageDraw,
    *,
    text: str,
    font: ImageFont.FreeTypeFont,
    fill: tuple[int, int, int] | tuple[int, int, int, int],
    xy: tuple[int, int],
    max_width: int,
    spacing: int,
    max_lines: int,
) -> int:
    lines = _fit_lines(draw, text, font, max_width)[:max_lines]
    x, y = xy
    line_height = int(font.size * 1.22)
    for line in lines:
        draw.text((x, y), line, font=font, fill=fill)
        y += line_height + spacing
    return y


def _gradient_background(width: int, height: int) -> Image.Image:
    image = Image.new("RGB", (width, height), NAVY)
    pixels = image.load()
    for y in range(height):
        ratio_y = y / max(1, height - 1)
        for x in range(width):
            ratio = (x / max(1, width - 1) + ratio_y) / 2
            pixels[x, y] = (
                int(NAVY[0] + (BLUE[0] - NAVY[0]) * ratio),
                int(NAVY[1] + (BLUE[1] - NAVY[1]) * ratio),
                int(NAVY[2] + (BLUE[2] - NAVY[2]) * ratio),
            )
    return image


def create_intro_card(path: Path, *, title: str, subtitle: str) -> None:
    image = _gradient_background(VIDEO_WIDTH, VIDEO_HEIGHT)
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((115, 105, 535, 175), radius=24, fill=YELLOW)
    draw.text((150, 121), "RN DOCUMENTAI", font=_font(34, bold=True), fill=NAVY)
    y = _draw_multiline(
        draw,
        text=title,
        font=_font(78, bold=True),
        fill=WHITE,
        xy=(115, 265),
        max_width=1570,
        spacing=8,
        max_lines=3,
    )
    _draw_multiline(
        draw,
        text=subtitle,
        font=_font(38),
        fill=MUTED,
        xy=(120, min(y + 38, 810)),
        max_width=1500,
        spacing=6,
        max_lines=2,
    )
    draw.rectangle((115, 930, 690, 942), fill=YELLOW)
    draw.text((115, 960), "RN Content Lab", font=_font(34, bold=True), fill=WHITE)
    image.save(path, "PNG", optimize=True)


def create_outro_card(path: Path, *, cta: str) -> None:
    image = _gradient_background(VIDEO_WIDTH, VIDEO_HEIGHT)
    draw = ImageDraw.Draw(image)
    draw.text((120, 160), "RN DOCUMENTAI", font=_font(48, bold=True), fill=YELLOW)
    y = _draw_multiline(
        draw,
        text=cta,
        font=_font(76, bold=True),
        fill=WHITE,
        xy=(120, 300),
        max_width=1600,
        spacing=10,
        max_lines=3,
    )
    draw.rounded_rectangle((120, min(y + 70, 800), 980, min(y + 170, 900)), radius=28, fill=YELLOW)
    draw.text(
        (165, min(y + 92, 822)),
        "Comece gratuitamente",
        font=_font(42, bold=True),
        fill=NAVY,
    )
    draw.text(
        (120, 965),
        "Documentos acadêmicos personalizados, editáveis e rastreáveis.",
        font=_font(30),
        fill=MUTED,
    )
    image.save(path, "PNG", optimize=True)


def create_thumbnail(
    path: Path,
    *,
    screen_video: Path,
    title: str,
    work_dir: Path,
) -> None:
    frame_path = work_dir / "thumbnail-frame.jpg"
    _run(
        [
            "ffmpeg",
            "-y",
            "-ss",
            "1",
            "-i",
            str(screen_video),
            "-frames:v",
            "1",
            "-vf",
            f"scale={THUMB_WIDTH}:{THUMB_HEIGHT}:force_original_aspect_ratio=increase,crop={THUMB_WIDTH}:{THUMB_HEIGHT}",
            "-q:v",
            "2",
            str(frame_path),
        ],
        timeout=120,
    )
    image = Image.open(frame_path).convert("RGBA")
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    overlay_draw.rectangle((0, 0, 760, THUMB_HEIGHT), fill=(NAVY[0], NAVY[1], NAVY[2], 235))
    overlay_draw.rectangle((760, 0, 980, THUMB_HEIGHT), fill=(NAVY[0], NAVY[1], NAVY[2], 105))
    image = Image.alpha_composite(image, overlay)
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((55, 55, 430, 115), radius=18, fill=YELLOW)
    draw.text((85, 68), "RN DOCUMENTAI", font=_font(28, bold=True), fill=NAVY)
    _draw_multiline(
        draw,
        text=title,
        font=_font(54, bold=True),
        fill=WHITE,
        xy=(55, 175),
        max_width=650,
        spacing=6,
        max_lines=5,
    )
    draw.text((55, 650), "RN Content Lab", font=_font(28, bold=True), fill=YELLOW)
    image.convert("RGB").save(path, "JPEG", quality=92, optimize=True)


def _make_still_video(image: Path, output: Path, duration: float) -> None:
    _run(
        [
            "ffmpeg",
            "-y",
            "-loop",
            "1",
            "-i",
            str(image),
            "-t",
            f"{duration:.3f}",
            "-vf",
            f"scale={VIDEO_WIDTH}:{VIDEO_HEIGHT},fps={FPS},format=yuv420p",
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-crf",
            "20",
            "-threads",
            "1",
            "-r",
            str(FPS),
            str(output),
        ]
    )


def _make_main_video(
    screen_video: Path,
    output: Path,
    *,
    source_duration: float,
    target_duration: float,
) -> None:
    pad_duration = max(0.0, target_duration - source_duration + 0.2)
    filter_chain = (
        f"scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:force_original_aspect_ratio=decrease,"
        f"pad={VIDEO_WIDTH}:{VIDEO_HEIGHT}:(ow-iw)/2:(oh-ih)/2:color=0x071930,"
        f"fps={FPS},tpad=stop_mode=clone:stop_duration={pad_duration:.3f},"
        f"trim=duration={target_duration:.3f},setpts=PTS-STARTPTS,format=yuv420p"
    )
    _run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(screen_video),
            "-vf",
            filter_chain,
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-crf",
            "20",
            "-threads",
            "1",
            "-r",
            str(FPS),
            str(output),
        ]
    )


def render_video(
    *,
    work_dir: Path,
    screen_video: Path,
    voiceover: Path,
    script: str,
    title: str,
    subtitle: str,
    cta: str,
) -> RenderResult:
    script = clean_text(script, max_length=20_000)
    title = clean_text(title, max_length=180)
    subtitle = clean_text(subtitle, max_length=240)
    cta = clean_text(cta, max_length=220)

    voice_duration = media_duration(voiceover)
    screen_duration = media_duration(screen_video)
    if voice_duration < 6:
        raise ValueError("A locução precisa ter pelo menos seis segundos.")

    intro_duration = min(3.5, max(2.0, voice_duration * 0.10))
    outro_duration = min(4.5, max(2.5, voice_duration * 0.11))
    main_duration = max(1.0, voice_duration - intro_duration - outro_duration)

    intro_png = work_dir / "intro.png"
    outro_png = work_dir / "outro.png"
    thumbnail = work_dir / "thumbnail.jpg"
    intro_video = work_dir / "intro.mp4"
    main_video = work_dir / "main.mp4"
    outro_video = work_dir / "outro.mp4"
    silent_video = work_dir / "silent.mp4"
    subtitles = work_dir / "subtitles.srt"
    output = work_dir / "video.mp4"

    create_intro_card(intro_png, title=title, subtitle=subtitle)
    create_outro_card(outro_png, cta=cta)
    create_thumbnail(
        thumbnail,
        screen_video=screen_video,
        title=title,
        work_dir=work_dir,
    )
    subtitles.write_text(build_srt(script, voice_duration), encoding="utf-8")

    _make_still_video(intro_png, intro_video, intro_duration)
    _make_main_video(
        screen_video,
        main_video,
        source_duration=screen_duration,
        target_duration=main_duration,
    )
    _make_still_video(outro_png, outro_video, outro_duration)

    concat_file = work_dir / "concat.txt"
    concat_file.write_text(
        "\n".join(
            [
                f"file '{intro_video.as_posix()}'",
                f"file '{main_video.as_posix()}'",
                f"file '{outro_video.as_posix()}'",
            ]
        ),
        encoding="utf-8",
    )
    _run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_file),
            "-c",
            "copy",
            str(silent_video),
        ]
    )

    subtitle_filter = (
        f"subtitles={subtitles.as_posix()}:"
        "force_style='FontName=DejaVu Sans,FontSize=22,"
        "PrimaryColour=&H00FFFFFF,OutlineColour=&H00121A25,"
        "BorderStyle=1,Outline=3,Shadow=1,Alignment=2,MarginV=48'"
    )
    _run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(silent_video),
            "-i",
            str(voiceover),
            "-vf",
            subtitle_filter,
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-crf",
            "20",
            "-threads",
            "1",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-ar",
            "48000",
            "-t",
            f"{voice_duration:.3f}",
            "-movflags",
            "+faststart",
            str(output),
        ]
    )

    video_bytes = output.stat().st_size
    thumbnail_bytes = thumbnail.stat().st_size
    if video_bytes < 10_000:
        raise RuntimeError("O vídeo final ficou anormalmente pequeno.")
    return RenderResult(
        duration_seconds=round(media_duration(output), 3),
        video_bytes=video_bytes,
        thumbnail_bytes=thumbnail_bytes,
        video_sha256=hashlib.sha256(output.read_bytes()).hexdigest(),
    )
