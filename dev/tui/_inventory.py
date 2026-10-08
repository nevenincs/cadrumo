"""Every TUI interface the source tree defines, found by reading it.

The inventory is derived, never hand-listed: a class is in it because it
subclasses a Textual ``App`` or ``Screen``, transitively, somewhere under
``src/cadrumo/entrypoints/tui``. Nothing here counts interfaces, and no
constant records how many there are -- a tally would encode this moment and
then stop detecting anything.

Reading rather than importing is forced by the architecture decision that
bars a development tool from importing, loading, annotating against or
registering from the TUI package. An AST walk over the source text takes
none of those actions, and is the same technique the shared source-import
analysis uses to inspect ``src`` from outside it.
"""

from __future__ import annotations

import ast
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Final

from dev._paths import REPO_ROOT, UTF_8
from dev.first_party_source import is_test_source

TUI_ROOT: Final[Path] = REPO_ROOT / "src" / "cadrumo" / "entrypoints" / "tui"

_TEXTUAL_APP_ROOT: Final[str] = "textual.app.App"
_TEXTUAL_SCREEN_ROOTS: Final[frozenset[str]] = frozenset({"textual.screen.Screen", "textual.screen.ModalScreen"})
"""The qualified Textual bases that make a subclass an operator-facing surface."""


def _source_declarations(root: Path) -> dict[str, _Declaration]:
    """Source declarations."""
    declared: dict[str, _Declaration] = {}
    for path in sorted(root.rglob("*.py")):
        if is_test_source(path, root=root):
            continue
        tree = ast.parse(path.read_text(encoding=UTF_8), filename=str(path))
        module = _module_name(path)
        bindings = _import_bindings(tree, module, is_package=path.name == "__init__.py")
        for node in ast.walk(tree):
            _record_class_declaration(node, module, path, bindings, declared)
    return declared


def _interface_lineage(declared: dict[str, _Declaration]) -> tuple[set[str], set[str], dict[str, list[str]]]:
    """Interface lineage."""
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
            grown = _admit_interface_declaration(qualname, declaration, apps, screens, resolve_base) or grown
        if not grown:
            break

    children: dict[str, list[str]] = {}
    for qualname, declaration in declared.items():
        _register_subclasses(qualname, declaration, resolve_base, apps, screens, children)
    return (apps, screens, children)


def _declared_interfaces(
    declared: dict[str, _Declaration], apps: set[str], screens: set[str], children: dict[str, list[str]]
) -> tuple[Interface, ...]:
    """Declared interfaces."""
    interfaces = [
        Interface(
            name=declaration.name,
            module=_module_name(declaration.path),
            path=declaration.path,
            line=declaration.line,
            kind=InterfaceKind.APP if qualname in apps else InterfaceKind.SCREEN,
            bases=declaration.bases,
            subclassed_by=tuple(sorted(children.get(qualname, ()))),
        )
        for qualname, declaration in declared.items()
        if qualname in apps or qualname in screens
    ]
    return tuple(sorted(interfaces, key=lambda item: item.qualname))


@dataclass(frozen=True)
class _Declaration:
    """One class plus import-resolved base references used by the census."""

    name: str
    path: Path
    line: int
    bases: tuple[str, ...]
    resolved_bases: tuple[str, ...]


class InterfaceKind(StrEnum):
    """What kind of operator-facing surface an interface class is.

    The one definition of the vocabulary. It was previously spelled as prose
    in the field docstring below over a field typed ``str``, which accepted
    every string and checked none -- the same hole the frame failure
    vocabulary had, one record over, on a field the manifest reader also
    revalidates from disk.
    """

    APP = "app"
    """A full-screen application: a subclass of Textual's ``App``."""

    SCREEN = "screen"
    """A screen or modal: a subclass of ``Screen`` or ``ModalScreen``."""


@dataclass(frozen=True)
class Interface:
    """One TUI interface class, as the source tree declares it."""

    name: str
    module: str
    path: Path
    line: int
    kind: InterfaceKind
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
        _record_import_bindings(node, module, is_package, bindings)
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


def scan(root: Path = TUI_ROOT) -> tuple[Interface, ...]:
    """Return every ``App`` or ``Screen`` subclass declared under ``root``.

    Resolution is transitive and order-independent: a class extending a local
    base that itself extends ``App`` is reached by repeating the sweep until
    it stops growing, so declaration order across files never decides whether
    an interface is found.
    """
    declared = _source_declarations(root)

    apps, screens, children = _interface_lineage(declared)

    return _declared_interfaces(declared, apps, screens, children)


__all__ = ["TUI_ROOT", "Interface", "InterfaceKind", "scan"]


def _record_import_bindings(node: ast.stmt, module: str, is_package: bool, bindings: dict[str, str]) -> None:
    """Record import bindings."""
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


def _record_class_declaration(
    node: ast.AST, module: str, path: Path, bindings: dict[str, str], declared: dict[str, _Declaration]
) -> None:
    """Record class declaration."""
    if not isinstance(node, ast.ClassDef):
        return
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


def _admit_interface_declaration(
    qualname: str,
    declaration: _Declaration,
    apps: set[str],
    screens: set[str],
    resolve_base: Callable[[str, str], str | None],
) -> bool:
    """Admit one class against the current transitive Textual lineage."""
    if qualname in apps or qualname in screens:
        return False
    resolved_bases = {
        resolved
        for base in declaration.resolved_bases
        if (resolved := resolve_base(_module_name(declaration.path), base))
    }
    if _TEXTUAL_APP_ROOT in declaration.resolved_bases or apps & resolved_bases:
        apps.add(qualname)
        return True
    elif _TEXTUAL_SCREEN_ROOTS & set(declaration.resolved_bases) or screens & resolved_bases:
        screens.add(qualname)
        return True
    return False


def _register_subclasses(
    qualname: str,
    declaration: _Declaration,
    resolve_base: Callable[[str, str], str | None],
    apps: set[str],
    screens: set[str],
    children: dict[str, list[str]],
) -> None:
    """Register subclasses."""
    for base in declaration.resolved_bases:
        resolved = resolve_base(_module_name(declaration.path), base)
        if resolved in apps or resolved in screens:
            children.setdefault(resolved, []).append(qualname)
