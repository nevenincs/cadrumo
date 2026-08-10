"""Drift-sensitive coverage for the S24 modelo precondition migration."""

from __future__ import annotations

import ast
import re
import tomllib
from pathlib import Path

import pytest

from ....entrypoints.cli import command_schema_refs
from ....entrypoints.mcp import build_verb_input_schemas
from ...operator_actions import OPERATOR_ACTION_CATALOGUE
from ...operator_surface import resolve_manifest_action_profiles
from ...operator_surface._manifest import (
    InputSchemaInventoryRow,
    LiveLeafInventoryRow,
    OperatorSurfaceReconciliation,
    ReconciledOperatorLeaf,
    ResultSchemaInventoryRow,
)
from .._preconditions import MODELO_PRECONDITION_PROFILES

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_ROOT = Path(__file__).parents[5]
_MODELO_PATH_PREFIX = "src/cadrumo/application/modelo/"

_ACTIVE_GROUPS = {
    ("_borrador_binding.py", "resolve_modelo_100_borrador_bindings"),
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
    ("_ledger_evidence_gate.py", "raise_if_deductible_vat_evidence_missing"),
    ("_export.py", "export_modelo_revision"),
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
    ("_verification_actions.py", "_collect_revision_verification_findings"),
    ("_verification_actions.py", "_cuota_less_without_base_findings"),
    ("_verification_actions.py", "_iva_wallet_blocking_verification_finding"),
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

_EXPECTED_PROFILE_IDENTITIES = {
    ("modelo.work.calculate", "modelo.work.calculate.borrador_snapshot.active", "modelo.work.calculate.borrador_snapshot.load_failed"),
    ("modelo.work.calculate", "modelo.work.calculate.borrador_snapshot.active", "modelo.work.calculate.borrador_snapshot.inactive"),
    ("modelo.work.calculate", "modelo.work.calculate.source_inputs.unowned", "modelo.work.calculate.source_inputs.binding_override_rejected"),
    ("modelo.work.calculate", "modelo.work.calculate.source_inputs.unowned", "modelo.work.calculate.source_inputs.casilla_override_rejected"),
    ("modelo.work.verify", "modelo.work.verify.lifecycle_path.required", "modelo.work.verify.lifecycle_path.direct_cross_period_promotion_refused"),
    ("modelo.work.calculate", "modelo.work.calculate.m390.reconciliation.complete", "modelo.work.calculate.m390.reconciliation.clean_m303_observations_missing"),
    ("modelo.work.calculate", "modelo.work.calculate.ledger_preflight.ready", "modelo.work.calculate.ledger_preflight.blocked"),
    ("modelo.work.calculate", "modelo.work.calculate.m200.accounting_result.present", "modelo.work.calculate.m200.accounting_result.ledger_rows_without_accounting_result"),
    ("modelo.work.calculate", "modelo.work.calculate.m349.operator_rows.present", "modelo.work.calculate.m349.operator_rows.intracom_ledger_without_operator_rows"),
    ("modelo.work.calculate", "modelo.work.required_bindings.resolved", "modelo.work.calculate.required_bindings_missing"),
    ("modelo.work.verify", "modelo.work.required_bindings.resolved", "modelo.work.verify.required_bindings_missing"),
    ("modelo.work.file", "modelo.work.required_bindings.resolved", "modelo.work.file.required_bindings_missing"),
    ("modelo.work.file", "modelo.work.file.deductible_vat_evidence.present", "modelo.work.file.deductible_vat_evidence.missing"),
    ("modelo.work.verify", "modelo.work.verify.registry_snapshot.available", "modelo.work.verify.registry_snapshot.unavailable"),
    ("modelo.work.verify", "modelo.work.verify.required_casillas.complete", "modelo.work.verify.required_casillas.missing"),
    ("modelo.work.verify", "modelo.work.verify.registry_predicate.satisfied", "modelo.work.verify.registry_predicate.failed"),
    ("modelo.work.verify", "modelo.work.verify.deductible_vat_evidence.present", "modelo.work.verify.deductible_vat_evidence.missing"),
    ("modelo.work.verify", "modelo.work.verify.ledger_row.taxable_base_present", "modelo.work.verify.ledger_row.cuota_less_base_missing"),
    ("modelo.work.verify", "modelo.work.verify.oss_source.routed", "modelo.work.verify.oss_source.unrouted"),
    ("modelo.work.verify", "modelo.work.verify.oss_evidence.present", "modelo.work.verify.oss_evidence.missing"),
    ("modelo.work.verify", "modelo.work.verify.ledger_snapshot.current", "modelo.work.verify.ledger_snapshot.drift_detected"),
    ("modelo.work.verify", "modelo.work.verify.m210.agrupacion.valid", "modelo.work.verify.m210.agrupacion.invalid"),
    ("modelo.work.verify", "modelo.work.verify.m210.rate.resolved", "modelo.work.verify.m210.rate.unresolved"),
    ("modelo.work.verify", "modelo.work.verify.m202.modality.complete", "modelo.work.verify.m202.modality.incomplete"),
    ("modelo.work.verify", "modelo.work.verify.cross_period_dependency.clean", "modelo.work.verify.cross_period_dependency.unclean"),
    ("modelo.work.verify", "modelo.work.verify.activity_start_date.present", "modelo.work.verify.activity_start_date.missing_for_first_filer_adjudication"),
    (
        "modelo.export",
        "modelo.export.deductible_vat_evidence.present",
        "modelo.export.deductible_vat_evidence.missing",
    ),
}


def _ledger_rows() -> list[dict[str, object]]:
    payload = tomllib.loads((_ROOT / "dev/cli_action_census_dispositions.toml").read_text(encoding="utf-8"))
    rows = payload["disposition"]
    assert isinstance(rows, list)
    return [row for row in rows if str(row["path"]).startswith(_MODELO_PATH_PREFIX)]


def _group(row: dict[str, object]) -> tuple[str, str]:
    return (Path(str(row["path"])).name, str(row["enclosing_symbol"]))


def test_frozen_modelo_ledger_has_exact_s24_and_reserved_partition() -> None:
    rows = _ledger_rows()
    active = [row for row in rows if _group(row) in _ACTIVE_GROUPS]
    retired = [row for row in rows if _group(row) in _RETIRED_VERIFICATION_GROUPS]

    assert {_group(row) for row in active} == _ACTIVE_GROUPS
    assert {_group(row) for row in retired} == _RETIRED_VERIFICATION_GROUPS
    assert _ACTIVE_GROUPS.isdisjoint(_RETIRED_VERIFICATION_GROUPS)


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
            "raise_if_deductible_vat_evidence_missing",
        }, (filename, symbol)


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
                    provenance="materialized production Click tree",
                ),
                result_schema=ResultSchemaInventoryRow(
                    subject_leaf_key=key,
                    schema_name=schema_refs[key].schema_name,
                    provenance="production result-schema registry",
                ),
                input_schema=InputSchemaInventoryRow(
                    subject_leaf_key=key,
                    required_input_names=tuple(parameter.name for parameter in schema.required_inputs),
                    provenance="production Click input projection",
                ),
                mounted_family=None,
                profile_policy=None,
                mcp_exposure=None,
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
    assert observed_identities == _EXPECTED_PROFILE_IDENTITIES
    actionable = {row.declaration.action.action_id for row in resolution.profiles if row.declaration.action is not None}
    assert actionable == {"operator.modelo.bindings.list", "operator.registry.verify"}
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
