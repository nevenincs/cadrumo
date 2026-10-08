"""Native CLI inventory preserves ordering, filters, and worker access scope."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import cast
from uuid import UUID, uuid4

import pytest
from click.testing import Result

from ....adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from ....application.modelo.work_inventory_operation import MODELO_WORK_LIST_OPERATION_DEFINITION_ID
from ....application.modelo.work_lifecycle import create_work_unit, discard_work_unit
from ....application.operations.frontend_requests import OPERATION_OBSERVATION_PROJECTION_ID
from ....application.user_profile.access_contracts import (
    AccessAction,
    AccessScope,
    DisclosureCategory,
    DisclosurePermission,
)
from ....application.user_profile.login_session import resolve_login_target
from ....core.config import override_settings
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....tests.cli_envelope import require_error_document, unwrap_cli_result
from ...adapter_composition import build_work_lifecycle_ports
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

_LABEL = "Native modelo inventory operator"


def _profile_facts() -> dict[str, str]:
    """Return complete, synthetic facts for the encrypted CLI profile."""
    return {
        "taxpayer_type.entity_type": "natural_person",
        "identity.name": "Native",
        "identity.surnames": "Inventory",
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


def _invoke_work(fixture: NativeCliProfileFixture, *arguments: str) -> Result:
    """Invoke a native work command through the profile password channel."""
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
                *arguments,
            ),
            input=json.dumps({"profile_passphrase": fixture.passphrase}),
        )
    assert fixture.passphrase not in result.output
    return result


def _scope_for_destination(client_id: UUID, *, periods: frozenset[Period] | None) -> AccessScope:
    """Grant only inventory read and its exact result projection."""
    return AccessScope(
        operations=frozenset({MODELO_WORK_LIST_OPERATION_DEFINITION_ID}),
        actions=frozenset(
            {
                AccessAction.SUBMIT,
                AccessAction.START,
                AccessAction.RESUME,
                AccessAction.OBSERVE,
                AccessAction.RESULT,
                AccessAction.CANCEL,
                AccessAction.DETACH,
            }
        ),
        disclosures=frozenset(
            {
                DisclosurePermission(
                    destination_id=client_id,
                    projection_id=OPERATION_OBSERVATION_PROJECTION_ID,
                    category=DisclosureCategory.OPERATION_METADATA,
                ),
                DisclosurePermission(
                    destination_id=client_id,
                    projection_id=f"{MODELO_WORK_LIST_OPERATION_DEFINITION_ID}.result",
                    category=DisclosureCategory.TAX_VALUES,
                ),
            }
        ),
        periods=periods,
        allow_period_independent=True,
        allow_delegation=False,
    )


def _empty_profile(_profile_id: UUID, _storage_root: Path) -> None:
    """Leave the API profile with an empty work-unit catalogue."""


def test_native_work_list_and_select_preserve_default_and_discarded_order(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation
) -> None:
    """Real worker inventory hides discarded rows by default and sorts periods."""
    with native_cli_profile_scope(tmp_path) as fixture:
        fixture.register(label=_LABEL, facts=_profile_facts())
        bucket_id = resolve_login_target(_LABEL).bucket_id
        first = modelo_operation_test_support.seeded_modelo_work_unit(UUID(bucket_id), operation=authority_operation)
        second = create_work_unit(
            bucket_id=bucket_id,
            modelo="130",
            filing_year=2025,
            period=Period.from_year_and_code(2025, "2T"),
            revision_id=first.revision_id,
            actor="native-work-inventory",
            ports=build_work_lifecycle_ports(bucket_id=bucket_id),
            operation=authority_operation,
        )
        third = create_work_unit(
            bucket_id=bucket_id,
            modelo="130",
            filing_year=2025,
            period=Period.from_year_and_code(2025, "4T"),
            revision_id=first.revision_id,
            actor="native-work-inventory",
            ports=build_work_lifecycle_ports(bucket_id=bucket_id),
            operation=authority_operation,
        )
        discarded = discard_work_unit(
            second.work_unit_id,
            actor="native-work-inventory",
            reason="native inventory filter case",
            ports=build_work_lifecycle_ports(bucket_id=bucket_id),
        )
        assert discarded.state.value == "descartado"
        close_active_bucket_session()

        listed = _invoke_work(fixture, "list")
        assert listed.exit_code == 0, listed.output
        list_result = unwrap_cli_result(listed)
        listed_units = cast("list[dict[str, object]]", list_result["work_units"])
        assert list_result["operation"] == "modelo.work.list"
        assert list_result["include_discarded"] is False
        assert list_result["work_unit_count"] == 2
        assert [cast("dict[str, object]", row["period"])["code"] for row in listed_units] == ["1T", "4T"]
        assert [row["state"] for row in listed_units] == ["borrador", "borrador"]

        selected = _invoke_work(fixture, "select", "--include-discarded")
        assert selected.exit_code == 0, selected.output
        select_result = unwrap_cli_result(selected)
        selected_units = cast("list[dict[str, object]]", select_result["work_units"])
        assert select_result["operation"] == "modelo.work.select"
        assert select_result["include_discarded"] is True
        assert select_result["work_unit_count"] == 3
        assert [cast("dict[str, object]", row["period"])["code"] for row in selected_units] == [
            "1T",
            "2T",
            "4T",
        ]
        assert [row["state"] for row in selected_units] == ["borrador", "descartado", "borrador"]
        assert [row["work_unit_id"] for row in selected_units] == [
            first.work_unit_id,
            second.work_unit_id,
            third.work_unit_id,
        ]
        assert discarded.work_unit_id == second.work_unit_id

        foreign = _invoke_work(fixture, "list", "--bucket-id", str(uuid4()))
        assert foreign.exit_code == 2, foreign.output
        error = require_error_document(foreign.output)["error"]
        assert error["code"] == "REFUSED_RUNTIME_FRONTEND"
        assert error["context"] == {"reason": "profile_mismatch"}


def test_native_api_work_list_requires_unbounded_period_scope(tmp_path: Path) -> None:
    """A finite-period key cannot read whole-profile inventory; an unbounded one can."""
    selected_period = Period.from_year_and_code(2025, "1T")

    with native_api_cli_session(
        tmp_path / "finite-period",
        scope_for_destination=lambda client_id: _scope_for_destination(client_id, periods=frozenset({selected_period})),
        prepare_profile=_empty_profile,
    ) as finite:
        refused = finite.invoke_credential_reference("app", "modelo", "work", "list")
        assert refused.exit_code == 2, refused.output
        error = require_error_document(refused.output)["error"]
        assert error["code"] == "REFUSED_RUNTIME_FRONTEND"
        assert error["context"] == {"reason": "period_denied"}
        assert "work_unit_count" not in refused.output

    with native_api_cli_session(
        tmp_path / "all-periods",
        scope_for_destination=lambda client_id: _scope_for_destination(client_id, periods=None),
        prepare_profile=_empty_profile,
    ) as whole_profile:
        accepted = whole_profile.invoke_credential_reference("app", "modelo", "work", "list")
        assert accepted.exit_code == 0, accepted.output
        result = unwrap_cli_result(accepted)
        assert result["operation"] == "modelo.work.list"
        assert result["include_discarded"] is False
        assert result["work_unit_count"] == 0
        assert result["work_units"] == []
