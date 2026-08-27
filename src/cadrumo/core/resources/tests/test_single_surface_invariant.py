"""Structural guard: resources() is the only resource-access surface.

The resource-management API contract mandates a single resource-access
boundary at ``src/cadrumo/core/resources/``. This test enforces the
invariant by scanning every production module under ``src/cadrumo/``
for unauthorised parallel-locator patterns.

Allow-listed exceptions:

* Files under ``src/cadrumo/core/resources/`` define the boundary itself.
* Tests (``test_*.py``, ``_test_*.py``, ``conftest.py``) may use
  ``bundled_path`` directly to verify the bundled data-tree SHAPE
  rather than the Repository surface, as documented in the plan's
  Proposed Changes section.
* The corpus-registry-packaging wheel guard
  (``src/cadrumo/tests/test_wheel_bundles_corpus_and_registry.py``)
  legitimately greps the data tree.

See Also:
    :func:`~core.resources.resources`
        Canonical repository factory that production code must use for bundled
        resource access.
    :func:`~core.resources.bundled_path`
        Lower-level bundled-data path helper allowed only at the resource
        boundary and in shape-verification tests.
    :func:`~tests._inventory.production_python_files`
        Shared production source inventory scanned for parallel resource
        locator constants.
"""

from __future__ import annotations

import pathlib
import re
from pathlib import Path

import pytest

from ....tests import SRC_CADRUMO, package_python_files, production_python_files, repo_path, repo_relative

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_RESOURCES_PKG = SRC_CADRUMO / "core" / "resources"


def _is_production_module(path: Path) -> bool:
    """Production = .py file not under resources/, not a test, not conftest."""
    if path.suffix != ".py":
        return False
    if path.is_relative_to(_RESOURCES_PKG):
        return False
    name = path.name
    if name == "conftest.py":
        return False
    return not (name.startswith("test_") or name.startswith("_test_"))


def _production_files() -> list[Path]:
    return sorted(p for p in production_python_files() if _is_production_module(p))


_PENDING_RETIREMENT_ALLOWLIST: frozenset[Path] = frozenset[Path]()
"""Allow-list of files allowed to declare a ``_DEFAULT_*_ROOT`` constant.

The allow-list is empty: every production module under
``src/cadrumo/`` routes resource resolution through
``cadrumo.core.resources`` exclusively. The companion test
:func:`test_allowlist_only_contains_files_that_actually_offend`
enforces that the allow-list cannot grow without the addition
of a corresponding offending constant; the structural guard
proper enforces that no file outside this set defines such a
constant.
"""


def test_no_default_root_constants_in_production() -> None:
    """No production module outside the allow-list defines a
    ``_DEFAULT_*_ROOT`` constant via :func:`bundled_path`.

    The allow-list ratchets down as P09 retirement lands; the
    final structural invariant is that no production file outside
    ``src/cadrumo/core/resources/`` defines such a constant.
    """

    pattern = re.compile(r"^_DEFAULT_[A-Z_]+_ROOT\s*=\s*bundled_path", re.MULTILINE)
    offenders: list[str] = []
    for path in _production_files():
        rel = repo_relative(path)
        # Normalise on POSIX-style separators so allow-list checks
        # work on Windows too.
        normalised = Path(rel)
        if normalised in _PENDING_RETIREMENT_ALLOWLIST:
            continue
        text = path.read_text(encoding="utf-8")
        if pattern.search(text):
            offenders.append(rel)
    assert not offenders, (
        "production files outside the allow-list defining "
        "_DEFAULT_*_ROOT = bundled_path(...) found; these must "
        f"route through cadrumo.core.resources.resources() instead: {offenders}"
    )


def test_allowlist_only_contains_files_that_actually_offend() -> None:
    """Every allow-list entry must still contain a _DEFAULT_*_ROOT
    definition; the moment a file is cleaned up its allow-list slot
    must be removed.
    """

    pattern = re.compile(r"^_DEFAULT_[A-Z_]+_ROOT\s*=\s*bundled_path", re.MULTILINE)
    stale: list[str] = []
    for rel in _PENDING_RETIREMENT_ALLOWLIST:
        absolute = repo_path(rel.as_posix())
        if not absolute.is_file():
            stale.append(f"{rel} (file missing)")
            continue
        text = absolute.read_text(encoding="utf-8")
        if not pattern.search(text):
            stale.append(f"{rel} (no _DEFAULT_*_ROOT remains)")
    assert not stale, f"the pending-retirement allow-list contains entries that no longer offend; remove them: {stale}"


_FILE_WALK_RE = re.compile(
    r"Path\(__file__\)\.resolve\(\)((?:\.parent)+)|Path\(__file__\)\.resolve\(\)\.parents\[(\d+)\]",
)

_SANCTIONED_CHECKOUT_ROOT_OWNERS: frozenset[str] = frozenset[str]()
"""Deliberately empty: NO production module may reconstruct a repository root.

This once exempted ``core/_config_state_root.py``, which classified the run as
a checkout or an installed distribution by probing for ``pyproject.toml`` and
``.git`` and anchored the taxpayer's encrypted store accordingly. That is gone:
the storage root is unconditionally the platform user-data directory, and a
developer redirects it with ``CADRUMO_LOCAL_STORAGE_ROOT`` like any other
operator override. A tax-filing product does not inspect the filesystem to work
out how it was installed, so there is no module left with a reason to be here.
Adding an entry back means a production module has started asking about
repositories again — treat that as the finding, not as a configuration step.
"""


def test_no_production_module_walks_out_of_the_package() -> None:
    """No production module may walk ``__file__`` out of the ``cadrumo`` package.

    Cadrumo ships as an installed application: at runtime there is no
    repository and no "project", only an application data root. Walking
    far enough up from ``__file__`` to escape the package reconstructs a
    source-checkout layout, which on an installed build lands in
    ``site-packages`` — or inside a packaging tool's ephemeral cache,
    where a prune can destroy whatever was written there. That is exactly
    the hazard :mod:`cadrumo.core._config_state_root` exists to close, so
    precisely one module may compute it, behind ``RunMode.CHECKOUT``.

    Walking *within* the package is fine and is NOT flagged: a wheel ships
    ``cadrumo/``'s own modules, so e.g. ``application/wizard`` reaching
    ``entrypoints/cli`` resolves correctly in every run mode. The gate is
    therefore depth-aware — it compares hop count against how deep the
    file sits — rather than banning ``__file__`` arithmetic outright.

    This is an eradication ratchet. It replaced a guard that policed
    *unused* ``PROJECT_ROOT`` imports, which turned vacuous the moment the
    constant was deleted; the property still worth defending is that the
    concept never comes back.
    """
    offenders: list[str] = []
    for path in package_python_files(include_data=True):
        rel = repo_relative(path)
        if rel in _SANCTIONED_CHECKOUT_ROOT_OWNERS or "/tests/" in rel:
            continue
        # Depth inside the package: src/cadrumo/a/b/mod.py sits 2 dirs below the
        # root, so depth+1 hops reach `cadrumo/` itself and anything beyond escapes.
        depth = len(pathlib.PurePosixPath(rel).parts) - 3
        for match in _FILE_WALK_RE.finditer(path.read_text(encoding="utf-8")):
            hops = match.group(1).count(".parent") if match.group(1) else int(match.group(2)) + 1
            if hops > depth + 1:
                offenders.append(f"{rel} (walks {hops} up from depth {depth})")
    assert not offenders, (
        "production modules walking __file__ out of the cadrumo package "
        "(resolve operator paths through the application data root instead — "
        f"Settings.cadrumo_local_storage_root): {offenders}"
    )


def test_resources_package_re_exports_boundary() -> None:
    """The boundary functions stay accessible through the package init."""

    from .. import as_path, bundled_path, packaged_data, resources

    assert packaged_data is not None
    assert bundled_path is not None
    assert as_path is not None
    assert resources is not None
