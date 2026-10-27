"""A setup review is displayed before claim, and answered only at its acknowledged revision."""

from __future__ import annotations

from typing import cast, override
from uuid import uuid4

import pytest
from pydantic import BaseModel
from textual.widgets import Button, Input, Static

from cadrumo.tests.components_role_replay import transcript_lines
from cadrumo_client.contracts.operation_access import OperationReviewClaimed
from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError

from .....adapters.outbound.components.protocol import ComponentsReviewLine, decode_components_line
from .....application.components_operations import (
    COMPONENTS_SETUP_OPERATION_ID,
    PROVISION_RESPONSE_SCHEMA,
    PROVISION_REVIEW_SCHEMA,
    ProvisionPlan,
    ProvisionReviewProjection,
)
from .....application.operations.frontend_projection import (
    OperationPublicProgressV1,
    OperationReviewAvailableInteractionV1,
    OperationReviewProjectionReferenceV1,
)
from .....application.operations.frontend_requests import (
    OperationObservationSuccessV1,
    OperationPublicEventPageV1,
    OperationResponseControlSuccessV1,
    OperationResponseMutationSuccessV1,
    OperationResponseRejectRequestV1,
    OperationReviewProjectionSuccessV1,
)
from .....application.operations.interactions import OperationResponseIntent
from .....application.operations.persistence.replay import OperationReplayStatus
from .....application.operations.registry import OperationRegistry
from .....application.operations.tests.test_public_contracts import _projection
from .....core.config import override_settings
from .....core.hashing import content_hash_hex
from .....core.i18n.render import tr
from .....core.operations import OperationLifecycle
from ....components_operation_composition import build_components_operations
from ...components.host import ScreenHostApp
from ...setup.screen import SetupScreen
from ...setup.tests.operations_fixture import SetupFixture
from ...tests.settling import settle_until
from ..controller_port import OperationControllerPort, OperationResponseControlPort
from ..interactions import OperationModalReviewInteractionV1, resolve_modal_interaction_state
from ..modal import OperationModal
from ..projection import build_operation_modal_view_model

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


class ReviewController:
    """Record the surface ordering; runtime custody itself is tested by its owner."""

    operation_id = "a" * 64
    actor_ref = "session:human"

    def __init__(self) -> None:
        group = build_components_operations()
        registry = OperationRegistry(definitions=group.definitions, public_registrations=group.registrations)
        contract = registry.lookup_public_contract(COMPONENTS_SETUP_OPERATION_ID)
        line = next(
            decode_components_line(raw)
            for raw in transcript_lines("setup_browser_completed")
            if b'"type":"review"' in raw
        )
        assert isinstance(line, ComponentsReviewLine)
        self.review = OperationReviewProjectionSuccessV1[ProvisionReviewProjection](
            projection_schema=PROVISION_REVIEW_SCHEMA.identity,
            definition_contract_digest=contract.definition_contract_digest,
            projection=ProvisionReviewProjection(
                reviewed_proposal_digest="c" * 64,
                plan_digest=line.plan_digest,
                plan=ProvisionPlan.model_validate_json(line.plan.model_dump_json()),
            ),
        )
        self.reference = OperationReviewProjectionReferenceV1(
            operation_id=self.operation_id,
            interaction_id="d" * 64,
            revision=4,
            review_projection_schema=PROVISION_REVIEW_SCHEMA.identity,
            definition_contract_digest=contract.definition_contract_digest,
            expires_at=None,
        )
        pending = OperationReviewAvailableInteractionV1(
            operation_id=self.operation_id,
            interaction_id=self.reference.interaction_id,
            revision=4,
            presentation_code="dependencies.setup.review",
            response_schema=PROVISION_RESPONSE_SCHEMA.identity,
            expires_at=None,
            review_reference=self.reference,
        )
        self.projection = _projection(
            contract_set=registry.public_contract_set,
            operation_id=self.operation_id,
            subject_ref="components:installation",
            definition_id=COMPONENTS_SETUP_OPERATION_ID,
            definition_contract=contract,
            phase_code=COMPONENTS_SETUP_OPERATION_ID,
            lifecycle=OperationLifecycle.WAITING_FOR_INTERACTION,
            pending_interaction=pending,
        )
        self.calls: list[str] = []
        self.claimed = False
        self.refusal: str | None = None
        self.answer_revision: int | None = None

    async def observe(self, after_cursor: int, *, page_limit: int = 256) -> OperationObservationSuccessV1:
        return OperationObservationSuccessV1(
            projection=self.projection,
            event_page=OperationPublicEventPageV1(
                operation_id=self.operation_id,
                anchor_cursor=0,
                requested_cursor=0,
                next_cursor=0,
                restart_cursor=None,
                status=OperationReplayStatus.CAUGHT_UP,
                events=(),
            ),
        )

    async def resolve_review_document(
        self, reference: OperationReviewProjectionReferenceV1, projection_type: type[BaseModel]
    ) -> tuple[OperationReviewProjectionSuccessV1[ProvisionReviewProjection], str]:
        self.calls.append("display")
        assert reference == self.reference
        return self.review, content_hash_hex(self.review.model_dump(mode="json"))

    async def claim_review(
        self, reference: OperationReviewProjectionReferenceV1, reviewed_document_digest: str
    ) -> OperationReviewClaimed:
        self.calls.append("claim")
        assert reference == self.reference
        assert reviewed_document_digest == content_hash_hex(self.review.model_dump(mode="json"))
        if self.refusal is not None:
            raise FrontendRefusedError(self.refusal)
        self.claimed = True
        return OperationReviewClaimed(
            request_id=uuid4(),
            runtime_boot_id=uuid4(),
            connection_id=uuid4(),
            reference=reference.model_copy(update={"revision": 5}),
            reviewed_document_digest=reviewed_document_digest,
            allowed_intents=frozenset({"apply", "reject"}),
        )

    async def response_control(self, *, interaction_id: str, revision: int) -> OperationResponseControlPort:
        self.calls.append("control")
        assert self.claimed and revision == 5
        return cast(OperationResponseControlPort, self)

    async def inspect(self) -> OperationResponseControlSuccessV1:
        self.calls.append("inspect")
        assert self.claimed
        return OperationResponseControlSuccessV1(
            operation_id=self.operation_id,
            interaction_id=self.reference.interaction_id,
            revision=5,
            available=True,
            permitted_intents=frozenset({"apply", "reject"}),
        )

    async def reject(self, request: OperationResponseRejectRequestV1) -> OperationResponseMutationSuccessV1:
        self.calls.append("reject")
        self.answer_revision = request.revision
        return OperationResponseMutationSuccessV1(
            operation_id=self.operation_id,
            interaction_id=request.interaction_id,
            revision=request.revision,
            response_action="reject",
        )


@pytest.mark.asyncio
async def test_display_claim_ack_inspect_and_answer_order() -> None:
    controller = ReviewController()
    modal = OperationModal(cast(OperationControllerPort, controller))
    with override_settings(cadrumo_output_language="en"):
        async with ScreenHostApp(modal).run_test(size=(120, 50)) as pilot:
            await settle_until(
                pilot, lambda: modal.query_one("#btn-operation-claim", Button).display, "review display", workers=False
            )
            assert "Browser for the tax agency website" in str(
                modal.query_one("#operation-modal-review", Static).render()
            )
            assert controller.calls == ["display"]
            assert modal.query_one("#btn-operation-apply", Button).disabled
            await modal._claim_review()
            assert controller.calls == ["display", "claim", "control", "inspect"]
            assert not modal.query_one("#btn-operation-reject", Button).disabled
            await modal._send_response(intent=OperationResponseIntent.REJECT)
            assert controller.answer_revision == 5
            assert controller.calls[-1] == "reject"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("code", "key"),
    [
        ("review_already_claimed", "operation.modal.claim.already_claimed"),
        ("review_claim_stale", "operation.modal.claim.stale"),
        ("response_authority_required", "operation.modal.claim.authority_lost"),
        ("connection_closed", "operation.modal.claim.unavailable"),
    ],
)
async def test_failed_claim_never_inspects_or_answers(code: str, key: str) -> None:
    controller = ReviewController()
    controller.refusal = code
    modal = OperationModal(cast(OperationControllerPort, controller))
    async with ScreenHostApp(modal).run_test(size=(120, 50)) as pilot:
        await settle_until(
            pilot, lambda: modal.query_one("#btn-operation-claim", Button).display, "review", workers=False
        )
        await modal._claim_review()
        await modal._send_response(intent=OperationResponseIntent.REJECT)
        assert controller.calls == ["display", "claim"]
        assert modal.query_one("#btn-operation-reject", Button).disabled
        message = str(modal.query_one("#operation-modal-action-refusal", Static).render())
        assert tr(key) in message
        assert code not in message


@pytest.mark.asyncio
async def test_unchanged_unclaimed_observation_does_not_issue_authority() -> None:
    controller = ReviewController()
    state = await resolve_modal_interaction_state(
        cast(OperationControllerPort, controller), controller.projection, ProvisionReviewProjection
    )
    retained = await resolve_modal_interaction_state(
        cast(OperationControllerPort, controller), controller.projection, ProvisionReviewProjection, current=state
    )
    assert isinstance(retained, OperationModalReviewInteractionV1)
    assert retained.control is None
    assert controller.calls == ["display"]


@pytest.mark.asyncio
async def test_progress_row_clears_when_the_next_projection_has_none() -> None:
    controller = ReviewController()
    modal = OperationModal(cast(OperationControllerPort, controller))
    async with ScreenHostApp(modal).run_test(size=(120, 50)) as pilot:
        await settle_until(
            pilot, lambda: modal.query_one("#btn-operation-claim", Button).display, "review", workers=False
        )
        progress = OperationPublicProgressV1(
            completed=25,
            total=100,
            unit_code="bytes",
            subject_code="browser",
            phase_code=controller.projection.phase_code,
            event_sequence=1,
            revision=4,
        )
        modal._view_model = build_operation_modal_view_model(
            controller.projection.model_copy(update={"progress": progress, "anchor_cursor": 1})
        )
        modal._refresh_view_state()
        assert "25%" in str(modal.query_one("#operation-modal-progress", Static).render())
        modal._view_model = build_operation_modal_view_model(controller.projection)
        modal._refresh_view_state()
        assert not str(modal.query_one("#operation-modal-progress", Static).render())


@pytest.mark.asyncio
async def test_known_reference_opens_response_only_and_closes_without_detaching() -> None:
    controller = ReviewController()

    class AttachedSetup(SetupFixture):
        @override
        async def review(self, operation_id: str) -> OperationControllerPort:
            self.reviews.append(operation_id)
            return cast(OperationControllerPort, controller)

    operations = AttachedSetup()
    screen = SetupScreen(operations)
    app = ScreenHostApp(screen)
    async with app.run_test(size=(120, 50)) as pilot:
        await settle_until(pilot, lambda: bool(screen.rows), "status")
        screen.query_one("#setup-review-reference", Input).value = controller.operation_id
        await pilot.click("#btn-setup-review")
        await settle_until(
            pilot, lambda: isinstance(app.screen, OperationModal), "existing setup review", workers=False
        )
        modal = app.screen
        assert isinstance(modal, OperationModal)
        await settle_until(
            pilot, lambda: modal.query_one("#btn-operation-claim", Button).display, "display", workers=False
        )
        assert operations.reviews == [controller.operation_id]
        assert operations.submissions == []
        assert not modal.query_one("#btn-operation-cancel", Button).display
        assert not modal.query_one("#btn-operation-detach", Button).display
        await modal._request_cancel()
        await modal._request_detach()
        assert controller.calls == ["display"]
        await modal._claim_review()
        await modal._send_response(intent=OperationResponseIntent.REJECT)
        assert controller.answer_revision == 5
        await modal.action_request_close()
        await settle_until(pilot, lambda: app.screen is screen, "closed without detach", workers=False)
        assert controller.calls == ["display", "claim", "control", "inspect", "reject"]


@pytest.mark.asyncio
async def test_response_only_reference_to_another_operation_never_resolves_or_claims() -> None:
    controller = ReviewController()
    controller.projection = _projection(operation_id=controller.operation_id)
    modal = OperationModal(cast(OperationControllerPort, controller), response_only=True)
    async with ScreenHostApp(modal).run_test(size=(120, 50)) as pilot:
        await settle_until(pilot, lambda: modal._observation_stopped, "foreign operation refused", workers=False)
        assert controller.calls == []
        assert modal.query_one("#btn-operation-apply", Button).disabled
        assert modal.query_one("#btn-operation-reject", Button).disabled
