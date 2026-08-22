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
from .._command_policy import command_execution_policy
from .._common import _emit_envelope
from .._common import activate_subcommand_output_language as _activate_subcommand_output_language
from .._errors import CliRefusedBoundaryError as _CliRefusedBoundaryError
from ._execution_policies import ENCRYPTED_DESTRUCTIVE, ENCRYPTED_READ, ENCRYPTED_WRITE, declare_metadata_group

_resolve_active_profile_pointer: Callable[[], ProfileBucketPointer | None] | None = None
_mounted_auth_app_ids: set[int] = set()
_scopes_registered = False

_REPRESENTED_NIF_KEY = "represented-nif"
"""Form key for the represented party's tax identifier."""

_SCOPES_KEY = "scopes"
"""Form key for the granted scope set."""

apoderado_app = typer.Typer(
    name="apoderado",
    help=tr("cli.config.auth.apoderado.help"),
    no_args_is_help=True,
)
scopes_app = typer.Typer(
    name="scopes",
    help=tr("cli.config.auth.apoderado.scopes.help"),
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
    help=tr("cli.config.auth.apoderado.scopes.list_help"),
)
@command_execution_policy(ENCRYPTED_READ)
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
    help=tr("cli.config.auth.apoderado.status_help"),
)
@command_execution_policy(ENCRYPTED_READ)
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

    lines = [
        f"bucket_id\t{result.bucket_id}",
        f"configured\t{result.configured}",
    ]
    if result.configured:
        lines.append(f"represented_nif\t{result.represented_nif}")
        lines.append(f"granted_scopes\t{','.join(result.granted_scopes)}")

    # Project the canonical ApoderadoStatus field-by-field rather than through a
    # JSON round-trip: the envelope now carries the same typed contract, and a
    # JSON dump would hand it a stringified instant that the strict schema
    # correctly refuses.
    status_result = ApoderadoStatusResult(
        bucket_id=result.bucket_id,
        configured=result.configured,
        represented_nif=result.represented_nif,
        granted_scopes=list(result.granted_scopes),
        catalogue_version=result.catalogue_version,
        configured_at=result.configured_at,
    )
    _emit_envelope(ctx, command="config.auth.apoderado.status", result=status_result, lines=lines)


@apoderado_app.command(
    "configure",
    help=tr("cli.config.auth.apoderado.configure_help"),
)
@command_execution_policy(ENCRYPTED_WRITE)
def apoderado_configure(
    ctx: typer.Context,
    represented_nif: str | None = typer.Option(
        None,
        "--represented-nif",
        help=tr("cli.config.auth.apoderado.configure.represented_nif_help"),
    ),
    scope: list[str] = typer.Option(
        None,
        "--scope",
        help=tr("cli.config.auth.apoderado.configure.scope_help"),
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
    from ....application.auth import ApoderadoRepresentedNifInvalidError, ApoderadoService
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
            # A late, catalogue-driven refusal must enumerate the accepted
            # scope set, never bare "value required" -- the CLI gate is the
            # operator's first instructive surface.
            raise _CliRefusedBoundaryError(
                translated_message="cli.config.auth.apoderado.configure.scope_required",
                context={"codes": ", ".join(sorted(svc.catalogue.code_set()))},
            )

    try:
        result = svc.configure(
            bucket_id=pointer.bucket_id,
            represented_nif=resolved_nif,
            scope_tokens=scope_tokens,
        )
    except ApoderadoRepresentedNifInvalidError as exc:
        # Both transports commit through the service's single identity
        # authority; the raw identifier never enters the refusal context.
        raise _CliRefusedBoundaryError(
            translated_message="errors.refused.refused_apoderado_invalid_represented_nif",
        ) from exc

    from .._config_payloads import ApoderadoConfigureResult

    lines = [
        f"bucket_id\t{result.bucket_id}",
        f"represented_nif\t{result.represented_nif}",
        f"granted_scopes\t{','.join(result.granted_scopes)}",
    ]
    configure_result = ApoderadoConfigureResult(
        bucket_id=result.bucket_id,
        represented_nif=result.represented_nif,
        granted_scopes=list(result.granted_scopes),
        catalogue_version=result.catalogue_version,
        configured_at=result.configured_at,
        notes=result.notes,
    )
    _emit_envelope(ctx, command="config.auth.apoderado.configure", result=configure_result, lines=lines)


def _collect_apoderado_answers_interactively(
    svc: ApoderadoService,
) -> tuple[str, tuple[str, ...]]:
    """Show the apoderado page and return ``(represented_nif, scope_tokens)``.

    One page with both values on it rather than a question at a time:
    choosing who you represent and what you may do for them is a single
    decision, and the scope list only makes sense next to the party it
    applies to.

    The scope choices come from the service's live catalogue, so a
    catalogue revision that adds a scope offers it without a change here.
    The NIF is checked by the canonical identity authority as it is typed
    — never a second identifier implementation.

    A host that cannot present a screen refuses with an apoderado-specific
    hint naming ``--represented-nif`` / ``--scope``, which is the actual
    recovery for this verb, rather than generic no-console copy.
    """
    from ....adapters.inbound.tui import FormField, FormFieldKind, FormPage, form_choices, multi_choice_tokens
    from ....core.i18n import tr as _tr
    from ....core.identity import IdentityError, validate_identity
    from ._manager_frontend import host_can_run_full_screen, present_form

    if not host_can_run_full_screen():
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.auth.apoderado.configure.no_console_hint",
        )

    def _check_nif(candidate: str) -> str | None:
        try:
            validate_identity(candidate.strip())
        except IdentityError:
            return _tr("wizard.errors.invalid_tax_id")
        return None

    page = FormPage(
        title=_tr("cli.config.auth.apoderado.help"),
        section=_tr("cli.config.auth.apoderado.configure_help"),
        fields=(
            FormField(
                key=_REPRESENTED_NIF_KEY,
                label=_tr("cli.config.auth.apoderado.configure.represented_nif_help"),
                hint=_tr("wizard.setup.format.tax-id"),
                validate=_check_nif,
            ),
            FormField(
                key=_SCOPES_KEY,
                label=_tr("cli.config.auth.apoderado.configure.scope_help"),
                kind=FormFieldKind.MULTI_CHOICE,
                choices=form_choices(
                    [
                        (scope.code, _tr(f"cli.config.auth.apoderado.scope.{scope.code.lower()}"))
                        for scope in svc.catalogue.scopes
                    ],
                ),
                validate=lambda value: None if value else _tr("cli.config.auth.apoderado.configure.scope_help"),
            ),
        ),
    )
    collected = present_form(page)
    if collected is None:
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.auth.apoderado.configure.no_console_hint",
        )
    return collected[_REPRESENTED_NIF_KEY].strip(), multi_choice_tokens(collected[_SCOPES_KEY])


@apoderado_app.command(
    "clear",
    help=tr("cli.config.auth.apoderado.clear_help"),
)
@command_execution_policy(ENCRYPTED_DESTRUCTIVE)
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
    ),
)
@command_execution_policy(ENCRYPTED_READ)
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
    from ....application.auth import ApoderadoService
    from ....application.workflow import workflow_state_repository

    workflow_state_repository().load()
    pointer = _active_profile_pointer()
    svc = ApoderadoService()

    # ``check`` is the live-verification verb. The live AEAT-read path is not
    # wired (live reads are refused at this boundary per the safety gate), so
    # the service refuses rather than silently re-reading stored configuration
    # and presenting it as a live result. Surface the registered refusal copy;
    # ``status`` is the offline configuration read.
    svc.check(bucket_id=pointer.bucket_id)


declare_metadata_group(apoderado_app)
declare_metadata_group(scopes_app)

__all__ = ["apoderado_app", "register_apoderado_commands"]
