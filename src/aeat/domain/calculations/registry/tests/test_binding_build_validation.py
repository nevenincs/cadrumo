"""Build-time rejection tests for the single binding validator contract.

The binding-interface hardening collapsed the three
incompatible binding-validation conventions onto one per-family
``validate(binding) -> list[str]`` accumulating validator, registered in the
single ``_BINDING_VALIDATOR_REGISTRY`` dispatch table and run by the
registry-build section validator for EVERY family.

This file proves the build gate is live for every source family: a malformed
binding (a bad op/fact pairing or a missing required selector field) is REJECTED
at registry-build (``RegistryValidator.validate_modelo`` — snapshot construction
validation), not only when a taxpayer calculation invokes the resolver. Before this
hardening, the four detail-record families and ``previous_filing`` enforced their
op/fact invariants ONLY at resolve time, so a malformed binding of those families
shipped clean through build and failed only on a calculation. This consolidation
made the build gate uniform across every family.

Anti-tautology proofs (the gate is not trivially rejecting everything):

  * a WELL-FORMED binding of each family passes the dispatch validator
    (``validate_binding_selector_shape`` returns ``[]``); and
  * the malformed binding is a CONSTRUCTIBLE
    :class:`DataBindingDefinition` — pydantic accepts the model, so the
    rejection is the build GATE's lifted op/fact invariant, not a schema-level
    refusal that would fire regardless of the build path.
"""

from __future__ import annotations

import pytest

from .....core.aggregation import BindingAggregation, BindingAggregationOp
from .....core.resources import bundled_path
from .. import RegistryCatalogues, RegistryValidator, load_registry_tree
from .._bindings import _BINDING_VALIDATOR_REGISTRY, validate_binding_selector_shape
from .._errors import RegistryValidationError
from .._schema import DataBindingDefinition, ModeloDefinition, ModeloRevision

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _committed_modelo_130() -> tuple[ModeloDefinition, RegistryCatalogues]:
    """Load the committed Modelo 130 modelo plus catalogues for the build path."""
    modelos, catalogues = load_registry_tree(bundled_path("registry", "aeat"))
    return next(modelo for modelo in modelos if modelo.id == "130"), catalogues


def _inject_binding(modelo: ModeloDefinition, replacement: DataBindingDefinition) -> ModeloDefinition:
    """Replace the first M130 binding with ``replacement`` and return the mutated modelo.

    Reusing an existing binding's id, legal_refs, and source_refs keeps the
    surrounding registry-build invariants (legal-authority coverage, evidence
    tiers) satisfied so the only thing the build can reject is the lifted
    binding op/fact invariant.
    """
    revision = modelo.revisions["2019-y-siguientes"]
    bindings = tuple(replacement if item.id == revision.bindings[0].id else item for item in revision.bindings)
    mutated = revision.model_copy(update={"bindings": bindings})
    return modelo.model_copy(update={"revisions": {**modelo.revisions, mutated.id: mutated}})


def _build_binding(
    *,
    source: str,
    selector: dict[str, object],
    op: BindingAggregationOp,
) -> DataBindingDefinition:
    """Build a binding of ``source`` reusing the first M130 binding's id and grounding."""
    modelo, _catalogues = _committed_modelo_130()
    base = modelo.revisions["2019-y-siguientes"].bindings[0]
    return base.model_copy(
        update={
            "source": source,
            "selector": selector,
            "aggregation": BindingAggregation(op=op),
        },
    )


# Per-family build-validation cases. Each case carries a well-formed selector
# (must pass the dispatch gate) and a malformed selector with a bad op/fact
# pairing or a missing required key (must be rejected at registry build).
_FAMILY_CASES: tuple[
    tuple[str, str, dict[str, object], BindingAggregationOp, dict[str, object], BindingAggregationOp], ...
] = (
    (
        "invoice (collectible)",
        "collectible_invoice",
        {"fact": "base_sum"},
        BindingAggregationOp.SUM,
        # operator_count must pair with count_distinct, not sum.
        {"fact": "operator_count"},
        BindingAggregationOp.SUM,
    ),
    (
        "counterpart (ledger_transaction)",
        "ledger_transaction",
        {"fact": "base_sum"},
        BindingAggregationOp.SUM,
        {"fact": "operator_count"},
        BindingAggregationOp.SUM,
    ),
    (
        "ledger_oss_aggregation",
        "ledger_oss_aggregation",
        {
            "regime": "external_scheme",
            "destination_member_state": "de",
            "rate_kind": "general",
            "invoice_direction": "issued",
            "transaction_kinds": ("external_scheme_services",),
            "fact": "iva_amount_sum",
        },
        BindingAggregationOp.SUM,
        # A complete OSS selector with the wrong op: ledger OSS supports only the
        # sum op, so the copy op trips the lifted aggregation-op invariant (not
        # the selector-shape gate).
        {
            "regime": "external_scheme",
            "destination_member_state": "de",
            "rate_kind": "general",
            "invoice_direction": "issued",
            "transaction_kinds": ("external_scheme_services",),
            "fact": "iva_amount_sum",
        },
        BindingAggregationOp.COPY,
    ),
    (
        "ledger_renta_income_aggregation",
        "ledger_renta_income_aggregation",
        {"modelo": "130", "target_casilla_id": "01", "fact": "gross_income_sum"},
        BindingAggregationOp.SUM,
        # An unknown fact value trips the typed selector Literal at build time
        # (a shape violation is also a build-time rejection, not resolve-only).
        {"modelo": "130", "target_casilla_id": "01", "fact": "not_a_real_fact"},
        BindingAggregationOp.SUM,
    ),
    (
        "ledger_renta_gasto_aggregation",
        "ledger_renta_gasto_aggregation",
        {"modelo": "130", "target_casilla_id": "02", "fact": "deductible_amount_sum"},
        BindingAggregationOp.SUM,
        # An unknown fact value trips the typed selector Literal at build time.
        {"modelo": "130", "target_casilla_id": "02", "fact": "not_a_real_fact"},
        BindingAggregationOp.SUM,
    ),
    (
        "related_party_operation",
        "related_party_operation",
        {"fact": "row_field", "row_field": "amount"},
        BindingAggregationOp.ROWS,
        # row_field fact without a row_field selector key.
        {"fact": "row_field"},
        BindingAggregationOp.ROWS,
    ),
    (
        "foreign_asset",
        "foreign_asset",
        {"fact": "row_field", "row_field": "valuation_amount"},
        BindingAggregationOp.ROWS,
        {"fact": "row_field"},
        BindingAggregationOp.ROWS,
    ),
    (
        "atribucion_member",
        "atribucion_member",
        {"fact": "row_field", "row_field": "base_imponible_assigned"},
        BindingAggregationOp.ROWS,
        {"fact": "row_field"},
        BindingAggregationOp.ROWS,
    ),
    (
        "refund_operation",
        "refund_operation",
        {"fact": "row_field", "row_field": "refund_amount"},
        BindingAggregationOp.ROWS,
        {"fact": "row_field"},
        BindingAggregationOp.ROWS,
    ),
    (
        "withholding",
        "withholding",
        {"fact": "retencion_sum", "claves": ("A",)},
        BindingAggregationOp.SUM,
        # perceptor_count must pair with count_distinct, not sum.
        {"fact": "perceptor_count", "claves": ("A",)},
        BindingAggregationOp.SUM,
    ),
    (
        "previous_filing",
        "previous_filing",
        {"source_modelo": "130", "source_casilla_id": "05"},
        BindingAggregationOp.COPY,
        # copy requires exactly one source casilla; two violates the invariant.
        {"source_modelo": "130", "period": "0A", "source_casilla_ids": ("05", "07")},
        BindingAggregationOp.COPY,
    ),
)

_FAMILY_IDS = tuple(case[0] for case in _FAMILY_CASES)


@pytest.mark.parametrize("case", _FAMILY_CASES, ids=_FAMILY_IDS)
def test_well_formed_binding_of_each_family_passes_the_build_gate(
    case: tuple[str, str, dict[str, object], BindingAggregationOp, dict[str, object], BindingAggregationOp],
) -> None:
    """Anti-tautology: a well-formed binding of each family passes the dispatch gate."""
    _label, source, well_formed_selector, well_formed_op, _bad_selector, _bad_op = case
    binding = _build_binding(source=source, selector=well_formed_selector, op=well_formed_op)
    assert validate_binding_selector_shape(binding) == [], f"well-formed {source} binding must pass the build gate"


@pytest.mark.parametrize("case", _FAMILY_CASES, ids=_FAMILY_IDS)
def test_malformed_binding_of_each_family_is_constructible(
    case: tuple[str, str, dict[str, object], BindingAggregationOp, dict[str, object], BindingAggregationOp],
) -> None:
    """Anti-tautology: the malformed binding is a constructible model.

    pydantic accepts the malformed binding as a :class:`DataBindingDefinition`,
    so the build rejection below is the GATE's lifted op/fact invariant — not a
    schema-construction refusal that would fire regardless of the build path.
    """
    _label, source, _good_selector, _good_op, malformed_selector, malformed_op = case
    binding = _build_binding(source=source, selector=malformed_selector, op=malformed_op)
    assert isinstance(binding, DataBindingDefinition)
    assert str(binding.source) == source


@pytest.mark.parametrize("case", _FAMILY_CASES, ids=_FAMILY_IDS)
def test_malformed_binding_of_each_family_rejected_at_registry_build(
    case: tuple[str, str, dict[str, object], BindingAggregationOp, dict[str, object], BindingAggregationOp],
) -> None:
    """A malformed binding of each family is rejected at registry build, not only resolve.

    The malformed binding is injected into the committed Modelo 130 modelo and
    run through ``RegistryValidator.validate_modelo`` — the snapshot-construction
    validation path. Every family (including the four detail-record families and
    ``previous_filing`` whose op/fact invariants previously ran only at resolve
    time) surfaces the lifted invariant as a build-time failure.
    """
    _label, source, _good_selector, _good_op, malformed_selector, malformed_op = case
    modelo, catalogues = _committed_modelo_130()
    malformed = _build_binding(source=source, selector=malformed_selector, op=malformed_op)
    mutated = _inject_binding(modelo, malformed)

    with pytest.raises(RegistryValidationError) as excinfo:
        RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(mutated)

    message = str(excinfo.value)
    assert malformed.id in message


def test_renta_gasto_binding_rejects_legacy_target_casilla_key() -> None:
    binding = _build_binding(
        source="ledger_renta_gasto_aggregation",
        selector={"modelo": "130", "target_casilla": "02", "fact": "deductible_amount_sum"},
        op=BindingAggregationOp.SUM,
    )

    diagnostics = validate_binding_selector_shape(binding)

    assert len(diagnostics) == 1
    assert "target_casilla_id" in diagnostics[0]
    assert "target_casilla" in diagnostics[0]


def test_dispatch_table_covers_every_validated_family() -> None:
    """Every family case names a source the dispatch table validates (no silent gap)."""
    covered = {str(key) for key in _BINDING_VALIDATOR_REGISTRY}
    for case in _FAMILY_CASES:
        source = case[1]
        assert source in covered, f"family case {source!r} is not in the validator dispatch table"


def test_isolated_revision_build_gate_runs_every_family() -> None:
    """A revision-level sanity check that the dispatch validator routes a member of each family.

    Builds a one-binding revision per family from the committed M130 binding and
    asserts the dispatch gate produces a failure for the malformed variant —
    exercising the single ``validate_binding_selector_shape`` path the build
    section validator runs for every binding.
    """
    for case in _FAMILY_CASES:
        _label, source, _good_selector, _good_op, malformed_selector, malformed_op = case
        malformed = _build_binding(source=source, selector=malformed_selector, op=malformed_op)
        failures = validate_binding_selector_shape(malformed)
        assert failures, f"malformed {source} binding must fail the dispatch gate"
        # Sanity: a one-binding revision carrying the malformed binding is still
        # a constructible ModeloRevision (the gate, not schema, rejects it).
        revision = _committed_modelo_130()[0].revisions["2019-y-siguientes"]
        one_binding = revision.model_copy(update={"bindings": (malformed,)})
        assert isinstance(one_binding, ModeloRevision)
