"""A rate box the registry stores as a fraction is written as the percentage its design field holds.

The Modelo 210 designs print the tipo de gravamen [21] and the convenio
percentage [25] as "(%)" fields of three integers and two decimals, while the
calculation stores each rate as a fraction of one (24 % as 0.24). The export
reads each box's declared scale and writes 24,00 % as 02400, never the fraction
as 00024, and the byte check reads the same scale back.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.filing_producer_key import FilingProducerKey
from ....core.period import Period
from ....core.prior_domiciliation_election import PriorDomiciliationElection
from ....domain.calculations.registry.errors import FilingYearOutsideSupportEnvelopeError, RegistryValidationError
from ....domain.calculations.registry.tests.published_authority import (
    published_snapshot,
    published_supported_filing_years,
)
from ....domain.filing.schema import ModeloDraft, ModeloDraftStatus
from ..draft_construction import build_draft
from ..export import render_filing_layout
from ..export_producer import filing_producer_values
from ..export_verification import mismatched_casilla_ids
from ..runtime import ModeloOperatorProfile, RegistrySchemaAccessor
from .export_support import _field_slice, _general_ingreso_producer_snapshot, export_schema_provider

pytestmark = [pytest.mark.integration, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_MODELO = "210"
_ANNUAL = "0A"
_CONVENIO = validated_casilla_id("porcentaje_convenio")
_TIPO = validated_casilla_id("tipo_gravamen")
_TIPO_RENTA = validated_casilla_id("tipo_renta")
_OFFICIAL_TIPO_RENTA = "01"
_PROJECTED_YEAR = "errors.snapshot.filing_year_projected"


def _provider(filing_year: int) -> RegistrySchemaAccessor:
    return export_schema_provider(filing_year=filing_year, period=_ANNUAL, modelos=(_MODELO,))


def _draft(filing_year: int) -> ModeloDraft:
    draft = build_draft(
        modelo=_MODELO,
        period=Period.from_year_and_code(filing_year, _ANNUAL),
        profile=ModeloOperatorProfile(tax_id="12345678Z", display_name="Rate box export scale"),
        inputs={
            "rendimientos_integros": Decimal("1000.00"),
            "tipo_renta": "general",
            "porcentaje_convenio": Decimal("0.15"),
        },
        schema_provider=_provider(filing_year),
    )
    # The calculation keeps the registry's tipo_renta token, which the design's
    # two-character code field cannot hold; the official code stands in so the
    # record renders and the rate fields are what this test reads.
    values = tuple(
        value.model_copy(update={"value": _OFFICIAL_TIPO_RENTA}) if value.casilla_id == _TIPO_RENTA else value
        for value in draft.values
    )
    return draft.model_copy(update={"status": ModeloDraftStatus.APROBADO, "values": values})


def _rendered(filing_year: int, draft: ModeloDraft) -> bytes:
    snapshot = _provider(filing_year).get_snapshot(_MODELO)
    producer_snapshot = _general_ingreso_producer_snapshot(_MODELO)
    headers = {
        **filing_producer_values(producer_snapshot),
        FilingProducerKey.IRNR_DECLARACION_TIPO: "N",
        FilingProducerKey.IRNR_DECLARANTE_FULL_NAME: "Ana Prueba",
        FilingProducerKey.IRNR_DECLARANTE_TAX_ID: "12345678Z",
    }
    return render_filing_layout(
        snapshot.revision.export_layouts[0],
        registry_snapshot=snapshot,
        draft=draft,
        headers=headers,
        producer_snapshot=producer_snapshot,
        prior_domiciliation_election=PriorDomiciliationElection.KEEP,
        product_software_identity=None,
    )


def _field_slice_of(filing_year: int, casilla_id: CasillaId) -> slice:
    layout = _provider(filing_year).get_snapshot(_MODELO).revision.export_layouts[0]
    record, field = next(
        (record, field) for record in layout.records for field in record.fields if field.casilla_id == casilla_id
    )
    return _field_slice(layout, record.id, field.id)


def _field_bytes(filing_year: int, payload: bytes, casilla_id: CasillaId) -> bytes:
    return payload[_field_slice_of(filing_year, casilla_id)]


def _exported_years() -> tuple[int, ...]:
    """The supported years with an edition of their own, the only ones an export reaches."""
    support = published_supported_filing_years()
    assert support is not None
    years: list[int] = []
    for year in sorted(support.years):
        try:
            published_snapshot(_MODELO, filing_year=year, period=_ANNUAL)
            _provider(year)
        except FilingYearOutsideSupportEnvelopeError:
            continue
        except RegistryValidationError as refused:
            if refused.translated_message != _PROJECTED_YEAR:
                raise
            continue
        years.append(year)
    return tuple(years)


def test_some_supported_year_exports_the_rate_boxes() -> None:
    assert _exported_years()


@pytest.mark.parametrize("year", _exported_years())
def test_each_rate_box_stored_as_a_fraction_is_written_as_its_percentage(year: int) -> None:
    draft = _draft(year)
    stored = {value.casilla_id: value.value for value in draft.values}
    assert stored[_TIPO] == Decimal("0.24"), year
    assert stored[_CONVENIO] == Decimal("0.15"), year

    payload = _rendered(year, draft)

    # Three integers and two decimals: 24 % is 024,00 and 15 % is 015,00.
    assert _field_bytes(year, payload, _TIPO) == b"02400", year
    assert _field_bytes(year, payload, _CONVENIO) == b"01500", year


@pytest.mark.parametrize("year", _exported_years())
def test_the_byte_check_reads_the_percentage_back_and_refuses_the_fraction(year: int) -> None:
    draft = _draft(year)
    payload = _rendered(year, draft)
    provider = _provider(year)
    layout = provider.get_subview(_MODELO).export_layouts[0]

    mismatched, checked = mismatched_casilla_ids(layout, draft=draft, payload=payload, schema_provider=provider)
    assert {_TIPO, _CONVENIO} <= set(checked), year
    assert not {_TIPO, _CONVENIO} & set(mismatched), year

    tipo = _field_slice_of(year, _TIPO)
    as_fraction = payload[: tipo.start] + b"00024" + payload[tipo.stop :]
    mismatched, _checked = mismatched_casilla_ids(layout, draft=draft, payload=as_fraction, schema_provider=provider)
    assert _TIPO in mismatched, year
