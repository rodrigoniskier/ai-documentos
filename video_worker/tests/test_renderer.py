import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from renderer import (
    _run,
    build_srt,
    clean_text,
    create_intro_card,
    sanitize_job_id,
)


class RendererHelpersTests(unittest.TestCase):
    def test_sanitize_job_id_accepts_safe_identifier(self):
        self.assertEqual(sanitize_job_id("rn-video_2026-07-25"), "rn-video_2026-07-25")

    def test_sanitize_job_id_rejects_path_traversal(self):
        with self.assertRaises(ValueError):
            sanitize_job_id("../../segredo")

    def test_clean_text_collapses_whitespace(self):
        self.assertEqual(clean_text("  RN   DocumentAI \n agora ", max_length=50), "RN DocumentAI agora")

    def test_build_srt_covers_full_duration(self):
        srt = build_srt(
            "Primeira frase. Segunda frase com um pouco mais de conteúdo.",
            12.5,
        )
        self.assertIn("00:00:00,000", srt)
        self.assertIn("00:00:12,500", srt)
        self.assertIn("Primeira frase.", srt)
        self.assertIn("Segunda frase", srt)

    def test_intro_card_has_expected_dimensions(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "intro.png"
            create_intro_card(
                output,
                title="Planos de Ensino com inteligência artificial",
                subtitle="Personalizados e editáveis.",
            )
            with Image.open(output) as image:
                self.assertEqual(image.size, (1920, 1080))

    def test_ffmpeg_commands_use_low_memory_defaults(self):
        with patch("renderer.subprocess.run") as run:
            run.return_value.returncode = 0
            run.return_value.stderr = ""
            _run(["ffmpeg", "-y", "-i", "input.mp4", "output.mp4"], timeout=60)

        command = run.call_args.args[0]
        self.assertIn("-filter_threads", command)
        self.assertEqual(command[command.index("-filter_threads") + 1], "1")
        self.assertEqual(run.call_args.kwargs["timeout"], 60)


if __name__ == "__main__":
    unittest.main()
