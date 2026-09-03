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

_TEXTUAL_APP_ROOT: Final[str] = "textual.app.App"
_TEXTUAL_SCREEN_ROOTS: Final[frozenset[str]] = frozenset(
    {"textual.screen.Screen", "textual.screen.ModalScreen"}
)
"""The qualified Textual bases that make a subclass an operator-facing surface."""


@dataclass(frozen=True)
class _Declaration:
    """One class plus import-resolved base references used by the census."""

    name: str
    path: Path
    line: int
    bases: tuple[str, ...]
    resolved_bases: tuple[str, ...]


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


def _base_reference(node: ast.expr) -> str | None:
    """Return the complete dotted spelling of one class base expression."""
    match node:
        case ast.Name(id=name):
            return name
        case ast.Attribute(value=value, attr=name):
            prefix = _base_reference(value)
            return None if prefix is None else f"{prefix}.{name}"
        case ast.Subscript(value=value):
            return _base_reference(value)
        case _:
            return None


def _imported_module(module: str, imported: str | None, level: int, *, is_package: bool) -> str:
    """Resolve an ``ImportFrom`` module exactly as Python's relative grammar does."""
    if level == 0:
        return imported or ""
    package = module.split(".") if is_package else module.split(".")[:-1]
    keep = len(package) - (level - 1)
    prefix = package[: max(keep, 0)]
    if imported:
        prefix.extend(imported.split("."))
    return ".".join(prefix)


def _import_bindings(tree: ast.Module, module: str, *, is_package: bool) -> dict[str, str]:
    """Map module-level imported names and aliases to their qualified symbols."""
    bindings: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            source = _imported_module(module, node.module, node.level, is_package=is_package)
            for alias in node.names:
                if alias.name == "*":
                    continue
                local = alias.asname or alias.name
                bindings[local] = f"{source}.{alias.name}" if source else alias.name
        elif isinstance(node, ast.Import):
            for alias in node.names:
                local = alias.asname or alias.name.split(".", maxsplit=1)[0]
                bindings[local] = alias.name if alias.asname else local
    return bindings


def _resolve_import_alias(reference: str, bindings: dict[str, str]) -> str:
    """Resolve the leading name of a base through its module import binding."""
    leading, separator, remainder = reference.partition(".")
    target = bindings.get(leading)
    if target is None:
        return reference
    return f"{target}.{remainder}" if separator else target


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
    declared: dict[str, _Declaration] = {}
    for path in sorted(root.rglob("*.py")):
        if _is_test_path(path):
            continue
        tree = ast.parse(path.read_text(encoding=UTF_8), filename=str(path))
        module = _module_name(path)
        bindings = _import_bindings(tree, module, is_package=path.name == "__init__.py")
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            bases = tuple(name for name in (_base_name(base) for base in node.bases) if name is not None)
            if bases:
                resolved_bases = tuple(
                    _resolve_import_alias(reference, bindings)
                    for reference in (_base_reference(base) for base in node.bases)
                    if reference is not None
                )
                declared[f"{module}.{node.name}"] = _Declaration(
                    name=node.name,
                    path=path,
                    line=node.lineno,
                    bases=bases,
                    resolved_bases=resolved_bases,
                )

    by_name: dict[str, list[str]] = {}
    for qualname, declaration in declared.items():
        by_name.setdefault(declaration.name, []).append(qualname)

    def resolve_base(module: str, base: str) -> str | None:
        """Resolve a local base first, then an unambiguous imported class name."""
        local = f"{module}.{base}"
        if local in declared:
            return local
        if base in declared:
            return base
        candidates = by_name.get(base.rsplit(".", maxsplit=1)[-1], ())
        return candidates[0] if len(candidates) == 1 else None

    apps: set[str] = set()
    screens: set[str] = set()
    while True:
        grown = False
        for qualname, declaration in declared.items():
            if qualname in apps or qualname in screens:
                continue
            resolved_bases = {
                resolved
                for base in declaration.resolved_bases
                if (resolved := resolve_base(_module_name(declaration.path), base))
            }
            if _TEXTUAL_APP_ROOT in declaration.resolved_bases or apps & resolved_bases:
                apps.add(qualname)
                grown = True
            elif _TEXTUAL_SCREEN_ROOTS & set(declaration.resolved_bases) or screens & resolved_bases:
                screens.add(qualname)
                grown = True
        if not grown:
            break

    children: dict[str, list[str]] = {}
    for qualname, declaration in declared.items():
        for base in declaration.resolved_bases:
            resolved = resolve_base(_module_name(declaration.path), base)
            if resolved in apps or resolved in screens:
                children.setdefault(resolved, []).append(qualname)

    interfaces = [
        Interface(
            name=declaration.name,
            module=_module_name(declaration.path),
            path=declaration.path,
            line=declaration.line,
            kind="app" if qualname in apps else "screen",
            bases=declaration.bases,
            subclassed_by=tuple(sorted(children.get(qualname, ()))),
        )
        for qualname, declaration in declared.items()
        if qualname in apps or qualname in screens
    ]
    return tuple(sorted(interfaces, key=lambda item: item.qualname))


__all__ = ["TUI_ROOT", "Interface", "scan"]
