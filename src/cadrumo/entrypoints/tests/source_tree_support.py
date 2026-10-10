"""Read a source tree's Python files and resolve the names each file binds.

A structural gate that reads what the source does has to answer two questions
before it can answer any other: which file an import statement names, and
where a name used in a file was defined. Both are answered here from syntax
alone, so a gate never imports the code it is reading, and two gates that ask
the same questions share one answer.

Paths are spelled with forward slashes relative to the tree root, optionally
behind a fixed prefix: a tree rooted at the repository spells
``src/cadrumo/...``, one rooted at the source directory spells ``cadrumo/...``.
"""

from __future__ import annotations

import ast
from collections.abc import Callable, Iterable, Mapping
from pathlib import Path

type NameOrigin = tuple[str, str]
"""The file that defines a name, and the name it carries there."""


def module_level_bindings(module: ast.Module) -> Iterable[tuple[str, ast.expr]]:
    """Every module-level ``name = value`` binding, annotated or not.

    A declaration carries the same meaning whether or not its author
    spelled a type for it, so both assignment forms are read. Reading only
    the bare form would let an annotated declaration leave a reading
    without any finding.
    """
    for node in module.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    yield target.id, node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.value is not None:
            yield node.target.id, node.value


class SourceTree:
    """The Python files of named top-level packages under one directory.

    Each file is parsed once and each import resolved once for the life of the
    tree; :meth:`cache_clear` drops both, so an owner can release the syntax
    trees of a large reading when it is done with them.
    """

    def __init__(
        self,
        root: Path,
        *,
        packages: frozenset[str],
        prefix: str = "",
        contains: Callable[[str], bool] | None = None,
    ) -> None:
        """Bind the tree to its directory, its packages and its file inventory.

        Args:
            root: Directory every path is relative to.
            packages: Top-level package names whose imports are resolved; an
                import of any other package names no file of this tree.
            prefix: Path spelled between the root and each package, ``"src"``
                for a tree rooted at the repository and empty for one rooted
                at the source directory.
            contains: Whether a path is a file of the tree. Defaults to the
                file existing on disk; a caller with a narrower inventory
                passes its own membership test.
        """
        self._root = root
        self._packages = packages
        self._prefix = tuple(part for part in prefix.split("/") if part)
        self._contains = contains if contains is not None else self._is_file
        self._parsed: dict[str, ast.Module] = {}
        self._module_paths: dict[tuple[str, str | None, int], str | None] = {}
        self._origins: dict[str, Mapping[str, NameOrigin]] = {}
        self._module_aliases: dict[str, Mapping[str, str]] = {}

    def _is_file(self, path: str) -> bool:
        return (self._root / path).is_file()

    def cache_clear(self) -> None:
        """Drop every parsed file and every resolved import."""
        self._parsed.clear()
        self._module_paths.clear()
        self._origins.clear()
        self._module_aliases.clear()

    def parsed(self, path: str) -> ast.Module:
        """Return the syntax tree of one file of the tree."""
        tree = self._parsed.get(path)
        if tree is None:
            tree = ast.parse((self._root / path).read_text(encoding="utf-8"), filename=path)
            self._parsed[path] = tree
        return tree

    def module_path(self, importer: str, module: str | None, level: int) -> str | None:
        """Resolve one import statement's module to a file of the tree.

        A reading that follows a name is only as good as this hop: a bare
        function name such as ``run`` or ``resolve`` is defined dozens of
        times across a tree, so a reference is resolved against the module
        the importing file actually names, never against every same-named
        helper in the tree.
        """
        key = (importer, module, level)
        if key not in self._module_paths:
            self._module_paths[key] = self._resolve_module_path(importer, module, level)
        return self._module_paths[key]

    def _resolve_module_path(self, importer: str, module: str | None, level: int) -> str | None:
        if level:
            base = importer.split("/")[:-1]
            if level > 1:
                base = base[: -(level - 1)]
            if not base:
                return None
        else:
            if module is None:
                return None
            package, _, rest = module.partition(".")
            if package not in self._packages:
                return None
            base = [*self._prefix, package]
            module = rest
        tail = [part for part in (module or "").split(".") if part]
        candidate = "/".join([*base, *tail])
        for suffix in (".py", "/__init__.py"):
            if self._contains(candidate + suffix):
                return candidate + suffix
        return None

    def name_origins(self, path: str) -> Mapping[str, NameOrigin]:
        """Every name this file binds, mapped to where it was defined.

        A name defined in the file itself resolves to the file; an imported
        name resolves to the module it was imported from. A locally defined
        name shadows an import of the same spelling, exactly as Python does.
        """
        origins = self._origins.get(path)
        if origins is None:
            origins = self._read_name_origins(path)
            self._origins[path] = origins
        return origins

    def _read_name_origins(self, path: str) -> Mapping[str, NameOrigin]:
        tree = self.parsed(path)
        origins: dict[str, NameOrigin] = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    owner = self.module_path(path, node.module, node.level)
                    if owner is None:
                        continue
                    submodule = self.module_path(
                        path, f"{node.module}.{alias.name}" if node.module else alias.name, node.level
                    )
                    origins[alias.asname or alias.name] = (
                        (submodule, alias.name)
                        if submodule is not None and node.module is None
                        else (owner, alias.name)
                    )
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
                origins[node.name] = (path, node.name)
        for name, _value in module_level_bindings(tree):
            origins[name] = (path, name)
        return origins

    def module_aliases(self, path: str) -> Mapping[str, str]:
        """Every name this file binds to a module of the tree, mapped to that module's file.

        ``from package import module`` binds a module exactly as it binds a
        function, and only the file inventory tells them apart. A reader that
        follows ``alias.NAME`` needs the module's own file, which the origin
        of the alias does not carry when the module sits in a named package.
        """
        aliases = self._module_aliases.get(path)
        if aliases is None:
            aliases = self._read_module_aliases(path)
            self._module_aliases[path] = aliases
        return aliases

    def _read_module_aliases(self, path: str) -> Mapping[str, str]:
        aliases: dict[str, str] = {}
        for node in ast.walk(self.parsed(path)):
            if not isinstance(node, ast.ImportFrom):
                continue
            for alias in node.names:
                submodule = self.module_path(
                    path, f"{node.module}.{alias.name}" if node.module else alias.name, node.level
                )
                if submodule is not None:
                    aliases[alias.asname or alias.name] = submodule
        return aliases


__all__ = ["NameOrigin", "SourceTree", "module_level_bindings"]
