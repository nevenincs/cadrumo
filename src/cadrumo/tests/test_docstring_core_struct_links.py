"""Navigability gate: modules that use a core struct must cross-link it.

The API documentation is only useful for navigation if its docstrings form a
graph that steers a reader toward the canonical "spine" types. A module that
depends on a core struct but never names it in a Sphinx cross-reference is a
dead end: the reader has no thread to follow back to the authoritative
definition.

This gate enforces one objective rule. For a fixed set of canonical core
structs, every module that *imports* one must *cross-link* it in at least one
docstring (the module docstring or any public symbol's docstring), using a
Sphinx role such as ``:class:`ModeloRevision```. The defining module of each
struct is exempt from linking to itself.

The gate is hard-cut: it requires zero violations and, on failure, enumerates
every ``module -> struct`` pair that still needs a link. There is no stored
baseline or per-item progress list; the worklist is recomputed from the AST on
every run, so it can only shrink to green as docstrings gain their links.
"""

from __future__ import annotations

import ast
import re
from collections import defaultdict
from pathlib import Path

import pytest

from ._inventory import SRC_CADRUMO, module_name, production_ast_items

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]

# The canonical spine. Each entry maps a core struct to the dotted module that
# defines it. ``test_core_struct_anchors_are_unambiguous`` pins every entry to
# a real, single class definition so the set cannot silently rot as the code
# moves. Extend this mapping to bring more of the spine under the gate.
CORE_STRUCTS: dict[str, str] = {
    "ValidatedRegistryAuthority": "cadrumo.domain.calculations.registry.authority",
    "RegistrySnapshot": "cadrumo.domain.calculations.registry.schema",
    "ModeloDefinition": "cadrumo.domain.calculations.registry.schema",
    "ModeloRevision": "cadrumo.domain.calculations.registry.schema",
    "CasillaObservation": "cadrumo.domain.calculations.registry.bindings",
    "CalculationRevision": "cadrumo.domain.modelos.calculation_revision",
    "OutputSchema": "cadrumo.core.json_contract",
    "SchemaEnvelope": "cadrumo.core.json_contract",
    "SecureObjectRepository": "cadrumo.adapters.persistence.storage.sql.secure_objects",
    # Security + classification
    "SensitivityClass": "cadrumo.core.classification",
    "Envelope": "cadrumo.adapters.persistence.storage.envelope._envelope",
    "MasterKeyProvider": "cadrumo.adapters.persistence.storage.master_key._master_key",
    # Portal registry
    "Portal": "cadrumo.domain.portals.codes",
    "PortalMetadata": "cadrumo.domain.portals.metadata",
    "PortalCategory": "cadrumo.domain.portals.categories",
    # Financial-input aggregates and their repositories
    "TransactionCatalogue": "cadrumo.domain.transactions.models",
    "TransactionCatalogueRepository": "cadrumo.adapters.persistence.profile.transactions",
    "InvoiceCatalogue": "cadrumo.domain.invoices._models",
    # Profile, deadlines, and filing records
    "TaxpayerProfile": "cadrumo.domain.deadlines._models",
    "Schedule": "cadrumo.domain.deadlines._models",
    "UserProfileRecord": "cadrumo.domain.user_profile.values",
    "ModeloDraft": "cadrumo.domain.filing._schema",
    "ModeloRecord": "cadrumo.domain.modelos.filing_record",
}

# A Sphinx cross-reference role capturing the referenced symbol's final segment,
# e.g. ``:class:`cadrumo.domain.filing.ModeloRevision``` -> ``ModeloRevision``.
_ROLE = re.compile(r":(?:mod|class|func|meth|obj|data|attr|exc|paramref):`[^`]*?([A-Za-z_][A-Za-z0-9_]*)`")


def _imported_anchors(tree: ast.AST) -> set[str]:
    """Core-struct names this module imports by name."""
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name in CORE_STRUCTS:
                    found.add(alias.name)
    return found


def _linked_anchors(tree: ast.AST) -> set[str]:
    """Core-struct names cross-referenced in any docstring of this module."""
    docstrings: list[str] = []
    if isinstance(tree, ast.Module):
        module_doc = ast.get_docstring(tree)
        if module_doc:
            docstrings.append(module_doc)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            doc = ast.get_docstring(node)
            if doc:
                docstrings.append(doc)
    linked: set[str] = set()
    for doc in docstrings:
        for name in _ROLE.findall(doc):
            if name in CORE_STRUCTS:
                linked.add(name)
    return linked


def test_core_struct_anchors_are_unambiguous() -> None:
    """Every declared anchor resolves to exactly one class at its canonical module."""
    assert CORE_STRUCTS, "the core-struct anchor set is empty; this gate would pass by scanning nothing"
    problems: list[str] = []
    for name, dotted in CORE_STRUCTS.items():
        base = SRC_CADRUMO.parent / Path(*dotted.split("."))
        # A canonical home is either a module file or a package __init__.
        path = base.with_suffix(".py")
        if not path.is_file():
            path = base / "__init__.py"
        if not path.is_file():
            problems.append(f"{name}: declared module {dotted} has no file")
            continue
        defs = re.findall(rf"^class {re.escape(name)}\b", path.read_text(encoding="utf-8"), re.MULTILINE)
        if len(defs) != 1:
            problems.append(f"{name}: expected exactly one `class {name}` in {dotted}, found {len(defs)}")
    assert not problems, "core-struct anchor set is stale:\n  " + "\n  ".join(problems)


def test_modules_that_use_a_core_struct_link_it() -> None:
    """A module importing a core struct must cross-link it in a docstring."""
    violations: dict[str, list[str]] = defaultdict(list)
    for path, tree in production_ast_items():
        module = module_name(path)
        linked = _linked_anchors(tree)
        for anchor in _imported_anchors(tree):
            if CORE_STRUCTS[anchor] == module:
                continue  # the struct's own home need not link to itself
            if anchor not in linked:
                violations[module].append(anchor)

    if violations:
        total = sum(len(v) for v in violations.values())
        lines = [
            f"{total} module->core-struct uses lack a docstring cross-reference.",
            "Add a Sphinx role (e.g. :class:`ModeloRevision`) to the module docstring",
            "or a public symbol's docstring where the struct is used:",
            "",
        ]
        for module in sorted(violations):
            for anchor in sorted(violations[module]):
                lines.append(f"  {module}  ->  :class:`{anchor}`")
        pytest.fail("\n".join(lines))


def _annotation_names(node: ast.AST) -> set[str]:
    """Return every bare identifier appearing in a (possibly nested) annotation."""
    names: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Name):
            names.add(child.id)
        elif isinstance(child, ast.Attribute):
            names.add(child.attr)
    return names


def test_public_functions_link_anchor_parameters() -> None:
    """A documented public function taking a core struct as a parameter links it.

    The spine is highest-signal at a function's own boundary: if a parameter is
    typed as a core struct, the function's docstring should cross-link it so a
    reader following the signature lands on the canonical definition.
    """
    violations: dict[str, list[str]] = defaultdict(list)
    for path, tree in production_ast_items():
        module = module_name(path)
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            if node.name.startswith("_"):
                continue
            doc = ast.get_docstring(node)
            if not doc:
                continue
            linked = {m for m in _ROLE.findall(doc) if m in CORE_STRUCTS}
            params = node.args.args + node.args.kwonlyargs + node.args.posonlyargs
            referenced: set[str] = set()
            for arg in params:
                if arg.annotation is not None:
                    referenced |= {n for n in _annotation_names(arg.annotation) if n in CORE_STRUCTS}
            for anchor in sorted(referenced - linked):
                violations[f"{module}::{node.name}"].append(anchor)

    if violations:
        total = sum(len(v) for v in violations.values())
        lines = [
            f"{total} public functions take a core struct their docstring does not link.",
            "Cross-link the parameter type (e.g. in the Args: section) with :class:`Name`:",
            "",
        ]
        for symbol in sorted(violations):
            for anchor in sorted(violations[symbol]):
                lines.append(f"  {symbol}  ->  :class:`{anchor}`")
        pytest.fail("\n".join(lines))


# ---------------------------------------------------------------------------
# Dotted cross-reference resolution
# ---------------------------------------------------------------------------
#
# The gates above ask whether a link is PRESENT. This one asks whether a link
# RESOLVES, which is a different failure and went undetected until a package
# split moved sixty-three symbols to a sibling and left the prose behind: one
# hundred and eighteen roles across forty-nine files pointed at a package
# exporting six. A role is a string, and a stale string is indistinguishable
# from a live one until something resolves it.
#
# Bare anchors stay out of scope deliberately. Project convention is a bare
# ``:class:`Name```, resolved by the documentation build against the whole
# public surface, so it names no single module to check against. Only a role
# naming a MODULE PATH asserts where a symbol lives, and only that assertion can
# be wrong here.
#
# Resolution is static: reading source beats importing, because importing makes
# this gate red whenever a peer's in-flight edit breaks an unrelated import
# chain, and a gate that reds on other people's work gets muted.

_DOTTED_ROLE = re.compile(r":(?:class|func|meth|attr|data|exc|obj|mod):`~?([A-Za-z_][A-Za-z0-9_.]*)`")

# Shrink-only debt ceiling, NOT a target. It is lowered as the debt burns down
# and must never be raised. The remaining entries are prose reaching past a
# facade into ``_module`` internals -- the class the architecture boundaries rule
# already governs.
#
# It landed at 204 and the first 60 of that drop was THIS DETECTOR, not work.
# ``core/__init__.py`` declares ``__all__: list[str] = [...]``, an ``ast.AnnAssign``
# rather than an ``ast.Assign``; reading only the latter parsed that facade as
# exporting zero symbols and turned all 61 roles into it -- 38 of them the lazily
# resolved ``BindingSourceKind``, a PEP 562 facade the boundaries rule explicitly
# sanctions -- into violations. A detector that flags a sanctioned pattern 38 times
# is reporting on itself. The same node type produced 112 false violations from
# this same file for an earlier sweep, so it is a recurrence and not a one-off:
# any AST walk over module-level constants must handle ``AnnAssign`` and
# ``AugAssign`` or it silently sees an empty set.
#
# Neither time did the finding list reveal it -- 61 plausible role names read
# exactly like debt. Both times the tell was the DENOMINATOR: an ``__all__`` of
# size zero, and one symbol holding 38 of 61. Print the denominator, or find the
# implausible concentration.
#
# THE TWO DROPS SO FAR ARE NOT THE SAME KIND OF THING, and a ceiling that falls
# without saying which is which records a lie about progress:
#
#   204 -> 144   this detector correcting itself. No docstring changed.
#   144 -> 110   thirty-four real repoints. ``CasillaId`` is exported by ``core``
#                and genuinely absent from the registry facade, so the roles
#                naming ``domain.calculations.registry.CasillaId`` were pointed
#                at a package that never owned it.
#   110 ->  18   ninety-two repoints, resolved by DEFINING module rather than by
#                exporting module. "Shortest public module that exports it" is the
#                wrong query: it picks re-exporters over owners, and would have
#                aimed seventeen roles at ``application.state_projection``, which
#                exports several repositories and owns none of them.
#
# 18 -> 2 was 16 real repoints, not a detector change. The earlier note here said
# all 18 named a symbol defined in more than one module; that was wrong and is
# corrected by measurement. Only four did, and the true causes were mundane: three
# citations dropped the ``tests`` package segment, and ten named a symbol that
# exists nowhere in the tree -- a truncated test-function name, an enum member cited
# without its class, and prose surviving the rename of the thing it described
# (``IVA_RATE_TABLE`` and ``CATEGORY_PROFILES_2025`` are both loader functions now).
#
# The recurring shape is worth naming, because five of the sixteen were instances of
# it: A CITATION AND ITS INVERSE ARE WRITTEN AS A PAIR, AND ONLY ONE HALF IS KEPT
# CORRECT. Each of those five sat one or two lines from a sibling role that had the
# module path right.
#
# What remains is one symbol, ``PeriodCode``, whose owning package publishes its
# sibling ``PeriodSelector`` but not it. The fix is promotion to the registry facade
# rather than a repoint at the private module that defines it -- deferred only
# because it is a facade edit, not because the answer is unclear.
#
# THIS WAS A COUNTING CEILING (``len(unresolved) <= 2``) AND THAT COULD NOT SAY WHAT
# IT MEANT. A ``<=`` passes identically at two, one or zero, so the gate could not
# distinguish "the known allowance" from "something else broke while the allowance
# got fixed", and once the population dropped the ceiling would have gone silently
# slack -- a shrink-only ratchet that stops ratcheting is indistinguishable from one
# that is holding. It also gated a tally, which is the thing this project's
# quality-gate rule forbids: a count encodes a moment and trains everyone to edit
# the constant.
#
# So the allowance is keyed by SYMBOL with a stated reason, and it is enforced from
# both ends: an unresolved reference to anything else fails, AND an allowance whose
# symbol has stopped being unresolved fails. The second half is what closes the
# ratchet -- promoting ``PeriodCode`` reds this gate until its entry is deleted,
# instead of leaving a permanently-satisfied ceiling behind.
_UNRESOLVED_DOTTED_REFERENCE_ALLOWANCE: dict[str, str] = {}

# Anchored to the exact report format built in _scan_dotted_references. A report the
# pattern cannot read is counted as a VIOLATION rather than skipped: if the format
# changes, this gate must fail loudly instead of quietly matching nothing and
# passing.
_REPORT_SYMBOL = re.compile(r"does not define '([^']+)'$")

# A derived scan selecting nothing satisfies the ceiling assertion perfectly.
# These floors sit far below the real figures so ordinary churn never moves them.
_MINIMUM_MODULES_SCANNED = 400
_MINIMUM_DOTTED_ROLES_EXAMINED = 50


def _module_file_for(parts: list[str]) -> Path | None:
    """Return the file backing a dotted module path, or ``None`` if there is none."""
    package_init = SRC_CADRUMO.joinpath(*parts, "__init__.py")
    if package_init.is_file():
        return package_init
    module_file = SRC_CADRUMO.joinpath(*parts[:-1], f"{parts[-1]}.py") if parts else None
    return module_file if module_file is not None and module_file.is_file() else None


def _defined_names(path: Path) -> set[str] | None:
    """Return every name a module defines or imports, or ``None`` when unparseable.

    Unions ``__all__`` with top-level definitions. The union is deliberate: a
    role reaching into a private module names something that module defines but
    does not publish, which is a different question from whether the reference
    resolves at all. This gate answers only the second.
    """
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        return None
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            names.update(target.id for target in node.targets if isinstance(target, ast.Name))
            if any(isinstance(t, ast.Name) and t.id == "__all__" for t in node.targets):
                try:
                    names.update(ast.literal_eval(node.value))
                except (ValueError, TypeError):
                    return None
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
            # ``__all__: list[str] = [...]`` is an AnnAssign, not an Assign, and
            # reading only the latter silently treats an annotated facade as
            # exporting nothing. That is not hypothetical: it produced sixty-one
            # false positives against ``core`` -- a lazy PEP 562 facade the
            # architecture rule explicitly sanctions -- and would have baked this
            # detector's blind spot into the ceiling below.
            if node.target.id == "__all__" and node.value is not None:
                try:
                    names.update(ast.literal_eval(node.value))
                except (ValueError, TypeError):
                    return None
        elif isinstance(node, ast.ImportFrom):
            names.update(alias.asname or alias.name for alias in node.names)
    return names


def _owning_module(target: str) -> tuple[Path, str] | None:
    """Return ``(module_file, symbol)`` for an in-repo dotted target, else ``None``.

    ``None`` covers stdlib and third-party targets, whose correctness belongs to
    the documentation build's resolver, and targets naming a module outright --
    a package does not re-export its own submodules through ``__all__``, so
    checking those would flag every module reference in the tree.
    """
    parts = target.split(".")
    if parts and parts[0] == "cadrumo":
        parts = parts[1:]
    if len(parts) < 2 or _module_file_for(parts) is not None:
        return None
    for split in range(len(parts) - 1, 0, -1):
        module_file = _module_file_for(parts[:split])
        if module_file is not None:
            return module_file, parts[split]
    return None


def _unresolved_reference(target: str) -> tuple[Path, str] | None:
    """Return the owning module and symbol when a dotted target does not resolve."""
    owned = _owning_module(target)
    if owned is None:
        return None
    module_file, symbol = owned
    defined = _defined_names(module_file)
    return None if defined is None or symbol in defined else (module_file, symbol)


def _scan_dotted_references(path: Path, tree: ast.AST) -> tuple[list[str], int]:
    """Return one module's unresolved-reference reports and how many targets it examined."""
    reports: list[str] = []
    examined = 0
    origin = path.relative_to(SRC_CADRUMO).as_posix()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        text = ast.get_docstring(node, clean=False)
        if not text:
            continue
        for target in _DOTTED_ROLE.findall(text):
            if _owning_module(target) is None:
                continue
            examined += 1
            missing = _unresolved_reference(target)
            if missing is None:
                continue
            owner = missing[0].relative_to(SRC_CADRUMO).as_posix()
            reports.append(f"{origin}: `{target}` -> {owner} does not define {missing[1]!r}")
    return reports, examined


def _unresolved_dotted_references() -> tuple[list[str], int, int]:
    """Return every unresolved dotted role, modules scanned, and targets examined."""
    unresolved: list[str] = []
    scanned = 0
    examined = 0
    for path, tree in production_ast_items():
        scanned += 1
        reports, seen = _scan_dotted_references(path, tree)
        unresolved.extend(reports)
        examined += seen
    return unresolved, scanned, examined


def test_dotted_reference_scan_is_non_empty() -> None:
    """Anti-vacuity: a scan selecting nothing satisfies the ceiling assertion perfectly."""
    _, scanned, examined = _unresolved_dotted_references()

    assert scanned >= _MINIMUM_MODULES_SCANNED, f"only {scanned} modules scanned; the walk collapsed"
    assert examined >= _MINIMUM_DOTTED_ROLES_EXAMINED, (
        f"only {examined} in-repo dotted roles examined; the pattern or the resolver collapsed"
    )


def test_dotted_reference_detector_still_discriminates() -> None:
    """Anti-vacuity: the resolver must reject a fabricated symbol and accept a real one."""
    owned = _owning_module("core.identity.ThisSymbolIsNotDefinedAnywhere")
    assert owned is not None, "the resolver no longer reaches core.identity"
    owning_file, owning_symbol = owned
    assert owning_file.parent.name == "identity", f"resolved to the wrong module: {owning_file}"
    assert owning_symbol == "ThisSymbolIsNotDefinedAnywhere"

    unresolved = _unresolved_reference("core.identity.ThisSymbolIsNotDefinedAnywhere")
    assert unresolved is not None, "a fabricated symbol resolved, so the check can never fail"
    unresolved_file, unresolved_symbol = unresolved
    assert unresolved_file.parent.name == "identity", f"reported the wrong owning module: {unresolved_file}"
    assert unresolved_symbol == "ThisSymbolIsNotDefinedAnywhere"

    assert _unresolved_reference("core.identity.BucketId") is None, (
        "a known-good target was rejected, so the check always fails"
    )


def test_dotted_cross_references_resolve_to_a_defining_module() -> None:
    """A role naming a module path must name a symbol that module defines."""
    unresolved, _, _ = _unresolved_dotted_references()

    unexpected = [
        report
        for report in unresolved
        if (match := _REPORT_SYMBOL.search(report)) is None
        or match.group(1) not in _UNRESOLVED_DOTTED_REFERENCE_ALLOWANCE
    ]

    assert not unexpected, (
        f"{len(unexpected)} dotted cross-reference(s) name a symbol their cited module does not "
        "define, and are not in the stated allowance. Repoint the reference at the module that "
        "owns the symbol; do not add an allowance entry to silence it.\n" + "\n".join(sorted(unexpected)[:40])
    )


def test_every_unresolved_reference_allowance_is_still_live() -> None:
    """The other half of the ratchet: a fixed allowance must be deleted, not left standing.

    Without this, the allowance degrades into exactly what the counting ceiling it
    replaced was -- a permanently-satisfied constant that no longer describes the
    tree. Promoting ``PeriodCode`` to the registry facade reds this test, and the
    fix is to delete its entry.
    """
    unresolved, _, _ = _unresolved_dotted_references()
    live = {match.group(1) for report in unresolved if (match := _REPORT_SYMBOL.search(report)) is not None}

    stale = sorted(set(_UNRESOLVED_DOTTED_REFERENCE_ALLOWANCE) - live)

    assert not stale, (
        f"allowance entries no longer describe any unresolved reference: {stale}. "
        "The citation was fixed; delete the entry rather than leaving it standing."
    )
