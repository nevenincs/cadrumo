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
    StorageError,
    get_storage_provider,
)
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
    # of how the operator's environment is configured.
    drive_settings = settings.model_copy(update={"aeat_storage_provider_kind": "google_drive"})
    if not drive_settings.aeat_google_drive_root_folder_id:
        raise CliRefusedBoundaryError(tr("cli.config.google.sync.root_folder_id_unset"))

    try:
        provider = get_storage_provider(profile_override=active, settings=drive_settings)
        report = provider.probe(read_only=read_only)
    except (GoogleAuthError, StorageError) as exc:
        raise CliRefusedBoundaryError(str(exc)) from exc

    payload = {
        "operation": "config.google.sync.probe",
        "profile": active,
        "provider_kind": report.provider_kind.value,
        "reachable": report.reachable,
        "writable": report.writable,
        "read_only": report.read_only,
        "root_folder_present": report.root_folder_present,
        "root_folder_id": drive_settings.aeat_google_drive_root_folder_id,
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
            f"root_folder_id\t{drive_settings.aeat_google_drive_root_folder_id}",
            f"detail\t{report.detail}",
        ),
    )


google_app.add_typer(sync_app, name="sync")


# Suppress unused-import false positive for `load_token` and `REQUIRED_SCOPES`;
# both are part of the public surface the sync sub-commands consume during
# their own command implementations (sync push / sync pull / sync calc export
# will land alongside P03 / P07 and import them through this same module).
_ = (load_token, REQUIRED_SCOPES)


__all__ = ["google_app"]
