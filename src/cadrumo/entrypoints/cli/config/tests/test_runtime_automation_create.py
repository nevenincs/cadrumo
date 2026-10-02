"""The first requester command has a closed protected input and output contract."""

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
from cadrumo.entrypoints.cli.config.runtime_access_management_payloads import ConfigProfileAutomationCreateResult
from cadrumo.entrypoints.cli.config.runtime_automation_request import AutomationCreateInput
from cadrumo.entrypoints.cli.config.secure_input import validate_secrets_payload
from cadrumo.entrypoints.cli.errors import CliRefusedBoundaryError

from ...tests.cli_runner import invoke_cached_cli

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_INVALID_JSON = "cli.config.custody.errors.secrets_stdin_invalid_json"
_INVALID_FIELDS = "cli.config.custody.errors.secrets_stdin_missing_fields"


def _proposal() -> EnrollmentProposal:
    return EnrollmentProposal(
        kind=EnrollmentKind.ENROLL,
        scope=AccessScope(
            operations=frozenset({"user-profile.field-mutation"}),
            actions=frozenset({AccessAction.SUBMIT}),
            disclosures=frozenset(),
            periods=None,
            allow_period_independent=True,
            allow_delegation=False,
        ),
        expires_at=now() + timedelta(days=30),
        key_expires_at=now() + timedelta(days=15),
        unattended=True,
        allow_os_lock=False,
    )


def _parse(raw: bytes) -> AutomationCreateInput:
    return validate_secrets_payload(
        raw, AutomationCreateInput, invalid_json_key=_INVALID_JSON, missing_fields_key=_INVALID_FIELDS
    )


def test_protected_proposal_accepts_canonical_json_but_rejects_changed_kind_and_nested_duplicates() -> None:
    proposal = _proposal()
    document = {"proposal": proposal.model_dump(mode="json")}
    parsed = _parse(json.dumps(document).encode())
    assert parsed.proposal == proposal
    assert "user-profile.field-mutation" not in repr(parsed)
    document["proposal"]["kind"] = "renew"
    with pytest.raises(CliRefusedBoundaryError):
        _parse(json.dumps(document).encode())
    raw = b'{"proposal":{"kind":"enroll","kind":"renew"}}'
    with pytest.raises(CliRefusedBoundaryError):
        _parse(raw)
    with pytest.raises(CliRefusedBoundaryError):
        _parse(b'{"proposal":{"kind":"enroll","scope":{"operations":["\\ud800"]}}}')
    document["proposal"]["kind"] = "enroll"
    document["proposal"]["unknown_private_value"] = "must-not-appear-in-refusal"
    with pytest.raises(CliRefusedBoundaryError) as refused:
        _parse(json.dumps(document).encode())
    assert "must-not-appear-in-refusal" not in str(refused.value)


def test_first_request_output_requires_exact_terminal_and_verified_reference() -> None:
    profile_id, request_id, grant_id, reference, key_id = (uuid4() for _ in range(5))
    pending = AutomationReceiptProjection(
        request_id=request_id,
        profile_id=profile_id,
        review_digest="a" * 64,
        grant_id=grant_id,
        stage=EnrollmentStage.REQUESTED,
        key_id=None,
        credential_reference=None,
    )
    completed = AutomationReceiptProjection(
        request_id=request_id,
        profile_id=profile_id,
        review_digest="a" * 64,
        grant_id=grant_id,
        stage=EnrollmentStage.COMPLETE,
        key_id=key_id,
        credential_reference=reference,
    )
    result = ConfigProfileAutomationCreateResult(
        profile_id=profile_id, submitted=pending, terminal=completed, credential_reference=reference
    )
    assert ConfigProfileAutomationCreateResult.model_validate_json(result.model_dump_json()) == result
    with pytest.raises(ValueError):
        ConfigProfileAutomationCreateResult(
            profile_id=uuid4(), submitted=pending, terminal=completed, credential_reference=reference
        )
    with pytest.raises(ValueError):
        ConfigProfileAutomationCreateResult(
            profile_id=profile_id, submitted=pending, terminal=completed, credential_reference=uuid4()
        )


def test_create_parser_requires_explicit_protected_channel_before_admission() -> None:
    help_result = invoke_cached_cli(("config", "profile", "automation", "create", "--help"))
    assert help_result.exit_code == 0, help_result.output
    assert "--secrets-stdin" in help_result.output and "--secrets-fd" in help_result.output
    refused = invoke_cached_cli(("--format", "json", "config", "profile", "automation", "create"))
    assert refused.exit_code != 0
    envelope = json.loads(refused.output)
    assert envelope["command"] == "config.profile.automation.create"
    assert envelope["error"]["code"] == "REFUSED_CLI_BOUNDARY"
    assert envelope["error"]["context"] is None
