"""Ownership proofs for every public ledger defining module."""

from __future__ import annotations

import ast
import inspect
import re
from importlib import import_module
from pathlib import Path
from types import ModuleType

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PACKAGE_ROOT = Path(__file__).parents[1]
_REPOSITORY_ROOT = _PACKAGE_ROOT.parents[3]
_SOURCE_SCAN_ROOTS = (_REPOSITORY_ROOT / "src", _REPOSITORY_ROOT / "dev")
_PUBLIC_MODULE_NAMES = (
    "actions_classification",
    "actions_common",
    "actions_export",
    "actions_import",
    "actions_lifecycle",
    "actions_manual",
    "actions_split_merge",
    "aeat_record_projection",
    "attachment_review",
    "batch_ingest",
    "classification_assembly",
    "classifier_inputs",
    "closure_findings",
    "confirm_establishment",
    "confirmation_gate",
    "confirmation_record",
    "consent_withdrawal",
    "counterparty_establishment",
    "country_vocabulary_advisory",
    "deterministic_findings",
    "document_direction",
    "document_transcription",
    "establishment_ladder",
    "evidence",
    "evidence_advisory",
    "evidence_draft",
    "evidence_input",
    "evidence_reference",
    "evidence_split",
    "evidence_textlayer",
    "extracted_document_cache",
    "extraction_draft_store",
    "filer_establishment",
    "grounded_reading",
    "grounding_anchor",
    "id_resolution",
    "identity_roles",
    "invoice_extraction_authority",
    "llm_classification",
    "llm_diagnostics",
    "llm_review_workflow",
    "models",
    "participation_read",
    "party_attribution",
    "party_colocation",
    "postal_shape_finding",
    "preconditions",
    "preflight",
    "protocols",
    "ratios",
    "regime_contradiction",
    "review_advisories",
    "review_projection",
    "rule_repository",
)
_RETIRED_MODULE_NAMES = tuple(f"_{name}" for name in _PUBLIC_MODULE_NAMES)
_PACKAGE_FACADE_IMPORT = re.compile(
    r"(?m)^\s*from\s+(?:cadrumo\.application\.ledger|(?:\.+)?application\.ledger|\.+ledger)\s+import\b"
)
_LEDGER_TEST_PACKAGE_FACADE_IMPORT = re.compile(r"(?m)^\s*from\s+\.\.\s+import\b")
_PUBLIC_DEFINING_MODULES: tuple[ModuleType, ...] = tuple(
    import_module(f"cadrumo.application.ledger.{name}") for name in _PUBLIC_MODULE_NAMES
)


def _imported_names(module: ModuleType) -> frozenset[str]:
    """Return every identifier imported by a public defining module."""
    source_path = Path(module.__file__ or "")
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.asname or alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            names.update(alias.asname or alias.name for alias in node.names)
    return frozenset(names)


def _locally_bound_names(module: ModuleType) -> frozenset[str]:
    """Return names whose public binding is authored in this module."""
    source_path = Path(module.__file__ or "")
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            names.add(node.name)
        elif isinstance(node, ast.TypeAlias) and isinstance(node.name, ast.Name):
            names.add(node.name.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
        elif isinstance(node, ast.Assign):
            names.update(target.id for target in node.targets if isinstance(target, ast.Name))
    return frozenset(names)


def test_public_module_inventory_is_complete_and_the_package_namespace_is_inert() -> None:
    """A defining module cannot appear without an ownership proof."""
    actual = {path.stem for path in _PACKAGE_ROOT.glob("*.py") if path.name != "__init__.py"}
    assert actual == set(_PUBLIC_MODULE_NAMES)

    initializer = ast.parse((_PACKAGE_ROOT / "__init__.py").read_text(encoding="utf-8"))
    assert not any(isinstance(node, ast.Import | ast.ImportFrom | ast.FunctionDef | ast.AsyncFunctionDef) for node in initializer.body)


def test_retired_ledger_modules_and_package_facade_imports_have_zero_remnants() -> None:
    """Moved defining paths and the retired package facade cannot be recreated."""
    retired_files = [str(_PACKAGE_ROOT / f"{name}.py") for name in _RETIRED_MODULE_NAMES if (_PACKAGE_ROOT / f"{name}.py").exists()]
    source_remnants: list[str] = []
    for source_root in _SOURCE_SCAN_ROOTS:
        for path in source_root.rglob("*.py"):
            source = path.read_text(encoding="utf-8")
            for retired_name in _RETIRED_MODULE_NAMES:
                qualified_path = f"cadrumo.application.ledger.{retired_name}"
                relative_path = f"ledger.{retired_name}"
                slash_path = f"application/ledger/{retired_name}.py"
                backslash_path = f"application\\ledger\\{retired_name}.py"
                retired_filename = f"{retired_name}.py"
                is_ledger_test = path.is_relative_to(_PACKAGE_ROOT / "tests")
                has_retired_filename = is_ledger_test and (
                    f'"{retired_filename}"' in source or f"'{retired_filename}'" in source
                )
                if (
                    qualified_path in source
                    or relative_path in source
                    or slash_path in source
                    or backslash_path in source
                    or has_retired_filename
                ):
                    source_remnants.append(f"{path}: {retired_name}")
            if _PACKAGE_FACADE_IMPORT.search(source):
                source_remnants.append(f"{path}: package facade import")
            if path.is_relative_to(_PACKAGE_ROOT / "tests") and _LEDGER_TEST_PACKAGE_FACADE_IMPORT.search(source):
                source_remnants.append(f"{path}: relative package facade import")

    assert retired_files == []
    assert source_remnants == []


@pytest.mark.parametrize("module", _PUBLIC_DEFINING_MODULES, ids=lambda module: module.__name__)
def test_every_public_ledger_export_is_owned_by_its_defining_module(module: ModuleType) -> None:
    """Exports are local definitions, never imports, aliases, or re-exports."""
    exported = tuple(module.__all__)
    assert exported
    assert len(exported) == len(set(exported))
    assert [name for name in exported if name not in vars(module)] == []
    assert sorted(set(exported) & _imported_names(module)) == []
    assert sorted(set(exported) - _locally_bound_names(module)) == []

    foreign_runtime_exports = {
        name: getattr(value, "__module__", None)
        for name in exported
        if (isinstance(value := getattr(module, name), type) or inspect.isroutine(value))
        and getattr(value, "__module__", None) != module.__name__
    }
    assert foreign_runtime_exports == {}
