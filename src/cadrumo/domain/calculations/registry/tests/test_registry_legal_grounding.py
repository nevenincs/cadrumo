"""Committed registry legal/source grounding through the real validator."""

from __future__ import annotations

import ast
import re
import tomllib
from pathlib import Path

import pytest

from .....core.resources import bundled_path, resources
from .. import RegistryValidator, verify_legal_catalogue
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
    authority = resources().modelos.authority
    return authority.root, authority.modelos, authority.catalogues


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


def _pending_ref_line_numbers(tree: ast.AST) -> set[int]:
    """Return the lines carrying a literal declared as *pending* grounding.

    A pending reference names a provision the code relies on but that is NOT in
    the bundled catalogue yet -- read from live authoritative text and recorded
    so the gap is visible rather than silent. It is the deliberate opposite of a
    citation, so demanding it resolve is a category error: the two claims cannot
    both hold, and before this exemption the pending marker was unsatisfiable.

    The exemption is not a hole. A literal marked pending is held to the INVERSE
    requirement by :func:`test_production_pending_legal_refs_are_not_catalogued`
    below -- it must be absent from the catalogue -- so marking a genuinely
    catalogued reference pending fails just as loudly as leaving a real citation
    ungrounded. Nothing can hide in the gap between the two.
    """
    lines: set[int] = set()
    for node in ast.walk(tree):
        value_node: ast.AST | None = None
        if isinstance(node, ast.Assign):
            names = [target.id for target in node.targets if isinstance(target, ast.Name)]
            if any("PENDING" in name.upper() for name in names):
                value_node = node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.value is not None and "PENDING" in node.target.id.upper():
                value_node = node.value
        elif isinstance(node, ast.keyword) and node.arg == "pending_legal_refs":
            value_node = node.value
        if value_node is None:
            continue
        lines.update(line for _value, line in _direct_string_literals(value_node))
    return lines


def _production_legal_ref_literals(*, pending: bool = False) -> dict[str, tuple[str, ...]]:
    """Collect legal-ref-shaped literals in production Python.

    With ``pending=False`` (the default) this returns the CITATIONS -- literals
    asserting a grounding, which must resolve to the catalogue and its corpus.
    With ``pending=True`` it returns the literals explicitly marked as pending
    grounding, which must not.
    """
    refs: dict[str, list[str]] = {}
    for path in _PRODUCTION_PACKAGE_ROOT.rglob("*.py"):
        if "tests" in path.relative_to(_PRODUCTION_PACKAGE_ROOT).parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        doc_lines = _docstring_line_numbers(tree)
        pending_lines = _pending_ref_line_numbers(tree)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
                continue
            if node.lineno in doc_lines or not _LEGAL_REF_LITERAL_RE.match(node.value):
                continue
            if (node.lineno in pending_lines) != pending:
                continue
            location = path.relative_to(_PRODUCTION_PACKAGE_ROOT.parent).as_posix()
            refs.setdefault(node.value, []).append(f"{location}:{node.lineno}")
    return {ref: tuple(locations) for ref, locations in refs.items()}


def _direct_string_literals(node: ast.AST) -> tuple[tuple[str, int], ...]:
    """Return every directly-written string literal in ``node``, ignoring empty ones.

    An empty literal is a "no reference yet" default rather than a reference —
    ``source_ref: str = ""`` on a persisted record declares the field unset, not
    a citation of the empty catalogue key. It can never resolve, because no
    catalogue is keyed on the empty string, so admitting it would report every
    such default as an unresolvable reference while catching nothing real.
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return ((node.value, node.lineno),) if node.value.strip() else ()
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
    assert not missing, "production Python legal reference literals absent from legal catalogue:\n" + "\n".join(
        f"{ref}: {refs_by_literal[ref]}" for ref in missing
    )
    verify_legal_catalogue({ref: catalogues.legal[ref] for ref in refs}, source_root=bundled_path())


def test_production_pending_legal_refs_are_not_catalogued(
    committed_registry: tuple[Path, tuple[ModeloDefinition, ...], RegistryCatalogues],
) -> None:
    """A reference marked pending must be genuinely ungrounded.

    This is the other half of the citation gate above, and what keeps the
    pending exemption from becoming a way to smuggle an ungrounded citation
    past it. Pending means "relied upon, read from live authoritative text,
    not bundled yet"; the moment the provision IS catalogued the marker is a
    lie, and the row must be promoted to a real ``legal_refs`` citation so the
    corpus check starts covering it.

    Failing here is good news: it means someone bundled the provision and the
    only remaining work is to move the reference to its grounded home.
    """
    _registry_root, _modelos, catalogues = committed_registry
    pending_by_literal = _production_legal_ref_literals(pending=True)

    catalogued = sorted(ref for ref in pending_by_literal if ref in catalogues.legal)
    assert not catalogued, (
        "production Python marks these legal references as pending, but they are in the legal catalogue.\n"
        "Promote each to a grounded legal_refs citation instead of leaving it marked pending:\n"
        + "\n".join(f"{ref}: {pending_by_literal[ref]}" for ref in catalogued)
    )


def test_production_python_source_ref_literals_resolve_to_catalogue_and_corpus(
    committed_registry: tuple[Path, tuple[ModeloDefinition, ...], RegistryCatalogues],
) -> None:
    _registry_root, _modelos, catalogues = committed_registry
    refs_by_literal = _production_source_ref_literals()
    refs = sorted(refs_by_literal)

    assert refs_by_literal, "production Python contains no direct source_refs literals"
    missing = sorted(ref for ref in refs if ref not in catalogues.sources)
    assert not missing, "production Python source_refs literals absent from source catalogue:\n" + "\n".join(
        f"{ref}: {refs_by_literal[ref]}" for ref in missing
    )
    verify_source_catalogue(bundled_path(), {ref: catalogues.sources[ref] for ref in refs})
