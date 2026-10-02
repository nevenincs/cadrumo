"""Human Google credential-source commands backed by the registered worker."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ....application.user_profile.google_configuration_operation_contracts import (
    GoogleCredentialSourceSetProjection,
    GoogleCredentialSourceSetRequest,
    GoogleCredentialSourceViewProjection,
    GoogleCredentialSourceViewRequest,
)
from ....core.google_credential_source import GoogleCredentialSourceKind
from ..common import emit_envelope
from ..runtime_profile_binding import bound_profile_client
from ._google_credential_source_payloads import (
    GoogleCredentialSourceSetResult,
    GoogleCredentialSourceViewResult,
)
from .runtime_google_configuration import run_google_configuration

if TYPE_CHECKING:
    import typer


def _set_result(projection: GoogleCredentialSourceSetProjection) -> GoogleCredentialSourceSetResult:
    return GoogleCredentialSourceSetResult(
        profile=str(projection.profile_id),
        kind=projection.kind,
        target_principal=projection.target_principal,
        target_scopes=list(projection.target_scopes),
        delegates=list(projection.delegates),
        subject=projection.subject,
        lifetime_s=projection.lifetime_s,
    )


def _view_result(projection: GoogleCredentialSourceViewProjection) -> GoogleCredentialSourceViewResult:
    return GoogleCredentialSourceViewResult(
        profile=str(projection.profile_id),
        configured=projection.configured,
        kind=projection.kind,
        target_principal=projection.target_principal,
        target_scopes=list(projection.target_scopes),
        delegates=list(projection.delegates),
        subject=projection.subject,
        lifetime_s=projection.lifetime_s,
    )


def _selection_lines(
    operation: str,
    projection: GoogleCredentialSourceSetProjection | GoogleCredentialSourceViewProjection,
) -> tuple[str, ...]:
    profile = str(projection.profile_id)
    lines = [f"operation\t{operation}", f"profile\t{profile}", f"kind\t{projection.kind.value}"]
    if projection.target_principal is None:
        return tuple(lines)
    lines.append(f"target_principal\t{projection.target_principal}")
    lines.extend(f"scope\t{scope}" for scope in projection.target_scopes)
    lines.extend(f"delegate\t{delegate}" for delegate in projection.delegates)
    if projection.subject is not None:
        lines.append(f"subject\t{projection.subject}")
    if projection.lifetime_s is not None:
        lines.append(f"lifetime_s\t{projection.lifetime_s}")
    return tuple(lines)


def google_credential_source_set(
    ctx: typer.Context,
    kind: GoogleCredentialSourceKind,
    target_principal: str | None = None,
    scopes: list[str] | None = None,
    delegates: list[str] | None = None,
    subject: str | None = None,
    lifetime_seconds: int | None = None,
) -> None:
    """Persist the selected source for the invocation's authenticated profile."""
    client = bound_profile_client(ctx)
    projection = run_google_configuration(
        ctx,
        GoogleCredentialSourceSetRequest(
            profile_id=client.profile_id,
            kind=kind,
            target_principal=target_principal,
            scopes=tuple(scopes or ()),
            delegates=tuple(delegates or ()),
            subject=subject,
            lifetime_seconds=lifetime_seconds,
        ),
        result_type=GoogleCredentialSourceSetProjection,
    )
    operation = "config.google.credential_source.set"
    emit_envelope(
        ctx,
        command=operation,
        result=_set_result(projection),
        lines=_selection_lines(operation, projection),
    )


def google_credential_source_view(ctx: typer.Context) -> None:
    """Report the exact profile's configured source or OAuth Desktop default."""
    client = bound_profile_client(ctx)
    projection = run_google_configuration(
        ctx,
        GoogleCredentialSourceViewRequest(profile_id=client.profile_id),
        result_type=GoogleCredentialSourceViewProjection,
    )
    operation = "config.google.credential_source.view"
    emit_envelope(
        ctx,
        command=operation,
        result=_view_result(projection),
        lines=_selection_lines(operation, projection),
    )


__all__ = ["google_credential_source_set", "google_credential_source_view"]
