"""Drift-sensitive coverage for the modelo precondition migration."""

from __future__ import annotations

import ast
import re
import tomllib
from pathlib import Path

import pytest

from cadrumo.application.modelo._preconditions import MODELO_PRECONDITION_PROFILES
from cadrumo.application.operator_actions.catalogue import OPERATOR_ACTION_CATALOGUE
from cadrumo.application.operator_surface.manifest import (
    InputSchemaInventoryRow,
    LiveLeafInventoryRow,
    OperatorSurfaceReconciliation,
    ReconciledOperatorLeaf,
    ResultSchemaInventoryRow,
    resolve_manifest_action_profiles,
)
from cadrumo.core.directory_scan import scan_directory
from cadrumo.core.i18n import extract_placeholders, lookup_translation_entry
from cadrumo.entrypoints.cli import command_schema_refs
from cadrumo.entrypoints.cli._verb_input_schema import build_verb_input_schemas

from .._paths import REPO_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_ROOT = REPO_ROOT
_MODELO_PATH_PREFIX = "src/cadrumo/application/modelo/"
_REQUIRED_PRODUCTION_FINDING_MODULES = {
    "src/cadrumo/application/calculations/_foreign_asset_redeclaration.py",
    "src/cadrumo/application/modelo/_art20_advisory.py",
    "src/cadrumo/application/modelo/_art52_advisory.py",
    "src/cadrumo/application/modelo/_attribution_received_advisory.py",
    "src/cadrumo/application/modelo/_autonomic_deduccion_advisory.py",
    "src/cadrumo/application/modelo/_dt12_advisory.py",
    "src/cadrumo/application/modelo/_dt12_antiquity_advisory.py",
    "src/cadrumo/application/modelo/_ledger_drift_gate.py",
    "src/cadrumo/application/modelo/_m210_agrupacion_renta.py",
    "src/cadrumo/application/modelo/_m210_convenio_lob_advisory.py",
    "src/cadrumo/application/modelo/_m210_rate.py",
    "src/cadrumo/application/modelo/_m303_m349_reconcile.py",
    "src/cadrumo/application/modelo/_objective_estimation_advisory.py",
    "src/cadrumo/application/modelo/_pulled_filing_reconcile.py",
    "src/cadrumo/application/modelo/_verification_actions.py",
    "src/cadrumo/application/modelo/_verification_cross_period.py",
    "src/cadrumo/application/modelo/_verification_predicates.py",
}

_INTENTIONAL_RECORD_LEVEL_FINDING_OWNERS = {
    (
        "src/cadrumo/application/modelo/_ledger_drift_gate.py",
        "_drift_finding",
    ): "ledger snapshot drift covers the contributing ledger as a whole",
    (
        "src/cadrumo/application/modelo/_m210_agrupacion_renta.py",
        "m210_agrupacion_renta_verification_findings",
    ): "annual grouped-renta integrity belongs to the detail-row set",
    (
        "src/cadrumo/application/modelo/_verification_actions.py",
        "_resolve_verification_snapshot",
    ): "an unresolved registry snapshot blocks the whole revision, so no single casilla owns it",
    (
        "src/cadrumo/application/modelo/_m303_m349_reconcile.py",
        "m303_m349_intracom_reconcile_findings",
    ): "the reconciliation compares several casillas across two modelos",
    (
        "src/cadrumo/application/modelo/_objective_estimation_advisory.py",
        "_objective_estimation_exclusion_advisory_findings",
    ): "the advisory compares profile facts with legal thresholds",
    (
        "src/cadrumo/application/modelo/_verification_actions.py",
        "_cuota_less_without_base_findings",
    ): "the finding identifies a contributing transaction row without one canonical target casilla",
    (
        "src/cadrumo/application/modelo/_verification_actions.py",
        "_missing_evidence_findings",
    ): "the evidence gap is transaction-grain and its diagnostic has no target casilla identity",
    (
        "src/cadrumo/application/modelo/_verification_actions.py",
        "_unrouted_oss_source_finding",
    ): "an unrouted OSS source reaches no binding or target casilla",
    (
        "src/cadrumo/application/modelo/_verification_actions.py",
        "_missing_oss_evidence_finding",
    ): "missing OSS evidence spans the revision's OSS bindings rather than one target",
    (
        "src/cadrumo/application/modelo/_verification_cross_period.py",
        "_modelo_202_incomplete_modality_finding",
    ): "Modelo 202 modality is a profile-derived filing-level decision",
    (
        "src/cadrumo/application/modelo/_verification_cross_period.py",
        "_cross_period_clean_state_findings",
    ): "dependency evidence names upstream casillas and target origins, not one canonical target row",
    (
        "src/cadrumo/application/modelo/_verification_cross_period.py",
        "_cross_period_operator_declared_suppression_advisory_finding",
    ): "the advisory concerns operator-declared activity-start provenance",
    (
        "src/cadrumo/application/modelo/_verification_cross_period.py",
        "_cross_period_first_year_fractional_suppression_advisory_finding",
    ): "the advisory concerns first-year filing obligation and modality",
    (
        "src/cadrumo/application/modelo/_verification_cross_period.py",
        "_cross_period_missing_activity_start_finding",
    ): "the blocker concerns an absent profile fact at work-record grain",
    (
        "src/cadrumo/application/modelo/_verification_cross_period.py",
        "_cross_period_modelo_not_applicable_advisory_finding",
    ): "the advisory summarizes one or more inapplicable source modelos",
    (
        "src/cadrumo/application/modelo/_verification_cross_period.py",
        "_cross_period_zero_value_previous_filing_advisory_finding",
    ): "zero-value suppression is dependency evidence without one guaranteed target casilla",
    (
        "src/cadrumo/application/modelo/_verification_cross_period.py",
        "_cross_period_m111_no_retenciones_advisory_finding",
    ): "the advisory concerns profile-backed no-obligation evidence for a source period",
    (
        "src/cadrumo/application/modelo/_verification_cross_period.py",
        "_cross_period_non_official_local_chain_advisory_finding",
    ): "the advisory concerns provenance of an admitted local filing chain",
}

_ACTIVE_GROUPS = {
    ("borrador_binding.py", "resolve_modelo_100_borrador_bindings"),
    ("_calculation_actions.py", "_reject_caller_overrides_of_source_bindings"),
    ("_calculation_actions.py", "_refuse_direct_cross_period_verification"),
    (
        "_calculation_modelo_adjustments.py",
        "_raise_if_m390_303_reconciliation_would_save_silent_zero",
    ),
    ("_calculation_preparation.py", "_raise_if_ledger_preflight_blocks_calculation"),
    ("_calculation_preparation.py", "_raise_if_m200_ledger_requires_accounting_result_input"),
    ("_m349_ledger_guard.py", "raise_if_m349_intracom_ledger_rows_need_operator_rows"),
    ("_required_binding_gate.py", "_raise_required_bindings_missing"),
    ("_filing_actions.py", "_require_filing_preconditions"),
    ("_ledger_evidence_gate.py", "raise_if_deductible_iva_evidence_missing"),
}

_IVA_WALLET_GROUPS = {
    ("_iva_wallet_gate.py", "apply_iva_compensation_decision_binding"),
    ("_iva_wallet_gate.py", "iva_wallet_override_suggestion"),
    ("_iva_wallet_gate.py", "require_persisted_iva_compensation_decision_for_work_unit"),
    ("_iva_wallet_gate.py", "require_persisted_iva_compensation_decision_matches_revision"),
}

_RETIRED_VERIFICATION_GROUPS = {
    ("_art20_advisory.py", "_art20_reduccion_advisory_finding"),
    ("_art52_advisory.py", "_art52_reduccion_advisory_finding"),
    ("_attribution_received_advisory.py", "_attribution_received_omission_advisory_findings"),
    ("_autonomic_deduccion_advisory.py", "_madrid_nacimiento_adopcion_eligibility_advisory_finding"),
    ("_dt12_advisory.py", "_dt12_reduccion_advisory_finding"),
    ("_dt12_antiquity_advisory.py", "_dt12_antiquity_advisory_finding"),
    ("_ledger_drift_gate.py", "_drift_finding"),
    ("_m210_agrupacion_renta.py", "m210_agrupacion_renta_verification_findings"),
    ("_m210_convenio_lob_advisory.py", "_m210_convenio_lob_advisory_finding"),
    ("_m210_rate.py", "_m210_blocking_finding"),
    ("_m210_rate.py", "_resolve_convenio_override"),
    ("_m210_rate.py", "resolve_m210_rate"),
    ("_m303_m349_reconcile.py", "m303_m349_intracom_reconcile_findings"),
    ("_objective_estimation_advisory.py", "_objective_estimation_exclusion_advisory_findings"),
    ("_verification_actions.py", "_cuota_less_without_base_findings"),
    ("_verification_actions.py", "_iva_wallet_error_verification_finding"),
    ("_verification_actions.py", "_missing_evidence_findings"),
    ("_verification_actions.py", "_missing_oss_evidence_finding"),
    ("_verification_actions.py", "_missing_required_casilla_finding"),
    ("_verification_actions.py", "_unrouted_oss_source_finding"),
    ("_verification_cross_period.py", "_cross_period_clean_state_findings"),
    ("_verification_cross_period.py", "_cross_period_clean_state_next_action"),
    ("_verification_cross_period.py", "_cross_period_first_year_fractional_suppression_advisory_finding"),
    ("_verification_cross_period.py", "_cross_period_m111_no_retenciones_advisory_finding"),
    ("_verification_cross_period.py", "_cross_period_missing_activity_start_finding"),
    ("_verification_cross_period.py", "_cross_period_modelo_not_applicable_advisory_finding"),
    ("_verification_cross_period.py", "_cross_period_non_official_local_chain_advisory_finding"),
    ("_verification_cross_period.py", "_cross_period_operator_declared_suppression_advisory_finding"),
    ("_verification_cross_period.py", "_cross_period_zero_value_previous_filing_advisory_finding"),
    ("_verification_cross_period.py", "_modelo_202_incomplete_modality_finding"),
    ("_verification_cross_period.py", "_raise_if_modelo_202_modality_incomplete"),
    ("_verification_cross_period.py", "_require_cross_period_clean_state"),
    ("_verification_predicates.py", "_evaluate_verification_predicates"),
}

_IVA_WALLET_BLOCKED_DECISION_SCENARIOS = (
    "filed_history_requires_override",
    "local_evidence_unreadable",
    "local_recurrence_requires_override",
    "no_usable_authority",
    "stale_wallet_local_recurrence_requires_override",
    "stale_wallet_no_local_recurrence",
    "wallet_local_recurrence_divergence",
)

_EXPECTED_PROFILE_IDENTITIES = {
    (
        "modelo.work.calculate",
        "modelo.work.calculate.m303_profile_readiness.ready",
        "modelo.work.calculate.m303_profile_readiness.iva_composition_missing",
    ),
    (
        "modelo.work.calculate",
        "modelo.work.calculate.m303_profile_readiness.ready",
        "modelo.work.calculate.m303_profile_readiness.iva_composition_unknown",
    ),
    (
        "modelo.work.calculate",
        "modelo.work.calculate.m303_profile_readiness.ready",
        "modelo.work.calculate.m303_profile_readiness.profile_absent",
    ),
    (
        "modelo.work.calculate",
        "modelo.work.calculate.m303_profile_readiness.ready",
        "modelo.work.calculate.m303_profile_readiness.profile_inactive",
    ),
    (
        "modelo.work.calculate",
        "modelo.work.calculate.m303_filing_evidence.valid",
        "modelo.work.calculate.m303_filing_evidence.exonerado_390_endpoint_coverage_incomplete",
    ),
    (
        "modelo.work.calculate",
        "modelo.work.calculate.m303_filing_evidence.valid",
        "modelo.work.calculate.m303_filing_evidence.exonerado_390_endpoints_on_non_applicable",
    ),
    (
        "modelo.work.calculate",
        "modelo.work.calculate.m303_filing_evidence.valid",
        "modelo.work.calculate.m303_filing_evidence.exonerado_390_not_final_period",
    ),
    (
        "modelo.work.calculate",
        "modelo.work.calculate.m303_filing_evidence.valid",
        "modelo.work.calculate.m303_filing_evidence.exonerado_390_observation_value_divergence",
    ),
    (
        "modelo.work.calculate",
        "modelo.work.calculate.m303_filing_evidence.valid",
        "modelo.work.calculate.m303_filing_evidence.exonerado_390_revision_value_divergence",
    ),
    (
        "modelo.work.calculate",
        "modelo.work.calculate.m303_filing_evidence.valid",
        "modelo.work.calculate.m303_filing_evidence.missing",
    ),
    (
        "modelo.work.calculate",
        "modelo.work.calculate.m303_filing_evidence.valid",
        "modelo.work.calculate.m303_filing_evidence.period_mismatch",
    ),
    (
        "modelo.work.calculate",
        "modelo.work.calculate.m303_filing_evidence.valid",
        "modelo.work.calculate.m303_filing_evidence.regimen_scope_profile_divergence",
    ),
    (
        "modelo.work.calculate",
        "modelo.work.calculate.m303_filing_evidence.valid",
        "modelo.work.calculate.m303_filing_evidence.regimen_snapshot_mismatch",
    ),
    (
        "modelo.work.calculate",
        "modelo.work.calculate.m303_filing_evidence.valid",
        "modelo.work.calculate.m303_filing_evidence.unsupported_modelo",
    ),
    (
        "modelo.filing_record.import",
        "modelo.filing_record.import.lifecycle.active",
        "modelo.filing_record.import.lifecycle.discarded",
    ),
    (
        "modelo.work.calculate",
        "modelo.work.calculate.lifecycle.active",
        "modelo.work.calculate.lifecycle.discarded",
    ),
    (
        "modelo.work.create",
        "modelo.work.create.lifecycle.target_available",
        "modelo.work.create.lifecycle.target_discarded",
    ),
    (
        "modelo.work.create",
        "modelo.work.create.period.filing_year.matches",
        "modelo.work.create.period.filing_year.mismatch",
    ),
    (
        "modelo.work.discard",
        "modelo.work.discard.lifecycle.not_already_discarded",
        "modelo.work.discard.lifecycle.already_discarded",
    ),
    (
        "modelo.work.rename",
        "modelo.work.rename.lifecycle.mutable",
        "modelo.work.rename.lifecycle.discarded",
    ),
    (
        "modelo.work.calculate",
        "modelo.work.calculate.borrador_snapshot.active",
        "modelo.work.calculate.borrador_snapshot.load_failed",
    ),
    (
        "modelo.work.calculate",
        "modelo.work.calculate.borrador_snapshot.active",
        "modelo.work.calculate.borrador_snapshot.inactive",
    ),
    (
        "modelo.work.calculate",
        "modelo.work.calculate.source_inputs.unowned",
        "modelo.work.calculate.source_inputs.binding_override_rejected",
    ),
    (
        "modelo.work.calculate",
        "modelo.work.calculate.source_inputs.unowned",
        "modelo.work.calculate.source_inputs.casilla_override_rejected",
    ),
    (
        "modelo.work.verify",
        "modelo.work.verify.lifecycle_path.required",
        "modelo.work.verify.lifecycle_path.direct_cross_period_promotion_refused",
    ),
    (
        "modelo.work.verify",
        "modelo.work.verify.work_address.resolved",
        "modelo.work.verify.work_address.exact_work_unit_absent",
    ),
    (
        "modelo.work.verify",
        "modelo.work.verify.work_address.resolved",
        "modelo.work.verify.work_address.natural_target_absent",
    ),
    (
        "modelo.work.file",
        "modelo.work.file.work_address.resolved",
        "modelo.work.file.work_address.exact_work_unit_absent",
    ),
    (
        "modelo.work.file",
        "modelo.work.file.work_address.resolved",
        "modelo.work.file.work_address.natural_target_absent",
    ),
    (
        "modelo.work.verify",
        "modelo.work.verify.calculation_revision.addresses_calculation",
        "modelo.work.verify.calculation_revision.work_unit_target",
    ),
    (
        "modelo.work.verify",
        "modelo.work.verify.calculation_revision.addresses_calculation",
        "modelo.work.verify.calculation_revision.work_unit_target_discarded",
    ),
    (
        "modelo.work.file",
        "modelo.work.file.calculation_revision.addresses_calculation",
        "modelo.work.file.calculation_revision.work_unit_target",
    ),
    (
        "modelo.work.file",
        "modelo.work.file.calculation_revision.addresses_calculation",
        "modelo.work.file.calculation_revision.work_unit_target_discarded",
    ),
    (
        "modelo.work.calculate",
        "modelo.work.calculate.m390.reconciliation.complete",
        "modelo.work.calculate.m390.reconciliation.clean_m303_observations_missing",
    ),
    (
        "modelo.work.calculate",
        "modelo.work.calculate.ledger_preflight.ready",
        "modelo.work.calculate.ledger_preflight.blocked",
    ),
    (
        "modelo.work.calculate",
        "modelo.work.calculate.m200.accounting_result.present",
        "modelo.work.calculate.m200.accounting_result.ledger_rows_without_accounting_result",
    ),
    (
        "modelo.work.calculate",
        "modelo.work.calculate.m349.operator_rows.present",
        "modelo.work.calculate.m349.operator_rows.intracom_ledger_without_operator_rows",
    ),
    (
        "modelo.work.calculate",
        "modelo.work.required_bindings.resolved",
        "modelo.work.calculate.required_bindings_missing",
    ),
    ("modelo.work.verify", "modelo.work.required_bindings.resolved", "modelo.work.verify.required_bindings_missing"),
    ("modelo.work.file", "modelo.work.required_bindings.resolved", "modelo.work.file.required_bindings_missing"),
    (
        "modelo.work.file",
        "modelo.work.file.deductible_iva_evidence.present",
        "modelo.work.file.deductible_iva_evidence.missing",
    ),
    (
        "modelo.work.file",
        "modelo.work.file.calculation_revision.verified",
        "modelo.work.file.calculation_revision.unverified",
    ),
    (
        "modelo.work.verify",
        "modelo.work.verify.registry_snapshot.available",
        "modelo.work.verify.registry_snapshot.unavailable",
    ),
    (
        "modelo.work.verify",
        "modelo.work.verify.required_casillas.complete",
        "modelo.work.verify.required_casillas.missing",
    ),
    (
        "modelo.work.verify",
        "modelo.work.verify.registry_predicate.satisfied",
        "modelo.work.verify.registry_predicate.failed",
    ),
    (
        "modelo.work.verify",
        "modelo.work.verify.deductible_iva_evidence.present",
        "modelo.work.verify.deductible_iva_evidence.missing",
    ),
    (
        "modelo.work.verify",
        "modelo.work.verify.ledger_row.taxable_base_present",
        "modelo.work.verify.ledger_row.cuota_less_base_missing",
    ),
    ("modelo.work.verify", "modelo.work.verify.oss_source.routed", "modelo.work.verify.oss_source.unrouted"),
    ("modelo.work.verify", "modelo.work.verify.oss_evidence.present", "modelo.work.verify.oss_evidence.missing"),
    (
        "modelo.work.verify",
        "modelo.work.verify.ledger_snapshot.current",
        "modelo.work.verify.ledger_snapshot.drift_detected",
    ),
    ("modelo.work.verify", "modelo.work.verify.m210.agrupacion.valid", "modelo.work.verify.m210.agrupacion.invalid"),
    ("modelo.work.verify", "modelo.work.verify.m210.rate.resolved", "modelo.work.verify.m210.rate.unresolved"),
    ("modelo.work.verify", "modelo.work.verify.m202.modality.complete", "modelo.work.verify.m202.modality.incomplete"),
    (
        "modelo.work.verify",
        "modelo.work.verify.cross_period_dependency.clean",
        "modelo.work.verify.cross_period_dependency.unclean",
    ),
    (
        "modelo.work.verify",
        "modelo.work.verify.activity_start_date.present",
        "modelo.work.verify.activity_start_date.missing_for_first_filer_adjudication",
    ),
    (
        "modelo.work.file",
        "modelo.work.file.m202.modality.complete",
        "modelo.work.file.m202.modality.incomplete",
    ),
    (
        "modelo.work.file",
        "modelo.work.file.cross_period_dependency.clean",
        "modelo.work.file.cross_period_dependency.unclean",
    ),
    (
        "modelo.work.file",
        "modelo.work.file.activity_start_date.present",
        "modelo.work.file.activity_start_date.missing_for_first_filer_adjudication",
    ),
    *{
        (
            "modelo.work.calculate",
            "modelo.work.calculate.iva_wallet.ready",
            f"modelo.work.calculate.iva_wallet.{scenario_code}",
        )
        for scenario_code in (
            "backend_casilla_conflict",
            *_IVA_WALLET_BLOCKED_DECISION_SCENARIOS,
            "caller_binding_conflict",
            "caller_casilla_conflict",
            "first_period_zero_ungrounded",
            "not_seeded",
            "registry_snapshot_unavailable",
            "selected_amount_missing",
            "supplied_decision_mismatch",
            "target_mismatch",
            "taxpayer_identity_missing",
            "taxpayer_mismatch",
            "unsupported_decision_type",
        )
    },
    *{
        (
            leaf,
            f"{leaf}.iva_wallet.ready",
            f"{leaf}.iva_wallet.{scenario_code}",
        )
        for leaf in ("modelo.work.verify", "modelo.work.file")
        for scenario_code in (
            "amount_mismatch",
            *_IVA_WALLET_BLOCKED_DECISION_SCENARIOS,
            "first_period_zero_ungrounded",
            "not_seeded",
            "registry_snapshot_unavailable",
            "revision_amount_missing",
            "selected_amount_missing",
            "target_mismatch",
        )
    },
}

_RESERVED_PROFILE_IDENTITIES = {
    (
        "modelo.export",
        "modelo.export.deductible_iva_evidence.present",
        "modelo.export.deductible_iva_evidence.missing",
    ),
    *{
        (
            "modelo.export",
            "modelo.export.iva_wallet.ready",
            f"modelo.export.iva_wallet.{scenario_code}",
        )
        for scenario_code in (
            "amount_mismatch",
            *_IVA_WALLET_BLOCKED_DECISION_SCENARIOS,
            "first_period_zero_ungrounded",
            "not_seeded",
            "registry_snapshot_unavailable",
            "revision_amount_missing",
            "selected_amount_missing",
            "target_mismatch",
        )
    },
}


def _ledger_rows() -> list[dict[str, object]]:
    payload = tomllib.loads((_ROOT / "dev/quality/cli_action_census_dispositions.toml").read_text(encoding="utf-8"))
    rows = payload["disposition"]
    assert isinstance(rows, list)
    return [row for row in rows if str(row["path"]).startswith(_MODELO_PATH_PREFIX)]


def _group(row: dict[str, object]) -> tuple[str, str]:
    return (Path(str(row["path"])).name, str(row["enclosing_symbol"]))


def test_modelo_ledger_has_complete_s24_and_reserved_partition() -> None:
    rows = _ledger_rows()
    active = [row for row in rows if _group(row) in _ACTIVE_GROUPS]
    retired = [row for row in rows if _group(row) in _RETIRED_VERIFICATION_GROUPS]
    iva_wallet = [row for row in rows if _group(row) in _IVA_WALLET_GROUPS]
    s24_row_ids = {id(row) for row in (*active, *retired, *iva_wallet)}
    reserved = [row for row in rows if id(row) not in s24_row_ids]

    assert {_group(row) for row in active} == _ACTIVE_GROUPS
    assert {_group(row) for row in retired} == _RETIRED_VERIFICATION_GROUPS
    assert {_group(row) for row in iva_wallet} == _IVA_WALLET_GROUPS
    assert _ACTIVE_GROUPS.isdisjoint(_RETIRED_VERIFICATION_GROUPS | _IVA_WALLET_GROUPS)
    assert _RETIRED_VERIFICATION_GROUPS.isdisjoint(_IVA_WALLET_GROUPS)
    assert s24_row_ids.isdisjoint({id(row) for row in reserved})
    assert s24_row_ids | {id(row) for row in reserved} == {id(row) for row in rows}


def test_every_active_group_constructs_or_delegates_to_a_typed_failure() -> None:
    for filename, symbol in sorted(_ACTIVE_GROUPS):
        tree = ast.parse((_ROOT / _MODELO_PATH_PREFIX / filename).read_text(encoding="utf-8"))
        functions = [
            node
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == symbol
        ]
        assert len(functions) == 1, (filename, symbol)
        call_names = {
            node.func.id
            for node in ast.walk(functions[0])
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        assert call_names & {
            "build_modelo_precondition_failure",
            "raise_if_deductible_iva_evidence_missing",
        }, (filename, symbol)
        assert not any(
            isinstance(node, ast.keyword) and node.arg in {"next_action", "suggestion"}
            for node in ast.walk(functions[0])
        ), (filename, symbol)
        assert not any(
            isinstance(node, ast.Constant) and isinstance(node.value, str) and "aeat " in node.value.lower()
            for node in ast.walk(functions[0])
        ), (filename, symbol)

    iva_wallet_source = (_ROOT / _MODELO_PATH_PREFIX / "_iva_wallet_gate.py").read_text(encoding="utf-8")
    assert "suggestion=" not in iva_wallet_source
    assert "aeat app modelo iva-wallet" not in iva_wallet_source
    assert "_raise_iva_wallet_precondition" in iva_wallet_source


def test_retired_verification_groups_have_no_parallel_action_or_localization_authority() -> None:
    for filename, symbol in sorted(_RETIRED_VERIFICATION_GROUPS):
        tree = ast.parse((_ROOT / _MODELO_PATH_PREFIX / filename).read_text(encoding="utf-8"))
        functions = [
            node
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == symbol
        ]
        for function in functions:
            assert not any(
                isinstance(node, ast.keyword) and node.arg in {"next_action", "suggestion"}
                for node in ast.walk(function)
            ), (filename, symbol)
            assert not any(
                isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "tr"
                for node in ast.walk(function)
            ), (filename, symbol)
            assert not any(
                isinstance(node, ast.Constant) and isinstance(node.value, str) and "aeat " in node.value.lower()
                for node in ast.walk(function)
            ), (filename, symbol)


def test_modelo_application_production_has_no_presentation_localization() -> None:
    for path in scan_directory(_ROOT / _MODELO_PATH_PREFIX, pattern="*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "tr":
                pytest.fail(f"{path.name}:{node.lineno} localizes inside the application layer")


def test_profiles_are_exact_and_resolve_against_live_schemas() -> None:
    schema_refs = {row.command: row for row in command_schema_refs()}
    input_schemas = build_verb_input_schemas(tuple(sorted(schema_refs)))
    reconciliation = OperatorSurfaceReconciliation(
        leaves=tuple(
            ReconciledOperatorLeaf(
                live_leaf=LiveLeafInventoryRow(
                    subject_leaf_key=key,
                    canonical_cli_path=schema.resolved_leaf.cli_path,
                    alias_cli_paths=schema.resolved_leaf.alias_paths,
                    provenance="production CommandSpec operator path",
                ),
                result_schema=ResultSchemaInventoryRow(
                    subject_leaf_key=key,
                    schema_name=schema_refs[key].schema_name,
                    provenance="production CommandSpec result schema",
                ),
                input_schema=InputSchemaInventoryRow(
                    subject_leaf_key=key,
                    required_input_names=tuple(parameter.name for parameter in schema.required_inputs),
                    provenance="production CommandSpec input projection",
                ),
                mounted_family=None,
                profile_policy=None,
                surface_exposure=None,
                exclusions=(),
            )
            for key, schema in sorted(input_schemas.items())
        ),
    )

    resolution = resolve_manifest_action_profiles(
        profiles=MODELO_PRECONDITION_PROFILES,
        catalogue=OPERATOR_ACTION_CATALOGUE,
        reconciliation=reconciliation,
    )

    observed_identities = {row.declaration.identity for row in resolution.profiles}
    assert observed_identities == _EXPECTED_PROFILE_IDENTITIES | _RESERVED_PROFILE_IDENTITIES
    assert observed_identities - _EXPECTED_PROFILE_IDENTITIES == _RESERVED_PROFILE_IDENTITIES
    actionable = {row.declaration.action.action_id for row in resolution.profiles if row.declaration.action is not None}
    assert actionable == {
        "operator.modelo.bindings.list",
        "operator.modelo.work.calculate",
        "operator.modelo.work.verify",
        "operator.registry.verify",
    }
    for row in resolution.profiles:
        if row.declaration.action is None:
            assert row.resolved_action is None
        else:
            assert row.resolved_action is not None


def test_typed_record_builders_do_not_embed_presentation_or_infer_from_finding_text() -> None:
    record_paths = (
        _ROOT / _MODELO_PATH_PREFIX / "_preconditions.py",
        _ROOT / _MODELO_PATH_PREFIX / "_verification_preconditions.py",
    )
    forbidden_key = re.compile(r"(?:^|_)(?:command|help|hint|message|next|prose|suggestion|text)(?:_|$)")
    for path in record_paths:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr in {"message", "kind"}:
                pytest.fail(f"{path.name}:{node.lineno} infers a precondition from finding presentation")
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
                continue
            if node.func.id == "tr":
                pytest.fail(f"{path.name}:{node.lineno} localizes an application precondition record")
            if node.func.id != "build_modelo_precondition_failure":
                continue
            for keyword in node.keywords:
                assert keyword.arg is None or forbidden_key.search(keyword.arg) is None
            assert "aeat " not in ast.unparse(node).lower()


def test_every_production_verification_finding_constructor_is_locale_neutral() -> None:
    observed_modules: set[str] = set()
    for path in scan_directory(_ROOT / "src/cadrumo", pattern="*.py", recursive=True):
        if "tests" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and (
                (isinstance(node.func, ast.Name) and node.func.id == "ModeloVerificationFinding")
                or (isinstance(node.func, ast.Attribute) and node.func.attr == "ModeloVerificationFinding")
            )
        ]
        if not calls:
            continue
        relative = path.relative_to(_ROOT).as_posix()
        observed_modules.add(relative)
        for call in calls:
            keywords = {keyword.arg: keyword.value for keyword in call.keywords if keyword.arg is not None}
            assert "message" not in keywords, (relative, call.lineno)
            locale_key = keywords.get("message_locale_key")
            assert isinstance(locale_key, ast.Constant) and isinstance(locale_key.value, str), (
                relative,
                call.lineno,
            )
            assert re.fullmatch(r"[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+", locale_key.value), (
                relative,
                call.lineno,
            )
            for locale in ("en", "es", "ca", "hu"):
                present, translated = lookup_translation_entry(locale_key.value, locale=locale)
                assert present and translated, (relative, call.lineno, locale_key.value, locale)
                facts = keywords.get("message_facts")
                if isinstance(facts, ast.Dict) and all(
                    isinstance(key, ast.Constant) and isinstance(key.value, str)
                    for key in facts.keys
                    if key is not None
                ):
                    fact_keys = {
                        key.value for key in facts.keys if isinstance(key, ast.Constant) and isinstance(key.value, str)
                    }
                    assert extract_placeholders(translated) <= fact_keys, (
                        relative,
                        call.lineno,
                        locale_key.value,
                        locale,
                    )
            assert "message_facts" in keywords, (relative, call.lineno)
            assert not {"next_action", "suggestion"} & keywords.keys(), (relative, call.lineno)
            assert not any(
                isinstance(descendant, ast.Call)
                and isinstance(descendant.func, ast.Name)
                and descendant.func.id == "tr"
                for value in keywords.values()
                for descendant in ast.walk(value)
            ), (relative, call.lineno)
    assert observed_modules >= _REQUIRED_PRODUCTION_FINDING_MODULES


def test_intentional_record_level_finding_owners_are_reasoned_and_stale_failing() -> None:
    """Protect record-level attribution decisions without freezing a constructor tally."""
    constructors_by_owner: dict[tuple[str, str], list[ast.Call]] = {}
    for path in scan_directory(_ROOT / _MODELO_PATH_PREFIX, pattern="*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        parents = {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}
        relative = path.relative_to(_ROOT).as_posix()
        for node in ast.walk(tree):
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "ModeloVerificationFinding"
            ):
                continue
            enclosing_owner: ast.AST = node
            while enclosing_owner in parents and not isinstance(
                enclosing_owner, (ast.FunctionDef, ast.AsyncFunctionDef)
            ):
                enclosing_owner = parents[enclosing_owner]
            assert isinstance(enclosing_owner, (ast.FunctionDef, ast.AsyncFunctionDef)), (relative, node.lineno)
            constructors_by_owner.setdefault((relative, enclosing_owner.name), []).append(node)

    unexpected_omission_owners: set[tuple[str, str]] = set()
    for owner, constructors in constructors_by_owner.items():
        has_omission = any(not any(keyword.arg == "casilla_id" for keyword in call.keywords) for call in constructors)
        if has_omission and owner not in _INTENTIONAL_RECORD_LEVEL_FINDING_OWNERS:
            unexpected_omission_owners.add(owner)

    assert not unexpected_omission_owners, sorted(unexpected_omission_owners)
    for owner, reason in _INTENTIONAL_RECORD_LEVEL_FINDING_OWNERS.items():
        assert reason.strip(), owner
        constructors = constructors_by_owner.get(owner)
        assert constructors is not None, f"stale record-level owner: {owner}; reason={reason}"
        assert all(not any(keyword.arg == "casilla_id" for keyword in call.keywords) for call in constructors), (
            f"record-level owner gained casilla attribution: {owner}; reason={reason}"
        )
