"""Real-behaviour tests for the printed-vs-recorded total cross-check on confirm.

The confirm path DERIVES an invoice's ``grand_total`` from the taxable base and
the registry-resolved rate slot; the figure printed on the document never
overwrites it. These tests pin the other half of that discipline: when the two
disagree, the disagreement is reported rather than discarded.

Builds real text-bearing PDFs in memory (reportlab), stores them through the
real encrypted evidence path, and confirms them through
:func:`~application.ledger.invoice_confirmation.confirm_invoice_draft_from_evidence`. No mocks.

See Also:
    :class:`~application.ledger.evidence_draft.PrintedTotalDiscrepancy`
        The record describing a printed-vs-recorded total disagreement.
    :func:`~application.ledger.evidence_draft.printed_total_discrepancy`
        The comparison this module exercises.
    :func:`~application.ledger.invoice_confirmation.confirm_invoice_draft_from_evidence`
        Confirm step that carries the discrepancy on its result.
"""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from ....adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core.config import Settings
from ....core.confirmation_gate import FindingResolutionAction
from ....domain.invoices.enums import InvoiceClass
from ....domain.iva.classification import InvoiceKind
from ....domain.iva.schema import IvaCategory
from ....tests.pdf_fixtures import text_pdf_bytes
from ..confirmation_gate import FindingResolution, confirmation_blockers
from ..invoice_confirmation import confirm_invoice_draft_from_evidence
from ..invoice_draft_extraction import extract_invoice_draft_from_evidence
from ._evidence_test_support import _BUCKET_ID, _make_svc
from ._evidence_test_support import runtime_profile as runtime_profile
from ._evidence_test_support import seeded_filer_profile as seeded_filer_profile
from ._ledger_value_fixtures import isolated_settings, secure_objects
from ._loopback_reader import serving_a_loopback_reader

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]
__all__ = ["isolated_settings", "runtime_profile", "secure_objects", "seeded_filer_profile"]

# A real Spanish CIF (AEAT checksum-valid).
_SUPPLIER_CIF = "B12345674"

# base 100,00 + cuota 21,00 = 121,00. The printed total equals the derived one.
_COHERENT_INVOICE_LINES = (
    "Factura de Acme Suministros SL",
    f"NIF: {_SUPPLIER_CIF}",
    "Numero de factura: 2026-0142",
    "Fecha: 10/03/2026",
    "Base imponible: 100,00",
    "IVA 21%",
    "Cuota IVA: 21,00",
    "Total factura: 121,00",
)

# A recargo de equivalencia invoice (LIVA art. 161): the supplier repercutes
# 5,20 on the entrega, so the document totals 126,20 while base + cuota is
# 121,00. The recargo has nowhere to go on the confirm path, so the record
# understates the document by exactly the surcharge -- which is the whole point
# of the cross-check.
_RECARGO_INVOICE_LINES = (
    "Factura de Acme Suministros SL",
    f"NIF: {_SUPPLIER_CIF}",
    "Numero de factura: 2026-0199",
    "Fecha: 11/03/2026",
    "Base imponible: 100,00",
    "IVA 21%",
    "Cuota IVA: 21,00",
    "Recargo de equivalencia 5,2%: 5,20",
    "Total factura: 126,20",
)

# A real loopback reader. These cases compare a COHERENT document against a
# RECARGO one, so a single canned reply would answer both identically and the
# discrepancy assertion would be comparing the stub to itself. Each document is
# answered with its own printed figures.
#
# Deliberately NOT supplying `recargo_amount`: the confirm path is what has
# nowhere to put the recargo, and that gap is the very thing these cases exist
# to detect. Supplying it here would repair the document before the code saw it.

_COHERENT_FIELDS = {
    "supplier_tax_id": _SUPPLIER_CIF,
    "supplier_tax_id_anchor": _SUPPLIER_CIF,
    "invoice_number": "2026-0142",
    "invoice_number_anchor": "2026-0142",
    "invoice_date": "2026-03-10",
    "invoice_date_anchor": "10/03/2026",
    "taxable_base": "100,00",
    "taxable_base_anchor": "100,00",
    "iva_rate": "21",
    "iva_rate_anchor": "21%",
    "iva_amount": "21,00",
    "iva_amount_anchor": "21,00",
    "grand_total": "121,00",
    "grand_total_anchor": "121,00",
}

_RECARGO_FIELDS = {
    **_COHERENT_FIELDS,
    "invoice_number": "2026-0199",
    "invoice_number_anchor": "2026-0199",
    "invoice_date": "2026-03-11",
    "invoice_date_anchor": "11/03/2026",
    "grand_total": "126,20",
    "grand_total_anchor": "126,20",
}


@pytest.fixture(autouse=True)
def _loopback_reader() -> Iterator[None]:
    """Serve a real reading endpoint keyed on each document's own figures."""
    with serving_a_loopback_reader(
        (("2026-0199", _RECARGO_FIELDS), ("2026-0142", _COHERENT_FIELDS)),
    ):
        yield


def _operator_attestations(
    *,
    evidence_id: str,
    isolated_settings: Settings,
) -> tuple[FindingResolution, ...]:
    """Answer each blocking finding this document raises, as the operator must.

    The confirm boundary refuses a document with an unanswered finding, and a
    recargo de equivalencia invoice raises an arithmetic-closure finding because
    the reading path does not recover the surcharge as a component. These cases
    are about the printed-total cross-check rather than about the gate, so the
    operator step the gate mandates is performed here explicitly --- one
    attestation per finding, each naming why the document is accepted as printed.

    Deliberately built per finding rather than as a blanket clearance: a helper
    that cleared the set unconditionally would be a bulk confirm reached through
    the test suite.
    """
    draft = extract_invoice_draft_from_evidence(
        bucket_id=_BUCKET_ID,
        evidence_id=evidence_id,
        settings=isolated_settings,
    )
    return tuple(
        FindingResolution(
            blocker_id=blocker.blocker_id,
            action=FindingResolutionAction.ATTEST,
            note="the document prints a recargo de equivalencia this reading path does not recover as a component",
        )
        for blocker in confirmation_blockers(draft)
    )


def _confirm(
    lines: tuple[str, ...],
    *,
    isolated_settings: Settings,
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
    filename: str,
):
    pdf_path = tmp_path / filename
    pdf_path.write_bytes(text_pdf_bytes(lines))
    svc = _make_svc(isolated_settings, secure_objects)
    record = svc.add(bucket_id=_BUCKET_ID, source_path=pdf_path).record
    return confirm_invoice_draft_from_evidence(
        counterparty_country="ES",
        bucket_id=_BUCKET_ID,
        kind=InvoiceKind.RECEIVED,
        evidence_id=record.evidence_id,
        counterparty_name="Acme Suministros SL",
        settings=isolated_settings,
        resolutions=_operator_attestations(
            evidence_id=record.evidence_id,
            isolated_settings=isolated_settings,
        ),
        invoice_repository=InvoiceCatalogueRepository(objects=secure_objects),
    )


def test_a_recargo_invoice_reports_the_printed_total_it_could_not_represent(
    isolated_settings: Settings,
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
) -> None:
    """The document totals 126,20; the record carries 121,00 and says so.

    This is the silent under-declaration the cross-check exists to catch: the
    recargo is a real amount the supplier charged, the record cannot hold it,
    and before this check the 5,20 simply vanished behind a valid-looking
    invoice.
    """
    result = _confirm(
        _RECARGO_INVOICE_LINES,
        isolated_settings=isolated_settings,
        secure_objects=secure_objects,
        tmp_path=tmp_path,
        filename="factura_recargo.pdf",
    )

    # The derived total still wins -- the printed figure never overwrites it.
    assert result.invoice.grand_total == Decimal("121.00")

    discrepancy = result.total_discrepancy
    assert discrepancy is not None, "a 5,20 recargo must not vanish silently"
    assert discrepancy.printed_total == Decimal("126.20")
    assert discrepancy.recorded_total == Decimal("121.00")
    # Positive difference is the under-declaration direction.
    assert discrepancy.difference == Decimal("5.20")


def test_a_coherent_invoice_reports_no_discrepancy(
    isolated_settings: Settings,
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
) -> None:
    """An advisory that fires on a clean document trains operators to ignore it.

    The negative control: base + cuota equals the printed total, so there is
    nothing to report and nothing is reported.
    """
    result = _confirm(
        _COHERENT_INVOICE_LINES,
        isolated_settings=isolated_settings,
        secure_objects=secure_objects,
        tmp_path=tmp_path,
        filename="factura.pdf",
    )

    assert result.invoice.grand_total == Decimal("121.00")
    assert result.total_discrepancy is None


def test_the_guarded_no_op_retry_still_reports_the_discrepancy(
    isolated_settings: Settings,
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
) -> None:
    """A re-confirm must not be a way to clear the alert.

    The second confirm resolves to the same identity and returns the existing
    invoice unchanged (``created=False``). If the discrepancy were computed only
    on the minting branch, an operator who re-ran the command would see a clean
    result for a document that still disagrees with its record.
    """
    pdf_path = tmp_path / "factura_recargo.pdf"
    pdf_path.write_bytes(text_pdf_bytes(_RECARGO_INVOICE_LINES))
    svc = _make_svc(isolated_settings, secure_objects)
    record = svc.add(bucket_id=_BUCKET_ID, source_path=pdf_path).record

    attestations = _operator_attestations(evidence_id=record.evidence_id, isolated_settings=isolated_settings)

    def _run():
        return confirm_invoice_draft_from_evidence(
            counterparty_country="ES",
            bucket_id=_BUCKET_ID,
            kind=InvoiceKind.RECEIVED,
            evidence_id=record.evidence_id,
            counterparty_name="Acme Suministros SL",
            settings=isolated_settings,
            resolutions=attestations,
            invoice_repository=InvoiceCatalogueRepository(objects=secure_objects),
        )

    first = _run()
    second = _run()

    assert first.created is True
    assert second.created is False, "the retry must be the guarded no-op, not a second row"
    assert second.total_discrepancy is not None, "a retry must not clear the alert"
    assert second.total_discrepancy.difference == Decimal("5.20")


def _confirm_with(
    lines: tuple[str, ...],
    *,
    isolated_settings: Settings,
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
    filename: str,
    **overrides: Any,
):
    """Confirm with operator overrides, the boundary's widened parameter set."""
    pdf_path = tmp_path / filename
    pdf_path.write_bytes(text_pdf_bytes(lines))
    svc = _make_svc(isolated_settings, secure_objects)
    record = svc.add(bucket_id=_BUCKET_ID, source_path=pdf_path).record
    return confirm_invoice_draft_from_evidence(
        counterparty_country="ES",
        bucket_id=_BUCKET_ID,
        kind=InvoiceKind.RECEIVED,
        evidence_id=record.evidence_id,
        counterparty_name="Acme Suministros SL",
        settings=isolated_settings,
        resolutions=_operator_attestations(
            evidence_id=record.evidence_id,
            isolated_settings=isolated_settings,
        ),
        invoice_repository=InvoiceCatalogueRepository(objects=secure_objects),
        **overrides,
    )


def test_a_declared_recargo_persists_and_clears_the_printed_total_discrepancy(
    isolated_settings: Settings,
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
) -> None:
    """The operator can now resolve the discrepancy the reader detects.

    The sibling test above pins the state this closes: the document totals
    126,20, the record could hold only 121,00, and the 5,20 recargo was
    reported as an unresolvable discrepancy. The detector was right and the
    operator had nowhere to put the answer.

    BOTH halves are asserted deliberately. Persisting the recargo without
    clearing the advisory would leave it firing on a now-correct record -- a
    new false positive, and the kind that teaches operators to ignore the
    alert that matters. Clearing it without persisting the recargo would be
    worse: the under-declaration would be silent again.
    """
    result = _confirm_with(
        _RECARGO_INVOICE_LINES,
        isolated_settings=isolated_settings,
        secure_objects=secure_objects,
        tmp_path=tmp_path,
        filename="factura_recargo_declarada.pdf",
        recargo_amount=Decimal("5.20"),
    )

    assert result.invoice.recargo_amount == Decimal("5.20")
    # The recargo rides INSIDE the invoice total (LIVA art. 161), so the record
    # now equals what the document printed.
    assert result.invoice.grand_total == Decimal("126.20")
    assert result.total_discrepancy is None, "the advisory must not fire on a record that now matches the document"


def test_the_confirm_boundary_carries_the_writer_regime_axes(
    isolated_settings: Settings,
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
) -> None:
    """Confirming from evidence reaches the same axes as direct entry.

    Before this the confirm boundary accepted only the extraction draft's
    field set, so an operator confirming a rectificativa or a
    retención-bearing invoice from evidence had to abandon the evidence path
    and re-enter the record by hand -- losing the attachment link that the
    confirm path exists to create.
    """
    result = _confirm_with(
        _RECARGO_INVOICE_LINES,
        isolated_settings=isolated_settings,
        secure_objects=secure_objects,
        tmp_path=tmp_path,
        filename="factura_regimen.pdf",
        recargo_amount=Decimal("5.20"),
        invoice_class=InvoiceClass.RECTIFICATIVA,
        series="R",
        rectifies_invoice_number="F-2026-0044",
        retention_rate=Decimal("0.15"),
        retention_amount=Decimal("15.00"),
        iva_category=IvaCategory.DOMESTIC_GENERAL,
    )

    invoice = result.invoice
    assert invoice.invoice_class is InvoiceClass.RECTIFICATIVA
    assert invoice.series == "R"
    assert invoice.rectifies_invoice_number == "F-2026-0044"
    assert invoice.retention_amount == Decimal("15.00")
    assert invoice.iva_category is IvaCategory.DOMESTIC_GENERAL
    # The retención is settled OUTSIDE the invoice total; only the recargo is in it.
    assert invoice.grand_total == Decimal("126.20")
