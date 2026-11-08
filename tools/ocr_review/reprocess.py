#!/usr/bin/env python3
"""Re-run OCR for each archive image; collect unresolved examples for labeling."""
import argparse
import json
from pathlib import Path
import shutil
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import cv2
from kiln.vision import crop_digits, read_digits_temperature, read_kiln_temperature
from server import load_items


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, default=ROOT / 'data/ocr-archive')
    parser.add_argument('--database', type=Path, default=ROOT / 'data/ocr-review/reviews.sqlite3')
    parser.add_argument('--failed', type=Path, default=ROOT / 'data/ocr-review/unrecognized')
    retry = parser.add_mutually_exclusive_group()
    retry.add_argument('--again', action='store_true', help='retry items already processed')
    retry.add_argument('--unrecognized', action='store_true', help='retry only unrecognized items')
    retry.add_argument('--id', action='append', help='retry a specific item ID (repeatable)')
    args = parser.parse_args()
    if not args.archive.is_dir():
        parser.error('archive directory does not exist')
    items, errors = load_items(args.archive)
    if errors:
        parser.error('\n'.join(errors))
    args.database.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(args.database, timeout=30) as db:
        db.execute('CREATE TABLE IF NOT EXISTS ocr_attempts (id TEXT PRIMARY KEY, value REAL, status TEXT NOT NULL)')
        attempts = dict(db.execute('SELECT id, status FROM ocr_attempts'))
        done = set() if args.again else set(attempts)
        # Prioritize images that had no OCR result when captured.
        pending = sorted((x for x in items if (x['id'] in args.id if args.id else attempts.get(x['id']) == 'unrecognized' if args.unrecognized else x['id'] not in done)), key=lambda x: (x['ocr'] is not None, x['id']))
        print(f'{len(pending)} images and records to process ({len(done)} already processed)', flush=True)
        for n, item in enumerate(pending, 1):
            path = args.archive / item['image'] if item['image'] else None
            image = cv2.imread(str(path)) if path else None
            if image is None:
                value, status = None, 'image_missing'
            elif item['kind'] == 'frame' and item.get('digits_roi'):
                value = read_digits_temperature(crop_digits(image, tuple(item['digits_roi'])))
                status = 'ok' if value is not None else 'unrecognized'
            elif item['kind'] == 'snapshot':
                value = read_kiln_temperature(image)
                status = 'ok' if value is not None else 'unrecognized'
            else:
                value, status = None, 'unknown_geometry'
            with db:
                db.execute('INSERT OR REPLACE INTO ocr_attempts(id, value, status) VALUES (?, ?, ?)', (item['id'], value, status))
            if status == 'unrecognized' and path:
                target = args.failed / item['burst']
                target.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, target / path.name)
                (target / (path.name + '.json')).write_text(json.dumps({'id': item['id'], 'source': item['image'], 'expected': None}, ensure_ascii=False, indent=2) + '\n')
            if n % 50 == 0 or n == len(pending):
                print(f'{n}/{len(pending)} processed', flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
