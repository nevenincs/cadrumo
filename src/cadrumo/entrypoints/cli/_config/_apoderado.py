"""Apoderado CLI command surface."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

import typer

if TYPE_CHECKING:
    from ....application.auth import ApoderadoService

from ....application.workflow import ProfileBucketPointer
from ....core.external_constants import OutputLanguage
from ....core.i18n import tr
from .._common import _emit_envelope
from .._common import activate_subcommand_output_language as _activate_subcommand_output_language
from .._errors import CliRefusedBoundaryError as _CliRefusedBoundaryError

_resolve_active_profile_pointer: Callable[[], ProfileBucketPointer | None] | None = None
_mounted_auth_app_ids: set[int] = set()
_scopes_registered = False

apoderado_app = typer.Typer(
    name="apoderado",
    help=tr("cli.config.auth.apoderado.help", default="Manage apoderado configuration"),
    no_args_is_help=True,
)
scopes_app = typer.Typer(
    name="scopes",
    help=tr("cli.config.auth.apoderado.scopes.help", default="Manage apoderado scope vocabulary"),
    no_args_is_help=True,
)


def register_apoderado_commands(
    auth_app: typer.Typer,
    *,
    resolve_active_profile_pointer: Callable[[], ProfileBucketPointer | None],
) -> None:
    """Mount apoderado commands on the config auth app."""
    global _scopes_registered
    global _resolve_active_profile_pointer

    _resolve_active_profile_pointer = resolve_active_profile_pointer
    if not _scopes_registered:
        apoderado_app.add_typer(scopes_app, name="scopes")
        _scopes_registered = True
    auth_app_id = id(auth_app)
    if auth_app_id in _mounted_auth_app_ids:
        return
    auth_app.add_typer(apoderado_app, name="apoderado")
    _mounted_auth_app_ids.add(auth_app_id)


def _active_profile_pointer() -> ProfileBucketPointer:
    if _resolve_active_profile_pointer is None:
        raise RuntimeError("apoderado commands were not registered")
    pointer = _resolve_active_profile_pointer()
    if pointer is None:
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.profile.no_active_profile",
        )
    return pointer


@scopes_app.command(
    "list",
    help=tr("cli.config.auth.apoderado.scopes.list_help", default="List accepted apoderado scopes"),
)
def apoderado_scopes_list(
    ctx: typer.Context,
    output_language: OutputLanguage | None = typer.Option(
        None,
        "--output-language",
        "--language",
        help=tr("cli.config.auth.output_language_help"),
    ),
) -> None:
    """List all available representative scopes in the vocabulary."""
    _activate_subcommand_output_language(ctx, output_language)
    from ....application.auth import ApoderadoService
    from .._config_payloads import ApoderadoScopesListResult

    svc = ApoderadoService()
    payload = svc.catalogue.model_dump(mode="json")
    lines = [f"{s.code}\t{tr(f'cli.config.auth.apoderado.scope.{s.code.lower()}')}" for s in svc.catalogue.scopes]
    scopes_result = ApoderadoScopesListResult.model_validate(payload)
    _emit_envelope(ctx, command="config.auth.apoderado.scopes.list", result=scopes_result, lines=lines)


@apoderado_app.command(
    "status",
    help=tr("cli.config.auth.apoderado.status_help", default="Show active apoderado configuration"),
)
def apoderado_status(
    ctx: typer.Context,
    output_language: OutputLanguage | None = typer.Option(
        None,
        "--output-language",
        "--language",
        help=tr("cli.config.auth.output_language_help"),
    ),
) -> None:
    _activate_subcommand_output_language(ctx, output_language)
    from ....application.auth import ApoderadoService
    from .._config_payloads import ApoderadoStatusResult

    pointer = _active_profile_pointer()
    svc = ApoderadoService()
    result = svc.status(bucket_id=pointer.bucket_id)

    payload = result.model_dump(mode="json")
    lines = [
        f"bucket_id\t{result.bucket_id}",
        f"configured\t{result.configured}",
    ]
    if result.configured:
        lines.append(f"represented_nif\t{result.represented_nif}")
        lines.append(f"granted_scopes\t{','.join(result.granted_scopes)}")

    status_result = ApoderadoStatusResult.model_validate(payload)
    _emit_envelope(ctx, command="config.auth.apoderado.status", result=status_result, lines=lines)


@apoderado_app.command(
    "configure",
    help=tr("cli.config.auth.apoderado.configure_help", default="Set active apoderado configuration"),
)
def apoderado_configure(
    ctx: typer.Context,
    represented_nif: str | None = typer.Option(
        None,
        "--represented-nif",
        help=tr("cli.config.auth.apoderado.configure.represented_nif_help", default="NIF of the represented party"),
    ),
    scope: list[str] = typer.Option(
        None,
        "--scope",
        help=tr("cli.config.auth.apoderado.configure.scope_help", default="Scope tokens (can be repeated)"),
    ),
    output_language: OutputLanguage | None = typer.Option(
        None,
        "--output-language",
        "--language",
        help=tr("cli.config.auth.output_language_help"),
    ),
) -> None:
    """Configure the active profile's apoderado representation.

    When ``--represented-nif`` is supplied the verb configures
    non-interactively from the flags (the automation and piped-host path).
    When it is omitted the verb becomes a door hosting the paged apoderado
    flow: the operator answers the represented-party and scope pages on the
    best frontend the host supports, and the reviewed answers commit through
    the same :class:`~cadrumo.application.auth.ApoderadoService`. Either way
    the write lands only in the apoderado encrypted namespace -- never as a
    profile fact.
    """
    _activate_subcommand_output_language(ctx, output_language)
    from ....application.auth import ApoderadoService
    from ....application.workflow import workflow_state_repository

    workflow_state_repository().load()
    pointer = _active_profile_pointer()
    svc = ApoderadoService()

    scope_tokens = tuple(scope or ())
    if represented_nif is None:
        resolved_nif, scope_tokens = _collect_apoderado_answers_interactively(svc)
    else:
        resolved_nif = represented_nif
        if not scope_tokens:
            raise _CliRefusedBoundaryError(
                translated_message="cli.config.auth.apoderado.configure.scope_help",
            )

    result = svc.configure(
        bucket_id=pointer.bucket_id,
        represented_nif=resolved_nif,
        scope_tokens=scope_tokens,
    )

    from .._config_payloads import ApoderadoConfigureResult

    payload = result.model_dump(mode="json")
    lines = [
        f"bucket_id\t{result.bucket_id}",
        f"represented_nif\t{result.represented_nif}",
        f"granted_scopes\t{','.join(result.granted_scopes)}",
    ]
    configure_result = ApoderadoConfigureResult.model_validate(payload)
    _emit_envelope(ctx, command="config.auth.apoderado.configure", result=configure_result, lines=lines)


def _collect_apoderado_answers_interactively(
    svc: ApoderadoService,
) -> tuple[str, tuple[str, ...]]:
    """Host the paged apoderado flow and return ``(represented_nif, scope_tokens)``.

    Builds the two-page apoderado :class:`FlowDefinition` from the service's
    live scope catalogue and runs it on the capability-selecting frontend in
    ``MODIFY`` mode with no checkpoint store: the answers stage in an
    in-memory :class:`FlowState` and are handed back for a single commit
    through the service. A host that cannot present an interactive flow
    (piped / non-interactive) refuses with the substrate's no-console copy,
    which points the operator at the ``--represented-nif`` / ``--scope`` flags.
    """
    from ....application.auth import apoderado_answers_from_state, build_apoderado_flow_definition
    from ....application.flows import FlowUnsupportedConsoleError
    from ....core.errors import resolve_error_message
    from ....core.flows import FlowMode
    from ._setup_flow_frontend import run_setup_flow_frontend

    definition = build_apoderado_flow_definition(svc.catalogue)
    try:
        state = run_setup_flow_frontend(
            definition,
            mode=FlowMode.MODIFY,
            registered_values=None,
            checkpoint_store=None,
        )
    except FlowUnsupportedConsoleError as exc:
        raise _CliRefusedBoundaryError(resolve_error_message(exc)) from exc
    return apoderado_answers_from_state(state)


@apoderado_app.command(
    "clear",
    help=tr("cli.config.auth.apoderado.clear_help", default="Retire the apoderado configuration"),
)
def apoderado_clear(
    ctx: typer.Context,
    output_language: OutputLanguage | None = typer.Option(
        None,
        "--output-language",
        "--language",
        help=tr("cli.config.auth.output_language_help"),
    ),
) -> None:
    _activate_subcommand_output_language(ctx, output_language)
    from ....application.auth import ApoderadoService
    from ....application.workflow import workflow_state_repository
    from .._config_payloads import ApoderadoClearResult

    workflow_state_repository().load()
    pointer = _active_profile_pointer()
    svc = ApoderadoService()
    cleared = svc.clear(bucket_id=pointer.bucket_id)

    clear_result = ApoderadoClearResult(bucket_id=pointer.bucket_id, cleared=cleared)
    lines = [
        f"bucket_id\t{pointer.bucket_id}",
        f"cleared\t{cleared}",
    ]
    _emit_envelope(ctx, command="config.auth.apoderado.clear", result=clear_result, lines=lines)


@apoderado_app.command(
    "check",
    help=tr(
        "cli.config.auth.apoderado.check_help",
        default="Verify against AEAT (unavailable; live reads are sealed). Use 'status' for the offline read.",
    ),
)
def apoderado_check(
    ctx: typer.Context,
    output_language: OutputLanguage | None = typer.Option(
        None,
        "--output-language",
        "--language",
        help=tr("cli.config.auth.output_language_help"),
    ),
) -> None:
    _activate_subcommand_output_language(ctx, output_language)
    from ....application.auth import ApoderadoLiveCheckUnavailableError, ApoderadoService
    from ....application.workflow import workflow_state_repository
    from ....core.errors import resolve_error_message

    workflow_state_repository().load()
    pointer = _active_profile_pointer()
    svc = ApoderadoService()

    # ``check`` is the live-verification verb. The live AEAT-read path is not
    # wired (live reads are refused at this boundary per the safety gate), so
    # the service refuses rather than silently re-reading stored configuration
    # and presenting it as a live result. Surface the registered refusal copy;
    # ``status`` is the offline configuration read.
    try:
        svc.check(bucket_id=pointer.bucket_id)
    except ApoderadoLiveCheckUnavailableError as exc:
        raise _CliRefusedBoundaryError(resolve_error_message(exc)) from exc


__all__ = ["apoderado_app", "register_apoderado_commands"]
