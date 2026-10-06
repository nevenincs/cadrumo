"""Config custody behavior handlers."""

from __future__ import annotations

import asyncio
from contextlib import suppress
from typing import TYPE_CHECKING
from uuid import UUID

import typer
from pydantic import SecretStr

from ....adapters.local_runtime.frontend_client import RuntimeFrontendClient
from ....core.external_constants import OutputLanguage
from ....core.i18n.render import tr
from ....core.json_contract import Notice, NoticeSeverity
from ..common import activate_subcommand_output_language as _activate_subcommand_output_language
from ..common import emit_envelope

if TYPE_CHECKING:
    from ....application.user_profile.login_session import ProfileLoginOutcome


from .secure_input import MachineSecretPayload, MachineSecretSelection


class LoginSecrets(MachineSecretPayload):
    """Strict machine-channel payload for ``config login``.

    One bounded JSON object carrying only the profile passphrase as a
    :class:`~pydantic.SecretStr`. The canonical payload base refuses an
    unexpected field and freezes the validated value. The passphrase is never
    accepted as an ``argv`` value.
    """

    passphrase: SecretStr


def _settings_has_explicit_output_language() -> bool:
    """Return whether the operator pinned a supported output language explicitly."""
    from ....core.config import load_settings
    from ....core.config_support import coerce_output_language_setting

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
    from ....application.user_profile.language_resolver import resolve_profile_output_language_hint
    from ....application.workflow.profile_bucket_scan import read_profile_bucket

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

    from ....application.user_profile.language_resolver import resolve_profile_output_language_hint
    from ....core.config import override_settings
    from ....core.i18n.render import clear_output_language_cache

    language = resolve_profile_output_language_hint(bucket_id)
    if language is None:
        language = _hint_via_label(bucket_id)
    if language is None:
        return
    ctx.with_resource(override_settings(cadrumo_output_language=language))
    clear_output_language_cache()


def _login_notices(outcome: ProfileLoginOutcome) -> tuple[Notice, ...]:
    """Project one login outcome's non-blocking diagnostics onto the Notice channel.

    Three distinct operator-visible conditions ride here rather than as
    bespoke ``result`` fields: the idempotent no-op that resumed a
    still-valid session, the cross-profile handover that closed the
    previous profile, and the degraded host that could not custody a
    session key and so logged in for this process only.
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
                context={"previous_profile_id": outcome.closed_previous_bucket_id},
            ),
        )
    if not outcome.session_persisted:
        notices.append(
            Notice(
                severity=NoticeSeverity.WARNING,
                code="config.login.session_not_persisted",
                message=tr("cli.config.login.notices.session_not_persisted"),
                context={"profile_id": outcome.bucket_id},
            ),
        )
    return tuple(notices)


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
    from cadrumo.adapters.local_runtime.runtime_client import open_installed_runtime_client

    from ....adapters.local_runtime.frontend_client_contracts import RuntimeFrontendRefusedError
    from ....application.operations.registry import OperationFrontendProjection
    from ....application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
    from ....application.user_profile.login_session import (
        ProfileLoginOutcome,
        ProfileReceiptRefusedError,
        resolve_login_target,
    )
    from ....application.user_profile.profile_pointer import (
        active_profile_pointer_transaction,
        observe_active_profile_pointer,
    )
    from ....domain.user_profile.errors import ProfileNotFoundError
    from ..common import no_active_profile_refusal
    from ..errors import CliRefusedBoundaryError
    from ._profile_support import unknown_profile_refusal
    from .secure_input import prompt_secret_no_echo, read_machine_secret_payload, terminal_can_prompt_for_secrets

    interactive = terminal_can_prompt_for_secrets()
    if machine_secret is None and not interactive:
        raise CliRefusedBoundaryError(translated_message="cli.config.login.passphrase_channel_absent")
    captured = observe_active_profile_pointer()
    target_name = name or captured.bucket_id
    if target_name is None:
        raise no_active_profile_refusal()
    try:
        target = resolve_login_target(target_name)
    except ProfileNotFoundError:
        raise unknown_profile_refusal(target_name) from None
    _pin_render_language_to_target_bucket(ctx, bucket_id=target.bucket_id)
    client = asyncio.run(
        open_installed_runtime_client(profile_id=UUID(target.bucket_id), frontend=OperationFrontendProjection.CLI)
    )
    try:
        admitted = None
        if machine_secret is None and interactive:
            with suppress(ProfileReceiptRefusedError):
                admitted = client.resume_receipt()
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
                raise CliRefusedBoundaryError(translated_message="cli.config.login.passphrase_channel_absent")
            try:
                admitted = client.login_password(proof, persist_receipt=True)
            finally:
                proof[:] = bytes(len(proof))
        receipt = admitted.human_login
        if receipt is None:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        # The live connection proves admission; the persisted pointer remains
        # non-authoritative metadata and cannot retarget an existing session.
        _require_current_profile_login(client)
        with active_profile_pointer_transaction() as selection:
            selection.compare_and_select(expected=captured, bucket_id=target.bucket_id)
        return ProfileLoginOutcome(
            bucket_id=target.bucket_id,
            label=target.label,
            authenticated_at=receipt.authenticated_at,
            idle_deadline=receipt.idle_deadline,
            absolute_deadline=receipt.absolute_deadline,
            session_persisted=receipt.session_persisted,
            already_authenticated=receipt.resumed,
        )
    except RuntimeFrontendRefusedError as error:
        raise CliRefusedBoundaryError(error.reason, context=error.context) from None
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
    from .secure_input import select_machine_secret_channel

    machine_secret = select_machine_secret_channel(
        secrets_stdin=secrets_stdin,
        secrets_fd=secrets_fd,
    )
    outcome = _login_through_the_prompt(
        ctx,
        name=name,
        machine_secret=machine_secret,
    )

    from ..config_payloads import ConfigLoginResult

    result = ConfigLoginResult(
        profile_id=outcome.bucket_id,
        active_profile=outcome.label,
        authenticated_at=outcome.authenticated_at,
        idle_deadline=outcome.idle_deadline,
        absolute_deadline=outcome.absolute_deadline,
        session_persisted=outcome.session_persisted,
        already_authenticated=outcome.already_authenticated,
        closed_previous_profile=outcome.closed_previous_bucket_id,
    )
    notices = _login_notices(outcome)
    emit_envelope(
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


def config_sign_in_status(
    ctx: typer.Context,
    output_language: OutputLanguage | None = None,
) -> None:
    """Observe the active profile without borrowing proof or extending sign-in."""
    _activate_subcommand_output_language(ctx, output_language)
    from cadrumo.adapters.local_runtime.runtime_client import open_installed_runtime_client

    from ....application.operations.registry import OperationFrontendProjection
    from ....application.runtime.sign_in import SignInPresence, SignInStatus
    from ....application.user_profile.profile_pointer import observe_active_profile_pointer
    from ..config_payloads import ConfigSignInStatusResult

    captured = observe_active_profile_pointer()
    status = SignInStatus(presence=SignInPresence.ABSENT)
    if captured.bucket_id is not None:
        client = asyncio.run(
            open_installed_runtime_client(profile_id=UUID(captured.bucket_id), frontend=OperationFrontendProjection.CLI)
        )
        try:
            status = client.sign_in_status().status
        finally:
            client.close()
    result = ConfigSignInStatusResult(profile_id=captured.bucket_id, status=status)
    emit_envelope(
        ctx,
        command="config.sign-in-status",
        result=result,
        lines=(
            f"presence\t{status.presence.value}",
            f"idle_deadline\t{status.idle_deadline.isoformat() if status.idle_deadline is not None else '<none>'}",
            "absolute_deadline\t"
            f"{status.absolute_deadline.isoformat() if status.absolute_deadline is not None else '<none>'}",
        ),
    )


def config_logout(
    ctx: typer.Context,
    output_language: OutputLanguage | None = None,
) -> None:
    """Revoke the selected profile's human sign-in through the runtime owner."""
    _activate_subcommand_output_language(ctx, output_language)
    from cadrumo.adapters.local_runtime.runtime_client import open_installed_runtime_client

    from ....adapters.local_runtime.frontend_client_contracts import RuntimeFrontendRefusedError
    from ....application.operations.registry import OperationFrontendProjection
    from ....application.user_profile.login_session import ProfileReceiptRefusedError
    from ....application.user_profile.profile_pointer import observe_active_profile_pointer
    from ....application.workflow.profile_bucket_scan import read_profile_bucket
    from ..errors import CliRefusedBoundaryError

    captured = observe_active_profile_pointer()
    target = read_profile_bucket(captured.bucket_id) if captured.bucket_id is not None else None
    outcome = None
    if captured.bucket_id is not None:
        client = asyncio.run(
            open_installed_runtime_client(profile_id=UUID(captured.bucket_id), frontend=OperationFrontendProjection.CLI)
        )
        try:
            outcome = client.human_sign_out()
        except (RuntimeFrontendRefusedError, ProfileReceiptRefusedError) as error:
            raise CliRefusedBoundaryError(str(error.reason), context={"reason": str(error.reason)}) from None
        finally:
            client.close()
    # Selection is a non-authoritative login target, not human access. Keep it
    # available for the next exact login; never overwrite a concurrent selection.
    signed_out = captured.bucket_id
    logged_out_profile = target.label if target is not None else signed_out

    from ..config_payloads import ConfigLogoutResult

    result = ConfigLogoutResult(
        logged_out_profile=logged_out_profile,
        already_logged_out=signed_out is None,
        human_receipt_revoked=outcome is not None,
        receipt_removed=None if outcome is None else outcome.receipt_removed,
        keychain_removed=None if outcome is None else outcome.keychain_removed,
        automation_enabled=None if outcome is None else outcome.automation_enabled,
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
    emit_envelope(
        ctx,
        command="config.logout",
        result=result,
        lines=(
            f"logged_out_profile\t{logged_out_profile or '<none>'}",
            f"human_receipt_revoked\t{result.human_receipt_revoked}",
            f"receipt_removed\t{result.receipt_removed}",
            f"keychain_removed\t{result.keychain_removed}",
            f"automation_enabled\t{result.automation_enabled}",
            *(notice.message for notice in notices),
        ),
        notices=notices,
    )


__all__ = ["config_login", "config_logout", "config_sign_in_status"]


def _require_current_profile_login(client: RuntimeFrontendClient) -> None:
    """Require the exact connected authenticated runtime session before selecting its pointer."""
    from ....adapters.local_runtime.frontend_client_contracts import RuntimeFrontendRefusedError
    from ....application.user_profile.access_contracts import AccessDenialCode

    current = client.status().status
    if (
        current.denial is not None
        or not current.connected
        or not current.credential_authenticated
        or not current.profile_bound
        or current.profile_id != client.profile_id
        or current.session_id != client.session_id
    ):
        raise RuntimeFrontendRefusedError(
            current.denial.value if current.denial is not None else AccessDenialCode.AUTHENTICATION_REQUIRED.value
        )
