import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from kiln.ocr_archive import OCRArchive


class OCRArchiveTests(unittest.TestCase):
    def test_rotation_keeps_newest_complete_bursts_within_limit(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {
            'KILN_OCR_ARCHIVE_DIR': temp, 'KILN_OCR_ARCHIVE_MAX_BYTES': '1000000',
        }):
            archive = OCRArchive()
            frame = np.zeros((10, 10, 3), dtype=np.uint8)
            args = ([frame], [25], 25, (0, 0, 10, 10), (0, 0, 10, 10))
            archive.save(*args)
            first = next(Path(temp).iterdir())
            size = sum(p.stat().st_size for p in first.iterdir())
            archive.max_bytes = size * 2
            archive.save(*args)
            archive.save(*args)
            bursts = sorted(Path(temp).iterdir())
            self.assertEqual(len(bursts), 2)
            self.assertNotIn(first, bursts)
            self.assertTrue(all((p / 'capture.json').is_file() for p in bursts))
            self.assertLessEqual(sum(f.stat().st_size for p in bursts for f in p.iterdir()), archive.max_bytes)

    def test_oversized_burst_does_not_remove_existing_archive(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {
            'KILN_OCR_ARCHIVE_DIR': temp, 'KILN_OCR_ARCHIVE_MAX_BYTES': '1000000',
        }):
            archive = OCRArchive()
            frame = np.zeros((10, 10, 3), dtype=np.uint8)
            args = ([frame], [25], 25, (0, 0, 10, 10), (0, 0, 10, 10))
            archive.save(*args)
            first = next(Path(temp).iterdir())
            archive.max_bytes = 1
            archive.save(*args)
            self.assertTrue((first / 'capture.json').exists())


if __name__ == '__main__':
    unittest.main()
