"""Apoderado CLI command surface."""

from __future__ import annotations

from typing import TYPE_CHECKING

import typer

if TYPE_CHECKING:
    from cadrumo.application.workflow.profile_bucket_models import ProfileBucketPointer

from ....core.external_constants import OutputLanguage
from ....core.i18n import tr
from .._common import activate_subcommand_output_language as _activate_subcommand_output_language
from .._common import emit_envelope
from .._errors import CliRefusedBoundaryError as _CliRefusedBoundaryError


def _active_profile_pointer() -> ProfileBucketPointer:
    from ._profile_support import resolve_active_profile_pointer

    pointer = resolve_active_profile_pointer()
    if pointer is None:
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.profile.no_active_profile",
        )
    return pointer


def apoderado_scopes_list(
    ctx: typer.Context,
    output_language: OutputLanguage | None = None,
) -> None:
    """List all available representative scopes in the vocabulary."""
    _activate_subcommand_output_language(ctx, output_language)
    from ....application.auth.apoderado_service import ApoderadoService
    from .._config_payloads import ApoderadoScopesListResult

    svc = ApoderadoService()
    payload = svc.catalogue.model_dump(mode="json")
    lines = [f"{s.code}\t{tr(f'cli.config.auth.apoderado.scope.{s.code.lower()}')}" for s in svc.catalogue.scopes]
    scopes_result = ApoderadoScopesListResult.model_validate(payload)
    emit_envelope(ctx, command="config.auth.apoderado.scopes.list", result=scopes_result, lines=lines)


def apoderado_status(
    ctx: typer.Context,
    output_language: OutputLanguage | None = None,
) -> None:
    _activate_subcommand_output_language(ctx, output_language)
    from ....application.auth.apoderado_service import ApoderadoService
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
    emit_envelope(ctx, command="config.auth.apoderado.status", result=status_result, lines=lines)


def apoderado_configure(
    ctx: typer.Context,
    represented_nif: str | None = None,
    scope: list[str] | None = None,
    output_language: OutputLanguage | None = None,
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
    from cadrumo.application.workflow.persistence import workflow_state_repository

    from ....application.auth.apoderado_flow import run_apoderado_flow
    from ....application.auth.apoderado_service import ApoderadoRepresentedNifInvalidError, ApoderadoService

    workflow_state_repository().load()
    pointer = _active_profile_pointer()
    svc = ApoderadoService()

    scope_tokens = tuple(scope or ())
    if represented_nif is None:
        from ....application.flows.errors import FlowUnsupportedConsoleError

        try:
            result = run_apoderado_flow(svc, bucket_id=pointer.bucket_id)
        except FlowUnsupportedConsoleError as exc:
            raise _CliRefusedBoundaryError(
                translated_message="cli.config.auth.apoderado.configure.no_console_hint",
            ) from exc
        except ApoderadoRepresentedNifInvalidError as exc:
            raise _CliRefusedBoundaryError(
                translated_message="errors.refused.refused_apoderado_invalid_represented_nif",
            ) from exc
    else:
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
                represented_nif=represented_nif,
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
    emit_envelope(ctx, command="config.auth.apoderado.configure", result=configure_result, lines=lines)


def apoderado_clear(
    ctx: typer.Context,
    output_language: OutputLanguage | None = None,
) -> None:
    _activate_subcommand_output_language(ctx, output_language)
    from cadrumo.application.workflow.persistence import workflow_state_repository

    from ....application.auth.apoderado_service import ApoderadoService
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
    emit_envelope(ctx, command="config.auth.apoderado.clear", result=clear_result, lines=lines)


def apoderado_check(
    ctx: typer.Context,
    output_language: OutputLanguage | None = None,
) -> None:
    _activate_subcommand_output_language(ctx, output_language)
    from cadrumo.application.workflow.persistence import workflow_state_repository

    from ....application.auth.apoderado_service import ApoderadoService

    workflow_state_repository().load()
    pointer = _active_profile_pointer()
    svc = ApoderadoService()

    # ``check`` is the live-verification verb. The live AEAT-read path is not
    # wired (live reads are refused at this boundary per the safety gate), so
    # the service refuses rather than silently re-reading stored configuration
    # and presenting it as a live result. Surface the registered refusal copy;
    # ``status`` is the offline configuration read.
    svc.check(bucket_id=pointer.bucket_id)


__all__ = [
    "apoderado_check",
    "apoderado_clear",
    "apoderado_configure",
    "apoderado_scopes_list",
    "apoderado_status",
]
