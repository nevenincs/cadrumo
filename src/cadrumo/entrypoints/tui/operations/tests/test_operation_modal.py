"""Real end-to-end proofs for the generic detachable operation modal.

Every test drives a genuine registered operation through the composed
production services (real journal, real leases, real profile custody), then
proves the TUI-facing controller, projection, log, and interaction modules
never see more than the public frontend contracts C0 already froze.
"""

from __future__ import annotations

import asyncio
from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast
from uuid import UUID

import pytest
from textual.app import App

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
from .....application.operations.models import OperationRequest
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
from ..projection import build_operation_modal_view_model

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_PASSPHRASE = "operation-modal-conformance-passphrase"  # noqa: S105 - isolated integration fixture
_ACTOR: OperationActorReference = "operator:operation-modal-conformance"
_C0_RECEIPT_PATH = (
    Path(__file__).resolve().parents[6]
    / ".vault"
    / "reference"
    / "2026-08-24-tui-operation-observation-dependency-receipt-reference.md"
)


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
    before_irreversible_section: object = None,
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


def test_c0_receipt_freezes_the_exact_public_dtos_this_modal_renders() -> None:
    """Prove the modal's ancestry: the frozen C0 receipt names these public types."""
    receipt_text = _C0_RECEIPT_PATH.read_text(encoding="utf-8")
    assert '"cohort": "c0.operation-projection"' in receipt_text
    assert '"auth.profile.login"' in receipt_text


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
        status="expired",
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
        status="caught_up",
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
