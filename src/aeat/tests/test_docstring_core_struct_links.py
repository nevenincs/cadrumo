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
from collections.abc import Mapping
from pathlib import Path

import pytest

from ._inventory import SRC_AEAT, ast_for_path, module_name, production_python_files

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]

# The canonical spine. Each entry maps a core struct to the dotted module that
# defines it. ``test_core_struct_anchors_are_unambiguous`` pins every entry to
# a real, single class definition so the set cannot silently rot as the code
# moves. Extend this mapping to bring more of the spine under the gate.
CORE_STRUCTS: dict[str, str] = {
    "ValidatedRegistryAuthority": "aeat.domain.calculations.registry._authority",
    "RegistrySnapshot": "aeat.domain.calculations.registry._schema",
    "ModeloDefinition": "aeat.domain.calculations.registry._schema",
    "ModeloRevision": "aeat.domain.calculations.registry._schema",
    "CasillaObservation": "aeat.domain.calculations.registry._bindings",
    "CalculationRevision": "aeat.domain.modelos._calculation_revision",
    "OutputSchema": "aeat.core.json_contract",
    "SchemaEnvelope": "aeat.core.json_contract",
    "SecureObjectRepository": "aeat.adapters.persistence.storage.sql.secure_objects",
    # Security + classification
    "SensitivityClass": "aeat.core.classification",
    "Envelope": "aeat.adapters.persistence.storage.envelope._envelope",
    "MasterKeyProvider": "aeat.adapters.persistence.storage.master_key._master_key",
    # Portal registry
    "Portal": "aeat.domain.portals._codes",
    "PortalMetadata": "aeat.domain.portals._metadata",
    "PortalCategory": "aeat.domain.portals._categories",
    # Financial-input aggregates and their repositories
    "TransactionCatalogue": "aeat.domain.transactions._models",
    "TransactionCatalogueRepository": "aeat.domain.transactions._repository",
    "InvoiceCatalogue": "aeat.domain.invoices._models",
    "InvoiceCatalogueRepository": "aeat.domain.invoices._repository",
    "BucketEventHistoryRepository": "aeat.domain.buckets._event_repository",
    # Profile, deadlines, and filing records
    "TaxpayerProfile": "aeat.domain.deadlines._models",
    "Schedule": "aeat.domain.deadlines._models",
    "UserProfileRecord": "aeat.domain.user_profile._values",
    "ModeloDraft": "aeat.domain.filing._schema",
    "ModeloRecord": "aeat.domain.modelos._filing_record",
}

# A Sphinx cross-reference role capturing the referenced symbol's final segment,
# e.g. ``:class:`aeat.domain.filing.ModeloRevision``` -> ``ModeloRevision``.
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


def _linked_anchors(tree: ast.Module) -> set[str]:
    """Core-struct names cross-referenced in any docstring of this module."""
    docstrings: list[str] = []
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
    problems: list[str] = []
    for name, dotted in CORE_STRUCTS.items():
        base = SRC_AEAT.parent / Path(*dotted.split("."))
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


def test_modules_that_use_a_core_struct_link_it(source_tree_ast: Mapping[Path, ast.AST]) -> None:
    """A module importing a core struct must cross-link it in a docstring."""
    violations: dict[str, list[str]] = defaultdict(list)
    for path in production_python_files():
        tree = ast_for_path(path, source_tree_ast)
        if tree is None:
            continue
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


def test_public_functions_link_anchor_parameters(source_tree_ast: Mapping[Path, ast.AST]) -> None:
    """A documented public function taking a core struct as a parameter links it.

    The spine is highest-signal at a function's own boundary: if a parameter is
    typed as a core struct, the function's docstring should cross-link it so a
    reader following the signature lands on the canonical definition.
    """
    violations: dict[str, list[str]] = defaultdict(list)
    for path in production_python_files():
        tree = ast_for_path(path, source_tree_ast)
        if tree is None:
            continue
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
