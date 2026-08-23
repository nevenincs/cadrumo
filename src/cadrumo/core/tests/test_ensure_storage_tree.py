"""The state tree is built on request, not as a side effect of writing to it.

Before this, directories in the derived-output taxonomy appeared only when
some consumer happened to write one: the local provider made its root on
first write, the journal repository made its own, bucket provisioning made a
bucket's. A caller could not ask for the tree, and a fresh machine held
whichever subset had been reached.

The directory names asserted below are deliberate literals. What this module
defends is that bootstrap *materialises* the declared tree on disk, so the
expectation must come from outside the declaration: resolving it through the
accessor would assert that whatever the taxonomy declares is whatever
bootstrap created, which holds even if bootstrap created nothing of the sort.
A renamed subpath **should** red these assertions.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path
from typing import Final

import pytest

from .. import iter_directory
from ..config import load_settings, override_settings
from ..errors import CoreValidationError
from ..storage_materialization import ensure_storage_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

PINNED_TAXONOMY_LITERALS: Final[frozenset[str]] = frozenset(
    {"tokens", "secrets", "blobs", "live-state", "logs", "cache", "drafts"},
)
"""Taxonomy-vocabulary literals this module deliberately pins. See the module docstring."""


def test_settings_and_derived_path_reads_do_not_materialise_storage(tmp_path: Path) -> None:
    """Reading configuration computes paths without creating their topology."""
    root = tmp_path / "read-only-state"

    with override_settings(cadrumo_local_storage_root=root):
        settings = load_settings()
        assert settings.cadrumo_token_dir == root / "tokens"
        assert settings.cadrumo_log_dir == root / "logs"

    assert not root.exists(), "settings/path resolution crossed the explicit materialization boundary"


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
    for expected in ("tokens", "secrets", "blobs", "live-state", "logs", "cache", "drafts"):
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

    context = refusal.value.context or {}
    assert "tokens" in str(context["state_directory_target"]), "the refusal must name the offending path"
    # Asserting the diagnosis, not merely the exception type. ``mkdir`` would
    # raise ``FileExistsError`` here on its own, and the generic
    # could-not-create handler would re-raise it as the same exception naming
    # the same path -- so a test that stopped at the type and the path passed
    # identically with the check deleted, and proved nothing about it. What
    # the check earns is telling the operator WHY: a file is sitting where a
    # directory belongs. The refusal is catalogue-rendered, so that WHY is the
    # ``occupied_by_file`` fact rather than a phrase inside a sentence, and the
    # mkdir-failure branch carries it as ``False`` alongside its ``OSError``
    # type -- the two branches stay distinguishable without any prose.
    assert context["occupied_by_file"] is True, (
        "the refusal must diagnose the occupancy, not just report a failed mkdir"
    )
    assert "mkdir_error_type" not in context, "the occupancy branch must not be reached through the mkdir handler"


def test_the_refusal_probe_would_otherwise_succeed(tmp_path: Path) -> None:
    """Positive control for the test above.

    Without the occupying file the same call succeeds, so that test is
    demonstrating the refusal rather than some unrelated breakage.
    """
    root = tmp_path / "state"
    root.mkdir()

    with override_settings(cadrumo_local_storage_root=root):
        assert ensure_storage_tree() == root


def test_the_root_is_restricted_to_its_owner(tmp_path: Path) -> None:
    """The tree holds encrypted records, the keys that open them, and the state over both.

    Nothing asserted these bits before, so a refactor restructuring the
    materialiser could have dropped the hardening in silence -- every other
    test would keep passing, because a world-readable directory works exactly
    as well as a private one until someone reads it.

    The mode assertion is guarded rather than skipped: hosts without POSIX
    modes still exercise everything above it, and the guard carries its own
    positive control so the assertion cannot pass vacuously where it does run.
    Loosening the bits afterwards must break the same comparison -- otherwise a
    platform that accepted ``chmod`` and ignored it would read as hardened.
    """
    root = tmp_path / "state"

    with override_settings(cadrumo_local_storage_root=root):
        ensure_storage_tree()

    assert root.is_dir()
    if os.name != "nt":
        assert stat.S_IMODE(root.stat().st_mode) == 0o700
        root.chmod(0o755)
        assert stat.S_IMODE(root.stat().st_mode) != 0o700, (
            "the platform accepted a mode change without applying it, so the assertion above proves nothing"
        )


def test_a_directory_removed_after_materialisation_is_rebuilt(tmp_path: Path) -> None:
    """A gap that opens after the first call is closed by the next one.

    The materialiser skips a target it finds already present, which is what
    makes the warm path cheap. That skip must key on what the filesystem says
    NOW, not on having run before -- otherwise a directory removed between
    invocations (a cleanup script, an operator tidying a cache, an
    interrupted uninstall) would never come back, and the gap would surface
    much later at a write.
    """
    with override_settings(cadrumo_local_storage_root=tmp_path / "state"):
        settings = load_settings()
        root = ensure_storage_tree(settings)

        from .._storage_taxonomy import storage_tree_targets

        removable = next(
            target
            for target in storage_tree_targets(settings)
            if target.is_dir() and target != root and not any(iter_directory(target))
        )
        removable.rmdir()
        assert not removable.exists()

        ensure_storage_tree(settings)
        assert removable.is_dir(), "a directory removed after the first call must be rebuilt"


def test_the_warm_tree_costs_no_mkdir(tmp_path: Path) -> None:
    """Re-materialising an intact tree must not re-issue creation calls.

    Every CLI invocation runs this over the whole taxonomy, so the
    already-built case is the one that matters. It used to ask three
    questions per target -- exists, then is_dir, then an unconditional mkdir
    that re-walked the path -- which is why this pins the absence of the
    third rather than a duration: a timing would measure the machine, while
    a mkdir on a directory that is already there is the waste itself.
    """
    with override_settings(cadrumo_local_storage_root=tmp_path / "state"):
        settings = load_settings()
        ensure_storage_tree(settings)

        created: list[Path] = []
        real_mkdir = Path.mkdir

        def counting_mkdir(self, *args, **kwargs):
            created.append(self)
            return real_mkdir(self, *args, **kwargs)

        Path.mkdir = counting_mkdir  # type: ignore[method-assign]
        try:
            ensure_storage_tree(settings)
        finally:
            Path.mkdir = real_mkdir  # type: ignore[method-assign]

        assert created == [], f"an intact tree issued {len(created)} mkdir call(s): {created[:3]}"


def test_the_warm_probe_would_catch_a_regression(tmp_path: Path) -> None:
    """Positive control for the test above.

    The same counter, over a tree that does NOT yet exist, must record the
    creations -- otherwise an empty list would prove only that the probe
    never ran.
    """
    with override_settings(cadrumo_local_storage_root=tmp_path / "fresh"):
        settings = load_settings()

        created: list[Path] = []
        real_mkdir = Path.mkdir

        def counting_mkdir(self, *args, **kwargs):
            created.append(self)
            return real_mkdir(self, *args, **kwargs)

        Path.mkdir = counting_mkdir  # type: ignore[method-assign]
        try:
            ensure_storage_tree(settings)
        finally:
            Path.mkdir = real_mkdir  # type: ignore[method-assign]

        assert created, "the probe records nothing even on a fresh tree; it cannot catch a regression"
