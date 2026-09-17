"""The registry-declared clave scope of Modelo 190 perceptor casillas.

Every case reads the published registry: the scope, the clave vocabulary and
the revision bindings are the shipped authority, not fixtures restating them.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date

import pytest

from ....core.casilla_id import validated_casilla_id
from ...calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ...calculations.registry.errors import RegistryValidationError
from ..perceptor_clave_scope import (
    ClaveScopeToken,
    PerceptorClaveScope,
    check_perceptor_clave_scope,
    perceptor_clave_scope_failures,
    resolve_perceptor_clave_scope,
    row_field_value_bindings,
    rows_missing_scoped_casilla,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_DESCENDANTS = validated_casilla_id("perc.descendientes-menores-3-total")
_CONTRACT = validated_casilla_id("perc.contrato-relacion")
_UNSCOPED = validated_casilla_id("perc.percepcion-dineraria")


@pytest.fixture
def operation() -> Iterator[PinnedAuthorityOperation]:
    with bundled_indexed_authority().operation() as leased:
        yield leased


def _scope(operation: PinnedAuthorityOperation, year: int) -> PerceptorClaveScope:
    return resolve_perceptor_clave_scope(effective_date=date(year, 12, 31), authority=operation)


@pytest.mark.parametrize(
    ("raw", "clave", "subclave"),
    [("A", "A", None), ("B.01", "B", "01"), (" G.08 ", "G", "08")],
)
def test_a_token_names_a_clave_and_optionally_one_subclave(raw: str, clave: str, subclave: str | None) -> None:
    assert ClaveScopeToken.parse(raw) == ClaveScopeToken(clave=clave, subclave=subclave)


@pytest.mark.parametrize("raw", ["", ".01", "B.1", "B.001", "B.xx"])
def test_a_malformed_token_is_refused(raw: str) -> None:
    with pytest.raises(RegistryValidationError, match=r"is not CLAVE or CLAVE\.NN"):
        ClaveScopeToken.parse(raw)


def test_family_data_belongs_to_work_income_claves_only(operation: PinnedAuthorityOperation) -> None:
    scope = _scope(operation, 2024)
    assert scope.modelo_id == "190"
    assert scope.admits(_DESCENDANTS, "A", None)
    assert scope.admits(_DESCENDANTS, "B", "01")
    assert not scope.admits(_DESCENDANTS, "B", "02")
    assert not scope.admits(_DESCENDANTS, "G", "01")
    assert scope.admits(_CONTRACT, "A", None)
    assert not scope.admits(_CONTRACT, "C", None)
    # A casilla the registry does not scope applies to every record.
    assert not scope.is_scoped(_UNSCOPED)
    assert scope.admits(_UNSCOPED, "G", "01")


def test_each_design_edition_carries_its_own_subclave_list(operation: PinnedAuthorityOperation) -> None:
    """The 2025 design widens clave B to subclaves 04 and 99; the 2024 one does not."""
    assert not _scope(operation, 2024).admits(_DESCENDANTS, "B", "04")
    assert _scope(operation, 2025).admits(_DESCENDANTS, "B", "04")
    assert _scope(operation, 2025).admits(_DESCENDANTS, "B", "99")


def test_an_ejercicio_before_every_variant_resolves_no_scope(operation: PinnedAuthorityOperation) -> None:
    with pytest.raises(RegistryValidationError):
        _scope(operation, 2022)


def test_row_casillas_map_to_the_row_bindings_that_fill_them(operation: PinnedAuthorityOperation) -> None:
    revision = operation.snapshot("190", filing_year=2024, period="0A").revision
    bindings = row_field_value_bindings(revision)
    assert bindings[_DESCENDANTS] == "modelo-190-perceptor-row-descendientes-menores-3-total"
    assert _UNSCOPED in bindings


def test_only_in_scope_rows_without_a_value_are_missing(operation: PinnedAuthorityOperation) -> None:
    scope = _scope(operation, 2024)
    value_binding = "modelo-190-perceptor-row-descendientes-menores-3-total"
    rows = {
        scope.row_clave_binding: {"0": "G", "1": "A", "2": "A", "3": "B", "4": "B"},
        scope.row_subclave_binding: {"0": "01", "3": "01", "4": "02"},
        value_binding: {"2": "0"},
    }
    missing = rows_missing_scoped_casilla(
        scope,
        casilla_id=_DESCENDANTS,
        value_binding=value_binding,
        row_binding_values=rows,
    )
    # G.01 and B.02 owe nothing; the A row with a zero is answered.
    assert missing == ("1", "3")


def test_the_scope_names_only_declared_casillas_and_registry_claves(operation: PinnedAuthorityOperation) -> None:
    scope = _scope(operation, 2025)
    revision = operation.snapshot("190", filing_year=2025, period="0A").revision
    declared = frozenset(casilla.id for casilla in revision.casillas)
    assert perceptor_clave_scope_failures(scope, casilla_ids=declared, authority=operation) == []

    without = declared - {_DESCENDANTS}
    failures = perceptor_clave_scope_failures(scope, casilla_ids=without, authority=operation)
    assert failures == [f"perceptor clave scope names casilla {_DESCENDANTS!r}, which the revision does not declare"]

    unknown = PerceptorClaveScope(
        modelo_id=scope.modelo_id,
        row_clave_binding=scope.row_clave_binding,
        row_subclave_binding=scope.row_subclave_binding,
        casillas={_DESCENDANTS: (ClaveScopeToken(clave="Z", subclave=None),)},
        effective_date=scope.effective_date,
    )
    (failure,) = perceptor_clave_scope_failures(unknown, casilla_ids=declared, authority=operation)
    assert "clave 'Z' is not in the registry vocabulary" in failure


def test_the_snapshot_check_claims_only_revisions_carrying_perceptor_records(
    operation: PinnedAuthorityOperation,
) -> None:
    del operation  # the leased operation scopes the check's governed-fact read
    revision_bindings = frozenset({"modelo-190-perceptor-row-clave", "modelo-190-perceptor-row-subclave"})
    assert check_perceptor_clave_scope("111", frozenset(), frozenset(), revision_bindings) == []
    assert check_perceptor_clave_scope("190", frozenset(), frozenset(), frozenset()) == []
