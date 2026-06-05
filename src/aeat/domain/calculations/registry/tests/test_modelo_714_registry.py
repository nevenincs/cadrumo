"""Tests for the committed Modelo 714 (patrimonio) registry foundation."""

from __future__ import annotations

import pytest

from .....core.resources import bundled_path
from .. import ModeloDefinition, RegistryCatalogues, RegistryValidator, build_snapshot, load_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _load_modelo_714() -> tuple[ModeloDefinition, RegistryCatalogues]:
    modelos, catalogues = load_registry_tree(bundled_path("registry", "aeat"))
    modelo = next(m for m in modelos if m.id == "714")
    return modelo, catalogues


def test_modelo_714_validator_accepts_committed_definition() -> None:
    modelo, catalogues = _load_modelo_714()
    assert modelo.id == "714"
    assert modelo.revisions, "714 must declare at least one revision"
    RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(modelo)


def test_modelo_714_revision_2021_declares_constructs() -> None:
    modelo, _ = _load_modelo_714()
    revision = modelo.revisions["2021-y-siguientes"]
    assert revision.constructs, "714 2021-y-siguientes revision must declare constructs"
    construct_ids = {c.id for c in revision.constructs}
    assert "m714-patrimonio-calculation" in construct_ids


def test_modelo_714_revision_2021_declares_manual_foundation_without_fake_formulas() -> None:
    modelo, _ = _load_modelo_714()
    revision = modelo.revisions["2021-y-siguientes"]
    patrimonio_calc = next(c for c in revision.constructs if c.id == "m714-patrimonio-calculation")
    assert not revision.formulas
    assert not patrimonio_calc.formulas
    casillas = {casilla.id: casilla for casilla in revision.casillas}
    for casilla_id in (
        "patrimonio.base-imponible",
        "patrimonio.base-liquidable",
        "patrimonio.cuota-integra",
        "patrimonio.cuota-a-ingresar",
    ):
        assert casillas[casilla_id].input_kind == "manual"


def test_modelo_714_snapshot_builds_for_2021_event_period() -> None:
    modelo, catalogues = _load_modelo_714()
    snapshot = build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=2021,
        period="0A",
    )
    assert snapshot.revision.id == "2021-y-siguientes"
