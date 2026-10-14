"""CLI presentation for runtime-owned human profile access controls."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

import typer
from pydantic import SecretStr

from cadrumo.application.operations.models import OperationId
from cadrumo.application.user_profile.access_contracts import DisclosurePageRequest
from cadrumo.application.user_profile.access_projections import PublicAccessSession
from cadrumo.application.user_profile.automation_enrollment import (
    AutomationReviewProjection,
    AutomationScopeProjection,
)
from cadrumo.application.user_profile.automation_lifecycle import AutomationDenialKind
from cadrumo.core.external_constants import OutputLanguage
from cadrumo.core.i18n.render import tr
from cadrumo.core.time.clock import now
from cadrumo_client.commands.access_management_payloads import (
    ConfigProfileAutomationDecisionResult,
    ConfigProfileAutomationDenyResult,
    ConfigProfileAutomationDisclosuresResult,
    ConfigProfileAutomationInspectResult,
    ConfigProfileAutomationListResult,
    ConfigProfileDisclosuresResult,
    ConfigProfileLockResult,
    ConfigProfileResumeResult,
    ConfigProfileSessionsResult,
    RuntimeSessionPayload,
)
from cadrumo_client.commands.errors import CliRefusedBoundaryError
from cadrumo_client.commands.profile_binding import require_profile_client
from cadrumo_client.commands.secure_input import (
    MachineSecretPayload,
    prompt_secret_no_echo,
    read_machine_secret_payload,
    select_machine_secret_channel,
)
from cadrumo_client.transport.automation_decision import AutomationDecision, run_automation_decision
from cadrumo_client.transport.automation_inventory import read_automation_inventory
from cadrumo_client.transport.frontend_client import FrontendClient
from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError

from .presentation import activate_subcommand_output_language, emit_envelope
from .profile_language import resolve_runtime_profile_output_language
from .profile_support import require_active_profile_pointer


class ProfileResumeSecrets(MachineSecretPayload):
    """One password carried only by the bounded leaf secret channel."""

    passphrase: SecretStr


class AutomationApprovalSecrets(MachineSecretPayload):
    """Fresh approval password from a dedicated bounded leaf channel."""

    passphrase: SecretStr


def _client(ctx: typer.Context, *, requested_language: OutputLanguage | None) -> FrontendClient:
    pointer = require_active_profile_pointer()
    client = require_profile_client(ctx, expected_profile_id=UUID(str(pointer.bucket_id)))
    language = resolve_runtime_profile_output_language(client, requested=requested_language)
    activate_subcommand_output_language(ctx, language)
    return client


def _refused(error: FrontendRefusedError) -> CliRefusedBoundaryError:
    return CliRefusedBoundaryError(context=error.context)


def _session_payload(session: PublicAccessSession, *, instant: datetime) -> RuntimeSessionPayload:
    return RuntimeSessionPayload(
        session_id=session.session_id,
        profile_id=session.profile_id,
        client_id=session.client_id,
        parent_session_id=session.parent_session_id,
        grant_id=session.grant_id,
        key_id=session.key_id,
        kind=session.kind,
        state=session.state,
        scope=AutomationScopeProjection.from_scope(session.scope),
        expires_at=session.expires_at,
        remaining_seconds=max(0, int((session.expires_at - instant).total_seconds())),
    )


def profile_sessions(ctx: typer.Context, output_language: OutputLanguage | None = None) -> None:
    """List allowlisted sessions and their remaining access for this profile."""
    client = _client(ctx, requested_language=output_language)
    try:
        sessions = client.sessions()
    except FrontendRefusedError as error:
        raise _refused(error) from error
    instant = now()
    projected = tuple(
        _session_payload(item, instant=instant) for item in sorted(sessions, key=lambda item: item.session_id)
    )
    emit_envelope(
        ctx,
        command="config.profile.sessions",
        result=ConfigProfileSessionsResult(profile_id=client.profile_id, sessions=projected),
        lines=tuple(
            f"session\t{item.session_id}\t{item.kind.value}\t{item.state.value}\t{item.remaining_seconds}"
            for item in projected
        ),
    )


def profile_disclosures(ctx: typer.Context, offset: int = 0, output_language: OutputLanguage | None = None) -> None:
    """Count this session's disclosures by category and print one page of the full list.

    Each run is a session of its own, so a page is read by offset alone and is
    not pinned to the list an earlier run read.
    """
    client = _client(ctx, requested_language=output_language)
    try:
        page = client.disclosure_page(DisclosurePageRequest(offset=offset))
    except FrontendRefusedError as error:
        raise _refused(error) from error
    emit_envelope(
        ctx,
        command="config.profile.disclosures",
        result=ConfigProfileDisclosuresResult(
            profile_id=client.profile_id,
            disclosure_count=page.total,
            disclosure_summary=page.disclosure_summary,
            disclosure_digest=page.disclosure_digest,
            page=page,
        ),
        lines=(
            f"disclosures\t{page.total}\t{page.disclosure_digest}",
            *(f"category\t{item.category.value}\t{item.count}" for item in page.disclosure_summary),
            *(
                f"disclosure\t{item.category.value}\t{item.projection_id}\t{item.destination_id}"
                for item in page.entries
            ),
            f"page\t{page.offset}\t{page.total}\t{'' if page.next_offset is None else page.next_offset}",
        ),
    )


def automation_list(ctx: typer.Context, output_language: OutputLanguage | None = None) -> None:
    """Read one authorized public automation inventory through the runtime."""
    client = _client(ctx, requested_language=output_language)
    try:
        completed = read_automation_inventory(client)
    except FrontendRefusedError as error:
        raise _refused(error) from error
    inventory = completed.projection
    emit_envelope(
        ctx,
        command="config.profile.automation.list",
        result=ConfigProfileAutomationListResult(
            profile_id=client.profile_id, operation_id=completed.operation_id, inventory=inventory
        ),
        lines=(
            f"profile_id\t{client.profile_id}",
            f"operation_id\t{completed.operation_id}",
            f"grants\t{len(inventory.grants)}",
            *(
                f"grant\t{item.grant_id}\t{item.state.value}\t{item.expires_at.isoformat()}"
                for item in inventory.grants
            ),
            f"keys\t{len(inventory.keys)}",
            *(f"key\t{item.key_id}\t{item.state.value}\t{item.expires_at.isoformat()}" for item in inventory.keys),
            f"requests\t{len(inventory.requests)}",
            *(
                f"request\t{item.receipt.request_id}\t{item.receipt.stage.value}\t{item.expires_at.isoformat()}"
                for item in inventory.requests
            ),
        ),
    )


def automation_disclosures(
    ctx: typer.Context,
    target_id: UUID,
    offset: int = 0,
    expected_digest: str | None = None,
    output_language: OutputLanguage | None = None,
) -> None:
    """Count one grant's or pending request's disclosures by category and print one page of the list.

    Each run reads the inventory afresh; ``--expected-digest`` pins a later
    page to the list an earlier run counted, and is refused if it changed.
    """
    client = _client(ctx, requested_language=output_language)
    try:
        request = DisclosurePageRequest(offset=offset, expected_digest=expected_digest)
    except ValueError:
        raise CliRefusedBoundaryError(
            translated_message="cli.config.profile.automation.disclosures.invalid_page"
        ) from None
    try:
        completed = read_automation_inventory(client, disclosures_of=target_id, disclosure_page=request)
    except FrontendRefusedError as error:
        raise _refused(error) from error
    page = completed.projection.disclosure_page
    if page is None:
        raise CliRefusedBoundaryError(translated_message="cli.config.profile.automation.review_not_found")
    emit_envelope(
        ctx,
        command="config.profile.automation.disclosures",
        result=ConfigProfileAutomationDisclosuresResult(
            profile_id=client.profile_id,
            inventory_operation_id=completed.operation_id,
            target_id=target_id,
            page=page,
        ),
        lines=(
            f"target_id\t{target_id}",
            f"disclosures\t{page.total}\t{page.disclosure_digest}",
            *(f"category\t{item.category.value}\t{item.count}" for item in page.disclosure_summary),
            *(
                f"disclosure\t{item.category.value}\t{item.projection_id}\t{item.destination_id}"
                for item in page.entries
            ),
            f"page\t{page.offset}\t{page.total}\t{'' if page.next_offset is None else page.next_offset}",
        ),
    )


def _review(client: FrontendClient, request_id: UUID) -> tuple[OperationId, AutomationReviewProjection]:
    """Find one exact currently reviewed request before any approval proof read."""
    try:
        completed = read_automation_inventory(client)
    except FrontendRefusedError as error:
        raise _refused(error) from error
    matching = tuple(item for item in completed.projection.requests if item.receipt.request_id == request_id)
    if len(matching) != 1 or matching[0].receipt.profile_id != client.profile_id:
        raise CliRefusedBoundaryError(translated_message="cli.config.profile.automation.review_not_found")
    return completed.operation_id, matching[0]


def _review_digest(review: AutomationReviewProjection, supplied: str) -> None:
    if supplied != review.receipt.review_digest:
        raise CliRefusedBoundaryError(translated_message="cli.config.profile.automation.review_digest_mismatch")


def _scope_lines(scope: AutomationScopeProjection) -> tuple[str, ...]:
    periods = (
        "all"
        if scope.periods is None
        else "none"
        if not scope.periods
        else ",".join(f"{item.filing_year}/{item.code}" for item in scope.periods)
    )
    categories = ",".join(f"{item.destination_id}/{item.category.value}" for item in scope.disclosure_categories)
    return (
        f"operations\t{','.join(scope.operations)}",
        f"actions\t{','.join(item.value for item in scope.actions)}",
        f"disclosures\t{scope.disclosure_count}\t{scope.disclosure_digest}",
        *(f"disclosure_category_count\t{item.category.value}\t{item.count}" for item in scope.disclosure_summary),
        f"disclosure_categories\t{categories}",
        f"periods\t{periods}",
        f"allow_period_independent\t{str(scope.allow_period_independent).lower()}",
        f"allow_delegation\t{str(scope.allow_delegation).lower()}",
    )


def _review_lines(review: AutomationReviewProjection) -> tuple[str, ...]:
    proposal = review.proposal
    return (
        f"request_id\t{review.receipt.request_id}",
        f"stage\t{review.receipt.stage.value}",
        f"review_digest\t{review.receipt.review_digest}",
        f"client_id\t{review.client_id}",
        f"destination_id\t{review.destination_id}",
        f"review_expires_at\t{review.expires_at.isoformat()}",
        f"kind\t{proposal.kind.value}",
        f"grant_expires_at\t{proposal.expires_at.isoformat()}",
        f"key_expires_at\t{proposal.key_expires_at.isoformat() if proposal.key_expires_at else ''}",
        f"target_grant_id\t{proposal.target_grant_id or ''}",
        f"target_key_id\t{proposal.target_key_id or ''}",
        f"unattended\t{str(proposal.unattended).lower()}",
        f"allow_os_lock\t{str(proposal.allow_os_lock).lower()}",
        *_scope_lines(proposal.scope),
    )


def automation_inspect(ctx: typer.Context, request_id: UUID, output_language: OutputLanguage | None = None) -> None:
    """Show only the selected current public review and its digest."""
    client = _client(ctx, requested_language=output_language)
    inventory_operation_id, review = _review(client, request_id)
    emit_envelope(
        ctx,
        command="config.profile.automation.inspect",
        result=ConfigProfileAutomationInspectResult(
            profile_id=client.profile_id, inventory_operation_id=inventory_operation_id, review=review
        ),
        lines=(
            f"profile_id\t{client.profile_id}",
            f"inventory_operation_id\t{inventory_operation_id}",
            *_review_lines(review),
        ),
    )


def _approval_password(*, secrets_stdin: bool, secrets_fd: int | None) -> bytearray:
    selection = select_machine_secret_channel(secrets_stdin=secrets_stdin, secrets_fd=secrets_fd)
    if selection is None:
        return bytearray(prompt_secret_no_echo(tr("cli.config.custody.current_passphrase_prompt")).encode("utf-8"))
    payload = read_machine_secret_payload(AutomationApprovalSecrets, selection=selection)
    try:
        return bytearray(payload.passphrase.get_secret_value().encode("utf-8"))
    finally:
        del payload


def _decision_result(
    ctx: typer.Context,
    client: FrontendClient,
    *,
    inventory_operation_id: OperationId,
    review: AutomationReviewProjection,
    decision: AutomationDecision,
    password: bytearray | None,
) -> None:
    """Publish exactly one reviewed decision and preserve canonical uncertainty."""
    try:
        completed = run_automation_decision(client, review, decision=decision, password=password)
    except FrontendRefusedError as error:
        raise _refused(error) from error
    emit_envelope(
        ctx,
        command=f"config.profile.automation.{decision}",
        result=ConfigProfileAutomationDecisionResult(
            profile_id=client.profile_id,
            inventory_operation_id=inventory_operation_id,
            operation_id=completed.operation_id,
            decision=decision,
            effect=completed.effect,
            receipt=completed.receipt,
        ),
        lines=(
            f"profile_id\t{client.profile_id}",
            f"inventory_operation_id\t{inventory_operation_id}",
            f"operation_id\t{completed.operation_id}",
            f"decision\t{decision}",
            f"effect\t{completed.effect.value}",
            f"request_id\t{completed.receipt.request_id}",
            f"stage\t{completed.receipt.stage.value}",
        ),
    )


def automation_approve(
    ctx: typer.Context,
    request_id: UUID,
    review_digest: str,
    secrets_stdin: bool = False,
    secrets_fd: int | None = None,
    output_language: OutputLanguage | None = None,
) -> None:
    """Approve an exact current review using a separate fresh password proof."""
    client = _client(ctx, requested_language=output_language)
    inventory_operation_id, review = _review(client, request_id)
    _review_digest(review, review_digest)
    password = _approval_password(secrets_stdin=secrets_stdin, secrets_fd=secrets_fd)
    try:
        _decision_result(
            ctx,
            client,
            inventory_operation_id=inventory_operation_id,
            review=review,
            decision="approve",
            password=password,
        )
    finally:
        password[:] = bytes(len(password))


def automation_decline(
    ctx: typer.Context,
    request_id: UUID,
    review_digest: str,
    output_language: OutputLanguage | None = None,
) -> None:
    """Decline an exact current review without asking for a password."""
    client = _client(ctx, requested_language=output_language)
    inventory_operation_id, review = _review(client, request_id)
    _review_digest(review, review_digest)
    _decision_result(
        ctx,
        client,
        inventory_operation_id=inventory_operation_id,
        review=review,
        decision="decline",
        password=None,
    )


def automation_deny(
    ctx: typer.Context,
    kind: str,
    target_id: UUID | None = None,
    output_language: OutputLanguage | None = None,
) -> None:
    """Revoke one key, one grant, or all profile automation."""
    client = _client(ctx, requested_language=output_language)
    if kind not in {"key", "grant", "all"} or ((kind != "all") != (target_id is not None)):
        raise CliRefusedBoundaryError(translated_message="cli.config.profile.automation.deny.target_mismatch")
    denial_kind = AutomationDenialKind(kind)
    try:
        receipt = client.deny_automation(denial_kind, target_id=target_id)
    except FrontendRefusedError as error:
        raise _refused(error) from error
    emit_envelope(
        ctx,
        command="config.profile.automation.deny",
        result=ConfigProfileAutomationDenyResult(
            profile_id=client.profile_id, kind=denial_kind, target_id=target_id, receipt=receipt
        ),
        lines=(
            f"profile_id\t{client.profile_id}",
            f"kind\t{denial_kind.value}",
            f"access_denied\t{str(receipt.access_denied).lower()}",
            f"cleanup_pending\t{str(receipt.cleanup_pending).lower()}",
        ),
    )


def _lock_result(client: FrontendClient, *, all_sessions: bool, session: UUID | None) -> ConfigProfileLockResult:
    """Preserve the exact selected target and the runtime's actual cascade."""
    if all_sessions and session is not None:
        raise CliRefusedBoundaryError(translated_message="cli.config.profile.lock.selector_conflict")
    if all_sessions:
        denial = client.deny_automation(AutomationDenialKind.PROFILE_LOCK)
        return ConfigProfileLockResult(
            profile_id=client.profile_id,
            scope="profile",
            target_session_id=None,
            session_ids=(),
            denial=denial,
        )
    if session is not None:
        locked = client.revoke_session(session)
        return ConfigProfileLockResult(
            profile_id=client.profile_id,
            scope="selected",
            target_session_id=session,
            session_ids=locked.session_ids,
            denial=None,
        )
    locked = client.lock()
    return ConfigProfileLockResult(
        profile_id=client.profile_id,
        scope="current",
        target_session_id=None,
        session_ids=locked.session_ids,
        denial=None,
    )


def profile_lock(
    ctx: typer.Context,
    all_sessions: bool = False,
    session: UUID | None = None,
    output_language: OutputLanguage | None = None,
) -> None:
    """Retire this session, a selected session, or the whole profile."""
    client = _client(ctx, requested_language=output_language)
    try:
        result = _lock_result(client, all_sessions=all_sessions, session=session)
    except FrontendRefusedError as error:
        raise _refused(error) from error
    emit_envelope(
        ctx,
        command="config.profile.lock",
        result=result,
        lines=(
            f"profile_id\t{client.profile_id}",
            f"scope\t{result.scope}",
            *((f"target_session_id\t{result.target_session_id}",) if result.target_session_id is not None else ()),
            *(f"session_id\t{item}" for item in result.session_ids),
        ),
    )


def _resume_password(*, secrets_stdin: bool, secrets_fd: int | None) -> bytearray:
    selection = select_machine_secret_channel(secrets_stdin=secrets_stdin, secrets_fd=secrets_fd)
    if selection is None:
        return bytearray(prompt_secret_no_echo(tr("cli.config.custody.current_passphrase_prompt")).encode("utf-8"))
    payload = read_machine_secret_payload(ProfileResumeSecrets, selection=selection)
    try:
        return bytearray(payload.passphrase.get_secret_value().encode("utf-8"))
    finally:
        del payload


def profile_resume(
    ctx: typer.Context,
    grant: tuple[UUID, ...] = (),
    secrets_stdin: bool = False,
    secrets_fd: int | None = None,
    output_language: OutputLanguage | None = None,
) -> None:
    """Unlock human access and reactivate only explicitly selected grants."""
    client = _client(ctx, requested_language=output_language)
    password = _resume_password(secrets_stdin=secrets_stdin, secrets_fd=secrets_fd)
    try:
        try:
            receipt = client.recover_profile(password, grants=frozenset(grant))
        except FrontendRefusedError as error:
            raise _refused(error) from error
    finally:
        password[:] = bytes(len(password))
    revocation = receipt.human_sign_in_revocation
    emit_envelope(
        ctx,
        command="config.profile.resume",
        result=ConfigProfileResumeResult(profile_id=client.profile_id, receipt=receipt),
        lines=(
            f"profile_id\t{client.profile_id}",
            f"lock_generation\t{receipt.lock_generation}",
            f"human_receipt_removed\t{None if revocation is None else revocation.receipt_removed}",
            f"human_keychain_removed\t{None if revocation is None else revocation.keychain_removed}",
            *(f"reactivated_grant\t{item}" for item in sorted(receipt.reactivated_grants)),
        ),
    )


__all__ = [
    "AutomationApprovalSecrets",
    "ProfileResumeSecrets",
    "automation_approve",
    "automation_decline",
    "automation_deny",
    "automation_inspect",
    "automation_list",
    "profile_disclosures",
    "profile_lock",
    "profile_resume",
    "profile_sessions",
]
