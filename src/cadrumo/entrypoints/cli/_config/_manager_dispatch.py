"""Route the interactive arm of the profile wizard verbs onto the manager.

`create` and `edit` are two closures off the same wizard flow, each bound to
its verb. The `create` closure refuses a name that already has a manifest; the
`edit` closure refuses a name that has none. The verb — not a runtime-detected
pointer — is the authority for the create-vs-edit branch.

Both are registered as per-LEAF lazy subcommands rather than built at
package-import time. :func:`~cadrumo.application.wizard.build_wizard_command`
reaches ``application.wizard`` -> ``application.workflow`` ->
``application.filing`` -> the justificante PDF adapter, so constructing these
two closures eagerly made every other `config` verb — `login` included — pay
for the wizard's whole dependency tail before parsing its own arguments.
Deferring only the *import* would not have helped: the closures were
CONSTRUCTED at module level, so the call kept the tail eager. The construction
itself has to move behind the resolution boundary, which is what
``LazySubcommand`` already provides for groups; `profile` is a
``CadrumoTyperGroup``, so the same machinery serves a leaf.

That deferral is why the frontend imports inside this module stay function-local
rather than moving to the top: hoisting them would re-eager exactly the tail the
lazy leaf exists to defer.

See Also:
    :mod:`~cadrumo.entrypoints.cli._config._manager_frontend`
        The full-screen manager and registration screens this module dispatches
        onto once it has decided the operator wants them.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import typer

from ....core.i18n import tr
from ....core.json_contract import Notice as _Notice
from ....core.json_contract import NoticeSeverity as _NoticeSeverity
from ....core.wizard_catalogue import get_setup_flow as _get_setup_flow
from .._command_suggestions import LazySubcommand as _LazySubcommand
from .._command_suggestions import register_lazy_subcommand as _register_lazy_subcommand
from .._common import _emit_envelope
from .._errors import command_error_boundary as _command_error_boundary
from .._errors import decorate_typer_app as _decorate_typer_app

if TYPE_CHECKING:
    from typing import Literal

    WizardPersistMode = Literal["create", "edit"]
    """Which arm of the shared wizard flow a registered leaf serves.

    Type-checking only: ``from __future__ import annotations`` keeps every
    annotation below a string at runtime, so the alias never needs to exist
    there. This module is the canonical home — the package facade imports it
    rather than restating the literal pair.
    """


def with_manager_frontend(wizard_command, *, mode: WizardPersistMode):
    """Divert the INTERACTIVE arm of a profile verb onto the manager.

    ``create`` and ``edit`` serve two audiences through one verb. A script
    or an agent passes field flags (or ``--quiet`` / ``--accept-defaults``)
    and wants a JSON envelope with no screen; an operator at a terminal
    wants their whole profile on one page, every field editable, nothing
    gated. Only the second arm is diverted here — the scripted path keeps
    the wizard, its flags, and its documented contract untouched.

    A profile name on the command line does NOT send ``create`` back to the
    flow: it prefills the registration screen's name field. Routing on it
    was a mistake -- ``config profile create NAME`` is the documented usage,
    so it meant the operator met the old paged flow every time and the new
    surface was effectively unreachable.
    """
    import functools

    @functools.wraps(wizard_command)
    def _dispatch(*args: object, **kwargs: object):
        from ._manager_frontend import (
            host_can_run_full_screen,
            manager_is_the_right_frontend,
            present_profile_manager,
            present_registration,
        )

        if not manager_is_the_right_frontend(
            mode=mode,
            scripted=bool(kwargs.get("quiet")) or bool(kwargs.get("accept_defaults")),
            explicit_fields=any(
                value is not None
                for key, value in kwargs.items()
                if key not in {"ctx", "profile_name", "quiet", "accept_defaults"}
            ),
            full_screen=host_can_run_full_screen(),
        ):
            return wizard_command(*args, **kwargs)

        ctx = kwargs.get("ctx")
        if not isinstance(ctx, typer.Context):
            # No Typer context to emit an envelope through; the wizard owns
            # its own output path, so hand the call straight back rather
            # than rendering a manager whose result could not be reported.
            return wizard_command(*args, **kwargs)
        if mode == "create":
            supplied = kwargs.get("profile_name")
            outcome = present_registration(
                suggested_name=supplied if isinstance(supplied, str) else None,
            )
            if outcome is None:
                emit_registration_abandoned(ctx)
                return None
            present_profile_manager(label=outcome.label)
            emit_manager_closed(ctx, outcome.label, created=True)
            return None

        present_profile_manager()
        emit_manager_closed(ctx, active_profile_label(), created=False)
        return None

    return _dispatch


def active_profile_label() -> str:
    """The active profile's operator-facing label, for the closing envelope."""
    from ....application.user_profile import ProfileRepository
    from ....core import require_active_bucket_id

    return ProfileRepository().load(require_active_bucket_id()).label


def emit_registration_abandoned(ctx: typer.Context) -> None:
    """Report a registration the operator left without completing.

    Not an error: leaving the first screen without creating a profile is an
    ordinary choice, so it emits a success envelope carrying an info notice
    rather than a refusal.
    """
    from ....application.wizard import ConfigProfileCreateResult

    _emit_envelope(
        ctx,
        command="config.profile.create",
        result=ConfigProfileCreateResult(profile_name="", status="abandoned"),
        lines=[tr("cli.config.profile.registration_abandoned")],
        notices=[
            _Notice(
                code="PROFILE_REGISTRATION_ABANDONED",
                severity=_NoticeSeverity.INFO,
                message=tr("cli.config.profile.registration_abandoned"),
            ),
        ],
    )


def emit_manager_closed(ctx: typer.Context, label: str, *, created: bool) -> None:
    """Report the manager session, naming the profile it operated on.

    The manager persists every edit as it is made, so this envelope closes
    the session rather than committing it — by the time it renders, the
    record already holds whatever the operator changed.
    """
    from ....application.wizard import ConfigProfileCreateResult, ConfigProfileEditResult

    message = tr(
        "cli.config.profile.manager_closed_created" if created else "cli.config.profile.manager_closed",
        profile=label,
    )
    result = (
        ConfigProfileCreateResult(profile_name=label, status="created", active_profile=label)
        if created
        else ConfigProfileEditResult(profile_name=label, status="updated")
    )
    _emit_envelope(
        ctx,
        command="config.profile.create" if created else "config.profile.edit",
        result=result,
        lines=[message],
        notices=[
            _Notice(
                code="PROFILE_MANAGER_CLOSED",
                severity=_NoticeSeverity.INFO,
                message=message,
            ),
        ],
    )


def register_lazy_wizard_leaf(name: str, mode: WizardPersistMode, **command_kwargs: object) -> None:
    """Register the `profile` wizard verb `name` as a deferred leaf.

    The factory returns a single-command Typer carrying no callback, which
    Typer materialises as a plain :class:`click.Command` rather than a
    group — so the leaf resolves exactly as an eagerly-registered one,
    having imported the wizard only when the operator asks for it.
    """

    def _factory() -> typer.Typer:
        from ....application.wizard import build_wizard_command

        leaf = typer.Typer()
        # KWARGS-ANY-RATIONALE-TYPER-COMMAND: `command_kwargs` carries the
        # help/epilog Typer passthrough captured at registration.
        leaf.command(name, **command_kwargs)(  # type: ignore[arg-type]
            _command_error_boundary(
                with_manager_frontend(
                    build_wizard_command(_get_setup_flow(), mode=mode),
                    mode=mode,
                ),
            ),
        )
        return leaf

    _register_lazy_subcommand("profile", _LazySubcommand(name, _factory, decorate=_decorate_typer_app))
