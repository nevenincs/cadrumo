"""Real-behaviour tests for the text reader's fitness probe over a loopback runtime.

The endpoint is a real HTTP server speaking the local chat wire shape; the
reply content is what varies. Prompt rendering, the transport, parsing and
grounding are the production code.
"""

from __future__ import annotations

import json
from collections.abc import Generator, Mapping
from contextlib import contextmanager
from http import HTTPStatus
from queue import Queue
from typing import ClassVar, override

import pytest

from .....application.provisioning_contracts import ProvisioningPreconditionCondition
from .....core.config import load_settings, override_settings
from .....tests.loopback_llm import (
    SilentLoopbackHandler,
    ollama_chat_reply,
    read_json_body,
    serving_loopback,
    write_json_response,
)
from ..role_fitness import probe_text_extraction_fitness

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_FIT_REPLY = json.dumps(
    {
        "invoice_number": "PROBE-0001",
        "invoice_number_anchor": "PROBE-0001",
        "taxable_base": "100.00 EUR",
        "taxable_base_anchor": "Base imponible: 100.00 EUR",
        "currency": "EUR",
        "currency_anchor": "EUR",
    }
)


class _Chat(SilentLoopbackHandler):
    content: ClassVar[str] = ""
    bodies: ClassVar[Queue[Mapping[str, object]]]

    @override
    def do_POST(self) -> None:
        self.bodies.put(read_json_body(self))
        write_json_response(self, ollama_chat_reply(self.content, eval_count=300), status=HTTPStatus.OK)


@contextmanager
def _runtime(content: str) -> Generator[Queue[Mapping[str, object]]]:
    _Chat.content = content
    _Chat.bodies = Queue()
    with serving_loopback(_Chat, path="/api/chat") as endpoint, override_settings(cadrumo_llm_ollama_chat_url=endpoint):
        yield _Chat.bodies


def test_a_parseable_grounded_answer_is_fit_and_the_real_request_shape_was_sent() -> None:
    with _runtime(_FIT_REPLY) as bodies:
        outcome = probe_text_extraction_fitness("text-model:1b", load_settings())

    assert outcome.fit is True
    assert outcome.grounded is True
    assert outcome.precondition_verdict is None
    body = bodies.get_nowait()
    messages = body["messages"]
    assert isinstance(messages, list)
    prompt = messages[-1]["content"]
    assert "PROBE-0001" in prompt, "the probe document rides the reader's own prompt"
    options = body["options"]
    assert isinstance(options, Mapping)
    # The reader's answer budget, plus the transport's reasoning allowance.
    assert options["num_predict"] > load_settings().cadrumo_llm_default_max_tokens


@pytest.mark.parametrize("content", ["", "I cannot help with that.", "<think>still thinking"])
def test_an_answer_the_parser_cannot_read_is_unfit(content: str) -> None:
    with _runtime(content):
        outcome = probe_text_extraction_fitness("vision-model:2b", load_settings())

    assert outcome.fit is False
    assert outcome.answer_parseable is False
    assert outcome.transport_failed is False
    assert outcome.precondition_verdict is not None
    assert outcome.precondition_verdict.failed_condition_id == ProvisioningPreconditionCondition.ROLE_MODEL_FIT_FOR_ROLE


def test_a_readable_answer_with_the_wrong_values_is_unfit() -> None:
    wrong = json.dumps({"invoice_number": "A-9999", "taxable_base": "5.00", "currency": "EUR"})
    with _runtime(wrong):
        outcome = probe_text_extraction_fitness("confused-model:1b", load_settings())

    assert outcome.fit is False
    assert outcome.answer_parseable is True
    assert outcome.facts["probe_values_grounded"] is False


def test_an_unreachable_runtime_is_a_transport_failure_not_unfitness() -> None:
    with override_settings(cadrumo_llm_ollama_chat_url="http://127.0.0.1:1/api/chat", cadrumo_llm_max_retries=0):
        outcome = probe_text_extraction_fitness("text-model:1b", load_settings())

    assert outcome.fit is False
    assert outcome.transport_failed is True
    assert outcome.precondition_verdict is not None
    assert outcome.precondition_verdict.failed_condition_id == ProvisioningPreconditionCondition.MODEL_READY
