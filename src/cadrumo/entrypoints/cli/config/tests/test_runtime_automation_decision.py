"""CLI automation decisions bind one review before reading approval proof."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import cast
from uuid import UUID, uuid4

import pytest
import typer
from pydantic import SecretStr, ValidationError

from cadrumo.adapters.local_runtime.automation_decision import (
    AutomationDecisionCompletion,
    AutomationDecisionRunError,
)
from cadrumo.adapters.local_runtime.automation_inventory import AutomationInventoryCompletion
from cadrumo.adapters.local_runtime.frontend_client import RuntimeFrontendClient
from cadrumo.application.user_profile.automation_enrollment import (
    AutomationInventoryProjection,
    AutomationProposalProjection,
    AutomationReceiptProjection,
    AutomationReviewProjection,
    AutomationScopeProjection,
    EnrollmentKind,
    EnrollmentStage,
)
from cadrumo.core.operations import OperationEffect
from cadrumo.entrypoints.cli.config import runtime_access_management as subject
from cadrumo.entrypoints.cli.config.runtime_access_management_payloads import (
    ConfigProfileAutomationDecisionResult,
    ConfigProfileAutomationInspectResult,
)
from cadrumo.entrypoints.cli.config.secure_input import (
    clear_staged_machine_secret_payloads,
    stage_machine_secret_payload,
)
from cadrumo.entrypoints.cli.errors import CliRefusedBoundaryError

from ...tests.cli_runner import invoke_cached_cli

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_DIGEST = "a" * 64
_PROOF = b"synthetic-fresh-approval-proof"


def _context() -> typer.Context:
    app = typer.Typer()

    @app.command()
    def noop() -> None:
        return

    return typer.Context(typer.main.get_command(app))


def _review(profile_id: UUID) -> AutomationReviewProjection:
    now = datetime.now(UTC)
    return AutomationReviewProjection(
        receipt=AutomationReceiptProjection(
            request_id=uuid4(),
            profile_id=profile_id,
            stage=EnrollmentStage.REQUESTED,
            review_digest=_DIGEST,
            grant_id=uuid4(),
            key_id=None,
            credential_reference=None,
        ),
        client_id=uuid4(),
        destination_id=uuid4(),
        proposal=AutomationProposalProjection(
            kind=EnrollmentKind.ENROLL,
            scope=AutomationScopeProjection(
                operations=("user-profile.field-mutation",),
                actions=(),
                disclosures=(),
                periods=None,
                allow_period_independent=True,
                allow_delegation=False,
            ),
            expires_at=now + timedelta(days=10),
            key_expires_at=now + timedelta(days=2),
            unattended=False,
            allow_os_lock=False,
            target_grant_id=None,
            target_key_id=None,
        ),
        expires_at=now + timedelta(minutes=5),
    )


def _bind(monkeypatch: pytest.MonkeyPatch) -> tuple[RuntimeFrontendClient, AutomationReviewProjection, list[object]]:
    profile_id = uuid4()
    client = cast(RuntimeFrontendClient, SimpleNamespace(profile_id=profile_id))
    review = _review(profile_id)
    events: list[object] = []
    monkeypatch.setattr(subject, "_client", lambda _ctx, *, requested_language: client)

    def read(bound: RuntimeFrontendClient) -> AutomationInventoryCompletion:
        assert bound is client
        events.append("inventory")
        return AutomationInventoryCompletion(
            operation_id="b" * 64,
            projection=AutomationInventoryProjection(grants=(), keys=(), requests=(review,)),
        )

    monkeypatch.setattr(subject, "read_automation_inventory", read)
    monkeypatch.setattr(subject, "emit_envelope", lambda _ctx, **kwargs: events.append(kwargs))
    return client, review, events


@pytest.mark.parametrize(
    ("path", "options"),
    (
        (("automation", "inspect"), ("request_id",)),
        (("automation", "approve"), ("--review-digest", "--secrets-stdin", "--secrets-fd")),
        (("automation", "decline"), ("--review-digest",)),
    ),
)
def test_live_parser_has_review_identity_but_no_password_argv(path: tuple[str, ...], options: tuple[str, ...]) -> None:
    result = invoke_cached_cli(("config", "profile", *path, "--help"))
    assert result.exit_code == 0, result.output
    assert all(option in result.output for option in options)
    assert "--password" not in result.output


def test_inspect_emits_exact_review_without_decision_or_password(monkeypatch: pytest.MonkeyPatch) -> None:
    client, review, events = _bind(monkeypatch)
    monkeypatch.setattr(subject, "_approval_password", lambda **_kwargs: pytest.fail("inspect read proof"))
    monkeypatch.setattr(subject, "run_automation_decision", lambda *_args, **_kwargs: pytest.fail("inspect decided"))

    subject.automation_inspect(_context(), review.receipt.request_id)

    assert events[0] == "inventory"
    output = events[1]
    assert isinstance(output, dict)
    assert output["command"] == "config.profile.automation.inspect"
    result = output["result"]
    assert isinstance(result, ConfigProfileAutomationInspectResult)
    assert result.profile_id == client.profile_id
    assert result.review == review
    assert _DIGEST in result.model_dump_json()
    assert review.proposal.expires_at.isoformat() in str(output["lines"])
    assert _PROOF.decode() not in result.model_dump_json()


def test_approval_leaf_uses_one_strict_staged_secret_payload() -> None:
    try:
        stage_machine_secret_payload(subject.AutomationApprovalSecrets(passphrase=SecretStr(_PROOF.decode())))
        proof = subject._approval_password(secrets_stdin=True, secrets_fd=None)
        assert proof == _PROOF
        proof[:] = bytes(len(proof))
        assert not any(proof)
        with pytest.raises(ValidationError):
            subject.AutomationApprovalSecrets.model_validate(
                {"passphrase": _PROOF.decode(), "unexpected": "not-accepted"}
            )
    finally:
        clear_staged_machine_secret_payloads()


@pytest.mark.parametrize("mismatch", ["unknown_request", "wrong_digest"])
def test_approval_rejects_review_mismatch_before_leaf_password(monkeypatch: pytest.MonkeyPatch, mismatch: str) -> None:
    _, review, events = _bind(monkeypatch)
    monkeypatch.setattr(subject, "_approval_password", lambda **_kwargs: pytest.fail("read proof before review"))
    request_id = uuid4() if mismatch == "unknown_request" else review.receipt.request_id
    digest = "c" * 64 if mismatch == "wrong_digest" else _DIGEST

    with pytest.raises(CliRefusedBoundaryError) as caught:
        subject.automation_approve(_context(), request_id, digest, secrets_stdin=True)

    assert caught.value.translated_message is not None
    assert events == ["inventory"]


def test_approval_passes_mutable_fresh_proof_once_and_wipes_it(monkeypatch: pytest.MonkeyPatch) -> None:
    client, review, events = _bind(monkeypatch)
    proof = bytearray(_PROOF)
    seen: list[object] = []
    monkeypatch.setattr(subject, "_approval_password", lambda **_kwargs: proof)

    def decide(
        bound: RuntimeFrontendClient,
        selected: AutomationReviewProjection,
        *,
        decision: str,
        password: bytearray | None,
    ) -> AutomationDecisionCompletion:
        assert bound is client and selected == review
        seen.extend((decision, password, bytes(password or b"")))
        return AutomationDecisionCompletion(
            operation_id="d" * 64,
            receipt=review.receipt.model_copy(update={"stage": EnrollmentStage.COMPLETE}),
            effect=OperationEffect.UPDATED,
        )

    monkeypatch.setattr(subject, "run_automation_decision", decide)

    subject.automation_approve(_context(), review.receipt.request_id, _DIGEST, secrets_stdin=True)

    assert events[0] == "inventory"
    assert seen == ["approve", proof, _PROOF]
    assert proof == bytes(len(_PROOF))
    output = events[1]
    assert isinstance(output, dict)
    result = output["result"]
    assert isinstance(result, ConfigProfileAutomationDecisionResult)
    assert result.operation_id == "d" * 64 and result.effect is OperationEffect.UPDATED
    assert _PROOF.decode() not in result.model_dump_json() + str(output["lines"])


def test_decline_never_reads_password_and_keeps_decision_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    client, review, events = _bind(monkeypatch)
    monkeypatch.setattr(subject, "_approval_password", lambda **_kwargs: pytest.fail("decline read proof"))

    def decide(
        bound: RuntimeFrontendClient,
        selected: AutomationReviewProjection,
        *,
        decision: str,
        password: bytearray | None,
    ) -> AutomationDecisionCompletion:
        assert bound is client and selected == review and decision == "decline" and password is None
        return AutomationDecisionCompletion(
            operation_id="e" * 64,
            receipt=review.receipt.model_copy(update={"stage": EnrollmentStage.DECLINED}),
            effect=OperationEffect.NONE,
        )

    monkeypatch.setattr(subject, "run_automation_decision", decide)
    subject.automation_decline(_context(), review.receipt.request_id, _DIGEST)
    assert events[0] == "inventory"
    output = events[1]
    assert isinstance(output, dict)
    assert output["command"] == "config.profile.automation.decline"
    result = output["result"]
    assert isinstance(result, ConfigProfileAutomationDecisionResult)
    assert result.operation_id == "e" * 64 and result.receipt.stage is EnrollmentStage.DECLINED


def test_post_submit_failure_retains_operation_and_wipes_password(monkeypatch: pytest.MonkeyPatch) -> None:
    _, review, events = _bind(monkeypatch)
    proof = bytearray(_PROOF)
    monkeypatch.setattr(subject, "_approval_password", lambda **_kwargs: proof)

    def fail(*_args: object, **_kwargs: object) -> None:
        raise AutomationDecisionRunError(operation_id="f" * 64, code="unavailable")

    monkeypatch.setattr(subject, "run_automation_decision", fail)
    with pytest.raises(AutomationDecisionRunError) as caught:
        subject.automation_approve(_context(), review.receipt.request_id, _DIGEST, secrets_stdin=True)
    assert caught.value.operation_id == "f" * 64
    assert proof == bytes(len(_PROOF))
    assert events == ["inventory"]
