"""Config custody command registration."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import typer

from ....core.external_constants import OutputLanguage
from ....core.i18n import tr
from .._common import _emit_envelope
from .._common import activate_subcommand_output_language as _activate_subcommand_output_language
from .._errors import CliRefusedBoundaryError as _CliRefusedBoundaryError
from ._custody_secret import register_secret_custody_commands


def select_profile_pointer(pointer: Any) -> None:
    """Select and unlock ``pointer`` through the canonical profile lifecycle span."""
    from ....application.user_profile import select_profile_with_lifecycle_span
    from ....domain.user_profile import ProfileNotFoundError

    try:
        select_profile_with_lifecycle_span(pointer.bucket_id)
    except ProfileNotFoundError as exc:
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.profile.unknown_profile",
            context={"name": pointer.label},
        ) from exc


def _register_switch_command(
    app: typer.Typer,
    *,
    resolve_active_profile_pointer: Callable[[], Any],
    resolve_profile_by_label: Callable[[str], Any],
    assert_profile_record_present: Callable[..., None],
) -> None:
    """Register the operator profile-switch transport command."""

    @app.command("switch", help=tr("cli.config.switch.help"))
    def config_switch(
        ctx: typer.Context,
        name: str | None = typer.Argument(None, help=tr("cli.config.switch.name_help")),
        output_language: OutputLanguage | None = typer.Option(
            None,
            "--output-language",
            "--language",
            help=tr("cli.config.auth.output_language_help"),
        ),
    ) -> None:
        """Switch the active profile through the canonical lifecycle span."""
        _activate_subcommand_output_language(ctx, output_language)
        if name is None:
            pointer = resolve_active_profile_pointer()
            if pointer is None:
                raise _CliRefusedBoundaryError(
                    translated_message="cli.config.errors.no_active_profile",
                )
        else:
            pointer = resolve_profile_by_label(name)
        assert_profile_record_present(
            ctx,
            profile_id=pointer.bucket_id,
            bucket_id=pointer.bucket_id,
            label=pointer.label,
        )
        select_profile_pointer(pointer)
        from .._config_payloads import ConfigSwitchResult

        result = ConfigSwitchResult(active_profile=pointer.label)
        _emit_envelope(
            ctx,
            command="config.switch",
            result=result,
            lines=(f"active_profile\t{pointer.label}",),
        )


def register_custody_commands(
    app: typer.Typer,
    *,
    resolve_active_profile_pointer: Callable[[], Any],
    resolve_profile_by_label: Callable[[str], Any],
    assert_profile_record_present: Callable[..., None],
) -> None:
    """Register root-level profile custody commands."""
    _register_switch_command(
        app,
        resolve_active_profile_pointer=resolve_active_profile_pointer,
        resolve_profile_by_label=resolve_profile_by_label,
        assert_profile_record_present=assert_profile_record_present,
    )
    register_secret_custody_commands(app)
