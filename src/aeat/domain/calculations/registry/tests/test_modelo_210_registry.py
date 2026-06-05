"""Tests for the committed Modelo 210 (IRNR non-resident taxation) registry foundation."""

from __future__ import annotations

import pytest

from .....core.resources import bundled_path
from .. import ModeloDefinition, RegistryCatalogues, RegistryValidator, build_snapshot, load_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _load_modelo_210() -> tuple[ModeloDefinition, RegistryCatalogues]:
    modelos, catalogues = load_registry_tree(bundled_path("registry", "aeat"))
    modelo = next(m for m in modelos if m.id == "210")
    return modelo, catalogues


def test_modelo_210_validator_accepts_committed_definition() -> None:
    modelo, catalogues = _load_modelo_210()
    assert modelo.id == "210"
    assert modelo.revisions, "210 must declare at least one revision"
    assert any(rev.formulas for rev in modelo.revisions.values()), "210 must declare formulas"
    RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(modelo)


def test_modelo_210_revision_2025_declares_constructs() -> None:
    modelo, _ = _load_modelo_210()
    revision = modelo.revisions["2025"]
    assert revision.constructs, "210 2025 revision must declare constructs"
    construct_ids = {c.id for c in revision.constructs}
    assert "m210-irnr-calculation" in construct_ids


def test_modelo_210_revision_2025_formula_targets_resolve() -> None:
    modelo, _catalogues = _load_modelo_210()
    revision = modelo.revisions["2025"]
    irnr_calc = next(c for c in revision.constructs if c.id == "m210-irnr-calculation")
    assert irnr_calc.formulas, "m210-irnr-calculation must declare formulas"
    # Verify all formula references in construct exist in the revision
    formula_ids = {f.id for f in revision.formulas}
    for formula_id in irnr_calc.formulas:
        assert formula_id in formula_ids, f"formula {formula_id} not found in revision formulas"


def test_modelo_210_snapshot_builds_for_2025_event_period() -> None:
    modelo, catalogues = _load_modelo_210()
    snapshot = build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=2025,
        period="evento",
    )
    assert snapshot.revision.id == "2025"
