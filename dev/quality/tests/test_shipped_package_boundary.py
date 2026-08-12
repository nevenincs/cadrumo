"""Gate: no shipped `cadrumo` module imports the unshipped `dev` tree.

The hard assertion is one line. Everything around it exists because this gate
has an unusually easy way to be worthless: the tree is compliant today, so a
scanner that found nothing because it was LOOKING at nothing would pass exactly
as loudly as the real one. A green result here has to mean "the boundary holds",
never "the walk returned no files".

Three independent proofs stand behind the assertion. The shipped set is checked
non-empty and checked to contain named modules that genuinely ship. The
detector is driven against real violating source rather than only synthetic
source. And the exclusion logic is proved to be doing real work rather than
excluding everything.

The second of those is worth stating plainly, because it is what makes this
gate adversarial rather than decorative. The repository contains dozens of
`from dev.x import y` statements under `src/cadrumo/**/tests/`, and they are
NOT violations: both distribution targets drop those directories, so the code
never reaches a consumer. That gives this gate something a purely synthetic
proof can never buy — real, first-party, currently-committed source in the
exact shape being hunted, sitting just outside the scanned set. If the scanner
were broken, pointing it at those files would find nothing, and the proof below
would fail.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Final

import pytest

from ..shipped_package_boundary import (
    REPO_ROOT,
    UNSHIPPED_IMPORT_ROOTS,
    scan,
    scan_file,
    shipped_python_files,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

#: Modules that unambiguously ship. Named individually so that a packaging
#: change which accidentally emptied the wheel would red this gate rather than
#: silently reducing it to a scan over nothing.
_MUST_BE_SHIPPED: Final[tuple[str, ...]] = (
    "src/cadrumo/core/atomic_write.py",
    "src/cadrumo/entrypoints/cli/__init__.py",
    "src/cadrumo/domain/calculations/registry/__init__.py",
)

#: Directories both distribution targets drop. They are the source of the real
#: violating statements this gate proves its detector against.
_EXCLUDED_TEST_GLOB: Final[str] = "src/cadrumo/**/tests/*.py"


def test_no_shipped_module_imports_the_unshipped_dev_tree() -> None:
    """The boundary holds: nothing in the wheel imports `dev`.

    `dev/` is excluded from both distribution targets, so any hit here is an
    `ImportError` on every installed consumer — a defect a repo-checkout suite
    run structurally cannot reproduce, because from a checkout the import
    resolves.
    """
    violations = scan()
    assert not violations, "shipped modules import the unshipped dev tree:\n" + "\n".join(
        violation.render() for violation in violations
    )


def test_the_shipped_set_is_real_and_not_empty() -> None:
    """The scan walked actual shipped modules, not an empty set."""
    shipped = shipped_python_files()
    assert len(shipped) > 500, f"only {len(shipped)} shipped modules found; the walk is not reaching the package"

    relative = {path.relative_to(REPO_ROOT).as_posix() for path in shipped}
    for expected in _MUST_BE_SHIPPED:
        assert expected in relative, f"{expected} ships but was not scanned"


def test_the_exclusion_drops_the_test_tree_it_is_supposed_to_drop() -> None:
    """Excluded test directories are absent from the shipped set.

    Without this the gate could be green because the exclusion silently matched
    nothing and the whole tree — tests included — happened to be compliant for
    some other reason.
    """
    shipped = {path.relative_to(REPO_ROOT).as_posix() for path in shipped_python_files()}
    assert not [path for path in shipped if "/tests/" in path], (
        "test modules are being scanned as shipped; the packaging exclusions are not being applied"
    )


def _real_files_importing_dev() -> list[Path]:
    """Return committed src-tree test modules that really import `dev`."""
    found: list[Path] = []
    for path in sorted((REPO_ROOT / "src" / "cadrumo").rglob("*.py")):
        if "tests" not in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            module = node.module if isinstance(node, ast.ImportFrom) and node.level == 0 else None
            if module and module.split(".", 1)[0] in UNSHIPPED_IMPORT_ROOTS:
                found.append(path)
                break
    return found


def test_the_detector_finds_real_committed_violations_when_pointed_at_them() -> None:
    """Anti-vacuity, against real source rather than a synthetic fixture.

    A detector can be correct on invented input and still never fire on the
    real thing. These are first-party, currently-committed modules holding the
    exact statement shape being hunted; they are legitimately outside the
    shipped set, which is precisely what makes them a free positive control.
    """
    real = _real_files_importing_dev()
    assert real, "no src-tree test module imports dev; this proof has lost its subject and must be re-grounded"

    for path in real:
        assert scan_file(path), f"the scanner found no dev import in {path}, which demonstrably has one"


def test_the_detector_catches_a_deferred_import(tmp_path: Path) -> None:
    """A function-local import is reported exactly like a module-level one.

    Deferring an import moves the failure from import time to call time. It
    does not remove it, and on an installed consumer it is the harder of the
    two to diagnose.
    """
    module = tmp_path / "deferred.py"
    module.write_text(
        "def build():\n    from dev.locales import LocaleManager\n    return LocaleManager\n",
        encoding="utf-8",
    )
    violations = scan_file(module)
    assert len(violations) == 1
    assert violations[0].line == 2


def test_the_detector_catches_a_literal_dynamic_import(tmp_path: Path) -> None:
    """A literal `import_module("dev.x")` is the same statement in disguise."""
    module = tmp_path / "dynamic.py"
    module.write_text(
        'import importlib\n\n\ndef build():\n    return importlib.import_module("dev.quality.shard")\n',
        encoding="utf-8",
    )
    violations = scan_file(module)
    assert len(violations) == 1
    assert "dev.quality.shard" in violations[0].statement


def test_a_relative_import_is_not_mistaken_for_a_dev_import(tmp_path: Path) -> None:
    """`from . import dev` inside the package is a sibling module, not the tree.

    The false-positive direction matters as much as the false-negative one: a
    gate that fires on compliant code gets routed around, which is how a hard
    boundary decays into an advisory.
    """
    module = tmp_path / "relative.py"
    module.write_text("from .dev import helper\n", encoding="utf-8")
    assert not scan_file(module)
