"""Real-behaviour tests for the text reader's fitness probe over a loopback runtime.

The endpoint is a real HTTP server speaking the local chat wire shape; the
reply content is what varies. Prompt rendering, the transport, parsing and
grounding are the production code.
"""

from __future__ import annotations

import contextlib
import json
import threading
from collections.abc import Generator, Mapping
from contextlib import ExitStack, contextmanager
from http import HTTPStatus
from pathlib import Path
from queue import Queue
from typing import ClassVar, override

import pytest

from .....application.local_reader import RoleFitnessOutcome, admit_local_reader
from .....application.provisioning_contracts import LOCAL_AI_PROVISION_ACTION_ID, ProvisioningPreconditionCondition
from .....application.provisioning_fitness import RoleFitnessVerdict, read_fitness_verdict
from .....core.config import Settings, load_settings, override_settings
from .....core.model_catalogue import ModelRole
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


class _SlowChat(SilentLoopbackHandler):
    released: ClassVar[threading.Event]

    @override
    def do_POST(self) -> None:
        read_json_body(self)
        # Holds the answer past the probe's bound, as a model too slow for this host does.
        self.released.wait(timeout=10)
        with contextlib.suppress(OSError):
            write_json_response(self, ollama_chat_reply(_FIT_REPLY, eval_count=300), status=HTTPStatus.OK)


def test_a_model_slower_than_the_probe_timeout_is_a_timeout_verdict_not_a_transport_failure() -> None:
    _SlowChat.released = threading.Event()
    with (
        serving_loopback(_SlowChat, path="/api/chat") as endpoint,
        override_settings(cadrumo_llm_ollama_chat_url=endpoint, cadrumo_llm_default_timeout_s=1),
    ):
        try:
            outcome = probe_text_extraction_fitness("slow-model:1b", load_settings())
        finally:
            _SlowChat.released.set()

    assert outcome.fit is False
    assert outcome.timed_out is True
    assert outcome.transport_failed is False
    assert outcome.settled is True
    assert outcome.facts["probe_timeout_s"] == 1
    assert outcome.precondition_verdict is not None
    assert (
        outcome.precondition_verdict.failed_condition_id
        == ProvisioningPreconditionCondition.ROLE_MODEL_FITNESS_WITHIN_TIMEOUT
    )


def test_an_unreachable_runtime_is_a_transport_failure_not_unfitness() -> None:
    with override_settings(cadrumo_llm_ollama_chat_url="http://127.0.0.1:1/api/chat"):
        outcome = probe_text_extraction_fitness("text-model:1b", load_settings())

    assert outcome.fit is False
    assert outcome.transport_failed is True
    assert outcome.timed_out is False
    assert outcome.precondition_verdict is not None
    assert outcome.precondition_verdict.failed_condition_id == ProvisioningPreconditionCondition.MODEL_READY


# ---------------------------------------------------------------------------
# the probe as a consumer's first-use admission, on a runtime that lists the model
# ---------------------------------------------------------------------------

_TEXT_MODEL = "text-model:1b"
_DIGEST = "sha256:text-weights-1"


class _Reader(SilentLoopbackHandler):
    """A runtime holding the text model under one digest and answering chat with ``content``."""

    content: ClassVar[str] = ""
    chats: ClassVar[Queue[Mapping[str, object]]]

    @override
    def do_GET(self) -> None:
        rows = [{"name": _TEXT_MODEL, "size": 1, "digest": _DIGEST}]
        write_json_response(self, {"models": rows}, status=HTTPStatus.OK)

    @override
    def do_POST(self) -> None:
        self.chats.put(read_json_body(self))
        write_json_response(self, ollama_chat_reply(self.content, eval_count=300), status=HTTPStatus.OK)


@contextmanager
def _reader(content: str, storage_root: Path) -> Generator[Queue[Mapping[str, object]]]:
    _Reader.content = content
    _Reader.chats = Queue()
    with (
        serving_loopback(_Reader, path="/api/chat") as endpoint,
        override_settings(
            cadrumo_local_storage_root=storage_root,
            cadrumo_llm_ollama_chat_url=endpoint,
            cadrumo_llm_ollama_text_model=_TEXT_MODEL,
        ),
    ):
        yield _Reader.chats


def _recorded() -> RoleFitnessVerdict | None:
    settings = load_settings()
    recorded = read_fitness_verdict(
        endpoint=settings.cadrumo_llm_ollama_chat_url,
        model=_TEXT_MODEL,
        digest=_DIGEST,
        role=ModelRole.TEXT_EXTRACTION,
    )
    return None if recorded is None else recorded.verdict


def test_a_first_read_sends_the_real_probe_once_and_admits_a_fit_model(tmp_path: Path) -> None:
    with _reader(_FIT_REPLY, tmp_path) as chats:
        first = admit_local_reader(ModelRole.TEXT_EXTRACTION, text_probe=probe_text_extraction_fitness)
        second = admit_local_reader(ModelRole.TEXT_EXTRACTION, text_probe=probe_text_extraction_fitness)
        recorded = _recorded()

    assert first.available is True and second.available is True
    assert chats.qsize() == 1, "the second read is admitted on the recorded verdict"
    assert "PROBE-0001" in json.dumps(chats.get_nowait()["messages"])
    assert recorded is RoleFitnessVerdict.FIT


def test_a_first_read_with_a_model_that_cannot_answer_the_reader_refuses_with_no_setup(tmp_path: Path) -> None:
    with _reader("I cannot help with that.", tmp_path) as chats:
        refused = admit_local_reader(ModelRole.TEXT_EXTRACTION, text_probe=probe_text_extraction_fitness)
        again = admit_local_reader(ModelRole.TEXT_EXTRACTION, text_probe=probe_text_extraction_fitness)
        recorded = _recorded()

    assert refused.available is False and again.available is False
    assert chats.qsize() == 1
    assert recorded is RoleFitnessVerdict.UNFIT
    assert refused.precondition_verdict is not None
    assert refused.precondition_verdict.failed_condition_id == ProvisioningPreconditionCondition.ROLE_MODEL_FIT_FOR_ROLE
    assert refused.precondition_verdict.action is None


def test_a_first_read_after_the_server_stopped_refuses_with_the_local_ai_setup(tmp_path: Path) -> None:
    _Reader.content = _FIT_REPLY
    _Reader.chats = Queue()
    with ExitStack() as server:
        endpoint = server.enter_context(serving_loopback(_Reader, path="/api/chat"))

        def stop_then_probe(model: str, settings: Settings) -> RoleFitnessOutcome:
            # The server stops between the inventory read and the probe, as a
            # crashed runtime does; the probe then reaches nothing.
            server.close()
            return probe_text_extraction_fitness(model, settings)

        with override_settings(
            cadrumo_local_storage_root=tmp_path,
            cadrumo_llm_ollama_chat_url=endpoint,
            cadrumo_llm_ollama_text_model=_TEXT_MODEL,
        ):
            status = admit_local_reader(ModelRole.TEXT_EXTRACTION, text_probe=stop_then_probe)
            recorded = _recorded()

    assert status.available is False
    assert recorded is None, "a probe that reached nothing is no verdict about the model"
    assert status.precondition_verdict is not None
    assert status.precondition_verdict.failed_condition_id == ProvisioningPreconditionCondition.RUNTIME_REACHABLE
    assert status.precondition_verdict.action is not None
    assert status.precondition_verdict.action.action_id == LOCAL_AI_PROVISION_ACTION_ID
