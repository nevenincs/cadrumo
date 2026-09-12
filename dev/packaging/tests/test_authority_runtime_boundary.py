"""Static release gates for artifact-only authority consumption."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from cadrumo.core.directory_scan import scan_directory
from dev._paths import REPO_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_SHIPPED_ROOT = REPO_ROOT / "src" / "cadrumo"
_YEAR_SELECTION_MODULES = (
    _SHIPPED_ROOT / "domain" / "calculations" / "registry" / "authority.py",
    _SHIPPED_ROOT / "domain" / "calculations" / "registry" / "snapshot.py",
    _SHIPPED_ROOT / "domain" / "calculations" / "registry" / "temporal.py",
)


def _production_modules(root: Path = _SHIPPED_ROOT) -> list[Path]:
    return [
        path
        for path in scan_directory(root, pattern="*.py", recursive=True)
        if "tests" not in path.parts and path.name != "conftest.py"
    ]


def _absolute_import_roots(tree: ast.AST) -> set[str]:
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.partition(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module.partition(".")[0])
    return roots


def _literal_path_parts(node: ast.AST, bindings: dict[str, tuple[str, ...]]) -> tuple[str, ...]:
    """Resolve static path fragments through calls, ``/`` composition, and names."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return (node.value,)
    if isinstance(node, ast.Name):
        return bindings.get(node.id, ())
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        return _literal_path_parts(node.left, bindings) + _literal_path_parts(node.right, bindings)
    if isinstance(node, ast.Call):
        values = [*node.args, *(keyword.value for keyword in node.keywords)]
        return tuple(part for value in values for part in _literal_path_parts(value, bindings))
    return ()


def _literal_path_bindings(tree: ast.AST) -> dict[str, tuple[str, ...]]:
    """Resolve module-local constants used to assemble resource paths."""
    bindings: dict[str, tuple[str, ...]] = {}
    assignments = tuple(node for node in getattr(tree, "body", ()) if isinstance(node, ast.Assign))
    for _ in range(len(assignments) + 1):
        changed = False
        for assignment in assignments:
            parts = _literal_path_parts(assignment.value, bindings)
            if not parts:
                continue
            for target in assignment.targets:
                if isinstance(target, ast.Name) and target.id not in bindings:
                    bindings[target.id] = parts
                    changed = True
        if not changed:
            break
    return bindings


def _literal_call_path(call: ast.Call, bindings: dict[str, tuple[str, ...]]) -> str:
    """Join statically resolvable call-path fragments; prose is never visited."""
    return "/".join(part.strip("/\\") for part in _literal_path_parts(call, bindings)).replace("\\", "/").lower()


def _authored_registry_accesses(tree: ast.AST) -> tuple[ast.Call, ...]:
    """Return direct calls that construct or access the authored registry path."""
    bindings = _literal_path_bindings(tree)
    return tuple(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and (
            "registry/aeat" in _literal_call_path(node, bindings)
            or "_data/registry/aeat" in _literal_call_path(node, bindings)
        )
    )


def test_raw_reader_census_resolves_indirect_path_composition() -> None:
    """A constant assembled with ``Path /`` cannot evade the production census."""
    tree = ast.parse(
        'AUTHORED = Path("_data") / "registry" / "aeat"\npayload = read_toml(AUTHORED / "iva" / "catalogues.toml")\n'
    )

    accesses = _authored_registry_accesses(tree)

    assert len(accesses) == 1
    assert accesses[0].lineno == 2


def test_shipped_runtime_has_no_operative_authored_registry_reader() -> None:
    """Production cannot construct the authored path or combine such access with a TOML parser."""
    modules = _production_modules()
    operative_accesses: dict[str, list[str]] = {}
    toml_readers: dict[str, list[str]] = {}
    covered_areas = {
        "domain/iva": False,
        "domain/calculations/registry": False,
        "domain/deadlines": False,
        "adapters/outbound/aeat/auth": False,
        "application/modelo": False,
    }
    for path in modules:
        relative = path.relative_to(_SHIPPED_ROOT).as_posix()
        for area in covered_areas:
            if relative.startswith(f"{area}/"):
                covered_areas[area] = True
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        accesses = _authored_registry_accesses(tree)
        if not accesses:
            continue
        operative_accesses[relative] = [
            f"line {call.lineno}: {ast.get_source_segment(source, call) or '<call>'}" for call in accesses
        ]
        forbidden_imports = sorted(_absolute_import_roots(tree) & {"tomllib", "rtoml"})
        if forbidden_imports:
            toml_readers[relative] = forbidden_imports

    assert len(modules) > 1500, "the shipped-code census is not covering the production tree"
    assert all(covered_areas.values()), f"raw-reader census missed production areas: {covered_areas}"
    assert toml_readers == {}, f"operative authored-registry readers import TOML parsers: {toml_readers}"
    assert operative_accesses == {}, (
        f"shipped modules access the development-only registry/aeat tree: {operative_accesses}"
    )


def test_revision_selection_delegates_year_admission_to_the_shared_catalogue() -> None:
    """Selection modules carry no literal product-year gate beside the catalogue authority."""
    literal_gates: list[str] = []
    for path in _YEAR_SELECTION_MODULES:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Compare):
                continue
            text = ast.get_source_segment(path.read_text(encoding="utf-8"), node) or ""
            if "filing_year" in text and any(
                isinstance(item, ast.Constant) and isinstance(item.value, int)
                for item in (node.left, *node.comparators)
            ):
                literal_gates.append(f"{path.name}:{node.lineno}:{text}")

    temporal_source = _YEAR_SELECTION_MODULES[-1].read_text(encoding="utf-8")
    assert "support.projection_coordinate(filing_year)" in temporal_source
    assert literal_gates == [], f"year selection duplicates literal admission limits: {literal_gates}"
