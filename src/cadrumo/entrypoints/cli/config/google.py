"""Human Google configuration and archive push commands.

Google account, folder, and probe commands submit exact-profile
requests to the authenticated worker. Archive mirroring uses its registered
profile operation as well.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ....adapters.outbound.storage.records import ProviderKind
from ....application.user_profile.archive_operation_ports import ProfileArchivePushReport
from ....application.user_profile.google_configuration_operation_contracts import (
    GoogleLoginProjection,
    GoogleLoginRequest,
    GoogleLogoutProjection,
    GoogleLogoutRequest,
    GoogleProbeProjection,
    GoogleProbeRequest,
    GoogleStatusProjection,
    GoogleStatusRequest,
)
from ....core.i18n.render import tr
from ....core.json_contract import Notice, NoticeSeverity
from ..common import emit_envelope
from ..runtime_profile_binding import bound_profile_client
from ._archive_push_payloads import (
    ProfileArchivePushDegradedManifestPayload,
    ProfileArchivePushFailedManifestPayload,
    ProfileArchivePushFailedObjectPayload,
    ProfileArchivePushResult,
)
from ._google_payloads import (
    GoogleLoginResult,
    GoogleLogoutResult,
    GoogleStatusResult,
    GoogleSyncProbeResult,
)
from .runtime_google_configuration import run_google_configuration

if TYPE_CHECKING:
    import typer


def google_login(ctx: typer.Context) -> None:
    """Run the worker's human-consented login flow."""
    client = bound_profile_client(ctx)
    projection = run_google_configuration(
        ctx,
        GoogleLoginRequest(profile_id=client.profile_id),
        result_type=GoogleLoginProjection,
    )
    profile = str(projection.profile_id)
    typed = GoogleLoginResult(
        profile=profile,
        account_email=projection.account_email,
        granted_scopes=list(projection.granted_scopes),
        root_folder_id=projection.root_folder_id,
    )
    emit_envelope(
        ctx,
        command="config.google.login",
        result=typed,
        lines=(
            "operation\tconfig.google.login",
            f"profile\t{profile}",
            f"account_email\t{projection.account_email}",
            f"root_folder_id\t{projection.root_folder_id}",
            *tuple(f"scope\t{scope}" for scope in projection.granted_scopes),
        ),
    )


def _google_status_result(projection: GoogleStatusProjection) -> GoogleStatusResult:
    return GoogleStatusResult(
        profile=str(projection.profile_id),
        session_present=projection.session_present,
        account_email=projection.account_email,
        granted_scopes=list(projection.granted_scopes),
        issued_at=projection.issued_at,
    )


def _google_status_lines(projection: GoogleStatusProjection) -> tuple[str, ...]:
    lines = [
        "operation\tconfig.google.status",
        f"profile\t{projection.profile_id}",
        f"session_present\t{projection.session_present}",
    ]
    if projection.session_present:
        lines.extend(
            (
                f"account_email\t{projection.account_email}",
                f"issued_at\t{projection.issued_at}",
                *tuple(f"scope\t{scope}" for scope in projection.granted_scopes),
            ),
        )
    return tuple(lines)


def google_status(ctx: typer.Context) -> None:
    """Report non-secret session metadata from the worker."""
    client = bound_profile_client(ctx)
    projection = run_google_configuration(
        ctx,
        GoogleStatusRequest(profile_id=client.profile_id),
        result_type=GoogleStatusProjection,
    )
    emit_envelope(
        ctx,
        command="config.google.status",
        result=_google_status_result(projection),
        lines=_google_status_lines(projection),
    )


def google_logout(ctx: typer.Context) -> None:
    """Clear session records through the worker."""
    client = bound_profile_client(ctx)
    projection = run_google_configuration(
        ctx,
        GoogleLogoutRequest(profile_id=client.profile_id),
        result_type=GoogleLogoutProjection,
    )
    profile = str(projection.profile_id)
    result = GoogleLogoutResult(
        profile=profile,
        token_removed=projection.token_removed,
        metadata_removed=projection.metadata_removed,
    )
    emit_envelope(
        ctx,
        command="config.google.logout",
        result=result,
        lines=(
            "operation\tconfig.google.logout",
            f"profile\t{profile}",
            f"token_removed\t{projection.token_removed}",
            f"metadata_removed\t{projection.metadata_removed}",
        ),
    )


def google_sync_probe(ctx: typer.Context, read_only: bool = False) -> None:
    """Run the canonical Google Drive probe through the registered worker."""
    client = bound_profile_client(ctx)
    projection = run_google_configuration(
        ctx,
        GoogleProbeRequest(profile_id=client.profile_id, read_only=read_only),
        result_type=GoogleProbeProjection,
    )
    profile = str(projection.profile_id)
    probe_result = GoogleSyncProbeResult(
        profile=profile,
        provider_kind=ProviderKind(projection.provider_kind),
        reachable=projection.reachable,
        writable=projection.writable,
        read_only=projection.read_only,
        root_folder_present=projection.root_folder_present,
        root_folder_id=projection.root_folder_id,
        detail=projection.detail,
    )
    emit_envelope(
        ctx,
        command="config.google.probe",
        result=probe_result,
        lines=(
            "operation\tconfig.google.probe",
            f"profile\t{profile}",
            f"provider_kind\t{projection.provider_kind}",
            f"reachable\t{projection.reachable}",
            f"writable\t{projection.writable}",
            f"read_only\t{projection.read_only}",
            f"root_folder_present\t{projection.root_folder_present}",
            f"root_folder_id\t{projection.root_folder_id}",
            f"detail\t{projection.detail}",
        ),
    )


def _google_sync_push_result(report: ProfileArchivePushReport) -> ProfileArchivePushResult:
    """Restore the established CLI payload from the canonical worker report."""
    return ProfileArchivePushResult(
        profile=report.profile,
        root_folder_id=report.root_folder_id,
        dry_run=report.dry_run,
        namespace_filter=report.namespace_filter,
        limit=report.limit,
        pushed_total=report.pushed_total,
        skipped_total=report.skipped_total,
        failed_total=report.failed_total,
        manifest_pushed_total=report.manifest_pushed_total,
        manifest_failed_total=report.manifest_failed_total,
        manifest_degraded_total=report.manifest_degraded_total,
        pushed_by_namespace=report.pushed_counts(),
        skipped_by_namespace=report.skipped_counts(),
        failed_objects=[
            ProfileArchivePushFailedObjectPayload(namespace=row.namespace, hmac=str(row.hmac), error=row.error)
            for row in report.failed_objects
        ],
        manifest_pushed_by_namespace=report.manifest_pushed_counts(),
        failed_manifests=[
            ProfileArchivePushFailedManifestPayload(namespace=row.namespace, error=row.error)
            for row in report.failed_manifests
        ],
        degraded_manifests=[
            ProfileArchivePushDegradedManifestPayload(namespace=row.namespace, detail=row.detail)
            for row in report.degraded_manifests
        ],
        cleanup_failed_objects=[
            ProfileArchivePushFailedObjectPayload(namespace=row.namespace, hmac=str(row.hmac), error=row.error)
            for row in report.cleanup_failed_objects
        ],
    )


def _google_sync_push_lines(report: ProfileArchivePushReport) -> list[str]:
    """Render the unchanged concise mirror summary from its closed report."""
    pushed_by_ns = report.pushed_counts()
    skipped_by_ns = report.skipped_counts()
    failed = report.failed_objects
    manifest_degraded = report.degraded_manifests
    cleanup_failed = report.cleanup_failed_objects
    lines = [
        "operation\tconfig.profile.archive.push",
        f"profile\t{report.profile}",
        f"root_folder_id\t{report.root_folder_id}",
        f"dry_run\t{report.dry_run}",
        f"namespace_filter\t{report.namespace_filter or '<all>'}",
        f"limit\t{report.limit or '<none>'}",
        f"pushed_total\t{report.pushed_total}",
        f"skipped_total\t{report.skipped_total}",
        f"failed_total\t{report.failed_total}",
        f"manifest_pushed_total\t{report.manifest_pushed_total}",
        f"manifest_failed_total\t{report.manifest_failed_total}",
        f"manifest_degraded_total\t{report.manifest_degraded_total}",
    ]
    for ns in sorted(set(pushed_by_ns) | set(skipped_by_ns)):
        lines.append(f"namespace\t{ns}\tpushed={pushed_by_ns.get(ns, 0)}\tskipped={skipped_by_ns.get(ns, 0)}")
    lines.extend(f"failed\t{row.namespace}\t{str(row.hmac)[:16]}\t{row.error}" for row in failed)
    lines.extend(f"degraded_manifest\t{row.namespace}\t{row.detail}" for row in manifest_degraded)
    lines.extend(f"cleanup_failed\t{row.namespace}\t{str(row.hmac)[:16]}\t{row.error}" for row in cleanup_failed)
    return lines


def _profile_archive_push_notices(report: ProfileArchivePushReport) -> list[Notice]:
    """Keep the established typed warning for unmanifested cleanup failures."""
    cleanup_failed = report.cleanup_failed_objects
    if not cleanup_failed:
        return []
    return [
        Notice(
            severity=NoticeSeverity.WARNING,
            code="config.profile.archive.push.unmanifested_object",
            message=tr(
                "cli.config.profile.archive.push_unmanifested_object_warning",
                count=str(len(cleanup_failed)),
            ),
            context={"namespaces": ",".join(sorted({row.namespace for row in cleanup_failed}))},
        ),
    ]


def profile_archive_push(
    ctx: typer.Context,
    namespace_filter: str | None = None,
    limit: int | None = None,
    dry_run: bool = False,
) -> None:
    """Mirror the exact authenticated profile through the registered worker."""
    from ....application.user_profile.archive_operation import ProfileArchivePushRequest
    from ..runtime_profile_archive import run_profile_archive_push
    from ..runtime_profile_binding import bound_profile_client

    client = bound_profile_client(ctx)
    projection = run_profile_archive_push(
        ctx,
        ProfileArchivePushRequest(
            profile_id=client.profile_id,
            namespace_filter=namespace_filter,
            limit=limit,
            dry_run=dry_run,
        ),
    )
    report = projection.report
    push_result = _google_sync_push_result(report)
    lines = _google_sync_push_lines(report)
    notices = _profile_archive_push_notices(report)
    emit_envelope(
        ctx,
        command="config.profile.archive.push",
        result=push_result,
        lines=tuple(lines),
        notices=notices,
    )


__all__ = [
    "google_login",
    "google_logout",
    "google_status",
    "google_sync_probe",
    "profile_archive_push",
]
