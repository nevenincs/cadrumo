"""Each refusal of an automation review or denial names its reason as a typed code in the error envelope."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import cast
from uuid import UUID, uuid4

import pytest
import typer

from cadrumo.application.user_profile.automation_enrollment import (
    AutomationInventoryProjection,
    AutomationProposalProjection,
    AutomationReceiptProjection,
    AutomationReviewProjection,
    AutomationScopeProjection,
    EnrollmentStage,
)
from cadrumo.core.errors.error_codes import build_error_envelope
from cadrumo_client.commands.errors import CliRefusedBoundaryError
from cadrumo_client.contracts.access_vocabulary import disclosure_digest
from cadrumo_client.contracts.automation_codes import AutomationReviewRefusal
from cadrumo_client.contracts.enrollment_proposal import EnrollmentKind
from cadrumo_client.transport.automation_inventory import AutomationInventoryCompletion
from cadrumo_client.transport.frontend_client import FrontendClient
from cadrumo_runtime.commands import runtime_access_management as subject

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _context() -> typer.Context:
    app = typer.Typer()

    @app.command()
    def noop() -> None:
        return

    return typer.Context(typer.main.get_command(app))


def _review(profile_id: UUID, request_id: UUID) -> AutomationReviewProjection:
    instant = datetime(1980, 11, 2, tzinfo=UTC)
    return AutomationReviewProjection(
        receipt=AutomationReceiptProjection(
            request_id=request_id,
            profile_id=profile_id,
            stage=EnrollmentStage.REQUESTED,
            review_digest="c" * 64,
            grant_id=uuid4(),
            key_id=None,
            credential_reference=None,
        ),
        client_id=uuid4(),
        destination_id=uuid4(),
        proposal=AutomationProposalProjection(
            kind=EnrollmentKind.ENROLL,
            scope=AutomationScopeProjection(
                operations=(),
                actions=(),
                disclosure_count=0,
                disclosure_summary=(),
                disclosure_digest=disclosure_digest(()),
                periods=None,
                allow_period_independent=False,
                allow_delegation=False,
            ),
            expires_at=instant + timedelta(days=1),
            key_expires_at=instant + timedelta(days=1),
            unattended=False,
            allow_os_lock=False,
            target_grant_id=None,
            target_key_id=None,
        ),
        expires_at=instant + timedelta(minutes=5),
    )


def _reason(error: CliRefusedBoundaryError) -> str | None:
    context = build_error_envelope(error).context
    return None if context is None else context.get("reason")


def _inventory_of(
    monkeypatch: pytest.MonkeyPatch, profile_id: UUID, *reviews: AutomationReviewProjection
) -> FrontendClient:
    client = cast(FrontendClient, SimpleNamespace(profile_id=profile_id))
    completion = AutomationInventoryCompletion(
        operation_id="a" * 64,
        projection=AutomationInventoryProjection(grants=(), keys=(), requests=reviews),
    )
    monkeypatch.setattr(subject, "read_automation_inventory", lambda _client: completion)
    return client


def test_a_request_not_under_review_is_refused_as_review_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    profile_id = uuid4()
    client = _inventory_of(monkeypatch, profile_id, _review(profile_id, uuid4()))

    with pytest.raises(CliRefusedBoundaryError) as refused:
        subject.runtime_access_management_review(client, uuid4())

    assert _reason(refused.value) == AutomationReviewRefusal.REVIEW_NOT_FOUND.value == "review_not_found"


def test_a_request_of_another_profile_is_refused_as_review_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    request_id = uuid4()
    client = _inventory_of(monkeypatch, uuid4(), _review(uuid4(), request_id))

    with pytest.raises(CliRefusedBoundaryError) as refused:
        subject.runtime_access_management_review(client, request_id)

    assert _reason(refused.value) == "review_not_found"


def test_a_stale_digest_is_refused_as_review_digest_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
    profile_id, request_id = uuid4(), uuid4()
    client = _inventory_of(monkeypatch, profile_id, _review(profile_id, request_id))
    _, review = subject.runtime_access_management_review(client, request_id)

    subject.runtime_access_management_review_digest(review, "c" * 64)
    with pytest.raises(CliRefusedBoundaryError) as refused:
        subject.runtime_access_management_review_digest(review, "d" * 64)

    assert _reason(refused.value) == AutomationReviewRefusal.REVIEW_DIGEST_MISMATCH.value == "review_digest_mismatch"


@pytest.mark.parametrize(("kind", "target_id"), [("key", None), ("grant", None), ("all", uuid4()), ("other", None)])
def test_a_denial_whose_target_does_not_fit_its_kind_is_refused_as_target_mismatch(
    monkeypatch: pytest.MonkeyPatch, kind: str, target_id: UUID | None
) -> None:
    client = cast(FrontendClient, SimpleNamespace(profile_id=uuid4()))
    monkeypatch.setattr(subject, "runtime_access_management_client", lambda _ctx, *, requested_language: client)

    with pytest.raises(CliRefusedBoundaryError) as refused:
        subject.automation_deny(_context(), kind, target_id)

    assert _reason(refused.value) == AutomationReviewRefusal.TARGET_MISMATCH.value == "target_mismatch"
