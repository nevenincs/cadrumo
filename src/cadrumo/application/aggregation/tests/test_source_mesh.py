"""Tests for canonical calculation source mesh contracts."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from ....adapters.persistence.storage.errors import DecryptionError
from ....core import BindingSourceKind, CalculationSourceLineageRole, CasillaId, validated_casilla_id
from ....core.resources import resources
from .. import (
    CalculationSourceDiagnostic,
    CalculationSourceProvenance,
    CalculationSourceResolution,
    CompositeSourceResolverId,
    collect_unhandled_source_diagnostics,
    merge_source_resolutions,
    storage_degradation_resolution,
)
from .._errors import AggregationValidationError
from .._source_mesh import SourceMeshError, out_of_window_summary_source_diagnostic

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_IVA_REPERCUTIDO_GENERAL_CASILLA: CasillaId = validated_casilla_id(
    "iva.repercutido.general",
    surface="_IVA_REPERCUTIDO_GENERAL_CASILLA",
)


def test_source_resolution_contract_is_strict_and_serializable() -> None:
    resolution = CalculationSourceResolution(
        resolver_id="ledger-iva",
        owned_sources=(BindingSourceKind.LEDGER_IVA_AGGREGATION,),
        binding_values={"modelo-303-iva-repercutido-general-cuota": Decimal("21.00")},
        enum_binding_values={"profile-ccaa": "madrid"},
        date_binding_values={"profile-birth-date": date(1980, 1, 31)},
        row_binding_values={("modelo-720-asset-row-valuation", 2): Decimal("60000.00")},
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
                resolver_id="ledger-iva",
                resolved_binding_source=BindingSourceKind.LEDGER_IVA_AGGREGATION,
                contributor_source_kind="ledger_iva_aggregation",
                contributor_binding_source=BindingSourceKind.LEDGER_IVA_AGGREGATION,
                lineage_role=CalculationSourceLineageRole.PRIMARY,
                source_ref="transaction:tx-1",
                parent_source_ref=None,
                fingerprint="sha256:abc",
            ),
        ),
    )

    assert tuple(resolution.source_transaction_ids) == ("tx-1", "tx-2")
    assert resolution.diagnostics[0].binding_source is BindingSourceKind.WITHHOLDING
    assert resolution.provenance[0].resolved_binding_source is BindingSourceKind.LEDGER_IVA_AGGREGATION
    assert resolution.model_dump(mode="json")["binding_values"] == {"modelo-303-iva-repercutido-general-cuota": "21.00"}
    assert resolution.model_dump(mode="json")["date_binding_values"] == {"profile-birth-date": "1980-01-31"}
    assert resolution.model_dump(mode="json")["row_binding_values"] == [
        {
            "binding_id": "modelo-720-asset-row-valuation",
            "row_index": 2,
            "value": "60000.00",
            "value_kind": "decimal",
        },
    ]
    assert resolution.model_dump(mode="json")["relation_values"] == {"modelo-180-rel-115-base-anual": "2128.75"}
    with pytest.raises(ValidationError, match="Extra inputs"):
        CalculationSourceResolution.model_validate({"resolver_id": "ledger-iva", "unexpected": True})


def test_source_resolution_row_binding_json_replay_restores_serialized_coordinates() -> None:
    resolution = CalculationSourceResolution(
        resolver_id="foreign-assets",
        owned_sources=(BindingSourceKind.FOREIGN_ASSET,),
        row_binding_values={
            ("modelo-720-asset-row-class", 2): "B",
            ("modelo-720-asset-row-identifier", 2): "000123",
            ("modelo-720-asset-row-valuation", 2): Decimal("60000.00"),
        },
    )

    raw = resolution.model_dump_json()
    replayed = CalculationSourceResolution.model_validate_json(raw)

    assert replayed.row_binding_values == {
        ("modelo-720-asset-row-class", 2): "B",
        ("modelo-720-asset-row-identifier", 2): "000123",
        ("modelo-720-asset-row-valuation", 2): Decimal("60000.00"),
    }
    assert replayed.model_dump_json() == raw


def test_source_resolution_rejects_serialized_row_binding_index_below_one() -> None:
    raw = (
        '{"resolver_id":"foreign-assets",'
        '"row_binding_values":[{"binding_id":"modelo-720-asset-row-class","row_index":0,"value":"B"}]}'
    )

    with pytest.raises(ValidationError) as exc_info:
        CalculationSourceResolution.model_validate_json(raw)

    context = exc_info.value.errors()[0].get("ctx")
    assert context is not None
    error = context["error"]
    assert isinstance(error, SourceMeshError)
    assert str(error) == "aggregation.source_mesh.errors.row_binding_index_invalid"


def test_source_resolution_rejects_invalid_serialized_decimal_row_binding_value() -> None:
    raw = (
        '{"resolver_id":"foreign-assets",'
        '"row_binding_values":[{"binding_id":"modelo-720-asset-row-valuation",'
        '"row_index":1,"value":"not-decimal","value_kind":"decimal"}]}'
    )

    with pytest.raises(ValidationError) as exc_info:
        CalculationSourceResolution.model_validate_json(raw)

    context = exc_info.value.errors()[0].get("ctx")
    assert context is not None
    error = context["error"]
    assert isinstance(error, SourceMeshError)
    assert str(error) == "aggregation.source_mesh.errors.row_binding_value_invalid"


def test_source_diagnostic_keeps_advisory_category_separate_from_binding_source() -> None:
    diagnostic = CalculationSourceDiagnostic(
        reason="settlement_not_computed",
        source_kind="settlement_casilla",
        message="settlement casilla must be operator-verified",
    )

    assert diagnostic.source_kind == "settlement_casilla"
    assert diagnostic.binding_source is None


def test_source_diagnostic_asserted_legal_refs_is_distinct_from_casilla_derived_refs() -> None:
    """The advisory-asserted path coexists with, and is independent of, the casilla-derived one.

    The two default independently and neither field's presence implies or
    excludes the other -- an advisory may carry only casilla-derived refs, only
    asserted refs, both, or neither.
    """
    casilla_derived_only = CalculationSourceDiagnostic(
        reason="aggregation_activity_undeclared",
        source_kind="undeclared_activity_income",
        message="casilla-derived grounding only",
        legal_refs=("ley-35-2006:art-58",),
    )
    asserted_only = CalculationSourceDiagnostic(
        reason="source_issue",
        source_kind="eligibility_rule_advisory",
        message="advisory-asserted grounding only",
        asserted_legal_refs=("ley-35-2006:art-81-3",),
    )
    both = CalculationSourceDiagnostic(
        reason="source_issue",
        source_kind="eligibility_rule_advisory",
        message="both grounding paths at once",
        legal_refs=("ley-35-2006:art-58",),
        asserted_legal_refs=("ley-35-2006:art-81-3",),
    )

    assert casilla_derived_only.asserted_legal_refs == ()
    assert asserted_only.legal_refs == ()
    assert both.legal_refs == ("ley-35-2006:art-58",)
    assert both.asserted_legal_refs == ("ley-35-2006:art-81-3",)


def test_source_diagnostic_rejects_mismatched_binding_source_projection() -> None:
    with pytest.raises(ValidationError) as exc_info:
        CalculationSourceDiagnostic(
            reason="source_issue",
            source_kind="ledger_iva_aggregation",
            binding_source=BindingSourceKind.PROFILE,
            message="source kind and binding source disagree",
        )

    context = exc_info.value.errors()[0].get("ctx")
    assert context is not None
    error = context["error"]
    assert isinstance(error, SourceMeshError)
    assert str(error) == "aggregation.source_mesh.errors.binding_source_mismatch"


def test_out_of_window_summary_source_diagnostic_carries_count_and_date_span() -> None:
    diagnostic = out_of_window_summary_source_diagnostic(
        source_kind="ledger_renta_income_aggregation",
        resolver_id="ledger_renta_income_aggregation",
        count=27_516,
        min_filing_date=date(2021, 1, 1),
        max_filing_date=date(2030, 12, 31),
    )

    assert diagnostic.reason == "source_issue"
    assert diagnostic.out_of_window_count == 27_516
    assert diagnostic.out_of_window_min_filing_date == date(2021, 1, 1)
    assert diagnostic.out_of_window_max_filing_date == date(2030, 12, 31)
    assert "27516 ledger transaction(s)" in diagnostic.message
    assert "2021-01-01..2030-12-31" in diagnostic.message
    assert diagnostic.model_dump(mode="json")["out_of_window_min_filing_date"] == "2021-01-01"


def test_source_diagnostic_rejects_incomplete_out_of_window_summary() -> None:
    with pytest.raises(ValidationError) as exc_info:
        CalculationSourceDiagnostic(
            reason="source_issue",
            source_kind="ledger_renta_income_aggregation",
            message="period summary",
            out_of_window_count=2,
        )

    context = exc_info.value.errors()[0].get("ctx")
    assert context is not None
    error = context["error"]
    assert isinstance(error, SourceMeshError)
    assert str(error) == "aggregation.source_mesh.errors.out_of_window_summary_incomplete"


def test_source_diagnostic_rejects_reversed_out_of_window_summary_span() -> None:
    with pytest.raises(ValidationError) as exc_info:
        CalculationSourceDiagnostic(
            reason="source_issue",
            source_kind="ledger_renta_income_aggregation",
            message="period summary",
            out_of_window_count=2,
            out_of_window_min_filing_date=date(2024, 6, 1),
            out_of_window_max_filing_date=date(2024, 1, 1),
        )

    context = exc_info.value.errors()[0].get("ctx")
    assert context is not None
    error = context["error"]
    assert isinstance(error, SourceMeshError)
    assert str(error) == "aggregation.source_mesh.errors.out_of_window_summary_date_span_invalid"


def test_source_provenance_projects_canonical_binding_source() -> None:
    provenance = CalculationSourceProvenance(
        resolver_id="relation_prefill",
        resolved_binding_source=BindingSourceKind.RELATION_PREFILL,
        contributor_source_kind=BindingSourceKind.RELATION_PREFILL.value,
        contributor_binding_source=BindingSourceKind.RELATION_PREFILL,
        lineage_role=CalculationSourceLineageRole.PRIMARY,
        source_ref="relation:modelo-100-rel-130",
        parent_source_ref=None,
        relation_id="modelo-100-rel-130-pagos-fraccionados",
        source_modelo="130",
        source_filing_year=2026,
        source_periods=("1T",),
        source_casilla_ids=("19",),
        legal_refs=("rd-439-2007:art-110",),
        source_refs=("aeat-modelo-130-instructions",),
    )

    assert provenance.contributor_source_kind == BindingSourceKind.RELATION_PREFILL.value
    assert provenance.resolved_binding_source is BindingSourceKind.RELATION_PREFILL
    assert provenance.model_dump(mode="json")["resolved_binding_source"] == BindingSourceKind.RELATION_PREFILL.value
    assert provenance.model_dump(mode="json")["source_casilla_ids"] == ["19"]


def test_source_provenance_requires_resolver_identity_and_resolution_refuses_mismatch() -> None:
    with pytest.raises(ValidationError):
        CalculationSourceProvenance.model_validate(
            {
                "resolved_binding_source": BindingSourceKind.COLLECTIBLE_INVOICE,
                "contributor_source_kind": "collectible_invoice",
                "contributor_binding_source": BindingSourceKind.COLLECTIBLE_INVOICE,
                "lineage_role": CalculationSourceLineageRole.PRIMARY,
                "source_ref": "collectible_invoice:inv-0001",
                "parent_source_ref": None,
            },
        )

    provenance = CalculationSourceProvenance(
        resolver_id="invoice_catalogue",
        resolved_binding_source=BindingSourceKind.COLLECTIBLE_INVOICE,
        contributor_source_kind="collectible_invoice",
        contributor_binding_source=BindingSourceKind.COLLECTIBLE_INVOICE,
        lineage_role=CalculationSourceLineageRole.PRIMARY,
        source_ref="collectible_invoice:inv-0001",
        parent_source_ref=None,
    )
    with pytest.raises(ValidationError) as exc_info:
        CalculationSourceResolution(
            resolver_id="wrong-resolver",
            owned_sources=(BindingSourceKind.COLLECTIBLE_INVOICE,),
            provenance=(provenance,),
        )
    assert "provenance_resolver_mismatch" in str(exc_info.value)


def test_source_provenance_refuses_binding_source_contradictions_and_marks_non_binding_rows() -> None:
    with pytest.raises(ValidationError, match="provenance_binding_source_mismatch"):
        CalculationSourceProvenance(
            resolver_id="invoice_catalogue",
            resolved_binding_source=BindingSourceKind.COLLECTIBLE_INVOICE,
            contributor_source_kind=BindingSourceKind.PAYABLE_INVOICE.value,
            contributor_binding_source=BindingSourceKind.COLLECTIBLE_INVOICE,
            lineage_role=CalculationSourceLineageRole.PRIMARY,
            source_ref="payable_invoice:inv-0001",
            parent_source_ref=None,
        )
    with pytest.raises(ValidationError, match="provenance_binding_source_missing"):
        CalculationSourceProvenance(
            resolver_id="invoice_catalogue",
            resolved_binding_source=BindingSourceKind.COLLECTIBLE_INVOICE,
            contributor_source_kind=BindingSourceKind.COLLECTIBLE_INVOICE.value,
            contributor_binding_source=None,
            lineage_role=CalculationSourceLineageRole.PRIMARY,
            source_ref="collectible_invoice:inv-0001",
            parent_source_ref=None,
        )

    non_binding = CalculationSourceProvenance(
        resolver_id="iva_wallet_decision",
        resolved_binding_source=BindingSourceKind.IVA_WALLET_DECISION,
        contributor_source_kind="filed-revision-authority",
        contributor_binding_source=None,
        lineage_role=CalculationSourceLineageRole.CONTRIBUTOR,
        source_ref="revision:abc",
        parent_source_ref="iva-wallet-decision:event-1",
    )
    assert non_binding.contributor_binding_source is None


def test_source_resolution_refuses_orphan_and_ambiguous_lineage_edges() -> None:
    primary = CalculationSourceProvenance(
        resolver_id="iva_wallet_decision",
        resolved_binding_source=BindingSourceKind.IVA_WALLET_DECISION,
        contributor_source_kind=BindingSourceKind.IVA_WALLET_DECISION.value,
        contributor_binding_source=BindingSourceKind.IVA_WALLET_DECISION,
        lineage_role=CalculationSourceLineageRole.PRIMARY,
        source_ref="iva-wallet-decision:event-1",
        parent_source_ref=None,
    )
    contributor = CalculationSourceProvenance(
        resolver_id="iva_wallet_decision",
        resolved_binding_source=BindingSourceKind.IVA_WALLET_DECISION,
        contributor_source_kind="aeat_wallet",
        contributor_binding_source=None,
        lineage_role=CalculationSourceLineageRole.CONTRIBUTOR,
        source_ref="https://sede.agenciatributaria.gob.es/wallet",
        parent_source_ref=primary.source_ref,
    )
    valid = CalculationSourceResolution(
        resolver_id="iva_wallet_decision",
        owned_sources=(BindingSourceKind.IVA_WALLET_DECISION,),
        provenance=(primary, contributor),
    )
    assert valid.provenance == (primary, contributor)

    with pytest.raises(ValidationError, match="provenance_contributor_parent_missing"):
        CalculationSourceResolution(
            resolver_id="iva_wallet_decision",
            owned_sources=(BindingSourceKind.IVA_WALLET_DECISION,),
            provenance=(contributor.model_copy(update={"parent_source_ref": "missing-primary"}),),
        )
    with pytest.raises(ValidationError, match="provenance_primary_ref_ambiguous"):
        CalculationSourceResolution(
            resolver_id="iva_wallet_decision",
            owned_sources=(BindingSourceKind.IVA_WALLET_DECISION,),
            provenance=(primary, primary),
        )


def test_reserved_composite_owner_ids_require_the_closed_typed_identity() -> None:
    with pytest.raises(ValidationError, match="reserved_composite_resolver_id"):
        CalculationSourceResolution(resolver_id="source_mesh")
    merged = merge_source_resolutions(())
    assert merged.resolver_id is CompositeSourceResolverId.EXCLUSIVE_MESH


def test_relation_source_provenance_rejects_incomplete_typed_trace() -> None:
    with pytest.raises(ValidationError) as exc_info:
        CalculationSourceProvenance(
            resolver_id="relation_prefill",
            resolved_binding_source=BindingSourceKind.RELATION_PREFILL,
            contributor_source_kind=BindingSourceKind.RELATION_PREFILL.value,
            contributor_binding_source=BindingSourceKind.RELATION_PREFILL,
            lineage_role=CalculationSourceLineageRole.PRIMARY,
            source_ref="relation:modelo-100-rel-130",
            parent_source_ref=None,
            relation_id="modelo-100-rel-130-pagos-fraccionados",
        )

    context = exc_info.value.errors()[0].get("ctx")
    assert context is not None
    error = context["error"]
    assert isinstance(error, SourceMeshError)
    assert str(error) == "aggregation.source_mesh.errors.relation_provenance_incomplete"


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


def test_source_resolution_validator_errors_are_localized() -> None:
    cases: tuple[tuple[dict[str, object], str], ...] = (
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
    )

    for payload, message_key in cases:
        with pytest.raises(ValidationError) as exc_info:
            CalculationSourceResolution.model_validate(payload)

        context = exc_info.value.errors()[0].get("ctx")
        assert context is not None, message_key
        error = context["error"]
        assert isinstance(error, SourceMeshError), message_key
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
        owned_sources=(BindingSourceKind.LEDGER_IVA_AGGREGATION,),
        binding_values={"modelo-303-iva-repercutido-general-cuota": Decimal("21.00")},
    )
    right = CalculationSourceResolution(
        resolver_id="manual-bridge",
        owned_sources=(BindingSourceKind.MANUAL_INPUT,),
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
        owned_sources=(BindingSourceKind.LEDGER_IVA_AGGREGATION,),
        bound_inputs_by_casilla_id={_IVA_REPERCUTIDO_GENERAL_CASILLA: Decimal("21.00")},
    )
    right = CalculationSourceResolution(
        resolver_id="invoice",
        owned_sources=(BindingSourceKind.PAYABLE_INVOICE,),
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
        owned_sources=(BindingSourceKind.RELATION_PREFILL,),
        relation_values={"modelo-180-rel-115-base-anual": Decimal("2128.75")},
    )
    right = CalculationSourceResolution(
        resolver_id="aeat-live",
        owned_sources=(BindingSourceKind.PREVIOUS_FILING,),
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


def test_source_resolution_merge_rejects_duplicate_row_binding_ownership() -> None:
    left = CalculationSourceResolution(
        resolver_id="foreign-assets",
        owned_sources=(BindingSourceKind.FOREIGN_ASSET,),
        row_binding_values={("modelo-720-asset-row-class", 1): "B"},
    )
    right = CalculationSourceResolution(
        resolver_id="manual-bridge",
        owned_sources=(BindingSourceKind.MANUAL_INPUT,),
        row_binding_values={("modelo-720-asset-row-class", 1): "I"},
    )

    with pytest.raises(AggregationValidationError) as exc_info:
        merge_source_resolutions((left, right))

    assert str(exc_info.value) == "aggregation.source_mesh.errors.duplicate_row_binding_owner"
    context = exc_info.value.context
    assert context is not None
    assert context["binding_id"] == "modelo-720-asset-row-class"
    assert context["row_index"] == 1
    assert context["first_resolver"] == "foreign-assets"
    assert context["second_resolver"] == "manual-bridge"


def test_source_resolution_merge_rejects_duplicate_binding_across_value_channels() -> None:
    left = CalculationSourceResolution(
        resolver_id="profile",
        owned_sources=(BindingSourceKind.PROFILE,),
        date_binding_values={"profile-birth-date": date(1980, 1, 31)},
    )
    right = CalculationSourceResolution(
        resolver_id="manual-bridge",
        owned_sources=(BindingSourceKind.MANUAL_INPUT,),
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
        resolver_id="ledger-iva",
        resolved_binding_source=BindingSourceKind.LEDGER_IVA_AGGREGATION,
        contributor_source_kind="ledger_iva_aggregation",
        contributor_binding_source=BindingSourceKind.LEDGER_IVA_AGGREGATION,
        lineage_role=CalculationSourceLineageRole.PRIMARY,
        source_ref="transaction:tx-1",
        parent_source_ref=None,
        fingerprint="sha256:abc",
    )

    binding_input = Decimal("21.07")
    relation_input = Decimal("38.49")
    ledger_resolution = CalculationSourceResolution(
        resolver_id="ledger-iva",
        owned_sources=(BindingSourceKind.LEDGER_IVA_AGGREGATION,),
        binding_values={"binding-decimal": binding_input},
        row_binding_values={("modelo-720-asset-row-valuation", 1): Decimal("60000.00")},
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
                owned_sources=(BindingSourceKind.PROFILE,),
                enum_binding_values={"profile-ccaa": "madrid"},
                diagnostics=(diagnostic,),
            ),
        ),
    )

    assert merged.resolver_id == "source_mesh"
    assert merged.owned_sources == (BindingSourceKind.LEDGER_IVA_AGGREGATION, BindingSourceKind.PROFILE)
    assert merged.binding_values["binding-decimal"] == ledger_resolution.binding_values["binding-decimal"]
    assert merged.row_binding_values[("modelo-720-asset-row-valuation", 1)] == Decimal("60000.00")
    assert merged.relation_values["relation-decimal"] == ledger_resolution.relation_values["relation-decimal"]
    assert merged.date_binding_values["profile-birth-date"] == date(1980, 1, 31)
    assert merged.enum_binding_values["profile-ccaa"] == "madrid"
    assert tuple(merged.source_transaction_ids) == ("tx-1",)
    assert merged.diagnostics == (diagnostic,)
    assert merged.provenance == (provenance,)


def test_unhandled_source_diagnostics_name_modelo_binding_and_source_kind() -> None:
    modelo_303 = resources().modelos.get("303")
    revision = modelo_303.revisions["2022"]

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

    with caplog.at_level("DEBUG", logger="cadrumo.application.aggregation._source_mesh"):
        resolution = storage_degradation_resolution(
            resolver_id="ledger-iva",
            owned_sources=(BindingSourceKind.LEDGER_IVA_AGGREGATION,),
            source_kinds=(BindingSourceKind.LEDGER_IVA_AGGREGATION,),
            error=error,
        )

    assert resolution.binding_values == {}
    assert resolution.diagnostics[0].reason == "storage_degraded"
    assert resolution.diagnostics[0].source_kind == "ledger_iva_aggregation"
    assert resolution.diagnostics[0].message
    assert any("source mesh resolver storage degradation" in record.message for record in caplog.records)
