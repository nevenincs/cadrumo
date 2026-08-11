"""Static regression gates for the strict canonical IVA profile shape."""

from __future__ import annotations

import ast
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest

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
class _LiteralMapExclusion:
    path: str
    line: int
    reason: str


# These are deliberately non-profile maps: censo-source labels, legal-reference
# metadata, blank-IVA refusal input, warning metadata, and raw calendar diagnostics.
_LITERAL_NON_PROFILE_EXCLUSIONS = (
    _LiteralMapExclusion(
        "src/cadrumo/entrypoints/cli/tests/_overview_calendar_support.py",
        198,
        "censo source-label map",
    ),
    _LiteralMapExclusion(
        "src/cadrumo/domain/user_profile/tests/test_taxpayer_type_schema_fields.py",
        348,
        "legal-reference metadata",
    ),
    _LiteralMapExclusion(
        "src/cadrumo/domain/deadlines/tests/test_m303_tax_territory_profile.py",
        51,
        "blank IVA answers prove no block is claimed",
    ),
    _LiteralMapExclusion(
        "src/cadrumo/application/overview/_calendar_warnings.py",
        43,
        "warning metadata",
    ),
    _LiteralMapExclusion(
        "src/cadrumo/application/user_profile/tests/test_profile_key_schema_required_parity.py",
        51,
        "schema-divergence metadata",
    ),
    _LiteralMapExclusion(
        "src/cadrumo/application/overview/tests/test_calendar.py",
        965,
        "raw calendar completeness diagnostics",
    ),
    _LiteralMapExclusion(
        "src/cadrumo/application/overview/tests/test_calendar.py",
        985,
        "raw calendar warning diagnostics",
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
    for path in (root / "src" / "cadrumo").rglob("*.py"):
        yield path, ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _relative(path: Path) -> str:
    return path.relative_to(_source_root()).as_posix()


def test_every_claimed_current_iva_profile_has_the_canonical_required_axes() -> None:
    incomplete_fact_containers: list[tuple[str, int, frozenset[str]]] = []
    incomplete_modelo_iva_constructors: list[tuple[str, int, frozenset[str]]] = []
    incomplete_literal_maps: set[tuple[str, int]] = set()

    for path, module in _iter_modules():
        relative_path = _relative(path)
        for node in ast.walk(module):
            if isinstance(node, ast.Tuple | ast.List):
                fact_paths = _profile_fact_paths(node)
                if _IVA_REGIME_PATH in fact_paths:
                    missing = _REQUIRED_IVA_FACT_PATHS - fact_paths
                    if missing:
                        incomplete_fact_containers.append((relative_path, node.lineno, missing))

            if isinstance(node, ast.Call) and _called_name(node) == "ModeloIVAProfile":
                provided = frozenset(keyword.arg for keyword in node.keywords if keyword.arg is not None)
                missing = _REQUIRED_MODELO_IVA_KEYWORDS - provided
                if missing:
                    incomplete_modelo_iva_constructors.append((relative_path, node.lineno, missing))

            if isinstance(node, ast.Dict):
                literal_paths = frozenset(
                    key.value for key in node.keys if isinstance(key, ast.Constant) and isinstance(key.value, str)
                )
                if _IVA_REGIME_PATH in literal_paths and _REQUIRED_IVA_FACT_PATHS - literal_paths:
                    incomplete_literal_maps.add((relative_path, node.lineno))

    assert incomplete_fact_containers == []
    assert incomplete_modelo_iva_constructors == []
    assert incomplete_literal_maps == {(entry.path, entry.line) for entry in _LITERAL_NON_PROFILE_EXCLUSIONS}
