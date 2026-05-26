"""Tests for committed Modelo 202 registry foundation."""

from __future__ import annotations

from datetime import date
from functools import lru_cache
from html import unescape

import pytest

from aeat.core.resources import bundled_path

from . import RegistryValidator, build_snapshot, load_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


@lru_cache(maxsize=1)
def _load_modelo_202():
    modelos, catalogues = load_registry_tree(bundled_path("registry", "aeat"))
    modelo = next(modelo for modelo in modelos if modelo.id == "202")
    return modelo, catalogues


def test_committed_modelo_202_validates_against_catalogues() -> None:
    modelo, catalogues = _load_modelo_202()

    RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(modelo)

    assert set(modelo.revisions) == {"2019-2022", "2023-2024", "2025-y-siguientes"}


def test_committed_modelo_202_marks_2025_only_b2_rate_bands_as_intentional_singletons() -> None:
    modelo, _catalogues = _load_modelo_202()
    revision = modelo.revisions["2025-y-siguientes"]
    casillas_by_id = {casilla.id: casilla for casilla in revision.casillas}

    for casilla_id in ("61", "62", "64", "65"):
        casilla = casillas_by_id[casilla_id]
        assert casilla.semantic_role_cardinality == "intentional_singleton"
        assert casilla.semantic_role_cardinality_reason is not None
        assert "2025-only" in casilla.semantic_role_cardinality_reason


def test_committed_modelo_202_static_cross_reference_and_construct_are_declared() -> None:
    modelo, catalogues = _load_modelo_202()
    snapshot = build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=2026,
        period="2P",
    )
    decision = snapshot.live_cross_references["modelo-202-static-documentation"]
    construct = snapshot.constructs["modelo-202-foundation"]

    assert decision.surface == "static_official_documentation"
    assert decision.requires_authentication is False
    assert decision.synthetic_data_allowed is False
    assert "presentation" in decision.forbidden_actions
    assert "modelo-202-portal" in construct.application_links
    assert "modelo-202-deadline" in construct.application_links
    assert set(construct.live_cross_references) == {"modelo-202-static-documentation"}
    assert set(construct.workbook_parity_refs) == {"modelo-202-dr-xlsx-2025"}
    assert set(construct.filing_schedules) == {"modelo-202-2025-y-siguientes-trimestral"}
    assert {
        "modelo-202-2025-1p",
        "modelo-202-2025-2p",
        "modelo-202-2025-3p",
        "modelo-202-2026-1p",
        "modelo-202-2026-2p",
        "modelo-202-2026-3p",
    } <= set(construct.deadline_windows)


def test_committed_modelo_202_deadline_windows_match_lis_art_40_and_aeat_calendar() -> None:
    """Modelo 202 uses the three LIS Art. 40 instalment windows.

    The law fixes April, October, and December in the first twenty
    calendar days. The committed dates below are the AEAT taxpayer
    calendar due dates after weekend rollover for 2025 and 2026.
    """
    modelo, catalogues = _load_modelo_202()
    revision = modelo.revisions["2025-y-siguientes"]
    source = catalogues.sources["aeat-modelo-202-instructions"]
    source_text = _normalized_text((bundled_path() / source.corpus_path).read_text(encoding="utf-8"))

    assert "primeros veinte dias naturales de los meses de abril" in source_text
    assert "octubre (2/p) y diciembre (3/p)" in source_text
    assert "sabado o dia inhabil se entenderan trasladados" in source_text

    windows = {window.id: window for window in revision.deadline_windows}
    expected = {
        "modelo-202-2025-1p": (date(2025, 4, 1), date(2025, 4, 21), date(2025, 4, 15)),
        "modelo-202-2025-2p": (date(2025, 10, 1), date(2025, 10, 20), date(2025, 10, 15)),
        "modelo-202-2025-3p": (date(2025, 12, 1), date(2025, 12, 22), date(2025, 12, 15)),
        "modelo-202-2026-1p": (date(2026, 4, 1), date(2026, 4, 20), date(2026, 4, 15)),
        "modelo-202-2026-2p": (date(2026, 10, 1), date(2026, 10, 20), date(2026, 10, 15)),
        "modelo-202-2026-3p": (date(2026, 12, 1), date(2026, 12, 21), date(2026, 12, 15)),
    }

    for window_id, (opens_on, closes_on, payment_cutoff_on) in expected.items():
        window = windows[window_id]
        assert window.period_kind == "quarterly"
        assert window.opens_on == opens_on
        assert window.closes_on == closes_on
        assert window.payment_cutoff_on == payment_cutoff_on
        assert "ley-27-2014:art-40" in window.legal_refs
        assert "aeat-modelo-202-instructions" in window.source_refs

    schedule = next(item for item in revision.filing_schedules if item.id == "modelo-202-2025-y-siguientes-trimestral")
    assert schedule.period_kind == "quarterly"
    assert schedule.periods == ("1P", "2P", "3P")


def test_committed_modelo_202_snapshots_build_for_each_registered_current_window() -> None:
    modelo, catalogues = _load_modelo_202()

    for filing_year in (2025, 2026):
        for period in ("1P", "2P", "3P"):
            snapshot = build_snapshot(
                modelo,
                catalogues,
                source_root=bundled_path(),
                filing_year=filing_year,
                period=period,
            )
            assert snapshot.revision.id == "2025-y-siguientes"
            assert "modelo-202-deadline" in snapshot.application_links


def _normalized_text(value: str) -> str:
    return (
        unescape(value)
        .replace("\xa0", " ")
        .casefold()
        .replace("á", "a")
        .replace("é", "e")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("ú", "u")
    )
