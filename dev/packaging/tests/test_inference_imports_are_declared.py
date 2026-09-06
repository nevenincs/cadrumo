"""Every third-party package the inference path imports is DECLARED, not inherited.

A dependency that is merely present is not a dependency that is promised. Pillow
is the case that motivated this: the page rasteriser calls ``bitmap.to_pil()``
and then ``image.save(...)``, which is a direct reliance on Pillow's behaviour,
while Pillow arrived in the install closure only because ``pdfplumber`` and
``pikepdf`` happen to depend on it. A release of either dropping Pillow would
have broken page rendering with no resolution-time signal at all -- the failure
would surface at runtime, on the first page rendered, wearing the rasteriser's
own "could not rasterise PDF pages" wrapper.

That specific hole is closed: Pillow is now declared in the base dependencies
AND in the ``llm`` extra. This gate exists so the CLASS stays closed. The next
incidental transitive to be relied on directly will not announce itself, and
nothing about an import statement reveals whether the package behind it was
promised or inherited.

**Declared means named in the metadata the built distribution carries** -- in
``[project] dependencies`` or in an optional-dependencies extra. A
``[dependency-groups]`` entry does NOT count: a PEP 735 group is a development
convenience that never reaches a wheel's ``Requires-Dist``, so a shipped module
resting on one rests on exactly the incidental presence this gate refuses. It
also deliberately does NOT mean "resolves in the current environment", because
everything resolves in the current environment; that is exactly the condition an
incidental transitive satisfies and the reason this defect is invisible without
a gate.

Only shipped modules are scanned. Both build targets exclude
``src/cadrumo/**/tests/**``, so a test module's ``import pytest`` is not a
shipped reliance; folding those in would force the dev groups back into the
declared set and reopen the hole above.

Import names are mapped to distribution names through
:func:`importlib.metadata.packages_distributions` rather than a hand-kept table,
so the mapping tracks what is actually installed instead of drifting from it --
``PIL`` to ``pillow`` is the mapping this gate was written for, and hard-coding
it would have made the gate an assertion about its own table.
"""

from __future__ import annotations

import ast
import tomllib
from collections.abc import Iterator
from importlib.metadata import packages_distributions
from pathlib import Path

import pytest

from cadrumo.core.directory_scan import scan_directory

from ..._paths import REPO_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_REPO_ROOT = REPO_ROOT
_INFERENCE_PACKAGE = _REPO_ROOT / "src" / "cadrumo" / "llm"

#: Import names that are the standard library or this project itself, so they
#: are never expected to appear in a dependency declaration.
_NOT_THIRD_PARTY = frozenset({"cadrumo", "cadrumo_data", "dev"})


def _declared_distributions() -> set[str]:
    """Every distribution the built distribution's own metadata promises.

    Normalised per PEP 503 so ``Pillow``, ``pillow`` and a hypothetical
    ``pil_low`` compare equal, which is how the packaging ecosystem itself
    treats them; a gate that compared raw strings would fail on capitalisation
    and teach everyone to distrust it.
    """
    with (_REPO_ROOT / "pyproject.toml").open("rb") as handle:
        pyproject = tomllib.load(handle)

    requirement_lists: list[list[str]] = [pyproject["project"].get("dependencies", [])]
    requirement_lists.extend(pyproject["project"].get("optional-dependencies", {}).values())
    # `[dependency-groups]` is deliberately absent: it is not published in the
    # distribution metadata, so it promises an installer of the wheel nothing.

    declared: set[str] = set()
    for requirements in requirement_lists:
        for requirement in requirements:
            if not isinstance(requirement, str):
                # Defensive: a non-string entry is not a requirement specifier.
                continue
            name = requirement.split(";")[0].strip()
            for separator in ("[", "=", ">", "<", "!", "~", " "):
                name = name.split(separator)[0]
            if name:
                declared.add(_normalise(name))
    return declared


def _normalise(name: str) -> str:
    return name.strip().lower().replace("_", "-").replace(".", "-")


def _top_level_imports(path: Path) -> Iterator[str]:
    """Yield the top-level module name of every absolute import in ``path``.

    Relative imports are skipped: they address this project, which is not a
    declarable dependency of itself.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name.split(".")[0]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            yield node.module.split(".")[0]


def _third_party_imports_under(root: Path) -> dict[str, list[str]]:
    """Map each third-party import name to the repo-relative files importing it."""
    stdlib_and_local = _NOT_THIRD_PARTY | _stdlib_names()
    found: dict[str, list[str]] = {}
    for path in scan_directory(root, pattern="*.py", recursive=True):
        if "tests" in path.relative_to(root).parts:
            # Not shipped by either build target, so not a shipped reliance.
            continue
        for name in _top_level_imports(path):
            if name in stdlib_and_local:
                continue
            found.setdefault(name, []).append(path.relative_to(_REPO_ROOT).as_posix())
    return found


def _stdlib_names() -> frozenset[str]:
    import sys

    return frozenset(sys.stdlib_module_names)


def test_every_third_party_import_in_the_inference_path_is_declared() -> None:
    """No module under the inference package relies on an undeclared package.

    Scoped to the inference path because that is where the reliance-on-a-
    transitive pattern actually occurred, and because a whole-repo sweep would
    fold in dev tooling whose dependency story is different.
    """
    declared = _declared_distributions()
    import_to_distributions = packages_distributions()

    undeclared: dict[str, list[str]] = {}
    for import_name, files in _third_party_imports_under(_INFERENCE_PACKAGE).items():
        distributions = {_normalise(name) for name in import_to_distributions.get(import_name, [])}
        if not distributions:
            # Not installed in this environment, so the mapping cannot be
            # resolved and the import name is the best available key.
            distributions = {_normalise(import_name)}
        if not (distributions & declared):
            undeclared[import_name] = files

    assert undeclared == {}, (
        "these packages are imported directly by the inference path but named in no pyproject "
        f"declaration, so they are relied on as incidental transitives: {undeclared}. Declare each "
        "in [project] dependencies or in the extra whose feature needs it -- do not remove the "
        "import and leave the reliance somewhere less visible."
    )


def test_the_imaging_package_is_declared_even_though_nothing_imports_it_by_name() -> None:
    """Pillow is the reliance that no import statement reveals.

    The rasteriser never writes ``import PIL``: it reaches Pillow from inside
    ``pypdfium2``'s ``to_pil()`` and then calls ``save`` on what comes back. So
    the scan above CANNOT see this reliance, and a gate built only on import
    statements would report the inference path clean while the original defect
    stood. Asserted directly for that reason, and the asymmetry is the finding
    rather than an exception to it.
    """
    assert "pillow" in _declared_distributions(), (
        "pillow is not declared in pyproject. The page rasteriser calls to_pil() and save() on the "
        "result, which is a direct reliance; without a declaration it arrives only because pdfplumber "
        "and pikepdf happen to require it, and either dropping it breaks page rendering at runtime "
        "with no resolution-time signal"
    )


def test_the_scan_finds_imports_at_all() -> None:
    """Non-vacuity: a scan that sees nothing would satisfy every assertion above.

    The two ways this gate could pass over nothing are a moved package
    directory and an AST walk that stops matching import nodes. Both look
    exactly like a clean run.
    """
    assert _INFERENCE_PACKAGE.is_dir(), f"the inference package is not at {_INFERENCE_PACKAGE}"
    imports = _third_party_imports_under(_INFERENCE_PACKAGE)
    assert imports, "no third-party imports found under the inference path; the scan is not reading anything"
    assert _declared_distributions(), "no dependencies parsed out of pyproject; the declaration reader is broken"


def test_a_development_group_entry_is_not_a_declaration() -> None:
    """The hole this reader was widened by: a dev group promises the wheel nothing.

    ``[dependency-groups]`` names roughly fifty distributions that no installer
    of the wheel ever receives. While they counted as declarations, a shipped
    inference module could ``import psutil`` -- present in this checkout, absent
    from ``Requires-Dist`` -- and the gate reported clean, which is the exact
    incidental-transitive reliance it was written to refuse.
    """
    declared = _declared_distributions()

    assert "pytest" not in declared, (
        "a [dependency-groups] entry is being counted as a declaration. Groups are development-only "
        "and never reach the built distribution's metadata, so accepting one lets a shipped module "
        "rely on a package the wheel does not require"
    )
    assert "anthropic" in declared, "the reader stopped seeing optional-dependencies extras"
    assert "pydantic" in declared, "the reader stopped seeing [project] dependencies"
