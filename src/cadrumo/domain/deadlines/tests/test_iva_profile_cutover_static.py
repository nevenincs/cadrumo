"""Static regression gates for the strict canonical IVA profile shape."""

from __future__ import annotations

import ast
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest

from ....core import scan_directory

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_IVA_SECTION = "iva"
_IVA_REGIME_PATH = _IVA_SECTION + ".regime"
_REQUIRED_IVA_FACT_PATHS = frozenset(
    (
        "tax_residence.jurisdiction_scope",
        _IVA_SECTION + ".m303_regime_composition",
        _IVA_SECTION + ".redeme_enrolled",
        _IVA_SECTION + ".cash_accounting_regime_enrolled",
        _IVA_SECTION + ".voluntary_sii_enrolled",
        _IVA_SECTION + ".hydrocarbon_deposit_advance_payment_deduction_entitled",
    ),
)
_REQUIRED_MODELO_IVA_KEYWORDS = frozenset(
    (
        "tax_territory",
        "regime_composition",
        "redeme_enrolled",
        "cash_accounting_regime_enrolled",
        "voluntary_sii_enrolled",
        "hydrocarbon_deposit_advance_payment_deduction_entitled",
    ),
)


@dataclass(frozen=True)
class _ProfileShapeExclusion:
    """One deliberately non-profile fixture fragment, keyed by its enclosing scope.

    Keyed by ``(path, function)`` rather than by line number: a line-keyed
    exemption silently detaches the moment anything above it shifts, which
    turns a reasoned exclusion into a stale one nobody re-reads. ``function``
    is ``None`` for a module-level map.
    """

    path: str
    function: str | None
    reason: str


# These are deliberately non-profile maps: censo-source labels, legal-reference
# metadata, blank-IVA refusal input, warning metadata, and raw calendar diagnostics.
_LITERAL_NON_PROFILE_EXCLUSIONS = (
    _ProfileShapeExclusion(
        "src/cadrumo/entrypoints/cli/tests/_overview_calendar_support.py",
        "_stamp_calendar_enrolment_from_censo",
        "censo source-label map",
    ),
    _ProfileShapeExclusion(
        "src/cadrumo/domain/user_profile/tests/test_taxpayer_type_schema_fields.py",
        "test_iva_profile_selector_legal_refs_resolve_against_catalogue",
        "legal-reference metadata",
    ),
    _ProfileShapeExclusion(
        "src/cadrumo/domain/deadlines/tests/test_m303_tax_territory_profile.py",
        "test_blank_wizard_iva_answers_do_not_claim_an_iva_block",
        "blank IVA answers prove no block is claimed",
    ),
    _ProfileShapeExclusion(
        "src/cadrumo/application/overview/_calendar_warnings.py",
        None,
        "warning metadata",
    ),
    _ProfileShapeExclusion(
        "src/cadrumo/application/user_profile/tests/test_profile_key_schema_required_parity.py",
        None,
        "schema-divergence metadata",
    ),
    _ProfileShapeExclusion(
        "src/cadrumo/application/overview/tests/test_calendar.py",
        "test_calendar_completeness_lists_uncomputable_with_reason",
        "raw calendar completeness diagnostics",
    ),
    _ProfileShapeExclusion(
        "src/cadrumo/application/overview/tests/test_calendar.py",
        "test_calendar_warnings_include_registry_deadline_window_predicates",
        "raw calendar warning diagnostics",
    ),
)

_FACT_CONTAINER_NON_PROFILE_EXCLUSIONS = (
    _ProfileShapeExclusion(
        "src/cadrumo/application/modelo/tests/test_m303_regimen_simplificado_scope.py",
        None,
        "schema-minimum fragment composed with the IVA block by each complete-profile fixture",
    ),
)


def _source_root() -> Path:
    return Path(__file__).resolve().parents[5]


def _called_name(call: ast.Call) -> str | None:
    if isinstance(call.func, ast.Name):
        return call.func.id
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return None


def _fact_path(call: ast.Call) -> str | None:
    if _called_name(call) != "UserProfileFact":
        return None
    value = next((keyword.value for keyword in call.keywords if keyword.arg == "path"), None)
    return value.value if isinstance(value, ast.Constant) and isinstance(value.value, str) else None


def _profile_fact_paths(container: ast.Tuple | ast.List) -> frozenset[str]:
    return frozenset(
        path for element in container.elts if isinstance(element, ast.Call) if (path := _fact_path(element))
    )


def _iter_modules() -> Iterator[tuple[Path, ast.Module]]:
    root = _source_root()
    for path in scan_directory(root / "src" / "cadrumo", pattern="*.py", recursive=True):
        yield path, ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _relative(path: Path) -> str:
    return path.relative_to(_source_root()).as_posix()


def _dicts_with_enclosing_function(module: ast.Module) -> Iterator[tuple[ast.Dict, str | None]]:
    """Yield every dict literal paired with the function that encloses it."""
    enclosing: list[str] = []
    results: list[tuple[ast.Dict, str | None]] = []

    def walk(node: ast.AST) -> None:
        entered = isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
        if entered:
            enclosing.append(node.name)  # type: ignore[union-attr]
        if isinstance(node, ast.Dict):
            results.append((node, enclosing[-1] if enclosing else None))
        for child in ast.iter_child_nodes(node):
            walk(child)
        if entered:
            enclosing.pop()

    walk(module)
    return iter(results)


def _fact_containers_with_enclosing_function(
    module: ast.Module,
) -> Iterator[tuple[ast.Tuple | ast.List, str | None]]:
    """Yield every fact container paired with the function that encloses it."""
    enclosing: list[str] = []
    results: list[tuple[ast.Tuple | ast.List, str | None]] = []

    def walk(node: ast.AST) -> None:
        entered = isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
        if entered:
            enclosing.append(node.name)  # type: ignore[union-attr]
        if isinstance(node, ast.Tuple | ast.List) and _profile_fact_paths(node):
            results.append((node, enclosing[-1] if enclosing else None))
        for child in ast.iter_child_nodes(node):
            walk(child)
        if entered:
            enclosing.pop()

    walk(module)
    return iter(results)


def test_every_claimed_current_iva_profile_has_the_canonical_required_axes() -> None:
    incomplete_fact_containers: set[tuple[str, str | None]] = set()
    incomplete_modelo_iva_constructors: list[tuple[str, int, frozenset[str]]] = []
    incomplete_literal_maps: set[tuple[str, str | None]] = set()

    for path, module in _iter_modules():
        relative_path = _relative(path)
        for node in ast.walk(module):
            if isinstance(node, ast.Call) and _called_name(node) == "ModeloIVAProfile":
                provided = frozenset(keyword.arg for keyword in node.keywords if keyword.arg is not None)
                missing = _REQUIRED_MODELO_IVA_KEYWORDS - provided
                if missing:
                    incomplete_modelo_iva_constructors.append((relative_path, node.lineno, missing))

        for fact_container, enclosing_function in _fact_containers_with_enclosing_function(module):
            fact_paths = _profile_fact_paths(fact_container)
            if _IVA_REGIME_PATH in fact_paths and _REQUIRED_IVA_FACT_PATHS - fact_paths:
                incomplete_fact_containers.add((relative_path, enclosing_function))

        for dict_node, enclosing_function in _dicts_with_enclosing_function(module):
            literal_paths = frozenset(
                key.value for key in dict_node.keys if isinstance(key, ast.Constant) and isinstance(key.value, str)
            )
            if _IVA_REGIME_PATH in literal_paths and _REQUIRED_IVA_FACT_PATHS - literal_paths:
                incomplete_literal_maps.add((relative_path, enclosing_function))

    assert incomplete_fact_containers == {
        (entry.path, entry.function) for entry in _FACT_CONTAINER_NON_PROFILE_EXCLUSIONS
    }
    assert incomplete_modelo_iva_constructors == []
    assert incomplete_literal_maps == {(entry.path, entry.function) for entry in _LITERAL_NON_PROFILE_EXCLUSIONS}
