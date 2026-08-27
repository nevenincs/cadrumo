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

from .....application.aggregation import DEFERRED_SOURCE_KINDS
from .....core import CasillaId, validated_casilla_id
from .....core.aggregation import BindingAggregation, BindingAggregationOp, BindingSourceKind
from .....core.resources import bundled_path
from .._validate import RegistryValidator
from ..bindings import (
    _BINDING_SELECTOR_REGISTRY,
    _BINDING_VALIDATOR_REGISTRY,
    validate_binding_selector_shape,
)
from ..errors import RegistryValidationError
from ..schema import DataBindingDefinition, ModeloDefinition, ModeloRevision, RegistryCatalogues
from ._registry_schema_support import _committed_modelo, _committed_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_M130_INGRESOS_CASILLA: CasillaId = validated_casilla_id("01", surface="_M130_INGRESOS_CASILLA")
_M130_GASTOS_CASILLA: CasillaId = validated_casilla_id("02", surface="_M130_GASTOS_CASILLA")
_M130_PAGOS_FRACCIONADOS_CASILLA: CasillaId = validated_casilla_id(
    "05",
    surface="_M130_PAGOS_FRACCIONADOS_CASILLA",
)
_M130_RESULTADO_PREVIO_CASILLA: CasillaId = validated_casilla_id("07", surface="_M130_RESULTADO_PREVIO_CASILLA")


def _deferred_validator_exemptions(
    *,
    deferred: frozenset[BindingSourceKind],
    declared: frozenset[BindingSourceKind],
    implemented: frozenset[BindingSourceKind],
) -> frozenset[BindingSourceKind]:
    """Return only sources that are deferred, undeclared, and validatorless."""
    return deferred - declared - implemented


def _committed_modelo_130() -> tuple[ModeloDefinition, RegistryCatalogues]:
    """Load the committed Modelo 130 modelo plus catalogues for the build path."""
    return _committed_modelo("130")


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
    base: DataBindingDefinition | None = None,
) -> DataBindingDefinition:
    """Build a binding of ``source`` reusing the first M130 binding's id and grounding."""
    if base is None:
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
        {"modelo": "130", "target_casilla_id": _M130_INGRESOS_CASILLA, "fact": "cash_received_sum"},
        BindingAggregationOp.SUM,
        # An unknown fact value trips the typed selector Literal at build time
        # (a shape violation is also a build-time rejection, not resolve-only).
        {"modelo": "130", "target_casilla_id": _M130_INGRESOS_CASILLA, "fact": "not_a_real_fact"},
        BindingAggregationOp.SUM,
    ),
    (
        "ledger_renta_gastos_pago_fraccionado_aggregation",
        "ledger_renta_gastos_pago_fraccionado_aggregation",
        {"modelo": "130", "target_casilla_id": _M130_GASTOS_CASILLA, "fact": "deductible_amount_sum"},
        BindingAggregationOp.SUM,
        # An unknown fact value trips the typed selector Literal at build time.
        {"modelo": "130", "target_casilla_id": _M130_GASTOS_CASILLA, "fact": "not_a_real_fact"},
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
        "donativo_donor",
        "donativo_donor",
        {"fact": "row_field", "row_field": "amount_donated"},
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
        {"source_modelo": "130", "source_casilla_id": _M130_PAGOS_FRACCIONADOS_CASILLA},
        BindingAggregationOp.COPY,
        # copy requires exactly one source casilla; two violates the invariant.
        {
            "source_modelo": "130",
            "period": "0A",
            "source_casilla_ids": (_M130_PAGOS_FRACCIONADOS_CASILLA, _M130_RESULTADO_PREVIO_CASILLA),
        },
        BindingAggregationOp.COPY,
    ),
    (
        "m303_regimen_simplificado_annual_summary",
        "m303_regimen_simplificado_annual_summary",
        {
            "source_modelo": "303",
            "source_period": "4T",
            "source_casilla_ids": ("51", "53", "52", "54", "55", "56", "57", "58"),
            "summary_casilla_id": "iva.anual.regimen-simplificado.cuota-resultante-no-agricola",
        },
        BindingAggregationOp.COPY,
        {
            "source_modelo": "303",
            "source_period": "3T",
            "source_casilla_ids": ("51", "53", "52", "54", "55", "56", "57", "58"),
            "summary_casilla_id": "iva.anual.regimen-simplificado.cuota-resultante-no-agricola",
        },
        BindingAggregationOp.COPY,
    ),
    (
        "inventory",
        "inventory",
        {
            "modelo": "100",
            "filing_year": 2025,
            "projection_grain": "taxpayer_year_activity",
            "fact": "row_field",
            "record": "inventory_activity",
            "grouping": "per_inventory_activity",
            "row_field": "closing_minus_opening_positive",
            "target_casilla_id": "0177",
        },
        BindingAggregationOp.ROWS,
        # The operation-to-destination identity is closed: an inventory
        # increase cannot be projected into the decrease casilla.
        {
            "modelo": "100",
            "filing_year": 2025,
            "projection_grain": "taxpayer_year_activity",
            "fact": "row_field",
            "record": "inventory_activity",
            "grouping": "per_inventory_activity",
            "row_field": "closing_minus_opening_positive",
            "target_casilla_id": "0182",
        },
        BindingAggregationOp.ROWS,
    ),
)

_FAMILY_IDS = tuple(case[0] for case in _FAMILY_CASES)


@pytest.mark.parametrize("case", _FAMILY_CASES, ids=_FAMILY_IDS)
def test_binding_family_build_gate_contract(
    case: tuple[str, str, dict[str, object], BindingAggregationOp, dict[str, object], BindingAggregationOp],
) -> None:
    """Each family accepts a good binding, constructs a bad one, and rejects it at build."""
    _label, source, well_formed_selector, well_formed_op, malformed_selector, malformed_op = case
    modelo, catalogues = _committed_modelo_130()
    base = modelo.revisions["2019-y-siguientes"].bindings[0]

    well_formed = _build_binding(source=source, selector=well_formed_selector, op=well_formed_op, base=base)
    assert validate_binding_selector_shape(well_formed) == [], f"well-formed {source} binding must pass the build gate"

    malformed = _build_binding(source=source, selector=malformed_selector, op=malformed_op, base=base)
    assert isinstance(malformed, DataBindingDefinition)
    assert str(malformed.source) == source
    mutated = _inject_binding(modelo, malformed)

    with pytest.raises(RegistryValidationError) as excinfo:
        RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(mutated)

    message = str(excinfo.value)
    assert malformed.id in message


def test_renta_gasto_binding_rejects_legacy_target_casilla_key() -> None:
    binding = _build_binding(
        source="ledger_renta_gastos_pago_fraccionado_aggregation",
        selector={"modelo": "130", "target_casilla": _M130_GASTOS_CASILLA, "fact": "deductible_amount_sum"},
        op=BindingAggregationOp.SUM,
    )

    diagnostics = validate_binding_selector_shape(binding)

    assert len(diagnostics) == 1
    assert "target_casilla_id" in diagnostics[0]
    assert "target_casilla" in diagnostics[0]


def test_dispatch_table_covers_every_validated_family() -> None:
    """Every family case names a source the dispatch table validates (no silent gap)."""
    assert all(isinstance(key, BindingSourceKind) for key in _BINDING_VALIDATOR_REGISTRY)
    covered = {str(key) for key in _BINDING_VALIDATOR_REGISTRY}
    for case in _FAMILY_CASES:
        source = case[1]
        assert source in covered, f"family case {source!r} is not in the validator dispatch table"


#: Binding source kinds resolved BEFORE the registry binding mesh (a pre-mesh
#: gate / source-mesh decision), so they never appear as a
#: ``DataBindingDefinition.source`` and carry no per-family selector or
#: validator. Documented as mesh-only in ``core.aggregation.BindingSourceKind``
#: (the borrador prefill decision and the M303 IVA-wallet compensación decision).
_DOCUMENTED_MESH_ONLY_SOURCE_KINDS = frozenset(
    {
        BindingSourceKind.BORRADOR,
        BindingSourceKind.IVA_WALLET_DECISION,
    },
)


def test_every_binding_source_kind_is_validator_dispatched_or_documented_mesh_only() -> None:
    """No BindingSourceKind ships unvalidated: it is dispatch-validated or documented mesh-only.

    A new binding source kind must either register a per-family validator in
    ``_BINDING_VALIDATOR_REGISTRY`` (and, by the selector/validator parity
    asserted below, a strict selector model) or be enrolled in the pinned
    mesh-only set. A member in NEITHER class fails here loudly, closing the gap
    where a new registry-declarable source could compile and silently skip the
    build-time binding validation the single-contract discipline requires.
    """
    validated = frozenset(_BINDING_VALIDATOR_REGISTRY)

    # A legal binding source (one carrying a strict selector model) has EXACTLY
    # one dispatch validator, and every dispatch validator has a selector model:
    # no legal source ships unvalidated and no validator dangles without a shape.
    assert validated == frozenset(_BINDING_SELECTOR_REGISTRY), (
        "validator dispatch table and selector-model table have drifted: "
        f"validator-only={sorted(str(s) for s in validated - frozenset(_BINDING_SELECTOR_REGISTRY))}, "
        f"selector-only={sorted(str(s) for s in frozenset(_BINDING_SELECTOR_REGISTRY) - validated)}"
    )

    # The two classes are disjoint: a source is validator-dispatched XOR mesh-only.
    assert validated.isdisjoint(_DOCUMENTED_MESH_ONLY_SOURCE_KINDS), (
        "a documented mesh-only source also carries a dispatch validator: "
        f"{sorted(str(s) for s in validated & _DOCUMENTED_MESH_ONLY_SOURCE_KINDS)}"
    )

    # A deferred member without a validator is the only further legal class.
    # The exemption is derived from production disposition and disappears as
    # soon as the source gains a validator (or leaves deferral on enrollment).
    modelos, _ = _committed_registry_tree()
    declared = frozenset(
        binding.source for modelo in modelos for revision in modelo.revisions.values() for binding in revision.bindings
    )
    deferred_without_validator = _deferred_validator_exemptions(
        deferred=DEFERRED_SOURCE_KINDS,
        declared=declared,
        implemented=validated,
    )
    unclassified = (
        frozenset(BindingSourceKind) - validated - _DOCUMENTED_MESH_ONLY_SOURCE_KINDS - deferred_without_validator
    )
    assert not unclassified


@pytest.mark.parametrize("ratchet", ["binding", "validator", "deferral"])
def test_inventory_validator_exemption_disappears_on_each_enrollment_ratchet(ratchet: str) -> None:
    """Any declaration, validator, or end of deferral removes the exemption."""
    inventory = BindingSourceKind.INVENTORY
    deferred = frozenset({inventory})
    declared: frozenset[BindingSourceKind] = frozenset[BindingSourceKind]()
    implemented: frozenset[BindingSourceKind] = frozenset[BindingSourceKind]()
    assert inventory in _deferred_validator_exemptions(
        deferred=deferred,
        declared=declared,
        implemented=implemented,
    )
    if ratchet == "binding":
        declared = frozenset({inventory})
    elif ratchet == "validator":
        implemented = frozenset({inventory})
    else:
        deferred = frozenset()
    assert inventory not in _deferred_validator_exemptions(
        deferred=deferred,
        declared=declared,
        implemented=implemented,
    )


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
