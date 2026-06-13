"""Apoderado CLI command surface."""

from __future__ import annotations

from collections.abc import Callable

import typer

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
    "list", help=tr("cli.config.auth.apoderado.scopes.list_help", default="List accepted apoderado scopes"),
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
    "status", help=tr("cli.config.auth.apoderado.status_help", default="Show active apoderado configuration"),
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
    "configure", help=tr("cli.config.auth.apoderado.configure_help", default="Set active apoderado configuration"),
)
def apoderado_configure(
    ctx: typer.Context,
    represented_nif: str = typer.Option(
        ...,
        "--represented-nif",
        help=tr("cli.config.auth.apoderado.configure.represented_nif_help", default="NIF of the represented party"),
    ),
    scope: list[str] = typer.Option(
        ...,
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
    _activate_subcommand_output_language(ctx, output_language)
    from ....application.auth import ApoderadoService
    from ....application.workflow import workflow_state_repository
    from .._config_payloads import ApoderadoConfigureResult

    workflow_state_repository().load()
    pointer = _active_profile_pointer()
    svc = ApoderadoService()
    result = svc.configure(
        bucket_id=pointer.bucket_id,
        represented_nif=represented_nif,
        scope_tokens=tuple(scope),
    )

    payload = result.model_dump(mode="json")
    lines = [
        f"bucket_id\t{result.bucket_id}",
        f"represented_nif\t{result.represented_nif}",
        f"granted_scopes\t{','.join(result.granted_scopes)}",
    ]
    configure_result = ApoderadoConfigureResult.model_validate(payload)
    _emit_envelope(ctx, command="config.auth.apoderado.configure", result=configure_result, lines=lines)


@apoderado_app.command(
    "clear", help=tr("cli.config.auth.apoderado.clear_help", default="Retire the apoderado configuration"),
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
