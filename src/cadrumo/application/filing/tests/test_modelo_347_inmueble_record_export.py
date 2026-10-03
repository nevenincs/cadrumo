"""A Modelo 347 fichero carries an inmueble record only for a lease.

Both record designs mark a type 2 record's kind at position 76: ``D`` for a
declarado, ``I`` for an inmueble. The inmueble record is the lessor's statement
of a business-premises lease (RD 1065/2007 art. 34.1.d), so a filer without
lease data files the type 1 record and one ``D`` record per declarado, and no
``I`` record at all. Lease data entered for the record files exactly one.

The fichero bytes come from the canonical layout renderer the export writes
with, fed the rows the real 347 resolver produced for synthetic counterparties.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import pytest

from cadrumo.domain.calculations.registry.tests.published_authority import published_revision

from ....core.aggregation import BindingSourceKind
from ....core.modelo import Modelo
from ....core.period import Period
from ....core.prior_domiciliation_election import PriorDomiciliationElection
from ....domain.calculations.registry.invoice_bindings import (
    InvoiceObservation,
    resolve_invoice_binding_row_values,
    resolve_invoice_binding_values,
)
from ....domain.filing.protocols import ModeloInputScalar, ModeloInputValue
from ..draft_construction import build_draft
from ..export import render_filing_layout
from ..export_producer import filing_producer_values
from ..runtime import ModeloOperatorProfile
from .export_support import _schema_provider, m151_producer_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

#: One-based position of the type 2 record kind in both 347 designs.
_KIND_POSITION = 76
_EJERCICIO = "decl.ejercicio"


@dataclass(frozen=True, slots=True)
class _Edition:
    revision: str
    year: int


_EDITIONS = (_Edition("2025-y-siguientes", 2025), _Edition("2011-2024", 2024))


def _observation(invoice_id: str, party_tax_id: str, name: str, year: int, clave: str) -> InvoiceObservation:
    return InvoiceObservation(
        invoice_id=invoice_id,
        source_kind=BindingSourceKind.COLLECTIBLE_INVOICE if clave == "B" else BindingSourceKind.PAYABLE_INVOICE,
        party_tax_id=party_tax_id,
        country_code="ES",
        transaction_date=date(year, 5, 12),
        base_amount=Decimal("8000.00"),
        invoice_total_amount=Decimal("8000.00"),
        operation_clave=clave,
        party_legal_name=name,
    )


def _resolved_inputs(edition: _Edition) -> dict[str, ModeloInputValue]:
    revision = published_revision("347", edition.revision)
    observations = (
        _observation("inv-cliente", "B12345674", "CLIENTE NACIONAL SL", edition.year, "B"),
        _observation("inv-proveedor", "A58818501", "PROVEEDOR NACIONAL SA", edition.year, "A"),
    )
    effective_date = date(edition.year, 12, 31)
    inputs: dict[str, ModeloInputValue] = {
        _EJERCICIO: str(edition.year),
        **{
            str(binding_id): value
            for binding_id, value in resolve_invoice_binding_values(
                revision, observations, effective_date=effective_date
            ).items()
        },
    }
    rows: dict[str, dict[str, ModeloInputScalar]] = {}
    for (binding_id, row_index), value in resolve_invoice_binding_row_values(
        revision, observations, effective_date=effective_date
    ).items():
        rows.setdefault(str(binding_id), {})[str(row_index)] = value
    inputs.update(rows)
    return inputs


def _fichero_lines(edition: _Edition, inputs: dict[str, ModeloInputValue]) -> list[str]:
    provider = _schema_provider(filing_year=edition.year, period="0A", modelos=("347",))
    draft = build_draft(
        modelo="347",
        period=Period.from_year_and_code(edition.year, "0A"),
        profile=ModeloOperatorProfile(tax_id="12345678Z", display_name="DECLARANTE PRUEBA"),
        inputs=inputs,
        schema_provider=provider,
    )
    # The draft carries the year casilla as a Decimal, which the four-digit-year
    # field refuses; the renderer receives the integer year the input contract names.
    draft = draft.model_copy(
        update={
            "values": tuple(
                value.model_copy(update={"value": edition.year}) if value.casilla_id == _EJERCICIO else value
                for value in draft.values
            ),
        },
    )
    producer_snapshot = m151_producer_snapshot().model_copy(update={"modelo": Modelo("347")})
    payload = render_filing_layout(
        provider.get_subview("347").export_layouts[0],
        registry_snapshot=provider.get_snapshot("347"),
        draft=draft,
        headers=filing_producer_values(producer_snapshot),
        producer_snapshot=producer_snapshot,
        prior_domiciliation_election=PriorDomiciliationElection.KEEP,
        product_software_identity=None,
    )
    return payload.decode("iso-8859-1").splitlines()


def _type_2_kinds(lines: list[str]) -> list[str]:
    return [line[_KIND_POSITION - 1] for line in lines if line.startswith("2347")]


@pytest.mark.parametrize("edition", _EDITIONS, ids=lambda item: item.revision)
def test_a_filer_without_leases_files_no_inmueble_record(edition: _Edition) -> None:
    lines = _fichero_lines(edition, _resolved_inputs(edition))

    assert len(lines) == 3
    assert lines[0].startswith("1347")
    assert _type_2_kinds(lines) == ["D", "D"]


@pytest.mark.parametrize("edition", _EDITIONS, ids=lambda item: item.revision)
def test_lease_data_files_one_inmueble_record(edition: _Edition) -> None:
    inputs: dict[str, ModeloInputValue] = {
        **_resolved_inputs(edition),
        "inmueble.arrendatario-nif": "B87654323",
        "inmueble.arrendatario-nombre": "ARRENDATARIO LOCAL SL",
        "inmueble.importe-operacion": Decimal("12000.00"),
        "inmueble.situacion": "1",
        "inmueble.referencia-catastral": "9872023VH5797S0001WX",
    }

    lines = _fichero_lines(edition, inputs)

    assert len(lines) == 4
    assert sorted(_type_2_kinds(lines)) == ["D", "D", "I"]
