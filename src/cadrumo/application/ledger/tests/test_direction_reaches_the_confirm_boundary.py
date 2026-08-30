"""Direction, end to end: profile identifier to derivation to confirm-time blocker.

Three links were each gated on their own and joined by nothing a person could
run. The derivation was gated GIVEN a filer identifier, the filer identifier was
gated GIVEN a profile, and the threading between them was gated structurally --
so ``suggested_kind`` could have been stamped ``None`` on every real document
while every unit suite stayed green. That is the failure this module exists to
make impossible: it drives the public entry point against a real encrypted
bucket carrying a real profile, a real PDF, a real text-layer transcription and
a real HTTP endpoint, and reads what comes out the other side.

Nothing in the application is substituted. The reading model's REPLY is authored
by these cases and served over a real socket, exactly as a runtime returns one;
everything downstream of that socket is production code. No inference runs, so
this is executable on a machine with no accelerator.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from http import HTTPStatus
from pathlib import Path
from typing import ClassVar, override

import pytest

from ....adapters.persistence.storage.sql.engine import dispose_engine
from ....core import ConfirmationBlockReason, DraftDiscrepancyKind
from ....core.config import load_settings, override_settings
from ....domain.iva.classification import InvoiceKind
from ....domain.user_profile.values import UserProfileFact
from ....tests.cli_runner import invoke_cached_cli
from ....tests.loopback_llm import (
    SilentLoopbackHandler,
    ollama_chat_reply,
    read_json_body,
    serving_loopback,
    write_json_response,
)
from ....tests.pdf_fixtures import text_pdf_bytes
from ....tests.profile_capsule import open_test_profile_session, set_active_test_profile_facts
from ....tests.secure_sql import isolated_profile_storage_root
from ....tests.user_profile import register_minimal_profile
from ..confirmation_gate import ConfirmationBlockedError, confirmation_blockers
from ..evidence_draft import (
    InvoiceDraft,
    confirm_invoice_draft_from_evidence,
    extract_invoice_draft_from_evidence,
)
from ..filer_establishment import FILER_TAX_ID_FACT_PATH
from ._loopback_reader import READING_RUNTIME_MODEL

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_PROFILE_ID = "9e0f3a2b-5d1c-4a77-9b2d-27ed6d6c7f10"
_FILER_CIF = "B17283946"
_COUNTERPARTY_CIF = "B12345674"
_BAD_CHECKSUM_CIF = "B1234567X"

#: A purchase invoice: the filer is the party being BILLED, so the document
#: places them on the customer side and the derivation must answer ``received``.
_PURCHASE_LINES = (
    "FACTURA 2026-0142",
    f"Proveedor: Acme Suministros SL  NIF: {_COUNTERPARTY_CIF}",
    f"Cliente: Tester SL  NIF: {_FILER_CIF}",
    "Base imponible: 100,00",
    "IVA 21%",
    "Cuota IVA: 21,00",
    "Total factura: 121,00",
)

_PURCHASE_READ = {
    "supplier_tax_id": _COUNTERPARTY_CIF,
    "supplier_tax_id_anchor": _COUNTERPARTY_CIF,
    "supplier_tax_id_role_evidence": "Proveedor:",
    "customer_tax_id": _FILER_CIF,
    "customer_tax_id_anchor": _FILER_CIF,
    "customer_tax_id_role_evidence": "Cliente:",
}

#: A factura simplificada: no counterparty identifier is printed at all, which
#: Spanish invoicing law permits. Nothing here is a defect.
_SIMPLIFICADA_LINES = (
    "TICKET 2026-0142",
    "Emisor: Acme Suministros SL",
    f"Cliente: Tester SL  NIF: {_FILER_CIF}",
    "Base imponible: 100,00",
    "IVA 21%",
    "Cuota IVA: 21,00",
    "Total factura: 121,00",
)

_SIMPLIFICADA_READ = {
    "customer_tax_id": _FILER_CIF,
    "customer_tax_id_anchor": _FILER_CIF,
    "customer_tax_id_role_evidence": "Cliente:",
}

#: The measured defect: the counterparty's printed identifier fails its control
#: character, so a validating read cannot see the real supplier at all.
_BAD_CHECKSUM_LINES = (
    "FACTURA 2026-0142",
    f"Proveedor: Acme Suministros SL  NIF: {_BAD_CHECKSUM_CIF}",
    f"Cliente: Tester SL  NIF: {_FILER_CIF}",
    "Base imponible: 100,00",
    "IVA 21%",
    "Cuota IVA: 21,00",
    "Total factura: 121,00",
)

_BAD_CHECKSUM_READ = {
    "supplier_tax_id": _BAD_CHECKSUM_CIF,
    "supplier_tax_id_anchor": _BAD_CHECKSUM_CIF,
    "supplier_tax_id_role_evidence": "Proveedor:",
    "customer_tax_id": _FILER_CIF,
    "customer_tax_id_anchor": _FILER_CIF,
    "customer_tax_id_role_evidence": "Cliente:",
}

_COMMON_READ = {
    "invoice_number": "2026-0142",
    "invoice_number_anchor": "2026-0142",
    "invoice_date": "2026-03-10",
    "taxable_base": "100,00",
    "taxable_base_anchor": "100,00",
    "iva_rate": "21",
    "iva_rate_anchor": "21%",
    "iva_amount": "21,00",
    "iva_amount_anchor": "21,00",
    "grand_total": "121,00",
    "grand_total_anchor": "121,00",
    "currency": "EUR",
}


class _ReaderEndpoint(SilentLoopbackHandler):
    """A real local endpoint speaking the runtime's ``/api/chat`` wire shape."""

    reply: ClassVar[str] = ""

    @override
    def do_POST(self) -> None:
        read_json_body(self)
        write_json_response(
            self,
            ollama_chat_reply(
                self.reply,
                model=READING_RUNTIME_MODEL,
                prompt_eval_count=100,
                eval_count=50,
            ),
            status=HTTPStatus.OK,
        )


@pytest.fixture
def reader_url() -> Iterator[str]:
    with serving_loopback(_ReaderEndpoint, path="/api/chat") as chat_url:
        yield chat_url


class _LiveDocument:
    """A real evidence record in a real bucket, read through the real entry point."""

    def __init__(self, evidence_id: str) -> None:
        self.evidence_id = evidence_id

    def extract(self) -> InvoiceDraft:
        return extract_invoice_draft_from_evidence(
            evidence_id=self.evidence_id,
            bucket_id=_PROFILE_ID,
            settings=load_settings(),
        )

    def confirm(self, *, kind: InvoiceKind) -> None:
        confirm_invoice_draft_from_evidence(
            bucket_id=_PROFILE_ID,
            kind=kind,
            counterparty_country="ES",
            evidence_id=self.evidence_id,
            settings=load_settings(),
        )


@pytest.fixture
def live_document(tmp_path: Path, reader_url: str):
    """Yield a factory standing up a real profile, bucket and evidence record.

    The profile declares the filer's own tax identifier, which is the fact the
    whole chain turns on: without it the role resolution declines to run and the
    derivation reports that it was never supplied.
    """
    dispose_engine()
    with (
        override_settings(
            cadrumo_local_storage_root=tmp_path,
            cadrumo_output_language="en",
            cadrumo_llm_ollama_chat_url=reader_url,
        ),
        isolated_profile_storage_root(tmp_path=tmp_path),
        open_test_profile_session(_PROFILE_ID),
    ):
        # Seeded through a detached WorkflowState, never a repository read:
        # the capsule publishes by an atomic no-replace rename onto
        # ``buckets/<profile-id>``, which a workflow-state repository
        # construction would otherwise materialise first and collide with.
        register_minimal_profile(profile_id=_PROFILE_ID, display_name="tester")
        set_active_test_profile_facts(
            (UserProfileFact(path=FILER_TAX_ID_FACT_PATH, value=_FILER_CIF),),
        )

        def _add(lines: tuple[str, ...], read: dict[str, str]) -> _LiveDocument:
            _ReaderEndpoint.reply = json.dumps({**_COMMON_READ, **read})
            document = tmp_path / f"factura-{len(lines)}-{len(read)}.pdf"
            document.write_bytes(text_pdf_bytes(lines))
            added = invoke_cached_cli(
                ["--format", "json", "app", "ledger", "evidence", "add", str(document), "--supplier", "Acme SL"],
            )
            assert added.exit_code == 0, added.output
            return _LiveDocument(json.loads(added.output)["result"]["evidence_id"])

        yield _add
    dispose_engine()


# ---------------------------------------------------------------------------
# The join
# ---------------------------------------------------------------------------


def test_the_profiles_identifier_reaches_the_derivation_on_the_live_path(live_document) -> None:
    """The anchor. Every case below is vacuous if this does not hold.

    Three separately-gated links -- the profile fact, the threading, the
    derivation -- joined for the first time. A ``None`` here would mean the
    apparatus is complete and unreached, which is exactly how it shipped.
    """
    draft = live_document(_PURCHASE_LINES, _PURCHASE_READ).extract()

    assert draft.suggested_kind is InvoiceKind.RECEIVED
    basis = next(e.note for e in draft.provenance if e.field == "suggested_kind")
    assert "customer" in basis, "the derivation must say which block it read the filer's identifier in"


# ---------------------------------------------------------------------------
# The cross-check, both directions, on the real confirm path
# ---------------------------------------------------------------------------


def test_confirming_against_the_documents_own_reading_raises_the_contradiction(live_document) -> None:
    """A purchase confirmed as a sale must not pass the gate.

    Booked the wrong way this moves a purchase into the sales column, inverts
    the cuota between soportado and repercutido, and reaches Modelo 347 as an
    operation the counterparty declared with the opposite sign.
    """
    document = live_document(_PURCHASE_LINES, _PURCHASE_READ)

    with pytest.raises(ConfirmationBlockedError) as raised:
        document.confirm(kind=InvoiceKind.ISSUED)

    assert ConfirmationBlockReason.UNRESOLVED_DIRECTION.value in str(raised.value)


def test_confirming_in_the_direction_the_document_supports_raises_no_direction_blocker(
    live_document,
) -> None:
    """The bound: an agreeing document must reach the gate carrying nothing.

    Asserted on the draft the confirm path builds rather than on the confirm's
    eventual outcome, because a document this fixture leaves without a
    counterparty name refuses later for that reason -- which would let a
    direction blocker hide behind an unrelated refusal.
    """
    draft = live_document(_PURCHASE_LINES, _PURCHASE_READ).extract()

    from ..evidence_draft import _with_direction_contradiction

    stamped = _with_direction_contradiction(draft, kind=InvoiceKind.RECEIVED)

    assert DraftDiscrepancyKind.DIRECTION_CONTRADICTED not in {f.kind for f in stamped.discrepancies}
    assert DraftDiscrepancyKind.DIRECTION_CONTRADICTED in {
        f.kind for f in _with_direction_contradiction(draft, kind=InvoiceKind.ISSUED).discrepancies
    }, "the same draft must contradict the other direction, or this passes for the wrong reason"


# ---------------------------------------------------------------------------
# Absent versus unverifiable, on the real reading path
# ---------------------------------------------------------------------------


def test_a_factura_simplificada_no_longer_blocks_on_a_role_it_never_stated(live_document) -> None:
    """A legitimate document must reach the operator without a blocker.

    Spanish invoicing law permits omitting the recipient's identifier on a
    simplificada. Blocking every one of them trains the operator to clear the
    finding unread.
    """
    draft = live_document(_SIMPLIFICADA_LINES, _SIMPLIFICADA_READ).extract()

    assert confirmation_blockers(draft) == ()


def test_a_counterparty_identifier_failing_its_checksum_still_blocks_on_the_live_path(
    live_document,
) -> None:
    """The genuine catch, proven through the reader that drops the value.

    The grounder rejects the identifier and drops it to ``None``, so by the time
    the role resolution reads the draft the slot is empty and indistinguishable
    from the simplificada above. The rejection is therefore recorded at the
    stage that performs it, and this case is what proves that record survives to
    the gate rather than being reconstructed downstream.
    """
    draft = live_document(_BAD_CHECKSUM_LINES, _BAD_CHECKSUM_READ).extract()

    assert draft.supplier_tax_id is None, "the unverifiable identifier must still be dropped"
    assert [blocker.reason for blocker in confirmation_blockers(draft)] == [
        ConfirmationBlockReason.AMBIGUOUS_IDENTITY,
    ]
