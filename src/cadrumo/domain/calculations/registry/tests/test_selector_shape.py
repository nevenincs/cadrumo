"""Strict tests for the binding selector-shape contract.

The :func:`validate_binding_selector_shape` helper pairs each
:attr:`DataBindingDefinition.source` value with a strict pydantic
model and asserts the binding's selector mapping validates against
the source's schema. As of F8 (the binding-vocabulary selector-typing
increment) the selector-shape half of that contract is also enforced
at MODEL CONSTRUCTION: ``DataBindingDefinition._validate_selector_shape``
dispatches on ``source`` through the same ``_BINDING_SELECTOR_REGISTRY``
(surfaced by :func:`selector_model_for_source`) and raises when the
selector mapping is misshapen — so a binding with a misshapen selector
can no longer be constructed at all. The op/fact cross-invariants (which
read the separate ``aggregation`` field) stay owned by
:func:`validate_binding_selector_shape` at snapshot build, so a binding
whose selector is well-shaped but whose op/fact pairing is wrong stays
constructible and is rejected by the build gate.

This file pins:

  * the registry of map-backed typed selectors is non-empty and
    registers every typed source key currently declared in
    ``_BINDING_SELECTOR_REGISTRY``;
  * a well-shaped selector for each typed source constructs and passes
    the gate;
  * a misshapen selector for a typed source is REFUSED AT CONSTRUCTION
    (the F8 tightening), with the diagnostic naming the binding id and
    the violated typed model;
  * registry-declared binding sources are fail-closed: every live source must
    have a selector model, and mesh-only source kinds are refused as
    ``DataBindingDefinition.source`` values.
"""

from __future__ import annotations

from collections.abc import Mapping

import pytest
from pydantic import ValidationError

from .....application.aggregation import DEFERRED_SOURCE_KINDS
from .....core import CasillaId, validated_casilla_id
from .....core.aggregation import BindingAggregation, BindingAggregationOp, BindingSourceKind
from .._binding_selector_utils import selector_as_dict
from .._bindings import (
    _BINDING_SELECTOR_REGISTRY,
    binding_source_casilla_ids,
    binding_source_modelo,
    selector_model_for_source,
    validate_binding_selector_shape,
)
from .._schema import DataBindingDefinition
from ._registry_schema_support import _committed_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_M111_RETENCIONES_CASILLA: CasillaId = validated_casilla_id("28", surface="_M111_RETENCIONES_CASILLA")
_M303_CARRY_CASILLA: CasillaId = validated_casilla_id("66", surface="_M303_CARRY_CASILLA")
_M100_MANUAL_BOOLEAN_CASILLA: CasillaId = validated_casilla_id("0168", surface="_M100_MANUAL_BOOLEAN_CASILLA")
_M130_SALDO_NEGATIVO_CASILLA: CasillaId = validated_casilla_id(
    "saldo-negativo-fin-periodo",
    surface="_M130_SALDO_NEGATIVO_CASILLA",
)
_M303_COMPENSACION_DISPONIBLE_CASILLA: CasillaId = validated_casilla_id(
    "iva.compensacion-disponible-fin-periodo",
    surface="_M303_COMPENSACION_DISPONIBLE_CASILLA",
)
_M303_CUOTA_DEVENGADA_TOTAL_CASILLA: CasillaId = validated_casilla_id(
    "iva.cuota-devengada-total",
    surface="_M303_CUOTA_DEVENGADA_TOTAL_CASILLA",
)
_M303_CUOTA_DEDUCIBLE_TOTAL_CASILLA: CasillaId = validated_casilla_id(
    "iva.cuota-deducible-total",
    surface="_M303_CUOTA_DEDUCIBLE_TOTAL_CASILLA",
)


def _deferred_selector_exemptions(
    *,
    deferred: set[BindingSourceKind],
    declared: set[BindingSourceKind],
    implemented: set[BindingSourceKind],
) -> set[BindingSourceKind]:
    """Return only sources that are deferred, undeclared, and selectorless."""
    return deferred - declared - implemented


_M303_PRORRATA_VOLUMEN_CON_DERECHO_CASILLA: CasillaId = validated_casilla_id(
    "iva.prorrata-volumen-con-derecho",
    surface="_M303_PRORRATA_VOLUMEN_CON_DERECHO_CASILLA",
)
_M303_PRORRATA_VOLUMEN_TOTAL_CASILLA: CasillaId = validated_casilla_id(
    "iva.prorrata-volumen-total",
    surface="_M303_PRORRATA_VOLUMEN_TOTAL_CASILLA",
)
_M303_PRORRATA_PORCENTAJE_CASILLA: CasillaId = validated_casilla_id(
    "iva.prorrata-porcentaje",
    surface="_M303_PRORRATA_PORCENTAJE_CASILLA",
)
_PRORRATA_REGULARIZACION_SOURCE_IDS: tuple[CasillaId, ...] = (
    _M303_CUOTA_DEDUCIBLE_TOTAL_CASILLA,
    _M303_PRORRATA_VOLUMEN_CON_DERECHO_CASILLA,
    _M303_PRORRATA_VOLUMEN_TOTAL_CASILLA,
    _M303_PRORRATA_PORCENTAJE_CASILLA,
)


def _binding(
    *,
    source: str | BindingSourceKind,
    selector: Mapping[str, object],
    binding_id: str = "test-binding",
    aggregation_op: BindingAggregationOp | None = None,
) -> DataBindingDefinition:
    """Build a minimal DataBindingDefinition for the gate to validate."""

    payload: dict[str, object] = {
        "id": binding_id,
        "source": source,
        "selector": selector,
        "legal_refs": ("ley-35-2006:art-99",),
        "source_refs": ("aeat-test",),
    }
    if aggregation_op is not None:
        payload["aggregation"] = {"op": aggregation_op}
    return DataBindingDefinition.model_validate(payload)


def _assert_selector_refused_at_construction(
    *,
    source: str,
    selector: Mapping[str, object],
    binding_id: str,
    expected_substrings: tuple[str, ...],
) -> None:
    """Assert a misshapen selector is refused when the binding is constructed.

    The F8 model-construction selector gate raises a pydantic
    :class:`ValidationError` wrapping the :class:`RegistryValidationError`
    diagnostic. The wrapped message must carry every ``expected_substring`` the
    snapshot-build gate's diagnostic carried, so the construction-time refusal is
    as informative as the former build-time one.
    """
    with pytest.raises(ValidationError) as excinfo:
        _binding(source=source, selector=selector, binding_id=binding_id)
    message = str(excinfo.value)
    for substring in expected_substrings:
        assert substring in message, f"expected {substring!r} in construction refusal:\n{message}"


def test_binding_selector_registry_covers_typed_sources() -> None:
    """Every registry-declared source kind has exactly one typed selector.

    Derived from :class:`BindingSourceKind` rather than restated as a member
    list: a hand-written expected set has to be edited by hand every time a kind
    is added, and when that edit is missed the gate fails for a bookkeeping
    reason while reporting a coverage one. This gate went red exactly that way
    when ``m303_regimen_simplificado_annual_summary`` was registered with a
    selector and a validator but never added here.

    Canonical members that are mesh-only or deferred without a selector are
    outside this gate. The production-derived deferral exemption disappears as
    soon as the selector is added or the source leaves deferral.
    """
    # BORRADOR resolves a whole pre-filled declaration rather than a selected
    # slice, and IVA_WALLET_DECISION is settled by the wallet decision rather
    # than by a selector; neither carries a selector map to validate.
    selectorless = {BindingSourceKind.BORRADOR, BindingSourceKind.IVA_WALLET_DECISION}
    modelos, _ = _committed_registry_tree()
    declared = {
        binding.source for modelo in modelos for revision in modelo.revisions.values() for binding in revision.bindings
    }
    deferred_without_selector = _deferred_selector_exemptions(
        deferred=set(DEFERRED_SOURCE_KINDS),
        declared=declared,
        implemented=set(_BINDING_SELECTOR_REGISTRY),
    )
    expected = set(BindingSourceKind) - selectorless - deferred_without_selector

    assert set(_BINDING_SELECTOR_REGISTRY) == expected
    assert all(isinstance(source, BindingSourceKind) for source in _BINDING_SELECTOR_REGISTRY)


@pytest.mark.parametrize("ratchet", ["binding", "selector", "deferral"])
def test_inventory_selector_exemption_disappears_on_each_enrollment_ratchet(ratchet: str) -> None:
    """Any declaration, selector, or end of deferral removes the exemption."""
    inventory = BindingSourceKind.INVENTORY
    deferred = {inventory}
    declared: set[BindingSourceKind] = set()
    implemented: set[BindingSourceKind] = set()
    assert inventory in _deferred_selector_exemptions(
        deferred=deferred,
        declared=declared,
        implemented=implemented,
    )
    if ratchet == "binding":
        declared.add(inventory)
    elif ratchet == "selector":
        implemented.add(inventory)
    else:
        deferred.remove(inventory)
    assert inventory not in _deferred_selector_exemptions(
        deferred=deferred,
        declared=declared,
        implemented=implemented,
    )


def test_construction_gate_dispatches_through_selector_model_for_source() -> None:
    """F8: the model construction gate dispatches via ``selector_model_for_source``.

    The accessor surfaces the same ``_BINDING_SELECTOR_REGISTRY`` table the model
    validator consumes, so the construction gate covers every registry-declared
    binding source.
    """
    for source, model in _BINDING_SELECTOR_REGISTRY.items():
        assert selector_model_for_source(source) is model


def test_constructed_binding_stores_hydrated_selector_model() -> None:
    """The canonical binding schema stores a source-family selector model."""

    binding = _binding(source=BindingSourceKind.PROFILE, selector={"profile_key": "taxpayer.nif"})
    selector_model = selector_model_for_source(BindingSourceKind.PROFILE)

    assert selector_model is not None
    assert isinstance(binding.selector, selector_model)
    assert selector_as_dict(binding) == {"profile_key": "taxpayer.nif"}
    assert binding.model_dump(mode="json")["selector"] == {"profile_key": "taxpayer.nif"}


def test_mesh_only_source_kinds_are_not_constructible_as_registry_bindings() -> None:
    """Mesh-only source kinds are first-class enum members, not registry bindings."""

    for source in (BindingSourceKind.BORRADOR, BindingSourceKind.IVA_WALLET_DECISION):
        with pytest.raises(ValidationError) as excinfo:
            _binding(
                source=source,
                selector={"profile_key": "tax.id"},
                binding_id=f"bad-mesh-only-{source.value}",
            )
        message = str(excinfo.value)
        assert source.value in message
        assert "not a registry binding source" in message


def test_previous_filing_selector_accepts_well_shaped_selector() -> None:
    """A previous_filing binding with a registry-valid selector passes the gate."""

    binding = _binding(
        source="previous_filing",
        selector={
            "source_modelo": "303",
            "filing_year_delta": -1,
            "period": "0A",
            "source_casilla_ids": (_M303_CARRY_CASILLA,),
        },
    )
    assert validate_binding_selector_shape(binding) == []


def test_prorrata_regularizacion_selector_accepts_canonical_m303_casilla_44_shape() -> None:
    """The prorrata regularisation source declares the regulated annual inputs."""

    binding = _binding(
        source="prorrata_regularizacion",
        selector={
            "source_modelo": "303",
            "source_casilla_ids": _PRORRATA_REGULARIZACION_SOURCE_IDS,
            "source_periods": ("1T", "2T", "3T", "4T"),
            "regularizacion_output": "modelo_303_casilla_44",
        },
        binding_id="prorrata-regularizacion-casilla-44",
    )

    assert validate_binding_selector_shape(binding) == []
    assert binding_source_modelo(binding) == "303"
    assert binding_source_casilla_ids(binding) == _PRORRATA_REGULARIZACION_SOURCE_IDS
    assert selector_as_dict(binding) == {
        "source_modelo": "303",
        "source_casilla_ids": _PRORRATA_REGULARIZACION_SOURCE_IDS,
        "source_periods": ("1T", "2T", "3T", "4T"),
        "regularizacion_output": "modelo_303_casilla_44",
    }


def test_prorrata_regularizacion_selector_accepts_canonical_m390_annual_shape() -> None:
    """Modelo 390's annual target consumes the same annual prorrata source."""

    binding = _binding(
        source="prorrata_regularizacion",
        selector={
            "source_modelo": "303",
            "source_casilla_ids": _PRORRATA_REGULARIZACION_SOURCE_IDS,
            "source_periods": ("1T", "2T", "3T", "4T"),
            "regularizacion_output": "modelo_390_regularizacion_anual",
        },
        binding_id="prorrata-regularizacion-modelo-390-anual",
    )

    assert validate_binding_selector_shape(binding) == []
    assert binding_source_modelo(binding) == "303"
    assert binding_source_casilla_ids(binding) == _PRORRATA_REGULARIZACION_SOURCE_IDS
    assert selector_as_dict(binding) == {
        "source_modelo": "303",
        "source_casilla_ids": _PRORRATA_REGULARIZACION_SOURCE_IDS,
        "source_periods": ("1T", "2T", "3T", "4T"),
        "regularizacion_output": "modelo_390_regularizacion_anual",
    }


def test_bienes_inversion_regularizacion_selector_accepts_canonical_m303_casilla_43_shape() -> None:
    """The capital-goods regularisation source declares the M303 casilla 43 target."""

    binding = _binding(
        source="bienes_inversion_regularizacion",
        selector={
            "source_modelo": "303",
            "regularizacion_output": "modelo_303_casilla_43",
        },
        binding_id="bienes-inversion-regularizacion-casilla-43",
    )

    assert validate_binding_selector_shape(binding) == []
    assert binding_source_modelo(binding) == "303"
    assert binding_source_casilla_ids(binding) == ()
    assert selector_as_dict(binding) == {
        "source_modelo": "303",
        "regularizacion_output": "modelo_303_casilla_43",
    }


def test_bienes_inversion_regularizacion_selector_accepts_canonical_m390_casilla_63_shape() -> None:
    """Modelo 390's annual capital-goods target consumes the same register source."""

    binding = _binding(
        source="bienes_inversion_regularizacion",
        selector={
            "source_modelo": "303",
            "regularizacion_output": "modelo_390_casilla_63",
        },
        binding_id="bienes-inversion-regularizacion-modelo-390-casilla-63",
    )

    assert validate_binding_selector_shape(binding) == []
    assert binding_source_modelo(binding) == "303"
    assert binding_source_casilla_ids(binding) == ()
    assert selector_as_dict(binding) == {
        "source_modelo": "303",
        "regularizacion_output": "modelo_390_casilla_63",
    }


def test_prorrata_regularizacion_selector_rejects_uncanonical_inputs() -> None:
    """The construction gate refuses partial or non-annual regularisation selectors."""

    cases = (
        (
            {
                "source_modelo": "303",
                "source_casilla_ids": (
                    _M303_PRORRATA_VOLUMEN_CON_DERECHO_CASILLA,
                    _M303_PRORRATA_VOLUMEN_TOTAL_CASILLA,
                    _M303_PRORRATA_PORCENTAJE_CASILLA,
                ),
                "source_periods": ("1T", "2T", "3T", "4T"),
                "regularizacion_output": "modelo_303_casilla_44",
            },
            "bad-prorrata-missing-deductible",
            ("prorrata_regularizacion", "canonical order"),
        ),
        (
            {
                "source_modelo": "303",
                "source_casilla_ids": _PRORRATA_REGULARIZACION_SOURCE_IDS,
                "source_periods": ("4T",),
                "regularizacion_output": "modelo_303_casilla_44",
            },
            "bad-prorrata-quarter-only",
            ("source_periods", "1T", "4T"),
        ),
        (
            {
                "source_modelo": "390",
                "source_casilla_ids": _PRORRATA_REGULARIZACION_SOURCE_IDS,
                "source_periods": ("1T", "2T", "3T", "4T"),
                "regularizacion_output": "modelo_303_casilla_44",
            },
            "bad-prorrata-source-modelo",
            ("source_modelo", "303"),
        ),
        (
            {
                "source_modelo": "303",
                "source_casilla_ids": _PRORRATA_REGULARIZACION_SOURCE_IDS,
                "source_periods": ("1T", "2T", "3T", "4T"),
                "regularizacion_output": "modelo_390-annual",
            },
            "bad-prorrata-output",
            ("regularizacion_output", "modelo_303_casilla_44", "modelo_390_regularizacion_anual"),
        ),
    )
    for selector, binding_id, expected_substrings in cases:
        _assert_selector_refused_at_construction(
            source="prorrata_regularizacion",
            selector=selector,
            binding_id=binding_id,
            expected_substrings=expected_substrings,
        )


def test_cross_filing_selectors_reject_legacy_and_invalid_source_keys() -> None:
    cases = (
        (
            "previous_filing",
            {
                "source_modelo": "303",
                "filing_year_delta": -1,
                "period": "0A",
                "source_casillas": ("66",),
            },
            "bad-legacy-source-casillas",
            ("source_casilla_ids", "source_casillas"),
        ),
        (
            "relation_prefill",
            {
                "source_modelo": "322",
                "source_periods": ("1T",),
                "source_casillas": (_M303_CUOTA_DEVENGADA_TOTAL_CASILLA,),
            },
            "bad-relation-prefill-legacy-source-casillas",
            ("source_casilla_ids", "source_casillas"),
        ),
        (
            "previous_filing",
            {"source_modelo": "111", "source_output": "28"},
            "bad-legacy-source-output",
            ("source_casilla_id", "source_output"),
        ),
        (
            "relation_prefill",
            {"source_modelo": "303", "source_output": "iva.cuota-devengada-total"},
            "bad-relation-prefill-source-output",
            ("source_casilla_id", "source_output"),
        ),
        (
            "previous_filing",
            {
                "source_modelo": "modelo-303",
                "source_casilla_id": _M303_CUOTA_DEVENGADA_TOTAL_CASILLA,
            },
            "bad-previous_filing-source-modelo",
            ("source_modelo", r"^\d{3}$"),
        ),
        (
            "relation_prefill",
            {
                "source_modelo": "modelo-303",
                "source_casilla_id": _M303_CUOTA_DEVENGADA_TOTAL_CASILLA,
            },
            "bad-relation_prefill-source-modelo",
            ("source_modelo", r"^\d{3}$"),
        ),
    )
    for source, selector, binding_id, expected_substrings in cases:
        _assert_selector_refused_at_construction(
            source=source,
            selector=selector,
            binding_id=binding_id,
            expected_substrings=expected_substrings,
        )


def test_previous_filing_selector_accepts_singular_source_casilla_id_shapes() -> None:
    """The direct-value-copy shape (singular source_casilla_id) passes.

    Real registry bindings (e.g. M100 retenciones relations against
    M111/M115/M123) declare a ``source_casilla_id`` casilla rather than
    a ``source_casilla_ids`` tuple. The typed selector must accept this
    second shape, validated as the exclusive alternative to the
    plural form. (The selector.relation shorthand was retired under
    selector contract; relation->binding linkage is via
    RelationDefinition.target_binding.)
    """

    selectors = (
        {
            "source_modelo": "111",
            "source_casilla_id": _M111_RETENCIONES_CASILLA,
        },
        {
            "source_modelo": "303",
            "source_casilla_id": _M303_COMPENSACION_DISPONIBLE_CASILLA,
            "source_period_offset_from_target": -1,
        },
    )
    for selector in selectors:
        binding = _binding(source="previous_filing", selector=selector)
        assert validate_binding_selector_shape(binding) == []


def test_previous_filing_selector_rejects_both_source_shapes() -> None:
    """Declaring source_casilla_id AND source_casilla_ids in the same selector fails.

    The two shapes are exclusive: one for direct copy, one for
    aggregation. A binding that declares both is malformed; the
    typed model surfaces this as a validation failure.
    """

    _assert_selector_refused_at_construction(
        source="previous_filing",
        selector={
            "source_modelo": "111",
            "source_casilla_id": _M111_RETENCIONES_CASILLA,
            "source_casilla_ids": (_M111_RETENCIONES_CASILLA,),
            "relation": "retenciones-trabajo-actividades-premios",
        },
        binding_id="bad-double-source",
        expected_substrings=("bad-double-source",),
    )


def test_previous_filing_selector_rejects_unknown_key() -> None:
    """An extra key on a previous_filing selector surfaces a typed diagnostic.

    The typed model declares ``extra='forbid'``; the gate must
    propagate the violation as a diagnostic naming the binding id
    and the typed model.
    """

    _assert_selector_refused_at_construction(
        source="previous_filing",
        selector={
            "source_modelo": "303",
            "filing_year_delta": -1,
            "source_casilla_ids": (_M303_CARRY_CASILLA,),
            "spurious_key": "leaked",
        },
        binding_id="bad-previous-filing",
        expected_substrings=("bad-previous-filing", "PreviousModeloSelector"),
    )


def test_withholding_selector_accepts_well_shaped_selector() -> None:
    """A withholding binding's fact + claves selector passes the gate."""

    binding = _binding(
        source="withholding",
        selector={
            "fact": "retencion_sum",
            "claves": ("A", "G"),
        },
    )
    assert validate_binding_selector_shape(binding) == []


def test_withholding_selector_rejects_unknown_fact() -> None:
    """An unknown fact value fails the typed-Literal contract.

    Audit selector-drift F2: the fact field was previously a bare
    ``str`` so bogus values passed the snapshot-build gate and were
    only rejected at handler-call time. With the Literal in place,
    the gate catches them now.
    """

    _assert_selector_refused_at_construction(
        source="withholding",
        selector={
            "fact": "bogus_fact_value",
            "claves": ("A",),
        },
        binding_id="bad-withholding-fact",
        expected_substrings=("bad-withholding-fact", "_WithholdingSelector", "bogus_fact_value"),
    )


def test_retenciones_aggregation_selector_accepts_well_shaped_selector() -> None:
    """The retenciones aggregation source validates declared scalar facts."""

    for fact in ("perceptor_count_distinct", "taxable_base_sum", "retencion_amount_sum"):
        binding = _binding(
            source="retenciones_aggregation",
            selector={
                "target_casilla_id": _M111_RETENCIONES_CASILLA,
                "fact": fact,
            },
        )
        assert validate_binding_selector_shape(binding) == []


def test_retenciones_aggregation_selector_rejects_unknown_fact() -> None:
    _assert_selector_refused_at_construction(
        source="retenciones_aggregation",
        selector={
            "target_casilla_id": _M111_RETENCIONES_CASILLA,
            "fact": "percepcion_count",
        },
        binding_id="bad-retenciones-fact",
        expected_substrings=("bad-retenciones-fact", "_RetencionesAggregationSelector", "percepcion_count"),
    )


def test_inventory_selector_enrollment_hydrates_the_family_model() -> None:
    """Inventory construction uses the canonical typed family selector."""

    binding = _binding(
        source=BindingSourceKind.INVENTORY,
        selector={
            "modelo": "100",
            "filing_year": 2025,
            "projection_grain": "taxpayer_year_activity",
            "fact": "row_field",
            "record": "inventory_activity",
            "grouping": "per_inventory_activity",
            "row_field": "opening_minus_closing_positive",
            "target_casilla_id": "0182",
        },
        aggregation_op=BindingAggregationOp.ROWS,
    )
    selector_model = selector_model_for_source(BindingSourceKind.INVENTORY)

    assert selector_model is not None
    assert isinstance(binding.selector, selector_model)
    assert validate_binding_selector_shape(binding) == []


def test_inventory_selector_enrollment_refuses_destination_drift() -> None:
    """Construction rejects a variation operation paired with the rival casilla."""

    _assert_selector_refused_at_construction(
        source=BindingSourceKind.INVENTORY,
        selector={
            "modelo": "100",
            "filing_year": 2025,
            "projection_grain": "taxpayer_year_activity",
            "fact": "row_field",
            "record": "inventory_activity",
            "grouping": "per_inventory_activity",
            "row_field": "opening_minus_closing_positive",
            "target_casilla_id": "0177",
        },
        binding_id="bad-inventory-destination",
        expected_substrings=(
            "bad-inventory-destination",
            "_InventorySelector",
            "opening_minus_closing_positive",
            "0182",
        ),
    )


def test_collectible_invoice_selector_accepts_well_shaped_selector() -> None:
    """A canonical scalar invoice-shaped binding passes the gate.

    A ``base_sum`` scalar fact must NOT declare ``row_field`` or ``grouping``
    (those are row-producer keys); the unified invoice validator rejects a
    scalar fact that carries a grouping. The well-shaped scalar selector here
    declares no grouping and passes.
    """

    binding = _binding(
        source=BindingSourceKind.COLLECTIBLE_INVOICE,
        selector={
            "fact": "base_sum",
        },
    )
    assert validate_binding_selector_shape(binding) == []


def test_collectible_invoice_row_field_selector_accepts_grouping() -> None:
    """A row-producer invoice-shaped binding declares row_field + grouping + op rows."""

    binding = DataBindingDefinition.model_validate(
        {
            "id": "collectible-rows",
            "source": BindingSourceKind.COLLECTIBLE_INVOICE,
            "selector": {
                "fact": "row_field",
                "row_field": "country_code",
                "grouping": "operator_clave",
            },
            "aggregation": BindingAggregation(op=BindingAggregationOp.ROWS),
            "legal_refs": ("ley-35-2006:art-99",),
            "source_refs": ("aeat-test",),
        },
    )
    assert validate_binding_selector_shape(binding) == []


def test_collectible_invoice_scalar_fact_rejects_grouping() -> None:
    """A scalar invoice fact paired with a row-producer grouping fails the unified gate.

    Under the single validator contract every invoice-shaped source runs the
    strict invoice fact/op invariant, so a ``base_sum`` scalar fact that also
    declares ``grouping`` (a row-producer key) is rejected at registry-build
    rather than slipping through the selector-shape entry point.
    """

    binding = _binding(
        source=BindingSourceKind.COLLECTIBLE_INVOICE,
        selector={
            "fact": "base_sum",
            "grouping": "operator_clave",
        },
        binding_id="bad-scalar-grouping",
    )
    failures = validate_binding_selector_shape(binding)
    assert failures
    assert "bad-scalar-grouping" in failures[0]


def test_counterpart_sources_validate_against_invoice_selector() -> None:
    """The four counterpart-aggregation sources share ``_InvoiceSelector``.

    ``ledger_transaction``, ``purchase_invoice_evidence``,
    ``payable_invoice``, and ``collectible_invoice`` all share the
    invoice-family selector shape (fact + claves + rectification_scope).
    Each must validate under the discriminator gate so a malformed
    selector under any of them fails at snapshot build.
    """

    for source in (
        "ledger_transaction",
        "purchase_invoice_evidence",
        "payable_invoice",
        "collectible_invoice",
    ):
        binding = _binding(
            source=source,
            selector={
                "fact": "base_sum",
                "claves": ("E", "M"),
                "rectification_scope": "exclude_rectifications",
            },
            binding_id=f"test-{source}",
        )
        assert validate_binding_selector_shape(binding) == [], f"well-shaped {source} selector should pass the gate"


def test_manual_input_accepts_supported_selector_shapes() -> None:
    """The casilla-id and record-field manual_input selector shapes validate.

    The boolean casilla-id shape is used by Modelo 100 estimacion-directa
    modality flags; the record-field shape is used by Modelo 131 etc.
    """

    selectors = (
        {
            "casilla_id": _M100_MANUAL_BOOLEAN_CASILLA,
            "data_type": "boolean",
            "true_value": "N",
            "false_value": "S",
        },
        {
            "record": "DPA",
            "field": "ano-inicio-actividad",
            "offset": 25,
            "length": 4,
            "data_type": "integer",
        },
    )
    for selector in selectors:
        binding = _binding(source="manual_input", selector=selector)
        assert validate_binding_selector_shape(binding) == []


def test_manual_input_rejects_malformed_selector_shapes() -> None:
    """Malformed manual_input selector shapes are rejected at construction."""

    cases = (
        (
            {
                "casilla_id": _M100_MANUAL_BOOLEAN_CASILLA,
                "record": "DPA",
                "field": "x",
                "offset": 1,
                "length": 1,
                "data_type": "integer",
            },
            "bad-mixed",
        ),
        (
            {
                "casilla": _M100_MANUAL_BOOLEAN_CASILLA,
                "data_type": "boolean",
                "true_value": "N",
                "false_value": "S",
            },
            "bad-generic-casilla-key",
        ),
        (
            {
                "casilla_id": _M100_MANUAL_BOOLEAN_CASILLA,
                "data_type": "boolean",
                "true_value": "N",
            },
            "bad-boolean",
        ),
    )
    for selector, binding_id in cases:
        _assert_selector_refused_at_construction(
            source="manual_input",
            selector=selector,
            binding_id=binding_id,
            expected_substrings=(binding_id,),
        )


def test_profile_selector_accepts_supported_shapes() -> None:
    """The scalar, composite, and profile-model selector shapes pass the gate.

    The TaxResidenceProfile shape on M100 uses this: ``profile_model``
    plus ``field`` without ``collection``, addressing a scalar field on
    a typed profile sub-model. The validator must accept this shape;
    ``collection`` is only required when ``repeating = true``.
    """

    selectors = (
        {
            "profile_key": "tax.id",
            "xsd_path": "/DatosIdentificativos/Declarante/DPNIF_D",
            "dictionary_field": "DPNIF_D",
        },
        {
            "profile_keys": ("surnames", "name"),
            "format": "surnames_name",
            "xsd_path": "/DatosIdentificativos/Declarante/DP_APENOM_D",
            "dictionary_field": "DP_APENOM_D",
        },
        {
            "profile_model": "TaxResidenceProfile",
            "field": "ccaa",
            "xsd_attribute": "codigoCADeclaracion",
            "dictionary_field": "ZCCAD",
        },
    )
    for selector in selectors:
        binding = _binding(source="profile", selector=selector)
        assert validate_binding_selector_shape(binding) == []


def test_profile_selector_rejects_malformed_shapes() -> None:
    """Malformed profile selector shapes are rejected at construction."""

    cases = (
        (
            {
                "profile_key": "tax.id",
                "profile_keys": ("a", "b"),
                "format": "surnames_name",
            },
            "bad-double-shape",
        ),
        (
            {
                "profile_key": "spouse.tax.id",
                "required_when_profile_key": "declaration.type",
            },
            "bad-required-when",
        ),
    )
    for selector, binding_id in cases:
        _assert_selector_refused_at_construction(
            source="profile",
            selector=selector,
            binding_id=binding_id,
            expected_substrings=(binding_id,),
        )


def test_invoice_binding_fact_op_mismatch_caught_at_snapshot_build() -> None:
    """Invoice fact/op cross-invariants fire at the snapshot-build gate.

    An invoice-source binding that declares ``fact = "operator_count"`` must
    pair it with ``aggregation.op = "count_distinct"``. A binding that pairs
    operator_count with op="sum" is structurally malformed; the single
    invoice validator lifts that invariant to build time so the snapshot-build
    gate catches it rather than only the resolver at handler-call time. Audit
    selector-drift F3.
    """
    # NEGATIVE TEST: source="collectible_invoice" is valid but the fact/op pair is invalid
    binding = DataBindingDefinition.model_validate(
        {
            "id": "bad-invoice-fact-op",
            "source": BindingSourceKind.COLLECTIBLE_INVOICE,
            "selector": {
                "fact": "operator_count",
                "claves": ("E", "M"),
                "rectification_scope": "exclude_rectifications",
            },
            "aggregation": BindingAggregation(op=BindingAggregationOp.SUM),  # mismatched op
            "legal_refs": ("ley-35-2006:art-99",),
            "source_refs": ("aeat-test",),
        },
    )
    failures = validate_binding_selector_shape(binding)
    assert failures
    assert "bad-invoice-fact-op" in failures[0]
    assert "invoice invariants" in failures[0]


def test_counterpart_binding_fact_op_mismatch_caught_at_snapshot_build() -> None:
    """Counterpart fact/op cross-invariants fire at the snapshot-build gate.

    ``ledger_transaction`` is a counterpart-only source (never an invoice
    source), so its build-time validator is the counterpart family validator.
    A binding that pairs ``fact = "operator_count"`` with op="sum" is
    structurally malformed; the lifted counterpart invariant catches it at
    snapshot build. Audit selector-drift F3.
    """
    binding = DataBindingDefinition.model_validate(
        {
            "id": "bad-counterpart-fact-op",
            "source": BindingSourceKind.LEDGER_TRANSACTION,
            "selector": {
                "fact": "operator_count",
                "claves": ("E", "M"),
                "rectification_scope": "exclude_rectifications",
            },
            "aggregation": BindingAggregation(op=BindingAggregationOp.SUM),  # mismatched op
            "legal_refs": ("ley-35-2006:art-99",),
            "source_refs": ("aeat-test",),
        },
    )
    failures = validate_binding_selector_shape(binding)
    assert failures
    assert "bad-counterpart-fact-op" in failures[0]
    assert "counterpart invariants" in failures[0]


def test_collectible_invoice_rejects_lowercase_clave() -> None:
    """Counterpart selectors inherit the uppercase-clave validator.

    The shared ``_InvoiceSelector`` enforces that claves are uppercase
    AEAT codes. A binding using a lowercase clave under any
    counterpart source must surface the violation through the gate.
    """

    _assert_selector_refused_at_construction(
        source=BindingSourceKind.COLLECTIBLE_INVOICE,
        selector={
            "fact": "base_sum",
            "claves": ("e",),  # lowercase: invalid
        },
        binding_id="bad-collectible",
        expected_substrings=("bad-collectible",),
    )


def test_bare_invoice_source_kind_is_not_constructible() -> None:
    """The retired bare ``invoice`` alias is outside the binding schema.

    The ``source`` field is the single canonical
    :class:`~cadrumo.core.BindingSourceKind` enum, so an unknown token is rejected
    by the before-validator with a ``not a valid BindingSourceKind`` value error.
    """

    with pytest.raises(ValidationError, match="not a valid BindingSourceKind"):
        _binding(
            source="invoice",
            selector={
                "fact": "base_sum",
                "claves": ("E",),
            },
            binding_id="bad-invoice",
        )


def test_previous_filing_selector_rejects_removed_relation_field() -> None:
    """The previous-filing selector no longer accepts a ``relation`` field.

    Historically the field was a runtime-ignored shorthand for documenting
    the cross-reference relation by id; the runtime resolves relation->
    binding linkage via ``RelationDefinition.target_binding`` and never
    consulted the selector value. The cleanup retired the field as dead schema
    surface — accepting arbitrary unverified strings was a silent-
    corruption hazard. The pydantic model now rejects unknown keys under
    ``extra='forbid'``; passing ``relation`` must surface as a typed
    diagnostic.
    """

    _assert_selector_refused_at_construction(
        source="previous_filing",
        selector={
            "source_modelo": "130",
            "source_casilla_id": _M130_SALDO_NEGATIVO_CASILLA,
            "relation": "atribucion-actividades-economicas",
        },
        binding_id="dead-relation-binding",
        expected_substrings=("dead-relation-binding", "relation"),
    )
