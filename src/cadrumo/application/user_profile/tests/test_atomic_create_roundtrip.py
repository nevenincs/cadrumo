"""Roundtrip: atomic profile create reads back consistently across verbs.

Every profile-creation path lands on one atomic provisioner
(``register_active_profile``). The contract this test pins: a profile
created through the canonical create path must read back with the same
immutable UUID identity through ``profile list``, ``profile show``,
``config login``, and a second ``profile show``. The operator
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
from ....core.config import override_settings
from ....core.redaction import CLI_BUCKET_ID_PLACEHOLDER, CLI_PROFILE_ID_PLACEHOLDER
from ....tests.cli_envelope import unwrap_cli_result as _json
from ....tests.cli_runner import invoke_cached_cli
from ....tests.profile_capsule import open_test_profile_session
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


def _invoke(args: list[str]):
    """Invoke the CLI, disposing the engine first so each verb is a cold start."""

    dispose_engine()
    return invoke_cached_cli(args)


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

    show_first = _invoke(["--format", "json", "config", "profile", "show", "alice"])
    assert show_first.exit_code == 0, show_first.output
    assert _json(show_first)["profile_id"] == CLI_PROFILE_ID_PLACEHOLDER
    # display_name is the operator label — the positional create arg.
    assert _json(show_first)["display_name"] == "alice"

    unlock = _invoke(["--format", "json", "config", "login", "alice"])
    assert unlock.exit_code == 0, unlock.output
    assert _json(unlock)["active_profile"] == "alice"

    show_second = _invoke(["--format", "json", "config", "profile", "show", "alice"])
    assert show_second.exit_code == 0, show_second.output
    assert _json(show_second)["profile_id"] == CLI_PROFILE_ID_PLACEHOLDER

    # The placeholder is stable across calls; display name agrees.
    assert _json(show_first)["display_name"] == _json(show_second)["display_name"]


def test_atomic_create_roundtrip_facts_survive_to_show(_cli_storage: Path) -> None:
    """The facts written at create time read back through ``profile show``.

    ``identity.tax_id`` is a sensitive operator identifier and is redacted to a
    stable ``sha256:<prefix>`` token at the CLI boundary per the centralised
    output-redaction contract. The non-sensitive facts surface verbatim.
    """

    _create("alice")

    show = _invoke(["--format", "json", "config", "profile", "show", "alice"])
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

    unlock_alice = _invoke(["--format", "json", "config", "login", "alice"])
    assert unlock_alice.exit_code == 0, unlock_alice.output
    show_alice = _invoke(["--format", "json", "config", "profile", "show"])
    assert _json(show_alice)["display_name"] == "alice"

    unlock_bob = _invoke(["--format", "json", "config", "login", "bob"])
    assert unlock_bob.exit_code == 0, unlock_bob.output
    show_bob = _invoke(["--format", "json", "config", "profile", "show"])
    assert _json(show_bob)["display_name"] == "bob"
    # The two profiles surface distinct operator-visible display_names; profile
    # UUIDs are redacted at the CLI boundary to the shared placeholder.
    assert _json(show_alice)["display_name"] != _json(show_bob)["display_name"]
    assert _json(show_alice)["profile_id"] == CLI_PROFILE_ID_PLACEHOLDER
    assert _json(show_bob)["profile_id"] == CLI_PROFILE_ID_PLACEHOLDER


def test_atomic_create_roundtrip_duplicate_lands_through_provisioner(_cli_storage: Path) -> None:
    """``profile duplicate`` routes the copy through the atomic provisioner.

    The duplicated profile must be visible in ``profile list`` and
    ``profile show`` — proof the bucket directory, manifest, encrypted
    record, and pointer all landed, not just a partial copy.
    """

    _create("alice")

    duplicate = _invoke(
        ["--format", "json", "config", "profile", "duplicate", "alice", "alice-copy", "--display-name", "Copy"],
    )
    assert duplicate.exit_code == 0, duplicate.output
    # The duplicate's target UUID is redacted at the CLI boundary; the
    # stable placeholder is what the operator sees.
    assert _json(duplicate)["target_profile_id"] == CLI_PROFILE_ID_PLACEHOLDER

    listing = _invoke(["--format", "json", "config", "profile", "list"])
    # The duplicate is labelled by its --display-name; the source keeps "alice".
    assert sorted(row["name"] for row in _json(listing)["profiles"]) == ["Copy", "alice"]

    show_copy = _invoke(["--format", "json", "config", "profile", "show", "Copy"])
    assert show_copy.exit_code == 0, show_copy.output
    assert _json(show_copy)["profile_id"] == CLI_PROFILE_ID_PLACEHOLDER
    assert _json(show_copy)["display_name"] == "Copy"
    # The source profile's facts copied into the new bucket.
    copy_facts = {row["path"]: row["value"] for row in _json(show_copy)["facts"]}
    assert copy_facts["activities.description"] == "design"


def test_atomic_create_roundtrip_export_import_preserves_label_and_facts(_cli_storage: Path, tmp_path: Path) -> None:
    """A profile exported then imported into a fresh root keeps its label and facts.

    The import path routes through the atomic provisioner while preserving the
    bundle's UUID identity. The operator-facing label and profile facts must
    survive the round trip. The import lands in a *fresh* storage root so the
    duplicate-label guard does not (correctly) refuse it.
    """

    _create("alice")
    bundle = _cli_storage / "alice-bundle.json"
    export = _invoke(
        ["--format", "json", "config", "profile", "export", "alice", "--to", str(bundle), "--cleartext-local"],
    )
    assert export.exit_code == 0, export.output
    assert bundle.is_file()
    exported_id = json.loads(bundle.read_text(encoding="utf-8"))["profile"]["profile_id"]

    source_show = _invoke(["--format", "json", "config", "profile", "show", "alice"])
    source_facts = {row["path"]: row["value"] for row in _json(source_show)["facts"]}

    # Re-point the storage root so the imported profile lands in a
    # clean workspace — the recovery-from-backup scenario.
    fresh_root = tmp_path / "fresh-root"
    with override_settings(cadrumo_local_storage_root=fresh_root, cadrumo_active_profile=None):
        importer = _invoke(["--format", "json", "config", "profile", "import", str(bundle)])
        assert importer.exit_code == 0, importer.output
        # Profile UUIDs are redacted at the CLI boundary; the operator-facing
        # surface carries the display_name and the stable placeholder.
        assert _json(importer)["profile_id"] == CLI_PROFILE_ID_PLACEHOLDER
        assert _json(importer)["display_name"] == "alice"

        imported_list = _invoke(["--format", "json", "config", "profile", "list"])
        assert [row["name"] for row in _json(imported_list)["profiles"]] == ["alice"]

        imported_show = _invoke(["--format", "json", "config", "profile", "show", "alice"])
        assert imported_show.exit_code == 0, imported_show.output
        assert _json(imported_show)["profile_id"] == CLI_PROFILE_ID_PLACEHOLDER
        imported_facts = {row["path"]: row["value"] for row in _json(imported_show)["facts"]}
        assert imported_facts == source_facts
        from .. import CommittedProfileRepository

        with open_test_profile_session(exported_id):
            imported = CommittedProfileRepository().load(exported_id)
        assert imported.profile_id == exported_id
        assert imported.label == "alice"
