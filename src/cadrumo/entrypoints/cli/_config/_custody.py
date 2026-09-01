"""Config custody behavior handlers."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING
from uuid import UUID

import typer
from pydantic import SecretStr

from ....core.external_constants import OutputLanguage
from ....core.i18n import tr
from ....core.json_contract import Notice, NoticeSeverity
from .._common import activate_subcommand_output_language as _activate_subcommand_output_language
from .._common import active_profile_label, emit_envelope

if TYPE_CHECKING:
    from ....application.user_profile.login_session import ProfileLoginOutcome


from .secure_input import MachineSecretPayload, MachineSecretSelection

#: Actor reference the logout command submits its supervised operation under.
_LOGOUT_ACTOR_REF = "cli:config-logout"


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
    from ....core.config import coerce_output_language_setting, load_settings

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
    from ....core.i18n import clear_output_language_cache

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
    """Log in through one explicit machine channel or a verified line prompt.

    Scripted, piped, CI, and JSON callers supply a bounded
    ``--secrets-stdin`` payload or one-shot ``--secrets-fd`` descriptor. A
    real console that cannot go full-screen receives the hardened no-echo
    prompt. With neither route, this CLI boundary refuses before authentication
    instead of delegating secret discovery to environment, settings, keyring,
    or the storage substrate.

    The descriptor is drained before the login call rather than inside the
    callback, so an unreadable or already-consumed descriptor refuses
    before any custody work begins. Both machine channels close over the
    value they read; neither re-reads if the login layer invokes the
    callback more than once.

    The callback always closes over a value acquired by this entrypoint, so
    application and storage code cannot silently redeclare transport policy.
    """
    from ....adapters.persistence.storage.custody.errors import ProfileCustodyPasswordError
    from ....application.user_profile.authentication import ProfileAuthenticationRefusedError
    from ....application.user_profile.login_session import login_profile
    from ..errors import CliRefusedBoundaryError
    from .secure_input import prompt_secret_no_echo, read_machine_secret_payload, terminal_can_prompt_for_secrets

    if machine_secret is not None:
        secrets = read_machine_secret_payload(LoginSecrets, selection=machine_secret)
        secret = secrets.passphrase.get_secret_value()

        def passphrase_callback() -> str:
            """Resolve the passphrase already read from the bounded machine channel."""
            return secret

    elif terminal_can_prompt_for_secrets():

        def passphrase_callback() -> str:
            """Read the profile passphrase on the hardened no-echo channel."""
            return prompt_secret_no_echo(tr("cli.config.login.passphrase_prompt"))

    else:
        raise CliRefusedBoundaryError(
            translated_message="cli.config.login.passphrase_channel_absent",
        )

    try:
        return login_profile(name=name, passphrase_callback=passphrase_callback)
    except (ProfileAuthenticationRefusedError, ProfileCustodyPasswordError):
        # The target could not be unlocked (a wrong passphrase, a corrupt
        # bucket DEK); render the refusal in the target's own output
        # language rather than the previous selection's. Both a UUID and a
        # label resolve a bucket-local hint here: login owns label
        # resolution internally and does not surface the resolved id on the
        # failure path, so the helper re-resolves a label through the
        # committed custody capsule projection, which stays readable while
        # the target's DEK is corrupt.
        if name is not None:
            _pin_render_language_to_target_bucket(ctx, bucket_id=name)
        raise


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

    from .._config_payloads import ConfigLoginResult

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


async def _run_logout_operation(profile_id: UUID) -> None:
    """Strong-close through the supervised operation platform, then settle it.

    The composed graph owns the journal, the lease and the executor. Its start
    door awaits the executor to completion, so the session is closed by the time
    this returns and the caller needs no observation pass to learn that.
    """
    from ....application.user_profile.operations import build_profile_logout_operation_request
    from ...operation_composition import compose_operation_dependencies

    services = compose_operation_dependencies()
    try:
        submission = await services.submission.submit(
            build_profile_logout_operation_request(profile_id),
            actor_ref=_LOGOUT_ACTOR_REF,
        )
        await services.submission.start(submission.receipt.operation_id)
    finally:
        await services.shutdown()


def config_logout(
    ctx: typer.Context,
    output_language: OutputLanguage | None = None,
) -> None:
    """Strong-close the profile session: seal, delete both halves, clear the pointer."""
    _activate_subcommand_output_language(ctx, output_language)
    from ....application.user_profile.login_session import has_live_profile_session, logout_active_profile
    from ....core.bucket_pointer import resolve_active_bucket_id

    signed_out_label = active_profile_label()
    active_bucket_id = resolve_active_bucket_id()
    signed_out = None
    if has_live_profile_session() and active_bucket_id is not None:
        # Supervision journals into profile-bound encrypted storage, which only
        # an open session can unlock. With a session there IS something to
        # strong-close and the journal records the operator's verb.
        asyncio.run(_run_logout_operation(UUID(str(active_bucket_id))))
        signed_out = str(active_bucket_id)
    else:
        # No open session: nothing to strong-close, only a stale selection to
        # clear. The same revocation authority the supervised executor calls
        # does that under the root lock, and returns None when there was not
        # even a selection, which keeps a repeated logout idempotent.
        signed_out = logout_active_profile()
    logged_out_profile = signed_out_label or signed_out

    from .._config_payloads import ConfigLogoutResult

    result = ConfigLogoutResult(
        logged_out_profile=logged_out_profile,
        already_logged_out=signed_out is None,
    )
    notices: tuple[Notice, ...] = ()
    if signed_out is None:
        notices = (
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
            *(notice.message for notice in notices),
        ),
        notices=notices,
    )


__all__ = ["config_login", "config_logout"]
