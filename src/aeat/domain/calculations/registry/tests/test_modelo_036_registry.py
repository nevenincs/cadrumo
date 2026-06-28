"""Tests for the committed Modelo 036 (censal alta/modificación/baja) registry foundation."""

from __future__ import annotations

from datetime import date
from functools import lru_cache

import pytest

from .....core.resources import bundled_path
from .. import ModeloDefinition, RegistryCatalogues, RegistryValidator, build_snapshot, load_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@lru_cache(maxsize=1)
def _load_modelo_036() -> tuple[ModeloDefinition, RegistryCatalogues]:
    modelos, catalogues = load_registry_tree(bundled_path("registry", "aeat"))
    modelo = next(m for m in modelos if m.id == "036")
    return modelo, catalogues


def test_modelo_036_validator_accepts_committed_definition() -> None:
    modelo, catalogues = _load_modelo_036()
    assert modelo.id == "036"
    assert modelo.revisions, "036 must declare at least one revision"
    assert any(rev.casillas for rev in modelo.revisions.values()), "036 must declare casillas"
    RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(modelo)


def test_modelo_036_metadata_matches_orden_eha_1274_2007_and_hac_1526_2024() -> None:
    modelo, _ = _load_modelo_036()
    assert modelo.tax_domain == "censo"
    assert modelo.cadence == "ad_hoc"
    assert modelo.jurisdiction == "ES-AEAT"
    assert "orden-eha-1274-2007:art-1" in modelo.legal_refs
    assert "orden-eha-1274-2007:art-2" in modelo.legal_refs
    assert "orden-hac-1526-2024:art-1" in modelo.legal_refs
    assert "rd-1065-2007:art-9" in modelo.legal_refs
    assert "rd-1065-2007:art-10" in modelo.legal_refs
    assert "rd-1065-2007:art-11" in modelo.legal_refs
    assert "aeat-dr-036-2025" in modelo.source_refs


def test_modelo_036_revision_starts_at_2025_02_03() -> None:
    modelo, _ = _load_modelo_036()
    revision = modelo.revisions["2025-02-03-y-siguientes"]
    assert revision.valid_from == date(2025, 2, 3)
    assert revision.period_selector.year_from == 2025
    assert set(revision.period_selector.periods) == {"alta", "modificacion", "baja"}


def test_modelo_036_snapshot_builds_for_event_periods() -> None:
    # M036 is event-triggered (cadence="ad_hoc"); the period names are
    # the three censal event kinds the form supports. Snapshot.period
    # max_length=32 accommodates these descriptive names.
    modelo, catalogues = _load_modelo_036()
    for period in ("alta", "modificacion", "baja"):
        snapshot = build_snapshot(
            modelo,
            catalogues,
            source_root=bundled_path(),
            filing_year=2025,
            period=period,
        )
        assert snapshot.revision.id == "2025-02-03-y-siguientes"


def test_modelo_036_snapshot_carries_rgat_substantive_grounding() -> None:
    modelo, catalogues = _load_modelo_036()
    snapshot = build_snapshot(modelo, catalogues, source_root=bundled_path(), filing_year=2025, period="alta")
    assert "rd-1065-2007:art-9" in snapshot.legal
    assert "rd-1065-2007:art-10" in snapshot.legal
    assert "rd-1065-2007:art-11" in snapshot.legal
    assert snapshot.legal["rd-1065-2007:art-9"].article == "9"
    assert "orden-eha-1274-2007:art-1" in snapshot.legal
    assert "aeat-modelo-036-procedure" in snapshot.sources


def test_modelo_036_filing_schedule_is_event_triggered() -> None:
    modelo, _ = _load_modelo_036()
    revision = modelo.revisions["2025-02-03-y-siguientes"]
    schedule = next(s for s in revision.filing_schedules if s.id == "modelo-036-event-triggered")
    assert schedule.period_kind == "ad_hoc"
    assert set(schedule.periods) == {"alta", "modificacion", "baja"}
