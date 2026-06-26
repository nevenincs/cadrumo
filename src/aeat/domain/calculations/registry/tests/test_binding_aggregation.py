"""Typed binding-aggregation contract: model round-trip, per-family default, refusal.

Covers the typed ``BindingAggregation`` model and the single
``binding_aggregation_op`` accessor that replaced the free-form ``aggregation``
mapping and the ~10 ad-hoc ``str((binding.aggregation or {}).get("op", ...))``
re-parses with their divergent ``sum``-vs-``rows`` silent defaults, collapsing
them onto one typed op enum and one declared per-family default.

These tests assert structure, validation, and the declared default mapping —
never a hand-computed Decimal (per no-tautological-calculation-tests). The
per-family default expectations are the plan's declared contract (detail-record
families fold to ``rows``; every other source folds to ``sum``), enumerated
independently here from the accessor under test. The anti-tautology proof
corrupts the ``op`` string and asserts the strict model rejects it, so the
round-trip cannot pass while the typed boundary is broken.

The op member set (``sum``, ``rows``, ``copy``, ``count_distinct``,
``prior_pagos_fraccionados``) is the complete set declared on a binding
``aggregation`` table across ``src/aeat/_data/registry`` (confirmed by sweep);
relation aggregation and formula-expression ops are a separate, unrelated axis.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from .....core.aggregation import BindingAggregation, BindingAggregationOp
from .. import CasillaId, validated_casilla_id
from .._binding_aggregation import binding_aggregation_op, default_binding_aggregation_op
from .._schema import DataBindingDefinition

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_DUMMY_LEGAL_ID = "rd-439-2007:art-110"
_DUMMY_SOURCE_ID = "aeat-modelo-130-instructions"
_M130_INGRESOS_CASILLA: CasillaId = validated_casilla_id("01", surface="_M130_INGRESOS_CASILLA")


# Per-source well-shaped selector mappings. As of F8 the binding selector is
# validated against its source family's schema at model CONSTRUCTION, so a test
# that exercises only the aggregation axis must still supply a selector that
# satisfies the registered per-family selector model (the casilla-set / op-fact
# business rules remain a snapshot-build concern, so these minimal selectors
# only have to clear the selector model itself). A source absent from this map
# is free-form at the schema level and takes the opaque fallback selector.
_WELL_SHAPED_SELECTORS: dict[str, dict[str, object]] = {
    "previous_filing": {"source_modelo": "130", "source_casilla_id": _M130_INGRESOS_CASILLA},
    "withholding": {"fact": "retencion_sum", "claves": ("A",)},
    "payable_invoice": {"fact": "base_sum"},
    "collectible_invoice": {"fact": "base_sum"},
    "ledger_transaction": {"fact": "base_sum"},
    "ledger_oss_aggregation": {
        "regime": "external_scheme",
        "destination_member_state": "de",
        "rate_kind": "general",
        "invoice_direction": "issued",
        "transaction_kinds": ("external_scheme_services",),
        "fact": "iva_amount_sum",
    },
    "ledger_iva_aggregation": {
        "categories": ("domestic_general_21",),
        "rate_kinds": ("general",),
        "flow_direction": "repercutido",
        "fact": "iva_amount_sum",
    },
    "ledger_renta_expense_aggregation": {
        "target_casilla_id": _M130_INGRESOS_CASILLA,
        "fact": "deductible_amount_sum",
    },
    "ledger_renta_income_aggregation": {
        "target_casilla_id": _M130_INGRESOS_CASILLA,
        "fact": "gross_income_sum",
    },
    "profile": {"profile_key": "tax.id"},
    "related_party_operation": {"fact": "row_field", "row_field": "amount"},
    "foreign_asset": {"fact": "row_field", "row_field": "valuation_amount"},
    "atribucion_member": {"fact": "row_field", "row_field": "base_imponible_assigned"},
    "refund_operation": {"fact": "row_field", "row_field": "refund_amount"},
}


def _binding(*, source: str, op: BindingAggregationOp | None) -> DataBindingDefinition:
    """Build a ``DataBindingDefinition`` for ``source`` with an optional typed op.

    Constructed through ``model_validate`` (the same boundary the registry
    loader uses) so the parametrised ``source`` string is validated against the
    canonical ``source`` enum AND the selector is validated against its source
    family's selector model (the F8 construction-time selector-shape gate). The
    selector is drawn from :data:`_WELL_SHAPED_SELECTORS` so each binding is
    well-formed at the schema level: these tests exercise the aggregation axis,
    not selector shape, so the minimal selector only has to clear the per-family
    selector model.
    """
    return DataBindingDefinition.model_validate(
        {
            "id": f"test-binding-aggregation-{source}",
            "source": source,
            "selector": _WELL_SHAPED_SELECTORS.get(source, {"target_casilla_id": _M130_INGRESOS_CASILLA}),
            "aggregation": None if op is None else BindingAggregation(op=op),
            "legal_refs": (_DUMMY_LEGAL_ID,),
            "source_refs": (_DUMMY_SOURCE_ID,),
        },
    )


# Every op member confirmed declared on a binding aggregation table in the
# registry authoring tree. The list is hand-written from the registry sweep,
# NOT derived from the enum under test.
_REGISTRY_DECLARED_OPS: tuple[str, ...] = (
    "sum",
    "rows",
    "copy",
    "count_distinct",
    "prior_pagos_fraccionados",
)


def test_binding_aggregation_op_member_set_matches_registry_declarations() -> None:
    """The enum's member values equal the complete registry-declared op set."""
    assert {member.value for member in BindingAggregationOp} == set(_REGISTRY_DECLARED_OPS)


@pytest.mark.parametrize("op_value", _REGISTRY_DECLARED_OPS)
def test_binding_aggregation_round_trips_through_strict_model(op_value: str) -> None:
    """A raw TOML ``{op = "<value>"}`` mapping hydrates to the typed member.

    Exercises the same ``model_validate`` boundary the registry loader uses:
    the plain string is coerced to its :class:`BindingAggregationOp` member,
    and a re-dump round-trips back to the canonical string value.
    """
    aggregation = BindingAggregation.model_validate({"op": op_value})

    assert isinstance(aggregation.op, BindingAggregationOp)
    assert aggregation.op == op_value
    assert aggregation.op.value == op_value
    assert aggregation.model_dump()["op"] == op_value
    # Constructed directly with the typed member round-trips identically.
    assert aggregation == BindingAggregation(op=BindingAggregationOp(op_value))


# The per-family default contract: detail-record families emit one row per
# observation (``rows``); every other source folds to a scalar (``sum``).
# Enumerated independently from the plan's declared mapping, not from the
# accessor under test.
_ROWS_DEFAULT_SOURCES: tuple[str, ...] = (
    "related_party_operation",
    "foreign_asset",
    "atribucion_member",
    "refund_operation",
)
_SUM_DEFAULT_SOURCES: tuple[str, ...] = (
    "previous_filing",
    "withholding",
    "payable_invoice",
    "collectible_invoice",
    "ledger_transaction",
    "ledger_oss_aggregation",
    "ledger_iva_aggregation",
    "ledger_renta_expense_aggregation",
    "ledger_renta_income_aggregation",
    "profile",
)


@pytest.mark.parametrize("source", _ROWS_DEFAULT_SOURCES)
def test_detail_record_family_defaults_to_rows(source: str) -> None:
    """A detail-record binding with no explicit op defaults to ``rows``."""
    assert default_binding_aggregation_op(source) is BindingAggregationOp.ROWS
    assert binding_aggregation_op(_binding(source=source, op=None)) is BindingAggregationOp.ROWS


@pytest.mark.parametrize("source", _SUM_DEFAULT_SOURCES)
def test_scalar_folding_family_defaults_to_sum(source: str) -> None:
    """A scalar-folding binding with no explicit op defaults to ``sum``."""
    assert default_binding_aggregation_op(source) is BindingAggregationOp.SUM
    assert binding_aggregation_op(_binding(source=source, op=None)) is BindingAggregationOp.SUM


@pytest.mark.parametrize("source", (*_ROWS_DEFAULT_SOURCES, *_SUM_DEFAULT_SOURCES))
def test_explicit_op_overrides_family_default(source: str) -> None:
    """An explicit typed op is returned verbatim regardless of the family default."""
    binding = _binding(source=source, op=BindingAggregationOp.COPY)
    assert binding_aggregation_op(binding) is BindingAggregationOp.COPY


def test_unknown_op_string_is_rejected_at_model_validation() -> None:
    """Anti-tautology: corrupting the op to an unknown string refuses at the boundary.

    If this ever passes, the typed aggregation boundary is broken and every
    round-trip assertion above is vacuous.
    """
    with pytest.raises(ValidationError):
        BindingAggregation.model_validate({"op": "average"})


def test_extra_aggregation_key_is_rejected_at_model_validation() -> None:
    """A stray extra key is refused under the strict ``extra='forbid'`` config."""
    with pytest.raises(ValidationError):
        BindingAggregation.model_validate({"op": "sum", "scale": 2})


def test_missing_op_is_rejected_at_model_validation() -> None:
    """An aggregation mapping with no ``op`` is refused (``op`` is required)."""
    with pytest.raises(ValidationError):
        BindingAggregation.model_validate({})


def test_binding_aggregation_is_frozen() -> None:
    """The typed model is immutable, matching the registry strict-frozen config."""
    aggregation = BindingAggregation(op=BindingAggregationOp.SUM)
    with pytest.raises(ValidationError):
        aggregation.op = BindingAggregationOp.ROWS  # type: ignore[misc]
