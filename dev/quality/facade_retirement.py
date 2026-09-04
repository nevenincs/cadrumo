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
- **A private defining module reached from another package.** Most of these
  facades forward out of leading-underscore modules, and the same boundary that
  makes an initialiser inert makes a private module private to its own package.
  Repointing an outside consumer at it would trade a facade for a cross-package
  private import, which is the worse of the two violations. Those sites are
  refused with a reason, and the fix is to make the defining module public
  first - work the facade was concealing.
- **A symbol defined in ``__main__``.** Refused everywhere, including inside
  the owning package, and reported under its own reason rather than as a
  privacy problem - because the fix is not to make ``__main__`` public. A module
  run as ``python -m package`` is an entry point, and a facade forwarding a
  library symbol out of one means the library lives inside the entry point.
  ``dev.docs.sequences`` is the repository's only instance and its ``__main__``
  is 890 lines.
- **The initialiser itself.** Emptying it is a separate act with a separate
  blast radius, and doing it in the same pass would leave the tree unimportable
  between two writes if the rewrite were interrupted.

Documentation cross-references are rewritten by the same map. A docstring
saying ``:class:`~dev.ingest_harness.HarnessReport``` names a path that only the
facade makes true, so emptying the initialiser turns fifteen live references
into dangling ones. They are the same restatement as the import and are fixed
from the same evidence.

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
    "NON_INERT_KINDS",
    "REFUSALS",
    "FacadePackage",
    "ImportSite",
    "apply_reference_rewrites",
    "facade_exports",
    "facade_import_sites",
    "imported_modules",
    "non_inert_contents",
    "reference_rewrites",
    "refusal_reason",
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


def imported_modules(node: ast.ImportFrom | ast.Import, path: pathlib.Path) -> tuple[str, ...]:
    """Return every module an import statement can be said to reference.

    :func:`resolve_relative` answers what an ``ImportFrom`` resolves TO, which is
    the package for ``from ..analysis import thing``. That is correct and it is
    not the whole answer: the name being imported may itself be a module, and a
    caller asking "which modules does this statement reference" needs both.

    This has been got wrong three times in one campaign, each time in a fresh
    walk written by someone who knew the rule: a facade consumer scan reported
    zero consumers where there were ninety, a module promoter left two files
    pointing at a module it had renamed, and a coverage probe reported six
    tested modules as untested while their test files sat beside them. The
    knowledge belongs in one function rather than in each walk's author.

    The result is CANDIDATES. ``from x import y`` yields both ``x`` and ``x.y``
    because ``y`` may be a module or may be a symbol, and nothing in the syntax
    says which. Callers intersect it with the module set they know about, which
    is the only place that question can be answered.
    """
    if isinstance(node, ast.Import):
        return tuple(alias.name for alias in node.names)
    resolved = resolve_relative(node, path)
    return (resolved, *(f"{resolved}.{alias.name}" for alias in node.names))


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


#: Everything an inert namespace marker may not carry, named once so the gate
#: and its report cannot disagree about what inertness means.
NON_INERT_KINDS: Final[tuple[str, ...]] = (
    "definition",
    "import",
    "assignment",
    "side_effect_call",
)


def non_inert_contents(initialiser: pathlib.Path) -> dict[str, tuple[str, ...]]:
    """Return what an initialiser carries that an inert marker may not.

    Forwarding is the loudest violation and the one the retirement removed, but
    the boundary is wider than that: an initialiser may not define symbols, run
    code at import, or bind module-level names either. A package that defines
    its own class in ``__init__.py`` forwards nothing and is still not a
    namespace marker.

    ``from __future__ import ...`` is excluded. It is a compiler directive with
    no runtime effect, and counting it made every initialiser look non-inert -
    the same exclusion the export reader needs, for the same reason.
    """
    tree = ast.parse(initialiser.read_text(encoding="utf-8"))
    found: dict[str, list[str]] = {kind: [] for kind in NON_INERT_KINDS}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            found["definition"].append(node.name)
        elif isinstance(node, ast.ImportFrom) and node.module != "__future__":
            found["import"].append(node.module or ".")
        elif isinstance(node, ast.Import):
            found["import"].append(node.names[0].name)
        elif isinstance(node, ast.Assign):
            found["assignment"].extend(target.id for target in node.targets if isinstance(target, ast.Name))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            found["assignment"].append(node.target.id)
        elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            found["side_effect_call"].append(ast.unparse(node.value.func))
    return {kind: tuple(names) for kind, names in found.items() if names}


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


#: Every reason a site can be refused, declared once so a caller can group by
#: it without reading the strings out of this module's source.
REFUSALS: Final[tuple[str, ...]] = (
    "unforwarded_name",
    "cross_package_private_target",
    "entry_point_target",
)


def refusal_reason(site: ImportSite, package: FacadePackage) -> str | None:
    """Return why this site cannot be rewritten, or ``None`` if it can.

    Two reasons, and the second is the one that makes this a report rather than
    a codemod that finishes the job. A facade forwarding out of ``_residual_identity``
    hides the fact that its public symbol has no public home; repointing an
    outside consumer straight at the private module satisfies the initialiser
    rule and breaks the module-privacy rule in the same edit. The site is left
    alone and named instead.

    Intra-package consumers are not refused: a private module is private to its
    own package, and its own tests may import it directly.

    ``__main__`` is refused separately and from everywhere, including inside the
    owning package. It matches the underscore test, but reporting it as a
    privacy problem names the wrong fix: nobody should make ``__main__`` public.
    A module run as ``python -m package`` is an entry point, and importing a
    library symbol out of it means the library lives inside the entry point.
    One package in the repository does this, and it is the single largest
    blocker in the facade work.
    """
    for name, _ in site.names:
        if name in package.submodules:
            continue
        module = package.exports.get(name)
        if module is None:
            return "unforwarded_name"
        leaf = module.rsplit(".", 1)[-1]
        if leaf == "__main__":
            return "entry_point_target"
        inside = site.consumer_package == package.dotted or site.consumer_package.startswith(f"{package.dotted}.")
        if leaf.startswith("_") and not inside:
            return "cross_package_private_target"
    return None


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
    if refusal_reason(site, package) is not None:
        return ()
    by_module: dict[str, list[str]] = collections.defaultdict(list)
    kept: list[str] = []
    for name, asname in site.names:
        if name in package.submodules:
            kept.append(name if asname is None else f"{name} as {asname}")
            continue
        module = package.exports[name]
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


def reference_rewrites(text: str, package: FacadePackage) -> tuple[str, int]:
    """Repoint dotted documentation references at the defining module.

    ``dev.ingest_harness.score_emission`` becomes
    ``dev.ingest_harness._scoring.score_emission``: the same correction the
    import rewrite makes, applied to the prose that states the same path.

    A submodule reference is left alone by construction - it is not in the
    export map - so ``dev.ingest_harness._scoring`` is not rewritten into
    itself. Longest names are replaced first so a name that is a prefix of
    another cannot claim its text.
    """
    replaced = 0
    for name in sorted(package.exports, key=len, reverse=True):
        if name in package.submodules:
            continue
        stale = f"{package.dotted}.{name}"
        fresh = f"{package.exports[name]}.{name}"
        if stale == fresh:
            continue
        # A reference is followed by a delimiter, never by another identifier
        # character; without that guard `Scored` would claim the text of
        # `ScoredField` even with the longest-first ordering above.
        index = 0
        while (index := text.find(stale, index)) != -1:
            after = index + len(stale)
            if after < len(text) and (text[after].isalnum() or text[after] == "_"):
                index = after
                continue
            text = text[:index] + fresh + text[after:]
            replaced += 1
            index += len(fresh)
    return text, replaced


def apply_reference_rewrites(package: FacadePackage, root: pathlib.Path = DEV_ROOT) -> tuple[int, int]:
    """Rewrite stale references under ``root``; return ``(files, references)``.

    This module's own file is skipped. Its docstring quotes a stale path as the
    example of what goes wrong, and rewriting that quotation into the corrected
    form deletes the explanation while leaving the sentence grammatical - the
    only self-reference here, and the only one that must not be repaired.
    """
    own = pathlib.Path(__file__).resolve()
    files = references = 0
    for path in sorted(root.rglob("*.py")):
        if "__pycache__" in path.parts or path.resolve() == own:
            continue
        original = path.read_text(encoding="utf-8")
        rewritten, count = reference_rewrites(original, package)
        if count:
            path.write_text(rewritten, encoding="utf-8")
            files += 1
            references += count
    return files, references


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
    parser.add_argument(
        "--references",
        action="store_true",
        help="also repoint dotted documentation references at the defining module",
    )
    arguments = parser.parse_args()

    packages = facade_packages()
    if arguments.package:
        packages = tuple(item for item in packages if item.dotted == arguments.package)
        if not packages:
            sys.stderr.write(f"no facade package named {arguments.package}\n")
            return 2
    sites = facade_import_sites(packages)

    by_package: collections.Counter[str] = collections.Counter(site.package for site in sites)
    by_dotted = {package.dotted: package for package in packages}
    refusals: collections.Counter[str] = collections.Counter()
    for site in sites:
        reason = refusal_reason(site, by_dotted[site.package])
        if reason is not None:
            refusals[reason] += 1
            sys.stdout.write(
                f"facade_retirement refused path={site.path} package={site.package} "
                f"line={site.lineno} reason={reason}" + chr(10)
            )
    refused = sum(refusals.values())
    for package in packages:
        sys.stdout.write(
            f"facade_retirement package={package.dotted} exports={len(package.exports)} "
            f"submodules={len(package.submodules)} consumer_sites={by_package[package.dotted]}\n"
        )
    files = len({site.path for site in sites})
    if arguments.apply:
        changed, rewritten = apply_rewrites(sites, packages)
        sys.stdout.write(f"applied files={changed} sites={rewritten}\n")
    if arguments.references and arguments.apply:
        for package in packages:
            touched, count = apply_reference_rewrites(package)
            sys.stdout.write(f"references package={package.dotted} files={touched} rewritten={count}\n")
    sys.stdout.write(
        f"summary packages={len(packages)} exports={sum(len(p.exports) for p in packages)} "
        f"sites={len(sites)} files={files} refused={refused} "
        + " ".join(f"{reason}={refusals[reason]}" for reason in REFUSALS)
        + chr(10)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
