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
import re
import sys
from dataclasses import dataclass
from pathlib import Path

__all__ = [
    "DanglingReference",
    "collect_defined_names",
    "dangling_references",
    "docstring_references",
]

_PACKAGE_ROOT = Path(__file__).resolve().parent.parent.parent / "src" / "cadrumo"

#: Sphinx roles that name a code object. ``:ref:`` and ``:doc:`` name document
#: anchors instead and are not this screen's business.
_ROLE = re.compile(r":(?:func|class|data|meth|attr|mod|obj|exc):`([^`]+)`")


@dataclass(frozen=True, slots=True)
class DanglingReference:
    """One docstring cross-reference whose target the package does not define."""

    module: str
    target: str
    role_text: str


def _module_symbols(tree: ast.Module) -> set[str]:
    """Return every name a module binds at module level, plus its class members."""
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            names.update(t.id for t in node.targets if isinstance(t, ast.Name))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return names


def _imported_names(tree: ast.Module) -> set[str]:
    """Return every name a module imports, under whatever alias it binds."""
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                names.add(alias.asname or alias.name.split(".")[0])
                names.add(alias.name.rsplit(".", 1)[-1])
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
            if not isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            text = ast.get_docstring(node)
            if not text:
                continue
            found.extend((module, match) for match in _ROLE.findall(text))
    return found


def dangling_references(root: Path) -> tuple[DanglingReference, ...]:
    """Report each cross-reference naming something the package does not define."""
    defined, imported, modules = collect_defined_names(root)
    # A `:mod:` role is habitually written relatively -- ``:mod:`_ledger``` for
    # ``cadrumo.entrypoints.cli._ledger`` -- so a bare last segment names a real
    # module and must not be reported as dangling.
    leaves = {name.rsplit(".", 1)[-1] for name in modules}
    known = defined | imported | leaves | set(dir(builtins))
    findings: list[DanglingReference] = []
    for module, raw in docstring_references(root):
        target = raw.lstrip("~.").split("(")[0].strip()
        if not target:
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
