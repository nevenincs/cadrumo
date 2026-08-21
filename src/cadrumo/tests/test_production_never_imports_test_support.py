"""No production module imports the shipped test-support package.

``cadrumo.tests`` ships inside the wheel, so nothing structural stops a
production module importing it. What that package holds is scaffolding:
fixtures that provision throwaway profiles, an ephemeral master-key provider,
helpers full of bare ``assert`` statements. Each of those is safe in a test and
wrong in a shipped path.

The sharpest instance is not hypothetical. ``EphemeralMasterKeyProvider`` opens
its session with ``bucket_id="ephemeral"``, and ``"ephemeral"`` is a member of
``_SYNTHETIC_SESSION_BUCKET_IDS`` in
:mod:`adapters.persistence.storage.runtime` -- the set whose whole function is
to SKIP the cross-bucket check. A production path that acquired such a session
would be able to attach a repository to any bucket at all, because the guard
that normally refuses a bucket the session does not serve is switched off for
exactly those ids. Nothing today does this, and nothing prevented it either.

A bare ``assert`` is the quieter half of the same problem: assertions are
removed under ``python -O``, so a production path that relies on one has a
guard in development and none in a wheel run with optimisations.

Scope: this checks IMPORTS, which is the reachable-from-production question. It
does not judge whether a helper is well placed -- see the declared entry below
for a case that is an import AND a placement defect, only one of which this
gate can see.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from . import non_test_package_python_files, repo_relative

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

#: Production modules that import test support, with what is known about each.
#:
#: An entry RECORDS a violation; it does not bless one. Each states why it has
#: not been moved, so the exemption cannot quietly become the convention.
_IMPORTS_TEST_SUPPORT: dict[str, str] = {
    "src/cadrumo/application/calculations/_multi_year.py": (
        "Holds a multi-year observation TEST SCAFFOLD -- it takes a tmp_path, provisions a "
        "throwaway profile through isolated_runtime_profile, and asserts with bare asserts. It is "
        "a test helper that came to rest in a production package, so the fix is a relocation into "
        "the owning tests/ directory rather than an import change, and relocations are atomic and "
        "belong to that module's owner (the calculations campaign), not to this one. Recorded here "
        "so the reach is visible while it waits."
    ),
}


def _modules_importing_test_support() -> dict[str, int]:
    """Return every production module importing a ``tests`` package, by line."""
    found: dict[str, int] = {}
    for path in non_test_package_python_files():
        # conftest.py is test infrastructure that the production walk still
        # yields; importing test support is its job, not a reach into it.
        if Path(path).name == "conftest.py":
            continue
        try:
            tree = ast.parse(Path(path).read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):  # pragma: no cover - unparsable file is its own failure
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and "tests" in node.module.split("."):
                found.setdefault(repo_relative(path), node.lineno)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if "tests" in alias.name.split("."):
                        found.setdefault(repo_relative(path), node.lineno)
    return found


def test_the_scan_reads_the_real_production_tree() -> None:
    """ANTI-VACUITY: an empty file list would clear every entry below."""
    files = [path for path in non_test_package_python_files() if Path(path).name != "conftest.py"]

    assert len(files) > 500, f"the production walk found only {len(files)} modules; it is not seeing the tree"
    assert any("adapters/persistence/storage" in repo_relative(path) for path in files), (
        "the walk is not reaching the storage package"
    )


def test_no_production_module_imports_test_support() -> None:
    """Test scaffolding must not be reachable from a shipped path."""
    offenders = sorted(
        f"{module}:{line}"
        for module, line in _modules_importing_test_support().items()
        if module not in _IMPORTS_TEST_SUPPORT
    )

    assert not offenders, (
        f"these production modules import the shipped test-support package: {offenders}. That "
        "package provisions throwaway profiles and carries bare asserts, and its ephemeral "
        "provider opens a session whose bucket id switches OFF the cross-bucket guard. Move the "
        "helper into the owning tests/ directory, or record it below with the reason it cannot "
        "move yet."
    )


def test_no_record_outlives_its_violation() -> None:
    """The half that rots: an entry for a module that no longer imports."""
    live = _modules_importing_test_support()
    stale = sorted(module for module in _IMPORTS_TEST_SUPPORT if module not in live)

    assert not stale, (
        f"these records no longer describe a production module importing test support: {stale}. "
        "Remove them -- an entry that outlives its violation reads as a known reach that is not "
        "there, and hides that the tree got better."
    )


def test_the_synthetic_bucket_exemption_is_still_what_makes_this_matter() -> None:
    """Anchor: the reason stated above must still be true of the code.

    This gate argues from a specific fact -- that the ephemeral provider's
    bucket id is a member of the set that disables the cross-bucket check. If
    that stops being true the argument needs rewriting, and a docstring nobody
    re-checks is how a gate ends up defending a hazard that moved.
    """
    from ..adapters.persistence.storage.runtime import _SYNTHETIC_SESSION_BUCKET_IDS

    assert "ephemeral" in _SYNTHETIC_SESSION_BUCKET_IDS
