"""Committed registry legal/source grounding through the real validator."""

from __future__ import annotations

import ast
import re
import tomllib
from pathlib import Path

import pytest

from .....core.resources import bundled_path
from .. import RegistryValidator, load_registry_tree, verify_legal_catalogue
from .._corpus_catalogue import verify_source_catalogue
from .._schema import ModeloDefinition, RegistryCatalogues

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_PRODUCTION_PACKAGE_ROOT = Path(__file__).resolve().parents[4]
_LEGAL_REF_LITERAL_RE = re.compile(
    r"^[a-z][a-z0-9-]+:(?:art|da|dt|df|dd|di|disp|anexo)-[a-z0-9.-]+(?:-[a-z0-9.-]+)*$",
    re.IGNORECASE,
)


@pytest.fixture(scope="module")
def committed_registry() -> tuple[Path, tuple[ModeloDefinition, ...], RegistryCatalogues]:
    registry_root = bundled_path("registry", "aeat")
    modelos, catalogues = load_registry_tree(registry_root)
    return registry_root, modelos, catalogues


def test_committed_registry_legal_and_construct_references_validate_through_loader(
    committed_registry: tuple[Path, tuple[ModeloDefinition, ...], RegistryCatalogues],
) -> None:
    """The loaded registry must satisfy legal refs and construct closure checks."""
    _registry_root, modelos, catalogues = committed_registry

    assert modelos, "committed registry load produced no modelos"

    validator = RegistryValidator(catalogues, source_root=bundled_path())
    validator.validate_registry(modelos)


def _collect_refs(value: object, key_name: str) -> tuple[str, ...]:
    found: list[str] = []

    def walk(value: object) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                if key == key_name:
                    if isinstance(item, list):
                        found.extend(ref for ref in item if isinstance(ref, str))
                    elif isinstance(item, str):
                        found.append(item)
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(value)
    return tuple(found)


@pytest.fixture(scope="module")
def raw_registry_refs(
    committed_registry: tuple[Path, tuple[ModeloDefinition, ...], RegistryCatalogues],
) -> dict[str, dict[str, tuple[str, ...]]]:
    registry_root, _modelos, _catalogues = committed_registry
    refs_by_key: dict[str, dict[str, tuple[str, ...]]] = {
        "legal_refs": {},
        "source_refs": {},
    }
    for path in registry_root.rglob("*.toml"):
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        relative_path = path.relative_to(registry_root).as_posix()
        for key_name, refs_by_file in refs_by_key.items():
            refs = _collect_refs(data, key_name)
            if refs:
                refs_by_file[relative_path] = refs
    return refs_by_key


def test_every_bundled_registry_toml_legal_ref_resolves_to_catalogue_and_corpus(
    committed_registry: tuple[Path, tuple[ModeloDefinition, ...], RegistryCatalogues],
    raw_registry_refs: dict[str, dict[str, tuple[str, ...]]],
) -> None:
    _registry_root, _modelos, catalogues = committed_registry
    refs_by_file = raw_registry_refs["legal_refs"]
    refs = sorted({ref for file_refs in refs_by_file.values() for ref in file_refs})

    assert refs_by_file, "bundled registry TOML contains no legal_refs keys"
    missing = sorted(ref for ref in refs if ref not in catalogues.legal)
    assert not missing, f"bundled registry TOML legal_refs absent from legal catalogue: {missing}"
    verify_legal_catalogue({ref: catalogues.legal[ref] for ref in refs}, source_root=bundled_path())


def test_every_bundled_registry_toml_source_ref_resolves_to_catalogue_and_corpus(
    committed_registry: tuple[Path, tuple[ModeloDefinition, ...], RegistryCatalogues],
    raw_registry_refs: dict[str, dict[str, tuple[str, ...]]],
) -> None:
    _registry_root, _modelos, catalogues = committed_registry
    refs_by_file = raw_registry_refs["source_refs"]
    refs = sorted({ref for file_refs in refs_by_file.values() for ref in file_refs})

    assert refs_by_file, "bundled registry TOML contains no source_refs keys"
    missing = sorted(ref for ref in refs if ref not in catalogues.sources)
    assert not missing, f"bundled registry TOML source_refs absent from source catalogue: {missing}"
    verify_source_catalogue(bundled_path(), {ref: catalogues.sources[ref] for ref in refs})


def _docstring_line_numbers(tree: ast.AST) -> set[int]:
    lines: set[int] = set()
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if not isinstance(body, list) or not body:
            continue
        first = body[0]
        if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
            start = getattr(first, "lineno", 0)
            end = getattr(first, "end_lineno", start)
            lines.update(range(start, end + 1))
    return lines


def _production_legal_ref_literals() -> dict[str, tuple[str, ...]]:
    refs: dict[str, list[str]] = {}
    for path in _PRODUCTION_PACKAGE_ROOT.rglob("*.py"):
        if "tests" in path.relative_to(_PRODUCTION_PACKAGE_ROOT).parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        doc_lines = _docstring_line_numbers(tree)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
                continue
            if node.lineno in doc_lines or not _LEGAL_REF_LITERAL_RE.match(node.value):
                continue
            location = path.relative_to(_PRODUCTION_PACKAGE_ROOT.parent).as_posix()
            refs.setdefault(node.value, []).append(f"{location}:{node.lineno}")
    return {ref: tuple(locations) for ref, locations in refs.items()}


def _direct_string_literals(node: ast.AST) -> tuple[tuple[str, int], ...]:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return ((node.value, node.lineno),)
    if isinstance(node, ast.Tuple | ast.List | ast.Set):
        values: list[tuple[str, int]] = []
        for item in node.elts:
            values.extend(_direct_string_literals(item))
        return tuple(values)
    return ()


def _production_source_ref_literals() -> dict[str, tuple[str, ...]]:
    refs: dict[str, list[str]] = {}
    for path in _PRODUCTION_PACKAGE_ROOT.rglob("*.py"):
        if "tests" in path.relative_to(_PRODUCTION_PACKAGE_ROOT).parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            value_node: ast.AST | None = None
            if isinstance(node, ast.Assign):
                names = [target.id for target in node.targets if isinstance(target, ast.Name)]
                if any("SOURCE_REF" in name.upper() or name == "source_refs" for name in names):
                    value_node = node.value
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                target_is_source_ref = "SOURCE_REF" in node.target.id.upper() or node.target.id == "source_refs"
                if node.value is not None and target_is_source_ref:
                    value_node = node.value
            elif isinstance(node, ast.keyword) and node.arg == "source_refs":
                value_node = node.value
            if value_node is None:
                continue
            location = path.relative_to(_PRODUCTION_PACKAGE_ROOT.parent).as_posix()
            for value, line_number in _direct_string_literals(value_node):
                refs.setdefault(value, []).append(f"{location}:{line_number}")
    return {ref: tuple(locations) for ref, locations in refs.items()}


def test_production_python_legal_ref_literals_resolve_to_catalogue_and_corpus(
    committed_registry: tuple[Path, tuple[ModeloDefinition, ...], RegistryCatalogues],
) -> None:
    _registry_root, _modelos, catalogues = committed_registry
    refs_by_literal = _production_legal_ref_literals()
    refs = sorted(refs_by_literal)

    assert refs_by_literal, "production Python contains no legal reference literals"
    missing = sorted(ref for ref in refs if ref not in catalogues.legal)
    assert not missing, (
        "production Python legal reference literals absent from legal catalogue:\n"
        + "\n".join(f"{ref}: {refs_by_literal[ref]}" for ref in missing)
    )
    verify_legal_catalogue({ref: catalogues.legal[ref] for ref in refs}, source_root=bundled_path())


def test_production_python_source_ref_literals_resolve_to_catalogue_and_corpus(
    committed_registry: tuple[Path, tuple[ModeloDefinition, ...], RegistryCatalogues],
) -> None:
    _registry_root, _modelos, catalogues = committed_registry
    refs_by_literal = _production_source_ref_literals()
    refs = sorted(refs_by_literal)

    assert refs_by_literal, "production Python contains no direct source_refs literals"
    missing = sorted(ref for ref in refs if ref not in catalogues.sources)
    assert not missing, (
        "production Python source_refs literals absent from source catalogue:\n"
        + "\n".join(f"{ref}: {refs_by_literal[ref]}" for ref in missing)
    )
    verify_source_catalogue(bundled_path(), {ref: catalogues.sources[ref] for ref in refs})
