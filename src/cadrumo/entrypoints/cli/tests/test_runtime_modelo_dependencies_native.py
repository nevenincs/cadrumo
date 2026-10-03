"""Native dependency reads stay in one authenticated profile worker."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import cast
from uuid import UUID

import pytest
from click.testing import Result

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from ....application.calculations.cross_period_clean_state import cross_period_dependency_inventory
from ....application.modelo.dependency_operation import (
    MODELO_DEPENDENCY_OPERATION_DEFINITION_ID,
    ModeloDependencyRequest,
    dependency_access_periods,
)
from ....application.operations.frontend_requests import OPERATION_OBSERVATION_PROJECTION_ID
from ....application.operations.public_period import PublicPeriod
from ....application.user_profile.access_contracts import (
    AccessAction,
    AccessScope,
    DisclosureCategory,
    DisclosurePermission,
)
from ....application.user_profile.login_session import login_profile, resolve_login_target
from ....core.config import override_settings
from ....core.period import Period
from ....domain.buckets.event import BucketEventObjectType, BucketEventType
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

_LABEL = "Native dependency inspection operator"
_TARGET = Period.from_year_and_code(2025, "0A")


def _facts() -> dict[str, str]:
    return {
        "taxpayer_type.entity_type": "natural_person",
        "identity.name": "Native",
        "identity.surnames": "Dependencies",
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
    close_active_bucket_session()
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
                "dependencies",
                *arguments,
            ),
            input=json.dumps({"profile_passphrase": fixture.passphrase}),
        )
    assert fixture.passphrase not in result.output
    return result


def test_native_inventory_and_clean_state_match_published_authority_without_mutation(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation
) -> None:
    with native_cli_profile_scope(tmp_path) as fixture:
        fixture.register(label=_LABEL, facts=_facts())
        profile_id = resolve_login_target(_LABEL).bucket_id
        modelo_operation_test_support.seeded_modelo_work_unit(UUID(profile_id), operation=authority_operation)
        expected_inventory = cross_period_dependency_inventory(authority_operation, filing_year=2025, modelos=("100",))
        before = BucketEventHistoryRepository().load().events
        close_active_bucket_session()

        inventory = _invoke(fixture, "--year", "2025", "--modelo", "100")
        assert inventory.exit_code == 0, inventory.output
        inventory_result = unwrap_cli_result(inventory)
        assert inventory_result["filing_year"] == 2025
        assert inventory_result["modelo_filter"] == "100"
        assert inventory_result["period_filter"] is None
        assert inventory_result["clean_state"] is None
        assert inventory_result["target_count"] == len(expected_inventory.items)
        assert tuple(inventory_result["target_modelos"]) == expected_inventory.target_modelos
        assert tuple(inventory_result["source_modelos"]) == expected_inventory.source_modelos

        detailed = _invoke(fixture, "--year", "2025", "--modelo", "100", "--period", "0A")
        assert detailed.exit_code == 0, detailed.output
        result = unwrap_cli_result(detailed)
        assert result["target_count"] == len(expected_inventory.items)
        assert result["period_filter"] == "0A"
        clean = cast("dict[str, object]", result["clean_state"])
        assert clean["target_modelo"] == "100"
        assert clean["target_filing_year"] == 2025
        assert cast("dict[str, object]", clean["target_period"])["code"] == "0A"
        assert "dependencies" in clean

        close_active_bucket_session()
        login_profile(
            name=_LABEL,
            passphrase_callback=lambda: fixture.passphrase,
            profile_decode_context=authority_operation.profile_decode_context(),
        )
        try:
            after = BucketEventHistoryRepository().load().events
            assert all(after.get(event_id) == event for event_id, event in before.items())
            added = tuple(event for event_id, event in after.items() if event_id not in before)
            assert all(
                event.event_type is BucketEventType.PROFILE_ACTIVATED
                and event.object_type is BucketEventObjectType.PROFILE
                and event.actor == "profile-login"
                and event.object_id == profile_id
                for event in added
            ), tuple((event.event_type.value, event.object_type.value) for event in added)
        finally:
            close_active_bucket_session()


def _scope(client_id: UUID, *, periods: frozenset[Period], result: bool = True) -> AccessScope:
    actions = {
        AccessAction.SUBMIT,
        AccessAction.START,
        AccessAction.RESUME,
        AccessAction.OBSERVE,
        AccessAction.CANCEL,
        AccessAction.DETACH,
    }
    if result:
        actions.add(AccessAction.RESULT)
    return AccessScope(
        operations=frozenset({MODELO_DEPENDENCY_OPERATION_DEFINITION_ID}),
        actions=frozenset(actions),
        disclosures=frozenset(
            {
                DisclosurePermission(
                    destination_id=client_id,
                    projection_id=OPERATION_OBSERVATION_PROJECTION_ID,
                    category=DisclosureCategory.OPERATION_METADATA,
                ),
                DisclosurePermission(
                    destination_id=client_id,
                    projection_id=f"{MODELO_DEPENDENCY_OPERATION_DEFINITION_ID}.result",
                    category=DisclosureCategory.TAX_VALUES,
                ),
            }
        ),
        periods=periods,
        allow_period_independent=False,
        allow_delegation=False,
    )


def test_native_target_only_grant_refuses_before_private_result(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation
) -> None:
    def prepare(profile_id: UUID, _root: Path) -> str:
        modelo_operation_test_support.seeded_modelo_work_unit(profile_id, operation=authority_operation)
        return str(profile_id)

    with native_api_cli_session(
        tmp_path / "target-only",
        scope_for_destination=lambda client_id: _scope(client_id, periods=frozenset({_TARGET})),
        prepare_profile=prepare,
    ) as session:
        denied = session.invoke_credential_reference(
            "app", "modelo", "work", "dependencies", "--year", "2025", "--modelo", "100", "--period", "0A"
        )
        assert denied.exit_code == 2, denied.output
        error = require_error_document(denied.output)["error"]
        assert error["context"] == {"reason": "period_denied"}
        assert "clean_state" not in denied.output

    request = ModeloDependencyRequest(
        profile_id=UUID("5aa00000-0000-4000-8000-0000000000aa"),
        filing_year=2025,
        modelo="100",
        period=PublicPeriod.from_period(_TARGET),
    )
    all_periods = dependency_access_periods(request, authority_operation)
    assert all_periods > frozenset({_TARGET})

    with native_api_cli_session(
        tmp_path / "result-denied",
        scope_for_destination=lambda client_id: _scope(client_id, periods=all_periods, result=False),
        prepare_profile=prepare,
    ) as session:
        denied = session.invoke_credential_reference(
            "app", "modelo", "work", "dependencies", "--year", "2025", "--modelo", "100", "--period", "0A"
        )
        assert denied.exit_code == 2, denied.output
        error = require_error_document(denied.output)["error"]
        context = cast("dict[str, object]", error["context"])
        assert context["reason"] == "operation_denied"
        assert context["terminal_condition"] == "succeeded"
        assert context["effect"] == "none"
        assert "clean_state" not in denied.output
