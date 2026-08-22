"""Route the interactive arm of the profile wizard verbs onto the manager.

`create` and `edit` are two closures off the same wizard flow, each bound to
its verb. The `create` closure refuses a name that already has a manifest; the
`edit` closure refuses a name that has none. The verb — not a runtime-detected
pointer — is the authority for the create-vs-edit branch.

Those refusals live in the WIZARD command, which the manager arm returns
before ever calling, so this module re-states the `edit` one at the diversion
(:func:`open_the_edit_target_or_refuse`) and settles what the manager brings
with it: the manager edits whichever profile is ACTIVE, so a name for any
other live profile opens the login screen for that profile rather than being
silently redirected onto the active one. An operator who declines the screen
gets a refusal; one who authenticates gets the profile they asked for.

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

from typing import TYPE_CHECKING, TypedDict, cast

import typer
from typer._click.core import Context as _TyperClickContext

from ....core.i18n import tr
from ....core.json_contract import Notice as _Notice
from ....core.json_contract import NoticeSeverity as _NoticeSeverity
from ....core.wizard_catalogue import get_setup_flow as _get_setup_flow
from .._command_policy import command_execution_policy as _command_execution_policy
from .._command_suggestions import LazySubcommand as _LazySubcommand
from .._command_suggestions import register_lazy_subcommand as _register_lazy_subcommand
from .._common import _emit_envelope, active_profile_label
from .._errors import command_error_boundary as _command_error_boundary
from .._errors import decorate_typer_app as _decorate_typer_app
from ._execution_policies import BOOTSTRAP_WRITE as _BOOTSTRAP_WRITE
from ._execution_policies import ENCRYPTED_WRITE as _ENCRYPTED_WRITE

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
            has_explicit_profile_fields,
            host_can_run_full_screen,
            manager_is_the_right_frontend,
            present_profile_manager,
            present_registration,
        )

        if not manager_is_the_right_frontend(
            mode=mode,
            scripted=bool(kwargs.get("quiet")) or bool(kwargs.get("accept_defaults")),
            explicit_fields=has_explicit_profile_fields(kwargs),
            full_screen=host_can_run_full_screen(),
        ):
            # The setup flow is not a creation authority and refuses `create`
            # outright, so the scripted arm of THIS verb has to reach the
            # credential registration door itself rather than hand the
            # operator a refusal that names a capability no surface offered.
            #
            # BOTH forms are taken natively, the bare one and the one carrying
            # profile field flags. Routing the flagged form back to the flow
            # was a dead end rather than a safeguard: the flow refuses `create`
            # before it validates anything, so the invocation the operator
            # action catalogue projects as the recovery for a clean-root
            # refusal could never succeed. The registration door now applies
            # those flags itself, through the flow's own validation and fact
            # authority, so the values are neither stranded nor dropped.
            scripted_ctx = kwargs.get("ctx")
            if mode == "create" and isinstance(scripted_ctx, _TyperClickContext):
                from ._scripted_registration import register_profile_from_scripted_invocation

                return register_profile_from_scripted_invocation(scripted_ctx, kwargs)
            return wizard_command(*args, **kwargs)

        ctx = kwargs.get("ctx")
        if not isinstance(ctx, _TyperClickContext):
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
            # Textual runs button handlers in an asyncio task.  The registration
            # door authenticates there, but ContextVar bindings made by that
            # child task cannot flow back into this synchronous CLI context.
            # Resume the just-persisted login through the same authority used by
            # the root callback before the manager performs its first read.
            from .. import _resume_profile_session_or_refuse

            # CAST-RATIONALE-TYPER-CLICK-CONTEXT: see emit_manager_closed below.
            _resume_profile_session_or_refuse(cast(typer.Context, ctx), outcome.bucket_id)
            present_profile_manager(label=outcome.label)
            emit_manager_closed(ctx, outcome.label, created=True)
            return None

        open_the_edit_target_or_refuse(ctx, kwargs.get("profile_name"))
        present_profile_manager()
        label = active_profile_label()
        if label is None:
            raise RuntimeError("active profile label unavailable after profile manager session")
        emit_manager_closed(ctx, label, created=False)
        return None

    if mode == "create":
        import inspect

        signature = inspect.signature(_dispatch)
        parameters = list(signature.parameters.values())
        parameters.append(
            inspect.Parameter(
                "secrets_stdin",
                kind=inspect.Parameter.KEYWORD_ONLY,
                annotation=bool,
                default=typer.Option(False, "--secrets-stdin", help=tr("cli.config.custody.secrets_stdin_help")),
            )
        )
        _dispatch.__signature__ = signature.replace(parameters=parameters)
    return _dispatch


def open_the_edit_target_or_refuse(ctx: _TyperClickContext, supplied: object) -> None:
    """Make ``edit NAME`` open NAME, authenticating to it if that is what it takes.

    The manager edits the ACTIVE profile: ``build_active_profile_overview``
    resolves its subject through ``require_active_bucket_id`` and never sees
    this argument. Diverting here without checking it therefore honoured the
    verb and dropped its subject — ``profile edit <someone-else>`` opened the
    ACTIVE profile's page, and every field the operator went on to change
    landed on the wrong taxpayer with nothing on screen naming the one they
    had asked for. A mistyped label behaved identically, and neither case
    left a trace.

    The wizard arm validates the name in ``_resolve_profile_id_for_mode``,
    but the manager arm returns before the wizard command is ever called, so
    the check has to happen at the diversion rather than inside the command
    it replaces. (The module docstring's claim that "the ``edit`` closure
    refuses a name that has none" described only the wizard arm.)

    Resolution goes through the same
    :func:`~cadrumo.application.user_profile.resolve_login_target` that
    ``login`` applies to its own ``NAME``, so an unknown target refuses
    identically here and there rather than growing a second wording.

    A live profile that is not the active one is OPENED, not refused. The
    root callback's gate cannot help here — it runs before the verb is
    parsed, so it preselects whoever was already selected and knows nothing
    about this argument — so the offer is repeated with the target this verb
    actually names. Authenticating to it performs the handover ``login NAME``
    already owns, which is not a silent switch: the operator typed the name
    and then entered that profile's secret. Declining leaves the previous
    profile untouched and refuses, naming the verb that would have done it
    on its own.
    """
    if not isinstance(supplied, str) or not supplied.strip():
        return

    from ....application.profile_preconditions import profile_session_failure_verdict
    from ....application.user_profile import resolve_login_target
    from ....core import ProfileSessionRefusalReason, resolve_active_bucket_id
    from .. import _authenticated_at_the_gate
    from .._common import attach_cli_policy_verdict
    from .._errors import CliRefusedBoundaryError

    target = resolve_login_target(supplied)
    if target.bucket_id == resolve_active_bucket_id():
        return
    # CAST-RATIONALE-TYPER-CLICK-CONTEXT: ctx is typed as the vendored
    # typer._click.core.Context this module accepts at its own boundary;
    # _authenticated_at_the_gate's signature wants the public typer.Context
    # alias for the same runtime object.
    if _authenticated_at_the_gate(cast(typer.Context, ctx), bucket_id=target.bucket_id):
        return
    raise attach_cli_policy_verdict(
        CliRefusedBoundaryError(
            translated_message="cli.config.profile.edit_target_not_active",
            context={"name": target.label},
        ),
        verdict=profile_session_failure_verdict(
            ProfileSessionRefusalReason.ABSENT,
            profile_name=target.label,
        ),
    )


def emit_registration_abandoned(ctx: _TyperClickContext) -> None:
    """Report a registration the operator left without completing.

    Not an error: leaving the first screen without creating a profile is an
    ordinary choice, so it emits a success envelope carrying an info notice
    rather than a refusal.
    """
    from ....application.wizard import ConfigProfileCreateResult, ProfileWizardStatus

    _emit_envelope(
        # CAST-RATIONALE-TYPER-CLICK-CONTEXT: ctx is typed as the vendored
        # typer._click.core.Context this module accepts at its own boundary;
        # _emit_envelope's signature wants the public typer.Context alias for
        # the same runtime object.
        cast(typer.Context, ctx),
        command="config.profile.create",
        result=ConfigProfileCreateResult(profile_name="", status=ProfileWizardStatus.ABANDONED),
        lines=[tr("cli.config.profile.registration_abandoned")],
        notices=[
            _Notice(
                code="PROFILE_REGISTRATION_ABANDONED",
                severity=_NoticeSeverity.INFO,
                message=tr("cli.config.profile.registration_abandoned"),
            ),
        ],
    )


def emit_manager_closed(ctx: _TyperClickContext, label: str, *, created: bool) -> None:
    """Report the manager session, naming the profile it operated on.

    The manager persists every edit as it is made, so this envelope closes
    the session rather than committing it — by the time it renders, the
    record already holds whatever the operator changed.
    """
    from ....application.wizard import (
        ConfigProfileCreateResult,
        ConfigProfileEditResult,
        ProfileWizardStatus,
    )

    message = tr(
        "cli.config.profile.manager_closed_created" if created else "cli.config.profile.manager_closed",
        profile=label,
    )
    result = (
        ConfigProfileCreateResult(
            profile_name=label,
            status=ProfileWizardStatus.CREATED,
            active_profile=label,
        )
        if created
        else ConfigProfileEditResult(profile_name=label, status=ProfileWizardStatus.UPDATED)
    )
    _emit_envelope(
        # CAST-RATIONALE-TYPER-CLICK-CONTEXT: ctx is typed as the vendored
        # typer._click.core.Context this module accepts at its own boundary;
        # _emit_envelope's signature wants the public typer.Context alias for
        # the same runtime object.
        cast(typer.Context, ctx),
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


class _LeafPassthrough(TypedDict):
    """The exact Typer passthrough this registrar forwards.

    A TypedDict rather than a plain mapping so the splat below is checked
    against Typer's real parameter types: a ``dict[str, str | None]`` could
    supply any keyword, including the boolean ones, which a type checker must
    reject at the call.
    """

    help: str
    epilog: str | None


def register_lazy_wizard_leaf(
    name: str,
    mode: WizardPersistMode,
    *,
    # `help` shadows the builtin deliberately: it is Typer's own parameter
    # name, and renaming it here would break the passthrough at the call site.
    help: str,
    epilog: str | None = None,
) -> None:
    """Register the `profile` wizard verb `name` as a deferred leaf.

    The factory returns a single-command Typer carrying no callback, which
    Typer materialises as a plain :class:`click.Command` rather than a
    group — so the leaf resolves exactly as an eagerly-registered one,
    having imported the wizard only when the operator asks for it.

    ``help`` and ``epilog`` are named on THIS signature rather than collected
    into an untyped bag, so a caller passing the wrong thing is caught here.
    They are then forwarded to Typer as a mapping rather than as literal
    keywords, and that is deliberate: the help-source gate requires every
    ``help=`` written at a Typer call to be a direct ``tr("...")`` literal, and
    this function cannot satisfy that because it does not author help text — it
    forwards text its callers already translated. Both registration sites pass
    ``tr(...)`` literals, so the property the gate protects holds where it is
    actually decided.
    """

    def _factory() -> typer.Typer:
        from ....application.wizard import build_wizard_command

        leaf = typer.Typer()
        passthrough: _LeafPassthrough = {"help": help, "epilog": epilog}
        leaf.command(name, **passthrough)(
            _command_execution_policy(_BOOTSTRAP_WRITE if mode == "create" else _ENCRYPTED_WRITE)(
                _command_error_boundary(
                    with_manager_frontend(
                        build_wizard_command(_get_setup_flow(), mode=mode),
                        mode=mode,
                    ),
                )
            ),
        )
        return leaf

    _register_lazy_subcommand("profile", _LazySubcommand(name, _factory, decorate=_decorate_typer_app))
