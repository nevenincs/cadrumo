"""The state tree is built on request, not as a side effect of writing to it.

Before this, directories in the derived-output taxonomy appeared only when
some consumer happened to write one: the local provider made its root on
first write, the journal repository made its own, bucket provisioning made a
bucket's. A caller could not ask for the tree, and a fresh machine held
whichever subset had been reached.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ..config import ensure_storage_tree, load_settings, override_settings
from ..errors import CoreValidationError

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_it_builds_the_tree_and_returns_the_root(tmp_path: Path) -> None:
    """A clean root comes back existing, with the declared directories under it."""
    root = tmp_path / "state"
    assert not root.exists(), "the fixture must start absent, or this proves nothing"

    with override_settings(cadrumo_local_storage_root=root):
        returned = ensure_storage_tree()

    assert returned == root
    assert root.is_dir()
    # The taxonomy is broad rather than a couple of directories; assert a few
    # of its distinct lifecycle groups rather than a count that would have to
    # be edited every time the taxonomy grows.
    for expected in ("tokens", "secrets", "blobs", "audit", "logs", "cache", "drafts"):
        assert (root / expected).is_dir(), f"{expected} was not materialised"


def test_calling_it_again_is_a_no_op(tmp_path: Path) -> None:
    """Idempotent, so a caller may ask without first checking."""
    root = tmp_path / "state"
    with override_settings(cadrumo_local_storage_root=root):
        first = ensure_storage_tree()
        (first / "tokens" / "sentinel").write_text("kept", encoding="utf-8")
        second = ensure_storage_tree()

    assert first == second
    assert (root / "tokens" / "sentinel").read_text(encoding="utf-8") == "kept", (
        "a second call must not disturb what the first one left"
    )


def test_a_file_valued_setting_gets_its_parent_not_a_directory(tmp_path: Path) -> None:
    """One entry in the taxonomy names a JSON file, not a directory.

    Creating the leaf would put a directory exactly where the document has to
    be written, and the failure would surface much later at the write.
    """
    root = tmp_path / "state"
    with override_settings(cadrumo_local_storage_root=root):
        ensure_storage_tree()
        ratios = Path(load_settings().cadrumo_usage_ratios_path)

    assert ratios.parent.is_dir(), "the file's directory must exist"
    assert not ratios.exists(), "the file itself must not be created"


def test_it_refuses_when_a_file_occupies_a_directory_path(tmp_path: Path) -> None:
    """A file sitting where a directory belongs is named, not worked around.

    Proving the refusal fires matters more than proving the happy path: a
    half-built tree reports success and fails later, somewhere else.
    """
    root = tmp_path / "state"
    root.mkdir()
    (root / "tokens").write_text("not a directory", encoding="utf-8")

    with override_settings(cadrumo_local_storage_root=root), pytest.raises(CoreValidationError) as refusal:
        ensure_storage_tree()

    message = str(refusal.value)
    assert "tokens" in message, "the refusal must name the offending path"
    # Asserting the diagnosis, not merely the exception type. ``mkdir`` would
    # raise ``FileExistsError`` here on its own, and the generic
    # could-not-create handler would re-raise it as the same exception naming
    # the same path -- so a test that stopped at the type and the path passed
    # identically with the check deleted, and proved nothing about it. What
    # the check earns is telling the operator WHY: a file is sitting where a
    # directory belongs.
    assert "occupied by a file" in message, "the refusal must diagnose the occupancy, not just report a failed mkdir"


def test_the_refusal_probe_would_otherwise_succeed(tmp_path: Path) -> None:
    """Positive control for the test above.

    Without the occupying file the same call succeeds, so that test is
    demonstrating the refusal rather than some unrelated breakage.
    """
    root = tmp_path / "state"
    root.mkdir()

    with override_settings(cadrumo_local_storage_root=root):
        assert ensure_storage_tree() == root
