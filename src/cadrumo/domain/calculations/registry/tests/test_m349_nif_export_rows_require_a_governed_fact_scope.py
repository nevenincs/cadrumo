"""A missing governed-fact scope is not reported as a malformed Modelo 349 identifier."""

from __future__ import annotations

from decimal import Decimal

import pytest

from cadrumo.core.errors.hierarchy import InternalInvariantError

from .._invoice_row_materialization import normalise_m349_nif_export_rows
from ..authority import bundled_indexed_authority
from ..errors import RegistryValidationError
from ..governed_fact_scope import outside_governed_fact_validation
from ..ids import BindingId

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_NIF: BindingId = "iva-349-operador-row-nif"
_COUNTRY: BindingId = "iva-349-operador-row-codigo-pais"


def _rows(nif: str) -> dict[tuple[BindingId, int], Decimal | str]:
    return {(_NIF, 0): nif, (_COUNTRY, 0): "DE"}


def test_a_missing_scope_is_an_invariant_failure_not_a_registry_validation_refusal() -> None:
    with (
        outside_governed_fact_validation(),
        pytest.raises(InternalInvariantError, match="requires an explicit generation-pinned governed-fact scope"),
    ):
        normalise_m349_nif_export_rows(_rows("DE123456789"))


def test_the_same_row_is_normalised_inside_a_scope() -> None:
    """CONTROL: the refusal above is the missing scope, not the identifier."""
    with bundled_indexed_authority().operation():
        normalised = normalise_m349_nif_export_rows(_rows("DE123456789"))

    assert normalised[(_NIF, 0)] == "123456789"


def test_a_malformed_identifier_is_still_a_registry_validation_refusal() -> None:
    with bundled_indexed_authority().operation(), pytest.raises(RegistryValidationError):
        normalise_m349_nif_export_rows(_rows("DE12"))
