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

import pytest
from pydantic import ValidationError

from .....core.aggregation import BindingAggregation, BindingAggregationOp, BindingSourceKind
from .. import CasillaId, validated_casilla_id
from .._binding_selector_utils import selector_as_dict
from .._bindings import (
    _BINDING_SELECTOR_REGISTRY,
    selector_model_for_source,
    validate_binding_selector_shape,
)
from .._schema import DataBindingDefinition

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


def _binding(
    *,
    source: str | BindingSourceKind,
    selector: dict[str, object],
    binding_id: str = "test-binding",
) -> DataBindingDefinition:
    """Build a minimal DataBindingDefinition for the gate to validate."""

    return DataBindingDefinition.model_validate(
        {
            "id": binding_id,
            "source": source,
            "selector": selector,
            "legal_refs": ("lirpf.art-99",),
            "source_refs": ("aeat.test",),
        },
    )


def _assert_selector_refused_at_construction(
    *,
    source: str,
    selector: dict[str, object],
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
    """The discriminator registry must enumerate every map-backed typed selector."""

    expected = {
        "previous_filing",
        "relation_prefill",
        # counterpart-aggregation family shares _InvoiceSelector
        "ledger_transaction",
        "purchase_invoice_evidence",
        "payable_invoice",
        "collectible_invoice",
        "ledger_oss_aggregation",
        "ledger_iva_aggregation",
        "ledger_renta_expense_aggregation",
        "ledger_renta_income_aggregation",
        "ledger_renta_gasto_aggregation",
        "retenciones_aggregation",
        "withholding",
        "related_party_operation",
        "foreign_asset",
        "atribucion_member",
        "refund_operation",
        "manual_input",
        "profile",
        "iva_compensation_annual_partition",
    }
    assert set(_BINDING_SELECTOR_REGISTRY) == expected


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


@pytest.mark.parametrize("source", (BindingSourceKind.BORRADOR, BindingSourceKind.IVA_WALLET_DECISION))
def test_mesh_only_source_kind_is_not_constructible_as_registry_binding(source: BindingSourceKind) -> None:
    """Mesh-only source kinds are first-class enum members, not registry bindings."""

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


def test_previous_filing_selector_rejects_legacy_source_casillas_key() -> None:
    _assert_selector_refused_at_construction(
        source="previous_filing",
        selector={
            "source_modelo": "303",
            "filing_year_delta": -1,
            "period": "0A",
            "source_casillas": ("66",),
        },
        binding_id="bad-legacy-source-casillas",
        expected_substrings=("source_casilla_ids", "source_casillas"),
    )


def test_relation_prefill_selector_rejects_legacy_source_casillas_key() -> None:
    _assert_selector_refused_at_construction(
        source="relation_prefill",
        selector={
            "source_modelo": "322",
            "source_periods": ("1T",),
            "source_casillas": (_M303_CUOTA_DEVENGADA_TOTAL_CASILLA,),
        },
        binding_id="bad-relation-prefill-legacy-source-casillas",
        expected_substrings=("source_casilla_ids", "source_casillas"),
    )


def test_previous_filing_selector_rejects_legacy_source_output_key() -> None:
    _assert_selector_refused_at_construction(
        source="previous_filing",
        selector={
            "source_modelo": "111",
            "source_output": "28",
        },
        binding_id="bad-legacy-source-output",
        expected_substrings=("source_casilla_id", "source_output"),
    )


def test_relation_prefill_selector_rejects_legacy_source_output_key() -> None:
    _assert_selector_refused_at_construction(
        source="relation_prefill",
        selector={
            "source_modelo": "303",
            "source_output": "iva.cuota-devengada-total",
        },
        binding_id="bad-relation-prefill-source-output",
        expected_substrings=("source_casilla_id", "source_output"),
    )


@pytest.mark.parametrize("source", ("previous_filing", "relation_prefill"))
def test_cross_filing_selectors_reject_non_modelo_id_source_modelo(source: str) -> None:
    selector: dict[str, object] = {
        "source_modelo": "modelo-303",
        "source_casilla_id": _M303_CUOTA_DEVENGADA_TOTAL_CASILLA,
    }
    _assert_selector_refused_at_construction(
        source=source,
        selector=selector,
        binding_id=f"bad-{source}-source-modelo",
        expected_substrings=("source_modelo", r"^\d{3}$"),
    )


def test_previous_filing_selector_accepts_singular_source_casilla_id_shape() -> None:
    """The direct-value-copy shape (singular source_casilla_id) passes.

    Real registry bindings (e.g. M100 retenciones relations against
    M111/M115/M123) declare a ``source_casilla_id`` casilla rather than
    a ``source_casilla_ids`` tuple. The typed selector must accept this
    second shape, validated as the exclusive alternative to the
    plural form. (The selector.relation shorthand was retired under
    selector contract; relation->binding linkage is via
    RelationDefinition.target_binding.)
    """

    binding = _binding(
        source="previous_filing",
        selector={
            "source_modelo": "111",
            "source_casilla_id": _M111_RETENCIONES_CASILLA,
        },
    )
    assert validate_binding_selector_shape(binding) == []


def test_previous_filing_selector_accepts_singular_source_casilla_id_with_period_offset() -> None:
    binding = _binding(
        source="previous_filing",
        selector={
            "source_modelo": "303",
            "source_casilla_id": _M303_COMPENSACION_DISPONIBLE_CASILLA,
            "source_period_offset_from_target": -1,
        },
    )
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
        expected_substrings=("bad-previous-filing", "_PreviousModeloSelector"),
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
            "legal_refs": ("lirpf.art-99",),
            "source_refs": ("aeat.test",),
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


def test_manual_input_accepts_boolean_casilla_shape() -> None:
    """The casilla_id-shape manual_input selector (boolean toggles) validates.

    Used by Modelo 100 estimacion-directa modality flags etc.
    """

    binding = _binding(
        source="manual_input",
        selector={
            "casilla_id": _M100_MANUAL_BOOLEAN_CASILLA,
            "data_type": "boolean",
            "true_value": "N",
            "false_value": "S",
        },
    )
    assert validate_binding_selector_shape(binding) == []


def test_manual_input_accepts_record_field_shape() -> None:
    """The record-field-shape manual_input selector (M131 etc) validates."""

    binding = _binding(
        source="manual_input",
        selector={
            "record": "DPA",
            "field": "ano-inicio-actividad",
            "offset": 25,
            "length": 4,
            "data_type": "integer",
        },
    )
    assert validate_binding_selector_shape(binding) == []


def test_manual_input_rejects_both_shapes_together() -> None:
    """Declaring casilla_id AND record-field in the same selector fails."""

    _assert_selector_refused_at_construction(
        source="manual_input",
        selector={
            "casilla_id": _M100_MANUAL_BOOLEAN_CASILLA,
            "record": "DPA",
            "field": "x",
            "offset": 1,
            "length": 1,
            "data_type": "integer",
        },
        binding_id="bad-mixed",
        expected_substrings=("bad-mixed",),
    )


def test_manual_input_rejects_generic_casilla_key() -> None:
    _assert_selector_refused_at_construction(
        source="manual_input",
        selector={
            "casilla": _M100_MANUAL_BOOLEAN_CASILLA,
            "data_type": "boolean",
            "true_value": "N",
            "false_value": "S",
        },
        binding_id="bad-generic-casilla-key",
        expected_substrings=("bad-generic-casilla-key",),
    )


def test_manual_input_boolean_casilla_requires_value_strings() -> None:
    """A boolean casilla must declare both true_value and false_value."""

    _assert_selector_refused_at_construction(
        source="manual_input",
        selector={
            "casilla_id": _M100_MANUAL_BOOLEAN_CASILLA,
            "data_type": "boolean",
            "true_value": "N",
            # missing false_value
        },
        binding_id="bad-boolean",
        expected_substrings=("bad-boolean",),
    )


def test_profile_selector_accepts_scalar_shape() -> None:
    """A scalar profile_key selector (taxpayer.tax.id etc) passes the gate."""

    binding = _binding(
        source="profile",
        selector={
            "profile_key": "tax.id",
            "xsd_path": "/DatosIdentificativos/Declarante/DPNIF_D",
            "dictionary_field": "DPNIF_D",
        },
    )
    assert validate_binding_selector_shape(binding) == []


def test_profile_selector_accepts_composite_shape() -> None:
    """A composite profile_keys + format selector passes the gate."""

    binding = _binding(
        source="profile",
        selector={
            "profile_keys": ("surnames", "name"),
            "format": "surnames_name",
            "xsd_path": "/DatosIdentificativos/Declarante/DP_APENOM_D",
            "dictionary_field": "DP_APENOM_D",
        },
    )
    assert validate_binding_selector_shape(binding) == []


def test_profile_selector_accepts_model_scalar_shape() -> None:
    """A profile_model + field selector (non-repeating) passes the gate.

    The TaxResidenceProfile shape on M100 uses this: ``profile_model``
    plus ``field`` without ``collection``, addressing a scalar field on
    a typed profile sub-model. The validator must accept this shape;
    ``collection`` is only required when ``repeating = true``.
    """

    binding = _binding(
        source="profile",
        selector={
            "profile_model": "TaxResidenceProfile",
            "field": "ccaa",
            "xsd_attribute": "codigoCADeclaracion",
            "dictionary_field": "ZCCAD",
        },
    )
    assert validate_binding_selector_shape(binding) == []


def test_profile_selector_rejects_multiple_shapes() -> None:
    """Declaring scalar + composite shapes in the same selector fails."""

    _assert_selector_refused_at_construction(
        source="profile",
        selector={
            "profile_key": "tax.id",
            "profile_keys": ("a", "b"),
            "format": "surnames_name",
        },
        binding_id="bad-double-shape",
        expected_substrings=("bad-double-shape",),
    )


def test_profile_selector_required_when_pair_must_match() -> None:
    """required_when_profile_key without required_when_value is rejected."""

    _assert_selector_refused_at_construction(
        source="profile",
        selector={
            "profile_key": "spouse.tax.id",
            "required_when_profile_key": "declaration.type",
            # missing required_when_value
        },
        binding_id="bad-required-when",
        expected_substrings=("bad-required-when",),
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
            "legal_refs": ("lirpf.art-99",),
            "source_refs": ("aeat.test",),
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
            "legal_refs": ("lirpf.art-99",),
            "source_refs": ("aeat.test",),
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
    :class:`~aeat.core.BindingSourceKind` enum, so an unknown token is rejected
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
