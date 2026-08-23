"""Nothing that ships may import a development-only dependency.

Standing mandate: no dev harness, smoke rig, or other non-production code lives
under ``src/cadrumo/``. Tests are the exception, and that exception is already
structural rather than trusted -- the wheel build excludes every ``tests``
directory, so a test module under ``src/`` is not shipped code.

What remained unguarded is the rest: a non-test module under ``src/`` DOES ship,
to every operator, in the wheel. The existing companion gate
(``DevToolingImportViolation`` in ``dev/quality/import_hygiene_scan.py``) catches a
shipped module importing this repo's own ``dev/`` tree. This one catches the
other half, which is how harness code actually announces itself: it reaches for
the tooling that only ever exists on a developer's machine.

**The signal is a dev-only DISTRIBUTION, not a name.** Judging by filename is
what makes this class hard -- shipped helper code can resemble development tooling
feature and ``_parity_harness.py`` is reached by a real CLI verb, while genuinely
non-production code is free to be blandly named. But a module that imports
``pytest``, ``reportlab``, ``hypothesis`` or ``torch`` cannot be production here,
because none of those is installed for an operator: on a real install the import
raises at module load.

That makes this gate stronger than a naming convention and cheaper than
consumer analysis. It is also strictly narrower: it detects non-production code
that DEPENDS on dev tooling, and says nothing about non-production code written
in pure standard library. That limit is stated rather than papered over -- the
remaining surface is author discipline and review.

The dev-only set is DERIVED, never listed: it is every distribution in a
dependency group that appears in neither ``[project] dependencies`` nor any
optional-dependencies extra. Listing it would freeze a moment and quietly stop
covering whatever was added afterwards.
"""

from __future__ import annotations

import ast
import tomllib
from collections.abc import Iterator
from importlib.metadata import packages_distributions
from pathlib import Path

import pytest

from cadrumo.core import scan_directory
from dev._paths import REPO_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_REPO_ROOT = REPO_ROOT
_SHIPPED_ROOT = _REPO_ROOT / "src" / "cadrumo"


def _normalise(name: str) -> str:
    """PEP 503 normalisation, so ``Pillow`` and ``pillow`` compare equal."""
    return name.strip().lower().replace("_", "-").replace(".", "-")


def _requirement_names(requirements: object) -> set[str]:
    names: set[str] = set()
    if not isinstance(requirements, list):
        return names
    for requirement in requirements:
        if not isinstance(requirement, str):
            # A dependency group may include another group as a table.
            continue
        name = requirement.split(";")[0].strip()
        for separator in ("[", "=", ">", "<", "!", "~", " "):
            name = name.split(separator)[0]
        if name:
            names.add(_normalise(name))
    return names


def _dev_only_distributions() -> set[str]:
    """Distributions available to developers and to nobody who installs this."""
    with (_REPO_ROOT / "pyproject.toml").open("rb") as handle:
        pyproject = tomllib.load(handle)

    shipped = _requirement_names(pyproject["project"].get("dependencies", []))
    for extra in pyproject["project"].get("optional-dependencies", {}).values():
        shipped |= _requirement_names(extra)

    grouped: set[str] = set()
    for group in pyproject.get("dependency-groups", {}).values():
        grouped |= _requirement_names(group)

    return grouped - shipped


def _dev_only_import_names() -> set[str]:
    """The import names those distributions provide, inverted from the environment.

    Derived rather than mapped by hand: ``pytest-xdist`` provides ``xdist``, and
    a hand-written table would have to keep guessing at that for every new dev
    tool.
    """
    dev_only = _dev_only_distributions()
    names: set[str] = set()
    for import_name, distributions in packages_distributions().items():
        if any(_normalise(dist) in dev_only for dist in distributions):
            names.add(import_name)
    # A distribution absent from this environment cannot be inverted, so fall
    # back to its own normalised name. Being unable to resolve a package must
    # not silently shrink what the gate looks for.
    return names | dev_only


def _is_test_surface(path: Path) -> bool:
    """True for anything the wheel build excludes or that exists to serve tests.

    ``conftest.py`` is named explicitly: package-level conftest modules sit
    OUTSIDE the excluded ``tests`` directories, so a path-segment check alone
    would treat pytest infrastructure as shipped code and report it.
    """
    return "tests" in path.parts or path.name == "conftest.py"


def _top_level_imports(path: Path) -> Iterator[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name.split(".")[0]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            yield node.module.split(".")[0]


def _shipped_modules() -> list[Path]:
    return [
        path for path in scan_directory(_SHIPPED_ROOT, pattern="*.py", recursive=True) if not _is_test_surface(path)
    ]


def test_no_shipped_module_imports_a_development_only_dependency() -> None:
    """A module that ships cannot depend on tooling an operator does not have.

    Function-local imports count and are deliberately not excused. Deferring a
    dev-tool import inside a function does not make the code production -- it
    only moves the failure from install time to the moment an operator reaches
    that branch, which is worse.
    """
    dev_only = _dev_only_import_names()

    offenders: dict[str, list[str]] = {}
    for path in _shipped_modules():
        for import_name in _top_level_imports(path):
            if import_name in dev_only:
                offenders.setdefault(path.relative_to(_REPO_ROOT).as_posix(), []).append(import_name)

    assert offenders == {}, (
        "these SHIPPED modules import development-only dependencies, so they are non-production code "
        f"living in the wheel: {offenders}. Move the module under dev/, or -- if it is genuinely a "
        "product feature -- promote the dependency out of the dev group and say why it ships."
    )


def test_the_gate_is_looking_at_something() -> None:
    """Non-vacuity: three independent ways this could pass over nothing.

    An empty dev-only set, an empty shipped-module list, or an import walk that
    stopped matching would each produce a green run indistinguishable from a
    clean tree.
    """
    assert _SHIPPED_ROOT.is_dir(), f"the shipped package is not at {_SHIPPED_ROOT}"

    dev_only = _dev_only_distributions()
    assert {"pytest", "ruff"} <= dev_only, (
        f"pytest and ruff must resolve as development-only; got {sorted(dev_only)[:10]}... "
        "if they now ship, this gate is measuring the wrong set"
    )

    modules = _shipped_modules()
    assert len(modules) > 100, f"only {len(modules)} shipped modules found; the scan is not reading the tree"
    assert any(_top_level_imports(path) for path in modules), "no imports parsed from any shipped module"


def test_the_test_surface_is_excluded_because_it_does_not_ship() -> None:
    """The tests exception is structural, and this checks it stayed that way.

    Tests are excused from the mandate only because the wheel build sheds them.
    If that exclusion were ever dropped, test modules WOULD ship and this gate's
    exemption would become a hole rather than a courtesy -- so the exclusion is
    asserted here rather than assumed.
    """
    with (_REPO_ROOT / "pyproject.toml").open("rb") as handle:
        pyproject = tomllib.load(handle)

    excluded = pyproject["tool"]["hatch"]["build"]["targets"]["wheel"]["exclude"]

    assert "src/cadrumo/tests" in excluded
    assert "src/cadrumo/**/tests" in excluded
    assert "src/cadrumo/**/tests/**" in excluded

    # And the exemption predicate must actually cover a real test module, or the
    # scan above is quietly excluding nothing.
    sample = next(_SHIPPED_ROOT.rglob("tests/test_*.py"))
    assert _is_test_surface(sample), f"{sample} is a test module the exemption failed to recognise"
