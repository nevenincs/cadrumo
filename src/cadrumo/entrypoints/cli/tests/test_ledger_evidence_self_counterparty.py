"""Real-CLI regression: an invoice cannot name the filer as its own counterparty.

The evidence reader identifies a counterparty by scanning for the first
checksum-valid Spanish tax id, and the on-host vision prompt asks for "the
supplier's NIF/NIE/CIF". On a RECEIVED invoice that lands on the supplier. On an
ISSUED one the issuer IS the filer, so the same scan returns the filer's own
identifier -- checksum-valid, so every identity check downstream passes it, and
bound for the Modelo 347 / 349 counterparty totals AEAT reconciles against what
the counterparty declared.

These tests drive the real Typer CLI, a real encrypted bucket session, and a
real reportlab-generated PDF. The filer's own tax id is read from the live
profile rather than hardcoded, so the test cannot drift from the harness.

See Also:
    :func:`~application.invoices.counterparty_is_the_filer`
        The profile-derived predicate under test.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ....application.wizard.status import load_active_taxpayer_profile
from ....application.workflow.persistence import workflow_state_repository
from ._ledger_ux_support import _add_evidence, _invoke, _open_bucket_session

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]
__all__ = ["_open_bucket_session"]

# A real Spanish CIF distinct from any profile identifier: the legitimate
# counterparty on a received invoice.
_SUPPLIER_CIF = "B12345674"


def _invoice_lines(tax_id: str, *, number: str) -> tuple[str, ...]:
    return (
        "Factura",
        f"NIF: {tax_id}",
        f"Numero de factura: {number}",
        "Fecha: 10/03/2026",
        "Base imponible: 100,00",
        "IVA 21%",
        "Cuota IVA: 21,00",
        "Total factura: 121,00",
    )


def _own_tax_id() -> str:
    """Return the active profile's own tax id, as the running app sees it."""
    return str(load_active_taxpayer_profile(workflow_state_repository().load()).tax_id)


def test_an_invoice_reading_back_the_filers_own_nif_is_refused(tmp_path: Path) -> None:
    """The issued-invoice failure: the letterhead identifier is the filer's own.

    Before this guard the confirm succeeded and recorded the filer as their own
    counterparty -- a fabricated counterparty identity, valid-looking because
    the filer's NIF passes the checksum, and destined for an informativa AEAT
    cross-checks against the counterparty's own filing.
    """
    own = _own_tax_id()
    evidence_id = _add_evidence(tmp_path, _invoice_lines(own, number="2026-0001"), filename="issued.pdf")

    confirmed = _invoke(
        [
            "--format", "json", "app", "ledger", "evidence", "confirm",
            "--country-code", "ES",
            "--evidence-id", evidence_id,
            "--kind", "issued",
            "--counterparty-name", "Cliente SL",
        ],
    )  # fmt: skip

    assert confirmed.exit_code != 0, confirmed.output
    # The refusal names the fix, not merely the fault: the operator is told to
    # supply the OTHER party's identifier.
    assert "counterparty-nif" in confirmed.output


def test_a_genuine_third_party_counterparty_still_confirms(tmp_path: Path) -> None:
    """The negative control: the guard must not block an ordinary received invoice."""
    evidence_id = _add_evidence(
        tmp_path,
        _invoice_lines(_SUPPLIER_CIF, number="2026-0142"),
        filename="received.pdf",
    )

    confirmed = _invoke(
        [
            "--format", "json", "app", "ledger", "evidence", "confirm",
            "--country-code", "ES",
            "--evidence-id", evidence_id,
            "--kind", "received",
            "--counterparty-name", "Acme Suministros SL",
        ],
    )  # fmt: skip

    assert confirmed.exit_code == 0, confirmed.output
    assert json.loads(confirmed.output)["result"]["created"] is True


def test_an_operator_confirming_the_misread_identifier_is_still_refused(tmp_path: Path) -> None:
    """Agreeing with the misread must not be a way past the guard.

    The document carries the filer's own NIF and the operator supplies the same
    value, so ``_agreed_counterparty_tax_id`` is satisfied -- the two sides
    agree. That earlier check answers "do these match?", not "is this a real
    counterparty?", so only this guard stands between an operator who rubber-
    stamps the misread and a self-dealing row.

    Constructed deliberately so the two identifiers AGREE: an override that
    merely DIFFERED from the extracted value would be refused by the
    disagreement check instead, and would prove nothing about this guard.
    """
    own = _own_tax_id()
    evidence_id = _add_evidence(
        tmp_path,
        _invoice_lines(own, number="2026-0143"),
        filename="override.pdf",
    )

    confirmed = _invoke(
        [
            "--format", "json", "app", "ledger", "evidence", "confirm",
            "--country-code", "ES",
            "--evidence-id", evidence_id,
            "--kind", "received",
            "--counterparty-nif", own,
            "--counterparty-name", "Yo Mismo",
        ],
    )  # fmt: skip

    assert confirmed.exit_code != 0, confirmed.output
    assert "counterparty-nif" in confirmed.output


def test_a_supplier_document_confirmed_as_issued_is_refused(tmp_path: Path) -> None:
    """The opposite mis-direction from the guard above, and it needs its own gate.

    Here the document names a real third-party supplier and the operator
    confirms it as ISSUED. The self-counterparty guard sees nothing wrong: the
    counterparty is a genuine third party and the record is internally
    coherent. It simply describes the wrong direction.

    The evidence settles it. On a genuinely issued document the printed
    supplier is the filer, so an extracted supplier who is somebody else is
    positive evidence that somebody else issued it.

    Direction is not cosmetic: a received invoice booked as issued moves a
    purchase into the sales column, inverts the cuota between soportado and
    repercutido, and reaches Modelo 347 as an operation the counterparty will
    have declared with the opposite sign -- and AEAT reconciles the two
    declarations against each other.
    """
    evidence_id = _add_evidence(
        tmp_path,
        _invoice_lines(_SUPPLIER_CIF, number="2026-0500"),
        filename="supplier_as_issued.pdf",
    )

    confirmed = _invoke(
        [
            "--format", "json", "app", "ledger", "evidence", "confirm",
            "--country-code", "ES",
            "--evidence-id", evidence_id,
            "--kind", "issued",
            "--counterparty-name", "Acme Suministros SL",
        ],
    )  # fmt: skip

    assert confirmed.exit_code != 0, confirmed.output
    # Matched on a phrase only THIS gate emits. Asserting merely that the word
    # "received" appears would also pass if some unrelated refusal fired, which
    # would leave the gate unproven while the test looked green.
    assert "names another issuer" in confirmed.output
    # And it names the remedy, not just the fault.
    assert "confirm it as received" in confirmed.output


def test_the_direction_gate_declines_to_judge_a_document_with_no_issuer_identity(
    tmp_path: Path,
) -> None:
    """Positive control: silence is not evidence, so the gate must not fire on it.

    A document the scan found no issuer identity on gives the gate nothing to
    compare against. Refusing there would block every issued invoice whose
    letterhead the extractor could not read -- a gate that refuses what it
    cannot judge is worse than no gate, because it blocks correct work while
    appearing principled.
    """
    evidence_id = _add_evidence(
        tmp_path,
        ("FACTURA", "Numero: 2026-0600", "Fecha: 10/03/2026", "Base imponible: 100,00", "Total: 121,00"),
        filename="no_issuer.pdf",
    )

    confirmed = _invoke(
        [
            "--format", "json", "app", "ledger", "evidence", "confirm",
            "--country-code", "ES",
            "--evidence-id", evidence_id,
            "--kind", "issued",
            "--counterparty-name", "Cliente SL",
            "--counterparty-nif", _SUPPLIER_CIF,
        ],
    )  # fmt: skip

    assert confirmed.exit_code == 0, confirmed.output
