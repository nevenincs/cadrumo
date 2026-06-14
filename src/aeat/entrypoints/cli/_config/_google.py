"""Operator-facing `aeat config google ...` Typer commands.

Four commands wire the Google OAuth Desktop backend
(`aeat.adapters.outbound.google`) into the CLI:

- `register --client-json <path>` — read + validate a Cloud Console
  Desktop client JSON and persist it as the operator's per-profile
  `oauth-client` record.
- `login [--refresh-only]` — run the loopback IP + PKCE consent flow
  and persist the resulting `oauth-token` + `oauth-metadata`. When
  `--refresh-only` is given, skip the consent screen and only refresh
  an existing credential.
- `status` — report account email, granted scopes, last refresh, and
  reauth-required flag. Honours the root `--format json|text` flag.
- `logout` — clear the `oauth-token` and `oauth-metadata` records but
  preserve the registered `oauth-client` so a subsequent `login` works
  without re-importing the JSON.

Every command resolves the active profile via
`_profile_binding.resolve_active_profile(--profile)` and surfaces
`GoogleAuthError` subclasses with the project's standard exit-code +
JSON envelope semantics.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypedDict

import typer
from pydantic import BaseModel, ConfigDict, ValidationError

# Importing the renta package registers the first-slice routing
# cross-domain snapshot check with the registry validator. build_snapshot
# of a Modelo 100 revision fails loudly if that check is unregistered, so
# the M100 routing referential-integrity gate runs on this CLI path.
from ....adapters.outbound.google import (
    REQUIRED_SCOPES,
    GoogleAuthClientNotRegisteredError,
    GoogleAuthError,
    GoogleAuthExpiredError,
    GoogleAuthValidationError,
    OAuthClient,
)
from ....adapters.outbound.google._oauth_flow import run_login_flow
from ....adapters.outbound.google._profile_binding import resolve_active_profile
from ....adapters.outbound.google._session_store import (
    delete_session,
    load_client,
    load_metadata,
    load_token,
    save_client,
    save_metadata,
    save_token,
)
from ....adapters.outbound.storage import (
    OutboundStorageError,
    OutboundStorageValidationError,
    RemoteMirrorIssue,
    RemoteMirrorIssueKind,
    RemoteMirrorNamespaceManifest,
    StorageProvider,
    build_remote_mirror_namespace_manifest,
    compare_remote_mirror_manifests,
    get_remote_mirror_namespace_manifest,
    get_storage_provider,
    inspect_remote_mirror_download,
    inspect_remote_mirror_upload,
    put_remote_mirror_namespace_manifest,
    remote_mirror_object_key_hmac,
)
from ....adapters.persistence.storage.runtime_repository import secure_object_repository_for_active_bucket
from ....adapters.persistence.storage.sql.secure_objects import SecureObjectRawRow, SecureObjectRepository
from ....core.config import load_settings
from ....core.hashing import sha256_hex
from ....core.i18n import tr
from .._common import _emit_envelope
from ._google_errors import _google_refusal
from ._google_folder import register_google_folder_commands
from ._google_payloads import (
    GoogleLoginResult,
    GoogleLogoutResult,
    GoogleRegisterResult,
    GoogleStatusResult,
    GoogleSyncDegradedManifestPayload,
    GoogleSyncFailedManifestPayload,
    GoogleSyncFailedObjectPayload,
    GoogleSyncProbeResult,
    GoogleSyncPushResult,
)
from ._google_sync_calc import (
    google_sync_calc_export,
    google_sync_calc_pull,
    google_sync_calc_verify,
    register_google_sync_calc_commands,
)

google_app = typer.Typer(
    name="google",
    help=tr("cli.config.google.help"),
    no_args_is_help=True,
)


class OAuthClientPayload(TypedDict):
    """Typed shape for a Cloud Console Desktop OAuth client JSON file.

    Cloud Console emits ``{"installed": {<client fields>}}`` for Desktop
    application types. Only the ``installed`` key is accepted here; the
    ``web`` variant is rejected by :func:`_coerce_client_json`.
    """

    # ANY-RETURN-RATIONALE-GOOGLE-OAUTH-STAGING: irreducible Google Cloud
    # Console JSON envelope; narrowed to OAuthClient before production use.
    installed: dict[str, Any]


class _OAuthClientWrapper(BaseModel):
    """Pydantic wrapper that validates the outer Cloud Console envelope.

    Validates that the JSON payload is a mapping that carries exactly an
    ``installed`` field, which must itself be a dict. Downstream callers
    then unwrap ``installed`` and validate the inner structure through
    :class:`OAuthClient`.
    """

    model_config = ConfigDict(frozen=True, extra="ignore")

    # ANY-RETURN-RATIONALE-GOOGLE-OAUTH-STAGING: irreducible Google Cloud
    # Console JSON envelope; narrowed to OAuthClient before production use.
    installed: dict[str, Any]


def _coerce_client_json(path: Path) -> OAuthClient:
    """Read ``path``, unwrap the Cloud Console wrapper, return an OAuthClient.

    Cloud Console emits the JSON as ``{"installed": {<client fields>}}``
    for Desktop application types and ``{"web": {...}}`` for Web
    applications. Only the Desktop ("installed") shape is accepted;
    other shapes raise `GoogleAuthValidationError`.
    """
    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise GoogleAuthValidationError(
            translated_message="cli.config.google.detail.client_json_unreadable",
            context={"path": str(path), "reason": str(exc)},
        ) from exc
    try:
        raw_payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise GoogleAuthValidationError(
            translated_message="cli.config.google.detail.client_json_invalid",
            context={"path": str(path), "reason": exc.msg},
        ) from exc
    try:
        wrapper = _OAuthClientWrapper.model_validate(raw_payload)
    except ValidationError as _wrapper_exc:
        # _OAuthClientWrapper.extra="ignore" accepts extra top-level keys; missing
        # "installed" raises a required-field ValidationError — both the web-client
        # shape (no "installed" key) and a non-dict payload map to client_json_not_desktop.
        raise GoogleAuthValidationError(
            translated_message="cli.config.google.detail.client_json_not_desktop",
            context={"path": str(path)},
        ) from _wrapper_exc
    # Cloud Console writes redirect_uris as a JSON array; strict pydantic
    # rejects list-vs-tuple coercion, so normalise before validation.
    coerced = dict(wrapper.installed)
    if isinstance(coerced.get("redirect_uris"), list):
        coerced["redirect_uris"] = tuple(coerced["redirect_uris"])
    try:
        return OAuthClient.model_validate(coerced)
    except ValidationError as exc:
        raise GoogleAuthValidationError(
            translated_message="cli.config.google.detail.client_json_schema_invalid",
            context={"path": str(path), "reason": str(exc.errors(include_url=False))},
        ) from exc


@google_app.command("register", help=tr("cli.config.google.register_help"))
def google_register(
    ctx: typer.Context,
    client_json: Path = typer.Option(
        ...,
        "--client-json",
        help=tr("cli.config.google.client_json_help"),
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
    ),
) -> None:
    """Register a Cloud Console Desktop OAuth client for the active profile."""
    try:
        active = resolve_active_profile()
        client = _coerce_client_json(client_json)
        save_client(active, client)
    except GoogleAuthError as exc:
        raise _google_refusal(exc) from exc

    typed = GoogleRegisterResult(
        profile=active,
        client_id=client.client_id,
        project_id=client.project_id,
    )
    _emit_envelope(
        ctx,
        command="config.google.register",
        result=typed,
        lines=(
            "operation\tconfig.google.register",
            f"profile\t{active}",
            f"client_id\t{client.client_id}",
            f"project_id\t{client.project_id}",
        ),
    )


@google_app.command("login", help=tr("cli.config.google.login_help"))
def google_login(
    ctx: typer.Context,
    refresh_only: bool = typer.Option(
        False,
        "--refresh-only",
        help=tr("cli.config.google.refresh_only_help"),
    ),
) -> None:
    """Run the loopback IP + PKCE consent flow (or refresh an existing credential)."""
    try:
        active = resolve_active_profile()
        client = load_client(active)
        if client is None:
            raise GoogleAuthClientNotRegisteredError(
                translated_message="cli.config.google.detail.client_unregistered",
                context={"profile": active},
                suggestion="aeat config google register --client-json <path>",
            )
        if refresh_only:
            metadata = load_metadata(active)
            if metadata is None:
                raise GoogleAuthExpiredError(
                    translated_message="cli.config.google.detail.no_metadata_for_refresh",
                    context={"profile": active},
                    suggestion="aeat config google login",
                )
            typed_refresh = GoogleLoginResult(
                profile=active,
                mode="refresh-only",
                account_email=metadata.account_email,
            )
            _emit_envelope(
                ctx,
                command="config.google.login",
                result=typed_refresh,
                lines=(
                    "operation\tconfig.google.login",
                    f"profile\t{active}",
                    "mode\trefresh-only",
                    f"account_email\t{metadata.account_email}",
                ),
            )
            return
        token, metadata = run_login_flow(client, active)
        save_token(active, token)
        save_metadata(active, metadata)
    except GoogleAuthError as exc:
        raise _google_refusal(exc) from exc

    typed_consent = GoogleLoginResult(
        profile=active,
        mode="consent",
        account_email=metadata.account_email,
        granted_scopes=list(metadata.granted_scopes),
    )
    _emit_envelope(
        ctx,
        command="config.google.login",
        result=typed_consent,
        lines=(
            "operation\tconfig.google.login",
            f"profile\t{active}",
            "mode\tconsent",
            f"account_email\t{metadata.account_email}",
            *tuple(f"scope\t{scope}" for scope in metadata.granted_scopes),
        ),
    )


@google_app.command("status", help=tr("cli.config.google.status_help"))
def google_status(
    ctx: typer.Context,
) -> None:
    """Report the current Google OAuth session state for the active profile."""
    try:
        active = resolve_active_profile()
    except GoogleAuthError as exc:
        raise _google_refusal(exc) from exc

    client = load_client(active)
    metadata = load_metadata(active)
    typed_status = GoogleStatusResult(
        profile=active,
        client_registered=client is not None,
        client_id=client.client_id if client is not None else None,
        session_present=metadata is not None,
        account_email=metadata.account_email if metadata is not None else None,
        granted_scopes=list(metadata.granted_scopes) if metadata is not None else [],
        issued_at=metadata.issued_at.isoformat() if metadata is not None else None,
        last_refresh_at=metadata.last_refresh_at.isoformat() if metadata is not None else None,
        reauth_required=metadata.reauth_required if metadata is not None else None,
    )
    lines = [
        "operation\tconfig.google.status",
        f"profile\t{active}",
        f"client_registered\t{client is not None}",
        f"session_present\t{metadata is not None}",
    ]
    if client is not None:
        lines.append(f"client_id\t{client.client_id}")
    if metadata is not None:
        lines.extend(
            (
                f"account_email\t{metadata.account_email}",
                f"issued_at\t{metadata.issued_at.isoformat()}",
                f"last_refresh_at\t{metadata.last_refresh_at.isoformat()}",
                f"reauth_required\t{metadata.reauth_required}",
                *tuple(f"scope\t{scope}" for scope in metadata.granted_scopes),
            ),
        )
    _emit_envelope(ctx, command="config.google.status", result=typed_status, lines=tuple(lines))


@google_app.command("logout", help=tr("cli.config.google.logout_help"))
def google_logout(
    ctx: typer.Context,
) -> None:
    """Clear the refresh token + metadata for the active profile.

    The registered OAuth client is intentionally preserved: a
    subsequent `aeat config google login` can re-acquire a session
    without the operator re-importing the Cloud Console JSON.
    """
    try:
        active = resolve_active_profile()
    except GoogleAuthError as exc:
        raise _google_refusal(exc) from exc

    token_removed, metadata_removed = delete_session(active)
    typed_logout = GoogleLogoutResult(
        profile=active,
        token_removed=token_removed,
        metadata_removed=metadata_removed,
        client_preserved=True,
    )
    _emit_envelope(
        ctx,
        command="config.google.logout",
        result=typed_logout,
        lines=(
            "operation\tconfig.google.logout",
            f"profile\t{active}",
            f"token_removed\t{token_removed}",
            f"metadata_removed\t{metadata_removed}",
            "client_preserved\tTrue",
        ),
    )


register_google_folder_commands(google_app, google_refusal=_google_refusal)


sync_app = typer.Typer(
    name="sync",
    help=tr("cli.config.google.sync.help"),
    no_args_is_help=True,
)


@sync_app.command("probe", help=tr("cli.config.google.sync.probe_help"))
def google_sync_probe(
    ctx: typer.Context,
    read_only: bool = typer.Option(
        False,
        "--read-only/--no-read-only",
        help=tr("cli.config.google.sync.probe_read_only_help"),
    ),
) -> None:
    """Build a real `GoogleDriveProvider` and execute `probe()` against `drive.googleapis.com`.

    Confirms that the per-profile OAuth records persisted by `login`
    yield usable credentials, the configured `aeat_google_drive_root_folder_id`
    resolves to a real folder, and (when `--no-read-only`) a sentinel
    file round-trips into `_probe/`.
    """
    try:
        active = resolve_active_profile()
    except GoogleAuthError as exc:
        raise _google_refusal(exc) from exc

    settings = load_settings()
    # The factory uses Settings.aeat_storage_provider_kind to pick the
    # backend. For the operator-driven probe we override to Google Drive
    # explicitly so the probe always exercises the Drive path regardless
    # of how the operator's environment is configured. The folder id
    # itself is resolved by the factory via the canonical precedence
    # (env var > persisted DriveConfig record); no separate gate here.
    drive_settings = settings.model_copy(update={"aeat_storage_provider_kind": "google_drive"})

    try:
        provider = get_storage_provider(settings=drive_settings)
        report = provider.probe(read_only=read_only)
    except (GoogleAuthError, OutboundStorageError) as exc:
        raise _google_refusal(exc) from exc

    # Pull the actual root folder id from the provider — the env var
    # OR the persisted DriveConfig may have supplied it; the provider
    # is the single resolved source of truth.
    resolved_root_folder_id = getattr(provider, "root_folder_id", "")
    probe_result = GoogleSyncProbeResult(
        profile=active,
        provider_kind=report.provider_kind.value,
        reachable=report.reachable,
        writable=report.writable,
        read_only=report.read_only,
        root_folder_present=report.root_folder_present,
        root_folder_id=resolved_root_folder_id,
        detail=report.detail,
    )
    _emit_envelope(
        ctx,
        command="config.google.sync.probe",
        result=probe_result,
        lines=(
            "operation\tconfig.google.sync.probe",
            f"profile\t{active}",
            f"provider_kind\t{report.provider_kind.value}",
            f"reachable\t{report.reachable}",
            f"writable\t{report.writable}",
            f"read_only\t{report.read_only}",
            f"root_folder_present\t{report.root_folder_present}",
            f"root_folder_id\t{resolved_root_folder_id}",
            f"detail\t{report.detail}",
        ),
    )


def _object_key_hmac(namespace: str, object_key: bytes) -> str:
    """Compute a stable per-`(namespace, object_key)` hex digest.

    Used by sync push to produce the Drive-side filename prefix
    `<hmac_prefix_8>--<label>.bin`. For v0 the digest is plain
    sha256(namespace + object_key); a per-profile keyed HMAC for
    unlinkability lands alongside P04 (snapshot escrow + HKDF).
    """
    return remote_mirror_object_key_hmac(namespace, object_key)


def _label_for(namespace: str) -> str:
    """Pick a Drive-filename label from `namespace`.

    Default policy: trailing dotted segment, capped at 32 chars,
    sanitised to alnum/dash/underscore. Per-namespace registered
    label-derivers override this default once they ship.
    """
    leaf = namespace.rsplit(".", 1)[-1] or "obj"
    safe = "".join(c if c.isalnum() or c in "-_." else "-" for c in leaf)
    return safe[:32] or "obj"


@dataclass(frozen=True)
class _MirrorRowPartition:
    """Row partition produced before any remote mirror write occurs.

    ``planned_rows_by_namespace`` carries the rows that will be uploaded on a
    non-dry-run; ``skipped_by_namespace`` records the per-namespace counts a
    dry-run reports without touching the provider.
    """

    planned_rows_by_namespace: dict[str, list[SecureObjectRawRow]]
    skipped_by_namespace: dict[str, int]


@dataclass(frozen=True)
class _MirrorPreflightOutcome:
    """Result of inspecting the existing remote mirror before pushing.

    ``manifests_by_namespace`` holds the locally-built manifest for each
    namespace cleared to push; ``blocked_namespaces`` names the namespaces a
    preflight failure removed from the push set. ``failed`` and ``degraded``
    accumulate the operator-facing `(namespace, detail)` diagnostics.
    """

    manifests_by_namespace: dict[str, RemoteMirrorNamespaceManifest]
    blocked_namespaces: set[str]
    failed: list[tuple[str, str]]
    degraded: list[tuple[str, str]]


@dataclass(frozen=True)
class _MirrorObjectPushOutcome:
    """Result of uploading each planned row's ciphertext to the provider.

    ``pushed_by_namespace`` counts the rows that uploaded cleanly;
    ``failed_namespaces`` names every namespace that saw at least one object
    failure (so its manifest is withheld); ``failed`` carries the
    `(namespace, hmac, error)` triples for the operator surface.
    """

    pushed_by_namespace: dict[str, int]
    failed_namespaces: set[str]
    failed: list[tuple[str, str, str]]


def _partition_mirror_rows(
    *,
    repository: SecureObjectRepository,
    namespace_filter: str | None,
    limit: int | None,
    dry_run: bool,
) -> _MirrorRowPartition:
    """Split :meth:`SecureObjectRepository.iter_all_records_raw` into push vs skip.

    Applies the optional ``namespace_filter`` and ``limit`` while iterating;
    on a dry-run every selected row is counted as skipped and no row is
    planned for upload.
    """
    planned_rows_by_ns: dict[str, list[SecureObjectRawRow]] = {}
    skipped_by_ns: dict[str, int] = {}
    total_seen = 0
    for raw_row in repository.iter_all_records_raw():
        if namespace_filter is not None and raw_row.namespace != namespace_filter:
            continue
        total_seen += 1
        if limit is not None and total_seen > limit:
            break
        if dry_run:
            skipped_by_ns[raw_row.namespace] = skipped_by_ns.get(raw_row.namespace, 0) + 1
            continue
        planned_rows_by_ns.setdefault(raw_row.namespace, []).append(raw_row)
    return _MirrorRowPartition(planned_rows_by_namespace=planned_rows_by_ns, skipped_by_namespace=skipped_by_ns)


def _preflight_mirror_namespaces(
    *,
    provider: StorageProvider,
    planned_rows_by_namespace: dict[str, list[SecureObjectRawRow]],
) -> _MirrorPreflightOutcome:
    """Inspect the existing remote mirror for every planned namespace.

    Builds the local :class:`RemoteMirrorNamespaceManifest` per namespace and
    compares it against the remote state. A namespace is blocked (and its
    manifest withheld) on a remote inspection error or a blocking revision
    conflict; degradations are recorded without blocking.
    """
    manifest_by_ns: dict[str, RemoteMirrorNamespaceManifest] = {}
    blocked: set[str] = set()
    failed: list[tuple[str, str]] = []
    degraded: list[tuple[str, str]] = []
    for namespace, rows in planned_rows_by_namespace.items():
        manifest = build_remote_mirror_namespace_manifest(namespace, rows)
        try:
            blocking_failures, degradations = _inspect_existing_remote_mirror(provider=provider, manifest=manifest)
        except OutboundStorageError as exc:
            failed.append((namespace, str(exc)))
            blocked.add(namespace)
            continue
        if degradations:
            degraded.append((namespace, "; ".join(degradations)))
        if blocking_failures:
            failed.append((namespace, "; ".join(blocking_failures)))
            blocked.add(namespace)
            continue
        manifest_by_ns[namespace] = manifest
    return _MirrorPreflightOutcome(
        manifests_by_namespace=manifest_by_ns,
        blocked_namespaces=blocked,
        failed=failed,
        degraded=degraded,
    )


def _push_mirror_objects(
    *,
    provider: StorageProvider,
    planned_rows_by_namespace: dict[str, list[SecureObjectRawRow]],
    blocked_namespaces: set[str],
) -> _MirrorObjectPushOutcome:
    """Upload every planned row's ciphertext payload to the provider.

    Skips namespaces that preflight blocked. Each row uploads via
    :meth:`StorageProvider.put` under its `<hmac>--<label>.bin` name; a
    per-object upload error records the failure and marks the namespace so
    its manifest is later withheld.
    """
    pushed_by_ns: dict[str, int] = {}
    failed_namespaces: set[str] = set()
    failed: list[tuple[str, str, str]] = []
    for namespace, rows in planned_rows_by_namespace.items():
        if namespace in blocked_namespaces:
            continue
        for raw_row in rows:
            hmac_hex = _object_key_hmac(raw_row.namespace, raw_row.object_key)
            label = _label_for(raw_row.namespace)
            content_hash = f"sha256-{sha256_hex(raw_row.payload)}"
            try:
                provider.put(
                    raw_row.namespace,
                    hmac_hex,
                    raw_row.payload,
                    content_hash=content_hash,
                    label=label,
                )
            except OutboundStorageError as exc:
                failed.append((raw_row.namespace, hmac_hex, str(exc)))
                failed_namespaces.add(raw_row.namespace)
                continue
            pushed_by_ns[raw_row.namespace] = pushed_by_ns.get(raw_row.namespace, 0) + 1
    return _MirrorObjectPushOutcome(
        pushed_by_namespace=pushed_by_ns,
        failed_namespaces=failed_namespaces,
        failed=failed,
    )


def _push_mirror_manifests(
    *,
    provider: StorageProvider,
    manifests_by_namespace: dict[str, RemoteMirrorNamespaceManifest],
    failed_namespaces: set[str],
    manifest_failed: list[tuple[str, str]],
) -> dict[str, int]:
    """Persist and verify each namespace manifest whose objects uploaded cleanly.

    Withholds the manifest for any namespace that saw an object failure.
    Appends post-push inspection failures (or a put error) onto the shared
    ``manifest_failed`` accumulator and returns the per-namespace object
    counts for the manifests that pushed and verified.
    """
    manifest_pushed_by_ns: dict[str, int] = {}
    for namespace, manifest in manifests_by_namespace.items():
        if namespace in failed_namespaces:
            continue
        try:
            put_remote_mirror_namespace_manifest(provider, manifest)
            inspection_failures = _inspect_pushed_remote_mirror(provider=provider, manifest=manifest)
        except OutboundStorageError as exc:
            manifest_failed.append((namespace, str(exc)))
            continue
        if inspection_failures:
            manifest_failed.append((namespace, "; ".join(inspection_failures)))
            continue
        manifest_pushed_by_ns[namespace] = manifest.object_count
    return manifest_pushed_by_ns


class _MirrorRowsResult(TypedDict):
    """Typed result of :func:`_push_secure_object_mirror_rows`.

    Each value mirrors the corresponding field on the mirror-pass outcome
    dataclasses (:class:`_MirrorObjectPushOutcome`,
    :class:`_MirrorRowPartition`, :class:`_MirrorPreflightOutcome`), so the
    push handler reads precisely-typed counts and diagnostic triples rather
    than ``object``.
    """

    pushed_by_namespace: dict[str, int]
    skipped_by_namespace: dict[str, int]
    failed_objects: list[tuple[str, str, str]]
    manifest_pushed_by_namespace: dict[str, int]
    failed_manifests: list[tuple[str, str]]
    degraded_manifests: list[tuple[str, str]]


def _push_secure_object_mirror_rows(
    *,
    provider: StorageProvider,
    repository: SecureObjectRepository,
    namespace_filter: str | None,
    limit: int | None,
    dry_run: bool,
) -> _MirrorRowsResult:
    if limit is not None and not dry_run:
        raise OutboundStorageValidationError(
            "non-dry-run Google sync push with --limit cannot produce a complete remote mirror manifest",
            context={"limit": str(limit)},
            suggestion="run without --limit, or add --dry-run for bounded inspection",
            translated_message="cli.config.google.detail.sync_push_limit_requires_dry_run",
        )

    partition = _partition_mirror_rows(
        repository=repository,
        namespace_filter=namespace_filter,
        limit=limit,
        dry_run=dry_run,
    )
    planned_rows_by_ns = partition.planned_rows_by_namespace

    if dry_run:
        preflight = _MirrorPreflightOutcome(manifests_by_namespace={}, blocked_namespaces=set(), failed=[], degraded=[])
    else:
        preflight = _preflight_mirror_namespaces(provider=provider, planned_rows_by_namespace=planned_rows_by_ns)

    object_push = _push_mirror_objects(
        provider=provider,
        planned_rows_by_namespace=planned_rows_by_ns,
        blocked_namespaces=preflight.blocked_namespaces,
    )

    manifest_failed = preflight.failed
    if dry_run:
        manifest_pushed_by_ns: dict[str, int] = {}
    else:
        manifest_pushed_by_ns = _push_mirror_manifests(
            provider=provider,
            manifests_by_namespace=preflight.manifests_by_namespace,
            failed_namespaces=object_push.failed_namespaces,
            manifest_failed=manifest_failed,
        )

    return {
        "pushed_by_namespace": object_push.pushed_by_namespace,
        "skipped_by_namespace": partition.skipped_by_namespace,
        "failed_objects": object_push.failed,
        "manifest_pushed_by_namespace": manifest_pushed_by_ns,
        "failed_manifests": manifest_failed,
        "degraded_manifests": preflight.degraded,
    }


def _inspect_existing_remote_mirror(
    *,
    provider: StorageProvider,
    manifest: RemoteMirrorNamespaceManifest,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    remote_manifest = get_remote_mirror_namespace_manifest(provider, manifest.namespace)
    if remote_manifest is None:
        return (), ()

    blocking_failures: list[str] = []
    degradations: list[str] = []
    for inspection in (
        compare_remote_mirror_manifests(local=manifest, remote=remote_manifest),
        inspect_remote_mirror_download(provider, remote_manifest),
    ):
        for issue in inspection.issues:
            formatted = _format_remote_mirror_issue(issue)
            if issue.kind is RemoteMirrorIssueKind.REVISION_CONFLICT:
                blocking_failures.append(formatted)
                continue
            degradations.append(formatted)
    return tuple(blocking_failures), tuple(degradations)


def _format_remote_mirror_issue(issue: RemoteMirrorIssue) -> str:
    object_key = issue.object_key_hmac[:16] if issue.object_key_hmac is not None else "<namespace>"
    return f"{issue.kind.value}:{object_key}:{issue.detail}"


def _inspect_pushed_remote_mirror(
    *,
    provider: StorageProvider,
    manifest: RemoteMirrorNamespaceManifest,
) -> tuple[str, ...]:
    failures: list[str] = []
    for inspection in (
        inspect_remote_mirror_upload(provider, manifest),
        inspect_remote_mirror_download(provider, manifest),
    ):
        for issue in inspection.issues:
            failures.append(_format_remote_mirror_issue(issue))
    return tuple(failures)


@sync_app.command("push", help=tr("cli.config.google.sync.push_help"))
def google_sync_push(
    ctx: typer.Context,
    namespace_filter: str | None = typer.Option(
        None,
        "--namespace",
        help=tr("cli.config.google.sync.push_namespace_help"),
    ),
    limit: int | None = typer.Option(
        None,
        "--limit",
        help=tr("cli.config.google.sync.push_limit_help"),
        min=1,
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run/--no-dry-run",
        help=tr("cli.config.google.sync.push_dry_run_help"),
    ),
) -> None:
    """Mirror every :class:`SecureObjectRepository` row's on-wire ciphertext to Drive.

    Walks :meth:`SecureObjectRepository.iter_all_records_raw` ordered by
    `(namespace, object_key)`. Each row's ciphertext payload uploads
    via `GoogleDriveProvider.put(...)` under the namespace's Drive
    folder, named `<hmac_prefix_8>--<label>.bin`. The local master
    key never leaves the host — only ciphertext reaches Drive.
    """
    try:
        active = resolve_active_profile()
    except GoogleAuthError as exc:
        raise _google_refusal(exc) from exc

    settings = load_settings()
    drive_settings = settings.model_copy(update={"aeat_storage_provider_kind": "google_drive"})

    try:
        provider = get_storage_provider(settings=drive_settings)
    except (GoogleAuthError, OutboundStorageError) as exc:
        raise _google_refusal(exc) from exc

    resolved_root_folder_id = getattr(provider, "root_folder_id", "")

    repository = secure_object_repository_for_active_bucket()
    try:
        mirror_result = _push_secure_object_mirror_rows(
            provider=provider,
            repository=repository,
            namespace_filter=namespace_filter,
            limit=limit,
            dry_run=dry_run,
        )
    except OutboundStorageError as exc:
        raise _google_refusal(exc) from exc
    pushed_by_ns = mirror_result["pushed_by_namespace"]
    skipped_by_ns = mirror_result["skipped_by_namespace"]
    failed = mirror_result["failed_objects"]
    manifest_pushed_by_ns = mirror_result["manifest_pushed_by_namespace"]
    manifest_failed = mirror_result["failed_manifests"]
    manifest_degraded = mirror_result["degraded_manifests"]

    push_result = GoogleSyncPushResult(
        profile=active,
        root_folder_id=resolved_root_folder_id,
        dry_run=dry_run,
        namespace_filter=namespace_filter,
        limit=limit,
        pushed_total=sum(pushed_by_ns.values()),
        skipped_total=sum(skipped_by_ns.values()),
        failed_total=len(failed),
        manifest_pushed_total=len(manifest_pushed_by_ns),
        manifest_failed_total=len(manifest_failed),
        manifest_degraded_total=len(manifest_degraded),
        pushed_by_namespace=dict(pushed_by_ns),
        skipped_by_namespace=dict(skipped_by_ns),
        failed_objects=[GoogleSyncFailedObjectPayload(namespace=ns, hmac=h, error=err) for ns, h, err in failed],
        manifest_pushed_by_namespace=dict(manifest_pushed_by_ns),
        failed_manifests=[GoogleSyncFailedManifestPayload(namespace=ns, error=err) for ns, err in manifest_failed],
        degraded_manifests=[
            GoogleSyncDegradedManifestPayload(namespace=ns, detail=detail) for ns, detail in manifest_degraded
        ],
    )
    lines: list[str] = [
        "operation\tconfig.google.sync.push",
        f"profile\t{active}",
        f"root_folder_id\t{resolved_root_folder_id}",
        f"dry_run\t{dry_run}",
        f"namespace_filter\t{namespace_filter or '<all>'}",
        f"limit\t{limit or '<none>'}",
        f"pushed_total\t{sum(pushed_by_ns.values())}",
        f"skipped_total\t{sum(skipped_by_ns.values())}",
        f"failed_total\t{len(failed)}",
        f"manifest_pushed_total\t{len(manifest_pushed_by_ns)}",
        f"manifest_failed_total\t{len(manifest_failed)}",
        f"manifest_degraded_total\t{len(manifest_degraded)}",
    ]
    for ns in sorted(set(pushed_by_ns) | set(skipped_by_ns)):
        pushed = pushed_by_ns.get(ns, 0)
        skipped = skipped_by_ns.get(ns, 0)
        lines.append(f"namespace\t{ns}\tpushed={pushed}\tskipped={skipped}")
    for ns, h, err in failed:
        lines.append(f"failed\t{ns}\t{h[:16]}\t{err}")
    for ns, detail in manifest_degraded:
        lines.append(f"degraded_manifest\t{ns}\t{detail}")
    _emit_envelope(ctx, command="config.google.sync.push", result=push_result, lines=tuple(lines))


register_google_sync_calc_commands(sync_app)
google_app.add_typer(sync_app, name="sync")


# Suppress unused-import false positive for `load_token` and `REQUIRED_SCOPES`;
# both are part of the public surface the sync sub-commands consume.
_ = (load_token, REQUIRED_SCOPES)


__all__ = ["google_app", "google_sync_calc_export", "google_sync_calc_pull", "google_sync_calc_verify"]
