import os
import json
import runpy
import sys

import cv2
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
            'KILN_AUTO_DISPLAY': '0',
        }):
            archive = OCRArchive()
            frame = np.zeros((10, 10, 3), dtype=np.uint8)
            args = ([frame], [None], None, (0, 0, 10, 10), (0, 0, 10, 10))
            archive.save(*args)
            first = next(Path(temp).iterdir())
            size = sum(p.stat().st_size for p in first.iterdir())
            archive.max_bytes = size * 2
            archive._last_full_frame = None
            archive.save(*args)
            archive._last_full_frame = None
            archive.save(*args)
            bursts = sorted(Path(temp).iterdir())
            self.assertEqual(len(bursts), 2)
            self.assertNotIn(first, bursts)
            self.assertTrue(all((p / 'capture.json').is_file() for p in bursts))
            self.assertLessEqual(sum(f.stat().st_size for p in bursts for f in p.iterdir()), archive.max_bytes)

    def test_oversized_burst_does_not_remove_existing_archive(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {
            'KILN_OCR_ARCHIVE_DIR': temp, 'KILN_OCR_ARCHIVE_MAX_BYTES': '1000000',
            'KILN_AUTO_DISPLAY': '0',
        }):
            archive = OCRArchive()
            frame = np.zeros((10, 10, 3), dtype=np.uint8)
            args = ([frame], [None], None, (0, 0, 10, 10), (0, 0, 10, 10))
            archive.save(*args)
            first = next(Path(temp).iterdir())
            archive.max_bytes = 1
            archive.save(*args)
            self.assertTrue((first / 'capture.json').exists())

    def test_color_crops_and_full_frame_every_sixty_seconds(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {
            'KILN_OCR_ARCHIVE_DIR': temp, 'KILN_AUTO_DISPLAY': '0',
        }), patch('kiln.ocr_archive.time.monotonic', side_effect=[0, 59, 60]):
            archive = OCRArchive()
            frame = np.random.default_rng(42).integers(0, 256, (72, 128, 3), dtype=np.uint8)
            args = ([frame] * 12, [None] * 12, None, (10, 20, 30, 15), (3, 2, 20, 10))
            for _ in range(3):
                archive.save(*args)
            bursts = sorted(Path(temp).iterdir())
            self.assertEqual(len(bursts), 3)
            for i, burst in enumerate(bursts):
                report = json.loads((burst / 'capture.json').read_text())
                self.assertEqual(len(report['frames']), 12)
                self.assertEqual((burst / 'full-frame.png').exists(), i != 1)
                crop = cv2.imread(str(burst / 'frame-00.png'))
                np.testing.assert_array_equal(crop, frame[20:35, 10:40])
                self.assertEqual(report['frames'][0]['digits_roi'], [3, 2, 20, 10])
                if i != 1:
                    np.testing.assert_array_equal(cv2.imread(str(burst / 'full-frame.png')), frame)
            full_size = len(OCRArchive._encode(frame)) * 12
            crop_size = sum(p.stat().st_size for p in bursts[1].glob('frame-*.png'))
            self.assertLess(crop_size, full_size / 10)

    def test_missing_display_keeps_metadata_and_can_be_replayed(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {
            'KILN_OCR_ARCHIVE_DIR': temp, 'KILN_AUTO_DISPLAY': '1',
        }):
            OCRArchive().save([np.zeros((72, 128, 3), dtype=np.uint8)], [None], None,
                              (10, 20, 30, 15), (3, 2, 20, 10))
            burst = next(Path(temp).iterdir())
            report = json.loads((burst / 'capture.json').read_text())
            self.assertIsNone(report['frames'][0]['file'])
            output = Path(temp) / 'review'
            with patch.object(sys, 'argv', ['camera_probe', '--input', str(burst), '--output', str(output)]):
                runpy.run_path('scripts/camera_probe.py', run_name='__main__')
            result = json.loads((output / 'report.json').read_text())
            self.assertEqual(result['results'][0]['error'], 'display_not_found_at_capture')

    def test_auto_crop_replay_uses_local_geometry_with_current_settings(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {
            'KILN_OCR_ARCHIVE_DIR': temp, 'KILN_AUTO_DISPLAY': '1',
        }), patch('kiln.ocr_archive.find_display_roi', return_value=(10, 20, 30, 15)):
            frame = np.random.default_rng(42).integers(0, 256, (72, 128, 3), dtype=np.uint8)
            OCRArchive().save([frame], [25], None, (10, 20, 30, 15), (3, 2, 20, 10))
            burst = next(Path(temp).iterdir())
            for current in (False, True):
                output = Path(temp) / ('current' if current else 'original')
                argv = ['camera_probe', '--input', str(burst), '--output', str(output)]
                if current:
                    argv.append('--current-settings')
                with patch.object(sys, 'argv', argv), patch('kiln.vision._run_tesseract', return_value='025'), \
                        patch('kiln.vision.read_digits_temperature', return_value=25) as read:
                    runpy.run_path('scripts/camera_probe.py', run_name='__main__')
                np.testing.assert_array_equal(read.call_args.args[0], frame[22:33, 12:38])
                result = json.loads((output / 'report.json').read_text())
                self.assertEqual(len(result['results']), 1)
                self.assertEqual(result['results'][0]['temperature'], 25)

    def test_successful_burst_is_not_archived(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {
            'KILN_OCR_ARCHIVE_DIR': temp,
        }):
            frame = np.zeros((10, 10, 3), dtype=np.uint8)
            archive = OCRArchive()
            for temperature in (0, 25):
                archive.save([frame], [temperature], temperature, (0, 0, 10, 10), (0, 0, 10, 10))
            self.assertEqual(list(Path(temp).iterdir()), [])


if __name__ == '__main__':
    unittest.main()
