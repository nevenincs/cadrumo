"""API documentation stub management: discovery, scaffolding, and conformance checks."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from cadrumo.core import scan_directory
from cadrumo.core.external_constants import UTF_8_ENCODING


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


# Module segments that exclude an entire subtree.
_EXCLUDED_PACKAGES: frozenset[str] = frozenset({"tests", "_data"})

# Subtree path-prefixes (relative to the package root) excluded from autodoc
# stubs.  The CLI is documented through the generated command reference rather
# than autodoc; importing the cli command/payload modules under autodoc also
# fails on pydantic model construction, so the cli implementation is not stubbed.
_EXCLUDED_SUBTREES: frozenset[tuple[str, ...]] = frozenset({("entrypoints", "cli")})

# Individual filenames excluded from stub coverage even inside included packages.
_EXCLUDED_FILENAMES: frozenset[str] = frozenset({"conftest.py"})

_UTF_8: str = UTF_8_ENCODING

# PEP 695 aliases do not produce Python-domain objects when ``automodule``
# enumerates members.  These aliases are nevertheless intentional public API
# and are referenced throughout the API prose and generated annotations.  Keep
# the small ownership table here, beside the stub generator, so each alias gets
# exactly one canonical ``py:data`` target at its public facade.
_PUBLIC_DATA_ALIASES: dict[str, tuple[str, ...]] = {
    "cadrumo.core": ("CasillaId",),
    "cadrumo.core.identity": ("ContentDigest", "SubjectTaxId", "TaxIdIdentityToken"),
}
_PUBLIC_FUNCTION_ALIASES: dict[str, tuple[str, ...]] = {
    "cadrumo.domain.calculations.registry": ("collect_registry_tree_fingerprints",),
}

# Pydantic materialises generic bases on each concrete consumer with the
# defining class's original ``__module__``/``__qualname__``.  Autodoc would
# consequently index the defining object (and its fields) again from every
# importing module.  Exclude only those imported names at the consumer stub;
# the defining-module stub remains their sole object owner.
_NON_OWNER_GENERIC_IMPORTS: dict[str, tuple[str, ...]] = {
    "cadrumo.application.aggregation._impatriado_income_ledger": ("LedgerAggregationResultBase",),
    "cadrumo.application.aggregation._irnr_income_ledger": ("LedgerAggregationResultBase",),
    "cadrumo.application.aggregation._renta_gasto_ledger": ("LedgerAggregationResultBase",),
    "cadrumo.application.aggregation._renta_income_ledger": ("LedgerAggregationResultBase",),
    "cadrumo.application.aggregation._renta_ledger": ("LedgerAggregationResultBase",),
    "cadrumo.application.operator_actions._models": ("PreconditionOutcomeInvariant",),
    "cadrumo.core.json_contract": ("PreconditionOutcomeInvariant",),
}

def _public_data_aliases(module_name: str) -> list[str]:
    """Render canonical Python-domain targets for public type aliases."""
    lines: list[str] = []
    for alias in _PUBLIC_DATA_ALIASES.get(module_name, ()):
        lines.extend(
            (
                f".. py:data:: {alias}",
                f"   :module: {module_name}",
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


def _stub_is_current(path: Path, content: str) -> bool:
    """Return True when *path* holds exactly the bytes *content* serialises to.

    The comparison is on BYTES. ``Path.read_text`` opens in universal-newline
    mode, so it folds ``\\r\\n`` to ``\\n`` before the caller sees anything: a
    stub whose terminators were translated after checkout decodes to the same
    string as the canonical LF content and compares EQUAL. The repository's
    ``.gitattributes`` normalises to LF on the index side as well, so ``git
    diff`` is silent on the same file. A text comparison therefore leaves the
    translated stub invisible to every reader there is.

    That was not hypothetical. Measured on 2026-07-28 against the committed
    tree: 60 of 1240 stubs under ``docs/api/`` carried CRLF on disk while
    ``python -m dev.docs.apidocs scaffold --check`` reported the tree
    conformant. The writer that translated them was this module's own, so the
    check could not see the drift it was itself introducing.

    Args:
        path: An existing stub file.
        content: The canonical generated RST for that stub.

    Returns:
        True when the file's bytes are exactly the UTF-8 LF encoding of *content*.
    """
    return path.read_bytes() == content.encode(_UTF_8)


class ApiStubManager:
    """Manage Sphinx ``automodule`` RST stubs under ``docs/api/``.

    Provides three entry points used by the developer CLI:

    - :meth:`scaffold` — write/sync ``docs/api/*.rst`` to match the current
      source tree, removing stale stubs and creating missing ones.
    - :meth:`check` — compute the drift between source modules and stubs
      without writing anything.
    - :meth:`audit` — return a human-readable health report.
    """

    def __init__(self, src_cadrumo: Path, docs_api: Path) -> None:
        """Initialise the manager with the source root and the docs API directory.

        Args:
            src_cadrumo: Absolute path to ``src/cadrumo/``.
            docs_api: Absolute path to ``docs/api/``.
        """
        self.src_cadrumo = src_cadrumo
        self.docs_api = docs_api

    # ── Discovery ────────────────────────────────────────────────────────────

    def _is_excluded(self, path: Path) -> bool:
        """Return True when *path* is outside the documentable module set.

        Args:
            path: An absolute ``Path`` to a Python file under ``src_cadrumo``.

        Returns:
            True when the file should be skipped.
        """
        relative = path.relative_to(self.src_cadrumo)
        parts = relative.parts

        filename = path.name
        if filename.startswith("test_") or filename.startswith("_test_"):
            return True
        if filename in _EXCLUDED_FILENAMES:
            return True

        for prefix in _EXCLUDED_SUBTREES:
            if parts[: len(prefix)] == prefix:
                return True

        return any(part in _EXCLUDED_PACKAGES for part in parts)

    def discover_modules(self) -> list[tuple[str, bool]]:
        """Walk ``src_cadrumo`` and collect ``(dotted_module_name, is_package)`` pairs.

        Returns:
            Sorted list of ``(dotted_name, is_package)`` tuples.
            ``is_package`` is ``True`` for ``__init__.py`` files.
        """
        results: list[tuple[str, bool]] = []

        for py_file in scan_directory(self.src_cadrumo, pattern="*.py", recursive=True):
            if self._is_excluded(py_file):
                continue

            relative = py_file.relative_to(self.src_cadrumo.parent)
            parts = list(relative.parts)

            if parts[-1] == "__init__.py":
                dotted = ".".join(parts[:-1])
                results.append((dotted, True))
            else:
                parts[-1] = parts[-1][: -len(".py")]
                dotted = ".".join(parts)
                results.append((dotted, False))

        return results

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
        lines.extend(_public_data_aliases(pkg_name))
        lines.extend(_public_function_aliases(pkg_name))

        if sub_packages:
            lines.append(self._toctree_block(sub_packages, "Subpackages"))

        if sub_modules:
            lines.append(self._toctree_block(sub_modules, "Submodules"))

        lines.append("")
        return "\n".join(lines)

    @staticmethod
    def _module_stub(mod_name: str) -> str:
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
        lines.extend(_public_data_aliases(mod_name))
        lines.extend(_public_function_aliases(mod_name))
        return "\n".join(lines)

    def _expected_stub_contents(self, all_modules: list[tuple[str, bool]] | None = None) -> dict[str, str]:
        """Return canonical stub content keyed by stub filename.

        Args:
            all_modules: Optional discovery result to reuse.

        Returns:
            Mapping of ``cadrumo.some.module.rst`` filenames to their generated RST.
        """
        modules = self.discover_modules() if all_modules is None else all_modules
        expected: dict[str, str] = {}
        for name, is_pkg in modules:
            if is_pkg:
                sub_pkgs, sub_mods = self._package_children(name, modules)
                content = self._package_stub(name, sub_pkgs, sub_mods)
            else:
                content = self._module_stub(name)
            expected[f"{name}.rst"] = content
        return expected

    # ── Public API ───────────────────────────────────────────────────────────

    def scaffold(self) -> ScaffoldResult:
        """Write and sync ``docs/api/*.rst`` to match the current source tree.

        Creates missing stubs, regenerates all existing stubs with canonical
        content, and removes stale stubs that no longer correspond to a source
        module.

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
        expected = set(expected_contents)
        written = 0
        unchanged = 0

        for filename, content in expected_contents.items():
            path = self.docs_api / filename
            if path.is_file() and _stub_is_current(path, content):
                unchanged += 1
                continue
            # newline="\n" pins the terminator. The default translates every
            # "\n" to the platform separator on write, which is what put CRLF
            # into 60 committed stubs; sibling generators under dev/docs/
            # already write this way.
            path.write_text(content, encoding=_UTF_8, newline="\n")
            written += 1

        removed_names: list[str] = []
        for existing in scan_directory(self.docs_api, pattern="*.rst"):
            if existing.name not in expected:
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

    def audit(self) -> str:
        """Return a human-readable health report for the stub tree.

        Returns:
            A multi-line report string describing stub coverage.
        """
        all_modules = self.discover_modules()
        drift = self.check()

        total_modules = len(all_modules)
        total_stubs = len(scan_directory(self.docs_api, pattern="*.rst")) - (
            1 if (self.docs_api / "modules.rst").exists() else 0
        )

        lines: list[str] = [
            "API stub health report",
            f"  Source modules : {total_modules}",
            f"  Stub files     : {total_stubs}",
            f"  Missing stubs  : {len(drift.missing_stubs)}",
            f"  Orphan stubs   : {len(drift.orphan_stubs)}",
            f"  Stale stubs    : {len(drift.stale_stubs)}",
        ]
        if drift.missing_stubs:
            lines.append("")
            lines.append("Missing stubs (no .rst for this module):")
            for name in drift.missing_stubs:
                lines.append(f"  {name}")
        if drift.orphan_stubs:
            lines.append("")
            lines.append("Orphan stubs (no matching source module):")
            for name in drift.orphan_stubs:
                lines.append(f"  {name}")
        if drift.stale_stubs:
            lines.append("")
            lines.append("Stale stubs (content differs from generator output):")
            for name in drift.stale_stubs:
                lines.append(f"  {name}")
        if drift.is_conformant:
            lines.append("")
            lines.append("Stub tree is conformant.")
        return "\n".join(lines)
