"""Modelo 200 registry behaviour backed by official source corpus."""

from __future__ import annotations

from datetime import date
from html import unescape

import pytest

from aeat.core.resources import bundled_path

from . import RegistryValidator, build_snapshot, load_registry_tree, resolve_export_layout

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


def test_modelo_200_liquidacion_cuota_chain_casillas_resolve_under_their_segmento() -> None:
    """The Liquidación cuota-chain casillas resolve under their DP200014 / DP200014B segmento.

    The segment-scoped casilla identity model lets Modelo 200 declare its
    Liquidación III / IV cuota-chain casillas under the AEAT record
    segments that carry them, distinct from the ECPN occurrences of the
    same five-digit numbers. This test resolves each cuota-chain casilla
    by its composed `(segmento:number)` id on the built snapshot and
    asserts it carries the expected `segmento` and bare `number`:
    `00552`, `00558`, `00562` in the Liquidación III segment `DP200014`
    and `00592`, `00599`, `00611` in the Liquidación IV segment
    `DP200014B`. It also asserts each is grounded with `legal_refs` and
    `source_refs`, the calculation-grounding contract.
    """
    modelo, catalogues = _load_modelo_200()
    snapshot = build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=2024,
        period="0A",
    )

    casilla_by_id = {casilla.id: casilla for casilla in snapshot.revision.casillas}
    expected = {
        "DP200014:00552": ("DP200014", "00552"),
        "DP200014:00558": ("DP200014", "00558"),
        "DP200014:00562": ("DP200014", "00562"),
        "DP200014B:00592": ("DP200014B", "00592"),
        "DP200014B:00599": ("DP200014B", "00599"),
        "DP200014B:00611": ("DP200014B", "00611"),
    }
    for casilla_id, (segmento, number) in expected.items():
        casilla = casilla_by_id.get(casilla_id)
        assert casilla is not None, (
            f"Liquidación cuota-chain casilla {casilla_id!r} must resolve on the "
            "Modelo 200 snapshot under its segment-scoped identity"
        )
        assert casilla.segmento == segmento
        assert casilla.number == number
        assert casilla.legal_refs, f"casilla {casilla_id!r} must carry legal_refs grounding"
        assert casilla.source_refs, f"casilla {casilla_id!r} must carry source_refs grounding"


def test_modelo_200_page_014_export_binding_resolves_00562_to_liquidacion() -> None:
    """The page-014 export binding resolves casilla 00562 to the Liquidación occurrence.

    Modelo 200 reuses the five-digit number `00562` across record
    segments: it is the Liquidación III cuota íntegra in segment
    `DP200014` and a distribución-de-dividendos field in the ECPN
    segment. The page-014 fichero-BOE export field for `00562` must bind
    the Liquidación cuota íntegra, not the ECPN occurrence. This resolves
    the export layout on the built snapshot and asserts the
    `modelo-200-page-014-casilla-00562` field's bound casilla is the
    Liquidación `DP200014:00562` identity.
    """
    modelo, catalogues = _load_modelo_200()
    snapshot = build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=2024,
        period="0A",
    )

    layout = resolve_export_layout(snapshot, "modelo-200-fichero-boe")
    page_014_field = layout.fields_by_id.get("modelo-200-page-014-casilla-00562")

    assert page_014_field is not None, (
        "the Modelo 200 fichero-BOE layout must carry the page-014 export "
        "field for casilla 00562"
    )
    assert page_014_field.casilla == "DP200014:00562", (
        "the page-014 export binding for 00562 must resolve to the Liquidación "
        f"DP200014 occurrence, not the ECPN one; got {page_014_field.casilla!r}"
    )

    liquidacion_casilla = next(
        (c for c in snapshot.revision.casillas if c.id == page_014_field.casilla), None
    )
    assert liquidacion_casilla is not None
    assert liquidacion_casilla.segmento == "DP200014"
    assert liquidacion_casilla.number == "00562"


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
