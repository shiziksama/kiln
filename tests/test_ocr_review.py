import importlib.util
import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

spec = importlib.util.spec_from_file_location('ocr_review_server', Path(__file__).resolve().parents[1] / 'tools/ocr_review/server.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ReviewServerTests(unittest.TestCase):
    def test_inventory_and_persistent_review(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = root / 'archive'
            burst = archive / 'burst-1'
            burst.mkdir(parents=True)
            (burst / 'frame-00.png').write_bytes(b'image')
            (burst / 'full-frame.png').write_bytes(b'snapshot')
            (burst / 'orphan.png').write_bytes(b'orphan')
            (burst / 'capture.json').write_text(json.dumps({'temperature': 25, 'frames': [
                {'file': 'frame-00.png', 'temperature': 25},
                {'file': None, 'temperature': None},
            ]}))
            database = root / 'reviews.sqlite3'
            server = module.ReviewServer(('127.0.0.1', 0), archive, database)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f'http://127.0.0.1:{server.server_port}'
            try:
                def get():
                    with urlopen(base + '/api/items') as response:
                        return json.load(response)['items']
                def save(data):
                    req = Request(base + '/api/review', json.dumps(data).encode(), {'Content-Type': 'application/json'})
                    with urlopen(req) as response:
                        return json.load(response)
                items = get()
                self.assertEqual(len(items), 4)  # two records, snapshot, orphan
                self.assertEqual(sum(item['image'] is None for item in items), 1)
                self.assertEqual(save({'id': items[0]['id'], 'decision': 'accept'})['value'], 25)
                self.assertEqual(save({'id': items[2]['id'], 'decision': 'correct', 'value': 27})['value'], 27)
                self.assertEqual(get()[0]['review']['value'], 25)
                self.assertEqual(get()[2]['review']['value'], 27)
                import sqlite3
                with sqlite3.connect(database) as db:
                    db.execute('INSERT INTO ocr_attempts VALUES (?, ?, ?)', (items[0]['id'], 26, 'ok'))
                self.assertEqual(get()[0]['attempt']['value'], 26)
                with self.assertRaises(HTTPError):
                    save({'id': items[0]['id'], 'decision': 'accept', 'value': 25})
                self.assertEqual(save({'id': items[0]['id'], 'decision': 'accept', 'value': 26})['value'], 26)
                with self.assertRaises(HTTPError):
                    save({'id': items[1]['id'], 'decision': 'accept'})
                with self.assertRaises(HTTPError):
                    save({'id': items[0]['id'], 'decision': 'correct', 'value': 1000})
            finally:
                server.shutdown()
                server.server_close()
                thread.join()
            reopened = module.ReviewServer(('127.0.0.1', 0), archive, database)
            try:
                with sqlite3.connect(database) as db:
                    self.assertEqual(db.execute('SELECT count(*) FROM reviews').fetchone()[0], 2)
            finally:
                reopened.server_close()


if __name__ == '__main__':
    unittest.main()
