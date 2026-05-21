"""Tests for canonical calculation source mesh contracts."""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from aeat.core.resources import bundled_path
from aeat.domain.calculations.registry import load_registry_tree

from . import (
    CalculationSourceDiagnostic,
    CalculationSourceProvenance,
    CalculationSourceResolution,
    collect_unhandled_source_diagnostics,
    merge_source_resolutions,
)
from ._errors import AggregationValidationError

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


def test_source_resolution_contract_is_strict_and_serializable() -> None:
    resolution = CalculationSourceResolution(
        resolver_id="ledger-iva",
        owned_sources=("ledger_iva_aggregation",),
        binding_values={"modelo-303-iva-repercutido-general-cuota": Decimal("21.00")},
        enum_binding_values={"profile-ccaa": "madrid"},
        relation_values={"modelo-180-rel-115-base-anual": Decimal("2128.75")},
        bound_casilla_inputs={"iva.repercutido.general": Decimal("21.00")},
        source_transaction_ids=("tx-2", "tx-1"),
        diagnostics=(
            CalculationSourceDiagnostic(
                reason="unhandled_binding_source",
                source_kind="withholding",
                binding_id="withholding-total",
                message="binding 'withholding-total' declares source 'withholding' with no enrolled resolver",
            ),
        ),
        provenance=(
            CalculationSourceProvenance(
                source_kind="ledger_iva_aggregation",
                source_ref="transaction:tx-1",
                fingerprint="sha256:abc",
            ),
        ),
    )

    assert tuple(resolution.source_transaction_ids) == ("tx-1", "tx-2")
    assert resolution.model_dump(mode="json")["binding_values"] == {
        "modelo-303-iva-repercutido-general-cuota": "21.00"
    }
    assert resolution.model_dump(mode="json")["relation_values"] == {"modelo-180-rel-115-base-anual": "2128.75"}
    with pytest.raises(ValidationError, match="Extra inputs"):
        CalculationSourceResolution.model_validate({"resolver_id": "ledger-iva", "unexpected": True})


def test_source_resolution_merge_rejects_duplicate_binding_ownership() -> None:
    left = CalculationSourceResolution(
        resolver_id="ledger-iva",
        owned_sources=("ledger_iva_aggregation",),
        binding_values={"modelo-303-iva-repercutido-general-cuota": Decimal("21.00")},
    )
    right = CalculationSourceResolution(
        resolver_id="manual-bridge",
        owned_sources=("manual_input",),
        binding_values={"modelo-303-iva-repercutido-general-cuota": Decimal("99.00")},
    )

    with pytest.raises(AggregationValidationError) as exc_info:
        merge_source_resolutions((left, right))

    assert str(exc_info.value) == "aggregation.source_mesh.errors.duplicate_binding_owner"
    context = exc_info.value.context
    assert context is not None
    assert context["binding_id"] == "modelo-303-iva-repercutido-general-cuota"
    assert context["first_resolver"] == "ledger-iva"
    assert context["second_resolver"] == "manual-bridge"


def test_source_resolution_merge_rejects_duplicate_bound_casilla_ownership() -> None:
    left = CalculationSourceResolution(
        resolver_id="ledger-iva",
        owned_sources=("ledger_iva_aggregation",),
        bound_casilla_inputs={"iva.repercutido.general": Decimal("21.00")},
    )
    right = CalculationSourceResolution(
        resolver_id="invoice",
        owned_sources=("invoice",),
        bound_casilla_inputs={"iva.repercutido.general": Decimal("99.00")},
    )

    with pytest.raises(AggregationValidationError) as exc_info:
        merge_source_resolutions((left, right))

    assert str(exc_info.value) == "aggregation.source_mesh.errors.duplicate_bound_casilla_owner"
    context = exc_info.value.context
    assert context is not None
    assert context["casilla_id"] == "iva.repercutido.general"
    assert context["first_resolver"] == "ledger-iva"
    assert context["second_resolver"] == "invoice"


def test_source_resolution_merge_rejects_duplicate_relation_ownership() -> None:
    left = CalculationSourceResolution(
        resolver_id="relation-prefill",
        owned_sources=("relation_prefill",),
        relation_values={"modelo-180-rel-115-base-anual": Decimal("2128.75")},
    )
    right = CalculationSourceResolution(
        resolver_id="aeat-live",
        owned_sources=("aeat_live",),
        relation_values={"modelo-180-rel-115-base-anual": Decimal("99.00")},
    )

    with pytest.raises(AggregationValidationError) as exc_info:
        merge_source_resolutions((left, right))

    assert str(exc_info.value) == "aggregation.source_mesh.errors.duplicate_relation_owner"
    context = exc_info.value.context
    assert context is not None
    assert context["relation_id"] == "modelo-180-rel-115-base-anual"
    assert context["first_resolver"] == "relation-prefill"
    assert context["second_resolver"] == "aeat-live"


def test_source_resolution_merge_preserves_values_provenance_and_diagnostics() -> None:
    diagnostic = CalculationSourceDiagnostic(
        reason="unhandled_binding_source",
        source_kind="withholding",
        binding_id="withholding-total",
        message="binding 'withholding-total' declares source 'withholding' with no enrolled resolver",
    )
    provenance = CalculationSourceProvenance(
        source_kind="ledger_iva_aggregation",
        source_ref="transaction:tx-1",
        fingerprint="sha256:abc",
    )

    binding_input = Decimal("21.07")
    relation_input = Decimal("38.49")
    ledger_resolution = CalculationSourceResolution(
        resolver_id="ledger-iva",
        owned_sources=("ledger_iva_aggregation",),
        binding_values={"binding-decimal": binding_input},
        relation_values={"relation-decimal": relation_input},
        source_transaction_ids=("tx-1",),
        provenance=(provenance,),
    )
    merged = merge_source_resolutions(
        (
            ledger_resolution,
            CalculationSourceResolution(
                resolver_id="profile",
                owned_sources=("profile",),
                enum_binding_values={"profile-ccaa": "madrid"},
                diagnostics=(diagnostic,),
            ),
        )
    )

    assert merged.resolver_id == "source_mesh"
    assert merged.owned_sources == ("ledger_iva_aggregation", "profile")
    assert merged.binding_values["binding-decimal"] == ledger_resolution.binding_values["binding-decimal"]
    assert merged.relation_values["relation-decimal"] == ledger_resolution.relation_values["relation-decimal"]
    assert merged.enum_binding_values["profile-ccaa"] == "madrid"
    assert tuple(merged.source_transaction_ids) == ("tx-1",)
    assert merged.diagnostics == (diagnostic,)
    assert merged.provenance == (provenance,)


def test_unhandled_source_diagnostics_name_modelo_binding_and_source_kind() -> None:
    modelos, _ = load_registry_tree(bundled_path("registry", "aeat"))
    modelo_303 = next(modelo for modelo in modelos if modelo.id == "303")
    revision = modelo_303.revisions["2009-y-siguientes"]

    diagnostics = collect_unhandled_source_diagnostics(revision, handled_sources=frozenset())

    ledger_diagnostics = tuple(
        diagnostic for diagnostic in diagnostics if diagnostic.source_kind == "ledger_iva_aggregation"
    )
    assert ledger_diagnostics
    assert all(diagnostic.reason == "unhandled_binding_source" for diagnostic in ledger_diagnostics)
    assert all(diagnostic.binding_id for diagnostic in ledger_diagnostics)
    assert all("ledger_iva_aggregation" in diagnostic.message for diagnostic in ledger_diagnostics)
