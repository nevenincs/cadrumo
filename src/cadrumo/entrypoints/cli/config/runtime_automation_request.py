"""Enrollment and own-grant changes through verified requester connections."""

from __future__ import annotations

import asyncio
import json
import time
from uuid import UUID

import typer
from pydantic import Field, field_validator

from cadrumo.adapters.local_runtime.runtime_client import open_installed_runtime_client
from cadrumo.adapters.local_runtime.runtime_credentials import open_installed_credential_client
from cadrumo.adapters.persistence.storage.custody.automation_store_composition import installed_automation_secret_store

from ....adapters.local_runtime.automation_requester import AutomationRequesterJourney
from ....adapters.local_runtime.frontend_client import RuntimeFrontendRefusedError
from ....application.operations.registry import OperationFrontendProjection
from ....application.runtime.deadline_budget import remaining_budget
from ....application.user_profile.automation_enrollment import (
    AutomationReceiptProjection,
    EnrollmentKind,
    EnrollmentProposal,
)
from ....core.external_constants import OutputLanguage
from ....core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ..common import activate_subcommand_output_language, emit_envelope
from ..errors import CliRefusedBoundaryError
from ..runtime_profile_admission import require_automation_change_credential_reference
from ..runtime_profile_binding import require_profile_client
from ._profile_support import require_active_profile_pointer
from .runtime_access_management_payloads import (
    ConfigProfileAutomationChangeResult,
    ConfigProfileAutomationCreateResult,
)
from .runtime_profile_view import resolve_runtime_profile_output_language
from .secure_input import (
    MachineSecretPayload,
    MachineSecretSelection,
    read_machine_secret_payload,
    select_machine_secret_channel,
    stage_machine_secret_payload,
)


def _proposal_from_json(value: object) -> EnrollmentProposal:
    if not isinstance(value, dict):
        raise ValueError("invalid enrollment proposal")
    try:
        encoded = json.dumps(value, allow_nan=False, ensure_ascii=True).encode("utf-8")
        return EnrollmentProposal.model_validate_json(encoded)
    except (TypeError, ValueError):
        raise ValueError("invalid enrollment proposal") from None


class AutomationCreateInput(MachineSecretPayload):
    """One hidden, strictly validated private ENROLL proposal from a bounded channel."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    proposal: EnrollmentProposal = Field(repr=False)

    @field_validator("proposal", mode="before")
    @classmethod
    def _decode_proposal(cls, value: object) -> EnrollmentProposal:
        proposal = _proposal_from_json(value)
        if proposal.kind is not EnrollmentKind.ENROLL:
            raise ValueError("automation create requires an ENROLL proposal")
        return proposal


class AutomationChangeInput(MachineSecretPayload):
    """One hidden own-grant mutation proposal from the bounded leaf channel."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    proposal: EnrollmentProposal = Field(repr=False)

    @field_validator("proposal", mode="before")
    @classmethod
    def _decode_proposal(cls, value: object) -> EnrollmentProposal:
        proposal = _proposal_from_json(value)
        if proposal.kind is EnrollmentKind.ENROLL:
            raise ValueError("automation change requires an own-grant proposal")
        return proposal


def _required_change_kind(kind: object) -> EnrollmentKind:
    if not isinstance(kind, str) or kind not in {"rotate", "renew", "change_scope"}:
        raise CliRefusedBoundaryError(translated_message="cli.config.custody.errors.automation_change_kind_mismatch")
    return EnrollmentKind(kind)


def _matching_change_payload(payload: AutomationChangeInput, kind: object) -> EnrollmentProposal:
    if payload.proposal.kind is not _required_change_kind(kind):
        raise CliRefusedBoundaryError(translated_message="cli.config.custody.errors.automation_change_kind_mismatch")
    return payload.proposal


def stage_automation_change_input(*, selection: MachineSecretSelection, kind: object) -> None:
    """Refuse a mismatched protected proposal before native root admission."""
    payload = read_machine_secret_payload(AutomationChangeInput, selection=selection)
    _matching_change_payload(payload, kind)
    stage_machine_secret_payload(payload)


def automation_create(
    ctx: typer.Context,
    secrets_stdin: bool = False,
    secrets_fd: int | None = None,
    output_language: OutputLanguage | None = None,
) -> None:
    """Submit one first enrollment and serve protected delivery until terminal."""
    selection = select_machine_secret_channel(secrets_stdin=secrets_stdin, secrets_fd=secrets_fd)
    if selection is None:
        raise CliRefusedBoundaryError(
            translated_message="cli.config.custody.errors.automation_create_proposal_required"
        )
    payload = read_machine_secret_payload(AutomationCreateInput, selection=selection)
    proposal = payload.proposal
    del payload
    profile_id = UUID(str(require_active_profile_pointer().bucket_id))
    store = installed_automation_secret_store()
    client = asyncio.run(open_installed_runtime_client(profile_id=profile_id, frontend=OperationFrontendProjection.CLI))
    try:
        language = resolve_runtime_profile_output_language(client, requested=output_language)
        activate_subcommand_output_language(ctx, language)
        try:
            enrollment = client.prepare_enrollment(store)
        except RuntimeFrontendRefusedError as error:
            raise CliRefusedBoundaryError(context={"reason": error.reason}) from error
        journey = AutomationRequesterJourney(enrollment, timeout=300)
        submitted = journey.submit(proposal)
        completed = journey.wait_for_terminal()
        terminal = completed.terminal
        reference = None if completed.credential is None else completed.credential.credential_reference
        emit_envelope(
            ctx,
            command="config.profile.automation.create",
            result=ConfigProfileAutomationCreateResult(
                profile_id=profile_id,
                submitted=submitted,
                terminal=terminal,
                credential_reference=reference,
            ),
            lines=(
                f"profile_id\t{profile_id}",
                f"request_id\t{terminal.request_id}",
                f"review_digest\t{terminal.review_digest}",
                f"stage\t{terminal.stage.value}",
                *((f"credential_reference\t{reference}",) if reference is not None else ()),
            ),
        )
    finally:
        client.close()


def automation_change(
    ctx: typer.Context,
    kind: str,
    secrets_stdin: bool = False,
    secrets_fd: int | None = None,
    output_language: OutputLanguage | None = None,
) -> None:
    """Publish one reviewed own-grant change and reconcile under fresh root proof."""
    selection = select_machine_secret_channel(secrets_stdin=secrets_stdin, secrets_fd=secrets_fd)
    if selection is None:
        raise CliRefusedBoundaryError(
            translated_message="cli.config.custody.errors.automation_change_proposal_required"
        )
    payload = read_machine_secret_payload(AutomationChangeInput, selection=selection)
    proposal = _matching_change_payload(payload, kind)
    del payload
    original_reference = require_automation_change_credential_reference(ctx)
    profile_id = UUID(str(require_active_profile_pointer().bucket_id))
    client = require_profile_client(ctx, expected_profile_id=profile_id)
    language = resolve_runtime_profile_output_language(client, requested=output_language)
    activate_subcommand_output_language(ctx, language)
    store = installed_automation_secret_store()
    try:
        enrollment = client.prepare_grant_change(store)
    except RuntimeFrontendRefusedError as error:
        raise CliRefusedBoundaryError(context={"reason": error.reason}) from error

    def reconcile(submitted: AutomationReceiptProjection, *, timeout: float) -> AutomationReceiptProjection:
        """Prove current own-grant authority on a new exact-profile connection."""
        deadline = time.monotonic() + timeout
        reference = (
            enrollment.delivered_credential_metadata().credential_reference
            if proposal.kind is EnrollmentKind.ROTATE
            else original_reference
        )
        fresh = asyncio.run(
            open_installed_credential_client(
                profile_id=profile_id,
                credential_reference=reference,
                frontend=OperationFrontendProjection.CLI,
                timeout=remaining_budget(deadline),
                secrets_store=store,
            )
        )
        try:
            return fresh.reconcile_enrollment(submitted.request_id, timeout=remaining_budget(deadline))
        finally:
            fresh.close()

    journey = AutomationRequesterJourney(enrollment, timeout=300, reconcile=reconcile)
    submitted = journey.submit(proposal)
    completed = journey.wait_for_terminal()
    reference = None if completed.credential is None else completed.credential.credential_reference
    emit_envelope(
        ctx,
        command="config.profile.automation.change",
        result=ConfigProfileAutomationChangeResult(
            profile_id=profile_id,
            kind=proposal.kind,
            submitted=submitted,
            terminal=completed.terminal,
            credential_reference=reference,
        ),
        lines=(
            f"profile_id\t{profile_id}",
            f"kind\t{proposal.kind.value}",
            f"request_id\t{completed.terminal.request_id}",
            f"review_digest\t{completed.terminal.review_digest}",
            f"stage\t{completed.terminal.stage.value}",
            *((f"credential_reference\t{reference}",) if reference is not None else ()),
        ),
    )


__all__ = [
    "AutomationChangeInput",
    "AutomationCreateInput",
    "automation_change",
    "automation_create",
    "stage_automation_change_input",
]
