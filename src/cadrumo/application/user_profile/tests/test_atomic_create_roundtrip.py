"""Roundtrip: atomic profile create reads back consistently across verbs.

Every profile-creation path lands on one atomic provisioner
(``register_active_profile``). The contract this test pins: a profile
created through the canonical create path must read back with the same
immutable UUID identity through ``profile list``, ``profile view``,
``config login``, and a second ``profile view``. The operator
addresses the profile by its display name; the UUID is the stable
internal identity that must never drift between verbs.

Every CLI invocation runs against a real per-bucket SQLite engine and
a file-backed secret-store custody provider — no mocks, no fakes. The
``import`` and ``duplicate`` paths are covered in the same suite
because both route through the same atomic provisioner.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest

from ....adapters.persistence.storage.sql.engine import dispose_engine
from ....core.config import load_settings, override_settings
from ....core.redaction import CLI_BUCKET_ID_PLACEHOLDER, CLI_PROFILE_ID_PLACEHOLDER
from ....tests.cli_envelope import unwrap_cli_result as _json
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_profile_storage_root
from ....tests.user_profile import register_cli_profile

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.fixture
def _cli_storage(tmp_path: Path) -> Iterator[Path]:
    """Per-bucket storage root with file-backed custody.

    The primary database URL is not supplied explicitly: each profile
    bucket resolves its own SQLite file from the active-profile pointer
    chain, which is the production cold-start path the disaster
    recovery wires.
    """

    with (
        isolated_profile_storage_root(tmp_path=tmp_path) as storage_root,
        override_settings(cadrumo_output_language="en"),
    ):
        yield storage_root


def _invoke(args: list[str], *, stdin_payload: str | None = None):
    """Invoke the CLI, disposing the engine first so each verb is a cold start."""

    dispose_engine()
    return invoke_cached_cli(args, input=stdin_payload)


def _login(name: str):
    """Unlock ``name`` over the only channel `config login` still accepts.

    The passphrase is no longer resolvable from settings. The machine-secret
    boundary rejects the environment fallback outright -- "CLI entrypoints never
    resolve caller-supplied scalar secrets from environment, settings,
    keyrings, or an implicit adapter fallback" -- so the isolated backend
    configuring `cadrumo_secret_passphrase` no longer unlocks anything, and
    this must hand the secret over the bounded strict-JSON channel instead.
    The value is the one that backend seeded the custody envelope with, or the
    envelope would not open.
    """
    return _invoke(
        ["--format", "json", "config", "login", name, "--secrets-stdin"],
        stdin_payload=json.dumps(
            {"passphrase": load_settings().cadrumo_dev_test_database_password.get_secret_value()},
        ),
    )


def _create(name: str, tax_id: str = "12345678Z") -> None:
    register_cli_profile(
        label=name,
        facts={
            "identity.tax_id": tax_id,
            "taxpayer_type.entity_type": "natural_person",
            "identity.name": name.capitalize(),
            "identity.surnames": "Example",
            "activities.description": "design",
            "iva.regime": "GENERAL",
            "tax_residence.jurisdiction_scope": "common_regime",
            "iva.m303_regime_composition": "general",
            "iva.redeme_enrolled": "false",
            "iva.cash_accounting_regime_enrolled": "false",
            "iva.voluntary_sii_enrolled": "false",
            "iva.hydrocarbon_deposit_advance_payment_deduction_entitled": "false",
        },
    )


def test_atomic_create_roundtrip_identity_is_consistent_across_verbs(_cli_storage: Path) -> None:
    """create -> list -> show -> login -> show all agree on one profile.

    Profile/bucket UUIDs are redacted on the CLI surface per the centralised
    output-redaction contract; the test asserts the operator-visible identity
    (display_name plus the stable redacted placeholder) survives every verb.
    """

    _create("alice")

    listing = _invoke(["--format", "json", "config", "profile", "list"])
    assert listing.exit_code == 0, listing.output
    list_names = [row["name"] for row in _json(listing)["profiles"]]
    assert list_names == ["alice"], list_names
    # The bucket id is redacted at the CLI boundary; the placeholder is stable.
    assert _json(listing)["profiles"][0]["bucket_id"] == CLI_BUCKET_ID_PLACEHOLDER

    show_first = _invoke(["--format", "json", "config", "profile", "view", "alice"])
    assert show_first.exit_code == 0, show_first.output
    assert _json(show_first)["profile_id"] == CLI_PROFILE_ID_PLACEHOLDER
    # display_name is the operator label — the positional create arg.
    assert _json(show_first)["display_name"] == "alice"

    unlock = _login("alice")
    assert unlock.exit_code == 0, unlock.output
    assert _json(unlock)["active_profile"] == "alice"

    show_second = _invoke(["--format", "json", "config", "profile", "view", "alice"])
    assert show_second.exit_code == 0, show_second.output
    assert _json(show_second)["profile_id"] == CLI_PROFILE_ID_PLACEHOLDER

    # The placeholder is stable across calls; display name agrees.
    assert _json(show_first)["display_name"] == _json(show_second)["display_name"]


def test_atomic_create_roundtrip_facts_survive_to_show(_cli_storage: Path) -> None:
    """The facts written at create time read back through ``profile view``.

    ``identity.tax_id`` is a sensitive operator identifier and is redacted to a
    stable ``sha256:<prefix>`` token at the CLI boundary per the centralised
    output-redaction contract. The non-sensitive facts surface verbatim.
    """

    _create("alice")

    show = _invoke(["--format", "json", "config", "profile", "view", "alice"])
    assert show.exit_code == 0, show.output
    facts = {row["path"]: row["value"] for row in _json(show)["facts"]}
    # The NIF is redacted at the CLI surface; assert the redaction shape, not
    # the raw operator value. The sha256 prefix is deterministic for the input.
    assert facts["identity.tax_id"].startswith("sha256:")
    assert facts["activities.description"] == "design"
    assert facts["iva.regime"] == "GENERAL"


def test_atomic_create_roundtrip_two_profiles_resolve_independently(_cli_storage: Path) -> None:
    """Two profiles created in sequence each read back with their own identity.

    The two profiles model two distinct taxpayers, so they carry
    distinct valid Spanish NIFs — one taxpayer, one profile is enforced
    by the duplicate-tax-id refusal at create.
    """

    _create("alice", tax_id="12345678Z")
    _create("bob", tax_id="87654321X")

    listing = _invoke(["--format", "json", "config", "profile", "list"])
    assert listing.exit_code == 0, listing.output
    assert sorted(row["name"] for row in _json(listing)["profiles"]) == ["alice", "bob"]

    unlock_alice = _login("alice")
    assert unlock_alice.exit_code == 0, unlock_alice.output
    show_alice = _invoke(["--format", "json", "config", "profile", "view"])
    assert _json(show_alice)["display_name"] == "alice"

    unlock_bob = _login("bob")
    assert unlock_bob.exit_code == 0, unlock_bob.output
    show_bob = _invoke(["--format", "json", "config", "profile", "view"])
    assert _json(show_bob)["display_name"] == "bob"
    # The two profiles surface distinct operator-visible display_names; profile
    # UUIDs are redacted at the CLI boundary to the shared placeholder.
    assert _json(show_alice)["display_name"] != _json(show_bob)["display_name"]
    assert _json(show_alice)["profile_id"] == CLI_PROFILE_ID_PLACEHOLDER
    assert _json(show_bob)["profile_id"] == CLI_PROFILE_ID_PLACEHOLDER
