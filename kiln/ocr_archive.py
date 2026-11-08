"""Size-bounded capture of OCR bursts for offline investigation."""
import json
import os
from pathlib import Path
import shutil
import time

import cv2

from kiln.vision import crop_display, find_display_roi


class OCRArchive:
    def __init__(self):
        self.root = Path(os.getenv('KILN_OCR_ARCHIVE_DIR', 'data/ocr-archive'))
        self._last_full_frame = None
        self.max_bytes = max(0, int(os.getenv('KILN_OCR_ARCHIVE_MAX_BYTES', '10000000000')))

    def save(self, frames, values, temperature, display_roi, digits_roi):
        if temperature is not None or not frames or not self.max_bytes:
            return
        directory = None
        try:
            self.root.mkdir(parents=True, exist_ok=True)
            now = time.monotonic()
            save_full = self._last_full_frame is None or now - self._last_full_frame >= 60
            report = {
                'format_version': 2,
                'frames': [],
                'full_frame': 'full-frame.png' if save_full else None,
                'temperature': temperature,
                'frame_temperatures': values,
                'display_roi': display_roi,
                'digits_roi': digits_roi,
                'settings': {name: os.getenv(name, default) for name, default in (
                    ('KILN_AUTO_DISPLAY', '1'), ('KILN_OCR_CHANNEL', 'green'),
                    ('KILN_OCR_DIGITS', '3'),
                )},
            }
            files = {}
            auto = os.getenv('KILN_AUTO_DISPLAY', '1') == '1'
            for i, frame in enumerate(frames):
                roi = find_display_roi(frame, display_roi) if auto else display_roi
                entry = {'file': None, 'source_roi': roi, 'temperature': values[i]}
                if roi is not None:
                    # Keep the whole colored panel, including the border around digits.
                    crop = crop_display(frame, roi)
                    if crop.size:
                        height, width = crop.shape[:2]
                        entry.update({
                            'file': f'frame-{i:02}.png',
                            'display_roi': (0, 0, width, height),
                            'digits_roi': (2, 2, width - 4, height - 4) if auto else digits_roi,
                        })
                        files[entry['file']] = self._encode(crop)
                report['frames'].append(entry)
            if save_full:
                files['full-frame.png'] = self._encode(frames[-1])
            files['capture.json'] = (json.dumps(report, indent=2) + '\n').encode()

            size = sum(len(data) for data in files.values())
            if size > self.max_bytes:
                print('OCR archive burst exceeds size limit; skipped', flush=True)
                return
            used = sum(p.stat().st_size for p in self.root.rglob('*') if p.is_file() and not p.is_symlink())
            archives = sorted(p for p in self.root.glob('burst-*')
                              if p.is_dir() and not p.is_symlink() and (p / 'capture.json').is_file())
            for old in archives:
                if used + size <= self.max_bytes:
                    break
                old_size = sum(p.stat().st_size for p in old.rglob('*') if p.is_file() and not p.is_symlink())
                shutil.rmtree(old)
                used -= old_size
            if used + size > self.max_bytes:
                print('OCR archive full; burst skipped', flush=True)
                return
            directory = self.root / f'burst-{time.time_ns()}'
            directory.mkdir()
            # Write the manifest last, so incomplete bursts are never treated as complete.
            for name, data in files.items():
                if name != 'capture.json':
                    (directory / name).write_bytes(data)
            (directory / 'capture.json').write_bytes(files['capture.json'])
            if save_full:
                self._last_full_frame = now
        except (OSError, cv2.error) as error:
            if directory is not None:
                shutil.rmtree(directory, ignore_errors=True)
            print(f'OCR archive failed: {error}', flush=True)

    @staticmethod
    def _encode(frame):
        ok, encoded = cv2.imencode('.png', frame)
        if not ok:
            raise OSError('Cannot encode archive frame')
        return encoded.tobytes()
