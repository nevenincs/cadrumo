"""Contract tests for the unresolved-binding diagnostic channel.

The engine already surfaces unresolved RELATIONS (``unresolved_relation_ids`` ->
non-blocking ``_UnresolvedFormulaDependencyError`` + a
``CalculationSourceDiagnostic``). These tests pin the mirrored BINDING channel:

* the resolver-population discriminator
  (:func:`expected_but_missing_binding_ids`) fires ONLY for a casilla-bound
  binding whose enrolled resolver RAN for a PRESENT source (the source kind is in
  ``owned_sources``) but produced no value — the silent-zero breach of
  ``no-silent-under-declaration`` — and stays silent for the legitimate
  absent-source zero;
* :func:`merge_source_resolutions` carries ``unresolved_binding_ids`` and
  discards a binding that a later resolver resolves;
* the formula-leaf escape makes a missing-binding formula leaf NON-blocking when
  (and only when) the binding id is marked unresolved.

The discriminator test grounds against the real committed Modelo 303 1T snapshot,
whose 19 ``ledger_iva_aggregation``-bound cuota casillas are the production
silent-zero surface this channel protects; it is not a tautology because it
exercises the registry's real bound-casilla / binding-source structure against
the discriminator, not a hand-built fixture echoing the formula under test.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.schema import ModeloRevision
from cadrumo.domain.calculations.registry.schema_formula import FormulaExpression

from ....core import BindingSourceKind
from ....core.resources import resources
from ....domain.calculations.registry.formula_runtime import (
    _evaluate_expression,
    _UnresolvedFormulaDependencyError,
)
from ...aggregation import CalculationSourceResolution, merge_source_resolutions
from .._calculation_source_staging import expected_but_missing_binding_ids

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_LEDGER_IVA = BindingSourceKind.LEDGER_IVA_AGGREGATION


def _modelo_303_revision() -> ModeloRevision:
    return resources().modelos.authority.snapshot("303", filing_year=2024, period="1T").revision


def test_expected_but_missing_fires_when_present_source_resolved_no_value() -> None:
    """A casilla-bound binding whose PRESENT source resolved no value is flagged.

    The Modelo 303 1T revision carries 19 ``ledger_iva_aggregation``-bound cuota
    casillas. With the source present (in ``owned_sources``) but no binding value
    resolved, every one is an expected-but-missing silent-zero surface and must be
    flagged so the formula leaf escapes and an advisory fires — NOT a silent zero.
    """
    revision = _modelo_303_revision()

    missing = expected_but_missing_binding_ids(
        revision,
        owned_sources=frozenset({_LEDGER_IVA}),
        resolved_binding_values={},
    )

    assert missing, "present-source-no-value must flag the ledger-iva bound casillas"
    # Every flagged row is a real BOUND casilla whose binding declares the present source.
    for binding_id, casilla_id, source in missing:
        assert source == _LEDGER_IVA
        assert binding_id
        assert casilla_id


def test_expected_but_missing_stays_silent_when_source_absent() -> None:
    """A binding whose source is ABSENT is a legitimate zero and must NOT fire.

    When the resolver never ran for the source (the source kind is not in
    ``owned_sources``), the taxpayer simply has no such data; the bound casilla's
    zero is correct and surfacing an advisory would be noise.
    """
    revision = _modelo_303_revision()

    missing = expected_but_missing_binding_ids(
        revision,
        owned_sources=frozenset(),
        resolved_binding_values={},
    )

    assert missing == ()


def test_expected_but_missing_stays_silent_when_present_source_resolved_values() -> None:
    """A present source that DID resolve the binding value must NOT fire."""
    revision = _modelo_303_revision()

    flagged = expected_but_missing_binding_ids(
        revision,
        owned_sources=frozenset({_LEDGER_IVA}),
        resolved_binding_values={},
    )
    resolved_values = {binding_id: Decimal("0") for binding_id, _casilla_id, _source in flagged}

    assert (
        expected_but_missing_binding_ids(
            revision,
            owned_sources=frozenset({_LEDGER_IVA}),
            resolved_binding_values=resolved_values,
        )
        == ()
    )


def test_merge_carries_unresolved_binding_ids_and_discards_resolved() -> None:
    """``merge_source_resolutions`` accumulates unresolved ids; a later value discards one."""
    unresolved_only = CalculationSourceResolution(
        resolver_id="resolver-a",
        owned_sources=(_LEDGER_IVA,),
        unresolved_binding_ids=("binding-x", "binding-y"),
    )
    resolves_x = CalculationSourceResolution(
        resolver_id="resolver-b",
        binding_values={"binding-x": Decimal("12.00")},
    )

    merged = merge_source_resolutions((unresolved_only, resolves_x))

    # binding-x resolved by a later resolver -> dropped; binding-y still unresolved.
    assert merged.unresolved_binding_ids == ("binding-y",)
    assert merged.binding_values["binding-x"] == Decimal("12.00")


def _evaluate_binding_leaf(*, unresolved: frozenset[str]) -> Decimal:
    return _evaluate_expression(
        FormulaExpression(binding="b1"),
        values={},
        binding_values={},
        parameters={},
        date_context={"filing_period": date(2025, 12, 31)},
        relation_values={},
        unresolved_relation_ids=frozenset(),
        unresolved_binding_ids=unresolved,
        unresolved_casilla_ids=set(),
        operand_refs=[],
        operand_casilla_refs=[],
        operand_values=[],
    )


def test_unmarked_missing_binding_leaf_raises_hard() -> None:
    """A missing binding leaf NOT marked unresolved is still a hard validation error."""
    with pytest.raises(RegistryValidationError) as exc:
        _evaluate_binding_leaf(unresolved=frozenset())
    assert exc.value.translated_message == "errors.calc.binding_value_missing"


def test_marked_unresolved_binding_leaf_escapes_non_blocking() -> None:
    """A missing binding leaf marked unresolved escapes non-blocking (mirrors relations).

    The formula target depending on the unresolved binding is omitted rather than
    raising ``binding_value_missing`` — the same non-blocking contract the relation
    channel provides via ``_UnresolvedFormulaDependencyError``.
    """
    with pytest.raises(_UnresolvedFormulaDependencyError) as exc:
        _evaluate_binding_leaf(unresolved=frozenset({"b1"}))
    assert exc.value.dependency_ids == ("b1",)
