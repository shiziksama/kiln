from pathlib import Path
import unittest
from unittest.mock import patch

import cv2
import numpy as np

from kiln.vision import _read_with_tesseract, read_kiln_temperature

FIXTURES = Path(__file__).parent / 'fixtures'


class DisplayOCRTests(unittest.TestCase):
    def test_real_displays_at_different_positions(self):
        for value in (25, 26):
            display = cv2.imread(str(FIXTURES / f'display-{value:03}.png'))
            for x, y in ((490, 210), (700, 400)):
                frame = np.zeros((720, 1280, 3), np.uint8)
                h, w = display.shape[:2]
                frame[y:y+h, x:x+w] = display
                cv2.rectangle(frame, (1000, 500), (1200, 600), (0, 0, 255), -1)
                with self.subTest(value=value, position=(x, y)):
                    self.assertEqual(read_kiln_temperature(frame), value)

    def test_no_display_has_no_temperature(self):
        self.assertIsNone(read_kiln_temperature(np.zeros((720, 1280, 3), np.uint8)))

    def test_truncated_and_disagreeing_results_are_rejected(self):
        image = cv2.imread(str(FIXTURES / 'display-025.png'))
        for outputs in (['02', '02', '02'], ['025', '028', '029']):
            with patch('kiln.vision._run_tesseract', side_effect=outputs):
                self.assertEqual(_read_with_tesseract(image), '')

    def test_all_digit_shapes_and_mixed_numbers(self):
        # Synthetic OCR fixtures exercise every numeral; this is not a decoder.
        patterns = ['abcdef', 'bc', 'abged', 'abgcd', 'fgbc', 'afgcd', 'afgecd', 'abc', 'abcdefg', 'abfgcd']
        strokes = {
            'a': ((8, 5), (30, 5)), 'b': ((32, 8), (32, 28)),
            'c': ((32, 34), (32, 54)), 'd': ((8, 57), (30, 57)),
            'e': ((5, 34), (5, 54)), 'f': ((5, 8), (5, 28)),
            'g': ((8, 31), (30, 31)),
        }
        for text in [str(d) * 3 for d in range(10)] + ['012', '345', '678', '901', '025', '026', '123', '456', '789']:
            mask = np.full((63, 126), 255, np.uint8)
            for i, digit in enumerate(text):
                for stroke in patterns[int(digit)]:
                    a, b = strokes[stroke]
                    cv2.line(mask, (a[0] + 42*i, a[1]), (b[0] + 42*i, b[1]), 0, 5)
            mask = cv2.resize(mask, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
            mask = cv2.copyMakeBorder(mask, 24, 24, 24, 24, cv2.BORDER_CONSTANT, value=255)
            with self.subTest(text=text):
                with patch('kiln.vision._prepare_for_ocr', return_value=mask):
                    self.assertEqual(_read_with_tesseract(np.zeros((1, 1, 3), np.uint8)), text)


if __name__ == '__main__':
    unittest.main()
