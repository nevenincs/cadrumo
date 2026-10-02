"""Native work creation uses the authenticated worker and durable writer."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from uuid import UUID

import pytest
from click.testing import Result

from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from ....application.modelo.work_create_operation import (
    MODELO_WORK_CREATE_APPLICABILITY_REFUSAL_CODE,
    MODELO_WORK_CREATE_OPERATION_DEFINITION_ID,
)
from ....application.operations.frontend_requests import OPERATION_OBSERVATION_PROJECTION_ID
from ....application.user_profile.access_contracts import (
    AccessAction,
    AccessScope,
    DisclosureCategory,
    DisclosurePermission,
)
from ....application.user_profile.login_session import login_profile, resolve_login_target
from ....core.config import override_settings
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....tests.cli_envelope import require_error_document, unwrap_cli_result
from ...tests import modelo_operation_test_support
from .cli_runner import invoke_cached_cli
from .native_api_cli_support import native_api_cli_session
from .runtime_profile_cli_fixture import NativeCliProfileFixture, native_cli_profile_scope

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers"),
]

_LABEL = "Native modelo create operator"


def _facts() -> dict[str, str]:
    return {
        "taxpayer_type.entity_type": "natural_person",
        "identity.name": "Native",
        "identity.surnames": "Create",
        "activities.description": "consulting",
        "censo.activity_start_date": "2025-01-01",
        "tax_residence.jurisdiction_scope": "common_regime",
        "iva.regime": "GENERAL",
        "iva.m303_regime_composition": "general",
        "iva.redeme_enrolled": "false",
        "iva.cash_accounting_regime_enrolled": "false",
        "iva.voluntary_sii_enrolled": "false",
        "iva.hydrocarbon_deposit_advance_payment_deduction_entitled": "false",
    }


def _invoke(fixture: NativeCliProfileFixture, *arguments: str) -> Result:
    assert fixture.label is not None
    with override_settings(cadrumo_cli_reveal_identifiers=False):
        result = invoke_cached_cli(
            (
                "--format",
                "json",
                "--profile",
                fixture.label,
                "--profile-secrets-stdin",
                "app",
                "modelo",
                "work",
                "create",
                *arguments,
            ),
            input=json.dumps({"profile_passphrase": fixture.passphrase}),
        )
    assert fixture.passphrase not in result.output
    return result


def _m130(*extra: str) -> tuple[str, ...]:
    return ("--modelo", "130", "--year", "2025", "--period", "1T", *extra)


def test_native_create_reuse_rename_matches_encrypted_work_catalogue(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation
) -> None:
    with native_cli_profile_scope(tmp_path) as fixture:
        fixture.register(label=_LABEL, facts=_facts())
        bucket_id = resolve_login_target(_LABEL).bucket_id
        close_active_bucket_session()

        created = _invoke(fixture, *_m130("--name", "Original"))
        assert created.exit_code == 0, created.output
        created_result = unwrap_cli_result(created)
        assert created_result["status"] == "created"
        unit_id = created_result["work_unit_id"]

        reused = _invoke(fixture, *_m130("--name", "Original"))
        assert reused.exit_code == 0, reused.output
        reused_result = unwrap_cli_result(reused)
        assert reused_result["status"] == "reused"
        assert reused_result["work_unit_id"] == unit_id
        assert reused_result["name_applied"] is None

        renamed = _invoke(fixture, *_m130("--name", "Renamed"))
        assert renamed.exit_code == 0, renamed.output
        renamed_result = unwrap_cli_result(renamed)
        assert renamed_result["status"] == "reused"
        assert renamed_result["work_unit_id"] == unit_id
        assert renamed_result["name_applied"] == "Renamed"

        close_active_bucket_session()
        login = login_profile(
            name=_LABEL,
            passphrase_callback=lambda: fixture.passphrase,
            profile_decode_context=authority_operation.profile_decode_context(),
        )
        assert login.bucket_id == bucket_id
        try:
            stored = WorkUnitCatalogueRepository(bucket_id=bucket_id).load().get(str(unit_id))
            assert stored is not None
            assert stored.name == "Renamed"
            assert stored.current_calculation_revision_id is None
            assert str(stored.modelo) == "130"
            assert stored.period == Period.from_year_and_code(2025, "1T")
        finally:
            close_active_bucket_session()


def test_native_applicability_refusal_has_bounded_detail_and_no_work(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation
) -> None:
    with native_cli_profile_scope(tmp_path) as fixture:
        fixture.register(label=_LABEL, facts=_facts())
        bucket_id = resolve_login_target(_LABEL).bucket_id
        close_active_bucket_session()
        refused = _invoke(
            fixture,
            "--modelo",
            "202",
            "--year",
            "2025",
            "--period",
            "1P",
            "--revision",
            "2025-y-siguientes",
        )
        assert refused.exit_code == 2, refused.output
        error = require_error_document(refused.output)["error"]
        context = error["context"]
        assert context["refusal_code"] == MODELO_WORK_CREATE_APPLICABILITY_REFUSAL_CODE
        assert context["terminal_condition"] == "refused"
        assert context["effect"] == "none"
        assert context["modelo"] == "202"
        assert isinstance(context["reason"], str) and context["reason"]
        assert len(context["operation_id"]) == 64

        close_active_bucket_session()
        login = login_profile(
            name=_LABEL,
            passphrase_callback=lambda: fixture.passphrase,
            profile_decode_context=authority_operation.profile_decode_context(),
        )
        assert login.bucket_id == bucket_id
        try:
            assert not any(
                str(unit.modelo) == "202"
                for unit in WorkUnitCatalogueRepository(bucket_id=bucket_id).load().work_units.values()
            )
        finally:
            close_active_bucket_session()


def _scope(
    client_id: UUID, *, period: Period, commit: bool, result: bool, result_disclosure: bool = True
) -> AccessScope:
    actions = {
        AccessAction.SUBMIT,
        AccessAction.START,
        AccessAction.RESUME,
        AccessAction.OBSERVE,
        AccessAction.CANCEL,
        AccessAction.DETACH,
    }
    if commit:
        actions.add(AccessAction.COMMIT)
    if result:
        actions.add(AccessAction.RESULT)
    disclosures = {
        DisclosurePermission(
            destination_id=client_id,
            projection_id=OPERATION_OBSERVATION_PROJECTION_ID,
            category=DisclosureCategory.OPERATION_METADATA,
        )
    }
    if result and result_disclosure:
        disclosures.add(
            DisclosurePermission(
                destination_id=client_id,
                projection_id=f"{MODELO_WORK_CREATE_OPERATION_DEFINITION_ID}.result",
                category=DisclosureCategory.TAX_VALUES,
            )
        )
    return AccessScope(
        operations=frozenset({MODELO_WORK_CREATE_OPERATION_DEFINITION_ID}),
        actions=frozenset(actions),
        disclosures=frozenset(disclosures),
        periods=frozenset({period}),
        allow_period_independent=False,
        allow_delegation=False,
    )


def test_native_create_requires_matching_period_and_commit_and_result_disclosure(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation
) -> None:
    def prepare(profile_id: UUID, _root: Path) -> str:
        unit = modelo_operation_test_support.seeded_modelo_work_unit(profile_id, operation=authority_operation)
        return unit.work_unit_id

    cases = (
        ("wrong-period", Period.from_year_and_code(2025, "2T"), True, True, "period_denied"),
        ("no-commit", Period.from_year_and_code(2025, "1T"), False, True, "REFUSED_PROFILE_ACCESS"),
    )
    for label, period, commit, result, reason in cases:
        with native_api_cli_session(
            tmp_path / label,
            scope_for_destination=lambda client_id, period=period, commit=commit, result=result: _scope(
                client_id, period=period, commit=commit, result=result
            ),
            prepare_profile=prepare,
        ) as session:
            refused = session.invoke_credential_reference("app", "modelo", "work", "create", *_m130("--name", "Denied"))
            assert refused.exit_code == 2, refused.output
            error = require_error_document(refused.output)["error"]
            assert error["context"]["reason"] == reason
            if label == "no-commit":
                assert error["context"]["terminal_condition"] == "refused"
                assert error["context"]["effect"] == "none"
            assert "name_applied" not in refused.output
            observed = session.invoke_password("app", "modelo", "work", "list")
            assert observed.exit_code == 0, observed.output
            units = unwrap_cli_result(observed)["work_units"]
            assert any(unit["work_unit_id"] == session.prepared and unit["name"] != "Denied" for unit in units)

    with native_api_cli_session(
        tmp_path / "no-result",
        scope_for_destination=lambda client_id: _scope(
            client_id, period=Period.from_year_and_code(2025, "1T"), commit=True, result=False
        ),
        prepare_profile=prepare,
    ) as session:
        denied = session.invoke_credential_reference("app", "modelo", "work", "create", *_m130("--name", "Committed"))
        assert denied.exit_code == 2, denied.output
        error = require_error_document(denied.output)["error"]
        assert error["context"]["reason"] == "operation_denied"
        assert error["context"]["terminal_condition"] == "succeeded"
        assert error["context"]["effect"] == "updated"
        assert "name_applied" not in denied.output
        observed = session.invoke_password("app", "modelo", "work", "list")
        assert observed.exit_code == 0, observed.output
        units = unwrap_cli_result(observed)["work_units"]
        assert any(unit["work_unit_id"] == session.prepared and unit["name"] == "Committed" for unit in units)

    disclosure_only_scope = _scope(
        UUID("5aa00000-0000-4000-8000-0000000000aa"),
        period=Period.from_year_and_code(2025, "1T"),
        commit=True,
        result=True,
        result_disclosure=False,
    )
    assert AccessAction.RESULT in disclosure_only_scope.actions
    assert all(
        permission.category is not DisclosureCategory.TAX_VALUES for permission in disclosure_only_scope.disclosures
    )
    with native_api_cli_session(
        tmp_path / "no-result-disclosure",
        scope_for_destination=lambda client_id: _scope(
            client_id,
            period=Period.from_year_and_code(2025, "1T"),
            commit=True,
            result=True,
            result_disclosure=False,
        ),
        prepare_profile=prepare,
    ) as session:
        denied = session.invoke_credential_reference("app", "modelo", "work", "create", *_m130("--name", "Committed"))
        assert denied.exit_code == 2, denied.output
        error = require_error_document(denied.output)["error"]
        assert error["context"]["reason"] == "disclosure_denied"
        assert error["context"]["terminal_condition"] == "succeeded"
        assert error["context"]["effect"] == "updated"
        assert "name_applied" not in denied.output
        observed = session.invoke_password("app", "modelo", "work", "list")
        assert observed.exit_code == 0, observed.output
        units = unwrap_cli_result(observed)["work_units"]
        assert any(unit["work_unit_id"] == session.prepared and unit["name"] == "Committed" for unit in units)


def test_native_applicability_refusal_detail_requires_result_permission(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation
) -> None:
    def prepare(profile_id: UUID, _root: Path) -> str:
        unit = modelo_operation_test_support.seeded_modelo_work_unit(profile_id, operation=authority_operation)
        return unit.work_unit_id

    with native_api_cli_session(
        tmp_path,
        scope_for_destination=lambda client_id: _scope(
            client_id, period=Period.from_year_and_code(2025, "1P"), commit=True, result=False
        ),
        prepare_profile=prepare,
    ) as session:
        denied = session.invoke_credential_reference(
            "app",
            "modelo",
            "work",
            "create",
            "--modelo",
            "202",
            "--year",
            "2025",
            "--period",
            "1P",
            "--revision",
            "2025-y-siguientes",
        )
        assert denied.exit_code == 2, denied.output
        error = require_error_document(denied.output)["error"]
        context = error["context"]
        assert context["terminal_condition"] == "refused"
        assert context["effect"] == "none"
        assert context["refusal_code"] == MODELO_WORK_CREATE_APPLICABILITY_REFUSAL_CODE
        assert "modelo" not in context
        assert "--allow-not-applicable" not in denied.output
        observed = session.invoke_password("app", "modelo", "work", "list")
        assert observed.exit_code == 0, observed.output
        assert all(unit["modelo"] != "202" for unit in unwrap_cli_result(observed)["work_units"])
