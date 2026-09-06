"""No module may import a package through a submodule named ``__init__``.

``from ..__init__ import app`` does not address the package. Python resolves it
as a SUBMODULE named ``__init__``, enters
``cadrumo.entrypoints.cli.config.__init__`` in ``sys.modules`` beside
``cadrumo.entrypoints.cli.config``, and executes the package body a SECOND
time. Any import-time side effect in that body therefore happens twice.

This is not theoretical. One test module carried that spelling and the config
package registers lazy CLI leaves at import, so ``profile create`` was
registered twice. It went unnoticed for as long as the registration tolerated a
duplicate; when a reusable lazy-node kernel added duplicate detection, six test
modules stopped collecting at once and the error named the CLI rather than the
import that caused it.

The spelling is never necessary -- ``from .. import app`` is equivalent and
binds the same object from the one canonical module -- so this forbids it
outright rather than trying to judge which package bodies are safe to run
twice.

SCOPE, deliberately narrow. The submodule is refused in BOTH spellings that
reach it. ``import cadrumo.entrypoints.cli.config.__init__`` names the same
submodule as the ``from`` form and carries the identical hazard -- run against
a package whose body prints, it prints twice and leaves two distinct module
objects in ``sys.modules`` -- so reading only ``ImportFrom`` left this gate
reporting no offence over one of the two ways to commit the offence.

The sibling spelling ``from .. import __init__ as pkg`` stays legal, and that
is a different judgement rather than an oversight: every module object already
has an ``__init__`` METHOD, so it binds a method-wrapper and imports nothing at
all. That is useless and misleading, but it is not the double-execution hazard
this gate exists for, and widening a gate to cover a second concern is how a
sharp rule becomes a vague one.
"""

from __future__ import annotations

import ast
from typing import Final

import pytest

from ..._paths import REPO_ROOT
from ..unread_inputs import report_unread

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_ROOTS: Final = ("src", "dev")
#: A generated baseline copy of the package tree; its contents are not authored here.
_EXCLUDED_SEGMENT: Final = ".baseline-source-snapshot"


def _names_a_dunder_init_submodule(dotted: str) -> bool:
    """Does this dotted path address a submodule literally named ``__init__``?"""
    return dotted == "__init__" or dotted.endswith(".__init__")


def _dunder_init_imports(tree: ast.AST) -> list[int]:
    """Return the line of every import addressing an ``__init__`` submodule.

    Both spellings reach it. ``from pkg.__init__ import name`` puts the package
    path on the ``ImportFrom`` node, while ``import pkg.__init__`` puts it on an
    alias of an ``Import`` node; the interpreter treats them alike, so a gate
    reading one node type refuses half the hazard and reports clean over the
    rest.
    """
    lines: list[int] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if _names_a_dunder_init_submodule(node.module or ""):
                lines.append(node.lineno)
        elif isinstance(node, ast.Import) and any(_names_a_dunder_init_submodule(alias.name) for alias in node.names):
            lines.append(node.lineno)
    return lines


def _scan() -> tuple[list[str], int]:
    """Return offending locations and the number of modules actually parsed."""
    offences: list[str] = []
    unparsed: list[str] = []
    parsed = 0
    for root in _ROOTS:
        for path in (REPO_ROOT / root).rglob("*.py"):
            if _EXCLUDED_SEGMENT in path.as_posix():
                continue
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except SyntaxError as refusal:
                # A peer mid-edit in a shared worktree; their syntax error is
                # their gate's to report, not a finding of this one. The loss
                # still lands here: an unparsed module contributes no offence
                # and reads as compliant. The floor below is post-swallow, but
                # 6,906 modules parse against a floor of 1,000, so most of the
                # tree could vanish before it fires.
                unparsed.append(f"{path} ({refusal})")
                continue
            parsed += 1
            offences.extend(f"{path.relative_to(REPO_ROOT).as_posix()}:{line}" for line in _dunder_init_imports(tree))
    report_unread(
        "dunder-init import scan",
        "these modules were not parsed, so a forbidden __init__ import inside one would "
        "not appear in the offences below",
        unparsed,
    )
    return offences, parsed


def test_no_module_imports_a_package_through_dunder_init() -> None:
    """DISCRIMINATING: the spelling that executes a package body twice."""
    offences, parsed = _scan()

    assert parsed > 1000, f"the scan reached only {parsed} modules; it is not covering the tree"
    assert not offences, (
        "these imports name a submodule `__init__`, which re-executes the package body and "
        "repeats every import-time side effect; write `from <package> import <name>` instead: "
        + ", ".join(sorted(offences))
    )


def test_the_detector_recognises_the_spelling_it_forbids() -> None:
    """ANTI-TAUTOLOGY: an emptiness claim is also satisfied by a blind detector.

    The assertion above passes just as well if `_dunder_init_imports` never
    matches anything, so the matcher is exercised against the exact form that
    shipped, plus the absolute spelling of the same hazard.
    """
    relative = ast.parse("from ..__init__ import app")
    absolute = ast.parse("from cadrumo.entrypoints.cli.config.__init__ import app")
    plain = ast.parse("import cadrumo.entrypoints.cli.config.__init__")
    aliased = ast.parse("import cadrumo.entrypoints.cli.config.__init__ as config")

    assert _dunder_init_imports(relative) == [1]
    assert _dunder_init_imports(absolute) == [1]
    assert _dunder_init_imports(plain) == [1], "the plain-import spelling reaches the same submodule"
    assert _dunder_init_imports(aliased) == [1], "an alias renames the binding, not the module executed"


def test_the_correct_spellings_are_not_flagged() -> None:
    """The fix, and the benign sibling, must both stay legal.

    Flagging `from .. import app` would refuse the very repair this gate asks
    for, and flagging `from .. import __init__ as pkg` would widen the rule
    past the hazard it names.
    """
    assert _dunder_init_imports(ast.parse("from .. import app")) == []
    assert _dunder_init_imports(ast.parse("from .. import __init__ as pkg")) == []
    assert _dunder_init_imports(ast.parse("import cadrumo.entrypoints.cli")) == []
