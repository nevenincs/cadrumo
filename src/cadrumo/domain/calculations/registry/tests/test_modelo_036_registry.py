"""Tests for the committed Modelo 036 (censal alta/modificación/baja) registry foundation."""

from __future__ import annotations

from datetime import date

import pytest

from cadrumo.domain.calculations.registry.schema import ModeloDefinition, RegistryCatalogues
from cadrumo.domain.calculations.registry.validate import RegistryValidator

from .....core import RegistryAuthorityGrade
from .....core.resources import bundled_path
from ._registry_schema_support import _committed_modelo, _committed_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]
_DECLARATION_PROFILE_TARGET_LEGAL_REFS = frozenset(
    [
        "orden-eha-1274-2007:art-1",
        "orden-eha-1274-2007:art-2",
        "orden-hac-1526-2024:art-1",
        "rd-1065-2007:art-10",
        "rd-1065-2007:art-11",
        "rd-1065-2007:art-9",
    ]
)


def _load_modelo_036() -> tuple[ModeloDefinition, RegistryCatalogues]:
    return _committed_modelo("036")


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
    assert revision.orden_aplicabilidad == (
        "orden-eha-1274-2007:art-1",
        "orden-hac-1526-2024:art-1",
        "orden-hac-1526-2024:df-unica",
    )


def test_modelo_036_snapshot_builds_for_event_periods() -> None:
    # M036 is event-triggered (cadence="ad_hoc"); the period names are
    # the three censal event kinds the form supports. Snapshot.period
    # max_length=32 accommodates these descriptive names.
    for period in ("alta", "modificacion", "baja"):
        # APPLICABILITY grade: modelo 036's registry declares that rung, and a
        # censal alta/modificacion/baja is filed on AEAT's sede -- this
        # application produces no fichero for it, so a filing-grade snapshot
        # asks for capability the modelo neither has nor claims.
        snapshot = _committed_snapshot("036", 2025, period, RegistryAuthorityGrade.APPLICABILITY)
        assert snapshot.revision.id == "2025-02-03-y-siguientes"


def test_modelo_036_snapshot_carries_rgat_substantive_grounding() -> None:
    snapshot = _committed_snapshot("036", 2025, "alta", RegistryAuthorityGrade.APPLICABILITY)
    assert "rd-1065-2007:art-9" in snapshot.legal
    assert "rd-1065-2007:art-10" in snapshot.legal
    assert "rd-1065-2007:art-11" in snapshot.legal
    assert snapshot.legal["rd-1065-2007:art-9"].article == "9"
    assert "orden-eha-1274-2007:art-1" in snapshot.legal
    assert "aeat-modelo-036-procedure" in snapshot.sources


def test_modelo_036_declaration_pdf_profile_legal_refs_match_target_casillas() -> None:
    modelo, _ = _load_modelo_036()
    revision = modelo.revisions["2025-02-03-y-siguientes"]
    casillas_by_id = {casilla.id: casilla for casilla in revision.casillas}
    profile = next(profile for profile in revision.extraction_profiles if profile.id == "modelo-036-declaracion-pdf")

    target_refs = frozenset(
        legal_ref for target in profile.target_casillas for legal_ref in casillas_by_id[target.casilla_id].legal_refs
    )

    assert target_refs == _DECLARATION_PROFILE_TARGET_LEGAL_REFS
    assert frozenset(profile.legal_refs) == _DECLARATION_PROFILE_TARGET_LEGAL_REFS


def test_modelo_036_filing_schedule_is_event_triggered() -> None:
    modelo, _ = _load_modelo_036()
    revision = modelo.revisions["2025-02-03-y-siguientes"]
    schedule = next(s for s in revision.filing_schedules if s.id == "modelo-036-event-triggered")
    assert schedule.period_kind == "ad_hoc"
    assert set(schedule.periods) == {"alta", "modificacion", "baja"}
