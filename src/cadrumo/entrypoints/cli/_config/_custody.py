"""Config custody command registration."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

import typer
from pydantic import BaseModel, ConfigDict, SecretStr

from ....core.external_constants import OutputLanguage
from ....core.i18n import tr
from ....core.json_contract import Notice, NoticeSeverity
from .._common import _emit_envelope, active_profile_label
from .._common import activate_subcommand_output_language as _activate_subcommand_output_language

if TYPE_CHECKING:
    from ....application.user_profile import ProfileLoginOutcome


class _LoginSecrets(BaseModel):
    """Strict ``--secrets-stdin`` payload for ``config login``.

    One bounded JSON object carrying only the profile passphrase as a
    :class:`~pydantic.SecretStr`; ``extra="forbid"`` refuses an unexpected
    field. The passphrase is never accepted as an ``argv`` value.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

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
    from ....application.user_profile import resolve_profile_output_language_hint
    from ....application.workflow import read_profile_bucket

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

    from ....application.user_profile import resolve_profile_output_language_hint
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


def _login_through_the_screen(*, name: str | None) -> ProfileLoginOutcome:
    """Log in on the full-screen surface, refusing when the operator leaves.

    Leaving the screen without unlocking is an ordinary choice, but it is
    not a successful login: ``login`` is the precondition every other verb
    is gated on, so reporting success with no session minted would hand a
    caller an exit code that says the gate is open when it is shut. The
    refusal names the verb to run again, exactly as the session gate does.

    A named target preselects its row; an unknown one is refused before
    the screen opens, so a mistyped label can never quietly become a
    login to whichever profile happened to sort first.
    """
    from ....application.cli_exception_preconditions import (
        CliExceptionPrecondition,
        cli_exception_no_recovery_verdict,
    )
    from .._common import attach_cli_policy_verdict
    from .._errors import CliRefusedBoundaryError
    from ._login_frontend import preselected_profile_id, present_login

    outcome = present_login(preselected=preselected_profile_id(name))
    if outcome is None:
        raise attach_cli_policy_verdict(
            CliRefusedBoundaryError(
                translated_message="cli.config.login.refusal.abandoned",
            ),
            verdict=cli_exception_no_recovery_verdict(
                CliExceptionPrecondition.LOGIN_COMPLETED,
                facts={"login_completed": False},
            ),
        )
    return outcome


def _login_through_the_prompt(
    ctx: typer.Context,
    *,
    name: str | None,
    secrets_stdin: bool,
    secrets_fd: int | None,
) -> ProfileLoginOutcome:
    """Log in through the line prompt, a machine secret channel, or the env secret.

    The path every scripted, piped, CI, and JSON caller takes: a named
    target, a bounded ``--secrets-stdin`` payload, a one-shot
    ``--secrets-fd`` descriptor, a configured
    ``CADRUMO_SECRET_PASSPHRASE``, or a line prompt on a real console that
    cannot go full-screen — and the same refusal when none of those
    supplied a passphrase.

    The descriptor is drained before the login call rather than inside the
    callback, so an unreadable or already-consumed descriptor refuses
    before any custody work begins. Both machine channels close over the
    value they read; neither re-reads if the login layer invokes the
    callback more than once.

    That line prompt is explicitly supplied rather than left to default.
    Passing no callback hands the read to the storage substrate's own
    resolver, which ends at a bare :func:`getpass.getpass`: an untranslated
    English prompt that silently degrades to an *echoing* read whenever it
    cannot control the terminal. ``login`` was the only custody path in
    this package still reaching it; every other secret is read through
    ``prompt_secret_no_echo``, which promotes that degradation to a
    refusal.

    The callback is supplied ONLY when it would change which channel is
    used — a real console, with no configured passphrase to consume first.
    A headless host keeps the substrate's env-var precedence, and a
    console-less one keeps the substrate's own refusal and exit code
    rather than acquiring this package's; neither behaviour moves.
    """
    from ....adapters.persistence.storage.custody import ProfileCustodyPasswordError
    from ....application.user_profile import ProfileAuthenticationRefusedError, login_profile
    from ....core.config import load_settings
    from .. import _headless_secret_channel_active
    from .._errors import CliRefusedBoundaryError
    from ._secure_input import (
        prompt_secret_no_echo,
        read_secrets_fd,
        read_secrets_stdin,
        terminal_can_prompt_for_secrets,
    )

    # Naming both machine channels is already refused upstream, so this reads
    # at most one of them; the ordering expresses no precedence.
    secrets: _LoginSecrets | None = None
    if secrets_fd is not None:
        secrets = read_secrets_fd(_LoginSecrets, descriptor=secrets_fd)
    elif secrets_stdin:
        secrets = read_secrets_stdin(_LoginSecrets)

    passphrase_callback: Callable[[], str] | None = None
    if secrets is not None:
        secret = secrets.passphrase.get_secret_value()

        def passphrase_callback() -> str:
            """Resolve the passphrase already read from the bounded machine channel."""
            return secret

    elif not _headless_secret_channel_active() and terminal_can_prompt_for_secrets():

        def passphrase_callback() -> str:
            """Read the profile passphrase on the hardened no-echo channel."""
            return prompt_secret_no_echo(tr("cli.config.login.passphrase_prompt"))

    try:
        return login_profile(name=name, passphrase_callback=passphrase_callback)
    except (ProfileAuthenticationRefusedError, ProfileCustodyPasswordError) as exc:
        # Distinguish "no password was offered" from "the password was wrong".
        # Custody refuses both through one error, and its absent-channel
        # wording is necessarily terse: it cannot name --secrets-stdin,
        # --secrets-fd or the environment variable, because those belong to
        # this entrypoint. Only here is it knowable that NO channel existed --
        # no callback was built and no passphrase is configured -- and only
        # then is the instructive refusal the right answer. A wrong password
        # offered through a real channel falls through unchanged: telling that
        # operator to supply a channel they already supplied would be worse
        # than the terse refusal. The check cannot move earlier either, because
        # login legitimately proceeds with no callback at all -- a configured
        # passphrase and a resumed session are both unlocked inside it.
        if (
            isinstance(exc, ProfileCustodyPasswordError)
            and passphrase_callback is None
            and load_settings().cadrumo_secret_passphrase is None
        ):
            raise CliRefusedBoundaryError(
                translated_message="cli.config.login.passphrase_channel_absent",
            ) from None
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
    from ._login_frontend import login_screen_is_available
    from ._secure_input import resolve_secrets_channel

    resolve_secrets_channel(secrets_stdin=secrets_stdin, secrets_fd=secrets_fd)
    if login_screen_is_available(ctx, secrets_stdin=secrets_stdin, secrets_fd=secrets_fd):
        outcome = _login_through_the_screen(name=name)
    else:
        outcome = _login_through_the_prompt(
            ctx,
            name=name,
            secrets_stdin=secrets_stdin,
            secrets_fd=secrets_fd,
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
    output_language: OutputLanguage | None = None,
) -> None:
    """Strong-close the profile session: seal, delete both halves, clear the pointer."""
    _activate_subcommand_output_language(ctx, output_language)
    from ....application.user_profile import logout_active_profile

    signed_out_label = active_profile_label()
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
    _emit_envelope(
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
