"""Profile custody must not reach the retired shared-master surface.

The per-profile capsule owns exactly one secret lineage: a password envelope
plus an independently domain-separated recovery record.  A shared global
``master.key`` reachable from the same composition would be a second, parallel
custody lifecycle beside it -- one that answers for every profile at once and
that no per-profile refusal can gate.  The two cannot coexist without the
weaker one deciding what a taxpayer's data is protected by.

Absence is the whole assertion here, so it is checked structurally: a
behavioural test can only prove that the route it happened to walk did not take
the retired path.  The detector is proved against a source that does use the
retired surface, because a name scanner that matches nothing reports a clean
tree and a broken gate identically.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PACKAGE_ROOT = Path(__file__).resolve().parent.parent
_STORAGE_ROOT = _PACKAGE_ROOT.parent.parent / "adapters" / "persistence" / "storage"

# The shared-master custody surface: the provider protocol and its
# implementations, the ambient activation/resolution seam that hands a caller
# the process-wide key, and the global recovery facade that re-wrapped it.
_RETIRED_CUSTODY_NAMES = frozenset(
    {
        "MasterKeyProvider",
        "KeyringMasterKeyProvider",
        "FileFallbackMasterKeyProvider",
        "UnsecuredMasterKeyProvider",
        "get_master_key_provider",
        "activate_master_key_provider",
        "get_master_key",
        "begin_recovery",
        "complete_recovery",
    }
)


def _production_modules(root: Path) -> list[Path]:
    return sorted(
        path
        for path in root.rglob("*.py")
        if "tests" not in path.relative_to(root).parts and "__pycache__" not in path.parts
    )


def _retired_references(source: str) -> set[str]:
    """Report every retired custody name the source imports, reads, or calls."""
    tree = ast.parse(source)
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            found |= {alias.name for alias in node.names} & _RETIRED_CUSTODY_NAMES
        elif isinstance(node, ast.Attribute) and node.attr in _RETIRED_CUSTODY_NAMES:
            found.add(node.attr)
        elif isinstance(node, ast.Name) and node.id in _RETIRED_CUSTODY_NAMES:
            found.add(node.id)
    return found


def test_detector_reports_a_module_that_does_use_the_retired_surface() -> None:
    """Anti-tautology: the scanner must red on the shape it exists to forbid."""
    using_provider = (
        "from ...adapters.persistence.storage import get_master_key_provider\n"
        "def unlock() -> bytes:\n"
        "    return get_master_key_provider().get_master_key()\n"
    )
    assert _retired_references(using_provider) == {"get_master_key_provider", "get_master_key"}
    assert _retired_references("from ._custody_transactions import canonical_payload_digest\n") == set()


def test_production_user_profile_never_reaches_shared_master_custody() -> None:
    modules = _production_modules(_PACKAGE_ROOT)
    assert modules, "the production user_profile tree must not be empty"
    offenders = {
        module.relative_to(_PACKAGE_ROOT).as_posix(): sorted(names)
        for module in modules
        if (names := _retired_references(module.read_text(encoding="utf-8")))
    }
    assert offenders == {}, (
        "profile custody composition must resolve secrets through the per-profile "
        f"capsule, not the retired shared-master surface: {offenders}"
    )


def test_retired_names_that_still_exist_belong_to_the_retired_package() -> None:
    """Anchor the forbidden names to the surface they are named for.

    Without this, renaming the retired surface would leave the gate above
    matching nothing and passing vacuously.  It is deliberately silent once the
    names are gone entirely: the absence gate still bites on reintroduction.
    """
    misplaced: dict[str, list[str]] = {}
    for path in _STORAGE_ROOT.parent.parent.rglob("*.py"):
        if "__pycache__" in path.parts or "tests" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        defined = {
            node.name
            for node in ast.walk(tree)
            if isinstance(node, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef)
        } & _RETIRED_CUSTODY_NAMES
        if defined and (_STORAGE_ROOT / "master_key") not in path.parents:
            misplaced[path.name] = sorted(defined)
    assert misplaced == {}, f"retired custody names defined outside the retired package: {misplaced}"
