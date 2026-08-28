"""Real end-to-end proofs for the generic detachable operation modal.

Every test drives a genuine registered operation through the composed
production services (real journal, real leases, real profile custody), then
proves the TUI-facing controller, projection, log, and interaction modules
never see more than the public frontend contracts C0 already froze.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Generator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast
from uuid import UUID

import pytest
from pydantic import ValidationError
from textual.app import App
from textual.pilot import Pilot
from textual.widgets import Button, Static

from .....adapters.persistence.operations.journal import OperationJournalRepository
from .....adapters.persistence.operations.lease import OperationLeaseFilesystemRepository
from .....adapters.persistence.operations.secure_references import operation_secure_reference_repository
from .....adapters.persistence.storage import SecureObjectRepository
from .....application.auth.operation_definitions import (
    build_auth_operation_definitions,
    build_auth_operation_registrations,
)
from .....application.operations.composition import (
    OperationComposedServices,
    OperationSubmission,
    compose_operation_services,
)
from .....application.operations.frontend_contracts import (
    OperationCancellationSuccessV1,
    OperationDetachSuccessV1,
    OperationObservationSuccessV1,
    OperationPublicEventPageV1,
    OperationResponseApplyRequestV1,
    OperationResponseMutationSuccessV1,
    OperationReviewAvailableInteractionV1,
    OperationReviewProjectionRefusalV1,
)
from .....application.operations.interactions import OperationActorReference
from .....application.operations.models import OperationRequest, OperationRevision
from .....application.operations.persistence.replay import OperationReplayStatus
from .....application.operations.registry import OperationRegistry
from .....application.user_profile.censal_observation import (
    CensalObservation,
    CensalObservationAddress,
    CensalObservationIdentity,
)
from .....application.user_profile.censal_operation import (
    CensalOperationAcquisition,
    CensalReviewProjectionV1,
    build_censal_operation_definition,
    build_censal_operation_registration,
    build_censal_operation_request,
)
from .....application.user_profile.custody_ports import profile_custody_secure_object_repository
from .....application.user_profile.login_session import login_profile
from .....application.user_profile.profile_record_repository import ProfileRecordRepository
from .....application.user_profile.registration import register_profile_with_credentials
from .....core import OperationEffect, OperationLifecycle, OperationTerminalCondition
from .....core.config import override_settings
from .....core.i18n import clear_output_language_cache
from .....core.time import now
from .....domain.user_profile.values import UserProfileFact
from .....tests.aeat_literal_fixtures import aeat_url
from .....tests.secure_sql import isolated_profile_storage_root
from ..controller import OperationController
from ..interactions import (
    OperationModalReviewInteractionV1,
    resolve_modal_interaction_state,
)
from ..logs import build_initial_log_view, fold_event_page
from ..modal import OperationModal, OperationModalDetachedOutcomeV1, OperationModalSettledOutcomeV1
from ..projection import OperationModalViewModelV1, build_operation_modal_view_model

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_PASSPHRASE = "operation-modal-conformance-passphrase"  # noqa: S105 - isolated integration fixture
_ACTOR: OperationActorReference = "operator:operation-modal-conformance"


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
    """One real production-shaped registry, journal, lease, and custody set."""

    async def acquire_censo() -> CensalOperationAcquisition:
        return CensalOperationAcquisition(observation=_observation())

    with isolated_profile_storage_root(tmp_path=tmp_path) as root:
        enrolled = register_profile_with_credentials(
            label="Operation modal conformance subject",
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
        registry = OperationRegistry(
            definitions=(*auth_definitions, censal_definition),
            public_registrations=tuple(
                sorted(
                    (*auth_registrations, build_censal_operation_registration(censal_definition)),
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
    payload = build_censal_operation_request(record)
    return await services.submission.submit(
        OperationRequest(
            definition_id="user-profile.censo-review",
            subject_ref=str(profile_id),
            payload=payload,
        ),
        actor_ref=_ACTOR,
    )


def test_controller_drives_a_review_operation_to_public_terminal_settlement(tmp_path: Path) -> None:
    """One real REVIEW operation, projected, interacted with, and settled."""
    with _runtime(tmp_path) as (services, _registry, profile_id):

        async def run() -> None:
            submitted = await _submit_censal_review(services, profile_id)
            controller = OperationController(services=services, submission=submitted, actor_ref=_ACTOR)
            await controller.start()

            log_view = build_initial_log_view(controller.operation_id)
            observed = await controller.observe(log_view.next_cursor)
            assert isinstance(observed, OperationObservationSuccessV1)
            log_view = fold_event_page(log_view, observed.event_page)
            assert log_view.next_cursor >= observed.event_page.anchor_cursor or log_view.rows

            projection = observed.projection
            assert projection.lifecycle is OperationLifecycle.WAITING_FOR_INTERACTION
            view_model = build_operation_modal_view_model(projection)
            assert view_model.interaction_affordance == "review_available"
            assert view_model.spinner_visible is True

            interaction = await resolve_modal_interaction_state(controller, projection)
            assert isinstance(interaction, OperationModalReviewInteractionV1)
            assert isinstance(interaction.projection, CensalReviewProjectionV1)
            assert interaction.apply_enabled is True
            assert interaction.reject_enabled is True

            pending = interaction.interaction
            assert isinstance(pending, OperationReviewAvailableInteractionV1)
            control = interaction.control
            applied = await control.apply(
                OperationResponseApplyRequestV1(
                    operation_id=controller.operation_id,
                    interaction_id=pending.interaction_id,
                    revision=pending.revision,
                    actor_ref=_ACTOR,
                    responded_at=now(),
                )
            )
            assert isinstance(applied, OperationResponseMutationSuccessV1)

            terminal_view_model = None
            for _ in range(200):
                observed = await controller.observe(log_view.next_cursor)
                assert isinstance(observed, OperationObservationSuccessV1)
                log_view = fold_event_page(log_view, observed.event_page)
                if observed.projection.lifecycle is OperationLifecycle.TERMINAL:
                    terminal_view_model = build_operation_modal_view_model(observed.projection)
                    break
                await asyncio.sleep(0)
            assert terminal_view_model is not None
            assert terminal_view_model.spinner_visible is False
            assert terminal_view_model.cancel_control_enabled is False
            assert terminal_view_model.detach_control_enabled is False
            assert terminal_view_model.terminal_copy_key == "operation.modal.terminal.succeeded"
            assert terminal_view_model.projection.effect is OperationEffect.UPDATED
            assert len(log_view.rows) > 0

        asyncio.run(run())


def test_controller_cooperative_cancellation_settles_with_public_acknowledgement(tmp_path: Path) -> None:
    """Cancel a genuinely running operation and observe its public settlement."""
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
            await controller.start()

            waiting = await controller.observe(0)
            assert isinstance(waiting, OperationObservationSuccessV1)
            pending = waiting.projection.pending_interaction
            assert isinstance(pending, OperationReviewAvailableInteractionV1)
            control = await controller.response_control(
                interaction_id=pending.interaction_id, revision=pending.revision
            )

            await control.apply(
                OperationResponseApplyRequestV1(
                    operation_id=controller.operation_id,
                    interaction_id=pending.interaction_id,
                    revision=pending.revision,
                    actor_ref=_ACTOR,
                    responded_at=now(),
                )
            )
            await reached_boundary.wait()
            running = await controller.observe(0)
            assert isinstance(running, OperationObservationSuccessV1)
            running_view_model = build_operation_modal_view_model(running.projection)
            assert running_view_model.cancel_control_enabled is True

            result = await controller.cancel(expected_revision=running.projection.revision)
            assert isinstance(result, OperationCancellationSuccessV1)
            assert result.cancellation_acknowledged is False
            release_boundary.set()

            terminal_view_model = None
            for _ in range(200):
                observed = await controller.observe(0)
                assert isinstance(observed, OperationObservationSuccessV1)
                if observed.projection.lifecycle is OperationLifecycle.TERMINAL:
                    terminal_view_model = build_operation_modal_view_model(observed.projection)
                    break
                await asyncio.sleep(0)
            assert terminal_view_model is not None
            assert terminal_view_model.projection.terminal_condition is OperationTerminalCondition.CANCELLED
            assert terminal_view_model.terminal_copy_key == "operation.modal.terminal.cancelled"

        asyncio.run(run())


def test_controller_detach_returns_the_public_detach_success(tmp_path: Path) -> None:
    """Detach a detach-allowed operation through the controller's narrow door."""
    with _runtime(tmp_path) as (services, registry, profile_id):

        async def run() -> None:
            # Resolve the exact request payload from the live registry rather
            # than guessing its shape.
            definition = registry.lookup("auth.session.reset")
            payload = definition.request_type.model_validate({"all_providers": True}, strict=True)
            submitted = await services.submission.submit(
                OperationRequest(
                    definition_id="auth.session.reset",
                    subject_ref=f"profile:{profile_id}",
                    payload=payload,
                ),
                actor_ref=_ACTOR,
            )
            controller = OperationController(services=services, submission=submitted, actor_ref=_ACTOR)
            before_start = await controller.observe(0)
            assert isinstance(before_start, OperationObservationSuccessV1)
            view_model = build_operation_modal_view_model(before_start.projection)
            assert view_model.detach_control_enabled is True

            result = await controller.detach(expected_revision=before_start.projection.revision)
            assert isinstance(result, OperationDetachSuccessV1)

        asyncio.run(run())


def test_fold_event_page_resynchronizes_and_then_replays_cursor_forward() -> None:
    """A resynchronizing page clears stale rows; a following page replays forward."""
    initial = build_initial_log_view("a" * 64)
    resync_page = OperationPublicEventPageV1(
        operation_id=initial.operation_id,
        anchor_cursor=50,
        requested_cursor=0,
        status=OperationReplayStatus.EXPIRED,
        events=(),
        next_cursor=50,
        restart_cursor=50,
    )
    resynchronized = fold_event_page(initial, resync_page)
    assert resynchronized.resynchronized is True
    assert resynchronized.rows == ()
    assert resynchronized.next_cursor == 50

    caught_up_page = OperationPublicEventPageV1(
        operation_id=initial.operation_id,
        anchor_cursor=50,
        requested_cursor=50,
        status=OperationReplayStatus.CAUGHT_UP,
        events=(),
        next_cursor=50,
        restart_cursor=None,
    )
    replayed = fold_event_page(resynchronized, caught_up_page)
    assert replayed.resynchronized is False
    assert replayed.status == "caught_up"
    assert replayed.next_cursor == 50


def test_review_unavailable_disposition_for_a_stale_reference(tmp_path: Path) -> None:
    """A REVIEW reference belonging to a different revision resolves as unavailable."""
    with _runtime(tmp_path) as (services, _registry, profile_id):

        async def run() -> None:
            submitted = await _submit_censal_review(services, profile_id)
            controller = OperationController(services=services, submission=submitted, actor_ref=_ACTOR)
            await controller.start()
            waiting = await controller.observe(0)
            assert isinstance(waiting, OperationObservationSuccessV1)
            pending = waiting.projection.pending_interaction
            assert isinstance(pending, OperationReviewAvailableInteractionV1)
            stale_reference = pending.review_reference.model_copy(update={"revision": pending.revision + 1})
            resolved = await controller.resolve_review(stale_reference)

            assert isinstance(resolved, OperationReviewProjectionRefusalV1)

        asyncio.run(run())


async def _run_modal_to_settlement(controller: OperationController) -> None:
    class _Host(App[None]):
        outcome: object = None

        async def _present(self) -> None:
            self.outcome = await self.push_screen_wait(OperationModal(controller))
            self.exit()

        def on_mount(self) -> None:
            self.run_worker(self._present())

    app = _Host()
    async with app.run_test(size=(100, 40)) as pilot:
        for _ in range(500):
            if app.outcome is not None:
                break
            await pilot.pause()
    assert isinstance(app.outcome, OperationModalSettledOutcomeV1 | OperationModalDetachedOutcomeV1)


def test_installed_modal_settles_a_real_operation_end_to_end(tmp_path: Path) -> None:
    """The installed Textual modal drives a real REVIEW operation to settlement."""
    with _runtime(tmp_path) as (services, _registry, profile_id):

        async def run() -> None:
            submitted = await _submit_censal_review(services, profile_id)
            controller = OperationController(services=services, submission=submitted, actor_ref=_ACTOR)
            await controller.start()
            waiting = await controller.observe(0)
            assert isinstance(waiting, OperationObservationSuccessV1)
            pending = waiting.projection.pending_interaction
            assert isinstance(pending, OperationReviewAvailableInteractionV1)
            control = await controller.response_control(
                interaction_id=pending.interaction_id, revision=pending.revision
            )

            await control.apply(
                OperationResponseApplyRequestV1(
                    operation_id=controller.operation_id,
                    interaction_id=pending.interaction_id,
                    revision=pending.revision,
                    actor_ref=_ACTOR,
                    responded_at=now(),
                )
            )
            await _run_modal_to_settlement(controller)

        asyncio.run(run())


@dataclass(frozen=True, slots=True)
class _RenderedSample:
    """One reading of the modal's widgets beside the revision that produced it.

    Sampling the revision and the widgets together is what makes the
    monotonicity claim checkable: a reading of the widgets alone cannot say
    which supervisor state it is a rendering of.
    """

    revision: OperationRevision
    status: str
    phase: str
    deadlines: str
    diagnostic: str
    receipt: str
    review: str
    log: str
    cancel_enabled: bool


def _sample(modal: OperationModal) -> _RenderedSample | None:
    """Read every declared fact off the live widgets, or None before the first poll."""
    # Read from the modal's own package-internal state: this test lives in
    # the modal's test package, and the revision a frame was drawn from is
    # not exposed on any widget.
    view_model = modal._view_model
    if view_model is None:
        return None
    # A dismissed modal reports itself mounted for a beat after its widget
    # tree has gone, so presence of the body is the reliable guard.
    if not modal.query("#operation-modal-status"):
        return None

    def _text(widget_id: str) -> str:
        return str(modal.query_one(widget_id, Static).content)

    return _RenderedSample(
        revision=view_model.projection.revision,
        status=_text("#operation-modal-status"),
        phase=_text("#operation-modal-phase"),
        deadlines=_text("#operation-modal-deadlines"),
        diagnostic=_text("#operation-modal-diagnostic"),
        receipt=_text("#operation-modal-receipt"),
        review=_text("#operation-modal-review"),
        log=_text("#operation-modal-log"),
        cancel_enabled=not modal.query_one("#btn-operation-cancel", Button).disabled,
    )


async def _timeline(controller: OperationController) -> tuple[list[_RenderedSample], OperationModalViewModelV1]:
    """Drive the installed modal to settlement, sampling the widgets throughout.

    The pending REVIEW is answered by pressing the modal's own apply control
    once the modal enables it. It cannot be answered from outside: the
    response capability is single-use and the modal's poll loop has already
    bound it, so an out-of-band bind is refused. Answering it before the
    modal mounts would settle the operation first and leave nothing to
    sample, which is the difference between watching a lifecycle and
    watching one that has already finished.
    """
    samples: list[_RenderedSample] = []

    class _Host(App[None]):
        outcome: OperationModalSettledOutcomeV1 | OperationModalDetachedOutcomeV1 | None = None

        async def _present(self) -> None:
            self.outcome = await self.push_screen_wait(OperationModal(controller))
            self.exit()

        def on_mount(self) -> None:
            self.run_worker(self._present())

    host = _Host()
    applied = False
    modal: OperationModal | None = None

    def _record() -> None:
        # Sample the modal itself rather than whatever screen is current, so
        # a frame drawn just before the screen is swapped is still read.
        if modal is None:
            return
        sample = _sample(modal)
        if sample is not None and (not samples or sample != samples[-1]):
            samples.append(sample)

    async with host.run_test(size=(120, 40)) as pilot:
        for _ in range(600):
            screen = host.screen
            if isinstance(screen, OperationModal) and screen.is_mounted:
                modal = screen
            _record()
            apply_control = modal.query("#btn-operation-apply") if modal is not None else []
            if not applied and apply_control and not apply_control.only_one(Button).disabled:
                applied = True
                await pilot.click("#btn-operation-apply")
            if host.outcome is not None:
                break
            await pilot.pause()
    assert applied, "the modal never offered the apply control, so the REVIEW was never answered"

    assert isinstance(host.outcome, OperationModalSettledOutcomeV1), (
        f"the modal did not settle; last sample {samples[-1] if samples else None}"
    )
    assert samples, "the modal settled without ever rendering a supervisor revision"
    return samples, host.outcome.view_model


def test_the_modal_renders_every_declared_fact_across_one_real_operation(tmp_path: Path) -> None:
    """Spinner, phase, deadline, cancel availability, logs, review and receipt all reach a widget."""
    with _runtime(tmp_path) as (services, _registry, profile_id):

        async def run() -> None:
            submitted = await _submit_censal_review(services, profile_id)
            controller = OperationController(services=services, submission=submitted, actor_ref=_ACTOR)
            await controller.start()
            samples, settled = await _timeline(controller)

            assert any(sample.status for sample in samples), "the spinner or terminal copy never reached the status row"
            assert any(sample.phase for sample in samples), "no supervisor phase ever reached the phase row"
            assert any(sample.deadlines for sample in samples), "no deadline ever reached the deadline row"
            assert any(sample.log for sample in samples), "no live log line ever reached the log row"

            # Terminal receipts: the settled view model carries the result
            # reference, and the widget carried it in the final sample.
            assert settled.receipt_kind == "result"
            assert settled.receipt_ref is not None

            # Diagnostic detail: this operation succeeds, so the projection
            # carries no diagnostic and the row must be blank rather than
            # holding a value it was never given.
            assert settled.diagnostic_ref is None
            assert all(sample.diagnostic == "" for sample in samples)

        asyncio.run(run())


def test_the_modal_renders_review_content_and_cancel_availability_while_waiting(tmp_path: Path) -> None:
    """The REVIEW body and the cancel affordance are rendered from the live projection."""
    with _runtime(tmp_path) as (services, _registry, profile_id):

        async def run() -> None:
            submitted = await _submit_censal_review(services, profile_id)
            controller = OperationController(services=services, submission=submitted, actor_ref=_ACTOR)
            await controller.start()

            class _Host(App[None]):
                def on_mount(self) -> None:
                    self.run_worker(self.push_screen_wait(OperationModal(controller)))

            host = _Host()
            async with host.run_test(size=(120, 40)) as pilot:
                waiting_sample = None
                for _ in range(400):
                    await pilot.pause()
                    screen = host.screen
                    if not isinstance(screen, OperationModal) or not screen.is_mounted:
                        continue
                    sample = _sample(screen)
                    if sample is not None and sample.review:
                        waiting_sample = sample
                        break
                assert waiting_sample is not None, "the REVIEW content never reached the review row"
                observed = await controller.observe(0)
                assert isinstance(observed, OperationObservationSuccessV1)
                assert waiting_sample.cancel_enabled == observed.projection.cancellable_now
                await host.action_quit()

        asyncio.run(run())


def test_rendered_state_follows_supervisor_revisions_and_never_regresses(tmp_path: Path) -> None:
    """Every rendered change is a step forward in the supervisor's own revision."""
    with _runtime(tmp_path) as (services, _registry, profile_id):

        async def run() -> None:
            submitted = await _submit_censal_review(services, profile_id)
            controller = OperationController(services=services, submission=submitted, actor_ref=_ACTOR)
            await controller.start()
            samples, settled = await _timeline(controller)

            revisions = [sample.revision for sample in samples]
            assert revisions == sorted(revisions), f"the modal rendered a stale supervisor revision: {revisions}"
            assert len(set(revisions)) > 1, (
                "the operation never advanced a revision while the modal watched, so this proves nothing"
            )
            # No frame may run ahead of the settlement the modal returned.
            assert samples[-1].revision <= settled.projection.revision
            assert settled.projection.lifecycle is OperationLifecycle.TERMINAL

        asyncio.run(run())


def test_a_derived_field_that_disagrees_with_its_projection_is_refused(tmp_path: Path) -> None:
    """The view model cannot carry a fact its own projection does not state."""
    with _runtime(tmp_path) as (services, _registry, profile_id):

        async def run() -> None:
            submitted = await _submit_censal_review(services, profile_id)
            controller = OperationController(services=services, submission=submitted, actor_ref=_ACTOR)
            await controller.start()
            observed = await controller.observe(0)
            assert isinstance(observed, OperationObservationSuccessV1)
            honest = build_operation_modal_view_model(observed.projection)
            base = {name: getattr(honest, name) for name in type(honest).model_fields}

            divergences: dict[str, object] = {
                "phase_code": "operation.phase.the.projection.never.declared",
                "execution_deadline_at": datetime(2000, 1, 1, tzinfo=UTC),
                "cleanup_deadline_at": datetime(2000, 1, 1, tzinfo=UTC),
                "diagnostic_ref": "diagnostic-the-projection-never-carried",
                "receipt_kind": "result",
                "receipt_ref": "receipt-the-projection-never-carried",
            }
            for field, value in divergences.items():
                assert base[field] != value, f"{field} must actually diverge, or this proves nothing"
                with pytest.raises(ValidationError):
                    OperationModalViewModelV1.model_validate(base | {field: value})

        asyncio.run(run())


def test_the_terminal_receipt_reaches_the_receipt_widget(tmp_path: Path) -> None:
    """The settled receipt is drawn by the modal's own render path.

    The receipt cannot be read off a widget during the settling frame: the
    modal draws it and dismisses within a single pause, and the widget tree
    is gone by the time the pilot regains control. So a real operation is
    driven to settlement through the controller, its settled projection is
    turned into a view model by the production derivation, and that view
    model is handed to the modal's own render method on a mounted screen.
    The data and the renderer are both production; only the moment is the
    test's.
    """
    with _runtime(tmp_path) as (services, _registry, profile_id):

        async def run() -> None:
            submitted = await _submit_censal_review(services, profile_id)
            controller = OperationController(services=services, submission=submitted, actor_ref=_ACTOR)
            await controller.start()
            observed = await controller.observe(0)
            assert isinstance(observed, OperationObservationSuccessV1)
            pending = observed.projection.pending_interaction
            assert isinstance(pending, OperationReviewAvailableInteractionV1)
            control = await controller.response_control(
                interaction_id=pending.interaction_id, revision=pending.revision
            )
            applied = await control.apply(
                OperationResponseApplyRequestV1(
                    operation_id=controller.operation_id,
                    interaction_id=pending.interaction_id,
                    revision=pending.revision,
                    actor_ref=_ACTOR,
                    responded_at=now(),
                )
            )
            assert isinstance(applied, OperationResponseMutationSuccessV1)

            # Polled at a tenth of a second rather than tighter: the
            # journal read takes a blocking lock on this same loop, so a
            # hot poll starves the executor that has to write the very
            # events being waited for.
            settled_projection = None
            last_lifecycle = None
            for _ in range(300):
                current = await controller.observe(0)
                assert isinstance(current, OperationObservationSuccessV1)
                last_lifecycle = current.projection.lifecycle
                if last_lifecycle is OperationLifecycle.TERMINAL:
                    settled_projection = current.projection
                    break
                await asyncio.sleep(0.1)
            assert settled_projection is not None, f"the operation never settled; last lifecycle {last_lifecycle}"
            settled = build_operation_modal_view_model(settled_projection)
            assert settled.receipt_kind == "result"
            assert settled.receipt_ref is not None

            # The modal is mounted over a second, still-live operation so it
            # stays open to be read. A modal bound to the settled operation
            # would observe TERMINAL on its first poll and dismiss before the
            # pilot could look at it.
            watched = await _submit_censal_review(services, profile_id)
            watching = OperationController(services=services, submission=watched, actor_ref=_ACTOR)

            class _Host(App[None]):
                def on_mount(self) -> None:
                    self.push_screen(OperationModal(watching))

            host = _Host()
            async with host.run_test(size=(120, 40)) as pilot:
                modal = None
                for _ in range(200):
                    await pilot.pause()
                    screen = host.screen
                    if isinstance(screen, OperationModal) and screen.query("#operation-modal-receipt"):
                        modal = screen
                        break
                assert modal is not None
                modal._refresh_detail_rows(settled)
                receipt = str(modal.query_one("#operation-modal-receipt", Static).content)
                assert settled.receipt_ref in receipt
                await host.action_quit()

        asyncio.run(run())


_ACTION_BUTTON_IDS = (
    "#btn-operation-reject",
    "#btn-operation-apply",
    "#btn-operation-cancel",
    "#btn-operation-detach",
    "#btn-operation-close",
)


async def _mounted_modal(host: App[None], pilot: Pilot[None]) -> OperationModal:
    """Wait for the pushed modal to mount, or fail rather than assert on nothing."""
    for _ in range(200):
        await pilot.pause()
        screen = host.screen
        if isinstance(screen, OperationModal) and screen.is_mounted:
            return screen
    raise AssertionError("the operation modal never mounted, so this check would prove nothing")


@pytest.mark.parametrize("locale", ["es", "en", "ca", "hu"])
def test_every_action_is_reachable_on_an_eighty_column_terminal(tmp_path: Path, locale: str) -> None:
    """No action may leave the modal body at the eighty-by-twenty-four floor.

    Overflow here is not cosmetic. These surfaces carry no horizontal scroll
    affordance, and the modal refuses to close for operations whose close
    policy demands a cancel request, so an operator whose Detach and Close
    have left the screen has no in-interface way out of a live operation.

    Five buttons hold at least eighty columns between them before gutters,
    because Textual gives every button a sixteen-column minimum, against a
    body sixty-four columns wide. So the single row overflowed in every
    language rather than only the wordiest one, and the fix has to hold in
    every language too. Each catalogue is exercised rather than trusting the
    ambient one, which guards the layout against a future label long enough
    to push past that minimum and change how the row wraps. The language is
    switched through the real settings override the application reads, not by
    passing a locale to the widgets, so the labels under measurement are the
    ones an operator in that language would actually see.
    """
    with _runtime(tmp_path) as (services, _registry, profile_id):

        async def run() -> None:
            submitted = await _submit_censal_review(services, profile_id)
            controller = OperationController(services=services, submission=submitted, actor_ref=_ACTOR)

            class _Host(App[None]):
                def on_mount(self) -> None:
                    self.push_screen(OperationModal(controller))

            host = _Host()
            async with host.run_test(size=(80, 24)) as pilot:
                modal = await _mounted_modal(host, pilot)
                body = modal.query_one("#operation-modal-body")
                buttons = [modal.query_one(selector, Button) for selector in _ACTION_BUTTON_IDS]

                for button in buttons:
                    region = button.region
                    assert region.width > 0 and region.height > 0, f"{button.id} has no visible area at the floor"
                    assert region.x >= body.region.x and region.right <= body.region.right, (
                        f"{button.id} is outside the modal body: {region} against {body.region}"
                    )
                    assert region.x >= 0 and region.right <= 80, (
                        f"{button.id} is outside an eighty-column terminal: {region}"
                    )
                    assert region.y >= 0 and region.y + region.height <= 24, (
                        f"{button.id} is outside a twenty-four row terminal: {region}"
                    )

                # The row genuinely wrapped rather than fitting by luck: five
                # controls this wide cannot share one row inside a sixty-four
                # column body, so a single row here would mean something was
                # clipped rather than laid out.
                assert len({button.region.y for button in buttons}) > 1, (
                    "the action row did not wrap at the floor, so it can only be fitting by clipping"
                )

                await host.action_quit()

        with override_settings(cadrumo_output_language=locale):
            clear_output_language_cache()
            try:
                asyncio.run(run())
            finally:
                clear_output_language_cache()


def test_the_action_row_collapses_to_one_row_when_the_body_is_wide(tmp_path: Path) -> None:
    """Wrapping is a response to width, not a permanent second row.

    The narrow-terminal fix must not cost a row at the sizes that never had
    the problem, so at a comfortable width every action shares a single row.
    """
    with _runtime(tmp_path) as (services, _registry, profile_id):

        async def run() -> None:
            submitted = await _submit_censal_review(services, profile_id)
            controller = OperationController(services=services, submission=submitted, actor_ref=_ACTOR)

            class _Host(App[None]):
                def on_mount(self) -> None:
                    self.push_screen(OperationModal(controller))

            host = _Host()
            async with host.run_test(size=(120, 40)) as pilot:
                modal = await _mounted_modal(host, pilot)
                rows = {modal.query_one(selector, Button).region.y for selector in _ACTION_BUTTON_IDS}
                assert len(rows) == 1, f"the actions occupy {len(rows)} rows at a width that fits one"
                await host.action_quit()

        asyncio.run(run())
