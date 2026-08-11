"""The DID page reaches disk for every disposition AEAT needs an account for.

The page was gated on refund-ness, so a **domiciliación del ingreso** (``U``) --
an ingreso the taxpayer pays by direct debit -- had its account page suppressed.
The filing went out with no account for AEAT to charge, silently, on the surface
a human files from.

AEAT's own field labelling is the authority here and it is unambiguous: position
23 is ``Domiciliación/Devolución - IBAN``, the single dual-purpose field on the
page, while the SWIFT-BIC, bank name, address, city, country code and marca SEPA
fields are each prefixed ``Devolución -``. So the page belongs to a charge as
well as a refund, and it belongs to a charge for its IBAN alone.

The axis is deliberately NOT refund-ness. Refund-ness also drives the
compensación carry decision, so answering both questions with one predicate made
a bank-details question able to move a carry-forward. These tests assert the
separation as well as the emission, because the tidying that would undo this fix
is exactly "just add U to the refund set".
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from ....core import (
    Period,
    PriorDomiciliationElection,
    ResultDisposition,
    result_disposition_is_refund,
    result_disposition_requires_bank_account,
)
from ....domain.calculations.registry import RegistrySnapshotRef
from ....domain.filing import ModeloDraft, ModeloValue, ModeloValueKind
from ....domain.submission import ModeloDraftStatus
from .._export_parity import _did_page_suppressed
from ._export_support import _schema_provider

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_DID_PAGE_RECORD_TYPE = "page_did"


def _approved_m303_draft(*, casilla_111: Decimal | None = None) -> ModeloDraft:
    provider = _schema_provider(modelos=("303",))
    subview = provider.get_subview("303")
    period = Period.from_year_and_code(2026, "1T")
    timestamp = datetime(2026, 5, 21, 12, 3, tzinfo=UTC)
    return ModeloDraft(
        draft_id="d" + "0" * 63,
        modelo="303",
        period=period,
        profile_tax_id="X1234567L",
        subject_tax_id="X1234567L",
        snapshot_ref=RegistrySnapshotRef(
            modelo="303",
            revision_id=subview.revision_id,
            modelo_year=period.filing_year,
            period=period.registry_token,
        ),
        status=ModeloDraftStatus.APROBADO,
        values=(
            ModeloValue(
                casilla_id="111",
                value=casilla_111,
                kind=ModeloValueKind.LITERAL,
                source="operator-declared Nota 3 amount",
            ),
        )
        if casilla_111 is not None
        else (),
        created_at=timestamp,
        updated_at=timestamp,
        schema_version=subview.schema_version,
    )


def _modelo_303_did_record():
    """Return the real DID record from the real M303 layout.

    Read from the registry rather than constructed, so a change to the record's
    declared ``record_type`` fails these tests instead of leaving them asserting
    against a shape the layout no longer has.
    """
    provider = _schema_provider(modelos=("303",))
    layout = provider.get_subview("303").export_layouts[0]
    matching = [record for record in layout.records if record.record_type == _DID_PAGE_RECORD_TYPE]
    assert len(matching) == 1, f"expected exactly one DID page record in the M303 layout, found {len(matching)}"
    return matching[0]


@pytest.mark.parametrize(
    "code",
    [
        ResultDisposition.DEVOLUCION.value,
        ResultDisposition.CUENTA_CORRIENTE_DEVOLUCION.value,
        ResultDisposition.DEVOLUCION_TRANSFERENCIA_EXTRANJERO.value,
        ResultDisposition.DOMICILIACION.value,
    ],
)
def test_the_account_page_reaches_disk_for_every_account_bearing_disposition(code: str) -> None:
    """``U`` is in this list, and its absence was the defect."""
    assert not _did_page_suppressed(
        _modelo_303_did_record(),
        draft=_approved_m303_draft(),
        headers={"declaration_type": code},
        prior_domiciliation_election=PriorDomiciliationElection.KEEP,
    )


@pytest.mark.parametrize(
    "code",
    [
        ResultDisposition.COMPENSACION.value,
        ResultDisposition.INGRESO.value,
        ResultDisposition.NEGATIVA.value,
    ],
)
def test_the_account_page_stays_suppressed_where_no_account_is_needed(code: str) -> None:
    """The negative side, so the guard is not simply disabled.

    A fix that emitted the page unconditionally would satisfy the test above and
    write the empty 823-byte account record the guard exists to prevent.
    """
    assert _did_page_suppressed(
        _modelo_303_did_record(),
        draft=_approved_m303_draft(),
        headers={"declaration_type": code},
        prior_domiciliation_election=PriorDomiciliationElection.KEEP,
    )


def test_cuenta_corriente_ingreso_stays_suppressed_as_an_unsettled_question() -> None:
    """``G`` is excluded, and this records that the exclusion is ungrounded.

    Settlement through the cuenta corriente tributaria may legitimately need no
    debit account, and no bundled AEAT text has been read that settles it. If
    someone later establishes that it does, this test is where the current answer
    admits it was never established.
    """
    assert _did_page_suppressed(
        _modelo_303_did_record(),
        draft=_approved_m303_draft(),
        headers={"declaration_type": ResultDisposition.CUENTA_CORRIENTE_INGRESO.value},
        prior_domiciliation_election=PriorDomiciliationElection.KEEP,
    )


def test_an_unparseable_disposition_suppresses_rather_than_guessing() -> None:
    """An unreadable header must not emit an account page on speculation."""
    assert _did_page_suppressed(
        _modelo_303_did_record(),
        draft=_approved_m303_draft(),
        headers={"declaration_type": "?"},
        prior_domiciliation_election=PriorDomiciliationElection.KEEP,
    )
    assert _did_page_suppressed(
        _modelo_303_did_record(),
        draft=_approved_m303_draft(),
        headers={},
        prior_domiciliation_election=PriorDomiciliationElection.KEEP,
    )


def test_domiciliacion_needs_the_page_without_being_a_refund() -> None:
    """The separation, asserted where the export reads it.

    The sibling core test pins the two predicates apart. This one pins that the
    EXPORT guard follows the account axis rather than the refund axis, which is
    the reading that was wrong. Folding ``U`` into the refund set would keep this
    passing while moving the carry decision, so both assertions are made here.
    """
    assert result_disposition_requires_bank_account(ResultDisposition.DOMICILIACION)
    assert not result_disposition_is_refund(ResultDisposition.DOMICILIACION), (
        "U became a refund disposition, which changes what a domiciliacion period carries forward"
    )
    assert not _did_page_suppressed(
        _modelo_303_did_record(),
        draft=_approved_m303_draft(),
        headers={"declaration_type": ResultDisposition.DOMICILIACION.value},
        prior_domiciliation_election=PriorDomiciliationElection.KEEP,
    )


@pytest.mark.parametrize(
    "disposition",
    [
        ResultDisposition.DEVOLUCION,
        ResultDisposition.CUENTA_CORRIENTE_DEVOLUCION,
        ResultDisposition.DEVOLUCION_TRANSFERENCIA_EXTRANJERO,
        ResultDisposition.DOMICILIACION,
    ],
)
def test_prior_domiciliation_x_never_suppresses_a_currently_account_bearing_disposition(
    disposition: ResultDisposition,
) -> None:
    """X removes only the Nota-3 route; D/V/X/U retain their own DID requirement."""
    assert not _did_page_suppressed(
        _modelo_303_did_record(),
        draft=_approved_m303_draft(casilla_111=Decimal("0")),
        headers={
            "declaration_type": disposition.value,
            "autoliq_rectificativa": "1",
            "prior_domiciliation_action": "X",
        },
        prior_domiciliation_election=PriorDomiciliationElection.CANCEL_OR_MODIFY,
    )


def test_casilla_111_without_a_rectificativa_leaves_an_ordinary_c_filing_unchanged() -> None:
    """Nota 3 has no effect on an ordinary filing even when c111 carries zero."""
    assert _did_page_suppressed(
        _modelo_303_did_record(),
        draft=_approved_m303_draft(casilla_111=Decimal("0")),
        headers={"declaration_type": ResultDisposition.COMPENSACION.value},
        prior_domiciliation_election=PriorDomiciliationElection.KEEP,
    )
