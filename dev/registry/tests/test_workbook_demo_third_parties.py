"""Both authored 347 eras use real invoice resolution for the fictional form."""

from decimal import Decimal

import pytest

from cadrumo.domain.modelos.calculation_revision import derive_calculation_revision_id

from ..workbook_demo import DemoCase, demonstration_snapshot
from ..workbook_demo_third_parties import third_party_observations, third_party_records, third_party_summary

pytestmark = [pytest.mark.integration, pytest.mark.hex_application, pytest.mark.usefixtures("governed_fact_scope")]


@pytest.mark.parametrize("year,era", [(2024, "2011-2024"), (2025, "2025-y-siguientes")])
def test_third_party_invoice_projection(year: int, era: str) -> None:
    snapshot = demonstration_snapshot(DemoCase("347", era, None, None, filing_year=year, period="0A"))
    summary = third_party_summary(snapshot)
    saved = third_party_records(snapshot)
    rows = saved.row_binding_values
    prefix = "modelo-347-contraparte-row-"
    assert set(rows[prefix + "nif"].values()) == {"12345678Z", "87654321X", "11111111H"}
    assert "22222222J" not in rows[prefix + "nif"].values()
    expected = {
        "12345678Z": ("A", ("1210", "2420", "3630", "4840")),
        "87654321X": ("B", ("4840", "3630", "2420", "1210")),
        "11111111H": ("B", ("1815", "1815", "1815", "1815")),
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
    assert rows["modelo-347-inmueble-row-arrendatario-nif"] == {"1": "11111111H"}
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
