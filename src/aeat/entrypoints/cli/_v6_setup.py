from __future__ import annotations

from pathlib import Path

import typer

from ...application.auth import (
    AUTH_PROVIDER_CATALOGUE,
    AuthProviderAvailability,
    get_auth_provider,
)
from ...application.profile import validate_profile
from ...application.user_cli import (
    clear_profile_values,
    set_active_profile,
    set_profile_values,
    state_repository,
    update_auth,
)
from ...domain.profile import (
    PROFILE_KEYS,
    get_profile_key,
)
from ._v6_common import (
    _active_profile_or_exit,
    _bad,
    _description_for,
    _emit,
    _exit,
    _label_for,
    _state,
)

app = typer.Typer(
    name="setup",
    help="Local prerequisites: profile, auth, readiness status.",
    no_args_is_help=True,
)
auth_app = typer.Typer(
    name="auth",
    help="AEAT auth provider configuration and login state.",
    no_args_is_help=True,
)
profile_app = typer.Typer(
    name="profile",
    help="Schema-backed taxpayer-profile editor.",
    no_args_is_help=True,
)

app.add_typer(auth_app, name="auth")
app.add_typer(profile_app, name="profile")


@app.command("init", help="Create or activate a setup profile and seed essentials.")
def setup_init(
    ctx: typer.Context,
    name: str = typer.Option(..., "--name", help="Profile name."),
    activity: str | None = typer.Option(None, "--activity", help="Business activity (free text)."),
    tax_id: str | None = typer.Option(None, "--tax-id", help="NIF / NIE."),
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
            "profile\t" + (updated.active_profile or ""),
            "next\taeat setup auth configure --provider certificate --file PATH",
        ],
    )


@app.command("status", help="Show profile, auth, and validation readiness with the next action.")
def setup_status(ctx: typer.Context) -> None:
    """Show profile, auth, and validation readiness."""
    current = _state()
    record = current.active_profile_record()
    profile_ready = False
    missing_required: list[str] = []
    if record is not None:
        result = validate_profile(record.values)
        profile_ready = result.valid
        missing_required = list(result.missing_required)
    auth_provider = current.auth.provider or ""
    login_ready = current.auth.authenticated_at is not None
    if record is None:
        next_action = "aeat setup init --name NAME"
    elif missing_required:
        next_action = f"aeat setup profile set {missing_required[0]} VALUE"
    elif not auth_provider:
        next_action = "aeat setup auth configure --provider certificate --file PATH"
    elif not login_ready:
        next_action = "aeat setup auth login"
    else:
        next_action = "aeat app overview status"
    payload = {
        "active_profile": current.active_profile,
        "profile_ready": profile_ready,
        "missing_required": missing_required,
        "auth_provider": auth_provider,
        "login_ready": login_ready,
        "next_action": next_action,
    }
    _emit(
        ctx,
        payload,
        [
            f"profile\t{current.active_profile or ''}",
            f"profile_ready\t{'yes' if profile_ready else 'no'}",
            f"missing\t{', '.join(missing_required) or '-'}",
            f"auth_provider\t{auth_provider}",
            f"login_ready\t{'yes' if login_ready else 'no'}",
            f"next\t{next_action}",
        ],
    )


# ---------------------------------------------------------------------
# `aeat setup auth` — auth-provider commands
# ---------------------------------------------------------------------


@auth_app.command("providers", help="List implemented and research-only AEAT auth providers.")
def auth_providers(ctx: typer.Context) -> None:
    """Render the v6 provider catalogue."""
    payload = {
        "providers": [
            {
                "id": entry.id,
                "label": _label_for(entry),
                "availability": entry.availability.value,
                "description": _description_for(entry),
            }
            for entry in AUTH_PROVIDER_CATALOGUE
        ]
    }
    lines: list[str] = ["id\tavailability\tdescription"]
    lines.extend(
        f"{entry.id}\t{entry.availability.value}\t{_description_for(entry)}" for entry in AUTH_PROVIDER_CATALOGUE
    )
    _emit(ctx, payload, lines)


@auth_app.command("configure", help="Configure an AEAT auth provider (refuses research-only providers).")
def auth_configure(
    ctx: typer.Context,
    provider: str = typer.Option(..., "--provider", help="Provider id (certificate / clave-movil)."),
    file: Path | None = typer.Option(None, "--file", help="Provider asset file (e.g. PKCS#12 certificate)."),
) -> None:
    """Configure an AEAT auth provider via the application catalogue."""
    try:
        listing = get_auth_provider(provider.strip().lower())
    except KeyError:
        raise _bad(f"unknown provider {provider!r}; run `aeat setup auth providers`")
    if listing.availability is AuthProviderAvailability.RESEARCH_ONLY:
        _emit(
            ctx,
            {"error": "research-only", "provider": listing.id, "description": _description_for(listing)},
            [f"error\tresearch-only\tprovider={listing.id}"],
        )
        _exit(2)
    if listing.id == "certificate" and file is None:
        raise _bad("certificate provider requires --file PATH")
    if listing.id == "certificate" and file is not None and not file.exists():
        raise _bad(f"--file {file} does not exist")
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
        [f"provider\t{updated.auth.provider}", "next\taeat setup auth login"],
    )


@auth_app.command("login", help="Record an AEAT login attempt against the configured provider.")
def auth_login(ctx: typer.Context) -> None:
    """Mark the configured provider as logged-in (offline marker for now)."""
    current = _state()
    if current.auth.provider is None:
        raise _bad("configure an auth provider first: aeat setup auth configure --provider …")
    record = current.active_profile_record()
    subject = record.values.get("tax.id") if record is not None else None
    updated = state_repository().update(lambda state: update_auth(state, authenticated=True, subject=subject))
    payload = {"auth": updated.auth}
    _emit(
        ctx,
        payload,
        [f"provider\t{updated.auth.provider}", f"subject\t{updated.auth.subject or ''}"],
    )


@auth_app.command("status", help="Show configured provider and login readiness.")
def auth_status(ctx: typer.Context) -> None:
    current = _state()
    ready = current.auth.provider is not None and current.auth.authenticated_at is not None
    payload = {"auth": current.auth, "ready": ready}
    _emit(
        ctx,
        payload,
        [
            f"provider\t{current.auth.provider or ''}",
            f"ready\t{'yes' if ready else 'no'}",
            f"authenticated_at\t{current.auth.authenticated_at.isoformat() if current.auth.authenticated_at else ''}",
        ],
    )


@auth_app.command("whoami", help="Show the locally recorded AEAT identity.")
def auth_whoami(ctx: typer.Context) -> None:
    current = _state()
    payload = {"provider": current.auth.provider, "subject": current.auth.subject}
    _emit(
        ctx,
        payload,
        [
            f"provider\t{current.auth.provider or ''}",
            f"subject\t{current.auth.subject or ''}",
        ],
    )


@auth_app.command("logout", help="Clear the local authentication marker.")
def auth_logout(ctx: typer.Context) -> None:
    updated = state_repository().update(lambda state: update_auth(state, authenticated=False))
    payload = {"auth": updated.auth}
    _emit(ctx, payload, [f"provider\t{updated.auth.provider or ''}", "logout\tok"])


# ---------------------------------------------------------------------
# `aeat setup profile` — schema-backed editor
# ---------------------------------------------------------------------


@profile_app.command("use", help="Activate a setup profile by name.")
def profile_use(ctx: typer.Context, name: str = typer.Argument(..., help="Profile name.")) -> None:
    updated = state_repository().update(lambda state: set_active_profile(state, name))
    payload = {"active_profile": updated.active_profile}
    _emit(ctx, payload, [f"profile\t{updated.active_profile or ''}"])


@profile_app.command("show", help="Show the active profile values.")
def profile_show(ctx: typer.Context) -> None:
    state, name = _active_profile_or_exit(ctx)
    record = state.active_profile_record()
    assert record is not None
    payload = {"active_profile": name, "values": record.values}
    lines: list[str] = [f"profile\t{name}"]
    lines.extend(f"{key}\t{value}" for key, value in sorted(record.values.items()))
    _emit(ctx, payload, lines)


@profile_app.command("list-keys", help="List every editable profile key with its requirement.")
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
    lines: list[str] = ["key\trequirement\tdescription"]
    lines.extend(f"{entry.key}\t{entry.requirement.value}\t{_description_for(entry)}" for entry in PROFILE_KEYS)
    _emit(ctx, payload, lines)


@profile_app.command("get", help="Read one profile value.")
def profile_get(ctx: typer.Context, key: str = typer.Argument(..., help="Profile key.")) -> None:
    state, name = _active_profile_or_exit(ctx)
    try:
        get_profile_key(key)
    except KeyError:
        raise _bad(f"unknown profile key {key!r}; run `aeat setup profile list-keys`")
    record = state.active_profile_record()
    assert record is not None
    value = record.values.get(key, "")
    _emit(ctx, {"key": key, "value": value}, [f"{key}\t{value}"])


@profile_app.command("set", help="Set one profile value.")
def profile_set(
    ctx: typer.Context,
    key: str = typer.Argument(..., help="Profile key."),
    value: str = typer.Argument(..., help="Profile value."),
) -> None:
    try:
        get_profile_key(key)
    except KeyError:
        raise _bad(f"unknown profile key {key!r}; run `aeat setup profile list-keys`")
    state, name = _active_profile_or_exit(ctx)
    updated = state_repository().update(lambda current: set_profile_values(current, name, {key: value}))
    record = updated.active_profile_record()
    assert record is not None
    _emit(ctx, {"key": key, "value": record.values.get(key, "")}, [f"{key}\t{record.values.get(key, '')}"])


@profile_app.command("unset", help="Clear one profile value.")
def profile_unset(ctx: typer.Context, key: str = typer.Argument(..., help="Profile key.")) -> None:
    try:
        get_profile_key(key)
    except KeyError:
        raise _bad(f"unknown profile key {key!r}; run `aeat setup profile list-keys`")
    state, name = _active_profile_or_exit(ctx)
    updated = state_repository().update(lambda current: clear_profile_values(current, name, (key,)))
    _emit(ctx, {"key": key}, [f"{key}\t(unset)"])


@profile_app.command("validate", help="Validate that the active profile has the required keys.")
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
        }
        _emit(ctx, payload, ["valid\tno", "missing\tprofile"])
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
    }
    lines: list[str] = [f"valid\t{'yes' if result.valid else 'no'}"]
    if result.missing_required:
        lines.append(f"missing\t{', '.join(result.missing_required)}")
    if result.unknown_keys:
        lines.append(f"unknown\t{', '.join(result.unknown_keys)}")
    _emit(ctx, payload, lines)
    if not result.valid:
        _exit(2)


@profile_app.command("list", help="List configured setup profiles.")
def profile_list(ctx: typer.Context) -> None:
    current = _state()
    payload = {"profiles": sorted(current.profiles.keys()), "active": current.active_profile}
    lines: list[str] = [f"active\t{current.active_profile or ''}"]
    lines.extend(f"profile\t{name}" for name in sorted(current.profiles.keys()))
    _emit(ctx, payload, lines)
