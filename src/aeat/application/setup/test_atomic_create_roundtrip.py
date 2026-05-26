"""Roundtrip: atomic profile create reads back consistently across verbs.

Every profile-creation path lands on one atomic provisioner
(``register_active_profile``). The contract this test pins: a profile
created through the canonical create path must read back with the same
immutable UUID identity through ``profile list``, ``profile show``,
``profile switch``, and a second ``profile show``. The operator
addresses the profile by its display name; the UUID is the stable
internal identity that must never drift between verbs.

Every CLI invocation runs against a real per-bucket SQLite engine and
a real unsecured master-key provider — no mocks, no fakes. The
``import`` and ``duplicate`` paths are covered in the same suite
because both route through the same atomic provisioner.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from pydantic import SecretStr

from aeat.adapters.persistence.storage.sql.engine import dispose_engine
from aeat.core.config import SecretStoreBackend, override_settings
from aeat.tests.cli_runner import invoke_cached_cli
from aeat.tests.secure_sql import dev_test_database_password

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]

_UUID_RE = r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"


@pytest.fixture
def _cli_storage(tmp_path: Path) -> Iterator[Path]:
    """Per-bucket storage root with file-backed custody.

    The primary database URL is not supplied explicitly: each profile
    bucket resolves its own SQLite file from the active-profile pointer
    chain, which is the production cold-start path the disaster
    recovery wires.
    """

    with override_settings(
        aeat_local_storage_root=tmp_path,
        aeat_active_profile=None,
        aeat_secret_store_backend=SecretStoreBackend.FILE,
        aeat_secret_passphrase=SecretStr(dev_test_database_password()),
        aeat_output_language="en",
    ) as settings:
        dispose_engine(settings)
        try:
            yield tmp_path
        finally:
            dispose_engine(settings)


def _invoke(args: list[str]):
    """Invoke the CLI, disposing the engine first so each verb is a cold start."""

    dispose_engine()
    return invoke_cached_cli(args)


def _json(result) -> dict:
    return json.loads(result.output)


def _create(name: str, tax_id: str = "12345678Z") -> None:
    result = _invoke(
        [
            "--format", "json",
            "config", "profile", "create", name,
            "--quiet",
            "--tax-id", tax_id,
            "--name", name.capitalize(),
            "--activity", "design",
            "--iva-regime", "GENERAL",
        ]
    )  # fmt: skip
    assert result.exit_code == 0, result.output


def test_atomic_create_roundtrip_identity_is_consistent_across_verbs(_cli_storage: Path) -> None:
    """create -> list -> show -> switch -> show all agree on one profile."""

    import re

    _create("alice")

    listing = _invoke(["--format", "json", "config", "profile", "list"])
    assert listing.exit_code == 0, listing.output
    list_names = [row["name"] for row in _json(listing)["profiles"]]
    assert list_names == ["alice"], list_names
    # The bucket id is a generated UUID, decoupled from the name.
    list_uuid = _json(listing)["profiles"][0]["bucket_id"]
    assert re.fullmatch(_UUID_RE, list_uuid)

    show_first = _invoke(["--format", "json", "config", "profile", "show", "alice"])
    assert show_first.exit_code == 0, show_first.output
    assert _json(show_first)["profile_id"] == list_uuid
    # display_name is the operator label — the positional create arg.
    assert _json(show_first)["display_name"] == "alice"

    switch = _invoke(["--format", "json", "config", "profile", "switch", "alice"])
    assert switch.exit_code == 0, switch.output
    assert _json(switch)["active_profile"] == "alice"

    show_second = _invoke(["--format", "json", "config", "profile", "show", "alice"])
    assert show_second.exit_code == 0, show_second.output
    assert _json(show_second)["profile_id"] == list_uuid

    # The same UUID identity surfaces from both show calls — no drift.
    assert _json(show_first)["profile_id"] == _json(show_second)["profile_id"]
    assert _json(show_first)["display_name"] == _json(show_second)["display_name"]


def test_atomic_create_roundtrip_facts_survive_to_show(_cli_storage: Path) -> None:
    """The facts written at create time read back through ``profile show``."""

    _create("alice")

    show = _invoke(["--format", "json", "config", "profile", "show", "alice"])
    assert show.exit_code == 0, show.output
    facts = {row["path"]: row["value"] for row in _json(show)["facts"]}
    assert facts["identity.tax_id"] == "12345678Z"
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

    switch_alice = _invoke(["--format", "json", "config", "profile", "switch", "alice"])
    assert switch_alice.exit_code == 0, switch_alice.output
    show_alice = _invoke(["--format", "json", "config", "profile", "show"])
    assert _json(show_alice)["display_name"] == "alice"

    switch_bob = _invoke(["--format", "json", "config", "profile", "switch", "bob"])
    assert switch_bob.exit_code == 0, switch_bob.output
    show_bob = _invoke(["--format", "json", "config", "profile", "show"])
    assert _json(show_bob)["display_name"] == "bob"
    # The two profiles carry distinct UUID identities.
    assert _json(show_alice)["profile_id"] != _json(show_bob)["profile_id"]


def test_atomic_create_roundtrip_duplicate_lands_through_provisioner(_cli_storage: Path) -> None:
    """``profile duplicate`` routes the copy through the atomic provisioner.

    The duplicated profile must be visible in ``profile list`` and
    ``profile show`` — proof the bucket directory, manifest, encrypted
    record, and pointer all landed, not just a partial copy.
    """

    _create("alice")

    import re

    duplicate = _invoke(
        ["--format", "json", "config", "profile", "duplicate", "alice", "alice-copy", "--display-name", "Copy"]
    )
    assert duplicate.exit_code == 0, duplicate.output
    # The duplicate lands under a fresh minted UUID, not the name.
    copy_uuid = _json(duplicate)["target_profile_id"]
    assert re.fullmatch(_UUID_RE, copy_uuid)

    listing = _invoke(["--format", "json", "config", "profile", "list"])
    # The duplicate is labelled by its --display-name; the source keeps "alice".
    assert sorted(row["name"] for row in _json(listing)["profiles"]) == ["Copy", "alice"]

    show_copy = _invoke(["--format", "json", "config", "profile", "show", "Copy"])
    assert show_copy.exit_code == 0, show_copy.output
    assert _json(show_copy)["profile_id"] == copy_uuid
    assert _json(show_copy)["display_name"] == "Copy"
    # The source profile's facts copied into the new bucket.
    copy_facts = {row["path"]: row["value"] for row in _json(show_copy)["facts"]}
    assert copy_facts["activities.description"] == "design"


def test_atomic_create_roundtrip_export_import_preserves_label_and_facts(_cli_storage: Path, tmp_path: Path) -> None:
    """A profile exported then imported into a fresh root keeps its label and facts.

    The import path routes through the atomic provisioner and mints a
    fresh UUID identity for the imported profile (the bundle's stored
    UUID was the originating machine's identity). The operator-facing
    label and the profile facts must survive the round trip. The import
    lands in a *fresh* storage root so the duplicate-label guard does
    not (correctly) refuse it.
    """

    import re

    _create("alice")
    bundle = _cli_storage / "alice-bundle.json"
    export = _invoke(["--format", "json", "config", "profile", "export", "alice", "--to", str(bundle)])
    assert export.exit_code == 0, export.output
    assert bundle.is_file()

    source_show = _invoke(["--format", "json", "config", "profile", "show", "alice"])
    source_facts = {row["path"]: row["value"] for row in _json(source_show)["facts"]}

    # Re-point the storage root so the imported profile lands in a
    # clean workspace — the recovery-from-backup scenario.
    fresh_root = tmp_path / "fresh-root"
    with override_settings(aeat_local_storage_root=fresh_root, aeat_active_profile=None):
        importer = _invoke(["--format", "json", "config", "profile", "import", str(bundle)])
        assert importer.exit_code == 0, importer.output
        # A fresh local identity is minted for the imported profile.
        imported_uuid = _json(importer)["profile_id"]
        assert re.fullmatch(_UUID_RE, imported_uuid)
        assert _json(importer)["display_name"] == "alice"

        imported_list = _invoke(["--format", "json", "config", "profile", "list"])
        assert [row["name"] for row in _json(imported_list)["profiles"]] == ["alice"]

        imported_show = _invoke(["--format", "json", "config", "profile", "show", "alice"])
        assert imported_show.exit_code == 0, imported_show.output
        assert _json(imported_show)["profile_id"] == imported_uuid
        imported_facts = {row["path"]: row["value"] for row in _json(imported_show)["facts"]}
        assert imported_facts == source_facts
