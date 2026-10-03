"""Native worker journey for registered modelo history, project and compare."""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path
from uuid import UUID

import pytest
from click.testing import Result

from ....adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from ....adapters.persistence.storage.tests.profile_capsule_runtime import (
    profile_authority_contexts,
    seed_test_profile_record,
)
from ....application.modelo.calculation_actions import calculate_modelo_revision
from ....application.modelo.tests.profile_fixture_values import MODELO_READY_PROFILE_FACTS
from ....application.modelo.work_lifecycle import create_work_unit
from ....application.user_profile.login_session import resolve_login_target
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ....domain.calculations.registry.tests.cross_period_seeding import resolved_revision
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, create_user_profile_record
from ....tests.cli_envelope import unwrap_cli_result
from ...adapter_composition import build_calculation_action_ports, build_work_lifecycle_ports
from ...tests import modelo_operation_test_support
from .cli_runner import invoke_cached_cli
from .runtime_profile_cli_fixture import NativeCliProfileFixture, native_cli_profile_scope

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers"),
]


def _invoke(profile: NativeCliProfileFixture, *command: str) -> Result:
    assert profile.label is not None
    close_active_bucket_session()
    result = invoke_cached_cli(
        ("--format", "json", "--profile", profile.label, "--profile-secrets-stdin", *command),
        input=json.dumps({"profile_passphrase": profile.passphrase}),
    )
    assert profile.passphrase not in result.output
    return result


def test_native_modelo_history_project_compare_reuse_real_stored_revisions(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation
) -> None:
    with native_cli_profile_scope(tmp_path) as profile:
        profile.register(
            label="native-modelo-history-project-compare",
            facts={
                "taxpayer_type.entity_type": "natural_person",
                "identity.name": "Native",
                "identity.surnames": "Projection",
                "activities.description": "consulting",
                "censo.activity_start_date": "2025-01-01",
                "tax_residence.jurisdiction_scope": "common_regime",
                "tax_residence.ccaa": "madrid",
                "iva.regime": "GENERAL",
                "iva.m303_regime_composition": "general",
                "iva.redeme_enrolled": "false",
                "iva.cash_accounting_regime_enrolled": "false",
                "iva.voluntary_sii_enrolled": "false",
                "iva.hydrocarbon_deposit_advance_payment_deduction_entitled": "false",
            },
        )
        assert profile.label is not None
        bucket_id = resolve_login_target(profile.label).bucket_id
        profile_id = UUID(bucket_id)
        revision_2025 = modelo_operation_test_support.seeded_modelo_calculation_revision(
            profile_id, operation=authority_operation
        )
        revision = resolved_revision(modelo="130", filing_year=2026, period="1T")
        unit = create_work_unit(
            bucket_id=bucket_id,
            modelo="130",
            filing_year=2026,
            period=Period.from_year_and_code(2026, "1T"),
            revision_id=revision.id,
            actor=modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
            ports=build_work_lifecycle_ports(bucket_id=bucket_id),
            operation=authority_operation,
        )
        with bundled_indexed_authority().operation() as calculation_operation:
            calculated = calculate_modelo_revision(
                unit.work_unit_id,
                ports=build_calculation_action_ports(bucket_id=bucket_id, operation=calculation_operation),
                actor=modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
                casilla_inputs={},
                binding_values=modelo_operation_test_support.FIRST_QUARTER_PRIOR_PERIOD_BINDINGS,
            )
        revision_2026 = str(calculated.calculation_revision_id)
        seed_test_profile_record(
            create_user_profile_record(
                context=profile_authority_contexts()[0],
                profile_id=bucket_id,
                setup_state=ProfileSetupState.COMPLETE,
                facts=(
                    *MODELO_READY_PROFILE_FACTS,
                    UserProfileFact(path="taxpayer_type.irpf_income_categories", value="actividad_economica"),
                    UserProfileFact(path="irpf.estimation_regime", value="directa_normal"),
                    UserProfileFact(path="tax_residence.ccaa", value="madrid"),
                    UserProfileFact(path="renta_filing.declaration_type", value="1"),
                    UserProfileFact(path="renta_taxpayer.birth_date", value=date(1980, 1, 1)),
                ),
            )
        )
        close_active_bucket_session()

        history = _invoke(profile, "app", "modelo", "history", "--modelo", "130", "--year", "2025")
        assert history.exit_code == 0, history.output
        events = unwrap_cli_result(history)
        assert events["modelo"] == "130" and events["year"] == 2025
        assert events["count"] == len(events["events"]) and events["count"] >= 2
        assert all(event["event_id"] and event["event_type"] and event["occurred_at"] for event in events["events"])

        project = _invoke(profile, "app", "modelo", "project", "--year", "2025", "--ccaa", "madrid")
        assert project.exit_code == 0, project.output
        projected = unwrap_cli_result(project)
        assert projected["year"] == 2025 and projected["ccaa"] == "madrid"
        assert projected["quarters_filed"] == 1 and projected["quarters_available"] == ["1T"]
        assert projected["is_extrapolated"] is True
        assert projected["casilla_observations"]
        assert projected["m100_projection"]["base_liquidable_general_0505"] is not None

        compared = _invoke(profile, "app", "modelo", "compare", "--modelo", "130", "--year", "2025", "--year", "2026")
        assert compared.exit_code == 0, compared.output
        comparison = unwrap_cli_result(compared)
        assert (comparison["year_a"], comparison["year_b"]) == (2025, 2026)
        assert comparison["year_a_revision_id"] == revision_2025
        assert comparison["year_b_revision_id"] == revision_2026
        assert comparison["delta_rows"] and comparison["sections"]
        assert all("legal_refs" in row and "source_refs" in row for row in comparison["delta_rows"])
