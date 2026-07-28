"""Config custody command registration."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

import typer
from pydantic import BaseModel, ConfigDict, SecretStr

from ....adapters.persistence.storage import SecretStoreError
from ....core.external_constants import OutputLanguage
from ....core.i18n import tr
from ....core.json_contract import Notice, NoticeSeverity
from .._common import _emit_envelope
from .._common import activate_subcommand_output_language as _activate_subcommand_output_language
from ._custody_secret import register_secret_custody_commands

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
    from ....core.config import load_settings
    from ....core.external_constants import SUPPORTED_OUTPUT_LANGUAGES

    try:
        settings = load_settings()
    except (AttributeError, KeyError, ValueError):
        return False
    if "cadrumo_output_language" not in settings.model_fields_set:
        return False
    raw = str(getattr(settings.cadrumo_output_language, "value", settings.cadrumo_output_language)).strip().lower()
    return raw in SUPPORTED_OUTPUT_LANGUAGES


def _hint_via_label(name: str) -> str | None:
    """Resolve an operator-typed profile label to its bucket's language hint.

    Returns ``None`` when the name matches no live profile, which is the
    correct outcome for a UUID that simply carries no hint and for a label
    that names nothing. The manifest scan reads plaintext files, so it does
    not depend on the target bucket's DEK being intact.
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
    own, so it is resolved to its UUID through the manifest scan first: that
    scan reads plaintext ``manifest.toml`` files and so stays readable under
    exactly the corrupt-DEK condition this helper exists to serve.
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


def _register_login_command(app: typer.Typer) -> None:
    """Register the profile-session login door."""

    @app.command("login", help=tr("cli.config.login.help"))
    def config_login(
        ctx: typer.Context,
        name: str | None = typer.Argument(None, help=tr("cli.config.login.name_help")),
        secrets_stdin: bool = typer.Option(
            False,
            "--secrets-stdin",
            help=tr("cli.config.custody.secrets_stdin_help"),
        ),
        output_language: OutputLanguage | None = typer.Option(
            None,
            "--output-language",
            "--language",
            help=tr("cli.config.auth.output_language_help"),
        ),
    ) -> None:
        """Authenticate one profile and mint its resumable session."""
        _activate_subcommand_output_language(ctx, output_language)
        from ....application.user_profile import login_profile
        from ._secure_input import read_secrets_stdin

        passphrase_callback: Callable[[], str] | None = None
        if secrets_stdin:
            secret = read_secrets_stdin(_LoginSecrets).passphrase.get_secret_value()

            def passphrase_callback() -> str:
                """Resolve the passphrase already read from the bounded stdin channel."""
                return secret

        try:
            outcome = login_profile(name=name, passphrase_callback=passphrase_callback)
        except SecretStoreError:
            # The target could not be unlocked (a wrong passphrase, a
            # corrupt bucket DEK); render the refusal in the target's own
            # output language rather than the previous selection's. Both a
            # UUID and a label resolve a bucket-local hint here: login owns
            # label resolution internally and does not surface the resolved
            # id on the failure path, so the helper re-resolves a label
            # through the plaintext manifest scan, which stays readable
            # while the target's DEK is corrupt.
            if name is not None:
                _pin_render_language_to_target_bucket(ctx, bucket_id=name)
            raise

        from .._config_payloads import ConfigLoginResult

        result = ConfigLoginResult(
            profile_id=outcome.bucket_id,
            active_profile=outcome.label,
            backend_kind=outcome.backend_kind.value,
            authenticated_at=outcome.authenticated_at.isoformat(),
            idle_deadline=outcome.idle_deadline.isoformat(),
            absolute_deadline=outcome.absolute_deadline.isoformat(),
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


def _register_logout_command(app: typer.Typer) -> None:
    """Register the profile-session strong-close door."""

    @app.command("logout", help=tr("cli.config.logout.help"))
    def config_logout(
        ctx: typer.Context,
        output_language: OutputLanguage | None = typer.Option(
            None,
            "--output-language",
            "--language",
            help=tr("cli.config.auth.output_language_help"),
        ),
    ) -> None:
        """Strong-close the profile session: seal, delete both halves, clear the pointer."""
        _activate_subcommand_output_language(ctx, output_language)
        from ....application.user_profile import logout_active_profile

        signed_out = logout_active_profile()

        from .._config_payloads import ConfigLogoutResult

        result = ConfigLogoutResult(
            logged_out_profile=signed_out,
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
                f"logged_out_profile\t{signed_out or '<none>'}",
                *(notice.message for notice in notices),
            ),
            notices=notices,
        )


def register_custody_commands(app: typer.Typer) -> None:
    """Register root-level profile custody commands.

    ``login`` owns profile selection end to end (UUID or exact label)
    through the application resolver, so no pointer or label resolver is
    injected here any more.
    """
    _register_login_command(app)
    _register_logout_command(app)
    register_secret_custody_commands(app)
