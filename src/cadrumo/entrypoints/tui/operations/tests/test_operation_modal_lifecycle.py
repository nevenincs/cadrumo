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
from textual.widgets import Button, Static

from cadrumo.adapters.outbound.aeat.browser.factory import default_browser_session_factory
from cadrumo.adapters.persistence.storage.certificate_secret_backend import build_certificate_secret_backend
from cadrumo.adapters.persistence.storage.operator_scope import build_operator_scope_ports
from cadrumo.entrypoints.adapter_composition import build_censal_fetch_port, build_verification_repository_bundle

from .....adapters.persistence.operations.journal import OperationJournalRepository
from .....adapters.persistence.operations.lease import OperationLeaseFilesystemRepository
from .....adapters.persistence.operations.secure_references import operation_secure_reference_repository
from .....adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from .....adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
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
from .....application.operations.frontend_projection import (
    OperationPublicProjectionV1,
    OperationReviewAvailableInteractionV1,
)
from .....application.operations.frontend_requests import (
    OperationObservationSuccessV1,
    OperationResponseApplyRequestV1,
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
from .....core.operations import (
    OperationClosePolicy,
    OperationEffect,
    OperationLifecycle,
    OperationTerminalCondition,
)
from .....core.time.clock import now
from .....domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from .....domain.user_profile.values import UserProfileFact
from .....tests.aeat_literal_fixtures import aeat_url
from ....operation_composition import build_auth_operation_ports
from ..controller import OperationController
from ..modal import OperationModal, OperationModalDetachedOutcomeV1, OperationModalOutcomeV1

_OPERATOR_SCOPE_PORTS = build_operator_scope_ports()

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_CREDENTIAL_INPUT = "operation-modal-lifecycle-passphrase"
_ACTOR: OperationActorReference = "operator:operation-modal-lifecycle"
_UI_DEADLINE_SECONDS = 60.0
"""How long a rendered condition may take to appear.

A wall-clock bound, not a count of pilot pauses: a pause is one message-pump
turn, and on a loaded host a few hundred of them elapse before the modal's
timed poll has run even once."""
_POLL_PAUSE_SECONDS = 0.02
_POLL_INTERVAL_SECONDS = 0.2
"""The modal's own observation interval, which liveness is measured in."""
_RESPONSE_LIVENESS_POLLS = 12
"""How many of the modal's polls a pending REVIEW must survive.

One is what the defect offered. A dozen spans well over two seconds of
real operator time, which is the scale at which the affordance either
holds or does not."""
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
) -> Generator[tuple[OperationComposedServices, OperationRegistry, UUID, PinnedAuthorityOperation]]:
    """One production-shaped registry, journal, lease, and custody set.

    The registry is composed from the production definition factories only:
    the auth family, the censal REVIEW operation, and the modelo verification
    operation, which is the tree's one registered ``REQUEST_CANCEL`` close
    policy and therefore the only real definition that can prove a close
    refusal.
    """

    async def acquire_censo() -> CensalOperationAcquisition:
        return CensalOperationAcquisition(observation=_observation())

    with (
        isolated_profile_storage_root(tmp_path=tmp_path) as root,
        bundled_indexed_authority().operation() as authority_operation,
    ):
        enrolled = register_profile_with_credentials(
            label="Operation modal lifecycle subject",
            passphrase=_CREDENTIAL_INPUT,
            facts=(UserProfileFact(path="identity.tax_id", value="12345678Z"),),
            profile_create_context=authority_operation.profile_create_context(),
            profile_decode_context=authority_operation.profile_decode_context(),
        )
        profile_id = UUID(enrolled.profile_id)
        initial_login = login_profile(
            name=enrolled.profile_id,
            passphrase_callback=lambda: _CREDENTIAL_INPUT,
            profile_decode_context=authority_operation.profile_decode_context(),
        )
        auth_definitions = build_auth_operation_definitions(
            ports=build_auth_operation_ports(), profile_login=lambda **_kwargs: initial_login
        )
        auth_registrations = build_auth_operation_registrations(auth_definitions)
        censal_definition = build_censal_operation_definition(
            certificate_secret_backend_factory=build_certificate_secret_backend,
            browser_session_factory=default_browser_session_factory,
            acquire=acquire_censo,
            before_irreversible_section=before_irreversible_section,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            censal_fetch_port=build_censal_fetch_port(),
        )
        verify_definition = build_modelo_work_verify_definition(
            certificate_secret_backend_factory=build_certificate_secret_backend,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            verification_repository_bundle_factory=build_verification_repository_bundle,
        )
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
                authority_operation=authority_operation,
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
                yield services, registry, profile_id, authority_operation
            finally:
                asyncio.run(services.shutdown())


async def _submit_censal_review(
    services: OperationComposedServices,
    profile_id: UUID,
    authority_operation: PinnedAuthorityOperation,
) -> OperationSubmission:
    record = ProfileRecordRepository.for_current_session(
        profile_id,
        profile_decode_context=authority_operation.profile_decode_context(),
    ).load(profile_id)
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


async def _advance_to_pending_review(
    services: OperationComposedServices, controller: OperationController
) -> OperationReviewAvailableInteractionV1:
    """Start the operation and return its REVIEW once the executor has stopped at it.

    The supervisor's own settlement wait returns when the executor stops at
    its review checkpoint, so nothing here depends on how fast the host is.
    """
    await controller.start()
    await services.submission.settled(controller.operation_id)
    pending = (await _project(controller)).pending_interaction
    assert isinstance(pending, OperationReviewAvailableInteractionV1), (
        "the censal REVIEW operation stopped without a pending interaction"
    )
    return pending


async def _settle(services: OperationComposedServices, controller: OperationController) -> OperationPublicProjectionV1:
    """Wait on the supervisor until the operation is terminal, then project it.

    A settlement wait can first return the executor's earlier stop at its
    review checkpoint; the next wait is then the continuation's own.
    """
    for _ in range(3):
        await services.submission.settled(controller.operation_id)
        projection = await _project(controller)
        if projection.lifecycle is OperationLifecycle.TERMINAL:
            return projection
    message = f"the operation was not terminal after its settlement completed: {projection.lifecycle}"
    raise AssertionError(message)


async def _pilot_until(pilot: Pilot[None], condition: Callable[[], bool], message: str) -> None:
    """Let the host run until ``condition`` holds, failing after a wall-clock deadline."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + _UI_DEADLINE_SECONDS
    while not condition():
        if loop.time() > deadline:
            raise AssertionError(message)
        await pilot.pause(_POLL_PAUSE_SECONDS)


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
    """Settle the modal until the named control has been enabled by a poll.

    A control is enabled by default before the modal has folded any
    observation, so enablement only counts once an observation is folded.
    """
    await _pilot_until(
        pilot,
        lambda: modal._view_model is not None and not modal.query_one(selector, Button).disabled,
        f"the modal never enabled {selector} from a supervisor observation",
    )


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


async def _click(pilot: Pilot[None], selector: str) -> None:
    """Click a modal control exactly once, as an operator does, and require it to land.

    No retry: the modal keeps its actions still while rows fill, so a click
    aimed where a control was drawn must reach it. A miss is a layout defect.
    """
    landed = await pilot.click(selector)
    assert landed, f"a single click on {selector} missed: the control moved under the pointer"


async def _await_outcome(pilot: Pilot[None], host: _ModalHost, controller: OperationController) -> None:
    """Wait for the modal to return, naming the supervisor's state if it never does."""
    try:
        await _pilot_until(pilot, lambda: host.outcome is not None, "the modal never returned its outcome")
    except AssertionError:
        projection = await _project(controller)
        screen = host.screen
        refusal = (
            str(screen.query_one("#operation-modal-action-refusal", Static).content)
            + f" interaction={type(screen._interaction).__name__}"
            + f" apply_disabled={screen.query_one('#btn-operation-apply', Button).disabled}"
            + f" reject_disabled={screen.query_one('#btn-operation-reject', Button).disabled}"
            if isinstance(screen, OperationModal)
            else "<modal not shown>"
        ) + f" app_exception={host._exception!r}"
        message = (
            "the modal never returned its outcome; the supervisor holds the operation at "
            f"lifecycle={projection.lifecycle} terminal={projection.terminal_condition} "
            f"pending={type(projection.pending_interaction).__name__} "
            f"cancellation_requested={projection.cancellation_requested} revision={projection.revision}; "
            f"the modal's action refusal reads {refusal!r}"
        )
        raise AssertionError(message) from None


async def _pause_until_rendered(pilot: Pilot[None], host: _ModalHost) -> OperationModal:
    """Settle the host until the modal has folded its first observation."""
    await host.presented.wait()

    def folded() -> bool:
        # Read from the modal's own package-internal state, as this test
        # package's other modal tests do: before the first fold every control
        # still carries its default, so the rendered body alone proves nothing.
        screen = host.screen
        return isinstance(screen, OperationModal) and screen._view_model is not None

    await _pilot_until(pilot, folded, "the operation modal never folded a supervisor observation")
    screen = host.screen
    assert isinstance(screen, OperationModal)
    return screen


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
        authority_operation,
    ):

        async def run() -> None:
            submitted = await _submit_censal_review(services, profile_id, authority_operation)
            controller = OperationController(services=services, submission=submitted, actor_ref=_ACTOR)
            pending = await _advance_to_pending_review(services, controller)
            control = await controller.response_control(
                interaction_id=pending.interaction_id, revision=pending.revision
            )
            await control.apply(_apply_request(controller, pending))
            await reached_boundary.wait()

            host = _ModalHost(controller)
            async with host.run_test(size=(100, 40)) as pilot:
                modal = await _pause_until_rendered(pilot, host)
                assert modal.query_one("#btn-operation-detach", Button).disabled is False
                await _click(pilot, "#btn-operation-detach")
                await _await_outcome(pilot, host, controller)

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
            settled = await _settle(services, controller)
            assert settled.terminal_condition is OperationTerminalCondition.SUCCEEDED
            assert settled.effect is OperationEffect.UPDATED

        asyncio.run(run())


def test_close_is_refused_while_a_request_cancel_operation_is_live(tmp_path: Path) -> None:
    """A live non-detachable operation refuses close and is left untouched."""
    with _runtime(tmp_path) as (services, registry, profile_id, _authority_operation):

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
        authority_operation,
    ):

        async def run() -> None:
            submitted = await _submit_censal_review(services, profile_id, authority_operation)
            controller = OperationController(services=services, submission=submitted, actor_ref=_ACTOR)
            pending = await _advance_to_pending_review(services, controller)
            control = await controller.response_control(
                interaction_id=pending.interaction_id, revision=pending.revision
            )
            await control.apply(_apply_request(controller, pending))
            await reached_boundary.wait()

            host = _ModalHost(controller)
            async with host.run_test(size=(100, 40)) as pilot:
                modal = await _pause_until_rendered(pilot, host)
                await _await_enabled(pilot, modal, "#btn-operation-cancel")
                await _click(pilot, "#btn-operation-cancel")
                requested = None
                loop = asyncio.get_running_loop()
                deadline = loop.time() + _UI_DEADLINE_SECONDS
                while requested is None and loop.time() < deadline:
                    await pilot.pause(_POLL_PAUSE_SECONDS)
                    candidate = await _project(controller)
                    if candidate.cancellation_requested:
                        requested = candidate
                assert requested is not None, "the cancel control never reached the supervisor"
                # The executor is parked inside its own boundary. Cancellation
                # has been asked for and not yet granted, which is exactly the
                # state a modal that assumed ownership would have skipped.
                assert requested.lifecycle is not OperationLifecycle.TERMINAL
                assert requested.cancellation_acknowledged is False
                await host.action_quit()

            release_boundary.set()
            settled = await _settle(services, controller)
            assert settled.terminal_condition is OperationTerminalCondition.CANCELLED

        asyncio.run(run())


def test_apply_through_the_modal_settles_the_operation_as_applied(tmp_path: Path) -> None:
    """The apply control routes through the bound response authority alone."""
    with _runtime(tmp_path) as (services, _registry, profile_id, authority_operation):

        async def run() -> None:
            submitted = await _submit_censal_review(services, profile_id, authority_operation)
            controller = OperationController(services=services, submission=submitted, actor_ref=_ACTOR)
            await _advance_to_pending_review(services, controller)

            host = _ModalHost(controller)
            async with host.run_test(size=(100, 40)) as pilot:
                modal = await _pause_until_rendered(pilot, host)
                await _await_enabled(pilot, modal, "#btn-operation-apply")
                await _click(pilot, "#btn-operation-apply")
                await _await_outcome(pilot, host, controller)

            settled = await _settle(services, controller)
            assert settled.terminal_condition is OperationTerminalCondition.SUCCEEDED
            assert settled.effect is OperationEffect.UPDATED

        asyncio.run(run())


def test_reject_through_the_modal_settles_the_operation_without_an_effect(tmp_path: Path) -> None:
    """Reject settles the same operation with no effect on the profile record."""
    with _runtime(tmp_path) as (services, _registry, profile_id, authority_operation):

        async def run() -> None:
            submitted = await _submit_censal_review(services, profile_id, authority_operation)
            controller = OperationController(services=services, submission=submitted, actor_ref=_ACTOR)
            await _advance_to_pending_review(services, controller)

            host = _ModalHost(controller)
            async with host.run_test(size=(100, 40)) as pilot:
                modal = await _pause_until_rendered(pilot, host)
                first_drawn_at = modal.query_one("#btn-operation-reject", Button).region
                await _await_enabled(pilot, modal, "#btn-operation-reject")
                # The rows filled between the first fold and enablement; the
                # control an operator aims at must not have moved meanwhile.
                assert modal.query_one("#btn-operation-reject", Button).region == first_drawn_at
                await _click(pilot, "#btn-operation-reject")
                await _await_outcome(pilot, host, controller)

            settled = await _settle(services, controller)
            assert settled.terminal_condition is OperationTerminalCondition.SUCCEEDED
            assert settled.effect is OperationEffect.NONE

        asyncio.run(run())


def test_the_response_controls_stay_live_across_many_polls_while_a_review_waits(tmp_path: Path) -> None:
    """Apply and reject remain offered for as long as the REVIEW is pending.

    The defect this pins offered both controls for exactly one poll and then
    switched them off permanently, at an unchanged revision, while the
    supervisor still waited for the answer. A proof that sampled the controls
    once would have passed against that behaviour, so this one samples across
    many consecutive polls and requires every sample to be live.
    """
    with _runtime(tmp_path) as (services, _registry, profile_id, authority_operation):

        async def run() -> None:
            submitted = await _submit_censal_review(services, profile_id, authority_operation)
            controller = OperationController(services=services, submission=submitted, actor_ref=_ACTOR)
            await controller.start()

            host = _ModalHost(controller)
            async with host.run_test(size=(100, 40)) as pilot:
                modal = await _pause_until_rendered(pilot, host)
                await _await_enabled(pilot, modal, "#btn-operation-apply")

                # Span several poll intervals, not several message-pump
                # cycles: the modal re-resolves its interaction on a timed
                # poll, so a budget counted in pauses can elapse without a
                # single re-resolution having happened.
                observed_polls = 0
                samples: list[tuple[bool, bool]] = []
                deadline = _RESPONSE_LIVENESS_POLLS * _POLL_INTERVAL_SECONDS
                elapsed = 0.0
                while elapsed < deadline:
                    await asyncio.sleep(_POLL_INTERVAL_SECONDS / 2)
                    elapsed += _POLL_INTERVAL_SECONDS / 2
                    await pilot.pause()
                    projection = await _project(controller)
                    if projection.lifecycle is not OperationLifecycle.WAITING_FOR_INTERACTION:
                        break
                    observed_polls += 1
                    samples.append(
                        (
                            not modal.query_one("#btn-operation-apply", Button).disabled,
                            not modal.query_one("#btn-operation-reject", Button).disabled,
                        )
                    )

                assert observed_polls >= _RESPONSE_LIVENESS_POLLS, (
                    f"only {observed_polls} samples were taken while the REVIEW waited, "
                    "which is too few to distinguish a live control from a one-frame one"
                )
                dead = [
                    index for index, (apply_live, reject_live) in enumerate(samples) if not (apply_live and reject_live)
                ]
                assert not dead, (
                    f"the response controls went dead at sample(s) {dead} while the REVIEW was still pending; "
                    "the modal must not rebind a single-use response capability on every poll"
                )

                # Still answerable at the end, which is the operator-facing
                # claim: the affordance was not merely drawn, it still works.
                await _click(pilot, "#btn-operation-reject")
                await host.action_quit()

            settled = await _settle(services, controller)
            assert settled.terminal_condition is OperationTerminalCondition.SUCCEEDED
            assert settled.effect is OperationEffect.NONE

        asyncio.run(run())
