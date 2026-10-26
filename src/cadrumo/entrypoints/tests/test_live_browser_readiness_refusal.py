"""Tax agency reads refuse a browser that is not set up before any credential or remote effect.

The refusals run through the real composed preflights, the real setup probe
over a real browsers root and the real supervisor. A root holding the probe's
completion markers is the contrast case: the same operation then gets past the
browser check and stops at the next local precondition instead.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import BaseModel

from ...adapters.outbound.aeat.browser.factory import BrowserRuntimeResourceScope
from ...adapters.persistence.operations.journal import OperationJournalRepository
from ...adapters.persistence.operations.lease import OperationLeaseFilesystemRepository
from ...adapters.persistence.operations.secure_references import operation_secure_reference_repository
from ...adapters.persistence.storage.tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile
from ...application.live.notifications_capture_operation import (
    NOTIFICATIONS_CAPTURE_DEFINITION_ID,
    NotificationsCaptureRequest,
    build_notifications_capture_definition,
    build_notifications_capture_registration,
)
from ...application.live.verify_capture_operation import (
    VERIFY_TGVI_CAPTURE_DEFINITION_ID,
    VerifyCaptureRequest,
    build_verify_capture_registration,
)
from ...application.operations.error_detail import OperationErrorDetailV1
from ...application.operations.models import OperationRequest
from ...application.operations.persistence.journal import OperationPersistedSnapshot
from ...application.operations.registry import OperationRegistry
from ...application.operations.supervisor import OperationSupervisor
from ...application.provisioning_browser import BROWSER_PROVISION_ACTION_ID
from ...application.provisioning_contracts import ProvisioningPreconditionCondition
from ...core.component_records import component_records_root
from ...core.config import Settings, override_settings
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...domain.calculations.registry.authority import bundled_indexed_authority
from ...tests.component_record_support import engine_browser_record, installed_driver_version
from ..live_state_composition import compose_live_state, preflight_filed_history_provider
from ..operation_composition import build_production_operation_registry

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_BROWSER_REFUSAL_CODE = "REFUSED_BROWSER_NOT_READY"


@contextmanager
def _recorded_browser(browsers: Path) -> Generator[None]:
    """Hand Playwright ``browsers``, holding builds the engine recorded for the installed driver."""
    with (
        override_settings(cadrumo_playwright_browsers_dir=browsers) as settings,
        engine_browser_record(
            records_root=component_records_root(settings),
            browsers_root=browsers,
            driver_version=installed_driver_version(),
        ),
    ):
        yield


@contextmanager
def _supervisor(profile: TestRuntimeProfile, registry: OperationRegistry, root: Path) -> Generator[OperationSupervisor]:
    with bundled_indexed_authority().operation() as authority:
        journal = OperationJournalRepository(storage_root=root)
        yield OperationSupervisor(
            authority_operation=authority,
            registry=registry,
            journal=journal,
            event_stream=journal,
            leases=OperationLeaseFilesystemRepository(storage_root=root),
            operands=operation_secure_reference_repository(objects=profile.repository),
            owner_id="1" * 64,
            lease_token_factory=lambda: "2" * 64,
            clock=lambda: datetime.now(UTC),
            lease_duration=timedelta(minutes=5),
        )


def _composed_identity_check(settings: Settings) -> OperationRegistry:
    """The production composition's identity check, registered alone."""
    definition = build_production_operation_registry(settings=settings).lookup(VERIFY_TGVI_CAPTURE_DEFINITION_ID)
    return OperationRegistry(
        definitions=(definition,), public_registrations=(build_verify_capture_registration(definition),)
    )


def _settle(
    supervisor: OperationSupervisor, request: OperationRequest[BaseModel], operation_id: str
) -> OperationPersistedSnapshot:
    async def run() -> OperationPersistedSnapshot:
        created = await supervisor.submit(request, operation_id=operation_id)
        await supervisor.start(created)
        return await supervisor.settled(created)

    return asyncio.run(run())


def _assert_browser_refusal(profile: TestRuntimeProfile, terminal: OperationPersistedSnapshot) -> None:
    assert terminal.terminal_condition is OperationTerminalCondition.REFUSED
    assert terminal.effect is OperationEffect.NONE
    receipt = terminal.terminal_receipt
    assert receipt is not None
    assert receipt.refusal_ref == _BROWSER_REFUSAL_CODE
    assert receipt.error_detail_ref is not None
    detail = asyncio.run(
        operation_secure_reference_repository(objects=profile.repository).resolve(
            receipt.error_detail_ref, OperationErrorDetailV1
        )
    )
    assert detail.error_code == _BROWSER_REFUSAL_CODE
    assert detail.message_key == "adapters.browser.errors.not_provisioned"
    assert detail.precondition_verdict_json is not None
    verdict = json.loads(detail.precondition_verdict_json)
    assert verdict["failed_condition_id"] == ProvisioningPreconditionCondition.PLAYWRIGHT_BROWSER_INSTALLED.value
    assert verdict["action"]["action_id"] == BROWSER_PROVISION_ACTION_ID


def test_live_capture_refuses_a_missing_browser_before_provider_readiness(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path / "profile") as profile:
        definition = build_notifications_capture_definition(
            compose_live_state, BrowserRuntimeResourceScope, preflight_filed_history_provider
        )
        registry = OperationRegistry(
            definitions=(definition,), public_registrations=(build_notifications_capture_registration(definition),)
        )
        request = OperationRequest[BaseModel](
            definition_id=NOTIFICATIONS_CAPTURE_DEFINITION_ID,
            subject_ref=profile_operation_subject(profile.bucket_id),
            payload=NotificationsCaptureRequest(profile_id=UUID(profile.bucket_id)),
        )
        with _supervisor(profile, registry, tmp_path / "operations") as supervisor:
            with override_settings(cadrumo_playwright_browsers_dir=tmp_path / "browsers-empty"):
                refused = _settle(supervisor, request, "3" * 64)
            with _recorded_browser(tmp_path / "browsers-recorded"):
                reached_provider = _settle(supervisor, request, "4" * 64)

        # This profile has no tax agency access configured, so provider
        # readiness would refuse it; the browser refusal came first.
        _assert_browser_refusal(profile, refused)
        assert reached_provider.terminal_condition is OperationTerminalCondition.REFUSED
        assert reached_provider.effect is OperationEffect.NONE
        assert reached_provider.terminal_receipt is not None
        assert reached_provider.terminal_receipt.refusal_ref == "REFUSED_AUTH_LOGIN_PRECONDITION"


def test_identity_check_refuses_a_missing_browser_before_any_remote_read(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path / "profile") as profile:
        request = OperationRequest[BaseModel](
            definition_id=VERIFY_TGVI_CAPTURE_DEFINITION_ID,
            subject_ref=profile_operation_subject(profile.bucket_id),
            payload=VerifyCaptureRequest(profile_id=UUID(profile.bucket_id), nif="12345678Z"),
        )
        with override_settings(cadrumo_playwright_browsers_dir=tmp_path / "browsers-empty") as settings:
            registry = _composed_identity_check(settings)
            with _supervisor(profile, registry, tmp_path / "operations") as supervisor:
                refused = _settle(supervisor, request, "5" * 64)

        _assert_browser_refusal(profile, refused)
