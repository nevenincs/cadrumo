"""Tests for the committed Modelo 184 (atribucion de rentas) registry."""

from __future__ import annotations

from datetime import date

import pytest

from .....core.resources import bundled_path
from .....tests.aeat_literal_fixtures import aeat_host
from .. import ModeloDefinition, RegistryCatalogues, RegistryValidator
from ._registry_schema_support import _committed_modelo, _committed_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]
_WWW1_HOST = aeat_host("www1")
_WWW6_HOST = aeat_host("www6")


def _load_modelo_184() -> tuple[ModeloDefinition, RegistryCatalogues]:
    return _committed_modelo("184")


def test_modelo_184_registry_validator_accepts_committed_definition() -> None:
    modelo, catalogues = _load_modelo_184()
    # A stubbed validator would silently accept an empty modelo. Pin the
    # committed modelo's shape so the test verifies validation actually
    # ran against non-trivial content rather than passing trivially.
    assert modelo.id == "184"
    assert modelo.revisions, "184 must declare at least one revision"
    assert any(rev.casillas for rev in modelo.revisions.values()), "184 must declare casillas"
    RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(modelo)


def test_modelo_184_modelo_metadata_matches_hap_2250_2015() -> None:
    modelo, _ = _load_modelo_184()

    assert modelo.title == "Entidades en régimen de atribución de rentas (informativa anual)"
    assert modelo.tax_domain == "informative"
    assert modelo.cadence == "annual"
    assert modelo.jurisdiction == "ES-AEAT"
    assert "orden-hap-2250-2015:art-1" in modelo.legal_refs
    assert "orden-hap-2250-2015:art-4" in modelo.legal_refs
    assert "aeat-dr-184-2025" in modelo.source_refs
    assert "aeat-modelo-184-procedure" in modelo.source_refs


def test_modelo_184_revision_period_selector_starts_at_2015() -> None:
    modelo, catalogues = _load_modelo_184()
    # The earlier half of the split carries the 2015 start. Orden HAC/1430/2025
    # partitioned this modelo at ejercicio 2025, so the revision reaching back to
    # 2015 is `2015-2024`; `2025-y-siguientes` starts at the boundary.
    revision = modelo.revisions["2015-2024"]

    # `valid_from` is the revision's DEVENGO window start, canonicalised to the
    # ejercicio start -- 87 of the tree's 95 revisions sit on January 1, and the
    # eight that do not are genuine mid-year regime starts (the 369 OSS esquemas,
    # 490's second quarter), never an orden's publication date. Asserting
    # 2015-10-30 here conflated the two axes: that is when Orden HAP/2250/2015
    # entered force, which is a fact about the ORDEN, and the window checks read
    # `valid_from` as a devengo date.
    assert revision.valid_from == date(2015, 1, 1)
    # The orden's own effective date, asserted where it actually lives, so the
    # fact this test used to cover is not dropped by moving it.
    assert catalogues.legal["orden-hap-2250-2015:art-1"].effective_from == date(2015, 10, 30)
    assert revision.period_selector.year_from == 2015
    assert revision.period_selector.periods == ("0A",)
    assert revision.orden_aplicabilidad == ("orden-hap-2250-2015:art-1",)


def test_modelo_184_snapshot_builds_for_each_published_filing_year() -> None:
    """Every published year resolves, and resolves to the half the orden governs.

    Before the split one revision answered for every year, so this could only
    assert that a snapshot built at all. Now it also pins WHICH side of the
    boundary each year lands on, which is the fact that matters: the two halves
    carry different byte layouts, so a year resolving to the wrong one would
    write a filing at the wrong offsets while still building cleanly.
    """
    expected_by_year = {
        2018: "2015-2024",
        2019: "2015-2024",
        2020: "2015-2024",
        2021: "2015-2024",
        2022: "2015-2024",
        2023: "2015-2024",
        2024: "2015-2024",
        # Orden HAC/1430/2025 art. cuarto is applicable for the first time to
        # ejercicio 2025 for modelo 184.
        2025: "2025-y-siguientes",
        2026: "2025-y-siguientes",
    }
    for filing_year, expected in expected_by_year.items():
        snapshot = _committed_snapshot("184", filing_year, "0A")
        assert snapshot.revision.id == expected, filing_year


def test_modelo_184_snapshot_exposes_legal_and_source_grounding() -> None:
    snapshot = _committed_snapshot("184", 2025, "0A")

    assert "orden-hap-2250-2015:art-1" in snapshot.legal
    assert "orden-hap-2250-2015:art-4" in snapshot.legal
    assert snapshot.revision.orden_aplicabilidad == ("orden-hap-2250-2015:art-1",)
    assert snapshot.legal["orden-hap-2250-2015:art-4"].article == "4"
    assert "aeat-dr-184-2025" in snapshot.sources
    assert "aeat-modelo-184-procedure" in snapshot.sources
    assert "boe-modelo-184-2015-form" in snapshot.sources
    assert snapshot.sources["aeat-modelo-184-procedure"].evidence_tier == "official_source_guidance"
    assert snapshot.sources["boe-modelo-184-2015-form"].evidence_tier == "layout_authority"


def test_modelo_184_february_deadline_windows_match_hap_2250_2015_art_4() -> None:
    modelo, _ = _load_modelo_184()
    revision = modelo.revisions["2025-y-siguientes"]
    windows = {w.id: w for w in revision.deadline_windows}

    expected = {
        "modelo-184-2018-0a": (date(2019, 2, 1), date(2019, 2, 28)),
        "modelo-184-2019-0a": (date(2020, 2, 1), date(2020, 2, 29)),
        "modelo-184-2020-0a": (date(2021, 2, 1), date(2021, 2, 28)),
        "modelo-184-2021-0a": (date(2022, 2, 1), date(2022, 2, 28)),
        "modelo-184-2022-0a": (date(2023, 2, 1), date(2023, 2, 28)),
        "modelo-184-2023-0a": (date(2024, 2, 1), date(2024, 2, 29)),
        "modelo-184-2024-0a": (date(2025, 2, 1), date(2025, 2, 28)),
        "modelo-184-2025-0a": (date(2026, 2, 1), date(2026, 2, 28)),
        "modelo-184-2026-0a": (date(2027, 2, 1), date(2027, 2, 28)),
    }

    for window_id, (opens, closes) in expected.items():
        assert windows[window_id].opens_on == opens
        assert windows[window_id].closes_on == closes


def test_modelo_184_live_cross_references_are_read_only() -> None:
    modelo, _ = _load_modelo_184()
    revision = modelo.revisions["2025-y-siguientes"]
    cross_refs = {ref.id: ref for ref in revision.live_cross_references}

    static_ref = cross_refs["modelo-184-static-documentation"]
    assert static_ref.surface == "static_official_documentation"
    assert static_ref.requires_authentication is False
    assert "presentation" in static_ref.forbidden_actions
    assert "signing" in static_ref.forbidden_actions

    filed_ref = cross_refs["modelo-184-filed-declarations-read"]
    assert filed_ref.surface == "authenticated_read_surface"
    assert filed_ref.requires_authentication is True
    assert filed_ref.requires_aeat_authorization is True
    assert set(filed_ref.allowed_methods) == {"GET", "HEAD", "OPTIONS"}
    assert set(filed_ref.allowed_hosts) == {
        _WWW1_HOST,
        _WWW6_HOST,
    }
    forbidden = set(filed_ref.forbidden_actions)
    assert {
        "presentation",
        "signing",
        "amendment",
        "payment",
        "cancellation",
        "declaration-submission",
        "document-submission",
        "server-side-save",
    }.issubset(forbidden)


def test_modelo_184_construct_links_living_filing_and_extractor_surfaces() -> None:
    modelo, _ = _load_modelo_184()
    revision = modelo.revisions["2025-y-siguientes"]
    construct = next(c for c in revision.constructs if c.id == "modelo-184-informative")

    assert "modelo-184-filing" in construct.application_links
    assert "modelo-184-extractor" in construct.application_links
    assert "modelo-184-deadline" in construct.application_links
    assert "modelo-184-portal" in construct.application_links
    assert construct.filing_schedules == ("modelo-184-anual",)
    assert "modelo-184-static-documentation" in construct.live_cross_references
    assert "modelo-184-filed-declarations-read" in construct.live_cross_references


def test_modelo_184_filing_schedule_is_annual_february() -> None:
    modelo, _ = _load_modelo_184()
    revision = modelo.revisions["2025-y-siguientes"]
    schedule = next(s for s in revision.filing_schedules if s.id == "modelo-184-anual")

    assert schedule.period_kind == "annual"
    assert schedule.periods == ("0A",)
    assert "orden-hap-2250-2015:art-4" in schedule.legal_refs
