"""复现官方库的 CDN cookie 挑战：第一次 POST 回 307，带 cookie 再来才给数据。

这不是假想场景——2026-11-20 实测 flk.npc.gov.cn 就是这样，
不处理的话整个工具直接抛 HTTPError 307。
"""

import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

from wenlv.corpus.flk import FlkClient

ROWS = [{"bbbs": "abc", "title": "中华人民共和国民法典", "sxx": 3, "gxrq": "2020-05-28"}]


class ChallengeHandler(BaseHTTPRequestHandler):
    seen_posts: list[str] = []

    def do_POST(self):
        ChallengeHandler.seen_posts.append(self.path)
        length = int(self.headers.get("Content-Length") or 0)
        self.rfile.read(length)

        if "wzws_cid" not in (self.headers.get("Cookie") or ""):
            # 第一跳：下发 cookie，跳回同一路径
            self.send_response(307)
            self.send_header("Set-Cookie", "wzws_cid=test; Path=/; HttpOnly")
            self.send_header("Location", self.path)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return

        body = json.dumps({"code": 200, "rows": ROWS}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


class RedirectChallengeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), ChallengeHandler)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def test_follows_307_with_cookie_and_keeps_post(self):
        ChallengeHandler.seen_posts.clear()
        client = FlkClient(timeout=5, base=f"http://127.0.0.1:{self.port}")
        laws = client.search_laws("民法典")

        self.assertEqual(len(laws), 1)
        self.assertEqual(laws[0].title, "中华人民共和国民法典")
        # 两次都是 POST，说明重定向没有把方法降级成 GET
        self.assertEqual(len(ChallengeHandler.seen_posts), 2)


if __name__ == "__main__":
    unittest.main()
