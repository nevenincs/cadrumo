"""Tests for canonical calculation source mesh contracts."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from ....adapters.persistence.storage.errors import DecryptionError
from ....core.resources import bundled_path
from ....domain.calculations.registry import CasillaId, load_registry_tree, validated_casilla_id
from .. import (
    CalculationSourceDiagnostic,
    CalculationSourceProvenance,
    CalculationSourceResolution,
    collect_unhandled_source_diagnostics,
    merge_source_resolutions,
    storage_degradation_resolution,
)
from .._errors import AggregationValidationError
from .._source_mesh import SourceMeshError

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_IVA_REPERCUTIDO_GENERAL_CASILLA: CasillaId = validated_casilla_id(
    "iva.repercutido.general",
    surface="_IVA_REPERCUTIDO_GENERAL_CASILLA",
)


def test_source_resolution_contract_is_strict_and_serializable() -> None:
    resolution = CalculationSourceResolution(
        resolver_id="ledger-iva",
        owned_sources=("ledger_iva_aggregation",),
        binding_values={"modelo-303-iva-repercutido-general-cuota": Decimal("21.00")},
        enum_binding_values={"profile-ccaa": "madrid"},
        date_binding_values={"profile-birth-date": date(1980, 1, 31)},
        relation_values={"modelo-180-rel-115-base-anual": Decimal("2128.75")},
        bound_inputs_by_casilla_id={_IVA_REPERCUTIDO_GENERAL_CASILLA: Decimal("21.00")},
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
    assert resolution.model_dump(mode="json")["binding_values"] == {"modelo-303-iva-repercutido-general-cuota": "21.00"}
    assert resolution.model_dump(mode="json")["date_binding_values"] == {"profile-birth-date": "1980-01-31"}
    assert resolution.model_dump(mode="json")["relation_values"] == {"modelo-180-rel-115-base-anual": "2128.75"}
    with pytest.raises(ValidationError, match="Extra inputs"):
        CalculationSourceResolution.model_validate({"resolver_id": "ledger-iva", "unexpected": True})


def test_source_resolution_rejects_legacy_bound_casilla_inputs_key() -> None:
    with pytest.raises(ValidationError, match="bound_casilla_inputs"):
        CalculationSourceResolution.model_validate(
            {
                "resolver_id": "ledger-iva",
                "bound_casilla_inputs": {_IVA_REPERCUTIDO_GENERAL_CASILLA: Decimal("21.00")},
            },
        )


def test_source_resolution_rejects_noncanonical_binding_keys() -> None:
    with pytest.raises(ValidationError) as decimal_exc:
        CalculationSourceResolution(
            resolver_id="source-mesh",
            binding_values={"Bad Binding": Decimal("1.00")},
        )
    assert decimal_exc.value.errors()[0]["loc"][0] == "binding_values"

    with pytest.raises(ValidationError) as enum_exc:
        CalculationSourceResolution(
            resolver_id="source-mesh",
            enum_binding_values={"Bad Binding": "madrid"},
        )
    assert enum_exc.value.errors()[0]["loc"][0] == "enum_binding_values"

    with pytest.raises(ValidationError) as date_exc:
        CalculationSourceResolution(
            resolver_id="source-mesh",
            date_binding_values={"Bad Binding": date(1980, 1, 31)},
        )
    assert date_exc.value.errors()[0]["loc"][0] == "date_binding_values"


def test_source_resolution_rejects_noncanonical_relation_keys() -> None:
    with pytest.raises(ValidationError) as relation_exc:
        CalculationSourceResolution(
            resolver_id="source-mesh",
            relation_values={"Bad Relation": Decimal("1.00")},
        )
    assert relation_exc.value.errors()[0]["loc"][0] == "relation_values"

    with pytest.raises(ValidationError) as unresolved_exc:
        CalculationSourceResolution(
            resolver_id="source-mesh",
            unresolved_relation_ids=("Bad Relation",),
        )
    assert unresolved_exc.value.errors()[0]["loc"][0] == "unresolved_relation_ids"


@pytest.mark.parametrize(
    ("payload", "message_key"),
    (
        (
            {"resolver_id": "source-mesh", "owned_sources": ("profile", " ")},
            "aggregation.source_mesh.errors.owned_sources_blank",
        ),
        (
            {"resolver_id": "source-mesh", "owned_sources": ("profile", "profile")},
            "aggregation.source_mesh.errors.owned_sources_duplicate",
        ),
        (
            {"resolver_id": "source-mesh", "source_transaction_ids": ("tx-1", " ")},
            "aggregation.source_mesh.errors.source_transaction_ids_blank",
        ),
        (
            {"resolver_id": "source-mesh", "source_transaction_ids": ("tx-1", "tx-1")},
            "aggregation.source_mesh.errors.source_transaction_ids_duplicate",
        ),
    ),
)
def test_source_resolution_validator_errors_are_localized(
    payload: dict[str, object],
    message_key: str,
) -> None:
    with pytest.raises(ValidationError) as exc_info:
        CalculationSourceResolution.model_validate(payload)

    context = exc_info.value.errors()[0].get("ctx")
    assert context is not None
    error = context["error"]
    assert isinstance(error, SourceMeshError)
    assert str(error) == message_key
    assert error.translated_message == message_key


def test_owned_sources_unknown_token_is_rejected_by_the_typed_field() -> None:
    """Anti-tautology: a non-member source token fails strict enum validation.

    The ``owned_sources`` carrier is typed ``tuple[BindingSourceKind, ...]`` and the
    before-coercer hydrates only KNOWN tokens; an unknown token falls through to the
    strict field, which rejects it. If this ever passes for a nonsense token, the
    carrier has silently widened back to bare strings and the type-lift is meaningless.
    """
    with pytest.raises(ValidationError) as exc_info:
        CalculationSourceResolution.model_validate(
            {"resolver_id": "source-mesh", "owned_sources": ("not_a_real_source_kind",)},
        )
    assert exc_info.value.errors()[0]["loc"][0] == "owned_sources"


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
        bound_inputs_by_casilla_id={_IVA_REPERCUTIDO_GENERAL_CASILLA: Decimal("21.00")},
    )
    right = CalculationSourceResolution(
        resolver_id="invoice",
        owned_sources=("payable_invoice",),
        bound_inputs_by_casilla_id={_IVA_REPERCUTIDO_GENERAL_CASILLA: Decimal("99.00")},
    )

    with pytest.raises(AggregationValidationError) as exc_info:
        merge_source_resolutions((left, right))

    assert str(exc_info.value) == "aggregation.source_mesh.errors.duplicate_bound_casilla_owner"
    context = exc_info.value.context
    assert context is not None
    assert context["casilla_id"] == _IVA_REPERCUTIDO_GENERAL_CASILLA
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
        owned_sources=("previous_filing",),
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


def test_source_resolution_merge_rejects_duplicate_binding_across_value_channels() -> None:
    left = CalculationSourceResolution(
        resolver_id="profile",
        owned_sources=("profile",),
        date_binding_values={"profile-birth-date": date(1980, 1, 31)},
    )
    right = CalculationSourceResolution(
        resolver_id="manual-bridge",
        owned_sources=("manual_input",),
        binding_values={"profile-birth-date": Decimal("1.00")},
    )

    with pytest.raises(AggregationValidationError) as exc_info:
        merge_source_resolutions((left, right))

    assert str(exc_info.value) == "aggregation.source_mesh.errors.duplicate_binding_owner"
    context = exc_info.value.context
    assert context is not None
    assert context["binding_id"] == "profile-birth-date"
    assert context["first_resolver"] == "profile"
    assert context["second_resolver"] == "manual-bridge"


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
        date_binding_values={"profile-birth-date": date(1980, 1, 31)},
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
        ),
    )

    assert merged.resolver_id == "source_mesh"
    assert merged.owned_sources == ("ledger_iva_aggregation", "profile")
    assert merged.binding_values["binding-decimal"] == ledger_resolution.binding_values["binding-decimal"]
    assert merged.relation_values["relation-decimal"] == ledger_resolution.relation_values["relation-decimal"]
    assert merged.date_binding_values["profile-birth-date"] == date(1980, 1, 31)
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


def test_storage_degradation_resolution_emits_diagnostic_and_debug_log(
    caplog: pytest.LogCaptureFixture,
) -> None:
    error = DecryptionError("ciphertext authentication failed")

    with caplog.at_level("DEBUG", logger="aeat.application.aggregation._source_mesh"):
        resolution = storage_degradation_resolution(
            resolver_id="ledger-iva",
            owned_sources=("ledger_iva_aggregation",),
            source_kinds=("ledger_iva_aggregation",),
            error=error,
        )

    assert resolution.binding_values == {}
    assert resolution.diagnostics[0].reason == "storage_degraded"
    assert resolution.diagnostics[0].source_kind == "ledger_iva_aggregation"
    assert resolution.diagnostics[0].message
    assert any("source mesh resolver storage degradation" in record.message for record in caplog.records)
