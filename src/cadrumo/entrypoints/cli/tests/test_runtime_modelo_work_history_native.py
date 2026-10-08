"""Native history CLI returns the canonical encrypted work-event timeline."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import cast
from uuid import UUID

import pytest
from click.testing import Result

from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....adapters.persistence.storage.master_key.active_session import (
    close_active_bucket_session,
    current_active_bucket_session,
)
from ....application.modelo.history import assemble_work_unit_history
from ....application.modelo.work_lifecycle import create_work_unit, discard_work_unit
from ....application.user_profile.login_session import authenticate_profile_for_invocation, resolve_login_target
from ....core.config import override_settings
from ....core.period import Period
from ....core.redaction.rules import redact_structured_for_cli_output
from ....domain.buckets.event import BucketEventObjectType, BucketEventType
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....tests.cli_envelope import unwrap_cli_result
from ...adapter_composition import build_modelo_history_ports, build_work_lifecycle_ports
from ...tests import modelo_operation_test_support
from ..modelo_aux_payloads import WorkHistoryResult, WorkUnitHistoryEventPayload
from .cli_runner import invoke_cached_cli
from .runtime_profile_cli_fixture import NativeCliProfileFixture, native_cli_profile_scope

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers"),
    pytest.mark.usefixtures("authority_operation"),
]

_LABEL = "Native modelo history operator"


def _invoke_history(fixture: NativeCliProfileFixture, *, work_unit_id: str) -> Result:
    """Invoke the installed command through the protected password channel."""
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
                "history",
                work_unit_id,
            ),
            input=json.dumps({"profile_passphrase": fixture.passphrase}),
        )
    assert fixture.passphrase not in result.output
    return result


def test_native_work_history_matches_pinned_encrypted_oracle_including_discard(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation
) -> None:
    """A discarded target stays readable; another period's events never leak."""
    with native_cli_profile_scope(tmp_path) as fixture:
        fixture.register(
            label=_LABEL,
            facts={
                "taxpayer_type.entity_type": "natural_person",
                "identity.name": "Native",
                "identity.surnames": "History",
                "activities.description": "consulting",
                "censo.activity_start_date": "2025-01-01",
                "tax_residence.jurisdiction_scope": "common_regime",
                "iva.regime": "GENERAL",
                "iva.m303_regime_composition": "general",
                "iva.redeme_enrolled": "false",
                "iva.cash_accounting_regime_enrolled": "false",
                "iva.voluntary_sii_enrolled": "false",
                "iva.hydrocarbon_deposit_advance_payment_deduction_entitled": "false",
            },
        )
        bucket_id = resolve_login_target(_LABEL).bucket_id
        revision_id, report_id = modelo_operation_test_support.seeded_modelo_verification_report(
            UUID(bucket_id), operation=authority_operation
        )
        revision = (
            CalculationRevisionCatalogueRepository(bucket_id=bucket_id)
            .load(operation=authority_operation)
            .get(revision_id)
        )
        assert revision is not None
        target_id = revision.work_unit_id
        adjacent = create_work_unit(
            bucket_id=bucket_id,
            modelo="130",
            filing_year=2025,
            period=Period.from_year_and_code(2025, "2T"),
            revision_id="2019-y-siguientes",
            actor="native-history",
            ports=build_work_lifecycle_ports(bucket_id=bucket_id),
            operation=authority_operation,
        )
        discarded = discard_work_unit(
            target_id,
            actor="native-history",
            reason="history remains available",
            ports=build_work_lifecycle_ports(bucket_id=bucket_id),
        )
        assert discarded.work_unit_id == target_id
        close_active_bucket_session()

        observed = _invoke_history(fixture, work_unit_id=target_id)
        assert observed.exit_code == 0, observed.output
        payload = unwrap_cli_result(observed)

        # The worker has closed its session. Open the named profile anew for
        # the independent encrypted oracle, using the same published pin.
        close_active_bucket_session()
        login = authenticate_profile_for_invocation(
            name=_LABEL,
            passphrase_callback=lambda: fixture.passphrase,
            profile_decode_context=authority_operation.profile_decode_context(),
        )
        active_session = current_active_bucket_session()
        assert login.bucket_id == bucket_id
        assert active_session is not None and active_session.bucket_id == bucket_id
        try:
            stored = WorkUnitCatalogueRepository(bucket_id=bucket_id).load().get(target_id)
            assert stored is not None and stored.state == discarded.state
            canonical = assemble_work_unit_history(
                target_id,
                ports=build_modelo_history_ports(bucket_id=bucket_id, operation=authority_operation),
                operation=authority_operation,
            )
        finally:
            close_active_bucket_session()

        expected = WorkHistoryResult(
            bucket_id=canonical.bucket_id,
            work_unit_id=canonical.work_unit_id,
            event_count=len(canonical.events),
            events=[
                WorkUnitHistoryEventPayload(
                    event_id=event.event_id,
                    occurred_at=event.occurred_at,
                    event_type=event.event_type,
                    object_type=event.object_type,
                    object_id=event.object_id,
                    actor=event.actor,
                    payload=dict(event.payload),
                )
                for event in canonical.events
            ],
        )
        expected_payload = cast(
            "dict[str, object]",
            redact_structured_for_cli_output(expected.model_dump(mode="json"), reveal_identifiers=False),
        )
        expected_events = cast("list[dict[str, object]]", expected_payload["events"])
        for expected_event, canonical_event in zip(expected_events, canonical.events, strict=True):
            timestamp = canonical_event.occurred_at.isoformat()
            assert timestamp.endswith("+00:00")
            expected_event["occurred_at"] = timestamp
        assert payload == expected_payload
        assert all(event.object_id != adjacent.work_unit_id for event in canonical.events)
        assert any(event.event_type is BucketEventType.MODELO_WORK_UNIT_DISCARDED for event in canonical.events)
        assert any(
            event.object_type is BucketEventObjectType.CALCULATION_REVISION and event.object_id == revision_id
            for event in canonical.events
        )
        assert any(
            event.object_type is BucketEventObjectType.VERIFICATION_REPORT and event.object_id == report_id
            for event in canonical.events
        )
