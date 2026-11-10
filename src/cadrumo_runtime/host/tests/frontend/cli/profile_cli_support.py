"""Small real-CLI helpers shared by profile CLI tests."""

from __future__ import annotations

import json
from collections.abc import Callable, Generator, Iterator
from contextlib import contextmanager
from datetime import date
from pathlib import Path

import pytest
from click.testing import Result

from cadrumo.adapters.persistence.profile.tests.profile_registration import register_cli_profile
from cadrumo.adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from cadrumo.core.config import override_settings
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope
from cadrumo_runtime.host.tests.frontend.cli.config.tests.isolated_storage_fixture import native_profile_view_server
from cadrumo_runtime.host.tests.native_commands.runtime_profile_cli_fixture import (
    NativeCliProfileFixture,
    native_cli_profile_scope,
)

from ...native_profile_facts import native_general_iva_facts
from .cli_runner import invoke_cached_cli


@pytest.fixture
def native_profile_runtime(tmp_path: Path) -> Iterator[None]:
    """Run a real installed profile worker for a test's isolated storage root."""
    storage_root = tmp_path / "cadrumo-storage"
    storage_root.mkdir(parents=True, exist_ok=True)
    with native_profile_view_server(storage_root):
        yield


def invoke_protected_profile(name: str, *args: str, json_output: bool = False, language: str | None = None) -> Result:
    """Prove the exact registered profile with its password on a native leaf."""
    from cadrumo.core.config import load_settings

    prefix = ("--format", "json") if json_output else ()
    if language is not None:
        prefix = (*prefix, "--language", language)
    secret = load_settings().cadrumo_dev_test_database_password.get_secret_value()
    return invoke_cached_cli(
        (*prefix, "--profile", name, "--profile-secrets-stdin", "config", "profile", *args),
        input=json.dumps({"profile_passphrase": secret}),
    )


def seed_profile(name: str, **facts: str) -> str:
    """Seed one profile through the credential registration door, and return its id.

    Use this wherever a test needs a profile to EXIST. ``create_quiet_profile``
    below instead drives the real scripted CLI creation lane with its bounded
    credential and paired recovery channels.
    """
    return register_cli_profile(label=name, facts=facts, log_in=False)


def create_quiet_profile(name: str, *options: str) -> Result:
    return invoke_profile_create(
        (
            "config",
            "profile",
            "create",
            name,
            "--quiet",
            "--accept-defaults",
            *_filing_identity_defaults(name, options),
            *options,
        ),
    )


def invoke_profile_create(argv: tuple[str, ...]) -> Result:
    """Run a ``config profile create`` argv with its credential and recovery channels.

    ``create`` MINTS a custody envelope, so it needs the operator passphrase and
    its confirmation -- unlike ``edit``, which opens an existing one and refuses a
    payload carrying the confirmation field. A test runner is not a terminal, so
    the bounded strict-JSON channel is the only one either verb accepts.
    """
    from cadrumo.core.config import load_settings

    secret = load_settings().cadrumo_dev_test_database_password.get_secret_value()
    return invoke_cached_cli(
        (*argv, "--secrets-stdin"),
        input=json.dumps({"passphrase": secret, "passphrase_confirmation": secret}),
    )


def login_profile(name: str) -> Result:
    """Open ``name``'s session over the bounded strict-JSON passphrase channel."""
    from cadrumo.core.config import load_settings

    secret = load_settings().cadrumo_dev_test_database_password.get_secret_value()
    return invoke_cached_cli(
        ("--format", "json", "config", "login", name, "--secrets-stdin"),
        input=json.dumps({"passphrase": secret}),
    )


def edit_quiet_profile(name: str, *options: str) -> Result:
    return invoke_protected_profile(name, "edit", "--quiet", *options)


def profile_rows(name: str) -> dict[str, str]:
    result = invoke_protected_profile(name, "view")
    assert result.exit_code == 0, result.output
    rows: dict[str, str] = {}
    for line in result.output.splitlines():
        if "\t" not in line:
            continue
        key, _, value = line.partition("\t")
        rows[key.strip()] = value.strip()
    return rows


def _filing_identity_defaults(name: str, options: tuple[str, ...]) -> tuple[str, ...]:
    option_set = set(options)
    defaults: list[str] = []
    if "--entity-type" not in option_set:
        defaults.extend(("--entity-type", "natural_person"))
    entity_type = _option_value(options, "--entity-type") or "natural_person"
    if entity_type == "legal_entity":
        if "--legal-name" not in option_set:
            defaults.extend(["--legal-name", f"{name} SL"])
        return tuple(defaults)
    if "--name" not in option_set:
        defaults.extend(["--name", name])
    if entity_type == "natural_person" and "--surnames" not in option_set:
        defaults.extend(["--surnames", "Test"])
    return tuple(defaults)


def _option_value(options: tuple[str, ...], flag: str) -> str | None:
    try:
        index = options.index(flag)
    except ValueError:
        return None
    value_index = index + 1
    if value_index >= len(options):
        return None
    value = options[value_index]
    return None if value.startswith("--") else value


def invoke_native_profile(profile: NativeCliProfileFixture, *command: str) -> Result:
    """Run one JSON command against the registered native profile with its secret on stdin."""
    assert profile.label is not None
    close_active_bucket_session()
    result = invoke_cached_cli(
        ("--language", "en", "--format", "json", "--profile", profile.label, "--profile-secrets-stdin", *command),
        input=json.dumps({"profile_passphrase": profile.passphrase}),
    )
    assert profile.passphrase not in result.output
    return result


def invoke_native_profile_revealing(profile: NativeCliProfileFixture, *command: str) -> Result:
    """Run one JSON command as ``invoke_native_profile`` does, with identifiers left unmasked."""
    with override_settings(cadrumo_cli_reveal_identifiers=True):
        return invoke_native_profile(profile, *command)


@contextmanager
def partial_taxpayer_invoker(tmp_path: Path, *, label: str) -> Generator[Callable[[list[str]], Result]]:
    """Serve one native profile holding a partial Catalan taxpayer and yield a command runner bound to it."""
    with native_cli_profile_scope(tmp_path) as profile:
        profile.register(
            label=label,
            facts={
                **native_general_iva_facts(),
                "identity.tax_id": "12345678Z",
                "identity.name": "Operator",
                "identity.surnames": "Example",
                "activities.description": "design",
                "censo.activity_start_date": date(filing_year_envelope().floor, 1, 1).isoformat(),
                "contact.postcode": "28013",
                "tax_residence.ccaa": "cataluna",
                "renta_filing.declaration_type": "1",
                "renta_taxpayer.birth_date": "1980-03-15",
                "renta_family.minor_children_in_unit": "false",
            },
        )

        def invoke(args: list[str]) -> Result:
            assert profile.label is not None
            close_active_bucket_session()
            return invoke_cached_cli(
                ("--language", "en", "--profile", profile.label, "--profile-secrets-stdin", *args),
                input=json.dumps({"profile_passphrase": profile.passphrase}),
            )

        yield invoke
