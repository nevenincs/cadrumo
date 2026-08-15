"""The recording endpoint shared by this package's real-HTTP telemetry suites.

The loopback start/stop plumbing lives in
:mod:`cadrumo.tests.loopback_recording_server`, which deliberately declines to
own handler classes because the recorded event shape differs between suites --
the two diagnostics suites record ``{path, body}`` and have no interest in the
content type. Both suites in THIS package assert on the content type, so they
share one shape, and one shape wants one definition.

This exists so neither suite has to import the other. A test module importing a
private name from a sibling test module is what broke collection here once
already, when the plumbing moved to its canonical home and the importing suite
was left behind.
"""

from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from queue import Queue
from typing import ClassVar, override

__all__ = ["RecordingTelemetryEndpoint"]


class RecordingTelemetryEndpoint(BaseHTTPRequestHandler):
    """Local telemetry-collector-shaped endpoint used to inspect the real HTTP POST."""

    events: ClassVar[Queue[dict[str, object]]]

    def do_POST(self) -> None:
        body = self.rfile.read(int(self.headers.get("content-length", "0")))
        self.events.put(
            {
                "path": self.path,
                "content_type": self.headers.get("content-type"),
                "body": json.loads(body.decode("utf-8")),
            },
        )
        self.send_response(HTTPStatus.OK)
        self.send_header("content-length", "0")
        self.end_headers()

    @override
    def log_message(self, format: str, *args: object) -> None:
        """Silence stdlib request logging during tests."""
