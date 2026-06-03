"""Minimal production-friendly HTTP server for FOCAS GPT Actions."""

from __future__ import annotations

import argparse
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from .service import analyze_match_input

MAX_BODY_BYTES = 2 * 1024 * 1024


class FocasApiHandler(BaseHTTPRequestHandler):
    server_version = "FOCAS-API/1.1.5"

    def _write_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _authorized(self) -> bool:
        expected = os.getenv("FOCAS_API_KEY")
        if not expected:
            return True
        authorization = self.headers.get("Authorization", "")
        return authorization == f"Bearer {expected}"

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            self._write_json(200, {"status": "ok", "service": "focas-api", "engine_version": "1.1.5"})
            return
        self._write_json(404, {"error": "not_found"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/v1/analyze":
            self._write_json(404, {"error": "not_found"})
            return
        if not self._authorized():
            self._write_json(401, {"error": "unauthorized"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._write_json(400, {"error": "invalid_content_length"})
            return
        if length <= 0 or length > MAX_BODY_BYTES:
            self._write_json(413, {"error": "request_body_size_invalid", "max_bytes": MAX_BODY_BYTES})
            return
        try:
            request = json.loads(self.rfile.read(length).decode("utf-8"))
            if not isinstance(request, dict):
                raise ValueError("request body must be a JSON object")
            match_input = request.get("match_input", request)
            if not isinstance(match_input, dict):
                raise ValueError("match_input must be a JSON object")
            include_report = bool(request.get("include_report", False))
            payload = analyze_match_input(match_input, include_report=include_report)
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            self._write_json(400, {"error": "invalid_match_input", "detail": str(exc)})
            return
        except Exception as exc:  # pragma: no cover - defensive service boundary
            self._write_json(500, {"error": "analysis_failed", "detail": str(exc)})
            return
        self._write_json(200, payload)

    def log_message(self, format: str, *args: Any) -> None:
        print(f"{self.client_address[0]} - {format % args}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve FOCAS as a GPT Action compatible JSON API.")
    parser.add_argument("--host", default=os.getenv("FOCAS_API_HOST", "0.0.0.0"))
    parser.add_argument("--port", default=int(os.getenv("PORT", "8787")), type=int)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), FocasApiHandler)
    print(f"FOCAS API listening on http://{args.host}:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
