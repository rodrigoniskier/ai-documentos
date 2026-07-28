import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from capture import (
    DEFAULT_TARGET_URL,
    _run,
    demo_identity,
    validate_target_url,
)


class CaptureHelpersTests(unittest.TestCase):
    def test_target_url_accepts_only_configured_https_host(self):
        with patch.dict(os.environ, {}, clear=False):
            self.assertEqual(validate_target_url(None), DEFAULT_TARGET_URL)

    def test_target_url_rejects_http(self):
        with self.assertRaises(ValueError):
            validate_target_url("http://rn-document-platform.onrender.com/")

    def test_target_url_rejects_another_host(self):
        with self.assertRaises(ValueError):
            validate_target_url("https://example.org/")

    def test_target_url_rejects_credentials_and_non_root_path(self):
        for value in (
            "https://user:password@rn-document-platform.onrender.com/",
            "https://rn-document-platform.onrender.com/admin/",
        ):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_target_url(value)

    def test_demo_identity_is_deterministic_and_synthetic(self):
        first = demo_identity("token-seguro", "video-final-2026")
        second = demo_identity("token-seguro", "video-final-2026")
        other = demo_identity("token-seguro", "outro-job")
        self.assertEqual(first, second)
        self.assertNotEqual(first.email, other.email)
        self.assertTrue(first.email.endswith("@example.com"))
        self.assertNotIn("video-final-2026", first.email)
        self.assertGreaterEqual(len(first.password), 20)

    def test_password_is_hidden_from_identity_repr(self):
        identity = demo_identity("token-seguro", "video-final-2026")
        self.assertNotIn(identity.password, repr(identity))

    def test_ffmpeg_timeout_becomes_explicit_runtime_error(self):
        expired = subprocess.TimeoutExpired(["ffmpeg"], 600)
        with patch("capture.subprocess.run", side_effect=expired):
            with self.assertRaisesRegex(
                RuntimeError,
                "excedeu o limite de 600 segundos",
            ):
                _run(["ffmpeg"], timeout=600)


if __name__ == "__main__":
    unittest.main()
