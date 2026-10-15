"""API documentation stub management: discovery, scaffolding, and conformance checks."""

from __future__ import annotations

import ast
import importlib.util
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from cadrumo.core.directory_scan import scan_directory
from cadrumo.core.external_constants import UTF_8_ENCODING
from dev.first_party_source import FIRST_PARTY_ROOTS


class ApiDocsError(RuntimeError):
    """Raised on API documentation stub management errors."""


@dataclass(frozen=True)
class ScaffoldResult:
    """Summary of a scaffold operation.

    Attributes:
        written: Number of stub files written or updated because their content changed.
        removed: Number of stale stub files removed.
        removed_names: Names of the removed stub files.
        unchanged: Number of already-current stub files left untouched.
    """

    written: int
    removed: int
    removed_names: list[str] = field(default_factory=list)
    unchanged: int = 0


@dataclass(frozen=True)
class DriftResult:
    """Result of a conformance check.

    Attributes:
        missing_stubs: Module names that have no corresponding stub file.
        orphan_stubs: Stub filenames that have no corresponding source module.
        stale_stubs: Module names whose existing stub content is not canonical.
    """

    missing_stubs: list[str] = field(default_factory=list)
    orphan_stubs: list[str] = field(default_factory=list)
    stale_stubs: list[str] = field(default_factory=list)

    @property
    def is_conformant(self) -> bool:
        """Return True when there is no drift between source modules and stubs."""
        return not self.missing_stubs and not self.orphan_stubs and not self.stale_stubs


#: Every shipped first-party Python package, as declared by the canonical
#: source-root inventory. Development tooling and packaging hooks remain
#: outside the public product API reference.
API_SOURCE_ROOTS: tuple[str, ...] = tuple(root for root in FIRST_PARTY_ROOTS if root.startswith("src/"))

#: Primary tax application package; its command subtree has a separately
#: generated reference and the authored API overview starts its reading path
#: here. Keep this semantic owner explicit rather than relying on root order.
API_SOURCE_PACKAGE: str = "cadrumo"

#: Package-relative subtree documented through the generated command
#: reference instead of autodoc.
CLI_REFERENCE_SUBTREE: tuple[str, ...] = ("entrypoints", "cli")

#: Module path segments that exclude every module beneath them.
#:
#: The four ``EXCLUDED_*`` declarations are the whole eligibility rule, read as
#: data by the test that re-derives the admitted module set independently of
#: :meth:`ApiStubManager.excludes_source`. Widening one is therefore a visible
#: one-line change here, and a defect in the filter code that applies them is
#: caught by that derivation rather than by a committed copy of the output.
EXCLUDED_PACKAGE_SEGMENTS: frozenset[str] = frozenset({"tests", "_data"})

#: Primary-application package-relative subtrees excluded from autodoc stubs.
#: The application CLI is documented through the generated command reference
#: rather than autodoc; importing its command/payload modules under autodoc also
#: fails on pydantic model construction, so that implementation is not stubbed.
EXCLUDED_SUBTREES: frozenset[tuple[str, ...]] = frozenset({CLI_REFERENCE_SUBTREE})

#: Filenames excluded from stub coverage even inside included packages.
EXCLUDED_FILENAMES: frozenset[str] = frozenset({"conftest.py"})

#: Filename prefixes that mark a test module wherever it sits.
EXCLUDED_FILENAME_PREFIXES: tuple[str, ...] = ("test_", "_test_")

_UTF_8: str = UTF_8_ENCODING

_PUBLIC_FUNCTION_ALIASES: dict[str, tuple[str, ...]] = {}

_TYPE_ALIAS_FACTORIES = frozenset(
    {
        "Annotated",
        "AsyncIterator",
        "Awaitable",
        "Callable",
        "Collection",
        "Iterable",
        "Iterator",
        "Literal",
        "Mapping",
        "MutableMapping",
        "NewType",
        "Protocol",
        "Sequence",
        "TypeAliasType",
    }
)
# Pydantic materialises generic bases on each concrete consumer with the
# defining class's original ``__module__``/``__qualname__``.  Autodoc would
# consequently index the defining object (and its fields) again from every
# importing module.  Exclude only those imported names at the consumer stub;
# the defining-module stub remains their sole object owner.
_NON_OWNER_GENERIC_IMPORTS: dict[str, tuple[str, ...]] = {
    "cadrumo.application.config_reset_repository": ("JournalRepositoryBase",),
    "cadrumo.application.aggregation.impatriado_income_ledger": ("LedgerAggregationResultBase",),
    "cadrumo.application.aggregation.irnr_income_ledger": ("LedgerAggregationResultBase",),
    "cadrumo.application.aggregation.renta_gasto_ledger": ("LedgerAggregationResultBase",),
    "cadrumo.application.aggregation.renta_income_ledger": ("LedgerAggregationResultBase",),
    "cadrumo.application.aggregation.renta_ledger": ("LedgerAggregationResultBase",),
    "cadrumo.application.operator_actions.models": ("PreconditionOutcomeInvariant",),
    "cadrumo.application.user_profile.bundle_export_operation": ("JournalRepositoryBase",),
    "cadrumo.core.json_contract": ("PreconditionOutcomeInvariant",),
}


def _type_alias_expression(value: ast.expr) -> bool:
    """Return whether *value* is a source expression that defines a type alias."""
    if isinstance(value, ast.Subscript):
        factory = value.value
        while isinstance(factory, ast.Attribute):
            factory = factory.value
        factory_name = value.value.attr if isinstance(value.value, ast.Attribute) else getattr(factory, "id", None)
        return factory_name in _TYPE_ALIAS_FACTORIES
    if isinstance(value, ast.BinOp):
        return isinstance(value.op, ast.BitOr)
    if isinstance(value, ast.Call):
        factory = value.func
        while isinstance(factory, ast.Attribute):
            factory = factory.value
        factory_name = value.func.attr if isinstance(value.func, ast.Attribute) else getattr(factory, "id", None)
        return factory_name in {"NewType", "TypeAliasType"}
    return False


def _source_root(path: Path) -> Path | None:
    """Find the ``src/<package>`` root containing *path*, including fixtures."""
    return next((parent for parent in path.parents if parent.parent.name == "src"), None)


def _module_name(source_root: Path, path: Path) -> str:
    """Return the importable module name for a Python source path."""
    relative = path.relative_to(source_root).with_suffix("")
    parts = relative.parts[:-1] if relative.name == "__init__" else relative.parts
    return ".".join((source_root.name, *parts))


def _module_source_path(source_root: Path, module_name: str) -> Path | None:
    """Resolve a module inside the source cohort containing *source_root*."""
    module_path = source_root.parent.joinpath(*module_name.split("."))
    source_path = module_path.with_suffix(".py")
    package_path = module_path / "__init__.py"
    if source_path.is_file():
        return source_path
    if package_path.is_file():
        return package_path
    return None


def _module_symbol_is_type(path: Path, symbol: str, seen: frozenset[tuple[Path, str]] = frozenset()) -> bool:
    """Follow an imported symbol to confirm it is a class or source type alias."""
    key = (path.resolve(), symbol)
    if key in seen:
        return False
    seen = seen | {key}
    try:
        source = path.read_text(encoding=_UTF_8)
        tree = ast.parse(source, filename=str(path))
    except (OSError, SyntaxError, UnicodeDecodeError):
        return False

    source_root = _source_root(path)
    module_name = _module_name(source_root, path) if source_root is not None else ""
    for statement in tree.body:
        if isinstance(statement, ast.ClassDef) and statement.name == symbol:
            return True
        if isinstance(statement, ast.TypeAlias) and statement.name.id == symbol:
            return True
        if (
            isinstance(statement, ast.AnnAssign)
            and isinstance(statement.target, ast.Name)
            and statement.target.id == symbol
            and isinstance(statement.annotation, ast.Name)
            and statement.annotation.id == "TypeAlias"
        ):
            return True
        if isinstance(statement, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == symbol for target in statement.targets
        ):
            if _type_alias_expression(statement.value):
                return True
            if isinstance(statement.value, ast.Name) and source_root is not None and module_name:
                return _module_symbol_is_type(path, statement.value.id, seen) or _imported_symbol_is_type(
                    path, tree, statement.value.id, seen
                )
    return _imported_symbol_is_type(path, tree, symbol, seen)


def _imported_symbol_is_type(
    path: Path,
    tree: ast.Module,
    symbol: str,
    seen: frozenset[tuple[Path, str]] = frozenset(),
) -> bool:
    """Return whether a module imports *symbol* from a class or alias owner."""
    source_root = _source_root(path)
    if source_root is None:
        return False
    module_name = _module_name(source_root, path)
    package = module_name if path.name == "__init__.py" else module_name.rpartition(".")[0]
    for statement in tree.body:
        if not isinstance(statement, ast.ImportFrom) or not statement.module:
            continue
        for imported in statement.names:
            local_name = imported.asname or imported.name
            if local_name != symbol:
                continue
            try:
                module_name = importlib.util.resolve_name(f"{'.' * statement.level}{statement.module}", package)
            except ImportError:
                continue
            imported_path = _module_source_path(source_root, module_name)
            if imported_path is not None and _module_symbol_is_type(imported_path, imported.name, seen):
                return True
    return False


def _type_alias_declarations(path: Path) -> tuple[tuple[str, str], ...]:
    """Return public top-level type alias declarations from *path*."""
    source = path.read_text(encoding=_UTF_8)
    tree = ast.parse(source, filename=str(path))
    aliases: dict[str, str] = {}
    for statement in tree.body:
        if isinstance(statement, ast.TypeAlias):
            if not statement.name.id.startswith("_"):
                declaration = ast.get_source_segment(source, statement) or ast.unparse(statement)
                aliases[statement.name.id] = declaration
            continue

        if (
            isinstance(statement, ast.AnnAssign)
            and isinstance(statement.target, ast.Name)
            and isinstance(statement.annotation, ast.Name)
            and statement.annotation.id == "TypeAlias"
            and not statement.target.id.startswith("_")
        ):
            declaration = ast.get_source_segment(source, statement) or ast.unparse(statement)
            aliases[statement.target.id] = declaration
            continue

        if not isinstance(statement, ast.Assign):
            continue

        targets = tuple(target.id for target in statement.targets if isinstance(target, ast.Name))
        public_targets = tuple(name for name in targets if not name.startswith("_"))
        if not public_targets:
            continue

        value = statement.value
        is_type_expression = _type_alias_expression(value)
        is_referenced_type_alias = isinstance(value, ast.Name) and _module_symbol_is_type(path, value.id)
        if is_type_expression or is_referenced_type_alias:
            declaration = ast.get_source_segment(source, statement) or ast.unparse(statement)
            aliases.update((name, declaration) for name in public_targets)

    return tuple(sorted(aliases.items()))


def _public_type_aliases(module_name: str, source_path: Path) -> list[str]:
    """Render type-alias targets and source declarations from their owner module."""
    lines: list[str] = []
    for alias, declaration in _type_alias_declarations(source_path):
        lines.extend(
            (
                f".. py:type:: {alias}",
                f"   :module: {module_name}",
                "",
                "   Declared in source::",
                "",
                *(f"      {line}" for line in declaration.splitlines()),
                "",
            )
        )
    return lines


def _public_function_aliases(module_name: str) -> list[str]:
    """Render canonical Python-domain targets for public function aliases."""
    lines: list[str] = []
    for alias in _PUBLIC_FUNCTION_ALIASES.get(module_name, ()):
        lines.extend((f".. py:function:: {alias}", f"   :module: {module_name}", ""))
    return lines


def stub_filename(module_name: str) -> str:
    """Return the ``docs/api`` stub filename that documents *module_name*."""
    return f"{module_name}.rst"


def _stub_is_current(path: Path, content: str) -> bool:
    """Return True when *path* holds exactly the bytes *content* serialises to.

    The comparison is on BYTES. ``Path.read_text`` opens in universal-newline
    mode, so it folds ``\\r\\n`` to ``\\n`` before the caller sees anything: a
    stub whose terminators were translated after checkout decodes to the same
    string as the canonical LF content and compares EQUAL. The repository's
    ``.gitattributes`` normalises to LF on the index side as well, so ``git
    diff`` is silent on the same file. A text comparison therefore leaves the
    translated stub invisible to every reader there is.

    That was not hypothetical. Measured on 2026-07-28, when the stubs were
    still committed: 60 of 1240 stubs under ``docs/api/`` carried CRLF on disk
    while the drift check reported the tree conformant. The writer that
    translated them was this module's own, so the check could not see the drift
    it was itself introducing. The same comparison decides which stubs a build
    rewrites, and an unwritten stub keeps its mtime, so Sphinx does not re-read
    a page whose bytes did not change.

    Args:
        path: An existing stub file.
        content: The canonical generated RST for that stub.

    Returns:
        True when the file's bytes are exactly the UTF-8 LF encoding of *content*.
    """
    return path.read_bytes() == content.encode(_UTF_8)


class ApiStubManager:
    """Manage Sphinx ``automodule`` RST stubs under ``docs/api/``.

    The stubs are build output, not source: a full-scope documentation build
    calls :meth:`scaffold` at ``builder-inited`` to write them into the source
    tree it is about to read (see ``docs/conf.py``), and they are never
    committed.

    - :meth:`scaffold` — write/sync ``docs/api/*.rst`` to match the current
      source tree, removing stale stubs and creating missing ones.
    - :meth:`check` — compute the drift between source modules and stubs
      without writing anything.
    """

    def __init__(
        self,
        src_cadrumo: Path,
        docs_api: Path,
        *,
        source_roots: Sequence[Path] | None = None,
    ) -> None:
        """Initialise with one fixture/source root or an explicit package cohort.

        Args:
            src_cadrumo: The primary application package root. Kept as the
                one-root seam for hermetic tests and existing callers.
            docs_api: Absolute path to ``docs/api/``.
            source_roots: Optional package roots to document together. When
                omitted, only ``src_cadrumo`` is scanned; repository builds use
                :meth:`for_repository` to require the canonical five-root set.
        """
        self.src_cadrumo = src_cadrumo
        self.source_roots = tuple(source_roots) if source_roots is not None else (src_cadrumo,)
        if not self.source_roots:
            raise ApiDocsError("At least one API source root must be configured")
        if len({root.parent.resolve() for root in self.source_roots}) != 1:
            raise ApiDocsError("API source roots must share one src/ parent directory")
        self.docs_api = docs_api

    @classmethod
    def for_repository(cls, repo_root: Path, docs_api: Path) -> ApiStubManager:
        """Create a manager for every configured first-party package under ``src/``.

        Missing canonical roots are a configuration error rather than an
        invitation to publish a partial API tree.
        """
        source_roots = tuple(repo_root.joinpath(*Path(root).parts) for root in API_SOURCE_ROOTS)
        missing = [root for root in source_roots if not root.is_dir()]
        if missing:
            missing_paths = ", ".join(str(root) for root in missing)
            raise ApiDocsError(f"Configured first-party API roots are missing: {missing_paths}")
        primary_source_root = repo_root / "src" / API_SOURCE_PACKAGE
        return cls(src_cadrumo=primary_source_root, docs_api=docs_api, source_roots=source_roots)

    # ── Discovery ────────────────────────────────────────────────────────────

    def excludes_source(self, path: Path) -> bool:
        """Return True when *path* is outside the documentable module set.

        Public because it is the ONE eligibility rule: the incremental docs
        planner asks this generator whether a changed path participates in
        the stub tree rather than restating the rule, which is how the two
        drifted apart before. The check is pure path arithmetic, so a
        deleted path can still be classified.

        Args:
            path: An absolute ``Path`` to a Python file under a configured source root.

        Returns:
            True when the file should be skipped.
        """
        source_root = next((root for root in self.source_roots if path.is_relative_to(root)), None)
        if source_root is None:
            raise ValueError(f"API source path is outside configured roots: {path}")
        relative = path.relative_to(source_root)
        parts = relative.parts

        filename = path.name
        if filename.startswith(EXCLUDED_FILENAME_PREFIXES):
            return True
        if filename in EXCLUDED_FILENAMES:
            return True

        if source_root.name == API_SOURCE_PACKAGE:
            for prefix in EXCLUDED_SUBTREES:
                if parts[: len(prefix)] == prefix:
                    return True

        return any(part in EXCLUDED_PACKAGE_SEGMENTS for part in parts)

    def discover_modules(self) -> list[tuple[str, bool]]:
        """Walk configured source roots and collect module/package pairs.

        Returns:
            Sorted list of ``(dotted_name, is_package)`` tuples.
            ``is_package`` is ``True`` for ``__init__.py`` files.
        """
        results: list[tuple[str, bool]] = []

        for source_root in self.source_roots:
            for py_file in scan_directory(source_root, pattern="*.py", recursive=True):
                if self.excludes_source(py_file):
                    continue

                relative = py_file.relative_to(source_root.parent)
                parts = list(relative.parts)

                if parts[-1] == "__init__.py":
                    dotted = ".".join(parts[:-1])
                    results.append((dotted, True))
                else:
                    parts[-1] = parts[-1][: -len(".py")]
                    dotted = ".".join(parts)
                    results.append((dotted, False))

        return sorted(results)

    # ── Content builders ─────────────────────────────────────────────────────

    @staticmethod
    def _package_children(
        pkg_name: str,
        all_modules: list[tuple[str, bool]],
    ) -> tuple[list[str], list[str]]:
        """Return direct sub-packages and direct sub-modules of *pkg_name*.

        Args:
            pkg_name: Dotted name of the package whose children to find.
            all_modules: Full discovery output from :meth:`discover_modules`.

        Returns:
            A ``(sub_packages, sub_modules)`` pair, each sorted.
        """
        prefix = pkg_name + "."
        prefix_depth = pkg_name.count(".") + 1

        sub_packages: list[str] = []
        sub_modules: list[str] = []

        for name, is_pkg in all_modules:
            if not name.startswith(prefix):
                continue
            depth = name.count(".")
            if depth != prefix_depth:
                continue
            if is_pkg:
                sub_packages.append(name)
            else:
                sub_modules.append(name)

        return sorted(sub_packages), sorted(sub_modules)

    @staticmethod
    def _heading(text: str) -> str:
        """Build an RST section heading with ``=`` underline.

        Args:
            text: The heading text.

        Returns:
            A two-line string: the text followed by an equal-length ``=`` underline.
        """
        return f"{text}\n{'=' * len(text)}"

    @staticmethod
    def _toctree_block(entries: list[str], label: str) -> str:
        """Build an RST ``toctree`` block.

        Args:
            entries: List of toctree entry strings (relative RST references).
            label: Section label placed above the toctree.

        Returns:
            An RST string containing the labelled section and toctree directive.
        """
        lines: list[str] = [
            "",
            label,
            "-" * len(label),
            "",
            ".. toctree::",
            "   :maxdepth: 4",
            "",
        ]
        for entry in entries:
            lines.append(f"   {entry}")
        return "\n".join(lines)

    def _package_stub(
        self,
        pkg_name: str,
        sub_packages: list[str],
        sub_modules: list[str],
    ) -> str:
        """Generate RST content for a package stub.

        ``:ignore-module-all:`` selects members by defining module rather than
        the ``__all__`` re-export list, so each symbol is documented exactly
        once, at the module that defines it. This is what prevents duplicate
        object descriptions when a symbol is re-exported through several public
        package levels. The short ``:class:``/``:func:`` references that package
        ``__init__`` docstrings make to their re-exported public names are
        bridged to that single canonical target by the documentation set's
        ``missing-reference`` resolver (see ``docs/conf.py``). Sub-packages and
        sub-modules are listed in separate ``toctree`` blocks.

        Args:
            pkg_name: Dotted name of the package.
            sub_packages: Direct child package names.
            sub_modules: Direct child module names.

        Returns:
            Complete RST source for the stub file.
        """
        title = f"{pkg_name} package"
        lines: list[str] = [
            self._heading(title),
            "",
            f".. automodule:: {pkg_name}",
            "   :members:",
            "   :show-inheritance:",
            "   :ignore-module-all:",
            "",
        ]
        lines.extend(_public_type_aliases(pkg_name, self._source_path(pkg_name)))
        lines.extend(_public_function_aliases(pkg_name))

        if sub_packages:
            lines.append(self._toctree_block(sub_packages, "Subpackages"))

        if sub_modules:
            lines.append(self._toctree_block(sub_modules, "Submodules"))

        lines.append("")
        return "\n".join(lines)

    def _module_stub(self, mod_name: str) -> str:
        """Generate RST content for a leaf-module stub.

        Every symbol is documented exactly once, at the module that defines it
        (``__module__``). ``:ignore-module-all:`` makes member selection follow
        the defining module rather than any ``__all__`` re-export list, so a
        symbol re-exported into one or more parent packages is documented here
        (its real home) and never duplicated on a package page. Short
        cross-references to the re-exported public name are bridged to this
        canonical target by the ``missing-reference`` resolver in
        ``docs/conf.py``.

        Args:
            mod_name: Dotted name of the module.

        Returns:
            Complete RST source for the stub file.
        """
        title = f"{mod_name} module"
        lines: list[str] = [
            f"{title}\n{'=' * len(title)}",
            "",
            f".. automodule:: {mod_name}",
            "   :members:",
            "   :show-inheritance:",
            "   :ignore-module-all:",
        ]
        excluded_generics = _NON_OWNER_GENERIC_IMPORTS.get(mod_name, ())
        if excluded_generics:
            lines.append(f"   :exclude-members: {','.join(excluded_generics)}")
        lines.append("")
        lines.extend(_public_type_aliases(mod_name, self._source_path(mod_name)))
        lines.extend(_public_function_aliases(mod_name))
        return "\n".join(lines)

    def _source_path(self, module_name: str) -> Path:
        """Return the source file for a discovered module name."""
        for source_root in self.source_roots:
            package_name = source_root.name
            if module_name != package_name and not module_name.startswith(package_name + "."):
                continue
            parts = module_name.split(".")[1:]
            module_path = source_root.joinpath(*parts)
            return module_path / "__init__.py" if module_path.is_dir() else module_path.with_suffix(".py")
        raise ValueError(f"API module is outside configured source roots: {module_name}")

    def _expected_stub_contents(self, all_modules: list[tuple[str, bool]] | None = None) -> dict[str, str]:
        """Return canonical stub content keyed by stub filename.

        Args:
            all_modules: Optional discovery result to reuse.

        Returns:
            Mapping of ``some_package.some.module.rst`` filenames to generated RST.
        """
        modules = self.discover_modules() if all_modules is None else all_modules
        expected: dict[str, str] = {}
        for name, is_pkg in modules:
            if is_pkg:
                sub_pkgs, sub_mods = self._package_children(name, modules)
                content = self._package_stub(name, sub_pkgs, sub_mods)
            else:
                content = self._module_stub(name)
            expected[stub_filename(name)] = content
        return expected

    # ── Public API ───────────────────────────────────────────────────────────

    def scaffold(self) -> ScaffoldResult:
        """Write and sync ``docs/api/*.rst`` to match the current source tree.

        Creates missing stubs, rewrites stubs whose bytes are not canonical,
        leaves current stubs untouched, and removes stubs that no longer
        correspond to a source module.

        Removal is unbounded because the tree is disposable build output that
        the next build regenerates in full. What a narrowed eligibility rule
        would silently drop is guarded instead by the test that re-derives the
        admitted module set from the source tree and the declared exclusions.

        Returns:
            A :class:`ScaffoldResult` summarising what changed.

        Raises:
            ApiDocsError: When the docs API directory cannot be created.
        """
        try:
            self.docs_api.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise ApiDocsError(f"Cannot create docs/api directory: {exc}") from exc

        expected_contents = self._expected_stub_contents()
        written = 0
        unchanged = 0

        for filename, content in expected_contents.items():
            path = self.docs_api / filename
            if path.is_file() and _stub_is_current(path, content):
                unchanged += 1
                continue
            # newline="\n" pins the terminator. The default translates every
            # "\n" to the platform separator on write, which put CRLF into 60
            # stubs; sibling generators under dev/docs/ write the same way.
            path.write_text(content, encoding=_UTF_8, newline="\n")
            written += 1

        removed_names: list[str] = []
        for existing in scan_directory(self.docs_api, pattern="*.rst"):
            if existing.name not in expected_contents:
                existing.unlink()
                removed_names.append(existing.name)

        return ScaffoldResult(
            written=written,
            removed=len(removed_names),
            removed_names=removed_names,
            unchanged=unchanged,
        )

    def check(self) -> DriftResult:
        """Compute drift between source modules and stub files without writing.

        Returns:
            A :class:`DriftResult` listing missing and orphan stubs.
            :attr:`DriftResult.is_conformant` is ``True`` when there is no drift.
        """
        expected_contents = self._expected_stub_contents()
        expected_stems: set[str] = {Path(filename).stem for filename in expected_contents}

        actual_stubs: set[str] = set()
        for rst_file in scan_directory(self.docs_api, pattern="*.rst"):
            if rst_file.name == "modules.rst":
                continue
            stem = rst_file.stem
            actual_stubs.add(stem)

        missing = sorted(expected_stems - actual_stubs)
        orphans = sorted(actual_stubs - expected_stems)
        stale = sorted(
            Path(filename).stem
            for filename, expected in expected_contents.items()
            if (self.docs_api / filename).is_file() and not _stub_is_current(self.docs_api / filename, expected)
        )
        return DriftResult(missing_stubs=missing, orphan_stubs=orphans, stale_stubs=stale)
