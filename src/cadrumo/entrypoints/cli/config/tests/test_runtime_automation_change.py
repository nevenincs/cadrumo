"""The CLI grant-change leaf requires a protected, kind-matched proposal."""

from __future__ import annotations

import json
from datetime import timedelta
from uuid import uuid4

import pytest

from cadrumo.application.user_profile.access_contracts import AccessAction, AccessScope
from cadrumo.application.user_profile.automation_enrollment import (
    AutomationReceiptProjection,
    EnrollmentKind,
    EnrollmentProposal,
    EnrollmentStage,
)
from cadrumo.core.time.clock import now
from cadrumo.entrypoints.cli.config.runtime_access_management_payloads import ConfigProfileAutomationChangeResult
from cadrumo.entrypoints.cli.config.runtime_automation_request import AutomationChangeInput, _matching_change_payload
from cadrumo.entrypoints.cli.config.secure_input import validate_secrets_payload
from cadrumo.entrypoints.cli.errors import CliRefusedBoundaryError

from ...tests.cli_runner import invoke_cached_cli

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _proposal(kind: EnrollmentKind) -> EnrollmentProposal:
    instant = now()
    return EnrollmentProposal(
        kind=kind,
        scope=AccessScope(
            operations=frozenset({"user-profile.field-mutation"}),
            actions=frozenset({AccessAction.SUBMIT}),
            disclosures=frozenset(),
            periods=None,
            allow_period_independent=True,
            allow_delegation=False,
        ),
        expires_at=instant + timedelta(days=30),
        key_expires_at=instant + timedelta(days=15) if kind in {EnrollmentKind.ENROLL, EnrollmentKind.ROTATE} else None,
        unattended=True,
        allow_os_lock=False,
        target_grant_id=None if kind is EnrollmentKind.ENROLL else uuid4(),
        target_key_id=uuid4() if kind is EnrollmentKind.ROTATE else None,
    )


def _parse(proposal: EnrollmentProposal) -> AutomationChangeInput:
    return validate_secrets_payload(
        json.dumps({"proposal": proposal.model_dump(mode="json")}).encode(),
        AutomationChangeInput,
        invalid_json_key="cli.config.custody.errors.secrets_stdin_invalid_json",
        missing_fields_key="cli.config.custody.errors.secrets_stdin_missing_fields",
    )


def test_protected_change_input_is_strict_and_kind_bound() -> None:
    for kind in (EnrollmentKind.ROTATE, EnrollmentKind.RENEW, EnrollmentKind.CHANGE_SCOPE):
        proposal = _proposal(kind)
        parsed = _parse(proposal)
        assert parsed.proposal == proposal
        assert str(proposal.target_grant_id) not in repr(parsed)
        assert _matching_change_payload(parsed, kind.value) == proposal
        wrong = EnrollmentKind.RENEW if kind is EnrollmentKind.ROTATE else EnrollmentKind.ROTATE
        with pytest.raises(CliRefusedBoundaryError):
            _matching_change_payload(parsed, wrong.value)
    with pytest.raises(CliRefusedBoundaryError):
        validate_secrets_payload(
            b'{"proposal":{"kind":"renew","kind":"rotate"}}',
            AutomationChangeInput,
            invalid_json_key="cli.config.custody.errors.secrets_stdin_invalid_json",
            missing_fields_key="cli.config.custody.errors.secrets_stdin_missing_fields",
        )
    with pytest.raises(CliRefusedBoundaryError):
        validate_secrets_payload(
            json.dumps({"proposal": _proposal(EnrollmentKind.ENROLL).model_dump(mode="json")}).encode(),
            AutomationChangeInput,
            invalid_json_key="cli.config.custody.errors.secrets_stdin_invalid_json",
            missing_fields_key="cli.config.custody.errors.secrets_stdin_missing_fields",
        )


def test_change_requires_exact_credential_route_before_profile_open() -> None:
    command = ("config", "profile", "automation", "change", "renew", "--secrets-stdin")
    for prefix in (
        (),
        ("--profile-auth-method", "api-key"),
        ("--profile-credential-ref", str(uuid4())),
        ("--profile-auth-method", "password", "--profile-credential-ref", str(uuid4())),
    ):
        refused = invoke_cached_cli(("--format", "json", *prefix, *command), input="{}")
        assert refused.exit_code != 0
        document = json.loads(refused.output)
        assert document["command"] == "config.profile.automation.change"
        assert document["error"]["code"] == "REFUSED_CLI_BOUNDARY"
        assert "--profile-auth-method api-key" in document["error"]["message"]
        assert "--profile-credential-ref" in document["error"]["message"]


def test_change_result_retains_exact_terminal_and_only_new_rotated_reference() -> None:
    profile_id, request_id, grant_id, key_id, reference = (uuid4() for _ in range(5))
    submitted = AutomationReceiptProjection(
        request_id=request_id,
        profile_id=profile_id,
        review_digest="a" * 64,
        grant_id=grant_id,
        stage=EnrollmentStage.REQUESTED,
        key_id=None,
        credential_reference=None,
    )
    complete = submitted.model_copy(
        update={"stage": EnrollmentStage.COMPLETE, "key_id": key_id, "credential_reference": reference}
    )
    rotated = ConfigProfileAutomationChangeResult(
        profile_id=profile_id,
        kind=EnrollmentKind.ROTATE,
        submitted=submitted,
        terminal=complete,
        credential_reference=reference,
    )
    assert ConfigProfileAutomationChangeResult.model_validate_json(rotated.model_dump_json()) == rotated
    with pytest.raises(ValueError):
        ConfigProfileAutomationChangeResult(
            profile_id=profile_id,
            kind=EnrollmentKind.RENEW,
            submitted=submitted,
            terminal=complete,
            credential_reference=reference,
        )
    with pytest.raises(ValueError):
        ConfigProfileAutomationChangeResult(
            profile_id=uuid4(),
            kind=EnrollmentKind.ROTATE,
            submitted=submitted,
            terminal=complete,
            credential_reference=reference,
        )
    renewed = ConfigProfileAutomationChangeResult(
        profile_id=profile_id,
        kind=EnrollmentKind.RENEW,
        submitted=submitted,
        terminal=submitted.model_copy(update={"stage": EnrollmentStage.COMPLETE}),
        credential_reference=None,
    )
    assert renewed.credential_reference is None
