"""Structural guard: resources() is the only resource-access surface.

The resource-management API contract mandates a single resource-access
boundary at ``src/aeat/core/resources/``. This test enforces the
invariant by scanning every production module under ``src/aeat/``
for unauthorised parallel-locator patterns.

Allow-listed exceptions:

* Files under ``src/aeat/core/resources/`` define the boundary itself.
* Tests (``test_*.py``, ``_test_*.py``, ``conftest.py``) may use
  ``bundled_path`` directly to verify the bundled data-tree SHAPE
  rather than the Repository surface, as documented in the plan's
  Proposed Changes section.
* The corpus-registry-packaging wheel guard
  (``src/aeat/tests/test_wheel_bundles_corpus_and_registry.py``)
  legitimately greps the data tree.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_REPO_ROOT = Path(__file__).resolve().parents[4]
_SRC = _REPO_ROOT / "src" / "aeat"
_RESOURCES_PKG = _SRC / "core" / "resources"


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
    return sorted(p for p in _SRC.rglob("*.py") if _is_production_module(p))


_PENDING_RETIREMENT_ALLOWLIST: frozenset[Path] = frozenset()
"""Allow-list of files allowed to declare a ``_DEFAULT_*_ROOT`` constant.

The allow-list is empty: every production module under
``src/aeat/`` routes resource resolution through
``aeat.core.resources`` exclusively. The companion test
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
    ``src/aeat/core/resources/`` defines such a constant.
    """

    pattern = re.compile(r"^_DEFAULT_[A-Z_]+_ROOT\s*=\s*bundled_path", re.MULTILINE)
    offenders: list[str] = []
    for path in _production_files():
        rel = path.relative_to(_REPO_ROOT)
        # Normalise on POSIX-style separators so allow-list checks
        # work on Windows too.
        normalised = Path(rel.as_posix())
        if normalised in _PENDING_RETIREMENT_ALLOWLIST:
            continue
        text = path.read_text(encoding="utf-8")
        if pattern.search(text):
            offenders.append(str(rel))
    assert not offenders, (
        "production files outside the allow-list defining "
        "_DEFAULT_*_ROOT = bundled_path(...) found; these must "
        f"route through aeat.core.resources.resources() instead: {offenders}"
    )


def test_allowlist_only_contains_files_that_actually_offend() -> None:
    """Every allow-list entry must still contain a _DEFAULT_*_ROOT
    definition; the moment a file is cleaned up its allow-list slot
    must be removed.
    """

    pattern = re.compile(r"^_DEFAULT_[A-Z_]+_ROOT\s*=\s*bundled_path", re.MULTILINE)
    stale: list[str] = []
    for rel in _PENDING_RETIREMENT_ALLOWLIST:
        absolute = _REPO_ROOT / rel
        if not absolute.is_file():
            stale.append(f"{rel} (file missing)")
            continue
        text = absolute.read_text(encoding="utf-8")
        if not pattern.search(text):
            stale.append(f"{rel} (no _DEFAULT_*_ROOT remains)")
    assert not stale, f"the pending-retirement allow-list contains entries that no longer offend; remove them: {stale}"


_PROJECT_ROOT_IMPORT_RE = re.compile(
    r"^from\s+(?:aeat\.core\.paths|\.{1,4}core\.paths)\s+import\s+([^\n]+)$",
    re.MULTILINE,
)


def test_no_dead_project_root_imports() -> None:
    """Every file importing ``PROJECT_ROOT`` from ``aeat.core.paths`` must reference it.

    ``PROJECT_ROOT`` is the legitimate resolver for ``var/``
    operator outputs and ``env/.env`` operator config (and for
    source-tree audit walks). When a module migrates a bundled-data
    read to :func:`bundled_path` it MUST drop the now-unused
    ``PROJECT_ROOT`` import — leaving the dead symbol on the import
    line creates false signal that PROJECT_ROOT is still relevant
    to that module.

    Scans every ``.py`` file in the tree, parses the
    ``from ...core.paths import ...`` lines, and asserts that any
    file importing ``PROJECT_ROOT`` references it at least once
    elsewhere in the body.
    """
    dead_imports: list[str] = []
    for path in _SRC.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for match in _PROJECT_ROOT_IMPORT_RE.finditer(text):
            imported = {name.strip() for name in match.group(1).split(",")}
            if "PROJECT_ROOT" not in imported:
                continue
            # Strip the import line itself before searching for usage so
            # that a single-line import does not satisfy its own gate.
            body = text[: match.start()] + text[match.end() :]
            if "PROJECT_ROOT" not in body:
                dead_imports.append(str(path.relative_to(_REPO_ROOT)))
    assert not dead_imports, (
        "modules that import PROJECT_ROOT but never reference it "
        "(drop the dead import; bundled-data reads go through "
        f"aeat.core.resources.bundled_path instead): {dead_imports}"
    )


def test_resources_package_re_exports_boundary() -> None:
    """The boundary functions stay accessible through the package init."""

    from .. import as_path, bundled_path, packaged_data, resources

    assert packaged_data is not None
    assert bundled_path is not None
    assert as_path is not None
    assert resources is not None
