#!/usr/bin/env python3
"""Compare the current OCR with reviewed archive images."""
import argparse
from collections import Counter
import json
from pathlib import Path
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
    parser.add_argument('--output', type=Path, default=ROOT / 'data/ocr-review/check-results.json')
    args = parser.parse_args()
    items, errors = load_items(args.archive)
    if not args.database.exists():
        parser.error('Review database does not exist; start the review page first')
    with sqlite3.connect(args.database) as db:
        reviews = {row[0]: (row[1], row[2]) for row in db.execute('SELECT id, decision, value FROM reviews')}
    results, counts = [], Counter()
    for item in items:
        review = reviews.get(item['id'])
        if not review:
            counts['unreviewed'] += 1
            continue
        if review[0] == 'unreadable':
            counts['unreadable'] += 1
            continue
        image = cv2.imread(str(args.archive / item['image'])) if item['image'] else None
        if image is None:
            actual, outcome = None, 'image_missing'
        else:
            if item['kind'] == 'frame':
                roi = item.get('digits_roi')
                actual = read_digits_temperature(crop_digits(image, tuple(roi))) if roi else None
                outcome = 'missing_geometry' if not roi else None
            elif item['kind'] == 'snapshot':
                actual, outcome = read_kiln_temperature(image), None
            else:
                actual, outcome = None, 'unknown_geometry'
            outcome = outcome or ('correct' if actual == review[1] else 'not_recognized' if actual is None else 'incorrect')
        counts[outcome] += 1
        results.append({'id': item['id'], 'expected': review[1], 'actual': actual, 'outcome': outcome})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({'counts': dict(counts), 'errors': errors, 'results': results}, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({'total': len(items), 'counts': dict(counts), 'archive_errors': len(errors), 'report': str(args.output)}, ensure_ascii=False))
    if errors or any(counts[k] for k in ('incorrect', 'not_recognized', 'image_missing', 'missing_geometry', 'unknown_geometry')):
        return 1
    return 2 if counts['unreviewed'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
