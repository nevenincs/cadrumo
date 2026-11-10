"""Both authored 347 eras use real invoice resolution for the fictional form."""

from decimal import Decimal

import pytest

from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope
from cadrumo.domain.modelos.calculation_revision import derive_calculation_revision_id

from ..workbook_demo import demonstration_snapshot
from ..workbook_demo_cases import DemoCase
from ..workbook_demo_third_parties import third_party_observations, third_party_records, third_party_summary
from .authored_edition_support import authored_revisions

pytestmark = [pytest.mark.integration, pytest.mark.hex_application, pytest.mark.usefixtures("governed_fact_scope")]


def _eras() -> list[tuple[int, str]]:
    """Each authored era that governs an exercise from the support floor up, with an exercise it governs."""
    floor = filing_year_envelope().floor
    return [
        (revision.valid_to.year if revision.valid_to is not None else revision.valid_from.year, str(revision.id))
        for revision in authored_revisions("347")
        if revision.valid_to is None or revision.valid_to.year >= floor
    ]


@pytest.mark.parametrize("year,era", _eras())
def test_third_party_invoice_projection(year: int, era: str) -> None:
    snapshot = demonstration_snapshot(DemoCase("347", era, None, None, filing_year=year, period="0A"))
    summary = third_party_summary(snapshot)
    saved = third_party_records(snapshot)
    rows = saved.row_binding_values
    prefix = "modelo-347-contraparte-row-"
    assert set(rows[prefix + "nif"].values()) == {"12345678Z", "X0001502F", "00001500M"}
    assert "00001501Y" not in rows[prefix + "nif"].values()
    expected = {
        "12345678Z": ("A", ("1210", "2420", "3630", "4840")),
        "X0001502F": ("B", ("4840", "3630", "2420", "1210")),
        "00001500M": ("B", ("1815", "1815", "1815", "1815")),
    }
    for index, nif in rows[prefix + "nif"].items():
        clave, amounts = expected[nif]
        assert rows[prefix + "clave"][index] == clave
        quarters = tuple(Decimal(rows[prefix + f"importe-q{q}"][index]) for q in range(1, 5))
        assert quarters == tuple(map(Decimal, amounts))
        assert Decimal(rows[prefix + "importe"][index]) == sum(quarters)
    assert summary["modelo-347-declarante-numero-personas-entidades"] == 3
    assert summary["modelo-347-declarante-importe-total-anual-operaciones"] == Decimal("31460")
    assert summary["modelo-347-declarante-numero-inmuebles"] == 1
    assert summary["modelo-347-declarante-importe-total-arrendamiento-locales"] == Decimal("7260")
    assert rows["modelo-347-inmueble-row-arrendatario-nif"] == {"1": "00001500M"}
    assert Decimal(rows["modelo-347-inmueble-row-importe"]["1"]) == Decimal("7260")
    assert saved.registry_snapshot_ref == snapshot.snapshot_ref
    assert saved.binding_overrides == {}
    assert saved.calculation_revision_id == derive_calculation_revision_id(
        work_unit_id=saved.work_unit_id,
        input_values_by_casilla_id={},
        binding_overrides={},
        casilla_values={},
        detail_rows=(),
        row_binding_values=rows,
        source_provenance=(),
        filing_instance_evidence=None,
    )
    assert third_party_records(snapshot).calculation_revision_id == saved.calculation_revision_id
    assert all(row.transaction_date.year == year for row in third_party_observations(year))
