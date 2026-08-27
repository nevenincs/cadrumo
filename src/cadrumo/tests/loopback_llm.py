"""Loopback HTTP plumbing for suites that dispatch against a real inference endpoint.

Every suite exercising the client, the adapters or a service that reaches them
needs a REAL socket: the question those tests ask is whether a request left the
process and what crossed the wire, and only an endpoint can answer it. A patch
at the transport seam answers a different question, so each of these suites
correctly stood up a ``ThreadingHTTPServer`` on loopback.

What they should not each own is the SAME twelve lines of bind-thread-shutdown
plumbing and the same reply-envelope literals. Those were copied verbatim across
more than a dozen modules, and a copy is where drift starts: one grew a
``join`` timeout the others lacked, several spelled the same Ollama envelope with
different token counts for no reason a reader could recover.

**The distinctive behaviour deliberately stays with the caller.** These suites
differ in ways that ARE the point of the test -- one holds a request open to pin
a concurrency ordering, one scripts a different status per arrival, one records
arrival TIMES to measure pacing, one forwards images. Folding those into a
single parameterised server would put the interesting behaviour behind a flag
and quietly change what a caller asserts. So this module owns the plumbing and
the wire envelopes; each suite declares only the handler behaviour it is about,
which is a few lines once the boilerplate is gone.

Nothing here is a mock, a stub or a patch. The server is real, the socket is
real, and everything downstream of it is production code -- only the REPLY is
authored, exactly as a real runtime's would be.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Final, override

from pydantic import TypeAdapter

__all__ = [
    "SilentLoopbackHandler",
    "ollama_chat_reply",
    "openai_chat_reply",
    "read_json_body",
    "read_text_body",
    "serving_loopback",
    "write_json_response",
    "write_raw_response",
]

#: The shutdown join budget. Generous enough that a loaded CI box does not trip
#: it, bounded so a wedged handler thread surfaces as a failure rather than
#: hanging the suite.
_JOIN_TIMEOUT_S: Final[float] = 5.0

_JSON_OBJECT_ADAPTER: TypeAdapter[dict[str, object]] = TypeAdapter(dict[str, object])


class SilentLoopbackHandler(BaseHTTPRequestHandler):
    """A request handler whose stdlib access log is silenced.

    Subclass this rather than :class:`~http.server.BaseHTTPRequestHandler`
    directly. The stdlib default writes a line to stderr per request, which
    buries real output under traffic no reader wants; every suite here had
    independently overridden it.
    """

    def do_POST(self) -> None:
        """Reject POST requests unless a suite supplies its endpoint behavior."""
        self.send_error(HTTPStatus.NOT_IMPLEMENTED)

    def do_GET(self) -> None:
        """Reject GET requests unless a suite supplies its endpoint behavior."""
        self.send_error(HTTPStatus.NOT_IMPLEMENTED)

    def do_DELETE(self) -> None:
        """Reject DELETE requests unless a suite supplies its endpoint behavior."""
        self.send_error(HTTPStatus.NOT_IMPLEMENTED)

    @override
    def log_message(self, format: str, *args: object) -> None:
        """Silence the stdlib per-request access log."""


def read_text_body(handler: BaseHTTPRequestHandler) -> str:
    """Return the handler's request body, decoded but not parsed.

    Reads exactly ``content-length`` bytes, which is what makes the connection
    reusable for the next request rather than leaving unread bytes in the socket.

    The undecoded sibling of :func:`read_json_body`, for the suites that record
    what arrived verbatim: their evidence is the transmitted text itself, and a
    parse-then-reserialise round trip would record a body the client never sent.

    Args:
        handler: The handler serving the request.

    Returns:
        The request body as text.
    """
    return handler.rfile.read(int(handler.headers.get("content-length", "0"))).decode("utf-8")


def read_json_body(handler: BaseHTTPRequestHandler) -> Mapping[str, object]:
    """Return the handler's request body, parsed as JSON.

    Args:
        handler: The handler serving the request.

    Returns:
        The decoded JSON object.
    """
    return _JSON_OBJECT_ADAPTER.validate_python(json.loads(read_text_body(handler)))


def write_json_response(
    handler: BaseHTTPRequestHandler,
    payload: Mapping[str, object],
    *,
    status: int,
    extra_headers: Mapping[str, str] | None = None,
) -> None:
    """Serialise ``payload`` and write it as a complete JSON response.

    The ``content-length`` header is derived from the encoded bytes rather than
    supplied, because a length that disagrees with the body is the one defect
    this helper exists to make unrepresentable -- a client then blocks waiting
    for bytes that never arrive, and the suite reads as a timeout somewhere far
    from its cause.

    Args:
        handler: The handler serving the request.
        payload: The JSON object to send.
        status: The HTTP status to send.
        extra_headers: Additional headers, such as ``retry-after`` on a 429.
    """
    write_raw_response(handler, json.dumps(payload).encode("utf-8"), status=status, extra_headers=extra_headers)


def write_raw_response(
    handler: BaseHTTPRequestHandler,
    body: bytes,
    *,
    status: int,
    content_type: str = "application/json",
    extra_headers: Mapping[str, str] | None = None,
) -> None:
    """Write ``body`` verbatim as a complete response.

    The escape hatch beneath :func:`write_json_response`, for the suite that
    needs to send a body which is NOT valid JSON while still claiming a JSON
    content type -- the "2xx whose payload does not match the provider schema"
    failure is a real wire shape, and a helper that could only serialise a
    mapping would force that suite to keep its own copy of the header plumbing.
    Both paths derive ``content-length`` from the same bytes here, so the one
    defect that hangs a client cannot be reintroduced on either.

    Args:
        handler: The handler serving the request.
        body: The exact bytes to send.
        status: The HTTP status to send.
        content_type: The declared content type.
        extra_headers: Additional headers, such as ``retry-after`` on a 429.
    """
    handler.send_response(status)
    for name, value in (extra_headers or {}).items():
        handler.send_header(name, value)
    handler.send_header("content-type", content_type)
    handler.send_header("content-length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def ollama_chat_reply(
    content: str,
    *,
    model: str = "gpt-oss",
    prompt_eval_count: int = 12,
    eval_count: int = 4,
) -> Mapping[str, object]:
    """Return a well-formed Ollama ``/api/chat`` completion envelope.

    The ``role`` is carried because the real runtime always sends it; a builder
    that omitted it would be describing a wire shape nothing on the other end
    ever produces.

    Args:
        content: The assistant message content the caller wants echoed back.
        model: The model name the runtime would report.
        prompt_eval_count: Prompt tokens the runtime would report.
        eval_count: Completion tokens the runtime would report.

    Returns:
        The reply object, shaped as the real runtime shapes it.
    """
    return {
        "model": model,
        "message": {"role": "assistant", "content": content},
        "prompt_eval_count": prompt_eval_count,
        "eval_count": eval_count,
    }


def openai_chat_reply(
    content: str,
    *,
    model: str = "gpt-4.1",
    prompt_tokens: int = 9,
    completion_tokens: int = 3,
    response_id: str = "chatcmpl-loopback",
) -> Mapping[str, object]:
    """Return a well-formed OpenAI ``/v1/chat/completions`` envelope.

    A separate builder rather than a mode on the Ollama one: the two are
    genuinely different protocols -- the content sits under ``choices`` here and
    under ``message`` there, and the usage counters are named differently. A
    single builder switching on a flag would let a suite assert against the
    wrong shape while still reading as though it had chosen one.

    Args:
        content: The assistant message content the caller wants echoed back.
        model: The model name the vendor would report.
        prompt_tokens: Prompt tokens the vendor would report.
        completion_tokens: Completion tokens the vendor would report.
        response_id: The completion id the vendor would report.

    Returns:
        The reply object, shaped as the vendor shapes it.
    """
    return {
        "id": response_id,
        "model": model,
        "choices": [{"message": {"content": content}}],
        "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens},
    }


@contextmanager
def serving_loopback(handler: type[BaseHTTPRequestHandler], *, path: str) -> Iterator[str]:
    """Serve ``handler`` on an ephemeral loopback port for the duration of the block.

    Binding port ``0`` lets the OS pick a free one, so parallel workers cannot
    collide on a fixed port -- and the URL is yielded rather than assumed,
    because a caller that reconstructed it would be guessing at the port the OS
    actually granted.

    The server is always torn down, including when the block raises: a leaked
    ``serve_forever`` thread outlives the test and its port stays bound, which
    surfaces later as an unrelated suite failing to bind.

    Args:
        handler: The request-handler class to serve. Subclass
            :class:`SilentLoopbackHandler` so the access log stays quiet.
        path: The request path to append to the yielded URL, such as
            ``/api/chat``.

    Yields:
        The full URL callers should point their endpoint setting at.
    """
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}{path}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=_JOIN_TIMEOUT_S)
