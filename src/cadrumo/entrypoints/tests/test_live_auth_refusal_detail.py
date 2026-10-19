"""Unconfigured AEAT access retains actionable detail through encrypted settlement."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest

from ...adapters.outbound.aeat.browser.factory import BrowserRuntimeResourceScope
from ...adapters.persistence.operations.journal import OperationJournalRepository
from ...adapters.persistence.operations.lease import OperationLeaseFilesystemRepository
from ...adapters.persistence.operations.secure_references import operation_secure_reference_repository
from ...adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from ...application.live.notifications_capture_operation import (
    NOTIFICATIONS_CAPTURE_DEFINITION_ID,
    NotificationsCaptureRequest,
    build_notifications_capture_definition,
    build_notifications_capture_registration,
)
from ...application.operations.error_detail import OperationErrorDetailV1, operation_error_detail_schema
from ...application.operations.frontend_requests import (
    OperationResultProjectionRequestV1,
    OperationResultProjectionSuccessV1,
)
from ...application.operations.models import OperationRequest
from ...application.operations.projection_services import OperationResultProjectionService
from ...application.operations.registry import OperationRegistry
from ...application.operations.supervisor import OperationSupervisor
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...domain.calculations.registry.authority import bundled_indexed_authority
from ..live_state_composition import compose_live_state, preflight_filed_history_provider

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def test_missing_aeat_setup_survives_capture_settlement_and_result_read(tmp_path: Path) -> None:
    """Real preflight and custody distinguish missing setup from expired sign-in."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile, bundled_indexed_authority().operation() as authority:
        definition = build_notifications_capture_definition(
            compose_live_state, BrowserRuntimeResourceScope, preflight_filed_history_provider
        )
        registration = build_notifications_capture_registration(definition)
        registry = OperationRegistry(definitions=(definition,), public_registrations=(registration,))
        durable_root = tmp_path / "operations"
        journal = OperationJournalRepository(storage_root=durable_root)
        operands = operation_secure_reference_repository(objects=profile.repository)
        supervisor = OperationSupervisor(
            authority_operation=authority,
            registry=registry,
            journal=journal,
            event_stream=journal,
            leases=OperationLeaseFilesystemRepository(storage_root=durable_root),
            operands=operands,
            owner_id="1" * 64,
            lease_token_factory=lambda: "2" * 64,
            clock=lambda: datetime.now(UTC),
            lease_duration=timedelta(minutes=5),
        )
        request = OperationRequest(
            definition_id=NOTIFICATIONS_CAPTURE_DEFINITION_ID,
            subject_ref=profile_operation_subject(profile.bucket_id),
            payload=NotificationsCaptureRequest(profile_id=UUID(profile.bucket_id)),
        )

        async def run() -> OperationErrorDetailV1:
            operation_id = await supervisor.submit(request, operation_id="3" * 64)
            await supervisor.start(operation_id)
            terminal = await supervisor.settled(operation_id)
            assert terminal.terminal_condition is OperationTerminalCondition.REFUSED
            assert terminal.effect is OperationEffect.NONE
            # Read through fresh repositories, as a later process does, rather
            # than relying on the raised exception or an in-memory projection.
            service = OperationResultProjectionService(
                reader=OperationJournalRepository(storage_root=durable_root),
                registry=registry,
                operands=operation_secure_reference_repository(objects=profile.repository),
            )
            projected = await service.resolve(
                OperationResultProjectionRequestV1(
                    operation_id=operation_id,
                    terminal_revision=terminal.revision,
                    definition_contract_digest=registration.contract.definition_contract_digest,
                    result_schema=operation_error_detail_schema(),
                ),
                OperationErrorDetailV1,
            )
            assert isinstance(projected, OperationResultProjectionSuccessV1)
            return projected.projection

        detail = asyncio.run(run())
        assert detail.error_code == "REFUSED_AUTH_LOGIN_PRECONDITION"
        assert detail.message_key == "application.auth.sync.errors.requirements_missing"
        context = {entry.key: entry.value for entry in detail.context}
        assert set(context["required_fields"].split(", ")) == {"identity.tax_id", "auth.provider"}
        assert context["reasons"]
        assert "expired" not in context["reasons"].lower()
