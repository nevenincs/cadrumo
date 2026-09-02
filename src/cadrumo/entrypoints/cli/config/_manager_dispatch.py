"""Project profile creation and editing through the CLI.

`create` and `edit` are two closures off the same wizard flow, each bound to
its verb. The `create` closure refuses a name that already has a manifest; the
`edit` closure refuses a name that has none. The verb — not a runtime-detected
pointer — is the authority for the create-vs-edit branch.

Both are registered as per-LEAF lazy subcommands rather than built at
package-import time. :func:`~cadrumo.application.wizard.commands.build_wizard_command`
reaches ``application.wizard`` -> ``application.workflow`` ->
``application.filing`` -> the justificante PDF adapter, so constructing these
two closures eagerly made every other `config` verb — `login` included — pay
for the wizard's whole dependency tail before parsing its own arguments.
Deferring only the *import* would not have helped: the closures were
CONSTRUCTED at module level, so the call kept the tail eager. The construction
itself has to move behind the resolution boundary, which is what
``LazySubcommand`` already provides for groups; `profile` is a
``CadrumoTyperGroup``, so the same machinery serves a leaf.

That deferral is why the CLI projection imports inside this module stay
function-local rather than moving to the top: hoisting them would re-eager
exactly the tail the lazy leaf exists to defer.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import cache
from typing import TYPE_CHECKING, cast

import typer
from typer._click.core import Context as _TyperClickContext

from ....core.i18n import tr
from ....core.wizard_catalogue import get_setup_flow as _get_setup_flow
from .._common import activate_subcommand_output_language
from ..errors import command_error_boundary as _command_error_boundary

if TYPE_CHECKING:
    from ....application.wizard.persistence import WizardPersistMode
    from ....core.external_constants import OutputLanguage


def with_profile_cli_projection(wizard_command: Callable[..., None], *, mode: WizardPersistMode) -> Callable[..., None]:
    """Route profile verbs through their canonical CLI projections.

    Creation has a dedicated CLI credential door because the setup wizard does
    not create profiles. Editing stays with the wizard, which owns its parsed
    field values and persistence behavior. Full-screen construction is not a
    CLI concern.
    """
    import functools

    @functools.wraps(wizard_command)
    def _dispatch(*args: object, **kwargs: object) -> None:
        from ._manager_frontend import has_explicit_profile_fields

        context = kwargs.get("ctx")
        if not isinstance(context, _TyperClickContext):
            raise TypeError("profile frontend dispatch requires a Typer context")
        from .._tui_policy import tui_was_requested

        tui_requested = tui_was_requested(cast("typer.Context", context))
        explicit_fields = has_explicit_profile_fields(kwargs)
        scripted = any(
            (
                bool(kwargs.get("quiet")),
                bool(kwargs.get("accept_defaults")),
                bool(kwargs.get("secrets_stdin")),
                kwargs.get("secrets_fd") is not None,
                kwargs.get("recovery_handoff_fd") is not None,
                kwargs.get("recovery_verification_fd") is not None,
            )
        )
        if tui_requested and (scripted or explicit_fields):
            raise typer.BadParameter(tr("cli.config.setup.tui_scripted_conflict"))

        if mode == "create":
            from ._scripted_registration import register_profile_from_scripted_invocation

            activate_subcommand_output_language(
                cast(typer.Context, context),
                cast("OutputLanguage | None", kwargs.get("output_language")),
            )
            return register_profile_from_scripted_invocation(context, kwargs)
        return wizard_command(*args, **kwargs)

    return _dispatch


@cache
def profile_wizard_behavior(mode: WizardPersistMode) -> Callable[..., None]:
    """Build the behavior-only wizard callable for one profile verb."""
    from ....application.wizard.commands import build_wizard_command

    return _command_error_boundary(
        with_profile_cli_projection(
            build_wizard_command(_get_setup_flow(), mode=mode),
            mode=mode,
        ),
    )


def profile_create(ctx: typer.Context, **parameters: object) -> None:
    """Run scripted profile registration through the canonical application door."""
    profile_wizard_behavior("create")(ctx=ctx, **parameters)


def profile_edit(ctx: typer.Context, **parameters: object) -> None:
    """Run the edit-mode profile wizard behavior."""
    profile_wizard_behavior("edit")(ctx=ctx, **parameters)


__all__ = [
    "profile_create",
    "profile_edit",
    "profile_wizard_behavior",
    "with_profile_cli_projection",
]
