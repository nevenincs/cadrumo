"""Screen: docstring cross-references that name nothing.

A Sphinx role in a docstring -- ``:func:`resolve_read_id```, ``:class:`Widget```
-- is a claim that the named symbol exists. Nothing checks it, so the claim
survives the symbol: a rename updates the code and leaves the prose, and a
deletion leaves a reference to something gone.

That is not cosmetic. This project has hit the consequence repeatedly. A
comment explained what a constant deliberately was NOT, months after that
constant was deleted. A module docstring told readers that the ledger read
verbs use ``resolve_read_id``, while the read verbs called a different function
and ``resolve_read_id`` itself had no caller at all -- so the prose pointed at
the copy nothing ran, and reading it would have sent a maintainer to the wrong
code. Documentation that names a dead symbol is worse than none: it is
confidently wrong.

A finding is a question, never a patch. Some of these references are accurate
statements about the PAST: ``core.decimal.formatting`` records that it
"consolidates the four independent ``_format_decimal`` copies that previously
lived in :mod:`_censo_live`, :mod:`_reconcile`, :mod:`_projection` and
:mod:`_translator`" -- four modules that no longer exist, named correctly. An
automated rewrite to the surviving public spellings was attempted here and
reverted: it repointed whichever of the four happened to have a public
namesake, turning a true sentence about history into a false one about the
present, and leaving the list internally inconsistent. Read each row before
touching it.

Only names this package could own are checked. A reference rooted at
``cadrumo`` must resolve to a module or a symbol the tree defines. A bare name
is checked only when the tree neither defines nor imports it anywhere, which is
what keeps ``:class:`Path``` and ``:class:`BaseModel``` out of the report
without an allowlist to maintain.

The screen exits 0 whatever it finds; the gate that refuses is a test.
"""

from __future__ import annotations

import argparse
import ast
import builtins
import collections
import itertools
import re
import sys
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

__all__ = [
    "DanglingReference",
    "collect_defined_names",
    "dangling_references",
    "docstring_references",
]

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_PACKAGE_ROOT = _REPO_ROOT / "src" / "cadrumo"

#: Trees that are not scanned for findings but whose module names a docstring
#: may legitimately reference. A gate in `src` naming its counterpart in
#: `dev/tests` is citing something real; reporting it would be an artefact of
#: where this screen happens to look.
_SIBLING_TREES: tuple[Path, ...] = (_REPO_ROOT / "dev", _REPO_ROOT / "src" / "cadrumo_harness")

#: Sphinx roles that name a code object. ``:ref:`` and ``:doc:`` name document
#: anchors instead and are not this screen's business.
_ROLE = re.compile(r":(?:func|class|data|meth|attr|mod|obj|exc):`([^`]+)`")

#: A long reference wraps inside its backticks, and the halves of a dotted path
#: resume on the next line with no space between them -- which is how Sphinx
#: reads it, and how it must be rejoined before resolving.
_REWRAP = re.compile(r"\s*\n\s*")


@dataclass(frozen=True, slots=True)
class DanglingReference:
    """One docstring cross-reference whose target the package does not define."""

    module: str
    target: str
    role_text: str


def _module_symbols(tree: ast.Module) -> set[str]:
    """Return every name a module binds: module level, class members, attributes.

    Instance attributes count. An ``:attr:`accepted_period_tokens``` reference
    names something assigned as ``self.accepted_period_tokens`` in ``__init__``
    and nowhere else, so a collector that only saw module-level bindings
    reported a live attribute as naming nothing.

    Function PARAMETERS are deliberately not collected. They would swell the
    known set with every argument name in the tree and start suppressing real
    findings, and a docstring names a parameter with ``:param:``, which is not
    a role this screen reads.
    """
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
                elif isinstance(target, ast.Attribute):
                    names.add(target.attr)
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name):
                names.add(node.target.id)
            elif isinstance(node.target, ast.Attribute):
                names.add(node.target.attr)
    return names


def _imported_names(tree: ast.Module) -> set[str]:
    """Return every name a module imports, plus the packages it imports FROM.

    The source package matters as much as the symbol. ``from
    cryptography.hazmat.primitives import hashes`` makes ``cryptography`` a
    name this tree demonstrably knows, and a screen that recorded only
    ``hashes`` reported ``:mod:`cryptography``` as naming nothing while
    twenty-two modules imported from it.
    """
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                names.add(alias.asname or alias.name.split(".")[0])
                names.add(alias.name.rsplit(".", 1)[-1])
        if isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
            names.add(node.module.rsplit(".", 1)[-1])
    return names


def collect_defined_names(root: Path) -> tuple[set[str], set[str], set[str]]:
    """Return (symbols defined, names imported, module dotted paths) for the tree."""
    defined: set[str] = set()
    imported: set[str] = set()
    modules: set[str] = set()
    for path in sorted(root.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        relative = path.relative_to(root.parent).with_suffix("")
        parts = list(relative.parts)
        if parts[-1] == "__init__":
            parts.pop()
        modules.add(".".join(parts))
        defined |= _module_symbols(tree)
        imported |= _imported_names(tree)
    return defined, imported, modules


def docstring_references(root: Path) -> list[tuple[str, str]]:
    """Return every (module, target) a docstring cross-reference names."""
    found: list[tuple[str, str]] = []
    for path in sorted(root.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        module = path.relative_to(root).as_posix()
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                text = ast.get_docstring(node)
                if text:
                    found.extend((module, match) for match in _ROLE.findall(text))
            for text in _attribute_docstrings(node):
                found.extend((module, match) for match in _ROLE.findall(text))
    return found


def _attribute_docstrings(node: ast.AST) -> Iterator[str]:
    """Yield the docstring that follows each assignment in a statement body.

    ``ast.get_docstring`` reaches a module, class and function docstring and
    nothing else, so the bare string beneath an assignment -- the form this
    codebase uses to document a constant -- was never scanned at all. A planted
    reference sat in one without the screen noticing, which is what proving a
    gate end-to-end is for.
    """
    body = getattr(node, "body", None)
    if not isinstance(body, list):
        return
    for previous, statement in itertools.pairwise(body):
        if not isinstance(previous, (ast.Assign, ast.AnnAssign)):
            continue
        if (
            isinstance(statement, ast.Expr)
            and isinstance(statement.value, ast.Constant)
            and isinstance(statement.value.value, str)
        ):
            yield statement.value.value


def _subscript_names(target: str) -> tuple[str, ...]:
    """Return the base and argument names a subscripted reference addresses.

    ``Envelope[BlobManifest]`` claims both names exist. Splitting on the
    bracket and checking each is what keeps a legitimate generic from reading
    as one long name the package does not define.
    """
    try:
        parsed = ast.parse(target, mode="eval")
    except SyntaxError:
        return (target.split("[", 1)[0].strip(),)
    names: list[str] = []
    for node in ast.walk(parsed):
        if isinstance(node, ast.Name):
            names.append(node.id)
        elif isinstance(node, ast.Attribute):
            names.append(node.attr)
    return tuple(dict.fromkeys(names))


def dangling_references(root: Path) -> tuple[DanglingReference, ...]:
    """Report each cross-reference naming something the package does not define."""
    defined, imported, modules = collect_defined_names(root)
    for sibling in _SIBLING_TREES:
        if sibling.exists():
            # MODULE names only. Pulling in every symbol these trees define
            # would let a shipped docstring resolve against a dev-only function
            # and quietly stop reporting a reference that crosses out of the
            # package -- which is a finding, not noise.
            _sibling_defined, _sibling_imported, sibling_modules = collect_defined_names(sibling)
            modules |= sibling_modules
    # A `:mod:` role is habitually written relatively -- ``:mod:`_ledger``` for
    # ``cadrumo.entrypoints.cli._ledger`` -- so a bare last segment names a real
    # module and must not be reported as dangling.
    leaves = {name.rsplit(".", 1)[-1] for name in modules}
    known = defined | imported | leaves | set(dir(builtins))
    findings: list[DanglingReference] = []
    for module, raw in docstring_references(root):
        # A long reference wraps across lines inside its backticks; the halves
        # of a dotted path rejoin with no space, which is how Sphinx reads it.
        target = _REWRAP.sub("", raw).lstrip("~.").split("(")[0].strip()
        if not target:
            continue
        if "[" in target:
            # A subscripted generic names its base AND its arguments, all of
            # which the package may own: ``Envelope[BlobManifest]`` is two
            # claims, not one unresolvable string.
            findings.extend(
                DanglingReference(module=module, target=part, role_text=raw)
                for part in _subscript_names(target)
                if part not in known and part not in modules
            )
            continue
        rooted = target.startswith("cadrumo.")
        if rooted and (target in modules or any(target.startswith(f"{name}.") for name in modules)):
            leaf = target.rsplit(".", 1)[-1]
            if leaf in known or target in modules:
                continue
            findings.append(DanglingReference(module=module, target=target, role_text=raw))
            continue
        leaf = target.rsplit(".", 1)[-1]
        if leaf in known or target in modules:
            continue
        if not rooted and "." in target:
            # A dotted path this package does not root is a third-party object.
            continue
        findings.append(DanglingReference(module=module, target=target, role_text=raw))
    return tuple(findings)


def main(argv: list[str] | None = None) -> int:
    """Print one greppable row per dangling reference; always exit 0."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--limit", type=int, default=0, help="show at most this many rows")
    args = parser.parse_args(argv)

    findings = dangling_references(_PACKAGE_ROOT)
    rows = findings[: args.limit] if args.limit else findings
    for finding in rows:
        sys.stdout.write(f"dangling target={finding.target} module={finding.module}\n")
    by_module = collections.Counter(finding.module for finding in findings)
    sys.stdout.write(f"summary dangling={len(findings)} modules={len(by_module)}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
