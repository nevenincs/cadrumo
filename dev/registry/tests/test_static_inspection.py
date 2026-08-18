"""Real-authority tests for the non-filing revision inspection projection."""

from __future__ import annotations

import ast
from collections.abc import Iterable
from pathlib import Path

import pytest

from .....core import scan_directory
from .. import RegistryRevisionInspection, bundled_revision_inspection

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


_REPOSITORY_ROOT = Path(__file__).resolve().parents[6]
_SOURCE_ROOT = _REPOSITORY_ROOT / "src" / "cadrumo"
_INSPECTION_SYMBOLS = frozenset(
    {
        "RegistryRevisionInspection",
        "bundled_revision_inspection",
        "inspect_revision",
    },
)
_RUNTIME_BOUNDARY_ROOTS = (
    _SOURCE_ROOT / "application",
    _SOURCE_ROOT / "adapters",
    _SOURCE_ROOT / "entrypoints",
)
_STATIC_CONSUMERS = (
    _REPOSITORY_ROOT / "dev" / "registry" / "_semantic_map_validation.py",
    _REPOSITORY_ROOT / "dev" / "registry" / "_semantic_map_join.py",
    _REPOSITORY_ROOT / "dev" / "registry" / "_dp30302_field_matrix.py",
    _REPOSITORY_ROOT / "dev" / "registry" / "_export_tree.py",
    _REPOSITORY_ROOT / "dev" / "registry" / "_variable_envelope.py",
)
_LEGACY_STATIC_SYMBOLS = frozenset(
    {
        "RegistrySnapshot",
        "build_snapshot",
        "load_modelo_directory",
        "validate_snapshot_source_authority",
        "validate_semantic_map_against_inspection",
        "join_record_design_semantics_inspection",
    },
)


def _python_sources(roots: Iterable[Path]) -> tuple[Path, ...]:
    return tuple(path for root in roots for path in scan_directory(root, pattern="*.py", recursive=True))


def _attribute_path(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute) and (parent := _attribute_path(node.value)) is not None:
        return f"{parent}.{node.attr}"
    return None


def _registry_api_references(tree: ast.AST, symbols: frozenset[str]) -> set[str]:
    """Resolve direct and aliased registry API imports through the AST."""
    module_aliases: dict[str, str] = {}
    referenced: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            referenced.update(alias.name for alias in node.names if alias.name in symbols)
            if node.module is not None:
                for alias in node.names:
                    qualified = f"{node.module}.{alias.name}"
                    if qualified.startswith("cadrumo.domain.calculations.registry"):
                        module_aliases[alias.asname or alias.name] = qualified
        elif isinstance(node, ast.Import):
            for alias in node.names:
                local = alias.asname or alias.name.split(".", maxsplit=1)[0]
                module_aliases[local] = alias.name
    for node in ast.walk(tree):
        if not isinstance(node, ast.Attribute) or (path := _attribute_path(node)) is None:
            continue
        local, _, suffix = path.partition(".")
        imported_module = module_aliases.get(local)
        if imported_module is None:
            continue
        qualified = f"{imported_module}.{suffix}" if suffix else imported_module
        if qualified.startswith("cadrumo.domain.calculations.registry.") and node.attr in symbols:
            referenced.add(node.attr)
    return referenced


def _function_definitions(tree: ast.AST) -> set[str]:
    return {node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}


def _non_registry_calculation_sources() -> tuple[Path, ...]:
    return tuple(
        path
        for path in _python_sources((_SOURCE_ROOT / "domain" / "calculations",))
        if "registry" not in path.relative_to(_SOURCE_ROOT / "domain" / "calculations").parts
    )


def _handoff_sources() -> tuple[Path, ...]:
    return tuple(
        path
        for path in _python_sources((_SOURCE_ROOT, _REPOSITORY_ROOT / "dev"))
        if "handoff" in path.as_posix().lower()
    )


def test_m303_midyear_designs_are_canonically_selected_without_a_snapshot() -> None:
    """Static inspection follows temporal selection yet retains no filing context."""
    early = bundled_revision_inspection("303", filing_year=2024, period="2T")
    late = bundled_revision_inspection("303", filing_year=2024, period="3T")

    assert isinstance(early, RegistryRevisionInspection)
    assert early.revision_id == "2024-hasta-08-y-2t"
    assert late.revision_id == "2024-desde-09-y-3t"
    assert "aeat-dr-303-2024-early" in early.revision_source_refs
    assert "aeat-dr-303-2024-late" in late.revision_source_refs
    assert "filing_year" not in RegistryRevisionInspection.model_fields
    assert "period" not in RegistryRevisionInspection.model_fields


def test_m038_inspection_retains_exact_model_law_and_construct_evidence() -> None:
    """The non-filing projection carries the selected revision's evidence union."""
    inspection = bundled_revision_inspection("038", filing_year=2025, period="01")

    assert inspection.revision_id == "2002-y-siguientes"
    assert inspection.legal_ref_ids == frozenset(
        {
            "ley-58-2003:art-93",
            "orden-hac-66-2002:art-1",
            "orden-hac-66-2002:art-6",
        },
    )
    assert inspection.source_ref_ids == frozenset(
        {
            "enrolled-modelo-038-layout",
            "enrolled-modelo-038-procedure",
        },
    )
    assert inspection.casilla_ids == frozenset({"decl.ejercicio", "decl.tipo-declaracion"})
    assert inspection.binding_ids == frozenset()
    assert tuple(ref.id for ref in inspection.workbook_parity_refs) == ("modelo-038-orden-static-layout",)
    assert inspection.live_cross_references == ()


def test_inspection_api_cannot_cross_from_static_authority_into_runtime_boundaries() -> None:
    """AST references keep inspection authority out of all runtime consumers."""
    offenders = {
        path.relative_to(_REPOSITORY_ROOT): _registry_api_references(
            ast.parse(path.read_text(encoding="utf-8")), _INSPECTION_SYMBOLS
        )
        for path in (
            *_python_sources(_RUNTIME_BOUNDARY_ROOTS),
            *_non_registry_calculation_sources(),
            *_handoff_sources(),
        )
        if _registry_api_references(ast.parse(path.read_text(encoding="utf-8")), _INSPECTION_SYMBOLS)
    }

    assert offenders == {}


def test_static_map_authority_has_no_snapshot_or_raw_loader_compatibility() -> None:
    """Static compiler stages admit only inspection authority, never filing state."""
    imported_legacy = {
        path.relative_to(_REPOSITORY_ROOT): _registry_api_references(
            ast.parse(path.read_text(encoding="utf-8")), _LEGACY_STATIC_SYMBOLS
        )
        for path in _STATIC_CONSUMERS
        if _registry_api_references(ast.parse(path.read_text(encoding="utf-8")), _LEGACY_STATIC_SYMBOLS)
    }
    defined_legacy = {
        path.relative_to(_REPOSITORY_ROOT): _function_definitions(
            ast.parse(path.read_text(encoding="utf-8"))
        ).intersection(_LEGACY_STATIC_SYMBOLS)
        for path in _STATIC_CONSUMERS
        if _function_definitions(ast.parse(path.read_text(encoding="utf-8"))).intersection(_LEGACY_STATIC_SYMBOLS)
    }

    assert imported_legacy == {}
    assert defined_legacy == {}


def test_inspection_census_understands_public_facade_and_private_module_aliases() -> None:
    """The boundary census is semantic AST inspection, not a text substring check."""
    direct = ast.parse(
        "from cadrumo.domain.calculations.registry import bundled_revision_inspection as inspect\n",
    )
    public_facade = ast.parse(
        "import cadrumo.domain.calculations.registry as registry\nvalue = registry.RegistryRevisionInspection\n"
    )
    module = ast.parse(
        "import cadrumo.domain.calculations.registry._authority as authority\nvalue = authority.inspect_revision\n"
    )
    imported_public_facade = ast.parse(
        "from cadrumo.domain.calculations import registry as r\nvalue = r.RegistryRevisionInspection\n"
    )
    imported_private_module = ast.parse(
        "from cadrumo.domain.calculations.registry import _authority as a\nvalue = a.inspect_revision\n"
    )

    assert _registry_api_references(direct, _INSPECTION_SYMBOLS) == {"bundled_revision_inspection"}
    assert _registry_api_references(public_facade, _INSPECTION_SYMBOLS) == {"RegistryRevisionInspection"}
    assert _registry_api_references(module, _INSPECTION_SYMBOLS) == {"inspect_revision"}
    assert _registry_api_references(imported_public_facade, _INSPECTION_SYMBOLS) == {"RegistryRevisionInspection"}
    assert _registry_api_references(imported_private_module, _INSPECTION_SYMBOLS) == {"inspect_revision"}


def test_legacy_census_detects_private_module_alias_bypass() -> None:
    """A static compiler cannot restore snapshot/loaders through module aliases."""
    legacy_alias = ast.parse(
        "import cadrumo.domain.calculations.registry._loader as loader\nvalue = loader.load_modelo_directory\n"
    )
    imported_legacy_alias = ast.parse(
        "from cadrumo.domain.calculations.registry import _loader as l\nvalue = l.load_modelo_directory\n"
    )

    assert _registry_api_references(legacy_alias, _LEGACY_STATIC_SYMBOLS) == {"load_modelo_directory"}
    assert _registry_api_references(imported_legacy_alias, _LEGACY_STATIC_SYMBOLS) == {"load_modelo_directory"}
