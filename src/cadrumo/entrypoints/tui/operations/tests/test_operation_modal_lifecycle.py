"""Real proofs that the operation modal never assumes it owns the process.

Every test here drives a genuine registered operation through the composed
production services and then exercises the installed Textual modal's detach,
close, apply, reject, and cancel paths. The property under test is ownership:
the modal is one attached viewer of a durable supervised operation, so closing
it, detaching from it, or asking it to cancel must never terminate the
operation, and the operation's own settlement must never depend on the modal
still being mounted.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Generator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast
from uuid import UUID

import pytest
from textual.app import App
from textual.pilot import Pilot
from textual.widgets import Button

from .....adapters.persistence.operations.journal import OperationJournalRepository
from .....adapters.persistence.operations.lease import OperationLeaseFilesystemRepository
from .....adapters.persistence.operations.secure_references import operation_secure_reference_repository
from .....adapters.persistence.storage import SecureObjectRepository
from .....application.auth.operation_definitions import (
    build_auth_operation_definitions,
    build_auth_operation_registrations,
)
from .....application.modelo.operation_definitions import (
    MODELO_WORK_VERIFY_OPERATION_DEFINITION_ID,
    build_modelo_work_verify_definition,
    build_modelo_work_verify_registration,
)
from .....application.operations.composition import (
    OperationComposedServices,
    OperationSubmission,
    compose_operation_services,
)
from .....application.operations.frontend_contracts import (
    OperationObservationSuccessV1,
    OperationPublicProjectionV1,
    OperationResponseApplyRequestV1,
    OperationReviewAvailableInteractionV1,
)
from .....application.operations.interactions import OperationActorReference
from .....application.operations.models import OperationRequest
from .....application.operations.registry import OperationRegistry
from .....application.user_profile.censal_observation import (
    CensalObservation,
    CensalObservationAddress,
    CensalObservationIdentity,
)
from .....application.user_profile.censal_operation import (
    CensalOperationAcquisition,
    build_censal_operation_definition,
    build_censal_operation_registration,
    build_censal_operation_request,
)
from .....application.user_profile.custody_ports import profile_custody_secure_object_repository
from .....application.user_profile.login_session import login_profile
from .....application.user_profile.profile_record_repository import ProfileRecordRepository
from .....application.user_profile.registration import register_profile_with_credentials
from .....core import OperationClosePolicy, OperationEffect, OperationLifecycle, OperationTerminalCondition
from .....core.time import now
from .....domain.user_profile.values import UserProfileFact
from .....tests.aeat_literal_fixtures import aeat_url
from .....tests.secure_sql import isolated_profile_storage_root
from ..controller import OperationController
from ..modal import OperationModal, OperationModalDetachedOutcomeV1, OperationModalOutcomeV1

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_PASSPHRASE = "operation-modal-lifecycle-passphrase"  # noqa: S105 - isolated integration fixture
_ACTOR: OperationActorReference = "operator:operation-modal-lifecycle"
_TERMINAL_POLL_BUDGET = 400
_POLL_PAUSE_SECONDS = 0.02
_WORKER_DRAIN_SECONDS = 0.5


def _observation() -> CensalObservation:
    return CensalObservation(
        identity=CensalObservationIdentity(nif="12345678Z"),
        domicilio_fiscal=CensalObservationAddress(
            tipo_via="CALLE",
            nombre_via="Mayor",
            numero_casa="7",
            codigo_postal="28013",
            referencia_catastral="1234567VK4713C0001AB",
        ),
        domicilio_notificacion=CensalObservationAddress(),
        captured_at=datetime(2026, 8, 24, 18, tzinfo=UTC),
        source_url=aeat_url("sede", "/censo/consulta"),
    )


@contextmanager
def _runtime(
    tmp_path: Path,
    *,
    before_irreversible_section: Callable[[], Awaitable[None]] | None = None,
) -> Generator[tuple[OperationComposedServices, OperationRegistry, UUID]]:
    """One production-shaped registry, journal, lease, and custody set.

    The registry is composed from the production definition factories only:
    the auth family, the censal REVIEW operation, and the modelo verification
    operation, which is the tree's one registered ``REQUEST_CANCEL`` close
    policy and therefore the only real definition that can prove a close
    refusal.
    """

    async def acquire_censo() -> CensalOperationAcquisition:
        return CensalOperationAcquisition(observation=_observation())

    with isolated_profile_storage_root(tmp_path=tmp_path) as root:
        enrolled = register_profile_with_credentials(
            label="Operation modal lifecycle subject",
            passphrase=_PASSPHRASE,
            facts=(UserProfileFact(path="identity.tax_id", value="12345678Z"),),
            recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic,
        )
        profile_id = UUID(enrolled.profile_id)
        initial_login = login_profile(name=enrolled.profile_id, passphrase_callback=lambda: _PASSPHRASE)
        auth_definitions = build_auth_operation_definitions(profile_login=lambda **_kwargs: initial_login)
        auth_registrations = build_auth_operation_registrations(auth_definitions)
        censal_definition = build_censal_operation_definition(
            acquire=acquire_censo,
            before_irreversible_section=before_irreversible_section,
        )
        verify_definition = build_modelo_work_verify_definition()
        registry = OperationRegistry(
            definitions=(*auth_definitions, censal_definition, verify_definition),
            public_registrations=tuple(
                sorted(
                    (
                        *auth_registrations,
                        build_censal_operation_registration(censal_definition),
                        build_modelo_work_verify_registration(verify_definition),
                    ),
                    key=lambda item: item.contract.definition_id,
                )
            ),
        )
        journal = OperationJournalRepository(storage_root=root / "operations")
        with profile_custody_secure_object_repository(profile_id=profile_id, dek=b"", root=root) as objects:
            services = compose_operation_services(
                registry=registry,
                journal=journal,
                reader=journal,
                event_stream=journal,
                leases=OperationLeaseFilesystemRepository(storage_root=root / "operations"),
                operands=operation_secure_reference_repository(objects=cast(SecureObjectRepository, objects)),
                owner_id="1" * 64,
                lease_token_factory=lambda: "2" * 64,
                clock=now,
                lease_duration=timedelta(minutes=10),
                execution_timeout=timedelta(hours=1),
                cleanup_timeout=timedelta(minutes=2),
            )
            try:
                yield services, registry, profile_id
            finally:
                asyncio.run(services.shutdown())


async def _submit_censal_review(services: OperationComposedServices, profile_id: UUID) -> OperationSubmission:
    record = ProfileRecordRepository.for_current_session(profile_id).load(profile_id)
    return await services.submission.submit(
        OperationRequest(
            definition_id="user-profile.censo-review",
            subject_ref=str(profile_id),
            payload=build_censal_operation_request(record),
        ),
        actor_ref=_ACTOR,
    )


async def _submit_modelo_verify(
    services: OperationComposedServices,
    registry: OperationRegistry,
    profile_id: UUID,
) -> OperationSubmission:
    """Submit, but never start, the tree's one request-cancel operation."""
    definition = registry.lookup(MODELO_WORK_VERIFY_OPERATION_DEFINITION_ID)
    payload = definition.request_type.model_validate(
        {"calculation_revision_id": "revision-under-modal-lifecycle-proof", "actor": _ACTOR},
        strict=True,
    )
    return await services.submission.submit(
        OperationRequest(
            definition_id=MODELO_WORK_VERIFY_OPERATION_DEFINITION_ID,
            subject_ref=f"profile:{profile_id}",
            payload=payload,
        ),
        actor_ref=_ACTOR,
    )


async def _project(controller: OperationController) -> OperationPublicProjectionV1:
    observed = await controller.observe(0)
    assert isinstance(observed, OperationObservationSuccessV1)
    return observed.projection


async def _advance_to_pending_review(controller: OperationController) -> OperationReviewAvailableInteractionV1:
    await controller.start()
    for _ in range(_TERMINAL_POLL_BUDGET):
        pending = (await _project(controller)).pending_interaction
        if isinstance(pending, OperationReviewAvailableInteractionV1):
            return pending
        await asyncio.sleep(_POLL_PAUSE_SECONDS)
    message = "the censal REVIEW operation never reached a pending interaction"
    raise AssertionError(message)


async def _settle(controller: OperationController) -> OperationPublicProjectionV1:
    for _ in range(_TERMINAL_POLL_BUDGET):
        projection = await _project(controller)
        if projection.lifecycle is OperationLifecycle.TERMINAL:
            return projection
        await asyncio.sleep(_POLL_PAUSE_SECONDS)
    message = "the operation never settled within the bounded poll budget"
    raise AssertionError(message)


def _apply_request(
    controller: OperationController,
    pending: OperationReviewAvailableInteractionV1,
) -> OperationResponseApplyRequestV1:
    """Build the exact apply request the modal's own apply path builds."""
    return OperationResponseApplyRequestV1(
        operation_id=controller.operation_id,
        interaction_id=pending.interaction_id,
        revision=pending.revision,
        actor_ref=_ACTOR,
        responded_at=now(),
    )


async def _await_enabled(pilot: Pilot[None], modal: OperationModal, selector: str) -> None:
    """Settle the modal until the named control has been enabled by a poll."""
    for _ in range(_TERMINAL_POLL_BUDGET):
        if not modal.query_one(selector, Button).disabled:
            return
        await pilot.pause()
    message = f"the modal never enabled {selector} from a supervisor observation"
    raise AssertionError(message)


class _ModalHost(App[None]):
    """Minimal host presenting exactly one operation modal, as production does."""

    def __init__(self, controller: OperationController) -> None:
        super().__init__()
        self._controller = controller
        self.outcome: OperationModalOutcomeV1 | None = None
        self.presented = asyncio.Event()

    async def _present(self) -> None:
        self.presented.set()
        self.outcome = await self.push_screen_wait(OperationModal(self._controller))
        # A modal that has returned its outcome no longer has a host to be
        # attached to; leaving the app running would hold the harness open
        # while the operation it was watching is still legitimately live.
        self.exit()

    def on_mount(self) -> None:
        self.run_worker(self._present())


async def _pause_until_rendered(pilot: Pilot[None], host: _ModalHost) -> OperationModal:
    """Settle the host until the modal has folded its first observation."""
    await host.presented.wait()
    for _ in range(_TERMINAL_POLL_BUDGET):
        await pilot.pause()
        screen = host.screen
        if isinstance(screen, OperationModal) and screen.is_mounted:
            status = screen.query_one("#operation-modal-status")
            if status.is_mounted:
                return screen
    message = "the operation modal never mounted its rendered body"
    raise AssertionError(message)


def test_detach_closes_the_modal_while_the_operation_keeps_running(tmp_path: Path) -> None:
    """Detaching returns the frontend but leaves the operation running durably."""
    reached_boundary = asyncio.Event()
    release_boundary = asyncio.Event()

    async def before_irreversible_section() -> None:
        reached_boundary.set()
        await release_boundary.wait()

    with _runtime(tmp_path, before_irreversible_section=before_irreversible_section) as (
        services,
        _registry,
        profile_id,
    ):

        async def run() -> None:
            submitted = await _submit_censal_review(services, profile_id)
            controller = OperationController(services=services, submission=submitted, actor_ref=_ACTOR)
            pending = await _advance_to_pending_review(controller)
            control = await controller.response_control(
                interaction_id=pending.interaction_id, revision=pending.revision
            )
            await control.apply(_apply_request(controller, pending))
            await reached_boundary.wait()

            host = _ModalHost(controller)
            async with host.run_test(size=(100, 40)) as pilot:
                modal = await _pause_until_rendered(pilot, host)
                assert modal.query_one("#btn-operation-detach", Button).disabled is False
                await pilot.click("#btn-operation-detach")
                for _ in range(_TERMINAL_POLL_BUDGET):
                    if host.outcome is not None:
                        break
                    await pilot.pause()

            # Let the dismissed modal's polling worker finish its in-flight
            # journal read before this test reads the same journal: the read
            # path takes a synchronous OS file lock, so overlapping the two
            # inside one event loop would stall the loop rather than queue.
            await asyncio.sleep(_WORKER_DRAIN_SECONDS)

            assert isinstance(host.outcome, OperationModalDetachedOutcomeV1)
            assert host.outcome.operation_id == controller.operation_id

            # The modal is gone. The operation must still be live and must
            # still settle on its own, with no attached frontend at all.
            detached_projection = await _project(controller)
            assert detached_projection.lifecycle is not OperationLifecycle.TERMINAL
            release_boundary.set()
            settled = await _settle(controller)
            assert settled.terminal_condition is OperationTerminalCondition.SUCCEEDED
            assert settled.effect is OperationEffect.UPDATED

        asyncio.run(run())


def test_close_is_refused_while_a_request_cancel_operation_is_live(tmp_path: Path) -> None:
    """A live non-detachable operation refuses close and is left untouched."""
    with _runtime(tmp_path) as (services, registry, profile_id):

        async def run() -> None:
            submitted = await _submit_modelo_verify(services, registry, profile_id)
            controller = OperationController(services=services, submission=submitted, actor_ref=_ACTOR)
            before = await _project(controller)
            assert before.close_policy is OperationClosePolicy.REQUEST_CANCEL
            assert before.lifecycle is not OperationLifecycle.TERMINAL

            host = _ModalHost(controller)
            async with host.run_test(size=(100, 40)) as pilot:
                modal = await _pause_until_rendered(pilot, host)
                assert modal.query_one("#btn-operation-detach", Button).disabled is True
                assert modal.query_one("#btn-operation-close", Button).disabled is True
                await pilot.press("escape")
                for _ in range(20):
                    await pilot.pause()
                still_mounted = isinstance(host.screen, OperationModal)
                await host.action_quit()

            assert still_mounted, "escape closed a modal bound to a live non-detachable operation"
            assert host.outcome is None

            after = await _project(controller)
            assert after.lifecycle is not OperationLifecycle.TERMINAL
            assert after.cancellation_requested is False
            assert after.revision == before.revision

        asyncio.run(run())


def test_cancel_requests_cooperative_stopping_without_terminating_the_operation(tmp_path: Path) -> None:
    """The cancel control asks; it never assumes the power to stop the process."""
    reached_boundary = asyncio.Event()
    release_boundary = asyncio.Event()

    async def before_irreversible_section() -> None:
        reached_boundary.set()
        await release_boundary.wait()

    with _runtime(tmp_path, before_irreversible_section=before_irreversible_section) as (
        services,
        _registry,
        profile_id,
    ):

        async def run() -> None:
            submitted = await _submit_censal_review(services, profile_id)
            controller = OperationController(services=services, submission=submitted, actor_ref=_ACTOR)
            pending = await _advance_to_pending_review(controller)
            control = await controller.response_control(
                interaction_id=pending.interaction_id, revision=pending.revision
            )
            await control.apply(_apply_request(controller, pending))
            await reached_boundary.wait()

            host = _ModalHost(controller)
            async with host.run_test(size=(100, 40)) as pilot:
                modal = await _pause_until_rendered(pilot, host)
                for _ in range(_TERMINAL_POLL_BUDGET):
                    if not modal.query_one("#btn-operation-cancel", Button).disabled:
                        break
                    await pilot.pause()
                assert modal.query_one("#btn-operation-cancel", Button).disabled is False
                await pilot.click("#btn-operation-cancel")
                requested = None
                for _ in range(_TERMINAL_POLL_BUDGET):
                    await pilot.pause()
                    candidate = await _project(controller)
                    if candidate.cancellation_requested:
                        requested = candidate
                        break
                assert requested is not None, "the cancel control never reached the supervisor"
                # The executor is parked inside its own boundary. Cancellation
                # has been asked for and not yet granted, which is exactly the
                # state a modal that assumed ownership would have skipped.
                assert requested.lifecycle is not OperationLifecycle.TERMINAL
                assert requested.cancellation_acknowledged is False
                await host.action_quit()

            release_boundary.set()
            settled = await _settle(controller)
            assert settled.terminal_condition is OperationTerminalCondition.CANCELLED

        asyncio.run(run())


def test_apply_through_the_modal_settles_the_operation_as_applied(tmp_path: Path) -> None:
    """The apply control routes through the bound response authority alone."""
    with _runtime(tmp_path) as (services, _registry, profile_id):

        async def run() -> None:
            submitted = await _submit_censal_review(services, profile_id)
            controller = OperationController(services=services, submission=submitted, actor_ref=_ACTOR)
            await _advance_to_pending_review(controller)

            host = _ModalHost(controller)
            async with host.run_test(size=(100, 40)) as pilot:
                modal = await _pause_until_rendered(pilot, host)
                await _await_enabled(pilot, modal, "#btn-operation-apply")
                await pilot.click("#btn-operation-apply")
                for _ in range(_TERMINAL_POLL_BUDGET):
                    if host.outcome is not None:
                        break
                    await pilot.pause()

            settled = await _settle(controller)
            assert settled.terminal_condition is OperationTerminalCondition.SUCCEEDED
            assert settled.effect is OperationEffect.UPDATED

        asyncio.run(run())


def test_reject_through_the_modal_settles_the_operation_without_an_effect(tmp_path: Path) -> None:
    """Reject settles the same operation with no effect on the profile record."""
    with _runtime(tmp_path) as (services, _registry, profile_id):

        async def run() -> None:
            submitted = await _submit_censal_review(services, profile_id)
            controller = OperationController(services=services, submission=submitted, actor_ref=_ACTOR)
            await _advance_to_pending_review(controller)

            host = _ModalHost(controller)
            async with host.run_test(size=(100, 40)) as pilot:
                modal = await _pause_until_rendered(pilot, host)
                await _await_enabled(pilot, modal, "#btn-operation-reject")
                await pilot.click("#btn-operation-reject")
                for _ in range(_TERMINAL_POLL_BUDGET):
                    if host.outcome is not None:
                        break
                    await pilot.pause()

            settled = await _settle(controller)
            assert settled.terminal_condition is OperationTerminalCondition.SUCCEEDED
            assert settled.effect is OperationEffect.NONE

        asyncio.run(run())
