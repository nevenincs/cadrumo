"""A served reading runtime for CLI suites whose documents the rule reader reads.

Text-layer evidence is read by the label rules first and by the semantic reader
for whatever the rules leave unread, so an ``evidence extract`` or ``confirm``
contacts a reading runtime even when every figure a suite asserts is printed
under a recognised label. Left unserved, that runtime is whatever this machine
happens to run at the configured address -- a real model on a workstation,
nothing on a CI host -- and the outcome would follow the host rather than the
code under test.
"""

from __future__ import annotations

from collections.abc import Iterator
from http import HTTPStatus
from typing import override

import pytest

from ....core.config import override_settings
from ....tests.loopback_llm import (
    SilentLoopbackHandler,
    ollama_chat_reply,
    read_json_body,
    serving_loopback,
    write_json_response,
)

__all__ = ["_rule_reading_runtime"]


class _ReaderThatProposesNothing(SilentLoopbackHandler):
    """A real reading runtime on loopback whose every answer proposes no field."""

    @override
    def do_POST(self) -> None:
        read_json_body(self)
        write_json_response(self, ollama_chat_reply("{}"), status=HTTPStatus.OK)


@pytest.fixture(autouse=True)
def _rule_reading_runtime() -> Iterator[None]:
    """Serve a reading runtime that proposes nothing, so the rule reading stands.

    The runtime is on-host, so its load is still admitted against measured
    headroom before the request is sent: the operator override admits a machine
    whose accelerator this build cannot measure, and the margin is zero because
    this runtime loads no weights. A measured shortfall still refuses.
    """
    with (
        serving_loopback(_ReaderThatProposesNothing, path="/api/chat") as chat_url,
        override_settings(
            cadrumo_llm_ollama_chat_url=chat_url,
            cadrumo_llm_contention_check_override=True,
            cadrumo_llm_contention_safety_margin_bytes=0,
        ),
    ):
        yield
