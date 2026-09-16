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
from typing import TYPE_CHECKING, cast

import typer
from typer._click.core import Context as _TyperClickContext

from ..common import activate_subcommand_output_language
from ..errors import command_error_boundary as _command_error_boundary

if TYPE_CHECKING:
    from ....application.wizard.models import WizardFlow
    from ....application.wizard.persistence import WizardPersistMode
    from ....core.external_constants import OutputLanguage
    from ....domain.calculations.registry.authority import PinnedAuthorityOperation


def with_profile_cli_projection(
    wizard_command: Callable[..., None],
    *,
    mode: WizardPersistMode,
    operation: PinnedAuthorityOperation,
    flow: WizardFlow,
) -> Callable[..., None]:
    """Route profile verbs through their canonical CLI projections.

    Creation has a dedicated CLI credential door because the setup wizard does
    not create profiles. Editing stays with the wizard, which owns its parsed
    field values and persistence behavior. Full-screen construction is not a
    CLI concern.
    """
    import functools

    @functools.wraps(wizard_command)
    def _dispatch(*args: object, **kwargs: object) -> None:
        context = kwargs.get("ctx")
        if not isinstance(context, _TyperClickContext):
            raise TypeError("profile frontend dispatch requires a Typer context")

        if mode == "create":
            from .scripted_registration import register_profile_from_scripted_invocation

            activate_subcommand_output_language(
                cast(typer.Context, context),
                cast("OutputLanguage | None", kwargs.get("output_language")),
            )
            return register_profile_from_scripted_invocation(
                context,
                kwargs,
                flow=flow,
                operation=operation,
            )
        return wizard_command(*args, **kwargs)

    return _dispatch


def profile_wizard_behavior(mode: WizardPersistMode) -> Callable[..., None]:
    """Run one wizard behavior while its indexed authority operation is leased."""
    from ....application.wizard.catalogue import build_setup_flow
    from ....application.wizard.commands import build_wizard_command
    from ....domain.calculations.registry.authority import bundled_indexed_authority
    from .._profile_authentication_notice import drain_profile_authentication_notices

    def _run(*args: object, **kwargs: object) -> None:
        # Keep the flow, command, and every profile context-dependent action
        # inside one operation lease.  A descriptor projected from a pinned
        # generation must not escape the lease that made its choices valid.
        with bundled_indexed_authority().operation() as operation:
            flow = build_setup_flow(operation)
            # The wizard emits its own envelope, below this package's funnel,
            # so it is handed the drain for the notices root authentication
            # staged for this invocation.
            wizard_command = build_wizard_command(
                flow,
                mode=mode,
                operation=operation,
                invocation_notices=drain_profile_authentication_notices,
            )
            projected = with_profile_cli_projection(
                wizard_command,
                mode=mode,
                operation=operation,
                flow=flow,
            )
            return _command_error_boundary(projected)(*args, **kwargs)

    return _run


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
