"""The text reader's field selection reaches the compiler, and the full path is unmoved.

The compiler gained a field selection, and every production caller kept passing
none: ``build_text_field_extraction_prompt`` took no such parameter, and
``TextInvoiceFieldExtractor`` neither accepted nor forwarded one. So the capability
existed one layer up from everything that could use it, and every read still
emitted all declared contracts.

**The parameter is not the property; the THREADING is.** A ``fields`` argument
accepted at the boundary and dropped before the compiler is precisely the defect
this closes, and it is invisible to any test that only checks the signature or
only checks the compiler. So the assertions here read the prompt the reader
actually builds, through its own request-building path, and count the contracts
in it.

**The full-set path must stay byte-identical.** Baselines were measured through
this reader, and a default that reorders or reshapes the prompt invalidates
comparability with everything already recorded while still looking correct. The
guard is byte equality against the unselected render, not a structural check --
a structural check passes on a prompt whose field ordering moved.
"""

from __future__ import annotations

from typing import Any, override

import pytest

from ...application.ledger.document_transcription import DocumentTranscription, TranscriberIdentity
from ...core import FieldOrigin
from .._client import LLMClient
from .._evidence_draft_text import (
    TextInvoiceFieldExtractor,
    build_text_field_extraction_prompt,
    default_extraction_authority_values,
)
from .._invoice_extraction_prompt import render_invoice_extraction_prompt
from .._invoice_field_contract import INVOICE_FIELD_CONTRACTS
from .._models import LLMProvider

pytestmark = [pytest.mark.integration, pytest.mark.hex_outbound_adapter]

_SENTINEL_TEXT = "FACTURA SENTINEL 2026"


class _RequestCapturedError(RuntimeError):
    """Raised once the request is in hand, so no transport is ever reached."""


class _CapturingClient(LLMClient):
    """Capture the built request and refuse to dispatch it.

    Injected through the reader's own declared ``client`` parameter, so the
    request under assertion is the one the production path builds. Nothing is
    sent: the point is the instruction, and reaching a provider to inspect it
    would make this test depend on a credential and a network.
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.request: Any = None

    @override
    async def complete(self, request: Any) -> Any:
        self.request = request
        raise _RequestCapturedError


def _prompt_the_reader_builds(*, fields: list[str] | None) -> str:
    """Return the prompt a reader configured with ``fields`` actually sends."""
    client = _CapturingClient(caller="tests.text_reader_field_subset", prompt_id="invoice-extraction")
    reader = TextInvoiceFieldExtractor(
        model="test-text-model",
        provider=LLMProvider.ANTHROPIC,
        client=client,
        fields=fields,
        public_corpus=True,
    )
    transcription = DocumentTranscription(
        text=_SENTINEL_TEXT,
        page_count=1,
        source_content_sha256="0" * 64,
        transcriber=TranscriberIdentity(
            origin=FieldOrigin.TEXT_LAYER,
            name="tests.text-layer",
            transport="deterministic",
            revision="1",
        ),
    )
    with pytest.raises(_RequestCapturedError):
        reader.extract(transcription=transcription)
    assert client.request is not None
    return str(client.request.prompt)


def _contract_lines(prompt: str) -> list[str]:
    """Return the field-contract lines the prompt carries, by declared name."""
    return [contract.field_name for contract in INVOICE_FIELD_CONTRACTS if f"- {contract.field_name}:" in prompt]


def test_the_unselected_prompt_is_byte_identical_to_the_compilers_own() -> None:
    """Passing no selection must change nothing at all.

    Byte equality, because comparability with every already-recorded baseline
    depends on this exact string.
    """
    values = default_extraction_authority_values()
    threaded = build_text_field_extraction_prompt(_SENTINEL_TEXT, values=values, fields=None)
    compiled = render_invoice_extraction_prompt(values=values)
    assert threaded == f"{compiled.text}\nINVOICE TEXT:\n{_SENTINEL_TEXT}"


def test_the_full_prompt_still_carries_every_declared_contract() -> None:
    """The default asks for the whole declaration, not a subset of it."""
    prompt = _prompt_the_reader_builds(fields=None)
    assert _contract_lines(prompt) == [contract.field_name for contract in INVOICE_FIELD_CONTRACTS]


@pytest.mark.parametrize("size", [1, 3, 7])
def test_the_readers_selection_reaches_the_prompt_it_sends(size: int) -> None:
    """The threading gate: a reader asked for N fields must SEND N contracts.

    This is the assertion a dropped selection fails. A reader that accepts
    ``fields`` and forwards nothing still passes a signature check and still
    passes every compiler test; it fails here, because the prompt it builds
    carries the whole declaration.
    """
    selection = [contract.field_name for contract in INVOICE_FIELD_CONTRACTS[:size]]
    prompt = _prompt_the_reader_builds(fields=selection)
    assert _contract_lines(prompt) == selection
    assert len(_contract_lines(prompt)) < len(INVOICE_FIELD_CONTRACTS)


def test_a_selected_read_still_carries_the_document_text() -> None:
    """Narrowing the ask must not narrow what the model is given to read.

    The selection governs which fields are requested, never how much of the
    document the model sees. A subset prompt that also truncated the evidence
    would measure a different task and look like a call-shape effect.
    """
    prompt = _prompt_the_reader_builds(fields=[INVOICE_FIELD_CONTRACTS[0].field_name])
    assert _SENTINEL_TEXT in prompt


def test_the_provenance_stamp_describes_the_prompt_that_was_sent() -> None:
    """A narrowed read must not stamp the full instruction.

    The stamp answers "under which instruction was this read performed". A stamp
    naming the full prompt while three fields were asked for is a confident wrong
    answer to exactly that question.
    """
    values = default_extraction_authority_values()
    selection = [contract.field_name for contract in INVOICE_FIELD_CONTRACTS[:3]]
    narrowed = render_invoice_extraction_prompt(values=values, fields=selection)
    full = render_invoice_extraction_prompt(values=values)
    assert narrowed.fingerprint != full.fingerprint

    client = _CapturingClient(caller="tests.text_reader_field_subset", prompt_id="invoice-extraction")
    reader = TextInvoiceFieldExtractor(
        model="test-text-model",
        provider=LLMProvider.ANTHROPIC,
        client=client,
        fields=selection,
        public_corpus=True,
    )
    assert reader._compiled_prompt().fingerprint == narrowed.fingerprint


def test_a_selection_the_declaration_cannot_satisfy_refuses_at_the_reader() -> None:
    """A bad name must refuse rather than silently emitting a shorter prompt.

    Dropped silently, an unknown name yields a prompt missing a contract nobody
    asked to remove -- and a measurement taken against it carries the authority
    of a number while describing a task nobody specified.
    """
    values = default_extraction_authority_values()
    with pytest.raises(ValueError, match=r"(?i)field"):
        build_text_field_extraction_prompt(_SENTINEL_TEXT, values=values, fields=["not_a_declared_field"])
