#!/usr/bin/env python3
"""Local, resumable review of every image and frame record in an OCR archive."""
import argparse
import json
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sqlite3
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parents[2]
PAGE = Path(__file__).with_name('index.html')


def load_items(root):
    items, referenced, errors = [], set(), []
    for manifest in sorted(root.glob('*/capture.json')):
        try:
            data = json.loads(manifest.read_text())
            frames = data['frames']
            if not isinstance(frames, list):
                raise ValueError('frames is not a list')
            for index, frame in enumerate(frames):
                name = frame.get('file')
                image = manifest.parent / name if name else None
                if image and (image.parent != manifest.parent or image.suffix.lower() != '.png'):
                    raise ValueError('invalid image path')
                if image:
                    referenced.add(image.relative_to(root).as_posix())
                items.append({'id': f'{manifest.parent.name}/frame-record-{index:03}',
                              'image': image.relative_to(root).as_posix() if image and image.is_file() else None,
                              'image_name': name, 'burst': manifest.parent.name,
                              'kind': 'frame', 'index': index,
                              'ocr': frame.get('temperature'), 'burst_ocr': data.get('temperature'),
                              'digits_roi': frame.get('digits_roi')})
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
            errors.append(f'{manifest.relative_to(root)}: {error}')
    # Include snapshots and any other PNG, even if it is absent from a manifest.
    for image in sorted(root.glob('*/*.png')):
        relative = image.relative_to(root).as_posix()
        if relative not in referenced:
            items.append({'id': relative, 'image': relative, 'image_name': image.name,
                          'burst': image.parent.name, 'kind': 'snapshot' if image.name == 'full-frame.png' else 'other',
                          'index': None, 'ocr': None, 'burst_ocr': None})
    return items, errors


class ReviewServer(ThreadingHTTPServer):
    def __init__(self, address, archive, database):
        self.archive = archive.resolve()
        self.items, self.errors = load_items(self.archive)
        self.by_id = {item['id']: item for item in self.items}
        self.database = database
        database.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(database) as db:
            db.execute('CREATE TABLE IF NOT EXISTS reviews (id TEXT PRIMARY KEY, decision TEXT NOT NULL, value INTEGER, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)')
            db.execute('CREATE TABLE IF NOT EXISTS ocr_attempts (id TEXT PRIMARY KEY, value REAL, status TEXT NOT NULL)')
        super().__init__(address, Handler)


class Handler(BaseHTTPRequestHandler):
    def respond(self, code, content, content_type):
        self.send_response(code)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(content)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(content)

    def json(self, code, obj):
        self.respond(code, json.dumps(obj, ensure_ascii=False).encode(), 'application/json; charset=utf-8')

    def do_GET(self):
        parsed = urlsplit(self.path)
        if parsed.path == '/':
            return self.respond(200, PAGE.read_bytes(), 'text/html; charset=utf-8')
        if parsed.path == '/api/items':
            with sqlite3.connect(self.server.database) as db:
                reviews = {r[0]: {'decision': r[1], 'value': r[2]} for r in db.execute('SELECT id, decision, value FROM reviews')}
                attempts = {r[0]: {'value': r[1], 'status': r[2]} for r in db.execute('SELECT id, value, status FROM ocr_attempts')}
            return self.json(200, {'items': [{**item, 'review': reviews.get(item['id']), 'attempt': attempts.get(item['id'])} for item in self.server.items], 'errors': self.server.errors})
        if parsed.path == '/api/export':
            with sqlite3.connect(self.server.database) as db:
                reviews = {r[0]: {'decision': r[1], 'value': r[2], 'updated_at': r[3]} for r in db.execute('SELECT id, decision, value, updated_at FROM reviews')}
            return self.json(200, {'items': [{**item, 'review': reviews.get(item['id'])} for item in self.server.items], 'errors': self.server.errors})
        if parsed.path == '/image':
            image_id = parse_qs(parsed.query).get('id', [''])[0]
            item = self.server.by_id.get(image_id)
            if not item or not item['image']:
                return self.send_error(404)
            path = (self.server.archive / item['image']).resolve()
            if not path.is_relative_to(self.server.archive) or not path.is_file():
                return self.send_error(404)
            return self.respond(200, path.read_bytes(), mimetypes.guess_type(path.name)[0] or 'application/octet-stream')
        self.send_error(404)

    def do_POST(self):
        if self.path != '/api/review':
            return self.send_error(404)
        try:
            if self.headers.get_content_type() != 'application/json':
                raise ValueError('invalid content type')
            length = int(self.headers.get('Content-Length', '0'))
            if length <= 0 or length > 4096:
                raise ValueError('invalid request length')
            data = json.loads(self.rfile.read(length))
            item = self.server.by_id[data['id']]
            decision = data['decision']
            if decision not in ('accept', 'correct', 'unreadable'):
                raise ValueError('invalid decision')
            if decision == 'accept':
                with sqlite3.connect(self.server.database) as db:
                    attempt = db.execute('SELECT value FROM ocr_attempts WHERE id = ?', (item['id'],)).fetchone()
                value = attempt[0] if attempt is not None else item['ocr']
                if not isinstance(value, (int, float)) or isinstance(value, bool) or not 0 <= value <= 999 or not float(value).is_integer():
                    raise ValueError('no valid OCR result to accept')
                value = int(value)
                if data.get('value', value) != value:
                    raise ValueError('OCR result changed; reload')
            elif decision == 'correct':
                if item['image'] is None:
                    raise ValueError('cannot label a missing image')
                value = data.get('value')
                if type(value) is not int or not 0 <= value <= 999:
                    raise ValueError('invalid temperature')
            else:
                value = None
            with sqlite3.connect(self.server.database) as db:
                db.execute('INSERT INTO reviews(id, decision, value) VALUES (?, ?, ?) ON CONFLICT(id) DO UPDATE SET decision=excluded.decision, value=excluded.value, updated_at=CURRENT_TIMESTAMP', (item['id'], decision, value))
            return self.json(200, {'decision': decision, 'value': value})
        except (ValueError, TypeError, KeyError, json.JSONDecodeError):
            return self.json(400, {'error': 'Invalid review'})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, default=ROOT / 'data/ocr-archive')
    parser.add_argument('--database', type=Path, default=ROOT / 'data/ocr-review/reviews.sqlite3')
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    if not args.archive.is_dir():
        parser.error(f'Archive directory does not exist: {args.archive}')
    server = ReviewServer(('127.0.0.1', args.port), args.archive, args.database)
    print(f'Open http://127.0.0.1:{server.server_port}/ — {len(server.items)} items, {len(server.errors)} errors', flush=True)
    server.serve_forever()


if __name__ == '__main__':
    main()
