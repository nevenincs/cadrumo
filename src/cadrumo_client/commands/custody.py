"""Direct AEAT sign-in and sign-out command behavior."""

from __future__ import annotations

import asyncio
from contextlib import suppress
from typing import TYPE_CHECKING, NoReturn
from uuid import UUID

import typer
from pydantic import SecretStr

from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.user_profile.login_session import ProfileLoginOutcome, ProfileReceiptRefusedError
from cadrumo.application.user_profile.profile_pointer import (
    active_profile_pointer_transaction,
    observe_active_profile_pointer,
)
from cadrumo.core.external_constants import OutputLanguage
from cadrumo.core.i18n.render import tr
from cadrumo.core.json_contract import Notice, NoticeSeverity
from cadrumo.core.output_rendering import OutputFormat, render_command_output
from cadrumo_client.commands.custody_payloads import ConfigLogoutResult
from cadrumo_client.commands.errors import CliRefusedBoundaryError, attach_cli_policy_verdict
from cadrumo_client.commands.secure_input import (
    MachineSecretPayload,
    MachineSecretSelection,
    prompt_secret_no_echo,
    read_machine_secret_payload,
    select_machine_secret_channel,
    terminal_can_prompt_for_secrets,
)
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.contracts.sign_in import HumanSignedOut
from cadrumo_client.transport.frontend_client import FrontendClient
from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError
from cadrumo_client.transport.installed_client import open_installed_client

if TYPE_CHECKING:
    pass


class LoginSecrets(MachineSecretPayload):
    """Strict machine-channel payload for ``config login``.

    One bounded JSON object carrying only the profile passphrase as a
    :class:`~pydantic.SecretStr`. The canonical payload base refuses an
    unexpected field and freezes the validated value. The passphrase is never
    accepted as an ``argv`` value.
    """

    passphrase: SecretStr


def _config_logout_result(
    outcome: HumanSignedOut | None,
    *,
    logged_out_profile: str | None,
    already_logged_out: bool,
) -> ConfigLogoutResult:
    """Project the runtime's sign-out facts without inferring remaining access."""
    return ConfigLogoutResult(
        logged_out_profile=logged_out_profile,
        already_logged_out=already_logged_out,
        human_receipt_revoked=outcome is not None,
        receipt_removed=None if outcome is None else outcome.receipt_removed,
        keychain_removed=None if outcome is None else outcome.keychain_removed,
        automation_enabled=None if outcome is None else outcome.automation_enabled,
        automation_access_remains=None if outcome is None else outcome.automation_access_remains,
    )


def _settings_has_explicit_output_language() -> bool:
    """Return whether the operator pinned a supported output language explicitly."""
    from cadrumo.core.config import load_settings
    from cadrumo.core.config_support import coerce_output_language_setting

    try:
        settings = load_settings()
    except (AttributeError, KeyError, ValueError):
        return False
    if "cadrumo_output_language" not in settings.model_fields_set:
        return False
    raw = str(getattr(settings.cadrumo_output_language, "value", settings.cadrumo_output_language))
    return coerce_output_language_setting(raw) is not None


def _hint_via_label(name: str) -> str | None:
    """Resolve an operator-typed profile label to its bucket's language hint.

    Returns ``None`` when the name matches no live profile, which is the
    correct outcome for a UUID that simply carries no hint and for a label
    that names nothing. ``read_profile_bucket`` resolves the label against
    the committed custody capsule projection (``CommittedProfileRepository``,
    seeded by ``list_current_profile_custody_capsule_ids``), whose commit
    marker and label record are plain committed files read without
    unwrapping the bucket's DEK, so this does not depend on the target
    bucket's DEK being intact.
    """
    from cadrumo.application.user_profile.language_resolver import resolve_profile_output_language_hint
    from cadrumo.application.workflow.profile_bucket_scan import read_profile_bucket

    pointer = read_profile_bucket(name)
    if pointer is None:
        return None
    return resolve_profile_output_language_hint(pointer.bucket_id)


def _pin_render_language_to_target_bucket(ctx: typer.Context, *, bucket_id: str) -> None:
    """Pin the render locale to the failed login target's bucket hint.

    A login that cannot unlock its target renders the storage/master-key
    refusal at the CLI boundary AFTER the pointer transaction has unwound
    and restored the previous selection, so the active-profile language
    resolver would otherwise localise the target's failure in the SOURCE
    profile's language. The target's output-language hint is a plaintext,
    bucket-local file readable without the (corrupt) DEK, so it can pin the
    render locale to the target the operator was logging in to. Skipped when
    the operator supplied an explicit language.

    ``bucket_id`` carries whatever the operator typed, which is a label at
    least as often as a UUID. A label resolves no bucket-local hint on its
    own, so it is resolved to its UUID through the committed custody capsule
    projection first: ``read_profile_bucket`` reads the capsule's commit
    marker and label record directly off disk, neither of which needs the
    bucket's DEK, so it stays readable under exactly the corrupt-DEK
    condition this helper exists to serve.
    """
    if _settings_has_explicit_output_language():
        return

    from cadrumo.application.user_profile.language_resolver import resolve_profile_output_language_hint
    from cadrumo.core.config import override_settings
    from cadrumo.core.i18n.render import clear_output_language_cache

    language = resolve_profile_output_language_hint(bucket_id)
    if language is None:
        language = _hint_via_label(bucket_id)
    if language is None:
        return
    ctx.with_resource(override_settings(cadrumo_output_language=language))
    clear_output_language_cache()


def _previous_profile_label(outcome: ProfileLoginOutcome) -> str | None:
    """Name the profile a cross-profile handover signed out by its label, as the active profile is named."""
    if outcome.closed_previous_bucket_id is None:
        return None
    from cadrumo.application.user_profile.login_session import resolve_login_target
    from cadrumo.domain.user_profile.errors import ProfileNotFoundError

    try:
        return resolve_login_target(outcome.closed_previous_bucket_id).label
    except ProfileNotFoundError:
        return None


def _login_notices(outcome: ProfileLoginOutcome, *, previous_profile: str | None = None) -> tuple[Notice, ...]:
    """Project one login outcome's non-blocking diagnostics onto the Notice channel.

    Three distinct operator-visible conditions ride here rather than as
    bespoke ``result`` fields: the idempotent no-op that resumed a
    still-valid session, the cross-profile handover that closed the
    previous profile, and the degraded host that could not custody a
    session key and so logged in for this process only. The closed profile
    is named by ``previous_profile``, its label, never by its identifier.
    """
    notices: list[Notice] = []
    if outcome.already_authenticated:
        notices.append(
            Notice(
                severity=NoticeSeverity.INFO,
                code="config.login.already_authenticated",
                message=tr("cli.config.login.notices.already_authenticated"),
                context={"profile_id": outcome.bucket_id},
            ),
        )
    if outcome.closed_previous_bucket_id is not None:
        notices.append(
            Notice(
                severity=NoticeSeverity.INFO,
                code="config.login.closed_previous_session",
                message=tr("cli.config.login.notices.closed_previous_session"),
                context=None if previous_profile is None else {"previous_profile": previous_profile},
            ),
        )
    if not outcome.session_persisted:
        notices.append(_session_not_persisted_notice(outcome))
    return tuple(notices)


def _session_not_persisted_notice(outcome: ProfileLoginOutcome) -> Notice:
    """Name the prerequisite that kept this sign-in from being stored, and what to do instead.

    The runtime reports only that it kept nothing. This process then asks the
    keychain itself: every later command must read the
    proof from it too, so a keychain this process cannot use explains the
    outcome and decides the remedy. A usable keychain here leaves the cause
    with the runtime, and the message says so rather than blaming the keychain.
    """
    from cadrumo.application.user_profile.login_session import profile_session_keychain_unavailability
    from cadrumo.core.profile_session import KeychainUnavailability

    keychain = profile_session_keychain_unavailability()
    if keychain is None:
        message = tr("cli.config.login.notices.session_not_persisted_unconfirmed")
    elif keychain is KeychainUnavailability.LOGON_WITHOUT_CREDENTIALS:
        message = tr("cli.config.login.notices.session_not_persisted_logon")
    elif keychain is KeychainUnavailability.NO_BACKEND:
        message = tr("cli.config.login.notices.session_not_persisted_no_backend")
    else:
        message = tr("cli.config.login.notices.session_not_persisted")
    context: dict[str, str] = {"profile_id": outcome.bucket_id}
    if keychain is not None:
        context["keychain"] = keychain.value
    return Notice(
        severity=NoticeSeverity.WARNING,
        code="config.login.session_not_persisted",
        message=message,
        context=context,
    )


def _login_through_the_prompt(
    ctx: typer.Context,
    *,
    name: str | None,
    machine_secret: MachineSecretSelection | None,
) -> ProfileLoginOutcome:
    """Admit the exact runtime profile before changing the CLI default target.

    Selection is only a hint for later invocations. Neither candidate failure
    nor successful selection retires another connection or profile receipt.
    """
    from cadrumo.application.user_profile.login_session import ProfileLoginOutcome, resolve_login_target
    from cadrumo.domain.user_profile.errors import ProfileNotFoundError

    interactive = terminal_can_prompt_for_secrets()
    captured = observe_active_profile_pointer()
    target_name = name or captured.bucket_id
    if target_name is None:
        raise CliRefusedBoundaryError(translated_message="cli.config.profile.no_active_profile")
    try:
        target = resolve_login_target(target_name)
    except ProfileNotFoundError:
        raise _unknown_profile_refusal(target_name) from None
    _pin_render_language_to_target_bucket(ctx, bucket_id=target.bucket_id)
    client = asyncio.run(
        open_installed_client(profile_id=UUID(target.bucket_id), frontend=OperationFrontendProjection.CLI)
    )
    try:
        admitted = None
        from cadrumo_client.commands.profile_binding import subscribe_profile_notices

        subscribe_profile_notices(ctx, client)
        # A live sign-in on this OS login is reused whether or not a terminal is attached.
        # Logging in to the profile with it is still the person's sign-in, so it hands over.
        if machine_secret is None:
            with suppress(ProfileReceiptRefusedError):
                admitted = client.resume_receipt(hand_over=True)
        if admitted is None:
            if machine_secret is not None:
                payload = read_machine_secret_payload(LoginSecrets, selection=machine_secret)
                try:
                    proof = bytearray(payload.passphrase.get_secret_value(), "utf-8")
                finally:
                    del payload
            elif interactive:
                proof = bytearray(prompt_secret_no_echo(tr("cli.config.login.passphrase_prompt")), "utf-8")
            else:
                from cadrumo.application.profile_preconditions import profile_password_channel_failure_verdict

                raise attach_cli_policy_verdict(
                    CliRefusedBoundaryError(translated_message="cli.config.login.passphrase_channel_absent"),
                    verdict=profile_password_channel_failure_verdict(profile_name=target.label),
                )
            try:
                admitted = client.login_password(proof, persist_receipt=True)
            finally:
                proof[:] = bytes(len(proof))
        receipt = admitted.human_login
        if receipt is None:
            raise RefusalError(RefusalCode.INVALID_FRAME)
        # The live connection proves admission; the persisted pointer remains
        # non-authoritative metadata and cannot retarget an existing session.
        _require_current_profile_login(client)
        with active_profile_pointer_transaction() as selection:
            # A concurrent sign-in to the same profile already published this selection.
            if selection.read().bucket_id != target.bucket_id:
                selection.compare_and_select(expected=captured, bucket_id=target.bucket_id)
        # One profile is signed in at a time; there was at most one other to sign out.
        signed_out = next(iter(admitted.signed_out_profile_ids), None)
        return ProfileLoginOutcome(
            bucket_id=target.bucket_id,
            label=target.label,
            authenticated_at=receipt.authenticated_at,
            idle_deadline=receipt.idle_deadline,
            absolute_deadline=receipt.absolute_deadline,
            session_persisted=receipt.session_persisted,
            already_authenticated=receipt.resumed,
            closed_previous_bucket_id=None if signed_out is None else str(signed_out),
        )
    except FrontendRefusedError as error:
        _raise_frontend_refusal(error)
    finally:
        client.close()


def config_login(
    ctx: typer.Context,
    name: str | None = None,
    secrets_stdin: bool = False,
    secrets_fd: int | None = None,
    output_language: OutputLanguage | None = None,
) -> None:
    """Authenticate one profile and mint its resumable session."""
    _activate_subcommand_output_language(ctx, output_language)

    machine_secret = select_machine_secret_channel(
        secrets_stdin=secrets_stdin,
        secrets_fd=secrets_fd,
    )
    outcome = _login_through_the_prompt(
        ctx,
        name=name,
        machine_secret=machine_secret,
    )

    from cadrumo_client.commands.custody_payloads import ConfigLoginResult

    previous_profile = _previous_profile_label(outcome)
    result = ConfigLoginResult(
        profile_id=outcome.bucket_id,
        active_profile=outcome.label,
        authenticated_at=outcome.authenticated_at,
        idle_deadline=outcome.idle_deadline,
        absolute_deadline=outcome.absolute_deadline,
        session_persisted=outcome.session_persisted,
        already_authenticated=outcome.already_authenticated,
        closed_previous_profile=previous_profile,
    )
    notices = _login_notices(outcome, previous_profile=previous_profile)
    _emit_envelope(
        ctx,
        command="config.login",
        result=result,
        lines=(
            f"active_profile\t{outcome.label}",
            f"profile_id\t{outcome.bucket_id}",
            f"idle_deadline\t{outcome.idle_deadline.isoformat()}",
            f"absolute_deadline\t{outcome.absolute_deadline.isoformat()}",
            *(notice.message for notice in notices),
        ),
        notices=notices,
    )


def config_logout(
    ctx: typer.Context,
    secrets_stdin: bool = False,
    secrets_fd: int | None = None,
    output_language: OutputLanguage | None = None,
) -> None:
    """Revoke the selected profile's human sign-in through the runtime owner.

    With no stored sign-in to resume, a password given on the machine-secret
    channel proves the person for this sign-out. That is how a sign-in that
    was never persisted, such as a held one, is ended from another process.
    """
    _activate_subcommand_output_language(ctx, output_language)

    machine_secret = select_machine_secret_channel(secrets_stdin=secrets_stdin, secrets_fd=secrets_fd)
    from cadrumo.application.workflow.profile_bucket_scan import read_profile_bucket_by_id

    captured = observe_active_profile_pointer()
    target = read_profile_bucket_by_id(captured.bucket_id) if captured.bucket_id is not None else None
    outcome = None
    if captured.bucket_id is not None:
        client = asyncio.run(
            open_installed_client(profile_id=UUID(captured.bucket_id), frontend=OperationFrontendProjection.CLI)
        )
        try:
            from cadrumo_client.commands.profile_binding import subscribe_profile_notices

            subscribe_profile_notices(ctx, client)
            if machine_secret is None:
                outcome = client.human_sign_out()
            else:
                payload = read_machine_secret_payload(LoginSecrets, selection=machine_secret)
                try:
                    proof = bytearray(payload.passphrase.get_secret_value(), "utf-8")
                finally:
                    del payload
                try:
                    try:
                        # A stored sign-in that resumes proves the person; the password is the fallback
                        # whenever it does not, whatever the reason the runtime gives.
                        client.resume_receipt()
                    except (ProfileReceiptRefusedError, FrontendRefusedError):
                        client.login_password(proof, persist_receipt=False)
                finally:
                    proof[:] = bytes(len(proof))
                outcome = client.human_sign_out()
        except FrontendRefusedError as error:
            _raise_frontend_refusal(error)
        except ProfileReceiptRefusedError as error:
            raise CliRefusedBoundaryError(
                str(error.reason),
                context={"reason": str(error.reason)},
                translated_message="cli.config.errors.profile_session_logout_unproven",
            ) from None
        finally:
            client.close()
    # Selection is a non-authoritative login target, not human access. Keep it
    # available for the next exact login; never overwrite a concurrent selection.
    signed_out = captured.bucket_id
    logged_out_profile = target.label if target is not None else signed_out

    result = _config_logout_result(
        outcome,
        logged_out_profile=logged_out_profile,
        already_logged_out=signed_out is None,
    )
    notices: tuple[Notice, ...] = ()
    if signed_out is None:
        notices += (
            Notice(
                severity=NoticeSeverity.INFO,
                code="config.logout.already_logged_out",
                message=tr("cli.config.logout.notices.already_logged_out"),
            ),
        )
    _emit_envelope(
        ctx,
        command="config.logout",
        result=result,
        lines=(
            f"logged_out_profile\t{logged_out_profile or '<none>'}",
            f"human_receipt_revoked\t{result.human_receipt_revoked}",
            f"receipt_removed\t{result.receipt_removed}",
            f"keychain_removed\t{result.keychain_removed}",
            f"automation_enabled\t{result.automation_enabled}",
            f"automation_access_remains\t{result.automation_access_remains}",
            *(notice.message for notice in notices),
        ),
        notices=notices,
    )


__all__ = ["config_login", "config_logout"]


def _require_current_profile_login(client: FrontendClient) -> None:
    """Require the exact connected authenticated runtime session before selecting its pointer."""
    from cadrumo.application.user_profile.access_contracts import AccessDenialCode

    current = client.status().status
    if (
        current.denial is not None
        or not current.connected
        or not current.credential_authenticated
        or not current.profile_bound
        or current.profile_id != client.profile_id
        or current.session_id != client.session_id
    ):
        raise FrontendRefusedError(
            current.denial.value if current.denial is not None else AccessDenialCode.AUTHENTICATION_REQUIRED.value
        )


def _activate_subcommand_output_language(ctx: typer.Context, language: OutputLanguage | None) -> None:
    """Apply an explicit leaf language choice to this invocation's output."""
    if language is None:
        return
    from cadrumo.core.config import override_settings
    from cadrumo.core.i18n.render import clear_output_language_cache

    ctx.with_resource(override_settings(cadrumo_output_language=language))
    clear_output_language_cache()


def _raise_frontend_refusal(error: FrontendRefusedError) -> NoReturn:
    """Translate the runtime's typed session refusal at the command boundary."""
    from cadrumo.application.user_profile.access_contracts import AccessDenialCode
    from cadrumo.core.profile_session import ProfileSessionRefusalReason, ReceiptBindingRefusal

    sign_in = error.sign_in
    key: str | None = None
    if sign_in is not None and sign_in.reason == "throttled":
        key = "errors.refused.refused_profile_login_throttled"
    elif sign_in is not None and isinstance(sign_in.reason, ProfileSessionRefusalReason):
        if sign_in.binding is ReceiptBindingRefusal.LOGIN_MISMATCH:
            key = "cli.config.errors.profile_session_login_mismatch"
        elif sign_in.binding is ReceiptBindingRefusal.GENERATION_CHANGED:
            key = "cli.config.errors.profile_session_signed_out"
        elif sign_in.binding is not None:
            key = "cli.config.errors.profile_session_unreadable"
        elif sign_in.reason is ProfileSessionRefusalReason.CUSTODY_CHANGED:
            key = "cli.config.errors.profile_session_custody_changed"
        elif sign_in.reason is ProfileSessionRefusalReason.SCHEMA_VERSION_MISMATCH:
            key = "cli.config.errors.profile_session_outdated"
        elif sign_in.reason in {ProfileSessionRefusalReason.MALFORMED, ProfileSessionRefusalReason.TAMPERED}:
            key = "cli.config.errors.profile_session_unreadable"
        elif sign_in.reason is ProfileSessionRefusalReason.KEYRING_UNAVAILABLE:
            key = "errors.auth.auth_storage_keyring_unavailable"
        elif sign_in.reason in {
            ProfileSessionRefusalReason.ABSENT,
            ProfileSessionRefusalReason.KEYCHAIN_ENTRY_MISSING,
        }:
            key = "cli.config.errors.profile_session_absent"
        else:
            key = "cli.config.errors.profile_session_expired"
    elif error.reason == AccessDenialCode.PROFILE_LOCKED.value:
        key = "errors.refused.profile_locked"
    raise CliRefusedBoundaryError(error.reason, context=error.context, translated_message=key) from None


def _emit_envelope(
    ctx: typer.Context,
    *,
    command: str,
    result: object,
    lines: tuple[str, ...],
    notices: tuple[Notice, ...] = (),
) -> None:
    """Render a typed direct-auth result through the shared success boundary."""
    from cadrumo.application.operator_output.emit import emit_operator_json_success
    from cadrumo.application.operator_output.sandbox_notice import sandbox_banner_line, sandbox_notice_for_active_bucket
    from cadrumo.application.workflow.profile_bucket_scan import read_profile_bucket_by_id
    from cadrumo.core.bucket_pointer import resolve_active_bucket_id

    root = ctx.find_root()
    root_state = root.obj if isinstance(root.obj, dict) else {}
    raw_format = root_state.get("format", root.params.get("format", root.params.get("format_", "text")))
    output_format = raw_format if isinstance(raw_format, OutputFormat) else OutputFormat(raw_format)
    active_id = resolve_active_bucket_id()
    pointer = None if active_id is None else read_profile_bucket_by_id(active_id)
    active_profile = None if pointer is None else pointer.label
    if output_format is OutputFormat.JSON:
        emit_operator_json_success(command, result, notices=notices, active_profile=active_profile)
        return
    notice_rows = tuple(f"notice\t{notice.code}\t{notice.message}" for notice in notices)
    rendered_lines = (*lines, *notice_rows)
    sandbox = sandbox_notice_for_active_bucket()
    if sandbox is not None:
        rendered_lines = (sandbox_banner_line(sandbox), *rendered_lines)
    rendered = render_command_output(format_name=output_format.value, payload=result, lines=rendered_lines)
    if rendered.text:
        typer.echo(rendered.text)


def _unknown_profile_refusal(name: str) -> Exception:
    """Keep the typed profile-selection verdict without importing the AEAT CLI."""
    from cadrumo.application.profile_preconditions import ProfileSelectionFailure, profile_selection_failure_verdict
    from cadrumo.domain.user_profile.errors import ProfileNotFoundError

    error = ProfileNotFoundError(
        translated_message="cli.config.profile.unknown_profile",
        context={"name": name},
    )
    return attach_cli_policy_verdict(
        error,
        verdict=profile_selection_failure_verdict(
            ProfileSelectionFailure.UNKNOWN,
            requested_profile=name,
        ),
    )
