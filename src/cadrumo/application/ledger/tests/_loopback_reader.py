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

The bind-thread-shutdown plumbing and the wire envelope come from the shared
loopback home; only the transcription-keyed reply behaviour, which is what this
module is about, is declared here.

See Also:
    :func:`~application.ledger.evidence_textlayer.transcribe_text_layer`
        Produces the text this endpoint is keyed on.
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from http import HTTPStatus
from typing import ClassVar, override

from ....core.config import override_settings
from ....tests.loopback_llm import (
    SilentLoopbackHandler,
    ollama_chat_reply,
    read_json_body,
    serving_loopback,
    write_json_response,
)

__all__ = ["READING_RUNTIME_MODEL", "ReaderReply", "serving_a_loopback_reader"]

#: One document's answer: a marker that identifies it in the transcription, and
#: the flat field/anchor object the reader would return for it.
ReaderReply = tuple[str, Mapping[str, str]]

READING_RUNTIME_MODEL = "qwen2.5:7b"
"""The model name the reading runtime reports on this route.

Shared by the ledger reading suites that declare their own handler behaviour, so
the reply envelope names one runtime rather than three independently-typed
spellings of it.
"""


class _LoopbackRequestHandler(SilentLoopbackHandler):
    """A real local endpoint speaking the reading runtime's ``/api/chat`` shape."""

    replies: ClassVar[Sequence[ReaderReply]] = ()
    fallback: ClassVar[Mapping[str, str]] = {}

    def _fields_for(self, prompt: str) -> Mapping[str, str]:
        for marker, fields in self.replies:
            if marker in prompt:
                return fields
        return self.fallback

    @override
    def do_POST(self) -> None:
        prompt = json.dumps(read_json_body(self)["messages"])
        write_json_response(
            self,
            ollama_chat_reply(
                json.dumps(dict(self._fields_for(prompt))),
                model=READING_RUNTIME_MODEL,
                prompt_eval_count=100,
                eval_count=50,
            ),
            status=HTTPStatus.OK,
        )


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
    _LoopbackRequestHandler.replies = tuple(replies)
    _LoopbackRequestHandler.fallback = dict(fallback or {})
    with (
        serving_loopback(_LoopbackRequestHandler, path="/api/chat") as chat_url,
        override_settings(cadrumo_llm_ollama_chat_url=chat_url),
    ):
        yield chat_url
