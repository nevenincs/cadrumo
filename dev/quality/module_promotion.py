"""Rename a private module to a public one and move every reference with it.

A facade cannot be retired while the symbols it forwards live in
leading-underscore modules: repointing an outside consumer at a private module
trades one boundary violation for a worse one. Giving those symbols a public
home is the precondition, and it is a rename plus a sweep of everything that
named the old path.

The sweep is the part that goes wrong. A module is referenced four ways and they
do not look alike:

- an absolute import, ``from dev.docs.preprocess._html import build_outputs``
- a relative import from inside the package, ``from ._html import build_outputs``
- a relative import from OUTSIDE it, ``from ...docs.preprocess._html import ...``
- the module imported BY NAME from its package, ``from .. import _html``
- dotted prose in a docstring, ``:mod:`dev.docs.preprocess._html```

The fourth resolves to the PACKAGE, not to the module, so a resolver looking for
the module's own dotted name never sees it - and the name it imports is exactly
the one that changes. Two files broke this way after seven renames, and a test
here had asserted the opposite: that traversal survives a rename. It does not.
Traversal survives a FACADE retirement, which is a different operation.

A module imported by name is then USED by name - ``_runner.publish(...)``,
``inspect.getsource(_compare)`` - and both have to move together. Rewriting the
import alone leaves the body referring to a name nothing binds, which is a
``NameError`` at the first call rather than an ``ImportError`` at collection:
later, and in a narrower test. Body uses are rewritten only in files whose
traversal import was itself rewritten, so a same-named local elsewhere is never
touched.

The third is the one that gets missed, and it was: a first version of this
handled relative imports for files inside the package and dotted text anywhere,
which leaves a three-dot import from a sibling tree falling between the two
branches. Two files broke at import. Every import here is resolved to its
absolute dotted name through one function instead, so where the file sits stops
mattering.

A statement that resolves to the renamed module but cannot be rewritten is
REPORTED, never skipped. Silence is the failure mode that costs the most: the
same relative-depth bug in a consumer scan reported zero consumers where there
were ninety, and a zero looks like a finished job.

Read-only by default; ``--apply`` performs the rename and the rewrite.
"""

from __future__ import annotations

import argparse
import ast
import pathlib
import sys
from dataclasses import dataclass
from typing import Final

from .facade_retirement import imported_modules, resolve_relative

__all__ = [
    "PromotionPlan",
    "ReferenceEdit",
    "plan_promotion",
    "public_name_is_safe",
]

#: Standard-library top-level module names a public module must not take. A
#: package-relative import would still resolve correctly, so this is not a
#: correctness rule - it is a readability one, and it is the reason
#: ``_html`` was promoted to ``normatives_html`` rather than to ``html``.
STDLIB_COLLISIONS: Final[frozenset[str]] = frozenset(sys.stdlib_module_names)


@dataclass(frozen=True, slots=True)
class ReferenceEdit:
    """One line naming the old module, and what it becomes."""

    path: pathlib.Path
    lineno: int
    before: str
    after: str
    #: ``import`` for a resolved import statement, ``traversal`` for the module
    #: imported by name from its package, ``usage`` for a body reference to that
    #: name, ``prose`` for dotted text.
    kind: str


@dataclass(frozen=True, slots=True)
class PromotionPlan:
    """Everything one rename touches."""

    old_dotted: str
    new_dotted: str
    module_file: pathlib.Path
    edits: tuple[ReferenceEdit, ...]
    #: Statements resolving to the renamed module that could not be rewritten.
    #: Never empty silently: a plan carrying one of these is not safe to apply.
    unhandled: tuple[ReferenceEdit, ...]
    #: Files the sweep could not read or parse. A file that does not parse is a
    #: file whose references were not examined, and reporting the plan without
    #: saying so would be the same silence this module exists to avoid - the
    #: sweep would look complete because the miss produced no output.
    unreadable: tuple[pathlib.Path, ...] = ()

    @property
    def files(self) -> int:
        """How many distinct files the rename touches."""
        return len({edit.path for edit in self.edits})


def public_name_is_safe(name: str) -> bool:
    """Whether a promoted module name avoids shadowing the standard library.

    ``html``, ``types``, ``schema``... only the first two are stdlib, and the
    check is against the live interpreter's own list rather than a written one,
    which would be a restatement that goes stale with the Python version.
    """
    return not name.startswith("_") and name not in STDLIB_COLLISIONS


def _rename_imported_name(line: str, old_stem: str, new_stem: str) -> str:
    """Replace a bare imported NAME on one line, leaving similar words alone.

    ``from .. import _compare`` and ``from .. import _compare, _schema`` both
    occur, and so does a multi-line parenthesised form where the name sits on
    its own line. The name is bounded by non-identifier characters on both
    sides, so ``_compare`` cannot claim the text of ``_comparison``.
    """
    result: list[str] = []
    index = 0
    while (found := line.find(old_stem, index)) != -1:
        before_ok = found == 0 or not (line[found - 1].isalnum() or line[found - 1] == "_")
        end = found + len(old_stem)
        after_ok = end >= len(line) or not (line[end].isalnum() or line[end] == "_")
        result.append(line[index:found])
        result.append(new_stem if (before_ok and after_ok) else old_stem)
        index = end
    result.append(line[index:])
    return "".join(result)


def plan_promotion(
    package_dir: pathlib.Path, old_stem: str, new_stem: str, *, search_root: pathlib.Path
) -> PromotionPlan:
    """Return every edit renaming ``old_stem`` to ``new_stem`` implies.

    Imports are matched by RESOLVING them, so an absolute import, a
    one-dot import from a sibling module and a three-dot import from another
    tree are all recognised as the same reference. Prose is matched on the
    fully-qualified dotted path, which is unambiguous and cannot collide with a
    same-named private module in another package - and several of these packages
    do have a ``_schema`` apiece.
    """
    package_dotted = ".".join(package_dir.parts)
    old_dotted = f"{package_dotted}.{old_stem}"
    new_dotted = f"{package_dotted}.{new_stem}"

    edits: list[ReferenceEdit] = []
    unhandled: list[ReferenceEdit] = []
    unreadable: list[pathlib.Path] = []
    traversal_files: set[pathlib.Path] = set()
    for path in sorted(search_root.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        try:
            text = path.read_text(encoding="utf-8")
            tree = ast.parse(text)
        except (SyntaxError, UnicodeDecodeError, OSError):
            unreadable.append(path)
            continue
        lines = text.splitlines()
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or resolve_relative(node, path) != old_dotted:
                continue
            before = lines[node.lineno - 1]
            after = before.replace(f".{old_stem} import", f".{new_stem} import", 1)
            record = ReferenceEdit(path=path, lineno=node.lineno, before=before, after=after, kind="import")
            (edits if after != before else unhandled).append(record)
        for node in ast.walk(tree):
            # The module imported by name from its own package. This RESOLVES to
            # the package, so the loop above never sees it, and the name in the
            # import list is precisely what the rename changes.
            # ``imported_modules`` is the shared answer to "which modules does
            # this statement reference", and asking it here rather than
            # re-deriving the rule is what keeps the two walks agreeing.
            if not isinstance(node, ast.ImportFrom):
                continue
            if old_dotted not in imported_modules(node, path):
                continue
            if resolve_relative(node, path) != package_dotted:
                continue
            for offset in range(node.lineno - 1, node.end_lineno or node.lineno):
                before = lines[offset]
                after = _rename_imported_name(before, old_stem, new_stem)
                if after == before:
                    continue
                edits.append(ReferenceEdit(path=path, lineno=offset + 1, before=before, after=after, kind="traversal"))
                traversal_files.add(path)
        for index, line in enumerate(lines, start=1):
            if old_dotted in line:
                edits.append(
                    ReferenceEdit(
                        path=path,
                        lineno=index,
                        before=line,
                        after=line.replace(old_dotted, new_dotted),
                        kind="prose",
                    )
                )

    # A module imported by name is used by name; the two must move together.
    for path in sorted(traversal_files):
        text = path.read_text(encoding="utf-8")
        tree = ast.parse(text)
        lines = text.splitlines()
        for node in ast.walk(tree):
            if not isinstance(node, ast.Name) or node.id != old_stem or not isinstance(node.ctx, ast.Load):
                continue
            before = lines[node.lineno - 1]
            after = _rename_imported_name(before, old_stem, new_stem)
            if after != before:
                edits.append(ReferenceEdit(path=path, lineno=node.lineno, before=before, after=after, kind="usage"))
    return PromotionPlan(
        old_dotted=old_dotted,
        new_dotted=new_dotted,
        module_file=package_dir / f"{old_stem}.py",
        edits=tuple(edits),
        unhandled=tuple(unhandled),
        unreadable=tuple(unreadable),
    )


def apply_promotion(plan: PromotionPlan, *, new_stem: str) -> int:
    """Apply every edit and rename the module file; return files changed.

    Refuses when the plan carries an unhandled statement. A partial rename
    leaves the tree unimportable, and the one thing worse than stopping is
    stopping halfway.
    """
    if plan.unhandled:
        raise ValueError(f"{len(plan.unhandled)} statement(s) could not be rewritten; refusing to apply")

    by_path: dict[pathlib.Path, list[ReferenceEdit]] = {}
    for edit in plan.edits:
        by_path.setdefault(edit.path, []).append(edit)
    for path, items in by_path.items():
        lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
        for edit in items:
            ending = "\r\n" if lines[edit.lineno - 1].endswith("\r\n") else "\n"
            lines[edit.lineno - 1] = edit.after + ending
        path.write_text("".join(lines), encoding="utf-8", newline="\n")
    plan.module_file.rename(plan.module_file.with_name(f"{new_stem}.py"))
    return len(by_path)


def main() -> int:
    """Report or apply one promotion; exit 2 on an unsafe name or unhandled reference."""
    parser = argparse.ArgumentParser(description="Promote a private module to a public name.")
    parser.add_argument("package", help="package directory, e.g. dev/docs/preprocess")
    parser.add_argument("old_stem", help="current module stem, e.g. _html")
    parser.add_argument("new_stem", help="public module stem, e.g. normatives_html")
    parser.add_argument("--apply", action="store_true", help="perform the rename and rewrite")
    arguments = parser.parse_args()

    if not public_name_is_safe(arguments.new_stem):
        sys.stderr.write(f"{arguments.new_stem} is private or shadows a standard-library module\n")
        return 2

    plan = plan_promotion(
        pathlib.Path(arguments.package),
        arguments.old_stem,
        arguments.new_stem,
        search_root=pathlib.Path("dev"),
    )
    for edit in plan.edits:
        sys.stdout.write(f"module_promotion {edit.kind} {edit.path}:{edit.lineno} {edit.before.strip()}\n")
    for edit in plan.unhandled:
        sys.stdout.write(f"module_promotion UNHANDLED {edit.path}:{edit.lineno} {edit.before.strip()}\n")
    if plan.unhandled:
        sys.stderr.write(f"{len(plan.unhandled)} statement(s) could not be rewritten\n")
        return 2
    if arguments.apply:
        changed = apply_promotion(plan, new_stem=arguments.new_stem)
        sys.stdout.write(f"applied files={changed} module={plan.new_dotted}\n")
    sys.stdout.write(
        f"summary old={plan.old_dotted} new={plan.new_dotted} edits={len(plan.edits)} "
        f"files={plan.files} unhandled={len(plan.unhandled)}\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
