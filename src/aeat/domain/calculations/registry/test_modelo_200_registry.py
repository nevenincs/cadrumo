"""Modelo 200 registry behaviour backed by official source corpus."""

from __future__ import annotations

from datetime import date
from html import unescape

import pytest

from aeat.core.resources import bundled_path

from . import RegistryValidator, build_snapshot, load_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]

_REGISTRY_ROOT = bundled_path("registry", "aeat")


def _load_modelo_200():
    modelos, catalogues = load_registry_tree(_REGISTRY_ROOT)
    modelo = next(item for item in modelos if item.id == "200")
    return modelo, catalogues


def test_modelo_200_validates_with_deadline_and_schedule_catalogue_refs() -> None:
    modelo, catalogues = _load_modelo_200()

    RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(modelo)

    snapshot = build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=2024,
        period="0A",
    )
    construct = snapshot.revision.constructs[0]
    assert construct.filing_schedules == ("modelo-200-2024-anual",)
    assert construct.deadline_windows == ("modelo-200-2024-0a",)
    linked_surfaces = {
        link.surface for link in snapshot.revision.application_links if link.id in construct.application_links
    }
    assert {
        "calculation",
        "filing",
        "review",
        "verification",
        "approval",
        "reconciliation",
        "deadline",
        "portal",
        "workflow",
    } <= linked_surfaces


def test_modelo_200_calendar_year_2024_deadline_matches_boe_order() -> None:
    modelo, catalogues = _load_modelo_200()
    snapshot = build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=2024,
        period="0A",
    )

    window = snapshot.revision.deadline_windows[0]
    source = catalogues.sources["boe-modelo-200-2025-form"]
    source_text = _normalized_text((bundled_path() / source.corpus_path).read_text(encoding="utf-8"))

    assert "modelo 200 de declaracion del impuesto sobre sociedades" in source_text
    assert "25 dias naturales siguientes a los seis meses posteriores" in source_text
    assert "desde el dia 1 de julio hasta el 22 de julio de 2025" in source_text
    assert window.opens_on == date(2025, 7, 1)
    assert window.closes_on == date(2025, 7, 25)
    assert window.payment_cutoff_on == date(2025, 7, 22)


def test_modelo_200_schedule_is_annual_for_calendar_year_entities() -> None:
    modelo, catalogues = _load_modelo_200()
    snapshot = build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=2024,
        period="0A",
    )

    schedule = snapshot.revision.filing_schedules[0]
    assert schedule.period_kind == "annual"
    assert schedule.periods == ("0A",)
    assert snapshot.revision.period_selector.periods == ("0A",)


def _normalized_text(value: str) -> str:
    return (
        unescape(value)
        .replace("\xa0", " ")
        .replace("\u2003", " ")
        .casefold()
        .replace("á", "a")
        .replace("é", "e")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("ú", "u")
    )
