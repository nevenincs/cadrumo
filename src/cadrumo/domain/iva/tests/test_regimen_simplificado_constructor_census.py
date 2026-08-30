"""Every régimen-simplificado row construction names the canonical annual-Orden authority.

The annual Orden projection owns the durable activity identity and minimum
quota.  A direct constructor that leaves those fields to a default, or an
activity row that does not name its selected Orden row, would recreate the
test-only and inferred identity paths the projection removed.  This AST gate covers both
production and test code so the proof fixtures cannot silently retain a
different construction contract.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from ....core.directory_scan import scan_directory
from ..regimen_simplificado_rows import (
    ActividadAgricolaSimplificado,
    ActividadNoAgricolaSimplificado,
    ActividadOrdenAnual,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_REQUIRED_KEYWORDS: dict[str, frozenset[str]] = {
    "ActividadAgricolaSimplificado": frozenset({"orden_id"}),
    "ActividadNoAgricolaSimplificado": frozenset({"orden_id"}),
    "ActividadOrdenAnual": frozenset({"orden_id", "cuota_minima_pct"}),
}


def _package_root() -> Path:
    """Return the shipped ``cadrumo`` package root."""
    return Path(__file__).resolve().parents[3]


def _constructor_sites() -> list[tuple[str, int, str, frozenset[str]]]:
    """Return every direct régimen-simplificado row constructor call in shipped code and its tests."""
    root = _package_root()
    sites: list[tuple[str, int, str, frozenset[str]]] = []
    for path in scan_directory(root, pattern="*.py", recursive=True):
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        relative = path.relative_to(root).as_posix()
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            function = node.func
            name = function.id if isinstance(function, ast.Name) else getattr(function, "attr", None)
            if name not in _REQUIRED_KEYWORDS:
                continue
            sites.append(
                (
                    relative,
                    node.lineno,
                    name,
                    frozenset(keyword.arg for keyword in node.keywords if keyword.arg is not None),
                )
            )
    return sites


def test_s59_constructor_scan_reaches_the_canonical_compiler() -> None:
    """Keep the all-code AST census non-vacuous and bound to the row-projection owner."""
    found = {(relative, name) for relative, _, name, _ in _constructor_sites()}

    assert (
        "domain/calculations/registry/_m303_orden_projection_compiler.py",
        "ActividadOrdenAnual",
    ) in found


def test_every_s59_constructor_passes_its_canonical_identity_keywords() -> None:
    """No call can reintroduce defaulted, inferred, or test-only Orden identity."""
    omissions = [
        f"{relative}:{lineno} {name} missing {sorted(_REQUIRED_KEYWORDS[name] - keywords)!r}"
        for relative, lineno, name, keywords in _constructor_sites()
        if _REQUIRED_KEYWORDS[name] - keywords
    ]

    assert omissions == [], (
        "S59 constructors must explicitly pass the canonical annual-Orden fields; "
        "resolve the required `orden_id` and `cuota_minima_pct` from the bundled S59 snapshot rather than "
        "adding a default, compatibility branch, or synthetic test identifier:\n  " + "\n  ".join(omissions)
    )


def test_s59_identity_fields_are_required_by_the_typed_models() -> None:
    """The AST gate cannot be bypassed through a model-level default."""
    assert ActividadAgricolaSimplificado.model_fields["orden_id"].is_required()
    assert ActividadNoAgricolaSimplificado.model_fields["orden_id"].is_required()
    assert ActividadOrdenAnual.model_fields["orden_id"].is_required()
    assert ActividadOrdenAnual.model_fields["cuota_minima_pct"].is_required()
