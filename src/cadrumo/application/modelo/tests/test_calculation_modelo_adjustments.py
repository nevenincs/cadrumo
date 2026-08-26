"""Canonical binding-to-casilla use in Modelo-specific calculation adjustments."""

from __future__ import annotations

import pytest

from cadrumo.domain.calculations.registry.schema_surfaces import CasillaDefinition

from ....core import Modelo
from ....domain.calculations.registry.authority import bundled_authority
from .._calculation_modelo_adjustments import (
    _m390_303_reconciliation_targets,
    detail_row_binding_values_for_calculation,
    union_detail_rows_by_identity,
)
from .._action_errors import ModeloAggregationBindingError

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_TARGET_BINDING = "modelo-390-prev-303-cuota-devengada-total"
_OTHER_BINDING = "modelo-390-prev-303-cuota-deducible-total"
_TARGET_CASILLA = "iva.anual.reconciliacion.devengada-303"
_RELATION = "modelo-390-rel-303-cuota-devengada-total"


def test_m390_reconciliation_target_reaches_a_binding_declared_only_as_an_alternate() -> None:
    """The adjustment consumes the canonical reverse join, including alternates."""
    snapshot = bundled_authority().snapshot(Modelo.M390.value, filing_year=2025, period="0A")
    revised_casillas = tuple(
        CasillaDefinition.model_validate(
            {
                **casilla.model_dump(),
                "localization_keys": casilla.localization_keys,
                "binding": _OTHER_BINDING,
                "alternate_bindings": (_TARGET_BINDING,),
            },
        )
        if casilla.id == _TARGET_CASILLA
        else casilla
        for casilla in snapshot.revision.casillas
    )
    revised_snapshot = snapshot.model_copy(
        update={"revision": snapshot.revision.model_copy(update={"casillas": revised_casillas})},
    )

    relation_targets = _m390_303_reconciliation_targets(revised_snapshot)
    target = next(row for row in relation_targets if row[0] == _RELATION)

    assert target[1] == _TARGET_BINDING
    assert target[2] == (_TARGET_CASILLA,)


class _FakeWorkUnit:
    """The bare attribute :func:`detail_row_binding_values_for_calculation` reads."""

    def __init__(self, modelo: Modelo) -> None:
        self.modelo = modelo


def _m349_operador(*, nif_comunitario: str, clave_operacion: str, importe) -> "Modelo349OperadorRow":
    from cadrumo.domain.modelos import Modelo349OperadorRow

    return Modelo349OperadorRow(
        codigo_pais="DE",
        nif_comunitario=nif_comunitario,
        razon_social="Deutschland GmbH",
        clave_operacion=clave_operacion,
        importe=importe,
    )


def test_union_keeps_disjoint_rows_from_both_supply_paths() -> None:
    """Two supply paths naming DIFFERENT counterparties both survive the union."""
    from decimal import Decimal

    resolver_row = _m349_operador(nif_comunitario="DE111111111", clave_operacion="E", importe=Decimal("1000.00"))
    caller_row = _m349_operador(nif_comunitario="FR222222222", clave_operacion="E", importe=Decimal("500.00"))

    unioned = union_detail_rows_by_identity(resolver_rows=(resolver_row,), caller_rows=(caller_row,))

    assert set(unioned) == {resolver_row, caller_row}


def test_union_collapses_an_identical_row_named_by_both_paths_to_one() -> None:
    """The bite proof this Step exists for: without the union, this pair double-counts.

    An invoice-sourced operador row the operator ALSO enters manually for the
    SAME (nif_comunitario, clave_operacion) must count once, not twice, in
    every downstream declarant-summary total.
    """
    from decimal import Decimal

    resolver_row = _m349_operador(nif_comunitario="DE123456789", clave_operacion="E", importe=Decimal("1000.00"))
    caller_row = _m349_operador(nif_comunitario="DE123456789", clave_operacion="E", importe=Decimal("1000.00"))

    unioned = union_detail_rows_by_identity(resolver_rows=(resolver_row,), caller_rows=(caller_row,))

    assert len(unioned) == 1
    values = detail_row_binding_values_for_calculation(
        work_unit=_FakeWorkUnit(Modelo.M349),
        detail_rows=unioned,
    )
    assert values["iva-349-declarante-numero-operadores"] == Decimal("1")
    assert values["iva-349-declarante-importe-operaciones"] == Decimal("1000.00")


def test_union_refuses_a_divergent_amount_for_the_same_identity_naming_the_field() -> None:
    """Two supply paths disagreeing on a declarable figure refuse, rather than pick a side."""
    from decimal import Decimal

    resolver_row = _m349_operador(nif_comunitario="DE123456789", clave_operacion="E", importe=Decimal("1000.00"))
    caller_row = _m349_operador(nif_comunitario="DE123456789", clave_operacion="E", importe=Decimal("2500.00"))

    with pytest.raises(ModeloAggregationBindingError) as excinfo:
        union_detail_rows_by_identity(resolver_rows=(resolver_row,), caller_rows=(caller_row,))

    context = excinfo.value.context
    assert context["reason"] == "detail_row_identity_conflict"
    assert context["identity"] == ["DE123456789", "E"]
    assert context["divergent_fields"] == ["importe"]


def test_union_is_a_no_op_for_a_modelo_whose_rows_come_from_one_source_alone() -> None:
    """M184/M232/M347 have no resolver-produced rows today: prove byte-identical output.

    Establishing this generically (empty resolver side) rather than special-
    casing each of the three modelos, since the union function itself has no
    modelo-specific branch -- it is the ABSENCE of a resolver contribution
    that must leave caller-supplied rows untouched, for any row kind.
    """
    from decimal import Decimal

    from cadrumo.domain.modelos import Modelo184MemberRow, Modelo232VinculadaRow, Modelo347ContraparteRow

    caller_rows = (
        Modelo184MemberRow(nif="12345678A", porcentaje=Decimal("50.00"), importe=Decimal("100.00")),
        Modelo232VinculadaRow(pais="ES", nif="87654321B", importe=Decimal("200.00")),
        Modelo347ContraparteRow(nif="11223344C", importe_Q1=Decimal("400.00")),
    )

    unioned = union_detail_rows_by_identity(resolver_rows=(), caller_rows=caller_rows)

    assert unioned == caller_rows

