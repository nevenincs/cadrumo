from __future__ import annotations

import asyncio
from pathlib import Path

import typer

from ...application.auth import (
    AUTH_PROVIDER_CATALOGUE,
    AuthProviderKind,
    AuthSessionUnavailableError,
    clear_auth_acquisition_lock,
    delete_persisted_session,
    ensure_authenticated_aeat_session,
    get_auth_provider,
    inspect_auth_acquisition_lock,
    require_verified_aeat_session,
)
from ...application.profile import list_profile_value_rows, validate_profile
from ...application.setup_status import build_setup_status
from ...application.user_cli import (
    clear_profile_values,
    set_active_profile,
    set_profile_values,
    state_repository,
    update_auth,
)
from ...core.config import Settings, load_settings
from ...domain.profile import (
    PROFILE_KEYS,
    get_profile_key,
)
from ._common import (
    _active_profile_or_exit,
    _bad,
    _description_for,
    _emit,
    _exit,
    _label_for,
    _state,
)
from ._i18n import tr

app = typer.Typer(
    name="setup",
    help=tr("cli.setup.app_help"),
    no_args_is_help=True,
)
auth_app = typer.Typer(
    name="auth",
    help=tr("cli.setup.auth.app_help"),
    no_args_is_help=True,
)
profile_app = typer.Typer(
    name="profile",
    help=tr("cli.setup.profile.app_help"),
    no_args_is_help=True,
)

app.add_typer(auth_app, name="auth")
app.add_typer(profile_app, name="profile")


@app.command("init", help=tr("cli.setup.init.help"))
def setup_init(
    ctx: typer.Context,
    name: str = typer.Option(..., "--name", help=tr("cli.setup.init.name_help")),
    activity: str | None = typer.Option(None, "--activity", help=tr("cli.setup.init.activity_help")),
    tax_id: str | None = typer.Option(None, "--tax-id", help=tr("cli.setup.init.tax_id_help")),
) -> None:
    """Create or activate a setup profile."""
    seeded: dict[str, str] = {}
    if tax_id:
        seeded["tax.id"] = tax_id
    if activity:
        seeded["activity"] = activity
    if seeded:
        updated = state_repository().update(lambda state: set_profile_values(state, name, seeded))
    else:
        updated = state_repository().update(lambda state: set_active_profile(state, name))
    record = updated.active_profile_record()
    payload = {
        "active_profile": updated.active_profile,
        "values": record.values if record is not None else {},
        "next": "aeat setup auth configure --provider certificate --file PATH",
    }
    _emit(
        ctx,
        payload,
        [
            f"{tr('cli.setup.headers.profile')}\t" + (updated.active_profile or ""),
            f"{tr('cli.setup.headers.next')}\taeat setup auth configure --provider certificate --file PATH",
        ],
    )


@app.command("status", help=tr("cli.setup.status.help"))
def setup_status(ctx: typer.Context) -> None:
    """Show profile, auth, and validation readiness."""
    report = build_setup_status(_state())
    payload = {
        "active_profile": report.active_profile,
        "profile_ready": report.profile_ready,
        "missing_required": list(report.missing_required),
        "profile_present_keys": report.profile_present_keys,
        "profile_total_keys": report.profile_total_keys,
        "auth_provider": report.auth_provider,
        "login_ready": report.login_ready,
        "next_action": report.next_action,
    }
    yes_label = tr("cli.setup.labels.yes")
    no_label = tr("cli.setup.labels.no")
    _emit(
        ctx,
        payload,
        [
            f"{tr('cli.setup.headers.profile')}\t{report.active_profile or ''}",
            f"{tr('cli.setup.headers.profile_ready')}\t{yes_label if report.profile_ready else no_label}",
            f"{tr('cli.setup.headers.missing')}\t{', '.join(report.missing_required) or '-'}",
            f"{tr('cli.setup.headers.completeness')}\t{report.profile_present_keys}/{report.profile_total_keys}",
            f"{tr('cli.setup.headers.auth_provider')}\t{report.auth_provider}",
            f"{tr('cli.setup.headers.login_ready')}\t{yes_label if report.login_ready else no_label}",
            f"{tr('cli.setup.headers.next')}\t{report.next_action}",
        ],
    )


# ---------------------------------------------------------------------
# `aeat setup auth` — auth-provider commands
# ---------------------------------------------------------------------


@auth_app.command("providers", help=tr("cli.setup.auth.providers.help"))
def auth_providers(ctx: typer.Context) -> None:
    """Render the provider catalogue."""
    payload = {
        "providers": [
            {
                "id": entry.id,
                "label": _label_for(entry),
                "description": _description_for(entry),
            }
            for entry in AUTH_PROVIDER_CATALOGUE
        ]
    }
    lines: list[str] = [f"{tr('cli.setup.headers.id')}\t{tr('cli.setup.headers.description')}"]
    lines.extend(f"{entry.id}\t{_description_for(entry)}" for entry in AUTH_PROVIDER_CATALOGUE)
    _emit(ctx, payload, lines)


@auth_app.command("configure", help=tr("cli.setup.auth.configure.help"))
def auth_configure(
    ctx: typer.Context,
    provider: str = typer.Option(..., "--provider", help=tr("cli.setup.auth.configure.provider_help")),
    file: Path | None = typer.Option(None, "--file", help=tr("cli.setup.auth.configure.file_help")),
) -> None:
    """Configure an AEAT auth provider via the application catalogue."""
    try:
        listing = get_auth_provider(provider.strip().lower())
    except KeyError as exc:
        raise _bad(tr("cli.setup.errors.unknown_provider").format(provider=provider)) from exc
    if listing.id == "certificate" and file is None:
        raise _bad(tr("cli.setup.errors.certificate_file_required"))
    if listing.id == "certificate" and file is not None and not file.exists():
        raise _bad(tr("cli.setup.errors.file_not_found").format(file=file))
    updated = state_repository().update(
        lambda state: update_auth(
            state,
            provider=listing.id,
            certificate_path=str(file.resolve()) if file is not None else None,
        )
    )
    payload = {"auth": updated.auth, "next": "aeat setup auth login"}
    _emit(
        ctx,
        payload,
        [
            f"{tr('cli.setup.headers.provider')}\t{updated.auth.provider}",
            f"{tr('cli.setup.headers.next')}\taeat setup auth login",
        ],
    )


@auth_app.command("login", help=tr("cli.setup.auth.login.help"))
def auth_login(
    ctx: typer.Context,
    fresh: bool = typer.Option(
        False,
        "--fresh",
        help="Clear the persisted provider session under the auth lock before authenticating.",
    ),
    reset_lock: bool = typer.Option(
        False,
        "--reset-lock",
        help=(
            "Remove an existing acquisition lock before authenticating; "
            "use only after confirming no auth process is running."
        ),
    ),
) -> None:
    """Authenticate with the configured AEAT provider and persist the verified session marker."""
    current = _state()
    if current.auth.provider is None:
        raise _bad(tr("cli.setup.errors.not_configured"))
    try:
        provider_kind = AuthProviderKind(current.auth.provider)
    except ValueError as exc:
        raise _bad(tr("cli.setup.errors.unknown_provider").format(provider=current.auth.provider)) from exc
    record = current.active_profile_record()
    profile_tax_id = record.values.get("tax.id") if record is not None else None
    if fresh:
        state_repository().update(lambda state: update_auth(state, authenticated=False, subject=""))
    result = asyncio.run(
        _authenticate_configured_provider(
            provider_kind,
            profile_tax_id=profile_tax_id,
            fresh=fresh,
            reset_lock=reset_lock,
        )
    )
    session = result.session
    assertion = result.assertion
    subject = session.identity_nif or profile_tax_id
    updated = state_repository().update(lambda state: update_auth(state, authenticated=True, subject=subject))
    payload = {"auth": updated.auth, "session": session, "assertion": assertion, "result": result}
    _emit(
        ctx,
        payload,
        [
            f"{tr('cli.setup.headers.provider')}\t{updated.auth.provider}",
            f"{tr('cli.setup.headers.subject')}\t{updated.auth.subject or ''}",
        ],
    )


@auth_app.command("status", help=tr("cli.setup.auth.status.help"))
def auth_status(ctx: typer.Context) -> None:
    current = _state()
    ready = False
    session = None
    error: str | None = None
    acquisition_lock = None
    if current.auth.provider is not None:
        try:
            provider_kind = AuthProviderKind(current.auth.provider)
            record = current.active_profile_record()
            profile_tax_id = record.values.get("tax.id") if record is not None else None
            settings = _settings_for_auth_provider(provider_kind, profile_tax_id=profile_tax_id)
            acquisition_lock = inspect_auth_acquisition_lock(settings, provider_kind)
            session = asyncio.run(require_verified_aeat_session(settings, kind=provider_kind))
            ready = True
            state_repository().update(
                lambda state: update_auth(state, authenticated=True, subject=session.identity_nif)
            )
        except (ValueError, AuthSessionUnavailableError) as exc:
            error = str(exc)
            state_repository().update(lambda state: update_auth(state, authenticated=False))
    current = _state()
    payload = {
        "auth": current.auth,
        "ready": ready,
        "session": session,
        "error": error,
        "acquisition_lock": acquisition_lock,
    }
    yes_no = tr("cli.setup.labels.yes") if ready else tr("cli.setup.labels.no")
    authenticated_at = current.auth.authenticated_at.isoformat() if current.auth.authenticated_at else ""
    lock_state = acquisition_lock.state.value if acquisition_lock is not None else ""
    _emit(
        ctx,
        payload,
        [
            f"{tr('cli.setup.headers.provider')}\t{current.auth.provider or ''}",
            f"{tr('cli.setup.headers.ready')}\t{yes_no}",
            f"{tr('cli.setup.headers.authenticated_at')}\t{authenticated_at}",
            f"auth_lock\t{lock_state}",
        ],
    )


@auth_app.command("reset", help=tr("cli.setup.auth.reset.help"))
def auth_reset(
    ctx: typer.Context,
    sessions: bool = typer.Option(False, "--sessions", help=tr("cli.setup.auth.reset.sessions_help")),
    locks: bool = typer.Option(False, "--locks", help=tr("cli.setup.auth.reset.locks_help")),
    all_: bool = typer.Option(False, "--all", help=tr("cli.setup.auth.reset.all_help")),
) -> None:
    """Manually clear local auth recovery state after a crash or broken login attempt."""

    current = _state()
    if current.auth.provider is None:
        raise _bad(tr("cli.setup.errors.not_configured"))
    try:
        provider_kind = AuthProviderKind(current.auth.provider)
    except ValueError as exc:
        raise _bad(tr("cli.setup.errors.unknown_provider").format(provider=current.auth.provider)) from exc
    reset_sessions = sessions or all_
    reset_locks = locks or all_
    if not reset_sessions and not reset_locks:
        raise _bad(tr("cli.setup.errors.reset_scope_required"))

    record = current.active_profile_record()
    profile_tax_id = record.values.get("tax.id") if record is not None else None
    settings = _settings_for_auth_provider(provider_kind, profile_tax_id=profile_tax_id)
    removed_sessions: list[Path] = []
    lock_status = None
    if reset_locks:
        lock_status = clear_auth_acquisition_lock(settings, provider_kind, reason="operator-reset-command")
    if reset_sessions:
        removed_sessions = delete_persisted_session(settings, kind=provider_kind)
        state_repository().update(lambda state: update_auth(state, authenticated=False, subject=""))

    updated = _state()
    payload = {
        "auth": updated.auth,
        "removed_sessions": removed_sessions,
        "reset_lock": lock_status,
    }
    lock_state = lock_status.state.value if lock_status is not None else "-"
    _emit(
        ctx,
        payload,
        [
            f"{tr('cli.setup.headers.provider')}\t{updated.auth.provider or ''}",
            f"removed_sessions\t{len(removed_sessions)}",
            f"auth_lock\t{lock_state}",
        ],
    )


@auth_app.command("whoami", help=tr("cli.setup.auth.whoami.help"))
def auth_whoami(ctx: typer.Context) -> None:
    current = _state()
    if current.auth.provider is None:
        raise _bad(tr("cli.setup.errors.not_configured"))
    try:
        provider_kind = AuthProviderKind(current.auth.provider)
    except ValueError as exc:
        raise _bad(tr("cli.setup.errors.unknown_provider").format(provider=current.auth.provider)) from exc
    record = current.active_profile_record()
    profile_tax_id = record.values.get("tax.id") if record is not None else None
    settings = _settings_for_auth_provider(provider_kind, profile_tax_id=profile_tax_id)
    session = asyncio.run(require_verified_aeat_session(settings, kind=provider_kind))
    updated = state_repository().update(
        lambda state: update_auth(state, authenticated=True, subject=session.identity_nif)
    )
    payload = {"provider": updated.auth.provider, "subject": updated.auth.subject, "session": session}
    _emit(
        ctx,
        payload,
        [
            f"{tr('cli.setup.headers.provider')}\t{updated.auth.provider or ''}",
            f"{tr('cli.setup.headers.subject')}\t{updated.auth.subject or ''}",
        ],
    )


@auth_app.command("logout", help=tr("cli.setup.auth.logout.help"))
def auth_logout(ctx: typer.Context) -> None:
    current = _state()
    removed: list[Path] = []
    if current.auth.provider is not None:
        try:
            provider_kind = AuthProviderKind(current.auth.provider)
            record = current.active_profile_record()
            profile_tax_id = record.values.get("tax.id") if record is not None else None
            settings = _settings_for_auth_provider(provider_kind, profile_tax_id=profile_tax_id)
            removed = delete_persisted_session(settings, kind=provider_kind)
        except ValueError:
            removed = []
    updated = state_repository().update(lambda state: update_auth(state, authenticated=False, subject=""))
    payload = {"auth": updated.auth, "removed_sessions": removed}
    _emit(
        ctx,
        payload,
        [f"{tr('cli.setup.headers.provider')}\t{updated.auth.provider or ''}", f"{tr('cli.setup.headers.logout')}\tok"],
    )


async def _authenticate_configured_provider(
    provider_kind: AuthProviderKind,
    *,
    profile_tax_id: str | None,
    fresh: bool = False,
    reset_lock: bool = False,
):
    """Ensure a verified AEAT session through the application auth API."""

    settings = _settings_for_auth_provider(provider_kind, profile_tax_id=profile_tax_id)
    return await ensure_authenticated_aeat_session(
        settings,
        kind=provider_kind,
        fresh=fresh,
        reset_lock=reset_lock,
        operation="setup-auth-login",
    )


def _settings_for_auth_provider(provider_kind: AuthProviderKind, *, profile_tax_id: str | None) -> Settings:
    """Return settings with CLI-owned auth defaults applied."""

    settings = load_settings()
    if provider_kind is not AuthProviderKind.CLAVE_MOVIL:
        return settings

    updates: dict[str, object] = {}
    if settings.aeat_clave_movil_dni_nie is None and profile_tax_id:
        updates["aeat_clave_movil_dni_nie"] = profile_tax_id

    return settings.model_copy(update=updates) if updates else settings


# ---------------------------------------------------------------------
# `aeat setup profile` — schema-backed editor
# ---------------------------------------------------------------------


@profile_app.command("use", help=tr("cli.setup.profile.use_help"))
def profile_use(
    ctx: typer.Context, name: str = typer.Argument(..., help=tr("cli.setup.profile.use_name_help"))
) -> None:
    updated = state_repository().update(lambda state: set_active_profile(state, name))
    payload = {"active_profile": updated.active_profile}
    _emit(ctx, payload, [f"{tr('cli.setup.headers.profile')}\t{updated.active_profile or ''}"])


@profile_app.command("show", help=tr("cli.setup.profile.show_help"))
def profile_show(
    ctx: typer.Context,
    all_keys: bool = typer.Option(False, "--all-keys", help=tr("cli.setup.profile.show_all_keys_help")),
    unset: bool = typer.Option(False, "--unset", help=tr("cli.setup.profile.show_unset_help")),
) -> None:
    state, name = _active_profile_or_exit(ctx)
    record = state.active_profile_record()
    assert record is not None
    rows = list_profile_value_rows(record.values, include_unset=all_keys or unset)
    payload = {
        "active_profile": name,
        "values": {row.key: row.value for row in rows if row.is_set and row.value is not None},
        "rows": rows,
    }
    lines: list[str] = [f"{tr('cli.setup.headers.profile')}\t{name}"]
    lines.extend(f"{row.key}\t{row.value if row.value is not None else '<unset>'}" for row in rows)
    _emit(ctx, payload, lines)


@profile_app.command("list-keys", help=tr("cli.setup.profile.list_keys_help"))
def profile_list_keys(ctx: typer.Context) -> None:
    payload = {
        "keys": [
            {
                "key": entry.key,
                "requirement": entry.requirement.value,
                "description": _description_for(entry),
            }
            for entry in PROFILE_KEYS
        ]
    }
    lines: list[str] = [
        f"{tr('cli.setup.headers.key')}\t{tr('cli.setup.headers.requirement')}\t{tr('cli.setup.headers.description')}"
    ]
    lines.extend(f"{entry.key}\t{entry.requirement.value}\t{_description_for(entry)}" for entry in PROFILE_KEYS)
    _emit(ctx, payload, lines)


@profile_app.command("get", help=tr("cli.setup.profile.get_help"))
def profile_get(ctx: typer.Context, key: str = typer.Argument(..., help=tr("cli.setup.profile.get_key_help"))) -> None:
    state, _name = _active_profile_or_exit(ctx)
    try:
        get_profile_key(key)
    except KeyError as exc:
        raise _bad(tr("cli.setup.errors.unknown_profile_key").format(key=key)) from exc
    record = state.active_profile_record()
    assert record is not None
    value = record.values.get(key, "")
    _emit(ctx, {"key": key, "value": value}, [f"{key}\t{value}"])


@profile_app.command("set", help=tr("cli.setup.profile.set_help"))
def profile_set(
    ctx: typer.Context,
    key: str = typer.Argument(..., help=tr("cli.setup.profile.set_key_help")),
    value: str = typer.Argument(..., help=tr("cli.setup.profile.set_value_help")),
) -> None:
    try:
        get_profile_key(key)
    except KeyError as exc:
        raise _bad(tr("cli.setup.errors.unknown_profile_key").format(key=key)) from exc
    _state_value, name = _active_profile_or_exit(ctx)
    updated = state_repository().update(lambda current: set_profile_values(current, name, {key: value}))
    record = updated.active_profile_record()
    assert record is not None
    _emit(ctx, {"key": key, "value": record.values.get(key, "")}, [f"{key}\t{record.values.get(key, '')}"])


@profile_app.command("unset", help=tr("cli.setup.profile.unset_help"))
def profile_unset(
    ctx: typer.Context, key: str = typer.Argument(..., help=tr("cli.setup.profile.unset_key_help"))
) -> None:
    try:
        get_profile_key(key)
    except KeyError as exc:
        raise _bad(tr("cli.setup.errors.unknown_profile_key").format(key=key)) from exc
    _state_value, name = _active_profile_or_exit(ctx)
    state_repository().update(lambda current: clear_profile_values(current, name, (key,)))
    _emit(ctx, {"key": key}, [f"{key}\t{tr('cli.setup.labels.unset')}"])


@profile_app.command("validate", help=tr("cli.setup.profile.validate_help"))
def profile_validate(ctx: typer.Context) -> None:
    current = _state()
    record = current.active_profile_record()
    if record is None:
        payload = {
            "valid": False,
            "missing": ["profile"],
            "missing_required": ["profile"],
            "present_required": [],
            "present_optional": [],
            "unknown_keys": [],
            "present_keys": 0,
            "total_keys": len(list_profile_value_rows({}, include_unset=True)),
        }
        _emit(
            ctx,
            payload,
            [
                f"{tr('cli.setup.headers.valid')}\t{tr('cli.setup.labels.no')}",
                f"{tr('cli.setup.headers.missing')}\tprofile",
                f"{tr('cli.setup.headers.completeness')}\t0/{payload['total_keys']}",
            ],
        )
        _exit(2)
    assert record is not None
    result = validate_profile(record.values)
    payload = {
        "valid": result.valid,
        "missing": list(result.missing_required),
        "missing_required": list(result.missing_required),
        "present_required": list(result.present_required),
        "present_optional": list(result.present_optional),
        "unknown_keys": list(result.unknown_keys),
        "present_keys": result.present_keys,
        "total_keys": result.total_keys,
    }
    lines: list[str] = [
        f"{tr('cli.setup.headers.valid')}\t{tr('cli.setup.labels.yes') if result.valid else tr('cli.setup.labels.no')}",
        f"{tr('cli.setup.headers.completeness')}\t{result.present_keys}/{result.total_keys}",
    ]
    if result.missing_required:
        lines.append(f"{tr('cli.setup.headers.missing')}\t{', '.join(result.missing_required)}")
    if result.unknown_keys:
        lines.append(f"{tr('cli.setup.headers.unknown')}\t{', '.join(result.unknown_keys)}")
    _emit(ctx, payload, lines)
    if not result.valid:
        _exit(2)


@profile_app.command("list", help=tr("cli.setup.profile.list_help"))
def profile_list(ctx: typer.Context) -> None:
    current = _state()
    payload = {"profiles": sorted(current.profiles.keys()), "active": current.active_profile}
    lines: list[str] = [f"{tr('cli.setup.headers.active')}\t{current.active_profile or ''}"]
    lines.extend(f"{tr('cli.setup.headers.profile')}\t{name}" for name in sorted(current.profiles.keys()))
    _emit(ctx, payload, lines)
