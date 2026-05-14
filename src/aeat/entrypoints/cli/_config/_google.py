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

import hashlib
import json
from pathlib import Path

import typer
from pydantic import ValidationError

from ....adapters.outbound.google import (
    GoogleAuthClientNotRegisteredError,
    GoogleAuthError,
    GoogleAuthExpiredError,
    GoogleAuthValidationError,
    OAuthClient,
)
from ....adapters.outbound.google._oauth_flow import run_login_flow
from ....adapters.outbound.google._profile_binding import resolve_active_profile
from ....adapters.outbound.google._records import REQUIRED_SCOPES
from ....adapters.outbound.google._records import DriveConfig
from ....adapters.outbound.google._session_store import (
    delete_session,
    load_client,
    load_drive_config,
    load_metadata,
    load_token,
    save_client,
    save_drive_config,
    save_metadata,
    save_token,
)
from ....adapters.outbound.storage import (
    StorageError,
    get_storage_provider,
)
from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core.config import load_settings
from .._common import _emit
from .._errors import CliRefusedBoundaryError
from .._i18n import tr

google_app = typer.Typer(
    name="google",
    help=tr("cli.config.google.help"),
    no_args_is_help=True,
)


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
            f"failed to read client JSON from {path}: {exc}",
            context={"path": str(path)},
        ) from exc
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise GoogleAuthValidationError(
            f"client JSON at {path} is not valid JSON: {exc.msg}",
            context={"path": str(path), "line": exc.lineno, "column": exc.colno},
        ) from exc
    if not isinstance(payload, dict) or "installed" not in payload:
        raise GoogleAuthValidationError(
            f"client JSON at {path} is not a Cloud Console Desktop client; "
            'expected an "installed" wrapper key',
            context={"path": str(path), "keys": sorted(payload.keys()) if isinstance(payload, dict) else []},
        )
    inner = payload["installed"]
    if not isinstance(inner, dict):
        raise GoogleAuthValidationError(
            f"client JSON at {path} has a non-object 'installed' wrapper",
            context={"path": str(path)},
        )
    # Cloud Console writes redirect_uris as a JSON array; strict pydantic
    # rejects list-vs-tuple coercion, so normalise before validation.
    coerced = dict(inner)
    if isinstance(coerced.get("redirect_uris"), list):
        coerced["redirect_uris"] = tuple(coerced["redirect_uris"])
    try:
        return OAuthClient.model_validate(coerced)
    except ValidationError as exc:
        raise GoogleAuthValidationError(
            f"client JSON at {path} failed schema validation: {exc.errors(include_url=False)}",
            context={"path": str(path)},
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
    profile: str | None = typer.Option(None, "--profile", help=tr("cli.config.google.profile_help")),
) -> None:
    """Register a Cloud Console Desktop OAuth client for the active profile."""

    try:
        active = resolve_active_profile(profile)
        client = _coerce_client_json(client_json)
        save_client(active, client)
    except GoogleAuthError as exc:
        raise CliRefusedBoundaryError(str(exc)) from exc

    payload = {
        "operation": "config.google.register",
        "profile": active,
        "client_id": client.client_id,
        "project_id": client.project_id,
    }
    _emit(
        ctx,
        payload,
        (
            "operation\tconfig.google.register",
            f"profile\t{active}",
            f"client_id\t{client.client_id}",
            f"project_id\t{client.project_id}",
        ),
    )


@google_app.command("login", help=tr("cli.config.google.login_help"))
def google_login(
    ctx: typer.Context,
    profile: str | None = typer.Option(None, "--profile", help=tr("cli.config.google.profile_help")),
    refresh_only: bool = typer.Option(
        False,
        "--refresh-only",
        help=tr("cli.config.google.refresh_only_help"),
    ),
) -> None:
    """Run the loopback IP + PKCE consent flow (or refresh an existing credential)."""

    try:
        active = resolve_active_profile(profile)
        client = load_client(active)
        if client is None:
            raise GoogleAuthClientNotRegisteredError(
                f"no OAuth client registered for profile {active!r}",
                context={"profile": active},
                suggestion="aeat config google register --client-json <path>",
            )
        if refresh_only:
            metadata = load_metadata(active)
            if metadata is None:
                raise GoogleAuthExpiredError(
                    f"no OAuth metadata for profile {active!r}; cannot refresh without a prior login",
                    context={"profile": active},
                    suggestion="aeat config google login",
                )
            payload = {
                "operation": "config.google.login",
                "profile": active,
                "mode": "refresh-only",
                "account_email": metadata.account_email,
            }
            _emit(
                ctx,
                payload,
                (
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
        raise CliRefusedBoundaryError(str(exc)) from exc

    payload = {
        "operation": "config.google.login",
        "profile": active,
        "mode": "consent",
        "account_email": metadata.account_email,
        "granted_scopes": list(metadata.granted_scopes),
    }
    _emit(
        ctx,
        payload,
        (
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
    profile: str | None = typer.Option(None, "--profile", help=tr("cli.config.google.profile_help")),
) -> None:
    """Report the current Google OAuth session state for the active profile."""

    try:
        active = resolve_active_profile(profile)
    except GoogleAuthError as exc:
        raise CliRefusedBoundaryError(str(exc)) from exc

    client = load_client(active)
    metadata = load_metadata(active)
    payload: dict[str, object] = {
        "operation": "config.google.status",
        "profile": active,
        "client_registered": client is not None,
        "client_id": client.client_id if client is not None else None,
        "session_present": metadata is not None,
        "account_email": metadata.account_email if metadata is not None else None,
        "granted_scopes": list(metadata.granted_scopes) if metadata is not None else [],
        "issued_at": metadata.issued_at.isoformat() if metadata is not None else None,
        "last_refresh_at": metadata.last_refresh_at.isoformat() if metadata is not None else None,
        "reauth_required": metadata.reauth_required if metadata is not None else None,
    }
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
            )
        )
    _emit(ctx, payload, tuple(lines))


@google_app.command("logout", help=tr("cli.config.google.logout_help"))
def google_logout(
    ctx: typer.Context,
    profile: str | None = typer.Option(None, "--profile", help=tr("cli.config.google.profile_help")),
) -> None:
    """Clear the refresh token + metadata for the active profile.

    The registered OAuth client is intentionally preserved: a
    subsequent `aeat config google login` can re-acquire a session
    without the operator re-importing the Cloud Console JSON.
    """

    try:
        active = resolve_active_profile(profile)
    except GoogleAuthError as exc:
        raise CliRefusedBoundaryError(str(exc)) from exc

    token_removed, metadata_removed = delete_session(active)
    payload = {
        "operation": "config.google.logout",
        "profile": active,
        "token_removed": token_removed,
        "metadata_removed": metadata_removed,
        "client_preserved": True,
    }
    _emit(
        ctx,
        payload,
        (
            "operation\tconfig.google.logout",
            f"profile\t{active}",
            f"token_removed\t{token_removed}",
            f"metadata_removed\t{metadata_removed}",
            "client_preserved\tTrue",
        ),
    )


folder_app = typer.Typer(
    name="folder",
    help=tr("cli.config.google.folder.help"),
    no_args_is_help=True,
)


@folder_app.command("set", help=tr("cli.config.google.folder.set_help"))
def google_folder_set(
    ctx: typer.Context,
    folder_id: str = typer.Argument(..., help=tr("cli.config.google.folder.folder_id_help")),
    profile: str | None = typer.Option(None, "--profile", help=tr("cli.config.google.profile_help")),
) -> None:
    """Persist the Drive root folder id under the active profile."""

    try:
        active = resolve_active_profile(profile)
    except GoogleAuthError as exc:
        raise CliRefusedBoundaryError(str(exc)) from exc

    config = DriveConfig(root_folder_id=folder_id.strip())
    save_drive_config(active, config)
    payload = {
        "operation": "config.google.folder.set",
        "profile": active,
        "root_folder_id": config.root_folder_id,
    }
    _emit(
        ctx,
        payload,
        (
            "operation\tconfig.google.folder.set",
            f"profile\t{active}",
            f"root_folder_id\t{config.root_folder_id}",
        ),
    )


@folder_app.command("get", help=tr("cli.config.google.folder.get_help"))
def google_folder_get(
    ctx: typer.Context,
    profile: str | None = typer.Option(None, "--profile", help=tr("cli.config.google.profile_help")),
) -> None:
    """Show the persisted Drive root folder id for the active profile."""

    try:
        active = resolve_active_profile(profile)
    except GoogleAuthError as exc:
        raise CliRefusedBoundaryError(str(exc)) from exc

    config = load_drive_config(active)
    payload = {
        "operation": "config.google.folder.get",
        "profile": active,
        "configured": config is not None,
        "root_folder_id": config.root_folder_id if config is not None else None,
    }
    _emit(
        ctx,
        payload,
        (
            "operation\tconfig.google.folder.get",
            f"profile\t{active}",
            f"configured\t{config is not None}",
            f"root_folder_id\t{config.root_folder_id if config is not None else '<unset>'}",
        ),
    )


google_app.add_typer(folder_app, name="folder")


sync_app = typer.Typer(
    name="sync",
    help=tr("cli.config.google.sync.help"),
    no_args_is_help=True,
)


@sync_app.command("probe", help=tr("cli.config.google.sync.probe_help"))
def google_sync_probe(
    ctx: typer.Context,
    profile: str | None = typer.Option(None, "--profile", help=tr("cli.config.google.profile_help")),
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
        active = resolve_active_profile(profile)
    except GoogleAuthError as exc:
        raise CliRefusedBoundaryError(str(exc)) from exc

    settings = load_settings()
    # The factory uses Settings.aeat_storage_provider_kind to pick the
    # backend. For the operator-driven probe we override to Google Drive
    # explicitly so the probe always exercises the Drive path regardless
    # of how the operator's environment is configured. The folder id
    # itself is resolved by the factory via the canonical precedence
    # (env var > persisted DriveConfig record); no separate gate here.
    drive_settings = settings.model_copy(update={"aeat_storage_provider_kind": "google_drive"})

    try:
        provider = get_storage_provider(profile_override=active, settings=drive_settings)
        report = provider.probe(read_only=read_only)
    except (GoogleAuthError, StorageError) as exc:
        raise CliRefusedBoundaryError(str(exc)) from exc

    # Pull the actual root folder id from the provider — the env var
    # OR the persisted DriveConfig may have supplied it; the provider
    # is the single resolved source of truth.
    resolved_root_folder_id = getattr(provider, "root_folder_id", "")
    payload = {
        "operation": "config.google.sync.probe",
        "profile": active,
        "provider_kind": report.provider_kind.value,
        "reachable": report.reachable,
        "writable": report.writable,
        "read_only": report.read_only,
        "root_folder_present": report.root_folder_present,
        "root_folder_id": resolved_root_folder_id,
        "detail": report.detail,
    }
    _emit(
        ctx,
        payload,
        (
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

    hasher = hashlib.sha256()
    hasher.update(namespace.encode("utf-8"))
    hasher.update(b"\x00")
    hasher.update(object_key)
    return hasher.hexdigest()


def _label_for(namespace: str) -> str:
    """Pick a Drive-filename label from `namespace`.

    Default policy: trailing dotted segment, capped at 32 chars,
    sanitised to alnum/dash/underscore. Per-namespace registered
    label-derivers (per P03.S04-S06 + P06.S14-S24) override this
    default once they ship.
    """

    leaf = namespace.rsplit(".", 1)[-1] or "obj"
    safe = "".join(c if c.isalnum() or c in "-_." else "-" for c in leaf)
    return safe[:32] or "obj"


@sync_app.command("push", help=tr("cli.config.google.sync.push_help"))
def google_sync_push(
    ctx: typer.Context,
    profile: str | None = typer.Option(None, "--profile", help=tr("cli.config.google.profile_help")),
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
    """Mirror every SecureObjectRepository row's on-wire ciphertext to Drive.

    Walks `SecureObjectRepository.iter_all_records_raw()` ordered by
    `(namespace, object_key)`. Each row's ciphertext payload uploads
    via `GoogleDriveProvider.put(...)` under the namespace's Drive
    folder, named `<hmac_prefix_8>--<label>.bin`. The local master
    key never leaves the host — only ciphertext reaches Drive per
    ADR-3's ciphertext-layer mirror.
    """

    try:
        active = resolve_active_profile(profile)
    except GoogleAuthError as exc:
        raise CliRefusedBoundaryError(str(exc)) from exc

    settings = load_settings()
    drive_settings = settings.model_copy(update={"aeat_storage_provider_kind": "google_drive"})

    try:
        provider = get_storage_provider(profile_override=active, settings=drive_settings)
    except (GoogleAuthError, StorageError) as exc:
        raise CliRefusedBoundaryError(str(exc)) from exc

    repository = SecureObjectRepository()
    pushed_by_ns: dict[str, int] = {}
    skipped_by_ns: dict[str, int] = {}
    failed: list[tuple[str, str, str]] = []
    total_seen = 0

    for raw_row in repository.iter_all_records_raw():
        if namespace_filter is not None and raw_row.namespace != namespace_filter:
            continue
        total_seen += 1
        if limit is not None and total_seen > limit:
            break
        hmac_hex = _object_key_hmac(raw_row.namespace, raw_row.object_key)
        label = _label_for(raw_row.namespace)
        content_hash = f"sha256-{hashlib.sha256(raw_row.payload).hexdigest()}"
        if dry_run:
            skipped_by_ns[raw_row.namespace] = skipped_by_ns.get(raw_row.namespace, 0) + 1
            continue
        try:
            provider.put(
                raw_row.namespace,
                hmac_hex,
                raw_row.payload,
                content_hash=content_hash,
                label=label,
            )
        except StorageError as exc:
            failed.append((raw_row.namespace, hmac_hex, str(exc)))
            continue
        pushed_by_ns[raw_row.namespace] = pushed_by_ns.get(raw_row.namespace, 0) + 1

    payload: dict[str, object] = {
        "operation": "config.google.sync.push",
        "profile": active,
        "root_folder_id": resolved_root_folder_id,
        "dry_run": dry_run,
        "namespace_filter": namespace_filter,
        "limit": limit,
        "pushed_total": sum(pushed_by_ns.values()),
        "skipped_total": sum(skipped_by_ns.values()),
        "failed_total": len(failed),
        "pushed_by_namespace": pushed_by_ns,
        "skipped_by_namespace": skipped_by_ns,
        "failed_objects": [
            {"namespace": ns, "hmac": h, "error": err}
            for ns, h, err in failed
        ],
    }
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
    ]
    for ns in sorted(set(pushed_by_ns) | set(skipped_by_ns)):
        pushed = pushed_by_ns.get(ns, 0)
        skipped = skipped_by_ns.get(ns, 0)
        lines.append(f"namespace\t{ns}\tpushed={pushed}\tskipped={skipped}")
    for ns, h, err in failed:
        lines.append(f"failed\t{ns}\t{h[:16]}\t{err}")
    _emit(ctx, payload, tuple(lines))


google_app.add_typer(sync_app, name="sync")


# Suppress unused-import false positive for `load_token` and `REQUIRED_SCOPES`;
# both are part of the public surface the sync sub-commands consume.
_ = (load_token, REQUIRED_SCOPES)


__all__ = ["google_app"]
