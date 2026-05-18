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
from ....adapters.outbound.google._calc_sheets_apply import (
    CalcSheetsApplyResult,
    apply_export_plan,
)
from ....adapters.outbound.google._oauth_flow import run_login_flow
from ....adapters.outbound.google._profile_binding import resolve_active_profile
from ....adapters.outbound.google._records import REQUIRED_SCOPES, DriveConfig
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
from ....adapters.outbound.storage._factory import (
    _build_google_credentials,
    _resolve_drive_root_folder_id,
)
from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....application.storage.calc_sheets import (
    OperatorInputs,
    RelationValues,
    build_export_plan,
)
from ....core.config import load_settings
from ....core.resources import bundled_path
from ....domain.calculations.registry._errors import (
    RegistrySnapshotError,
    RegistryValidationError,
)
from ....domain.calculations.registry._loader import load_registry_tree
from ....domain.calculations.registry._snapshot import build_snapshot
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
            f'client JSON at {path} is not a Cloud Console Desktop client; expected an "installed" wrapper key',
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
) -> None:
    """Register a Cloud Console Desktop OAuth client for the active profile."""

    try:
        active = resolve_active_profile()
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
) -> None:
    """Report the current Google OAuth session state for the active profile."""

    try:
        active = resolve_active_profile()
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
) -> None:
    """Clear the refresh token + metadata for the active profile.

    The registered OAuth client is intentionally preserved: a
    subsequent `aeat config google login` can re-acquire a session
    without the operator re-importing the Cloud Console JSON.
    """

    try:
        active = resolve_active_profile()
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
) -> None:
    """Persist the Drive root folder id under the active profile."""

    try:
        active = resolve_active_profile()
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
) -> None:
    """Show the persisted Drive root folder id for the active profile."""

    try:
        active = resolve_active_profile()
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
        provider = get_storage_provider(settings=drive_settings)
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
    label-derivers override this default once they ship.
    """

    leaf = namespace.rsplit(".", 1)[-1] or "obj"
    safe = "".join(c if c.isalnum() or c in "-_." else "-" for c in leaf)
    return safe[:32] or "obj"


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
    """Mirror every SecureObjectRepository row's on-wire ciphertext to Drive.

    Walks `SecureObjectRepository.iter_all_records_raw()` ordered by
    `(namespace, object_key)`. Each row's ciphertext payload uploads
    via `GoogleDriveProvider.put(...)` under the namespace's Drive
    folder, named `<hmac_prefix_8>--<label>.bin`. The local master
    key never leaves the host — only ciphertext reaches Drive.
    """

    try:
        active = resolve_active_profile()
    except GoogleAuthError as exc:
        raise CliRefusedBoundaryError(str(exc)) from exc

    settings = load_settings()
    drive_settings = settings.model_copy(update={"aeat_storage_provider_kind": "google_drive"})

    try:
        provider = get_storage_provider(settings=drive_settings)
    except (GoogleAuthError, StorageError) as exc:
        raise CliRefusedBoundaryError(str(exc)) from exc

    resolved_root_folder_id = getattr(provider, "root_folder_id", "")

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
        "failed_objects": [{"namespace": ns, "hmac": h, "error": err} for ns, h, err in failed],
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


calc_app = typer.Typer(
    name="calc",
    help=tr("cli.config.google.sync.calc.help"),
    no_args_is_help=True,
)


def _resolve_credentials_and_root(profile: str) -> tuple[object, str]:
    """Hydrate refreshable Google credentials + the configured Drive root."""

    settings = load_settings()
    credentials = _build_google_credentials(profile=profile)
    root_folder_id = _resolve_drive_root_folder_id(profile=profile, settings=settings)
    if not root_folder_id:
        raise CliRefusedBoundaryError(
            tr("cli.config.google.sync.calc.export.root_folder_required"),
        )
    return credentials, root_folder_id


def _load_snapshot(modelo: str, period: str, year: int):
    modelos, catalogues = load_registry_tree(bundled_path("registry", "aeat"))
    chosen = next((candidate for candidate in modelos if candidate.id == modelo), None)
    if chosen is None:
        available = ", ".join(sorted(candidate.id for candidate in modelos))
        raise CliRefusedBoundaryError(
            tr(
                "cli.config.google.sync.calc.export.unknown_modelo",
                modelo=modelo,
                available=available,
            ),
        )
    try:
        return build_snapshot(
            chosen,
            catalogues,
            source_root=bundled_path(),
            filing_year=year,
            period=period,
        )
    except (RegistrySnapshotError, RegistryValidationError) as exc:
        raise CliRefusedBoundaryError(
            tr(
                "cli.config.google.sync.calc.export.snapshot_failure",
                modelo=modelo,
                period=period,
                year=year,
                detail=str(exc),
                default=(
                    "Cannot build registry snapshot for modelo "
                    f"{modelo} ({period} {year}): {exc}"
                ),
            ),
        ) from exc


@calc_app.command("export", help=tr("cli.config.google.sync.calc.export_help"))
def google_sync_calc_export(
    ctx: typer.Context,
    modelo: str = typer.Option(..., "--modelo", help=tr("cli.config.google.sync.calc.export.modelo_help")),
    period: str = typer.Option(..., "--period", help=tr("cli.config.google.sync.calc.export.period_help")),
    year: int = typer.Option(
        ..., "--year", help=tr("cli.config.google.sync.calc.export.year_help"), min=2000, max=2099
    ),
    prefill_relations: bool = typer.Option(
        False,
        "--prefill-relations/--no-prefill-relations",
        help=tr("cli.config.google.sync.calc.export.prefill_relations_help"),
    ),
) -> None:
    """Export the registry calculation surface for a modelo + period to a real
    Google Sheets workbook under the operator's `aeat-vault/`.

    Materialises Entradas (operator inputs), Cálculos (formula cells with
    per-casilla ROUND-wrapped Decimal parity), Procedencia (audit trail),
    Tarifas (parameter + relation mirrors), and Guía (engine version +
    registry SHA stamps the pull adapter validates against).

    When `--prefill-relations` is set, the engine consults the local
    `CalculationObservationRepository` for prior filings of the
    relations' source modelos, pre-resolves the relation values via
    `resolve_relations_from_local_store`, and stamps each prefilled
    Tarifas cell with provenance metadata (source modelo + filing year
    + periods + resolution timestamp). Without prior filings in the
    local store the flag is a no-op and the workbook ships with blank
    relation cells the operator fills by hand.
    """

    from ....application.calculations import resolve_relations_from_local_store

    try:
        active = resolve_active_profile()
    except GoogleAuthError as exc:
        raise CliRefusedBoundaryError(str(exc)) from exc

    try:
        credentials, root_folder_id = _resolve_credentials_and_root(active)
    except (GoogleAuthError, StorageError) as exc:
        raise CliRefusedBoundaryError(str(exc)) from exc

    snapshot = _load_snapshot(modelo, period, year)
    if prefill_relations:
        plan = build_export_plan(
            snapshot,
            operator_inputs=OperatorInputs(),
            relation_resolver=resolve_relations_from_local_store,
        )
    else:
        plan = build_export_plan(
            snapshot,
            operator_inputs=OperatorInputs(),
            relation_values=RelationValues(),
        )

    try:
        result: CalcSheetsApplyResult = apply_export_plan(
            plan,
            credentials=credentials,
            root_folder_id=root_folder_id,
        )
    except (GoogleAuthError, StorageError) as exc:
        raise CliRefusedBoundaryError(str(exc)) from exc

    payload = {
        "operation": "config.google.sync.calc.export",
        "profile": active,
        "modelo": snapshot.modelo.id,
        "revision": snapshot.revision.id,
        "period": snapshot.period,
        "year": snapshot.filing_year,
        "engine_version": plan.metadata.engine_version,
        "registry_sha": plan.metadata.registry_sha,
        "root_folder_id": root_folder_id,
        "folder_id": result.folder_id,
        "spreadsheet_id": result.spreadsheet_id,
        "spreadsheet_url": result.spreadsheet_url,
        "value_cells_written": result.value_cells_written,
        "formula_cells_written": result.formula_cells_written,
        "protected_ranges_written": result.protected_ranges_written,
        "tab_count": result.tab_count,
    }
    _emit(
        ctx,
        payload,
        (
            "operation\tconfig.google.sync.calc.export",
            f"profile\t{active}",
            f"modelo\t{snapshot.modelo.id}",
            f"revision\t{snapshot.revision.id}",
            f"period\t{snapshot.period}",
            f"year\t{snapshot.filing_year}",
            f"engine_version\t{plan.metadata.engine_version}",
            f"registry_sha\t{plan.metadata.registry_sha}",
            f"folder_id\t{result.folder_id}",
            f"spreadsheet_id\t{result.spreadsheet_id}",
            f"spreadsheet_url\t{result.spreadsheet_url}",
            f"value_cells_written\t{result.value_cells_written}",
            f"formula_cells_written\t{result.formula_cells_written}",
            f"protected_ranges_written\t{result.protected_ranges_written}",
            f"tab_count\t{result.tab_count}",
        ),
    )


@calc_app.command("verify", help=tr("cli.config.google.sync.calc.verify_help"))
def google_sync_calc_verify(
    ctx: typer.Context,
    modelo: str = typer.Option(..., "--modelo", help=tr("cli.config.google.sync.calc.export.modelo_help")),
    period: str = typer.Option(..., "--period", help=tr("cli.config.google.sync.calc.export.period_help")),
    year: int = typer.Option(
        ..., "--year", help=tr("cli.config.google.sync.calc.export.year_help"), min=2000, max=2099
    ),
    scenario_path: Path | None = typer.Option(
        None,
        "--scenario",
        help=tr("cli.config.google.sync.calc.verify.scenario_help"),
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
    ),
) -> None:
    """Run a three-way parity check (AEAT oracle, local Decimal runtime, Sheets).

    The scenario file is a JSON document carrying operator inputs,
    bindings, relations, and an optional AEAT-published expected
    output map. When omitted every casilla is taken as zero and only
    backend↔Sheets parity is checked; verdict surfaces as
    `inconclusive` in that case.
    """

    from decimal import Decimal

    from ....application.storage.calc_sheets._parity_harness import (
        OperatorInputScenario,
        verify_modelo_parity,
    )

    try:
        active = resolve_active_profile()
    except GoogleAuthError as exc:
        raise CliRefusedBoundaryError(str(exc)) from exc

    try:
        credentials, root_folder_id = _resolve_credentials_and_root(active)
    except (GoogleAuthError, StorageError) as exc:
        raise CliRefusedBoundaryError(str(exc)) from exc

    snapshot = _load_snapshot(modelo, period, year)

    if scenario_path is None:
        scenario = OperatorInputScenario(scenario_label="empty-defaults")
    else:
        raw = json.loads(scenario_path.read_text(encoding="utf-8"))

        def _to_decimal_map(node: object) -> dict[str, Decimal]:
            if not isinstance(node, dict):
                return {}
            return {str(k): Decimal(str(v)) for k, v in node.items()}

        scenario = OperatorInputScenario(
            inputs_by_number=_to_decimal_map(raw.get("inputs_by_number")),
            bindings=_to_decimal_map(raw.get("bindings")),
            enum_bindings={str(k): str(v) for k, v in (raw.get("enum_bindings") or {}).items()},
            relation_values=_to_decimal_map(raw.get("relation_values")),
            expected_by_number=_to_decimal_map(raw.get("expected_by_number")),
            scenario_label=str(raw.get("scenario_label") or scenario_path.stem),
        )

    report = verify_modelo_parity(snapshot, scenario, credentials=credentials, root_folder_id=root_folder_id)

    payload: dict[str, object] = {
        "operation": "config.google.sync.calc.verify",
        "profile": active,
        "modelo": report.modelo_id,
        "revision": report.revision_id,
        "period": report.period,
        "year": report.filing_year,
        "spreadsheet_id": report.spreadsheet_id,
        "spreadsheet_url": report.spreadsheet_url,
        "verdict": report.verdict,
        "aeat_oracle_present": report.aeat_oracle_present,
        "computed_count": len(report.casillas),
        "divergence_count": len(report.divergences),
        "divergences": [
            {
                "casilla": c.casilla_number,
                "label": c.label,
                "local": str(c.local) if c.local is not None else None,
                "sheets": str(c.sheets) if c.sheets is not None else None,
                "aeat": str(c.aeat) if c.aeat is not None else None,
            }
            for c in report.divergences
        ],
    }
    lines: list[str] = [
        "operation\tconfig.google.sync.calc.verify",
        f"profile\t{active}",
        f"modelo\t{report.modelo_id}",
        f"revision\t{report.revision_id}",
        f"period\t{report.period}",
        f"year\t{report.filing_year}",
        f"spreadsheet_url\t{report.spreadsheet_url}",
        f"verdict\t{report.verdict}",
        f"aeat_oracle_present\t{report.aeat_oracle_present}",
        f"computed_count\t{len(report.casillas)}",
        f"divergence_count\t{len(report.divergences)}",
    ]
    for div in report.divergences:
        lines.append(f"divergence\t{div.casilla_number}\tlocal={div.local}\tsheets={div.sheets}\taeat={div.aeat}")
    _emit(ctx, payload, tuple(lines))


@calc_app.command("pull", help=tr("cli.config.google.sync.calc.pull_help"))
def google_sync_calc_pull(
    ctx: typer.Context,
    modelo: str = typer.Option(..., "--modelo", help=tr("cli.config.google.sync.calc.export.modelo_help")),
    period: str = typer.Option(..., "--period", help=tr("cli.config.google.sync.calc.export.period_help")),
    year: int = typer.Option(
        ..., "--year", help=tr("cli.config.google.sync.calc.export.year_help"), min=2000, max=2099
    ),
    spreadsheet_id: str = typer.Option(
        ...,
        "--spreadsheet-id",
        help=tr("cli.config.google.sync.calc.pull.spreadsheet_id_help"),
        min=1,
    ),
    compute: bool = typer.Option(
        False,
        "--compute/--no-compute",
        help=tr("cli.config.google.sync.calc.pull.compute_help"),
    ),
    assemble_observations: bool = typer.Option(
        False,
        "--assemble-observations/--no-assemble-observations",
        help=tr("cli.config.google.sync.calc.pull.assemble_observations_help"),
    ),
) -> None:
    """Read operator-edited cells back from a workbook into typed records.

    The workbook's developer-metadata stamps must match the supplied
    snapshot's `(modelo, revision, period, year)` quadruple. A
    `metadata_match=stale` result returns the edits but signals that
    the workbook was compiled against a different registry slice;
    callers should refuse to apply stale edits to the local store.
    """

    from ....adapters.outbound.google._calc_sheets_pull import (
        PullResult,
        compute_from_pull,
        pull_operator_edits,
    )

    try:
        active = resolve_active_profile()
    except GoogleAuthError as exc:
        raise CliRefusedBoundaryError(str(exc)) from exc

    try:
        credentials, _ = _resolve_credentials_and_root(active)
    except (GoogleAuthError, StorageError) as exc:
        raise CliRefusedBoundaryError(str(exc)) from exc

    snapshot = _load_snapshot(modelo, period, year)

    try:
        result: PullResult = pull_operator_edits(
            snapshot,
            spreadsheet_id=spreadsheet_id,
            credentials=credentials,
        )
    except (GoogleAuthError, StorageError) as exc:
        raise CliRefusedBoundaryError(str(exc)) from exc

    populated_operator = [e for e in result.operator_edits if e.value is not None]
    populated_bindings = [e for e in result.binding_edits if e.value is not None]
    populated_relations = [e for e in result.relation_edits if e.value is not None]
    populated_row_sets = [rs for rs in result.row_set_edits if rs.cells]
    row_set_cells_total = sum(len(rs.cells) for rs in populated_row_sets)

    assembled_groupings, assembled_observation_count = _assemble_pull_observations(
        populated_row_sets=populated_row_sets,
        snapshot=snapshot,
        enabled=assemble_observations,
    )

    computed_casillas = _compute_pull_casillas(
        snapshot=snapshot,
        result=result,
        enabled=compute,
        compute_from_pull=compute_from_pull,
    )

    payload: dict[str, object] = {
        "operation": "config.google.sync.calc.pull",
        "profile": active,
        "modelo": snapshot.modelo.id,
        "revision": snapshot.revision.id,
        "period": snapshot.period,
        "year": snapshot.filing_year,
        "spreadsheet_id": result.spreadsheet_id,
        "metadata_match": result.metadata_match,
        "metadata": {
            "modelo_id": result.metadata.modelo_id,
            "revision_id": result.metadata.revision_id,
            "filing_year": result.metadata.filing_year,
            "period": result.metadata.period,
            "engine_version": result.metadata.engine_version,
            "registry_sha": result.metadata.registry_sha,
            "exported_at": result.metadata.exported_at,
        },
        "cells_read": result.cells_read,
        "operator_edits_total": len(result.operator_edits),
        "operator_edits_populated": len(populated_operator),
        "binding_edits_populated": len(populated_bindings),
        "relation_edits_populated": len(populated_relations),
        "operator_edits": [
            {
                "casilla": e.casilla_number,
                "label": e.label,
                "value": str(e.value) if e.value is not None else None,
            }
            for e in populated_operator
        ],
        "binding_edits": [
            {"binding": e.binding, "value": str(e.value) if e.value is not None else None} for e in populated_bindings
        ],
        "relation_edits": [
            {"relation": e.relation, "value": str(e.value) if e.value is not None else None}
            for e in populated_relations
        ],
        "row_set_edits_populated": len(populated_row_sets),
        "row_set_cells_populated": row_set_cells_total,
        "assembled_groupings": assembled_groupings,
        "assembled_observation_count": assembled_observation_count,
        "row_set_edits": [
            {
                "grouping": rs.grouping,
                "cells": [
                    {
                        "binding": c.binding,
                        "row_index": c.row_index,
                        "value": str(c.value) if c.value is not None else None,
                    }
                    for c in rs.cells
                ],
            }
            for rs in populated_row_sets
        ],
        "computed": computed_casillas,
    }
    lines: list[str] = [
        "operation\tconfig.google.sync.calc.pull",
        f"profile\t{active}",
        f"modelo\t{snapshot.modelo.id}",
        f"revision\t{snapshot.revision.id}",
        f"period\t{snapshot.period}",
        f"year\t{snapshot.filing_year}",
        f"spreadsheet_id\t{result.spreadsheet_id}",
        f"metadata_match\t{result.metadata_match}",
        f"metadata.modelo_id\t{result.metadata.modelo_id}",
        f"metadata.revision_id\t{result.metadata.revision_id}",
        f"metadata.registry_sha\t{result.metadata.registry_sha}",
        f"cells_read\t{result.cells_read}",
        f"operator_edits_populated\t{len(populated_operator)}",
        f"binding_edits_populated\t{len(populated_bindings)}",
        f"relation_edits_populated\t{len(populated_relations)}",
        f"row_set_edits_populated\t{len(populated_row_sets)}",
        f"row_set_cells_populated\t{row_set_cells_total}",
    ]
    for e in populated_operator:
        lines.append(f"casilla\t{e.casilla_number}\t{e.value}\t{e.label}")
    for e in populated_bindings:
        lines.append(f"binding\t{e.binding}\t{e.value}")
    for e in populated_relations:
        lines.append(f"relation\t{e.relation}\t{e.value}")
    for rs in populated_row_sets:
        for c in rs.cells:
            lines.append(f"row_set\t{rs.grouping}\t{c.row_index}\t{c.binding}\t{c.value}")
    for assembled in assembled_groupings:
        lines.append(
            f"assembled\t{assembled['grouping']}\t{assembled['source_kind']}\t{assembled['observation_count']}"
        )
    for entry in computed_casillas:
        lines.append(f"computed\t{entry['casilla_id']}\t{entry['value']}\t{entry['formula_id']}")
    _emit(ctx, payload, tuple(lines))


def _assemble_pull_observations(
    *,
    populated_row_sets: list,  # type: ignore[type-arg]
    snapshot,  # type: ignore[no-untyped-def]
    enabled: bool,
) -> tuple[list[dict[str, object]], int]:
    """Per-grouping assemble-observations fan-out for the pull command.

    Returns ``(groupings, total_observation_count)``. When ``enabled``
    is false (assemble-observations flag not passed), returns
    ``([], 0)``. Storage errors raised by the application service are
    re-wrapped as :class:`CliRefusedBoundaryError` so the CLI emits a
    typed error envelope.
    """
    if not enabled:
        return [], 0
    from ....application.calculations import assemble_observations_for_grouping

    groupings: list[dict[str, object]] = []
    total = 0
    for row_set in populated_row_sets:
        try:
            source_kind, observations = assemble_observations_for_grouping(
                row_set.grouping,
                row_set.cells,
                snapshot.revision,
                filing_year=snapshot.filing_year,
            )
        except StorageError as exc:
            raise CliRefusedBoundaryError(str(exc)) from exc
        total += len(observations)
        groupings.append(
            {
                "grouping": row_set.grouping,
                "source_kind": source_kind,
                "observation_count": len(observations),
                "observations": [obs.model_dump(mode="json") for obs in observations],
            }
        )
    return groupings, total


def _compute_pull_casillas(
    *,
    snapshot,  # type: ignore[no-untyped-def]
    result,  # type: ignore[no-untyped-def]
    enabled: bool,
    compute_from_pull,  # type: ignore[no-untyped-def]
) -> list[dict[str, str]]:
    """Compute casillas from the pulled edits, refusing stale workbook stamps.

    When ``enabled`` is false (compute flag not passed), returns an
    empty list. A pull whose ``metadata_match`` is anything other
    than ``"matches"`` raises :class:`CliRefusedBoundaryError` —
    computing against a stale workbook would silently apply edits
    against a different registry slice.
    """
    if not enabled:
        return []
    if result.metadata_match != "matches":
        raise CliRefusedBoundaryError(
            tr(
                "cli.config.google.sync.calc.pull.compute_refused_stale",
                metadata_match=result.metadata_match,
            ),
        )
    try:
        calc = compute_from_pull(snapshot, result)
    except StorageError as exc:
        raise CliRefusedBoundaryError(str(exc)) from exc
    return [
        {
            "casilla_id": entry.target,
            "value": str(entry.value),
            "formula_id": entry.formula_id,
        }
        for entry in calc.entries
    ]


sync_app.add_typer(calc_app, name="calc")
google_app.add_typer(sync_app, name="sync")


# Suppress unused-import false positive for `load_token` and `REQUIRED_SCOPES`;
# both are part of the public surface the sync sub-commands consume.
_ = (load_token, REQUIRED_SCOPES)


__all__ = ["google_app"]
