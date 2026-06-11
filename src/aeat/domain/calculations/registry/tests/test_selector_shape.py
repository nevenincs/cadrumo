"""Strict tests for the snapshot-time selector-shape gate.

The :func:`validate_binding_selector_shape` helper pairs each
:attr:`DataBindingDefinition.source` value with a strict pydantic
model and asserts the binding's selector mapping validates against
the source's schema. The snapshot-build path runs this on every
binding so a misshapen selector fails at construction rather than
at handler-call time.

This file pins:

  * the registry of map-backed typed selectors is non-empty and
    registers every typed source key currently declared in
    ``_BINDING_SELECTOR_REGISTRY``;
  * a well-shaped selector for each typed source passes the gate;
  * a misshapen selector for a typed source surfaces the violation
    as a typed diagnostic string (not as a silent pass);
  * a binding whose source is intentionally free-form (no entry in
    the discriminator registry) returns no diagnostics, so the gate
    remains incremental rather than fail-closed.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from .._bindings import (
    _BINDING_SELECTOR_REGISTRY,
    validate_binding_selector_shape,
)
from .._schema import DataBindingDefinition

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _binding(
    *,
    source: str,
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
        "related_party_operation",
        "foreign_asset",
        "atribucion_member",
        "refund_operation",
        "manual_input",
        "profile",
    }
    assert set(_BINDING_SELECTOR_REGISTRY) == expected


def test_previous_filing_selector_accepts_well_shaped_selector() -> None:
    """A previous_filing binding with a registry-valid selector passes the gate."""

    binding = _binding(
        source="previous_filing",
        selector={
            "source_modelo": "303",
            "filing_year_delta": -1,
            "period": "0A",
            "source_casillas": ("66",),
        },
    )
    assert validate_binding_selector_shape(binding) == []


def test_previous_filing_selector_accepts_singular_source_output_shape() -> None:
    """The direct-value-copy shape (singular source_output) passes.

    Real registry bindings (e.g. M100 retenciones relations against
    M111/M115/M123) declare a ``source_output`` casilla rather than
    a ``source_casillas`` tuple. The typed selector must accept this
    second shape, validated as the exclusive alternative to the
    plural form. (The selector.relation shorthand was retired under
    selector contract; relation->binding linkage is via
    RelationDefinition.target_binding.)
    """

    binding = _binding(
        source="previous_filing",
        selector={
            "source_modelo": "111",
            "source_output": "28",
        },
    )
    assert validate_binding_selector_shape(binding) == []


def test_previous_filing_selector_accepts_singular_source_output_with_period_offset() -> None:
    binding = _binding(
        source="previous_filing",
        selector={
            "source_modelo": "303",
            "source_output": "iva.compensacion-disponible-fin-periodo",
            "source_period_offset_from_target": -1,
        },
    )
    assert validate_binding_selector_shape(binding) == []


def test_previous_filing_selector_rejects_both_source_shapes() -> None:
    """Declaring source_output AND source_casillas in the same selector fails.

    The two shapes are exclusive: one for direct copy, one for
    aggregation. A binding that declares both is malformed; the
    typed model surfaces this as a validation failure.
    """

    binding = _binding(
        source="previous_filing",
        selector={
            "source_modelo": "111",
            "source_output": "28",
            "source_casillas": ("28",),
            "relation": "retenciones-trabajo-actividades-premios",
        },
        binding_id="bad-double-source",
    )
    failures = validate_binding_selector_shape(binding)
    assert failures
    assert "bad-double-source" in failures[0]


def test_previous_filing_selector_rejects_unknown_key() -> None:
    """An extra key on a previous_filing selector surfaces a typed diagnostic.

    The typed model declares ``extra='forbid'``; the gate must
    propagate the violation as a diagnostic naming the binding id
    and the typed model.
    """

    binding = _binding(
        source="previous_filing",
        selector={
            "source_modelo": "303",
            "filing_year_delta": -1,
            "source_casillas": ("66",),
            "spurious_key": "leaked",
        },
        binding_id="bad-previous-filing",
    )
    failures = validate_binding_selector_shape(binding)
    assert failures, "extra key on previous_filing selector must be flagged"
    assert "bad-previous-filing" in failures[0]
    assert "_PreviousModeloSelector" in failures[0]


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

    binding = _binding(
        source="withholding",
        selector={
            "fact": "bogus_fact_value",
            "claves": ("A",),
        },
        binding_id="bad-withholding-fact",
    )
    failures = validate_binding_selector_shape(binding)
    assert failures
    assert "bad-withholding-fact" in failures[0]


def test_collectible_invoice_selector_accepts_well_shaped_selector() -> None:
    """A canonical invoice-shaped binding with grouping + fact passes the gate."""

    binding = _binding(
        source="collectible_invoice",
        selector={
            "fact": "base_sum",
            "grouping": "operator_clave",
        },
    )
    assert validate_binding_selector_shape(binding) == []


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
    """The casilla-shape manual_input selector (boolean toggles) validates.

    Used by Modelo 100 estimacion-directa modality flags etc.
    """

    binding = _binding(
        source="manual_input",
        selector={
            "casilla": "0168",
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
    """Declaring casilla AND record-field in the same selector fails."""

    binding = _binding(
        source="manual_input",
        selector={
            "casilla": "0168",
            "record": "DPA",
            "field": "x",
            "offset": 1,
            "length": 1,
            "data_type": "integer",
        },
        binding_id="bad-mixed",
    )
    failures = validate_binding_selector_shape(binding)
    assert failures
    assert "bad-mixed" in failures[0]


def test_manual_input_boolean_casilla_requires_value_strings() -> None:
    """A boolean casilla must declare both true_value and false_value."""

    binding = _binding(
        source="manual_input",
        selector={
            "casilla": "0168",
            "data_type": "boolean",
            "true_value": "N",
            # missing false_value
        },
        binding_id="bad-boolean",
    )
    failures = validate_binding_selector_shape(binding)
    assert failures
    assert "bad-boolean" in failures[0]


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

    binding = _binding(
        source="profile",
        selector={
            "profile_key": "tax.id",
            "profile_keys": ("a", "b"),
            "format": "surnames_name",
        },
        binding_id="bad-double-shape",
    )
    failures = validate_binding_selector_shape(binding)
    assert failures
    assert "bad-double-shape" in failures[0]


def test_profile_selector_required_when_pair_must_match() -> None:
    """required_when_profile_key without required_when_value is rejected."""

    binding = _binding(
        source="profile",
        selector={
            "profile_key": "spouse.tax.id",
            "required_when_profile_key": "declaration.type",
            # missing required_when_value
        },
        binding_id="bad-required-when",
    )
    failures = validate_binding_selector_shape(binding)
    assert failures
    assert "bad-required-when" in failures[0]


def test_counterpart_binding_fact_op_mismatch_caught_at_snapshot_build() -> None:
    """Counterpart fact/op cross-invariants fire at the snapshot-build gate.

    A counterpart-source binding that declares ``fact = "operator_count"``
    must pair it with ``aggregation.op = "count_distinct"`` (per the
    handler-call-time invariant in ``_validated_counterpart_selector``).
    A binding that pairs operator_count with op="sum" is structurally
    malformed; without this lifted invariant the snapshot-build gate
    would pass it and the resolver would only raise at handler-call
    time. Audit selector-drift F3.
    """
    # NEGATIVE TEST: source="collectible_invoice" is valid but the fact/op pair is invalid (ty: invalid-argument-type)
    binding = DataBindingDefinition(
        id="bad-counterpart-fact-op",
        source="collectible_invoice",  # type: ignore
        selector={
            "fact": "operator_count",
            "claves": ("E", "M"),
            "rectification_scope": "exclude_rectifications",
        },
        aggregation={"op": "sum"},  # mismatched op — should be "count_distinct"
        legal_refs=("lirpf.art-99",),
        source_refs=("aeat.test",),
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

    binding = _binding(
        source="collectible_invoice",
        selector={
            "fact": "base_sum",
            "claves": ("e",),  # lowercase: invalid
        },
        binding_id="bad-collectible",
    )
    failures = validate_binding_selector_shape(binding)
    assert failures
    assert "bad-collectible" in failures[0]


def test_bare_invoice_source_kind_is_not_constructible() -> None:
    """The retired bare ``invoice`` alias is outside the binding schema."""

    with pytest.raises(ValidationError, match="Input should be"):
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

    binding = _binding(
        source="previous_filing",
        selector={
            "source_modelo": "130",
            "source_output": "saldo-negativo-fin-periodo",
            "relation": "atribucion-actividades-economicas",
        },
        binding_id="dead-relation-binding",
    )
    failures = validate_binding_selector_shape(binding)
    assert failures, "selector.relation must be rejected by the gate"
    assert "dead-relation-binding" in failures[0]
    assert "relation" in failures[0].lower() or "extra" in failures[0].lower()
