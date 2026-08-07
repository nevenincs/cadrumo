"""A real loopback reading endpoint, shared by the suites that need one.

Wiring the semantic reader made every text-PDF extract and confirm depend on a
reading model. The suites that exercise those paths were written long before
that and are about MINTING, IDEMPOTENCY, OVERRIDES, LINKING and DISCREPANCY
REPORTING -- not about what happens when no reader is installed. Without an
endpoint they all stop at a connection error, which says nothing about any of
those contracts.

This serves one: a real :class:`~http.server.ThreadingHTTPServer` on a loopback
port speaking the runtime's ``/api/chat`` wire shape. Real HTTP, the real
provider client, the real router. **No model is loaded and no inference runs.**

It is not a mock and not a patch. Nothing in the code under test is
substituted; only the REPLY is authored, exactly as a real runtime's would be,
and everything downstream of the socket is production code.

**Replies are keyed on the transcription**, never canned. A single fixed payload
would answer every document identically, so a suite comparing two documents
would be comparing the stub to itself -- and an assertion about a discrepancy
between them would pass without the code under test ever being consulted. Each
caller supplies markers drawn from its own documents.

See Also:
    :func:`~application.ledger.transcribe_text_layer`
        Produces the text this endpoint is keyed on.
    ``application/tests/test_provisioning_hardware_contention.py``
        The loopback shape this adopts, so the tree carries one pattern.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import ClassVar, override

from ....core.config import override_settings

__all__ = ["ReaderReply", "serving_a_loopback_reader"]

#: One document's answer: a marker that identifies it in the transcription, and
#: the flat field/anchor object the reader would return for it.
ReaderReply = tuple[str, Mapping[str, str]]


class _ReaderStub(BaseHTTPRequestHandler):
    """A real local endpoint speaking the reading runtime's ``/api/chat`` shape."""

    replies: ClassVar[Sequence[ReaderReply]] = ()
    fallback: ClassVar[Mapping[str, str]] = {}

    def _fields_for(self, prompt: str) -> Mapping[str, str]:
        for marker, fields in self.replies:
            if marker in prompt:
                return fields
        return self.fallback

    def do_POST(self) -> None:
        body = self.rfile.read(int(self.headers.get("content-length", "0")))
        prompt = json.dumps(json.loads(body.decode("utf-8"))["messages"])
        payload = json.dumps(
            {
                "model": "qwen2.5:7b",
                "message": {"role": "assistant", "content": json.dumps(dict(self._fields_for(prompt)))},
                "prompt_eval_count": 100,
                "eval_count": 50,
            },
        ).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    @override
    def log_message(self, format: str, *args: object) -> None:
        """Silence the handler's stderr access log."""


@contextmanager
def serving_a_loopback_reader(
    replies: Sequence[ReaderReply],
    *,
    fallback: Mapping[str, str] | None = None,
) -> Iterator[str]:
    """Serve a real reading endpoint for the duration of the block.

    Args:
        replies: ``(marker, fields)`` pairs. The first marker found in the
            transcription decides the answer, so each document gets its OWN
            printed figures back.
        fallback: Fields returned when no marker matches. Defaults to empty,
            which is the honest answer for a document this caller did not
            describe -- a reader that recovered nothing, rather than one that
            invented another document's values.

    Yields:
        The chat URL, with settings already pointed at it.
    """
    _ReaderStub.replies = tuple(replies)
    _ReaderStub.fallback = dict(fallback or {})
    server = ThreadingHTTPServer(("127.0.0.1", 0), _ReaderStub)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    chat_url = f"http://127.0.0.1:{server.server_port}/api/chat"
    try:
        with override_settings(cadrumo_llm_ollama_chat_url=chat_url):
            yield chat_url
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
