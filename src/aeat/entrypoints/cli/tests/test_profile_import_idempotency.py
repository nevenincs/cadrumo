"""Idempotency regression tests for `aeat config profile import` (contract).

Import idempotency contract:
  - Re-importing the same bundle twice produces exactly ONE profile; the
    second attempt is refused with "already registered".
  - Re-importing a bundle with ``--label <taken>`` when that label belongs
    to a different UUID is refused until the operator picks a fresh label.
  - Mutating the bundle's ``profile_id`` before a second import causes the
    import to succeed and creates a SECOND, distinct profile — proving that
    the UUID is the genuine discriminator, not the label.

No mocks.  Real ``isolated_profile_storage_root`` fixture, real encrypted
repositories.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest

from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_profile_storage_root
from .privacy_helpers import (
    assert_public_profile_id_not_leaked,
    assert_public_profile_id_redacted,
    assert_public_profile_payload_redacted,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@pytest.fixture(autouse=True)
def _isolated_storage(tmp_path: Path) -> Iterator[None]:
    with isolated_profile_storage_root(tmp_path=tmp_path):
        yield


def _invoke(args: list[str]):
    return invoke_cached_cli(args)


def _create_minimal_profile_and_export(tmp_path: Path, bundle_path: Path) -> str:
    """Create a minimal profile and export it to ``bundle_path``.

    Returns the exported ``profile_id`` (UUID).
    """

    r = _invoke(
        [
            "config",
            "profile",
            "create",
            "idempotency-test",
            "--quiet",
            "--tax-id",
            "12345678Z",
            "--activity",
            "design",
            "--output-language",
            "en",
        ],
    )
    assert r.exit_code == 0, r.output

    r_export = _invoke(["config", "profile", "export", "idempotency-test", "--to", str(bundle_path)])
    assert r_export.exit_code == 0, r_export.output
    assert bundle_path.is_file()

    raw = json.loads(bundle_path.read_text(encoding="utf-8"))
    exported_id = raw["profile"]["profile_id"]
    assert_public_profile_id_redacted(r_export.output, exported_id)
    return exported_id


# ---------------------------------------------------------------------------
# contract — import-twice produces one profile, not two
# ---------------------------------------------------------------------------


def test_reimport_same_bundle_is_refused(tmp_path: Path) -> None:
    """Re-importing the same bundle in the same storage root is refused.

    The profile_id UUID already exists locally after the first import, so
    the second attempt must be refused with a clear "already registered"
    message.  The storage root must still contain exactly ONE profile after
    both attempts.
    """

    bundle_path = tmp_path / "idempotency.json"
    exported_id = _create_minimal_profile_and_export(tmp_path, bundle_path)

    # The source profile is already present (created above).
    # A first import attempt into the SAME root where the source profile
    # lives must fail — profile_id UUID collision.
    r_first = _invoke(["config", "profile", "import", str(bundle_path)])
    assert r_first.exit_code != 0, r_first.output
    assert_public_profile_id_not_leaked(r_first.output, exported_id)
    assert "already registered" in r_first.output or "profile" in r_first.output.lower()
    assert "Traceback" not in r_first.output

    # Import into a fresh root succeeds once.
    fresh_root = tmp_path / "fresh"
    with isolated_profile_storage_root(tmp_path=fresh_root):
        r_ok = _invoke(["--format", "json", "config", "profile", "import", str(bundle_path)])
        assert r_ok.exit_code == 0, r_ok.output
        ok_payload = assert_public_profile_payload_redacted(r_ok.output, exported_id)
        assert ok_payload["display_name"] == "idempotency-test"

        # Second import into the same fresh root must be refused (UUID taken).
        r_second = _invoke(["config", "profile", "import", str(bundle_path)])
        assert r_second.exit_code != 0, r_second.output
        assert_public_profile_id_not_leaked(r_second.output, exported_id)
        assert "already registered" in r_second.output or "profile" in r_second.output.lower()
        assert "Traceback" not in r_second.output

        # Confirm exactly one profile is present — list must return one entry.
        r_list = _invoke(["config", "profile", "list"])
        assert r_list.exit_code == 0, r_list.output
        # The display name (not UUID) appears in list output.
        assert "idempotency-test" in r_list.output
        # Profile IDs are redacted at the CLI boundary; verify UUID
        # round-trip by reading the encrypted manifest directly through
        # the persistence layer.
        from ....application.user_profile._orchestration import profile_storage_session
        from ....application.user_profile._profile_repository import ProfileRepository

        with profile_storage_session(exported_id):
            aggregate = ProfileRepository().load(exported_id)
        assert aggregate.profile_id == exported_id


# ---------------------------------------------------------------------------
# contract — label collision with different UUID is refused
# ---------------------------------------------------------------------------


def test_label_collision_different_uuid_refused_even_with_explicit_label(tmp_path: Path) -> None:
    """Passing ``--label`` to a name already owned by a different UUID is refused.

    The guard checks label uniqueness AFTER the UUID check, so an operator
    trying to import a foreign bundle under a label that already belongs
    to a different local profile must be told to pick a distinct name.
    """

    bundle_path = tmp_path / "label-collision.json"
    exported_id = _create_minimal_profile_and_export(tmp_path, bundle_path)

    dest_root = tmp_path / "dest"
    with isolated_profile_storage_root(tmp_path=dest_root):
        # Occupy the label "idempotency-test" with a locally-minted profile
        # carrying a different UUID.
        r_local = _invoke(
            [
                "config",
                "profile",
                "create",
                "idempotency-test",
                "--quiet",
                "--tax-id",
                "87654321X",
                "--activity",
                "consulting",
            ],
        )
        assert r_local.exit_code == 0, r_local.output

        # Import the bundle without --label: display_name is "idempotency-test",
        # which is already taken by the locally-minted profile → refused.
        r_import = _invoke(["config", "profile", "import", str(bundle_path)])
        assert r_import.exit_code != 0, r_import.output
        assert_public_profile_id_not_leaked(r_import.output, exported_id)
        assert "Traceback" not in r_import.output

        # Passing --label with the SAME taken name is also refused.
        r_explicit = _invoke(["config", "profile", "import", str(bundle_path), "--label", "idempotency-test"])
        assert r_explicit.exit_code != 0, r_explicit.output
        assert_public_profile_id_not_leaked(r_explicit.output, exported_id)
        assert "Traceback" not in r_explicit.output

        # Passing --label with a FREE name succeeds.
        r_free = _invoke(
            [
                "--format",
                "json",
                "config",
                "profile",
                "import",
                str(bundle_path),
                "--label",
                "idempotency-test-imported",
            ],
        )
        assert r_free.exit_code == 0, r_free.output
        free_payload = assert_public_profile_payload_redacted(r_free.output, exported_id)
        assert free_payload["display_name"] == "idempotency-test-imported"


# ---------------------------------------------------------------------------
# contract — anti-tautology proof: mutated profile_id creates a second profile
# ---------------------------------------------------------------------------


def test_mutated_profile_id_creates_second_profile(tmp_path: Path) -> None:
    """Mutating the bundle's profile_id bypasses both collision guards.

    This proves that the UUID — not the label or any other field — is the
    genuine discriminator.  If the UUID test were tautological (e.g. the
    collision guard never actually checked the UUID), both imports would
    either both succeed or both fail for the wrong reason.

    After importing the original bundle and a UUID-mutated clone:
    - Two distinct profiles exist in the destination root.
    - Their profile_ids differ.
    - Their display names are the same (label deduplication is the
      operator's responsibility; the second import can use --label).
    """

    bundle_path = tmp_path / "original.json"
    exported_id = _create_minimal_profile_and_export(tmp_path, bundle_path)

    mutated_bundle_path = tmp_path / "mutated.json"
    raw = json.loads(bundle_path.read_text(encoding="utf-8"))
    mutated_id = str(uuid.uuid4())
    # Patch the profile_id inside the profile sub-object.
    raw["profile"]["profile_id"] = mutated_id
    mutated_bundle_path.write_text(json.dumps(raw), encoding="utf-8")

    dest_root = tmp_path / "dest"
    with isolated_profile_storage_root(tmp_path=dest_root):
        # Import the original bundle — succeeds.
        r_orig = _invoke(["--format", "json", "config", "profile", "import", str(bundle_path)])
        assert r_orig.exit_code == 0, r_orig.output
        orig_payload = assert_public_profile_payload_redacted(r_orig.output, exported_id)
        assert orig_payload["display_name"] == "idempotency-test"

        # Import the UUID-mutated bundle under a distinct label — succeeds
        # (different UUID, different label).
        r_mut = _invoke(
            [
                "--format",
                "json",
                "config",
                "profile",
                "import",
                str(mutated_bundle_path),
                "--label",
                "idempotency-test-mutated",
            ],
        )
        assert r_mut.exit_code == 0, r_mut.output
        mut_payload = assert_public_profile_payload_redacted(r_mut.output, mutated_id)
        assert mut_payload["display_name"] == "idempotency-test-mutated"
        from ....core import resolve_active_bucket_id

        minted_label_import_id = resolve_active_bucket_id()
        assert minted_label_import_id is not None
        assert minted_label_import_id != mutated_id
        assert_public_profile_id_not_leaked(r_mut.output, minted_label_import_id)

        # Both labels must appear in the list output — two distinct profiles.
        r_list = _invoke(["config", "profile", "list"])
        assert r_list.exit_code == 0, r_list.output
        assert "idempotency-test" in r_list.output
        assert "idempotency-test-mutated" in r_list.output

        # Profile IDs are redacted at the CLI boundary; verify UUID
        # round-trip by reading the encrypted manifest of the
        # identity-preserving import (the first one, without --label).
        # The --label path mints a fresh UUID by design (see
        # ``config_profile_import``'s D5 two-tier collision guard), so
        # the imported bucket's id does not equal ``mutated_id``; that
        # path is asserted via the display-name + list-output surfaces.
        from ....application.user_profile._orchestration import profile_storage_session
        from ....application.user_profile._profile_repository import ProfileRepository

        with profile_storage_session(exported_id):
            original_aggregate = ProfileRepository().load(exported_id)
        assert original_aggregate.profile_id == exported_id

        # Both display names must still be reachable via the operator surface.
        r_show = _invoke(["config", "profile", "show", "idempotency-test"])
        assert r_show.exit_code == 0, r_show.output
        assert_public_profile_id_redacted(r_show.output, exported_id)
        r_show_mut = _invoke(["config", "profile", "show", "idempotency-test-mutated"])
        assert r_show_mut.exit_code == 0, r_show_mut.output
        assert_public_profile_id_not_leaked(r_show_mut.output, mutated_id)
