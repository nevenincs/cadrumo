"""Authentication setup and readiness on the existing censal pull surface."""

from __future__ import annotations

from pathlib import Path

import click
import typer

from cadrumo_client.commands.errors import CliRefusedBoundaryError
from cadrumo_client.commands.profile_binding import bound_profile_client
from cadrumo_client.commands.registered_operation import run_registered_operation
from cadrumo_client.commands.registered_operation_errors import invalid_completion_error
from cadrumo_client.commands.secure_input import prompt_secret_no_echo, terminal_can_prompt_for_secrets
from cadrumo_client.transport.frontend_client import FrontendClient

from ....application.auth.auth_read_contracts import (
    AUTH_READ_OPERATION_DEFINITION_ID,
    AuthReadProjection,
    AuthReadRequest,
)
from ....application.auth.catalogue import known_auth_provider_ids
from ....application.auth.operation_definitions import (
    AUTH_CONFIGURE_OPERATION_DEFINITION_ID,
    AuthConfigureOperationRequest,
)
from ....application.auth.provider_configure_operation_access import AuthConfigurePublicResultV2
from ....application.auth.sync_readiness import AuthSyncReadiness
from ....application.auth.sync_requirement_text import sync_requirement_reason
from ....application.user_profile.profile_operation_contracts import ProfileFieldMutationOperationRequest
from ....application.user_profile.view_operation import ProfileViewFactItem, ProfileViewPageKind
from ....core.auth_provider import AuthProviderKind, ClaveMovilRoute
from ....core.i18n.render import tr
from ....core.operations import OperationEffect, profile_operation_subject
from ....core.output_rendering import OutputFormat
from ..common import format_of
from ._profile_mutation import execute_profile_mutation, mutation_deadline, read_mutation_baseline


def read_censo_auth(client: FrontendClient) -> AuthSyncReadiness:
    """Read the worker's requirements without acquiring an AEAT session."""
    completed = run_registered_operation(
        client,
        AuthReadRequest(profile_id=client.profile_id, kind="sync_readiness"),
        definition_id=AUTH_READ_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=AuthReadProjection,
        request_version=1,
        result_version=1,
        timeout=60,
    )
    projection = completed.projection
    if (
        projection.profile_id != client.profile_id
        or projection.kind != "sync_readiness"
        or projection.sync_readiness is None
        or completed.effect is not OperationEffect.NONE
    ):
        raise invalid_completion_error(completed)
    return projection.sync_readiness


def require_censo_auth(ctx: typer.Context, *, configure: bool = False) -> None:
    """Offer setup at a console, and return actionable failures for scripts."""
    client = bound_profile_client(ctx)
    readiness = read_censo_auth(client)
    interactive = format_of(ctx) is not OutputFormat.JSON and terminal_can_prompt_for_secrets()
    if configure and not interactive:
        raise _readiness_error(readiness, console_required=True)
    if configure or (not readiness.ready and interactive and typer.confirm(tr("cli.censo_auth.offer"), default=True)):
        _configure(client, readiness)
        readiness = read_censo_auth(client)
    if not readiness.ready:
        raise _readiness_error(readiness)


def _readiness_error(readiness: AuthSyncReadiness, *, console_required: bool = False) -> CliRefusedBoundaryError:
    missing = "; ".join(
        f"{item.field}: {sync_requirement_reason(item.reason)}" for item in readiness.requirements if not item.satisfied
    )
    return CliRefusedBoundaryError(
        translated_message="cli.censo_auth.console_required" if console_required else "cli.censo_auth.required",
        context={"requirements": missing, "command": "aeat config profile censo pull --configure-auth"},
    )


def _save_field(client: FrontendClient, path: str, value: str) -> None:
    deadline = mutation_deadline()
    baseline = read_mutation_baseline(client, deadline=deadline)
    execute_profile_mutation(
        client,
        ProfileFieldMutationOperationRequest(
            profile_id=client.profile_id,
            expected_revision=baseline.record_revision,
            expected_content_digest=baseline.content_digest,
            path=path,
            value=value,
        ),
        deadline=deadline,
    )


def _prompt_field(client: FrontendClient, path: str) -> None:
    baseline = read_mutation_baseline(client, deadline=mutation_deadline())
    current = next(
        (
            item.value
            for item in baseline.items(ProfileViewPageKind.FACTS)
            if isinstance(item, ProfileViewFactItem) and item.path == path
        ),
        "",
    )
    # Credential inputs never become prompt defaults or get echoed to stdout.
    value = prompt_secret_no_echo(tr("cli.censo_auth.field", field=path))
    if value:
        _save_field(client, path, value.strip())
    elif not current:
        typer.echo(tr("cli.censo_auth.still_missing", field=path), err=True)


def _configure(client: FrontendClient, readiness: AuthSyncReadiness) -> None:
    choices = known_auth_provider_ids()
    provider = typer.prompt(
        tr("cli.censo_auth.method"),
        type=click.Choice(choices),
        default=readiness.provider or None,
    )
    kind = AuthProviderKind(provider)
    route = None
    certificate = None
    if kind is AuthProviderKind.CLAVE_MOVIL:
        route = ClaveMovilRoute(
            typer.prompt(
                tr("cli.censo_auth.route"),
                type=click.Choice(tuple(item.value for item in ClaveMovilRoute)),
                default=readiness.route or "qr",
            )
        )
    if kind is AuthProviderKind.CERTIFICATE:
        value = prompt_secret_no_echo(tr("cli.censo_auth.certificate"))
        certificate = Path(value).expanduser().resolve(strict=False) if value else None
    completed = run_registered_operation(
        client,
        AuthConfigureOperationRequest(provider=kind, certificate_path=certificate, clave_movil_route=route),
        definition_id=AUTH_CONFIGURE_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=AuthConfigurePublicResultV2,
        request_version=1,
        result_version=2,
        timeout=120,
    )
    if completed.projection.profile_id != client.profile_id or completed.projection.provider is not kind:
        raise invalid_completion_error(completed)
    _prompt_field(client, "identity.tax_id")
    if kind is not AuthProviderKind.CERTIFICATE:
        _prompt_field(client, "auth.dni_nie")
        if kind is AuthProviderKind.CLAVE_MOVIL and route is ClaveMovilRoute.APP_REQUEST:
            pending = read_censo_auth(client)
            for item in pending.requirements:
                if item.field in {"auth.fecha_validez", "auth.numero_soporte"}:
                    _prompt_field(client, item.field)
    if kind in {AuthProviderKind.CERTIFICATE, AuthProviderKind.CLAVE_PERMANENTE}:
        _save_password(client, kind)
    typer.echo(tr("cli.censo_auth.saved"), err=True)


def _save_password(client: FrontendClient, provider: AuthProviderKind) -> None:
    import json

    from ....application.auth.credential_operations import (
        AUTH_CREDENTIAL_SAVE_OPERATION_DEFINITION_ID,
        AuthCredentialSaveRequest,
        AuthCredentialSaveResult,
    )

    password = prompt_secret_no_echo(tr("cli.censo_auth.password"))
    if not password:
        return
    secret = bytearray(json.dumps({"password": password}).encode("utf-8"))
    password = ""
    try:
        completed = run_registered_operation(
            client,
            AuthCredentialSaveRequest(provider=provider.value),
            definition_id=AUTH_CREDENTIAL_SAVE_OPERATION_DEFINITION_ID,
            subject_ref=profile_operation_subject(str(client.profile_id)),
            result_type=AuthCredentialSaveResult,
            request_version=1,
            result_version=1,
            timeout=120,
            secret=secret,
        )
        if not completed.projection.saved or completed.projection.provider != provider.value:
            raise invalid_completion_error(completed)
    finally:
        secret[:] = b"\x00" * len(secret)


__all__ = ["read_censo_auth", "require_censo_auth"]
