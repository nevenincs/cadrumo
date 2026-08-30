"""A cross-reference that names a symbol its cited module does not have.

The nitpicky ``-n -W`` Sphinx build proves a reference RESOLVES against the
built object inventory. That inventory is assembled from the API stubs, and a
role written as ``:func:`domain.deadlines.engine``` resolves happily when the
inventory holds *something* under that name -- so a role can name the wrong
KIND of object, or a symbol that moved to a sibling module, and still build
clean. The sibling gate
``src/cadrumo/tests/test_docstring_well_formedness.py`` proves a docstring is
structurally sound; neither proves its cross-references point at what they
claim.

That gap is load-bearing here. This project carries its reasoning in
docstrings -- why a guard is narrow, which module owns a concept, where a
value's single home is -- so a cross-reference is a navigational contract, and
a stale one sends the next reader to a module that does not hold the symbol.
The measured backlog was six, each a real mis-citation rather than a style
complaint:

* two roles naming a MODULE with ``:func:``, so the reference asserted a
  callable where a module sits;
* a registry scalar alias cited on the package facade that does not export it,
  twice, while its sibling ``PeriodSelector`` genuinely is exported -- the
  asymmetry is exactly what makes the citation look right;
* a storage filename cited on ``core.config``, which re-exports the *former*
  name and not this one;
* a replay payload cited on the registry facade while it lives in
  ``_live_parity``.

A hard cut with no stored baseline, which a backlog of six affords: a ratchet
over an unknown population is how a gate gets disabled.

**The predicate is DEFINES-OR-EXPORTS, not ``__all__``.** A role naming a
private symbol in the module that defines it is truthful, and the first draft
of this gate keyed on ``__all__`` alone and reported sixty-two offenders, of
which fifty-six were correct citations of private symbols. A detector that
spends its credibility on noise before it finds anything is one nobody runs;
the narrower predicate is what leaves six real defects standing.

**Only DOTTED first-party targets are judged.** A bare anchor
(``:class:`ModeloRevision```) is the documented house style and is resolved by
the build's missing-reference resolver, so it carries no module claim for this
gate to check. Third-party and stdlib targets are out of reach of a source
walk. The judged population is therefore roughly a third of the roles in the
tree, and the floor below proves that share never silently empties.
"""

from __future__ import annotations

import ast
import re
from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from ..core.directory_scan import scan_directory
from ._inventory import SRC_CADRUMO, production_python_files, repo_relative

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]

if TYPE_CHECKING:
    from collections.abc import Iterator

#: Sphinx roles that name a Python object or module.
_ROLE = re.compile(r":(?P<role>class|func|meth|attr|data|exc|obj|mod):`(?P<target>[^`<>\s]+)`")

#: Roles whose target is a module rather than an object inside one.
_MODULE_ROLES = frozenset({"mod"})

#: Lower bound on judged references. A bound, never a tally: the point is that
#: the dotted first-party population cannot silently fall to nothing (a broken
#: regex, a renamed package root) and leave every assertion below vacuous. It
#: sits far under the measured population so ordinary churn never touches it.
_MINIMUM_JUDGED_REFERENCES = 2000


@cache
def _first_party_roots() -> frozenset[str]:
    """Top-level ``cadrumo`` subpackages, read from the tree.

    Roles in this codebase omit the distribution root -- ``:class:`~llm.
    LLMClient``` rather than ``cadrumo.llm.LLMClient`` -- so a target is
    first-party when its head segment is a real subpackage. Derived rather
    than listed, so a new subpackage is judged the day it appears.
    """
    return frozenset(
        entry.name for entry in scan_directory(SRC_CADRUMO) if entry.is_dir() and (entry / "__init__.py").exists()
    )


def module_file(dotted: str) -> Path | None:
    """Return the source file for a dotted first-party module, or None."""
    parts = dotted.split(".")
    module = SRC_CADRUMO.joinpath(*parts).with_suffix(".py")
    if module.exists():
        return module
    package = SRC_CADRUMO.joinpath(*parts, "__init__.py")
    return package if package.exists() else None


@cache
def module_names(path: Path) -> frozenset[str]:
    """Every name the module defines, imports, or lists in ``__all__``.

    The union is deliberate. ``__all__`` alone under-reports: a private helper
    cited from its own defining module is a truthful reference and must not be
    flagged. Definitions alone under-report the other way: a facade whose whole
    surface is re-exports would appear to hold nothing.

    Names bound inside ``if`` / ``try`` branches count, which covers the
    optional-dependency fallback idiom where a class is defined in an
    ``except ImportError`` arm.
    """
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"), filename=str(path))
    except (OSError, SyntaxError):
        return frozenset[str]()
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
                    if target.id == "__all__":
                        names |= _literal_names(node.value)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
        elif isinstance(node, ast.ImportFrom):
            names.update(alias.asname or alias.name for alias in node.names)
        elif isinstance(node, ast.Import):
            names.update(alias.asname or alias.name.split(".")[0] for alias in node.names)
    return frozenset(names)


def _literal_names(node: ast.expr) -> set[str]:
    """Return the string members of an ``__all__`` literal, or nothing."""
    try:
        value = ast.literal_eval(node)
    except (ValueError, SyntaxError):
        return set()
    return {item for item in value if isinstance(item, str)} if isinstance(value, list | tuple) else set()


def _dotted_first_party_targets(text: str) -> Iterator[tuple[int, str, str]]:
    """Yield ``(line, role, target)`` for every dotted first-party role."""
    for match in _ROLE.finditer(text):
        role = match.group("role")
        target = match.group("target")
        assert isinstance(role, str)
        assert isinstance(target, str)
        target = target.lstrip("~!").strip()
        if "." not in target or target.split(".")[0] not in _first_party_roots():
            continue
        yield text[: match.start()].count("\n") + 1, role, target


def cross_reference_defect(role: str, target: str) -> str | None:
    """Return why *target* is unreachable under *role*, or None when it holds.

    A non-module role is checked against the module named by every segment but
    the last. When that module does not exist the target is retried one
    segment shorter, which is how ``Class.method`` targets resolve: the
    method's owner is the class, and the class must live in the module.
    """
    if role in _MODULE_ROLES:
        return None if module_file(target) is not None else f"no module named {target}"
    module, _, symbol = target.rpartition(".")
    path = module_file(module)
    if path is not None:
        return None if symbol in module_names(path) else f"{module} neither defines nor exports {symbol}"
    owner_module, _, owner = module.rpartition(".")
    owner_path = module_file(owner_module)
    if owner_path is None:
        return f"no module named {module}"
    return None if owner in module_names(owner_path) else f"{owner_module} neither defines nor exports {owner}"


def cross_reference_defects() -> list[str]:
    """Return one entry per production role naming an unreachable target."""
    defects: list[str] = []
    for path in production_python_files():
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line, role, target in _dotted_first_party_targets(text):
            reason = cross_reference_defect(role, target)
            if reason is not None:
                defects.append(f"{repo_relative(path)}:{line} :{role}:`{target}` -- {reason}")
    return defects


def judged_reference_count() -> int:
    """How many dotted first-party roles the gate actually judged."""
    total = 0
    for path in production_python_files():
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        total += sum(1 for _ in _dotted_first_party_targets(text))
    return total


def test_no_cross_reference_names_a_symbol_its_module_does_not_have() -> None:
    """A role pointing at a module that does not hold the symbol misdirects.

    Not a formatting complaint: a reader following the reference lands in a
    module that never had the thing, and concludes the concept moved, was
    deleted, or that they misread the name. Fix the citation to the symbol's
    real home, or restore the symbol to the module the docstring claims.
    """
    defects = cross_reference_defects()
    assert not defects, "these cross-references name a symbol their cited module does not hold: " + "; ".join(defects)


def test_the_judged_population_has_not_emptied() -> None:
    """A gate that judges nothing passes for the wrong reason.

    The regex, the first-party root derivation and the module resolver can each
    fail silently to an empty judged set, and the assertion above would then be
    green over a tree nobody checked. Floored as a bound rather than pinned as a
    count, so the property is 'this gate still reaches the tree' and not 'the
    tree still has exactly this many references'.
    """
    judged = judged_reference_count()
    assert judged >= _MINIMUM_JUDGED_REFERENCES, (
        f"only {judged} dotted first-party cross-references were judged; the scan has lost its reach"
    )


def test_the_first_party_roots_came_from_the_tree() -> None:
    """A root set that emptied would make every target read as third-party."""
    roots = _first_party_roots()
    assert {"core", "domain", "application", "adapters", "entrypoints"} <= roots, (
        f"the first-party root set looks wrong: {sorted(roots)}"
    )


# -- proof that the detector bites, and that it does not bite at random ------


def test_the_detector_catches_a_symbol_the_module_does_not_hold() -> None:
    """The recall half, driven against a real module rather than a fixture.

    ``core.config`` is a real module and this name is not in it, which is the
    exact shape of one defect this gate was written over: a constant cited on
    the config facade while it lives in the state-root module behind it.
    """
    defect = cross_reference_defect("data", "core.config.NoSuchConstantLivesHere")
    assert defect is not None, "the detector cleared a citation naming a symbol core.config does not hold"


def test_the_detector_catches_a_module_that_does_not_exist() -> None:
    """The ``:mod:`` arm, which resolves nothing rather than a missing member."""
    assert cross_reference_defect("mod", "core.no_such_module_exists") is not None


def test_the_detector_clears_a_public_facade_symbol() -> None:
    """The precision half: a correct citation must stay silent.

    Without this the gate could pass the assertions above by flagging
    everything, and a detector that flags correct code is one somebody
    switches off.
    """
    assert cross_reference_defect("class", "core.Modelo") is None


def test_the_detector_clears_a_private_symbol_in_its_defining_module() -> None:
    """The predicate that separates this gate from an ``__all__`` check.

    A private helper cited from the module that defines it is truthful. The
    first draft of this gate keyed on ``__all__`` alone and reported fifty-six
    of these as defects, which is how a detector loses the room before it
    reports the six that matter.
    """
    assert cross_reference_defect("func", "core.redaction._redact_cli_string") is None


def test_the_detector_resolves_a_method_through_its_owning_class() -> None:
    """A ``Class.method`` target names a module one segment further up."""
    assert cross_reference_defect("meth", "core.Modelo.no_such_method") is None
    reason = cross_reference_defect("meth", "core.NoSuchClass.method")
    assert reason is not None
    assert "NoSuchClass" in reason
