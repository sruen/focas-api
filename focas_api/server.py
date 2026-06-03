"""Minimal production-friendly HTTP server for FOCAS GPT Actions."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from .service import audit_match_input, analyze_match_input, verify_independent_judgement

MAX_BODY_BYTES = 2 * 1024 * 1024


class FocasApiHandler(BaseHTTPRequestHandler):
    server_version = "FOCAS-API/1.1.6-material"

    def _write_text(self, status: int, body: str, content_type: str) -> None:
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

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
            self._write_json(200, {"status": "ok", "service": "focas-api", "engine_version": "1.1.6-material"})
            return
        if self.path == "/openapi.yaml":
            schema_path = Path(__file__).with_name("openapi.yaml")
            self._write_text(200, schema_path.read_text(encoding="utf-8"), "application/yaml")
            return
        self._write_json(404, {"error": "not_found"})

    def _read_json_body(self) -> dict[str, Any]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise ValueError("invalid_content_length") from exc
        if length <= 0 or length > MAX_BODY_BYTES:
            raise ValueError(f"request_body_size_invalid; max_bytes={MAX_BODY_BYTES}")
        request = json.loads(self.rfile.read(length).decode("utf-8"))
        if not isinstance(request, dict):
            raise ValueError("request body must be a JSON object")
        return request

    def do_POST(self) -> None:  # noqa: N802
        if self.path not in {"/v1/audit", "/v1/analyze", "/v1/verify"}:
            self._write_json(404, {"error": "not_found"})
            return
        if not self._authorized():
            self._write_json(401, {"error": "unauthorized"})
            return
        try:
            request = self._read_json_body()
            if self.path == "/v1/verify":
                audit_payload = request.get("audit_payload")
                independent_judgement = request.get("independent_judgement")
                if not isinstance(audit_payload, dict):
                    raise ValueError("audit_payload must be a JSON object")
                if not isinstance(independent_judgement, dict):
                    raise ValueError("independent_judgement must be a JSON object")
                payload = verify_independent_judgement(
                    audit_payload=audit_payload,
                    independent_judgement=independent_judgement,
                )
            else:
                match_input = request.get("match_input", request)
                if not isinstance(match_input, dict):
                    raise ValueError("match_input must be a JSON object")
                include_report = bool(request.get("include_report", False))
                # /v1/analyze remains as a compatibility alias, but returns a material audit only.
                if self.path == "/v1/analyze":
                    payload = analyze_match_input(match_input, include_report=include_report)
                else:
                    payload = audit_match_input(match_input, include_report=include_report)
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            self._write_json(400, {"error": "invalid_request", "detail": str(exc)})
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
