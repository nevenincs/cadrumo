"""Strict tests for the snapshot-time selector-shape gate.

The :func:`validate_binding_selector_shape` helper pairs each
:attr:`DataBindingDefinition.source` value with a strict pydantic
model and asserts the binding's selector mapping validates against
the source's schema. The snapshot-build path runs this on every
binding so a misshapen selector fails at construction rather than
at handler-call time.

This file pins:

  * the registry of typed selectors is non-empty and registers the
    ten typed sources defined in ``_bindings``;
  * a well-shaped selector for each typed source passes the gate;
  * a misshapen selector for a typed source surfaces the violation
    as a typed diagnostic string (not as a silent pass);
  * a binding whose source is intentionally free-form (no entry in
    the discriminator registry) returns no diagnostics, so the gate
    remains incremental rather than fail-closed.
"""

from __future__ import annotations

import pytest

from ._bindings import (
    _BINDING_SELECTOR_REGISTRY,
    _InvoiceSelector,
    _PreviousFilingSelector,
    _WithholdingSelector,
    validate_binding_selector_shape,
)
from ._schema import DataBindingDefinition

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def _binding(
    *,
    source: str,
    selector: dict[str, object],
    binding_id: str = "test-binding",
) -> DataBindingDefinition:
    """Build a minimal DataBindingDefinition for the gate to validate."""

    return DataBindingDefinition(
        id=binding_id,
        source=source,  # type: ignore[arg-type]  # narrowed at runtime by the Literal
        selector=selector,  # type: ignore[arg-type]  # the gate validates per-source
        legal_refs=("lirpf.art-99",),
        source_refs=("aeat.test",),
    )


def test_binding_selector_registry_covers_typed_sources() -> None:
    """The discriminator registry must enumerate every typed selector."""

    expected = {
        "previous_filing",
        "invoice",
        "ledger_oss_aggregation",
        "ledger_iva_aggregation",
        "ledger_renta_expense_aggregation",
        "withholding",
        "related_party_operation",
        "foreign_asset",
        "atribucion_member",
        "refund_operation",
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
    """The direct-value-copy shape (singular source_output + relation) passes.

    Real registry bindings (e.g. M100 retenciones relations against
    M111/M115/M123) declare a ``source_output`` casilla rather than
    a ``source_casillas`` tuple. The typed selector must accept this
    second shape, validated as the exclusive alternative to the
    plural form.
    """

    binding = _binding(
        source="previous_filing",
        selector={
            "source_modelo": "111",
            "source_output": "28",
            "relation": "retenciones-trabajo-actividades-premios",
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
    assert "_PreviousFilingSelector" in failures[0]


def test_withholding_selector_accepts_well_shaped_selector() -> None:
    """A withholding binding's fact + claves selector passes the gate."""

    binding = _binding(
        source="withholding",
        selector={
            "fact": "retencion_practicada_sum",
            "claves": ("A", "G"),
        },
    )
    assert validate_binding_selector_shape(binding) == []


def test_invoice_selector_accepts_well_shaped_selector() -> None:
    """An invoice binding with grouping + fact passes the gate."""

    binding = _binding(
        source="invoice",
        selector={
            "fact": "base_amount_sum",
            "grouping": "operator_clave",
        },
    )
    assert validate_binding_selector_shape(binding) == []


def test_free_form_source_returns_no_diagnostics() -> None:
    """A binding whose source has no registry entry short-circuits cleanly.

    Sources like ``manual_input`` and ``profile`` are not yet typed
    in the discriminator registry; the gate must return an empty
    failure list for them so existing registry data keeps loading.
    """

    binding = _binding(
        source="manual_input",
        selector={"label": "operator-supplied", "value_kind": "decimal"},
    )
    assert validate_binding_selector_shape(binding) == []


def test_invoice_selector_rejects_misshapen_selector() -> None:
    """An invoice binding missing the required ``fact`` key fails the gate."""

    binding = _binding(
        source="invoice",
        selector={
            # ``fact`` is required on _InvoiceSelector; omitting it
            # must surface a validation diagnostic, not pass silently.
            "grouping": "operator_clave",
        },
        binding_id="bad-invoice",
    )
    failures = validate_binding_selector_shape(binding)
    assert failures, "invoice selector missing required field must be flagged"
    assert "bad-invoice" in failures[0]
    assert "_InvoiceSelector" in failures[0]
