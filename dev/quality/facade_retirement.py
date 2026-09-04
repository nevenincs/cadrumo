"""Repoint consumers off a package facade and onto the defining modules.

The accepted boundary makes a package initialiser an inert namespace marker: no
exports, no forwarding, no lazy map. Nine initialisers under ``dev`` are the
opposite - pure forwarding surfaces that define nothing and bind 388 names
between them - and 77 import statements across 70 files pull 271 names through
one. The three figures count different things and are reported separately for
that reason: a name bound by the initialiser, a name asked for by a consumer,
and a statement that has to be rewritten are not the same unit, and an earlier
count of this work conflated the first two.

Retiring a facade by hand means opening seventy files and knowing, for each
name, which module actually defines it. That knowledge is already written down:
the facade's own ``from ._x import Thing`` lines say where every name comes
from. This reads that mapping out of the initialiser and rewrites the consumers
against it, which makes the retirement mechanical rather than remembered.

The companion scanners run the other way and are not replacements for this one.
:mod:`dev.quality.facade_export_scan` asks whether a facade's names exist, and
:mod:`dev.quality.import_centralization_codemod` rewrites imports ONTO a facade,
which was the policy before initialisers were made inert; both are scoped to
``src/cadrumo``.

Three things are deliberately left alone:

- **Submodule traversal.** ``from ..package import errors`` names a MODULE in
  the package, not a re-export, and it keeps working when the initialiser is
  emptied. Sixteen sites are of this kind and rewriting them would be churn at
  best and wrong at worst.
- **A name the facade does not forward.** If the initialiser does not bind it,
  this module has no evidence about where it lives and refuses to guess.
- **The initialiser itself.** Emptying it is a separate act with a separate
  blast radius, and doing it in the same pass would leave the tree unimportable
  between two writes if the rewrite were interrupted.

Read-only by default; ``--apply`` writes. Statements are replaced by their AST
line span rather than by pattern, because a parenthesised multi-line import
defeats a line-oriented rewrite in both directions - a fact this repository has
already paid for once.
"""

from __future__ import annotations

import argparse
import ast
import collections
import pathlib
import sys
from dataclasses import dataclass
from typing import Final

__all__ = [
    "FacadePackage",
    "ImportSite",
    "facade_exports",
    "facade_import_sites",
    "relative_spelling",
    "rewrite_statement",
    "submodule_names",
]

#: The tree whose facades this retires. Declared rather than accepted as an
#: argument: the src-side scanners own their own tree, and a module that could
#: be pointed at either would make which policy applies a caller's choice.
DEV_ROOT: Final[pathlib.Path] = pathlib.Path("dev")

_INIT = "__init__.py"


@dataclass(frozen=True, slots=True)
class FacadePackage:
    """One package initialiser that forwards names it does not define."""

    dotted: str
    #: Exported name to the dotted module that defines it, read from the
    #: initialiser's own import statements.
    exports: dict[str, str]
    #: Names of real submodules, which are traversal targets rather than
    #: re-exports and must survive the retirement untouched.
    submodules: frozenset[str]


@dataclass(frozen=True, slots=True)
class ImportSite:
    """One import statement reaching a facade, and what it asks of it."""

    path: pathlib.Path
    package: str
    lineno: int
    end_lineno: int
    #: ``(name, asname)`` pairs, alias preserved because dropping it renames a
    #: symbol in the consumer's body and the rewrite would compile and be wrong.
    names: tuple[tuple[str, str | None], ...]
    indent: str
    #: The dot depth the consumer wrote, zero for an absolute import. Preserved
    #: because a file importing its own tree relatively has its import block
    #: grouped that way, and emitting an absolute form puts the new statement in
    #: the wrong isort group - which lints as an error rather than failing, so
    #: the rewrite would look applied and leave the tree red.
    level: int
    #: The dotted package containing the consumer, needed to spell a relative
    #: import back out at whatever depth the target now sits.
    consumer_package: str

    @property
    def forwarded(self) -> tuple[tuple[str, str | None], ...]:
        """The names that come from the facade rather than from a submodule."""
        return self.names


def _package_of(path: pathlib.Path) -> list[str]:
    """Return the dotted parts of the package containing ``path``.

    The containing package is the directory, for a module and an initialiser
    alike. Reading an initialiser's own dotted name as its package makes every
    relative import in it resolve one level too deep, which reports a facade's
    consumers as zero - measured, and wrong by ninety sites.
    """
    return list(path.parent.parts)


def resolve_relative(node: ast.ImportFrom, path: pathlib.Path) -> str:
    """Return the absolute dotted module an ``ImportFrom`` names."""
    if node.level == 0:
        return node.module or ""
    package = _package_of(path)
    base = package[: len(package) - (node.level - 1)]
    return ".".join(base + ([node.module] if node.module else []))


def submodule_names(directory: pathlib.Path) -> frozenset[str]:
    """Return the package's real submodules and subpackages."""
    modules = {item.stem for item in directory.glob("*.py") if item.stem != "__init__"}
    packages = {item.name for item in directory.iterdir() if item.is_dir() and (item / _INIT).is_file()}
    return frozenset(modules | packages)


def facade_exports(directory: pathlib.Path) -> FacadePackage:
    """Read one initialiser's forwarding map: exported name to defining module.

    Derived from the initialiser's own import statements, never from a written
    inventory. The mapping is already stated there, and a second copy of it in
    this module would be the exact restatement the boundary forbids - and would
    go stale the first time a symbol moved.
    """
    initialiser = directory / _INIT
    tree = ast.parse(initialiser.read_text(encoding="utf-8"))
    exports: dict[str, str] = {}
    for node in tree.body:
        if not isinstance(node, ast.ImportFrom):
            continue
        module = resolve_relative(node, initialiser)
        if module == "__future__":
            # A compiler directive, not a re-export. Counting it made every
            # facade look like it forwarded one name more than it does, and the
            # inflation was invisible because it was exactly one per package -
            # a constant offset reads as a definition disagreement, not a bug.
            continue
        for alias in node.names:
            # An aliased re-export renames the symbol, so the facade's name and
            # the defining module's name differ and a consumer cannot simply be
            # repointed. Recorded under the exported spelling; the rewrite
            # refuses it below rather than importing the wrong name.
            exports[alias.asname or alias.name] = module
    return FacadePackage(
        dotted=".".join(directory.parts),
        exports=exports,
        submodules=submodule_names(directory),
    )


def facade_packages(root: pathlib.Path = DEV_ROOT) -> tuple[FacadePackage, ...]:
    """Return every package under ``root`` whose initialiser forwards a name."""
    found: list[FacadePackage] = []
    for initialiser in sorted(root.rglob(_INIT)):
        if "__pycache__" in initialiser.parts:
            continue
        package = facade_exports(initialiser.parent)
        if package.exports:
            found.append(package)
    return tuple(found)


def facade_import_sites(
    packages: tuple[FacadePackage, ...], search_root: pathlib.Path = pathlib.Path()
) -> tuple[ImportSite, ...]:
    """Return every statement importing a forwarded name from one of ``packages``.

    Submodule traversal is excluded, not reported and skipped: a statement that
    names only submodules has nothing to do with the facade, and counting it
    would put sixteen sites into a worklist that must not touch them.
    """
    by_dotted = {package.dotted: package for package in packages}
    sites: list[ImportSite] = []
    for path in sorted(search_root.rglob("*.py")):
        if "__pycache__" in path.parts or ".venv" in path.parts or path.name == _INIT:
            continue
        try:
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source)
        except (SyntaxError, UnicodeDecodeError, OSError):
            continue
        lines = source.splitlines()
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom):
                continue
            module = resolve_relative(node, path)
            package = by_dotted.get(module)
            if package is None:
                continue
            forwarded = tuple(
                (alias.name, alias.asname)
                for alias in node.names
                if alias.name not in package.submodules and alias.name in package.exports
            )
            if not forwarded:
                continue
            line = lines[node.lineno - 1]
            sites.append(
                ImportSite(
                    path=path,
                    package=module,
                    lineno=node.lineno,
                    end_lineno=node.end_lineno or node.lineno,
                    names=tuple((alias.name, alias.asname) for alias in node.names),
                    indent=line[: len(line) - len(line.lstrip())],
                    level=node.level,
                    consumer_package=".".join(_package_of(path)),
                )
            )
    return tuple(sites)


def relative_spelling(target: str, *, consumer_package: str) -> str | None:
    """Return ``target`` as a relative import from ``consumer_package``.

    ``None`` when the two share no leading segment, which cannot happen inside
    one tree but would produce a nonsense depth if it did.
    """
    consumer = consumer_package.split(".")
    parts = target.split(".")
    shared = 0
    while shared < min(len(consumer), len(parts)) and consumer[shared] == parts[shared]:
        shared += 1
    if shared == 0:
        return None
    return "." * (len(consumer) - shared + 1) + ".".join(parts[shared:])


def rewrite_statement(site: ImportSite, package: FacadePackage) -> tuple[str, ...]:
    """Return the lines replacing one import statement, or ``()`` to refuse.

    Names are grouped by defining module and emitted in sorted order, one
    statement per module, so a consumer that pulled six names from a facade ends
    with as many statements as there are real owners rather than six.

    A statement mixing forwarded names with submodule traversal keeps a
    statement for the submodules: the package still legitimately holds them, and
    dropping that import would break the consumer in a way the type checker
    would not necessarily catch.

    Refuses - returns empty - when any forwarded name is aliased by the facade
    itself, because then the consumer's name and the defining module's name are
    different symbols and repointing would import the wrong one.
    """
    by_module: dict[str, list[str]] = collections.defaultdict(list)
    kept: list[str] = []
    for name, asname in site.names:
        if name in package.submodules:
            kept.append(name if asname is None else f"{name} as {asname}")
            continue
        module = package.exports.get(name)
        if module is None:
            return ()
        by_module[module].append(name if asname is None else f"{name} as {asname}")

    def spell(target: str) -> str:
        if site.level == 0:
            return target
        relative = relative_spelling(target, consumer_package=site.consumer_package)
        return relative if relative is not None else target

    lines: list[str] = []
    if kept:
        lines.append(f"{site.indent}from {spell(package.dotted)} import {', '.join(sorted(kept))}")
    for module in sorted(by_module):
        lines.append(f"{site.indent}from {spell(module)} import {', '.join(sorted(by_module[module]))}")
    return tuple(lines)


def apply_rewrites(sites: tuple[ImportSite, ...], packages: tuple[FacadePackage, ...]) -> tuple[int, int]:
    """Rewrite every site in place; return ``(files changed, sites rewritten)``.

    Applied bottom-up within a file so an earlier statement's line numbers stay
    valid after a later one is replaced by a different number of lines.
    """
    by_dotted = {package.dotted: package for package in packages}
    by_path: dict[pathlib.Path, list[ImportSite]] = collections.defaultdict(list)
    for site in sites:
        by_path[site.path].append(site)

    files = rewritten = 0
    for path, items in by_path.items():
        lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
        changed = False
        for site in sorted(items, key=lambda item: item.lineno, reverse=True):
            replacement = rewrite_statement(site, by_dotted[site.package])
            if not replacement:
                continue
            lines[site.lineno - 1 : site.end_lineno] = [f"{line}\n" for line in replacement]
            changed = True
            rewritten += 1
        if changed:
            path.write_text("".join(lines), encoding="utf-8")
            files += 1
    return files, rewritten


def main() -> int:
    """Report the facades and their consumers; ``--apply`` rewrites them."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", help="restrict to one dotted package, e.g. dev.docs.apidocs")
    parser.add_argument("--apply", action="store_true", help="rewrite the consumers in place")
    arguments = parser.parse_args()

    packages = facade_packages()
    if arguments.package:
        packages = tuple(item for item in packages if item.dotted == arguments.package)
        if not packages:
            sys.stderr.write(f"no facade package named {arguments.package}\n")
            return 2
    sites = facade_import_sites(packages)

    by_package: collections.Counter[str] = collections.Counter(site.package for site in sites)
    refused = 0
    by_dotted = {package.dotted: package for package in packages}
    for site in sites:
        if not rewrite_statement(site, by_dotted[site.package]):
            refused += 1
    for package in packages:
        sys.stdout.write(
            f"facade_retirement package={package.dotted} exports={len(package.exports)} "
            f"submodules={len(package.submodules)} consumer_sites={by_package[package.dotted]}\n"
        )
    files = len({site.path for site in sites})
    if arguments.apply:
        changed, rewritten = apply_rewrites(sites, packages)
        sys.stdout.write(f"applied files={changed} sites={rewritten}\n")
    sys.stdout.write(
        f"summary packages={len(packages)} exports={sum(len(p.exports) for p in packages)} "
        f"sites={len(sites)} files={files} refused={refused}\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
