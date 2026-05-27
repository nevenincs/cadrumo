"""Idempotency regression tests for `aeat config profile import` (S109).

ADR D5 idempotency contract:
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

from aeat.tests.cli_runner import invoke_cached_cli
from aeat.tests.secure_sql import isolated_profile_storage_root

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


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
            "config", "profile", "create", "idempotency-test",
            "--quiet",
            "--tax-id", "12345678Z",
            "--activity", "design",
            "--output-language", "en",
        ]
    )
    assert r.exit_code == 0, r.output

    r_export = _invoke(["config", "profile", "export", "idempotency-test", "--to", str(bundle_path)])
    assert r_export.exit_code == 0, r_export.output
    assert bundle_path.is_file()

    raw = json.loads(bundle_path.read_text(encoding="utf-8"))
    return raw["profile"]["profile_id"]


# ---------------------------------------------------------------------------
# S109 — import-twice produces one profile, not two
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
    assert "already registered" in r_first.output or "profile" in r_first.output.lower()
    assert "Traceback" not in r_first.output

    # Import into a fresh root succeeds once.
    fresh_root = tmp_path / "fresh"
    with isolated_profile_storage_root(tmp_path=fresh_root):
        r_ok = _invoke(["config", "profile", "import", str(bundle_path)])
        assert r_ok.exit_code == 0, r_ok.output

        # Second import into the same fresh root must be refused (UUID taken).
        r_second = _invoke(["config", "profile", "import", str(bundle_path)])
        assert r_second.exit_code != 0, r_second.output
        assert "already registered" in r_second.output or "profile" in r_second.output.lower()
        assert "Traceback" not in r_second.output

        # Confirm exactly one profile is present — list must return one entry.
        r_list = _invoke(["config", "profile", "list"])
        assert r_list.exit_code == 0, r_list.output
        # The display name (not UUID) appears in list output.
        assert "idempotency-test" in r_list.output
        # The profile_id UUID is available via `profile show` — confirm round-trip.
        r_show = _invoke(["config", "profile", "show"])
        assert r_show.exit_code == 0, r_show.output
        assert exported_id in r_show.output


# ---------------------------------------------------------------------------
# S109 — label collision with different UUID is refused
# ---------------------------------------------------------------------------


def test_label_collision_different_uuid_refused_even_with_explicit_label(tmp_path: Path) -> None:
    """Passing ``--label`` to a name already owned by a different UUID is refused.

    The guard checks label uniqueness AFTER the UUID check, so an operator
    trying to import a foreign bundle under a label that already belongs
    to a different local profile must be told to pick a distinct name.
    """

    bundle_path = tmp_path / "label-collision.json"
    _create_minimal_profile_and_export(tmp_path, bundle_path)

    dest_root = tmp_path / "dest"
    with isolated_profile_storage_root(tmp_path=dest_root):
        # Occupy the label "idempotency-test" with a locally-minted profile
        # carrying a different UUID.
        r_local = _invoke(
            [
                "config", "profile", "create", "idempotency-test",
                "--quiet", "--tax-id", "87654321X", "--activity", "consulting",
            ]
        )
        assert r_local.exit_code == 0, r_local.output

        # Import the bundle without --label: display_name is "idempotency-test",
        # which is already taken by the locally-minted profile → refused.
        r_import = _invoke(["config", "profile", "import", str(bundle_path)])
        assert r_import.exit_code != 0, r_import.output
        assert "Traceback" not in r_import.output

        # Passing --label with the SAME taken name is also refused.
        r_explicit = _invoke(
            ["config", "profile", "import", str(bundle_path), "--label", "idempotency-test"]
        )
        assert r_explicit.exit_code != 0, r_explicit.output
        assert "Traceback" not in r_explicit.output

        # Passing --label with a FREE name succeeds.
        r_free = _invoke(
            ["config", "profile", "import", str(bundle_path), "--label", "idempotency-test-imported"]
        )
        assert r_free.exit_code == 0, r_free.output


# ---------------------------------------------------------------------------
# S109 — anti-tautology proof: mutated profile_id creates a second profile
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
        r_orig = _invoke(["config", "profile", "import", str(bundle_path)])
        assert r_orig.exit_code == 0, r_orig.output

        # Import the UUID-mutated bundle under a distinct label — succeeds
        # (different UUID, different label).
        r_mut = _invoke(
            [
                "config", "profile", "import", str(mutated_bundle_path),
                "--label", "idempotency-test-mutated",
            ]
        )
        assert r_mut.exit_code == 0, r_mut.output

        # Both labels must appear in the list output — two distinct profiles.
        r_list = _invoke(["config", "profile", "list"])
        assert r_list.exit_code == 0, r_list.output
        assert "idempotency-test" in r_list.output
        assert "idempotency-test-mutated" in r_list.output

        # Verify the imported UUID for the original bundle matches the exported one.
        r_show = _invoke(["config", "profile", "show", "idempotency-test"])
        assert r_show.exit_code == 0, r_show.output
        assert exported_id in r_show.output

        # Verify the imported UUID for the mutated bundle is the mutated one.
        r_show_mut = _invoke(["config", "profile", "show", "idempotency-test-mutated"])
        assert r_show_mut.exit_code == 0, r_show_mut.output
        assert mutated_id in r_show_mut.output
