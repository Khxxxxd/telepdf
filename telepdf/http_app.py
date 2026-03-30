from __future__ import annotations

import json
import mimetypes
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict
from urllib.parse import urlparse

from .config import STATIC_DIR, ensure_data_dir
from .telegram_service import TelepdfArchiver


class AppServer:
    def __init__(self) -> None:
        ensure_data_dir()
        self.archiver = TelepdfArchiver()

    def build_handler(self):
        archiver = self.archiver

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                if self._route_path() == "/api/status":
                    self._send_json(HTTPStatus.OK, archiver.get_status())
                    return
                self._serve_static()

            def do_HEAD(self) -> None:
                self._serve_static(include_body=False)

            def do_POST(self) -> None:
                try:
                    payload = self._read_json()
                    path = self._route_path()
                    if path == "/api/config":
                        response = archiver.save_config(
                            api_id=payload.get("api_id", ""),
                            api_hash=payload.get("api_hash", ""),
                            phone=payload.get("phone", ""),
                        )
                    elif path == "/api/auth/send-code":
                        response = archiver.send_code()
                    elif path == "/api/auth/verify":
                        response = archiver.verify_code(
                            code=payload.get("code", ""),
                            password=payload.get("password", ""),
                        )
                    elif path == "/api/downloads/start":
                        response = archiver.start_download(
                            source_identifier=payload.get("source", ""),
                            output_dir=payload.get("output_dir", ""),
                        )
                    else:
                        self._send_json(HTTPStatus.NOT_FOUND, {"error": "Endpoint not found."})
                        return
                except ValueError as exc:
                    self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
                    return
                except Exception as exc:  # pragma: no cover - handled in runtime
                    self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc)})
                    return

                self._send_json(HTTPStatus.OK, response)

            def _read_json(self) -> Dict[str, Any]:
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0:
                    return {}
                raw = self.rfile.read(length)
                return json.loads(raw.decode("utf-8"))

            def _send_json(self, status: HTTPStatus, payload: Dict[str, Any]) -> None:
                body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _route_path(self) -> str:
                return urlparse(self.path).path

            def _serve_static(self, include_body: bool = True) -> None:
                route_path = self._route_path()
                relative_path = route_path if route_path != "/" else "/index.html"
                target_path = (STATIC_DIR / relative_path.lstrip("/")).resolve()
                if not str(target_path).startswith(str(STATIC_DIR.resolve())) or not target_path.exists():
                    self.send_error(HTTPStatus.NOT_FOUND, "Not found")
                    return
                mime_type, _ = mimetypes.guess_type(str(target_path))
                content = target_path.read_bytes()
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", mime_type or "application/octet-stream")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                if include_body:
                    self.wfile.write(content)

            def log_message(self, format: str, *args: Any) -> None:
                return

        return Handler


def run_server(host: str = "127.0.0.1", port: int = 8000) -> None:
    app = AppServer()
    server = ThreadingHTTPServer((host, port), app.build_handler())
    print(f"TelePDF running on http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
