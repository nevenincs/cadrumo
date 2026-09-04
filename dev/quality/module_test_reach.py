"""Report which ``dev`` modules no test in the tree reaches.

A module no test imports is not necessarily wrong - a thin CLI wrapper over a
tested library is fine - but nothing distinguishes that case from a module whose
behaviour nobody asserts until somebody looks. Forty-two of this tree's 352
modules are in that position, and the useful question is not the count but which
of them can do damage.

So each unreached module is reported with what it can do:

- ``writes`` - the module calls ``write_text``, ``rename``, ``unlink`` or
  ``mkdir``, so running it changes the tree. An untested module that rewrites
  source files is the most expensive kind a repository can hold, and this
  campaign has the receipts: the two codemods written during it carried three
  silent defects between them, every one found by the tests they were given.
- ``applies`` - the module declares an ``--apply``-shaped flag, so it is
  intended to be run destructively rather than only inspected.
- ``operator`` - the module has a ``main``, so somebody is meant to invoke it.

None of those makes a module wrong, and the report gates nothing. What it does
is put ``writes`` and ``applies`` at the top, because "untested" means something
different for a module that prints a census than for one that rewrites imports.

Reach is computed through :func:`dev.quality.facade_retirement.imported_modules`
rather than a walk written here. That rule - an import references more modules
than it resolves to - has produced three defects in this campaign, one of them a
hand-written version of exactly this measurement that reported six tested
modules as untested. Asking the shared function is the whole reason this module
can be trusted about its own subject.
"""

from __future__ import annotations

import ast
import collections
import pathlib
import sys
from dataclasses import dataclass
from typing import Final

from .facade_retirement import imported_modules

__all__ = [
    "CAPABILITIES",
    "UnreachedModule",
    "module_capabilities",
    "unreached_modules",
]

#: Every capability this report can attribute, worst first. Declared once so the
#: ordering and the census cannot disagree about what they rank.
CAPABILITIES: Final[tuple[str, ...]] = ("writes", "applies", "operator")

#: Calls that change the tree. Matched on the attribute name, which is what a
#: reader greps for, and deliberately not on the full call chain - ``path.write_text``
#: and ``atomic_write_text`` are the same risk under different spellings.
#:
#: ``replace`` was here and is not, because ``str.replace`` is far commoner than
#: ``Path.replace`` and no attribute-name test can tell them apart. It attributed
#: ``writes`` to two modules whose only offence was normalising a path separator,
#: putting them in the same rank as a codemod - which is the failure that costs
#: most in a report whose whole purpose is ranking. The lost ``Path.replace``
#: detections are the price, and they are rare where the other five are not.
_WRITE_CALLS: Final[frozenset[str]] = frozenset({"write_text", "write_bytes", "rename", "unlink", "mkdir", "rmdir"})

_DEV_ROOT: Final[pathlib.Path] = pathlib.Path("dev")


@dataclass(frozen=True, slots=True)
class UnreachedModule:
    """One module no test imports, and what running it can do."""

    dotted: str
    path: str
    capabilities: tuple[str, ...]

    @property
    def rank(self) -> int:
        """Lower sorts first: a writing module outranks a reporting one."""
        return min((CAPABILITIES.index(name) for name in self.capabilities), default=len(CAPABILITIES))


def _is_test(path: pathlib.Path) -> bool:
    """Whether ``path`` is a test module, a test package member, or a conftest."""
    return "tests" in path.parts or path.name.startswith("test_") or path.name == "conftest.py"


def module_capabilities(tree: ast.Module) -> tuple[str, ...]:
    """Return what running the parsed module can do, worst first.

    Read from the syntax rather than by importing anything: importing a module
    to ask what it does is how a report acquires the side effects it is
    measuring.
    """
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            attribute = node.func.attr if isinstance(node.func, ast.Attribute) else None
            name = node.func.id if isinstance(node.func, ast.Name) else None
            if (attribute or "") in _WRITE_CALLS or (name or "").endswith("write_text"):
                found.add("writes")
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value == "--apply":
            found.add("applies")
        elif isinstance(node, ast.FunctionDef) and node.name == "main":
            found.add("operator")
    return tuple(name for name in CAPABILITIES if name in found)


def unreached_modules(root: pathlib.Path = _DEV_ROOT) -> tuple[UnreachedModule, ...]:
    """Return every module under ``root`` that no test in it reaches.

    Package initialisers are excluded: they are inert namespace markers in this
    tree, so "no test imports it" says nothing about them.

    Both walks below skip a file they cannot read, and the two skips fail in
    OPPOSITE directions, which is why they are reported separately.

    A skipped TEST contributes no imports, so every module only it reaches is
    reported unreached - a false finding, and this list is used to choose
    work. A skipped MODULE is dropped from the result entirely, so a genuinely
    unreached module becomes invisible - the finding disappears instead.

    Measured over this tree: 520 test modules and 356 modules, none
    unparsable. Both skips are announced rather than fatal, because a tree
    edited concurrently can present a half-written file and one bad file must
    not cost the report.
    """
    modules: dict[str, pathlib.Path] = {}
    tests: list[pathlib.Path] = []
    for path in sorted(root.rglob("*.py")):
        if "__pycache__" in path.parts or path.name == "__init__.py":
            continue
        if _is_test(path):
            tests.append(path)
        else:
            modules[".".join(path.with_suffix("").parts)] = path

    unread_tests: list[str] = []
    unread_modules: list[str] = []
    reached: set[str] = set()
    for path in tests:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError, OSError) as error:
            unread_tests.append(f"{path}: {error}")
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom | ast.Import):
                reached.update(imported_modules(node, path))

    unreached: list[UnreachedModule] = []
    for dotted, path in sorted(modules.items()):
        if dotted in reached:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError, OSError) as error:
            unread_modules.append(f"{path}: {error}")
            continue
        unreached.append(UnreachedModule(dotted=dotted, path=path.as_posix(), capabilities=module_capabilities(tree)))
    if unread_tests:
        sys.stderr.write(
            f"module_test_reach: {len(unread_tests)} test module(s) could not be read, so any "
            "module only they import is listed unreached in error: " + repr(unread_tests) + chr(10)
        )
    if unread_modules:
        sys.stderr.write(
            f"module_test_reach: {len(unread_modules)} module(s) could not be read and are "
            "absent from this report entirely: " + repr(unread_modules) + chr(10)
        )
    return tuple(sorted(unreached, key=lambda item: (item.rank, item.dotted)))


def main() -> int:
    """Print one row per unreached module, most capable first; always exit 0."""
    unreached = unreached_modules()
    for item in unreached:
        sys.stdout.write(f"module_test_reach path={item.path} capabilities={','.join(item.capabilities) or 'none'}\n")
    tally: collections.Counter[str] = collections.Counter(name for item in unreached for name in item.capabilities)
    census = " ".join(f"{name}={tally[name]}" for name in CAPABILITIES)
    writing = [item for item in unreached if "writes" in item.capabilities]
    sys.stdout.write(
        f"summary unreached={len(unreached)} {census} writing_and_applying="
        + str(sum(1 for item in writing if "applies" in item.capabilities))
        + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
