"""Config custody command registration."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

import typer

from ....core.external_constants import OutputLanguage
from ....core.i18n import tr
from .._common import _emit_envelope
from .._common import activate_subcommand_output_language as _activate_subcommand_output_language
from .._errors import CliRefusedBoundaryError as _CliRefusedBoundaryError
from ._custody_secret import register_secret_custody_commands

if TYPE_CHECKING:
    from ....application.workflow import ProfileBucketPointer


def select_profile_pointer(pointer: ProfileBucketPointer) -> None:
    """Select and unlock ``pointer`` through the canonical profile lifecycle span."""
    from ....application.user_profile import select_profile_with_lifecycle_span

    select_profile_with_lifecycle_span(pointer.bucket_id)


def _resolve_switch_target(
    name: str,
    *,
    resolve_profile_by_label: Callable[[str], ProfileBucketPointer],
) -> ProfileBucketPointer:
    """Resolve a ``switch`` target from an unambiguous UUID or an exact label.

    ``switch`` is the single accepted profile selector (ADR
    ``cli-authority-verb-conformance``, Decision 3): it accepts the same
    identifiers profile and sandbox listing return — the immutable bucket
    UUID, or the exact operator label, including a sandbox's canonical
    ``sandbox:<name>`` label. A bare sandbox short name is NOT implicitly
    namespaced: it carries no ``sandbox:`` prefix, so it matches no sandbox
    bucket and the label resolver refuses it as an unknown profile — the
    sandbox namespace check the removed ``sandbox use`` door performed is
    preserved by requiring the canonical label. A live UUID resolves
    directly; a tombstoned UUID falls through to the label resolver, which
    refuses it. UUID/label ambiguity or duplicate labels refuse through the
    injected label resolver's typed selection error.
    """
    from ....application.workflow import read_profile_bucket_by_id
    from ....domain.user_profile import UserProfileStatus

    trimmed = name.strip()
    if trimmed:
        by_id = read_profile_bucket_by_id(trimmed)
        if by_id is not None and by_id.status is not UserProfileStatus.TOMBSTONED:
            return by_id
    return resolve_profile_by_label(name)


def _register_switch_command(
    app: typer.Typer,
    *,
    resolve_active_profile_pointer: Callable[[], ProfileBucketPointer | None],
    resolve_profile_by_label: Callable[[str], ProfileBucketPointer],
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
            pointer = _resolve_switch_target(name, resolve_profile_by_label=resolve_profile_by_label)
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
    resolve_active_profile_pointer: Callable[[], ProfileBucketPointer | None],
    resolve_profile_by_label: Callable[[str], ProfileBucketPointer],
) -> None:
    """Register root-level profile custody commands."""
    _register_switch_command(
        app,
        resolve_active_profile_pointer=resolve_active_profile_pointer,
        resolve_profile_by_label=resolve_profile_by_label,
    )
    register_secret_custody_commands(app)
