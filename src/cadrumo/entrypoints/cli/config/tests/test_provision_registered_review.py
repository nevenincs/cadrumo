"""The CLI explicitly claims the displayed setup document before responding."""

from uuid import uuid4

import pytest
import typer
import typer.main

from cadrumo_client.commands.registered_operation_contracts import RegisteredOperationCompletion
from cadrumo_client.commands.registered_operation_deadlines import RegisteredOperationSettlement
from cadrumo_client.contracts.contracts import RefusalError
from cadrumo_client.contracts.operation_access import OperationReviewClaim, OperationReviewClaimed

from .....application.components_operations import (
    COMPONENTS_STATUS_DEFINITION_ID,
    COMPONENTS_VERIFY_DEFINITION_ID,
    PROVISION_RESPONSE_SCHEMA,
    PROVISION_REVIEW_SCHEMA,
    ProvisionOutcome,
    ProvisionReadRequest,
    ProvisionResult,
)
from .....application.dependency_contracts import DependencyItemKind
from .....application.operations.frontend_projection import (
    OperationReviewAvailableInteractionV1,
    OperationReviewProjectionReferenceV1,
)
from .....application.operations.interactions import OperationResponseIntent
from .....core.hashing import content_hash_hex
from .....core.operations import OperationEffect
from .. import provision_cli
from ..provision_cli import _claim_review

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _pending() -> OperationReviewAvailableInteractionV1:
    reference = OperationReviewProjectionReferenceV1(
        operation_id="a" * 64,
        interaction_id="b" * 64,
        revision=5,
        review_projection_schema=PROVISION_REVIEW_SCHEMA.identity,
        definition_contract_digest="c" * 64,
        expires_at=None,
    )
    return OperationReviewAvailableInteractionV1(
        operation_id=reference.operation_id,
        interaction_id=reference.interaction_id,
        revision=reference.revision,
        presentation_code="config.provision.review",
        response_schema=PROVISION_RESPONSE_SCHEMA.identity,
        expires_at=None,
        review_reference=reference,
    )


@pytest.mark.parametrize("fault", [None, "digest", "interaction", "revision"])
def test_claim_binds_the_exact_document_and_refuses_a_mismatched_successor(fault: str | None) -> None:
    pending = _pending()
    document = {"outcome": "success", "projection": {"plan_digest": "d" * 64}}
    profile, session = uuid4(), uuid4()
    calls: list[OperationReviewClaim] = []

    def exchange(request):
        assert isinstance(request, OperationReviewClaim)
        calls.append(request)
        reference = request.reference.model_copy(update={"revision": 6})
        if fault == "interaction":
            reference = reference.model_copy(update={"interaction_id": "e" * 64})
        if fault == "revision":
            reference = reference.model_copy(update={"revision": 7})
        return OperationReviewClaimed(
            request_id=request.request_id,
            runtime_boot_id=uuid4(),
            connection_id=uuid4(),
            reference=reference,
            reviewed_document_digest="f" * 64 if fault == "digest" else request.reviewed_document_digest,
            allowed_intents=frozenset({OperationResponseIntent.APPLY, OperationResponseIntent.REJECT}),
        )

    if fault is not None:
        with pytest.raises(RefusalError):
            _claim_review(pending, document, profile, session, exchange)
    else:
        claimed = _claim_review(pending, document, profile, session, exchange)
        assert claimed.revision == 6 and claimed.review_reference.revision == 6
    assert len(calls) == 1
    assert calls[0].reference == pending.review_reference
    assert calls[0].reviewed_document_digest == content_hash_hex(document)
    assert calls[0].profile_id == profile and calls[0].session_id == session


@pytest.mark.parametrize(
    ("full", "items", "definition"),
    [
        (False, (), COMPONENTS_STATUS_DEFINITION_ID),
        (True, (), COMPONENTS_VERIFY_DEFINITION_ID),
        (True, (DependencyItemKind.BROWSER,), COMPONENTS_VERIFY_DEFINITION_ID),
    ],
)
def test_component_reads_submit_typed_registered_requests(
    monkeypatch: pytest.MonkeyPatch, full: bool, items: tuple[DependencyItemKind, ...], definition: str
) -> None:
    app = typer.Typer()

    @app.command()
    def noop() -> None: ...

    ctx = typer.Context(typer.main.get_command(app), obj={"format": "text"})
    client = object()
    calls = []
    monkeypatch.setattr(provision_cli, "bound_profile_client", lambda _ctx: client)

    def run(bound, payload, **kwargs):
        calls.append((bound, payload, kwargs))
        return RegisteredOperationCompletion(
            operation_id="a" * 64, projection=ProvisionResult(outcome=ProvisionOutcome.OK), effect=OperationEffect.NONE
        )

    monkeypatch.setattr(provision_cli, "run_registered_operation", run)
    result = provision_cli._read(ctx, items, full=full)
    assert result.outcome is ProvisionOutcome.OK
    bound, payload, kwargs = calls[0]
    assert bound is client and payload == ProvisionReadRequest(items=items)
    assert kwargs["definition_id"] == definition
    assert callable(kwargs["on_events"]) is full
    assert kwargs["settlement_timeout"] == (
        RegisteredOperationSettlement.UNBOUNDED if full else provision_cli._QUICK_SETTLEMENT_S
    )
