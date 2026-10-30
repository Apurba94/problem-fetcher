"""HTTP receiver for the Competitive Companion browser extension.

The extension POSTs one JSON document per problem to http://localhost:<port>/ (configure the port in its
settings; 10043 and 27121 are common defaults). Each payload becomes a problem folder."""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .model import Problem
from .workspace import write_problem

DEFAULT_PORT = 10043


class _Handler(BaseHTTPRequestHandler):
    server_version = "problem-fetcher/0.1"

    def log_message(self, fmt, *args):          # quiet by default
        if getattr(self.server, "verbose", False):
            super().log_message(fmt, *args)

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length)
        try:
            data = json.loads(raw.decode("utf-8"))
            problem = Problem.from_companion(data)
            folder = write_problem(self.server.root, problem, self.server.lang, self.server.template_dir)
        except (ValueError, KeyError, OSError) as exc:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(("error: %s" % exc).encode())
            return
        self.server.received.append((problem, folder))
        if self.server.on_problem:
            self.server.on_problem(problem, folder)
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"folder": folder}).encode())

    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"problem-fetcher is listening; send problems with Competitive Companion")


def make_server(root, port=DEFAULT_PORT, lang="py", template_dir=None, on_problem=None, verbose=False, host="127.0.0.1"):
    srv = ThreadingHTTPServer((host, port), _Handler)
    srv.root, srv.lang, srv.template_dir, srv.on_problem, srv.verbose = root, lang, template_dir, on_problem, verbose
    srv.received = []
    return srv


def serve_in_background(root, port=0, **kw):
    """Start a receiver on a background thread (port=0 picks a free port). Returns the server."""
    srv = make_server(root, port, **kw)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv
