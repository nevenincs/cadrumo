"""The tree on disk is the taxonomy's member set, and nothing else.

The materialiser used to be able to drift from the declaration in two
directions, and neither moved a test. A declared member it never created left
a fresh machine holding whichever subset of the tree some consumer had
happened to write. A directory it created from a list of its own put a
location outside the declaration entirely -- the very defect a typed authority
exists to make impossible.

The sibling module proves the materialiser *works*: it builds a tree, it is
idempotent, it refuses an occupied path, it restricts the root. This one proves
the tree it builds is the declared one. The oracle is the filesystem, walked
after the fact, compared against an expectation derived from
:data:`~core.storage_taxonomy.STORAGE_TAXONOMY`. Building the expectation by
calling the same iteration the materialiser calls would assert nothing at all.

Parity is asserted in both directions, because each catches a different defect:

- **Nothing declared is missing.** A member the materialiser skips.
- **Nothing on disk is unexplained.** Every directory under the root is a
  declared target, an ancestor of one, or the root itself. Intermediate
  segments (``cache``, ``financial``, ``audit/registry``) are ancestors and
  legitimate; a directory that is neither is the materialiser carrying a second
  list.

The file-versus-directory distinction gets its own assertion rather than
riding the set comparison, because getting it wrong is silent in exactly the
way the set comparison cannot see: a file member's leaf created as a directory
still leaves the parent present, so parity holds while a directory sits
precisely where a document must be written. That failure surfaces much later,
at the write, far from its cause.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

import pytest

from ..storage_taxonomy import (
    STORAGE_TAXONOMY,
    StorageCategory,
    StorageLocation,
    StorageNodeKind,
    StorageScope,
)
from ..config import Settings, load_settings, override_settings
from ..directory_scan import DirectoryEntryKind, scan_directory
from ..storage_materialization import ensure_storage_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

PINNED_TAXONOMY_LITERALS: Final[frozenset[str]] = frozenset({"financial", "cache", "invoices", "llm-cache"})
"""Taxonomy-vocabulary literals this module deliberately pins.

``"financial"`` and ``"cache"`` in the ancestor-detector tests
(``test_the_unexplained_detector_accepts_ancestors_and_the_root`` and its
sibling) are the example intermediate-segment shapes the detector must treat
as ancestors rather than findings; the module's own docstring names both
explicitly as ancestors this parity check must not misclassify. ``"invoices"``
and ``"llm-cache"`` are the leaf members under those two ancestors in the same
two tests (``root / "cache" / "llm-cache"``, ``root / "financial" /
"invoices"``), completing the same fixture shapes rather than a separate pin.
"""


def _materialisable_members() -> tuple[StorageLocation, ...]:
    """Root-scoped members that name a settings field, in declaration order.

    Members with no field are fixed layout the bucket lifecycle provisions per
    bucket, so the root tree is not where they appear.
    """
    return tuple(
        location
        for location in STORAGE_TAXONOMY.values()
        if location.scope is StorageScope.ROOT and location.settings_field is not None
    )


def expected_directories(settings: Settings) -> dict[Path, str]:
    """Return each directory the declaration requires, mapped to its member name.

    A directory member contributes itself. A file member contributes its parent
    and explicitly **not** its leaf. A member whose field resolves to ``None``
    is an opt-in location the operator has not asked for and contributes
    nothing.

    Derived from the declaration and compared against disk, never against the
    materialiser's own target list.
    """
    expected: dict[Path, str] = {}
    for location in _materialisable_members():
        assert location.settings_field is not None
        value = getattr(settings, location.settings_field, None)
        if value is None:
            continue
        resolved = Path(value)
        target = resolved.parent if location.node_kind is StorageNodeKind.FILE else resolved
        expected[target] = location.category.value
    return expected


def unexplained_directories(observed: set[Path], expected: set[Path], root: Path) -> tuple[Path, ...]:
    """Return observed directories that no declared target explains.

    A directory is explained when it is the root, a declared target, or an
    ancestor of one -- ``cache`` exists because ``cache/llm-cache`` does.
    Anything else was created from somewhere other than the declaration.
    """
    explained = {root}
    for target in expected:
        explained.add(target)
        explained.update(target.parents)
    return tuple(sorted(directory for directory in observed if directory not in explained))


def _observed_directories(root: Path) -> set[Path]:
    return set(scan_directory(root, recursive=True, select=DirectoryEntryKind.DIRECTORIES))


@pytest.fixture
def materialised(tmp_path: Path) -> tuple[Path, Settings]:
    """Build the tree once under a private root and hand back the settings used."""
    root = tmp_path / "state"
    assert not root.exists(), "the fixture must start absent, or this proves nothing"
    with override_settings(cadrumo_local_storage_root=root):
        ensure_storage_tree()
        settings = load_settings()
    return root, settings


def test_the_declared_and_observed_sets_are_both_non_degenerate(
    materialised: tuple[Path, Settings],
) -> None:
    """Two empty sets agree, so both sides must be shown to be real.

    Every comparison below is an equality between a declaration-derived
    expectation and observed disk state. If the taxonomy collapsed, or the
    materialiser stopped creating anything, the two would agree perfectly and
    the parity assertions would certify a tree that does not exist. Bounds
    rather than counts, so the floor does not rot on the next member.
    """
    root, settings = materialised
    expected = expected_directories(settings)
    observed = _observed_directories(root)

    assert len(expected) >= 20, (
        f"the declaration produced only {len(expected)} expected director(ies): {sorted(expected)}. "
        "The taxonomy declares dozens of root-derived members, so this means discovery collapsed "
        "and the parity comparisons below would hold vacuously"
    )
    assert len(observed) >= 20, (
        f"the materialiser created only {len(observed)} director(y/ies) under {root}. Parity "
        "against an empty tree is not parity"
    )


def test_every_declared_directory_exists_on_disk(materialised: tuple[Path, Settings]) -> None:
    """A member the materialiser skips fails here, named by its category."""
    root, settings = materialised
    expected = expected_directories(settings)
    assert expected, "the declaration produced no directories; discovery, not the tree, is broken"

    missing = sorted(f"{name} at {path}" for path, name in expected.items() if not path.is_dir())
    assert not missing, (
        f"storage taxonomy member(s) declared but never materialised: {missing}. The materialiser "
        "derives its targets from the declaration, so a gap here means a member is excluded from "
        "that derivation -- a fresh machine would hold every other directory and not this one, and "
        f"the absence would surface at the first write beneath {root}"
    )


def test_no_directory_on_disk_is_unexplained(materialised: tuple[Path, Settings]) -> None:
    """A directory outside the declaration means a second list is in play."""
    root, settings = materialised
    unexplained = unexplained_directories(_observed_directories(root), set(expected_directories(settings)), root)
    assert not unexplained, (
        f"directories exist under the storage root that no declared member explains: "
        f"{[str(path) for path in unexplained]}. Every application-chosen segment is governed by "
        "the taxonomy, not only the top of each category, so declare the location as a member "
        "rather than creating it alongside the declared tree"
    )


def test_a_file_members_leaf_is_never_created_as_a_directory(materialised: tuple[Path, Settings]) -> None:
    """The parent is created; the leaf is left for the document.

    Separate from the set comparison on purpose. Creating the leaf leaves the
    parent present too, so parity would still hold while a directory sat
    exactly where the document must be written.
    """
    root, settings = materialised
    file_members = [
        location
        for location in _materialisable_members()
        if location.node_kind is StorageNodeKind.FILE and getattr(settings, location.settings_field or "", None)
    ]
    assert file_members, (
        "no file-valued root member resolved, so this assertion covers nothing. The taxonomy "
        "declares at least one (the usage-ratios document); if that changed, this gate needs "
        "re-pointing rather than deleting"
    )

    for location in file_members:
        assert location.settings_field is not None
        leaf = Path(getattr(settings, location.settings_field))
        assert leaf.parent.is_dir(), f"{location.category.value}: the document's directory must exist under {root}"
        assert not leaf.is_dir(), (
            f"{location.category.value}: a directory was created at {leaf}, which is where the "
            "document itself must be written. The node kind is a declared field precisely so this "
            "cannot be guessed from a name suffix"
        )
        assert not leaf.exists(), f"{location.category.value}: the materialiser must not create the document"


def test_the_usage_ratios_document_is_declared_a_file() -> None:
    """The node kind of a document is a property of what it is, and is pinned.

    Nothing else asserted this. Flipping it to ``DIRECTORY`` would make the
    materialiser create a directory at the document's own path, and the
    assertion above would then report that no file member resolved rather than
    naming the cause. The usage-ratios entry is a single JSON document holding
    one entry per category -- it is a file the way a manifest is a file, not by
    convention of its field name -- so the declaration is pinned against the
    artefact rather than restated from the taxonomy.
    """
    location = STORAGE_TAXONOMY[StorageCategory.USAGE_RATIOS]
    assert location.node_kind is StorageNodeKind.FILE, (
        "the usage-ratios entry is a JSON document, not a directory; declaring it a directory "
        "puts a directory exactly where the document must be written"
    )
    assert not location.subpath.endswith("/")


def test_an_opt_in_member_with_no_value_is_not_materialised(materialised: tuple[Path, Settings]) -> None:
    """A location the operator has not asked for is absent, and that is parity.

    The registry disk cache is the worked case: its name is taxonomy-governed
    while its field is deliberately not derived, because the resolver selects
    its shared-temporary branch by observing the field is unset. Materialising
    it would retire that branch by side effect.
    """
    root, settings = materialised
    unset = [
        location
        for location in _materialisable_members()
        if getattr(settings, location.settings_field or "", None) is None
    ]
    assert unset, (
        "no root member resolved to None, so this control covers nothing; the taxonomy declares "
        "at least one opt-in member whose field is deliberately not derived"
    )

    for location in unset:
        subpath = root / location.relative_path()
        assert not subpath.exists(), (
            f"{location.category.value} resolved to None yet {subpath} was created; an opt-in "
            "location must stay absent until the operator asks for it"
        )
    # And its absence must not read as a parity failure.
    assert not unexplained_directories(_observed_directories(root), set(expected_directories(settings)), root)


def test_parity_survives_a_second_call_and_preserves_what_was_written(
    materialised: tuple[Path, Settings],
) -> None:
    """Idempotence, asserted as parity rather than as a bare no-op.

    The control against a "clean state" implementation: a materialiser that
    removed and recreated the tree would satisfy every set comparison above on
    the second call and destroy the taxpayer's data doing it.
    """
    root, settings = materialised
    expected = expected_directories(settings)
    sentinel = next(iter(sorted(expected))) / "sentinel.txt"
    sentinel.write_text("kept", encoding="utf-8")

    with override_settings(cadrumo_local_storage_root=root):
        ensure_storage_tree()

    assert sentinel.read_text(encoding="utf-8") == "kept", (
        "a second call destroyed content the first call's tree held; materialisation preserves "
        "existing content and may never remove-and-recreate for a clean state"
    )
    assert not [path for path in expected if not path.is_dir()]
    assert not unexplained_directories(_observed_directories(root), set(expected), root)


# --------------------------------------------------------------------- #
# Discrimination: each comparison fires on its own defect                #
# --------------------------------------------------------------------- #


def test_the_unexplained_detector_fires_on_a_directory_outside_the_declaration() -> None:
    """A second list shows up as a directory nothing declares."""
    root = Path("/state")
    expected = {root / "cache" / "llm-cache"}
    observed = {root / "cache", root / "cache" / "llm-cache", root / "scratch"}
    assert unexplained_directories(observed, expected, root) == (root / "scratch",)


def test_the_unexplained_detector_accepts_ancestors_and_the_root() -> None:
    """The control: intermediate segments are explained, not findings.

    Without this the detector would flag ``cache`` and ``financial`` on every
    run, and a gate that reddens on everything is as useless as one that never
    reddens.
    """
    root = Path("/state")
    expected = {root / "cache" / "llm-cache", root / "financial" / "invoices"}
    observed = {root, root / "cache", root / "cache" / "llm-cache", root / "financial", root / "financial" / "invoices"}
    assert unexplained_directories(observed, expected, root) == ()
