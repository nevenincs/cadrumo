"""Every TUI interface the source tree defines, found by reading it.

The inventory is derived, never hand-listed: a class is in it because it
subclasses a Textual ``App`` or ``Screen``, transitively, somewhere under
``src/cadrumo/entrypoints/tui``. Nothing here counts interfaces, and no
constant records how many there are -- a tally would encode this moment and
then stop detecting anything.

Reading rather than importing is forced by the architecture decision that
bars a development tool from importing, loading, annotating against or
registering from the TUI package. An AST walk over the source text takes
none of those actions, and is the same technique the import-hygiene scanner
already uses to inspect ``src`` from outside it.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from .._paths import REPO_ROOT, UTF_8

TUI_ROOT: Final[Path] = REPO_ROOT / "src" / "cadrumo" / "entrypoints" / "tui"

_TEXTUAL_ROOTS: Final[frozenset[str]] = frozenset({"App", "Screen", "ModalScreen"})
"""The Textual base classes that make a subclass an operator-facing surface."""


@dataclass(frozen=True)
class Interface:
    """One TUI interface class, as the source tree declares it."""

    name: str
    module: str
    path: Path
    line: int
    kind: str
    """``app`` for a full-screen application, ``screen`` for a screen or modal."""
    bases: tuple[str, ...]
    subclassed_by: tuple[str, ...]

    @property
    def qualname(self) -> str:
        """The dotted module path plus class name."""
        return f"{self.module}.{self.name}"

    @property
    def is_base(self) -> bool:
        """Whether another interface in the tree extends this one.

        A class that is only ever subclassed is a substrate, not a surface an
        operator reaches, so the catalogue is allowed to leave it unrendered
        without that counting as a coverage gap.
        """
        return bool(self.subclassed_by)


def _base_name(node: ast.expr) -> str | None:
    """Reduce a base-class expression to the bare class name it names."""
    match node:
        case ast.Name(id=name):
            return name
        case ast.Attribute(attr=name):
            return name
        case ast.Subscript(value=value):
            return _base_name(value)
        case _:
            return None


def _module_name(path: Path) -> str:
    """The dotted import path a source file would be imported under."""
    relative = path.relative_to(REPO_ROOT / "src").with_suffix("")
    return ".".join(relative.parts)


def _is_test_path(path: Path) -> bool:
    """Whether a file sits in a test tree rather than the shipped surface."""
    return "tests" in path.parts


def scan(root: Path = TUI_ROOT) -> tuple[Interface, ...]:
    """Return every ``App`` or ``Screen`` subclass declared under ``root``.

    Resolution is transitive and order-independent: a class extending a local
    base that itself extends ``App`` is reached by repeating the sweep until
    it stops growing, so declaration order across files never decides whether
    an interface is found.
    """
    declared: dict[str, tuple[str, Path, int, tuple[str, ...]]] = {}
    for path in sorted(root.rglob("*.py")):
        if _is_test_path(path):
            continue
        tree = ast.parse(path.read_text(encoding=UTF_8), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            bases = tuple(name for name in (_base_name(base) for base in node.bases) if name is not None)
            if bases:
                module = _module_name(path)
                declared[f"{module}.{node.name}"] = (node.name, path, node.lineno, bases)

    by_name: dict[str, list[str]] = {}
    for qualname, (name, _path, _line, _bases) in declared.items():
        by_name.setdefault(name, []).append(qualname)

    def resolve_base(module: str, base: str) -> str | None:
        """Resolve a local base first, then an unambiguous imported class name."""
        local = f"{module}.{base}"
        if local in declared:
            return local
        candidates = by_name.get(base, ())
        return candidates[0] if len(candidates) == 1 else None

    apps: set[str] = set()
    screens: set[str] = set()
    while True:
        grown = False
        for qualname, (_name, path, _line, bases) in declared.items():
            if qualname in apps or qualname in screens:
                continue
            resolved_bases = {resolved for base in bases if (resolved := resolve_base(_module_name(path), base))}
            if "App" in bases or apps & resolved_bases:
                apps.add(qualname)
                grown = True
            elif {"Screen", "ModalScreen"} & set(bases) or screens & resolved_bases:
                screens.add(qualname)
                grown = True
        if not grown:
            break

    children: dict[str, list[str]] = {}
    for qualname, (_name, path, _line, bases) in declared.items():
        for base in bases:
            resolved = resolve_base(_module_name(path), base)
            if resolved in apps or resolved in screens:
                children.setdefault(resolved, []).append(qualname)

    interfaces = [
        Interface(
            name=name,
            module=_module_name(path),
            path=path,
            line=line,
            kind="app" if qualname in apps else "screen",
            bases=bases,
            subclassed_by=tuple(sorted(children.get(qualname, ()))),
        )
        for qualname, (name, path, line, bases) in declared.items()
        if qualname in apps or qualname in screens
    ]
    return tuple(sorted(interfaces, key=lambda item: item.qualname))


__all__ = ["TUI_ROOT", "Interface", "scan"]
