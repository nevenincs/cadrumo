"""The production supervisor driving a real browser over real local HTTP.

The executor here owns the production browser adapter -- a real Playwright
runtime and a real :class:`BrowserSession` -- and navigates it against a real
local HTTP server. Nothing about the transport is simulated: an actual request
crosses an actual socket, and the resource the supervisor is asked to release
is the same one production would hand it.

Two things this is positioned to catch that a narrower proof cannot. A real
browser is expensive and slow to release, so a supervisor that merely
schedules cleanup rather than completing it shows up here. And trace logging
is asserted from the durable journal rather than from an in-memory handle,
alongside a check that the transport's sensitive value never reaches any
persisted byte.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import BaseModel, Field

from ....adapters.outbound.aeat.browser._factory import DefaultBrowserSession
from ....adapters.outbound.aeat.browser.tests.real_http_boundary import (
    LocalHttpBoundary,
    opened_http_boundary,
    real_browser_factory,
)
from ....adapters.persistence.operations.journal import OperationJournalRepository
from ....adapters.persistence.operations.lease import OperationLeaseFilesystemRepository
from ....adapters.persistence.operations.secure_references import (
    OperationSecureReferenceRepository,
    operation_secure_reference_repository,
)
from ....adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from ....core.config import AEAT_CERTIFICATE_PROTECTED_URL, Settings
from ....core.models import STRICT_FROZEN_CONFIG
from ....core.operations import (
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
    OperationLifecycle,
    OperationTerminalCondition,
)
from ....tests.secure_sql import isolated_runtime_profile
from ..capabilities import (
    OperationBaselinePolicy,
    OperationCapabilities,
    OperationConflictScope,
    OperationOwnedResource,
    OperationReplayPolicy,
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
)
from ..events import OperationLogSeverity
from ..models import OperationRequest
from ..owner import OperationExecutorContext
from ..persistence.events import OperationLogRecord, OperationPhaseEvent
from ..registry import (
    OperationDefinition,
    OperationExecutorFactory,
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
    OperationRegistry,
    OperationSchemaBindingV1,
)
from ..supervisor import OperationSupervisor

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_NOW = datetime(2026, 8, 28, 15, tzinfo=UTC)
_DEFINITION_ID = "operation.supervisor.real-resource"
_PHASE_NAVIGATE = "operation.phase.navigate"
_PHASE_SETTLE = "operation.phase.settle"
_TRACE_CODE = "operation.trace.navigation"
_RESULT_REF = "result:real-navigation"


class ResourceRequest(BaseModel):
    """Encrypted operand reaching the real secure-reference adapter."""

    model_config = STRICT_FROZEN_CONFIG

    target_url: str = Field(min_length=1)


class ResourceResult(BaseModel):
    """Registry result type for this operation."""

    model_config = STRICT_FROZEN_CONFIG

    reference: str = Field(min_length=1)


class BrowserOwningExecutor:
    """Own the production browser adapter and drive one real navigation."""

    def __init__(self, *, boundary: LocalHttpBoundary) -> None:
        self._boundary = boundary
        self.browser: DefaultBrowserSession | None = None
        self.response_status: int | None = None
        self.final_url: str | None = None

    async def execute(
        self,
        request: OperationRequest[ResourceRequest],
        context: OperationExecutorContext,
    ) -> str | None:
        browser = await real_browser_factory(
            boundary=self._boundary,
            profile_name="operation-real-resource",
        )(Settings())
        # The factory is declared against the port; this suite deliberately
        # owns the concrete production adapter so its teardown can be observed.
        assert isinstance(browser, DefaultBrowserSession)
        self.browser = browser
        context.cleanup.own(browser, family=OperationOwnedResource.PROCESS)

        await context.events.phase(_PHASE_NAVIGATE)
        await context.events.log(code=_TRACE_CODE, severity=OperationLogSeverity.DEBUG)

        browser_context = await browser.create_context()
        try:
            page = await browser_context.new_page()
            response = await browser.navigate(page, request.payload.target_url)
            self.response_status = None if response is None else response.status
            self.final_url = page.url
        finally:
            await browser_context.close()

        await context.events.log(code=_TRACE_CODE, severity=OperationLogSeverity.INFO)
        await context.events.phase(_PHASE_SETTLE)
        await context.events.effect(OperationEffect.NONE)
        return _RESULT_REF


def _capabilities() -> OperationCapabilities:
    return OperationCapabilities(
        durability=OperationDurability.RECORDED,
        cancellation=OperationCancellation.UNSUPPORTED,
        deadline=OperationDeadline.ABSENT,
        replay=OperationReplayPolicy.IDEMPOTENT_SUBMIT,
        baseline=OperationBaselinePolicy.NONE,
        request_storage=OperationRequestStoragePolicy.SECURE_REFERENCE,
        sensitive_input=OperationSensitiveInputPolicy.SECURE_REFERENCE,
        conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
        owned_resources=frozenset({OperationOwnedResource.PROCESS}),
        permitted_effects=frozenset({OperationEffect.NONE, OperationEffect.UNKNOWN}),
        close_policy=OperationClosePolicy.DETACH_ALLOWED,
    )


def _supervisor(
    *,
    journal: OperationJournalRepository,
    leases: OperationLeaseFilesystemRepository,
    operands: OperationSecureReferenceRepository,
    executor: BrowserOwningExecutor,
) -> OperationSupervisor:
    definition = OperationDefinition(
        definition_id=_DEFINITION_ID,
        request_type=ResourceRequest,
        result_type=ResourceResult,
        executor_factory=OperationExecutorFactory(
            request_type=ResourceRequest,
            executor_type=BrowserOwningExecutor,
            build=lambda: executor,
        ),
        phase_codes=(_PHASE_NAVIGATE, _PHASE_SETTLE),
        interaction_kinds=frozenset(),
        capabilities=_capabilities(),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset({OperationFrontendProjection.TUI}),
    )
    registration = OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id="operation.supervisor.real-resource.request",
            schema_version=1,
            model_type=ResourceRequest,
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id="operation.supervisor.real-resource.result",
            schema_version=1,
            model_type=ResourceResult,
        ),
    )
    return OperationSupervisor(
        registry=OperationRegistry(definitions=(definition,), public_registrations=(registration,)),
        journal=journal,
        event_stream=journal,
        leases=leases,
        operands=operands,
        owner_id="1" * 64,
        lease_token_factory=lambda: "2" * 64,
        clock=lambda: _NOW,
        lease_duration=timedelta(minutes=10),
        cleanup_timeout=timedelta(minutes=5),
    )


def _repositories(
    *,
    storage_root: Path,
    profile_objects: SecureObjectRepository,
) -> tuple[OperationJournalRepository, OperationLeaseFilesystemRepository, OperationSecureReferenceRepository]:
    return (
        OperationJournalRepository(storage_root=storage_root),
        OperationLeaseFilesystemRepository(storage_root=storage_root),
        operation_secure_reference_repository(objects=profile_objects),
    )


def _durable_bytes(storage_root: Path) -> bytes:
    """Concatenate every byte the operation platform wrote under this root."""
    return b"".join(path.read_bytes() for path in storage_root.rglob("*") if path.is_file())


def test_supervisor_settles_a_real_browser_navigation_and_releases_the_runtime(tmp_path: Path) -> None:
    """A real navigation settles, and the supervisor closes the real runtime."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        storage_root = tmp_path / "durable-state"
        journal, leases, operands = _repositories(
            storage_root=storage_root,
            profile_objects=profile.repository,
        )

        async def navigate_under_supervision() -> None:
            async with opened_http_boundary() as boundary:
                boundary.configure("success")
                executor = BrowserOwningExecutor(boundary=boundary)
                supervisor = _supervisor(
                    journal=journal,
                    leases=leases,
                    operands=operands,
                    executor=executor,
                )
                operation_id = "3" * 64
                await supervisor.submit(
                    OperationRequest[BaseModel](
                        definition_id=_DEFINITION_ID,
                        subject_ref="subject:real-resource",
                        payload=ResourceRequest(target_url=AEAT_CERTIFICATE_PROTECTED_URL),
                    ),
                    operation_id=operation_id,
                )
                terminal = await supervisor.start(operation_id)
                replay = await journal.read_after(operation_id, 0, limit=64)

                browser = executor.browser
                assert browser is not None

                # Real HTTP happened: the local server saw the request, and the
                # requested URL remained the production AEAT target.
                assert boundary.navigation_count >= 1
                assert AEAT_CERTIFICATE_PROTECTED_URL in boundary.requested_urls
                assert executor.response_status == 200

                # The supervisor released the real runtime rather than merely
                # scheduling it. Both halves of the adapter's teardown ran.
                assert browser.session_closed

                # Trace logging is durable, carries its declared severities, and
                # sits alongside the declared phases.
                logged = [event for event in replay.events if isinstance(event, OperationLogRecord)]
                assert {record.severity for record in logged} == {
                    OperationLogSeverity.DEBUG,
                    OperationLogSeverity.INFO,
                }
                assert all(record.code == _TRACE_CODE for record in logged)
                phases = [event.phase_code for event in replay.events if isinstance(event, OperationPhaseEvent)]
                assert phases == [_PHASE_NAVIGATE, _PHASE_SETTLE]

                assert terminal.lifecycle is OperationLifecycle.TERMINAL
                assert terminal.terminal_condition is OperationTerminalCondition.SUCCEEDED
                assert terminal.terminal_receipt is not None
                assert terminal.terminal_receipt.result_ref == _RESULT_REF

        asyncio.run(navigate_under_supervision())


def test_a_real_sensitive_redirect_never_reaches_any_persisted_byte(tmp_path: Path) -> None:
    """A sensitive value the executor really saw is absent from durable state."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        storage_root = tmp_path / "durable-state"
        journal, leases, operands = _repositories(
            storage_root=storage_root,
            profile_objects=profile.repository,
        )

        async def navigate_a_sensitive_redirect() -> None:
            async with opened_http_boundary() as boundary:
                # This scenario redirects the production target through a real
                # redirect whose query carries a sensitive value.
                boundary.configure("sensitive-error")
                executor = BrowserOwningExecutor(boundary=boundary)
                supervisor = _supervisor(
                    journal=journal,
                    leases=leases,
                    operands=operands,
                    executor=executor,
                )
                operation_id = "4" * 64
                await supervisor.submit(
                    OperationRequest[BaseModel](
                        definition_id=_DEFINITION_ID,
                        subject_ref="subject:sensitive-redirect",
                        payload=ResourceRequest(target_url=AEAT_CERTIFICATE_PROTECTED_URL),
                    ),
                    operation_id=operation_id,
                )
                terminal = await supervisor.start(operation_id)

                browser = executor.browser
                assert browser is not None
                assert terminal.lifecycle is OperationLifecycle.TERMINAL

                # Positive control on the transport: the executor genuinely
                # ended up holding the sensitive value, so its absence from
                # disk below is a real finding rather than a value that was
                # never in play.
                assert executor.final_url is not None
                assert boundary.sensitive_token in executor.final_url

                # The supervisor released the real runtime here too.
                assert browser.session_closed

                persisted = _durable_bytes(storage_root)

                # Positive control on the scan: it genuinely reads the durable
                # content, so the absence asserted next means something.
                assert operation_id.encode() in persisted

                # The sensitive value never reached any persisted byte.
                assert boundary.sensitive_token.encode() not in persisted

        asyncio.run(navigate_a_sensitive_redirect())
