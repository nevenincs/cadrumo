"""An amendment must state the detail rows that constitute the declaration.

For M184, M232, M347 and M349 the per-counterpart rows ARE the return. The
amendment path never set them, and neither of the state transitions after it
recomputes anything, so an amended M347 was filed declaring no counterparties
at all -- a substantive false statement about the period rather than a missing
annex.

Inheriting the baseline's rows would not have fixed it. LGT art. 122.2 para. 2
gives the two amendment kinds opposite meanings: a complementaria COMPLETES the
original, so its rows are the ones being added, while a sustitutiva REPLACES
it, so its rows are the full corrected set. Nothing in the call distinguishes
them, and the corrected aggregate totals were computed for neither reading. So
the caller states the rows and the code refuses to guess.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

import pytest

from ....domain.modelos.calculation_revision import derive_calculation_revision_id
from ....domain.modelos.row_models import (
    DETAIL_ROW_BEARING_MODELOS,
    Modelo347ContraparteRow,
    ModeloDetailRow,
)
from ..action_errors import AmendmentDetailRowsRequiredError
from ..amendment_actions import _require_amendment_detail_rows

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _revision_id(*, detail_rows: Sequence[ModeloDetailRow] | None = None) -> str:
    """Derive a revision id whose only moving part is ``detail_rows``.

    Spelled with explicit keywords rather than a shared mapping unpacked with
    ``**``: the signature is keyword-only, and a dict unpack hides every
    argument type from the checker.
    """
    if detail_rows is None:
        return derive_calculation_revision_id(
            work_unit_id="a" * 64,
            input_values_by_casilla_id={},
            binding_overrides={},
            casilla_values={},
            source_provenance=(),
            filing_instance_evidence=None,
        )
    return derive_calculation_revision_id(
        work_unit_id="a" * 64,
        input_values_by_casilla_id={},
        binding_overrides={},
        casilla_values={},
        source_provenance=(),
        filing_instance_evidence=None,
        detail_rows=detail_rows,
    )


def _counterparty() -> Modelo347ContraparteRow:
    return Modelo347ContraparteRow(
        nif="B12345678",
        nombre="Suministros Delta SL",
        importe_Q1=Decimal("4000.00"),
    )


@pytest.mark.parametrize("modelo", sorted(DETAIL_ROW_BEARING_MODELOS))
def test_a_row_bearing_modelo_refuses_an_amendment_that_omits_its_rows(modelo: str) -> None:
    """Silence is not a nil declaration; the two amendment kinds read it apart."""
    with pytest.raises(AmendmentDetailRowsRequiredError):
        _require_amendment_detail_rows(modelo=modelo, supplied=None)


@pytest.mark.parametrize("modelo", sorted(DETAIL_ROW_BEARING_MODELOS))
def test_an_explicitly_empty_set_is_an_answer_and_is_accepted(modelo: str) -> None:
    """Declaring that the period had no counterparts is a statement, not silence."""
    assert _require_amendment_detail_rows(modelo=modelo, supplied=[]) == ()


@pytest.mark.parametrize("modelo", ["303", "130", "210"])
def test_a_modelo_whose_rows_are_not_the_declaration_needs_no_answer(modelo: str) -> None:
    """210 is the interesting one: it HAS a row type, and still does not qualify.

    ``Modelo210AgrupacionRentaRow`` groups several rentas into one return as a
    convenience, so a 210 with no grouping rows is an ordinary single-renta
    return rather than a nil declaration. Requiring rows there would refuse a
    perfectly complete amendment.
    """
    assert _require_amendment_detail_rows(modelo=modelo, supplied=None) == ()


def test_supplied_rows_are_carried_through_unchanged() -> None:
    """The guard resolves, it does not filter."""
    row = _counterparty()
    assert _require_amendment_detail_rows(modelo="347", supplied=[row]) == (row,)


def test_detail_rows_move_the_revision_content_address() -> None:
    """Why the rows must reach ``derive_calculation_revision_id`` too.

    ``detail_rows`` is part of the revision's content address. A draft carrying
    rows whose id was derived without them would address itself as a revision
    declaring none, and the upsert would then land on -- and overwrite --
    whatever already sits at that address.
    """
    assert _revision_id(detail_rows=()) != _revision_id(detail_rows=(_counterparty(),))


def test_omitting_the_argument_addresses_a_revision_exactly_as_an_empty_set_does() -> None:
    """The no-churn guarantee for every modelo that declares no rows.

    The amendment path now passes ``detail_rows`` explicitly on every call. If
    an empty tuple addressed differently from the previous omission, every
    already-filed non-bearing revision would move address at once.
    """
    assert _revision_id() == _revision_id(detail_rows=())
