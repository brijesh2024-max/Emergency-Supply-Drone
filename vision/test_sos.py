import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from .sos import inspect_placard, write_placard


class PlacardTest(unittest.TestCase):
    def test_bundled_sign(self):
        result = inspect_placard()
        self.assertEqual(result["label"], "SOS")
        self.assertEqual(result["template_agreement"], 1)
        self.assertEqual(result["review_status"], "pending")

    def test_blank_frame_has_no_alert(self):
        with tempfile.TemporaryDirectory() as location:
            path = Path(location) / "blank.png"
            with patch("vision.sos.LETTERS", ["0" * 15] * 5):
                write_placard(path)
            result = inspect_placard(path)
            self.assertFalse(result["detected"])
            self.assertIsNone(result["label"])
