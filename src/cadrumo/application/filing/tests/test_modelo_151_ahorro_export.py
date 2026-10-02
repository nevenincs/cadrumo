"""Modelo 151's export writes the computed ahorro base and cuota into boxes [18] and [20].

Preview and filing share one formula path: the cuota the calculation shows is
the cuota the fichero carries. The 2015-2022 design places ``Base liquidable del
ahorro [18]`` at byte 808 and ``Cuota correspondiente a la base liquidable general
del ahorro [20]`` at byte 842 of record M15108000. The 2023 design uses those
offsets on M15110000. The rendered bytes are read back from the official offsets.

The cuota expected here is summed tranche by tranche from the escala of art.
93.2.e).2.º for each tested year, never copied from the registry.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import pytest

from ....core.casilla_id import validated_casilla_id
from ....core.period import Period
from ....core.prior_domiciliation_election import PriorDomiciliationElection
from ....domain.calculations.registry.export_parse import parse_export_payload
from ....domain.filing.software_identity import AeatProductSoftwareEvidence, AeatProductSoftwareIdentity
from ....domain.submission.models import ModeloDraftStatus
from ..draft_construction import build_draft
from ..export import export_draft
from ..runtime import ModeloOperatorProfile
from .export_support import _schema_provider, m151_producer_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_SURFACE = "modelo-151-ahorro-export"
_BASE_GENERAL = validated_casilla_id("impatriado.base-liquidable-general", surface=_SURFACE)
_BASE_AHORRO = validated_casilla_id("impatriado.base-liquidable-ahorro", surface=_SURFACE)
_RETENCIONES = validated_casilla_id("impatriado.retenciones", surface=_SURFACE)
_CUOTA_AHORRO = validated_casilla_id("impatriado.cuota-integra-ahorro", surface=_SURFACE)

_BASE_AHORRO_VALUE = Decimal("250000.00")


def _software() -> AeatProductSoftwareIdentity:
    """Synthetic product identity; both 151 layouts open with a filing envelope that prints it."""
    return AeatProductSoftwareIdentity(
        program_identifier="C151",
        developer_tax_id="Y0000001S",
        evidence=(AeatProductSoftwareEvidence(reference="aeat-software-registration:c151", digest="a" * 64),),
    )


@dataclass(frozen=True, slots=True)
class _Coordinate:
    year: int
    liquidation_record: str
    base_field: str
    cuota_field: str
    top_rate: Decimal


#: The escala above 200.000 charges 26 % in 2022 and 27 % in 2023.
_COORDINATES = (
    _Coordinate(2022, "m151-page-08", "m151-2015.pagina08.f041", "m151-2015.pagina08.f043", Decimal("0.26")),
    _Coordinate(2023, "m151-page-10", "m151-2023.pagina10.f041", "m151-2023.pagina10.f043", Decimal("0.27")),
)


def _expected_cuota(coordinate: _Coordinate) -> Decimal:
    tranches = (
        (Decimal("0"), Decimal("6000"), Decimal("0.19")),
        (Decimal("6000"), Decimal("50000"), Decimal("0.21")),
        (Decimal("50000"), Decimal("200000"), Decimal("0.23")),
        (Decimal("200000"), _BASE_AHORRO_VALUE, coordinate.top_rate),
    )
    return sum(((upper - lower) * rate for lower, upper, rate in tranches), Decimal("0")).quantize(Decimal("0.01"))


@pytest.mark.parametrize("coordinate", _COORDINATES, ids=lambda item: str(item.year))
def test_boxes_18_and_20_carry_the_computed_ahorro_chain(coordinate: _Coordinate, tmp_path: Path) -> None:
    provider = _schema_provider(filing_year=coordinate.year, period="0A", modelos=("151",))
    draft = build_draft(
        modelo="151",
        period=Period.from_year_and_code(coordinate.year, "0A"),
        profile=ModeloOperatorProfile(tax_id="12345678Z", display_name="Ahorro export test"),
        inputs={
            _BASE_GENERAL: Decimal("0"),
            _BASE_AHORRO: _BASE_AHORRO_VALUE,
            _RETENCIONES: Decimal("0"),
        },
        schema_provider=provider,
    ).model_copy(update={"status": ModeloDraftStatus.APROBADO})
    expected = _expected_cuota(coordinate)
    draft_values = {str(value.casilla_id): value.value for value in draft.values}
    assert Decimal(str(draft_values[str(_CUOTA_AHORRO)])) == expected

    output_path = tmp_path / f"modelo-151-{coordinate.year}.txt"
    export_draft(
        draft,
        output_path=output_path,
        producer_snapshot=m151_producer_snapshot(),
        prior_domiciliation_election=PriorDomiciliationElection.KEEP,
        product_software_identity=_software(),
        schema_provider=provider,
    )

    layout = provider.get_subview("151").export_layouts[0]
    record = next(item for item in layout.records if str(item.id) == coordinate.liquidation_record)
    offsets = {str(field.id): field.offset for field in record.fields}
    assert (offsets[coordinate.base_field], offsets[coordinate.cuota_field]) == (808, 842)
    parsed = parse_export_payload(layout, output_path.read_bytes(), sources=provider.sources)
    by_field = {(str(item.record_id), str(item.field_id)): item for item in parsed.fields}
    base_box = by_field[(coordinate.liquidation_record, coordinate.base_field)]
    cuota_box = by_field[(coordinate.liquidation_record, coordinate.cuota_field)]

    assert str(base_box.casilla_id) == str(_BASE_AHORRO)
    assert str(cuota_box.casilla_id) == str(_CUOTA_AHORRO)
    assert Decimal(str(base_box.value)) == _BASE_AHORRO_VALUE
    assert Decimal(str(cuota_box.value)) == expected
    if coordinate.year == 2023:
        marker = by_field[("m151-did", "m151-2023.did.f014")]
        assert marker.raw == "0"
        assert marker.value == 0
