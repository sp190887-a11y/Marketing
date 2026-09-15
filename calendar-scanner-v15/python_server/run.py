from __future__ import annotations

import os
from socketserver import ThreadingMixIn
from wsgiref.simple_server import WSGIServer, make_server

from app import application


class ThreadingWSGIServer(ThreadingMixIn, WSGIServer):
    daemon_threads = True


if __name__ == "__main__":
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8080"))
    with make_server(host, port, application, server_class=ThreadingWSGIServer) as server:
        print(f"Нарисуй сам: http://{host}:{port}")
        server.serve_forever()
