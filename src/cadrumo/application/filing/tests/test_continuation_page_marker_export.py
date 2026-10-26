"""The ``Indicador de página complementaria`` marks a continuation page, never an amendment.

Every official design that prints this slot at posición 12, longitud 1, reads it the
same way, and none ties it to a declaración complementaria:

- DR303 (``aeat-dr-303-2022`` through ``aeat-dr-303-2026``) and DR353
  (``aeat-dr-353-2021-2025``, ``aeat-dr-353-2026``) state it in their notes: "El campo
  indicador de página complementaria se cumplimentará cuando en el fichero van más de
  una página del mismo tipo", and "La C de la columna Comp indica los campos que pueden
  tener contenido en las páginas complementarias". DR353 2026 página 02 admits only
  ``blanco``.
- DR131 (``aeat-dr-131-2024`` onwards) prints ``En blanco`` for the slot on página 1,
  which every filing carries once, and ``Blanco (No complementaria) o "C"
  (Complementaria)`` only on the DPA page, which repeats per activity and carries the
  same ``Com`` column of continuable campos. A declaración complementaria is declared on
  página 1 itself, campo 67 ``blanco o "X"``.
- DR232 (``aeat-dr-232-2016``, ``aeat-dr-232-2018``) prints ``C o blanco`` on DR23201 and
  DR23202, both with a ``Comp`` column, and declares the complementaria at campo 16,
  ``Declaración complementaria o sustitutiva``, ``S, C o blanco``.

So a complementaria's first page writes blank there and only a further page of the same
type writes ``C``. The expected bytes are transcribed from those designs, never read from
the layout under test.

Real-behaviour: shipped export fields from the published authority, the real producer
snapshot, the real fixed-width writer and, for modelo 131, the whole ``export_draft``
path with its post-write verification. No mocks, stubs, skips or xfail.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.tests.published_authority import published_snapshot

from ....core.casilla_id import validated_casilla_id
from ....core.modelo import Modelo
from ....core.prior_domiciliation_election import PriorDomiciliationElection
from ....domain.calculations.registry.schema import RegistrySnapshot
from ....domain.calculations.registry.schema_exports import (
    ExportFieldDefinition,
    ExportLayoutDefinition,
    ExportRecordDefinition,
)
from ....domain.filing.errors import FilingExportValidationError
from ....domain.filing.software_identity import development_mock_software_identity
from ....domain.submission.models import ModeloDraftStatus
from ..draft_construction import build_draft
from ..export import export_draft
from ..producer_snapshot import GeneralFilingProfileFacts, build_filing_producer_snapshot
from ..projection import FilingRecordRenderContext
from ..record_field_renderer import continuation_page_marker, format_field
from ..runtime import ModeloOperatorProfile
from .export_support import _PERIOD, _schema_provider, _typed_producer_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

#: Posición 12, longitud 1 in every design above.
_POSITION = 12
_CONTINUATION = "C"
_PRINCIPAL = " "

#: (modelo, filing year, period, record id, field id) of every shipped page indicator.
_PAGE_INDICATORS = (
    ("131", 2026, "1T", "modelo-131-dpa", "modelo-131-dpa-complementaria-indicator"),
    ("131", 2026, "3T", "modelo-131-dpa", "modelo-131-dpa-complementaria-indicator"),
    ("232", 2025, "0A", "m232-operaciones-vinculadas", "m232-2018.dr23201.f005"),
    ("232", 2025, "0A", "m232-paraisos-fiscales", "m232-2018.dr23202.f005"),
    ("303", 2026, "1T", "m303-regimen-simplificado", "m303-2026.dp30302.f005"),
    ("303", 2026, "1T", "m303-prorrata-deducciones", "m303-2026.dp30305.f005"),
    ("303", 2025, "1T", "m303-regimen-simplificado", "m303-2025.dp30302.f005"),
    ("303", 2025, "1T", "m303-prorrata-deducciones", "m303-2025.dp30305.f005"),
    ("353", 2025, "01", "m353-declaracion", "m353-2021.pagina01.f005"),
    ("353", 2026, "02", "m353-declaracion", "m353-2026.pagina01.f005"),
    ("353", 2026, "02", "m353-domiciliacion-devolucion", "m353-2026.pagina02.f005"),
)


def _shipped(
    modelo: str, filing_year: int, period: str, record_id: str, field_id: str
) -> tuple[RegistrySnapshot, ExportLayoutDefinition, ExportRecordDefinition, ExportFieldDefinition]:
    snapshot = published_snapshot(modelo, filing_year=filing_year, period=period)
    for layout in snapshot.revision.export_layouts:
        for record in layout.records:
            if str(record.id) != record_id:
                continue
            for field in record.fields:
                if field.id == field_id:
                    return snapshot, layout, record, field
    raise AssertionError(f"{field_id} is no longer a shipped Modelo {modelo} page indicator on {record_id}")


@pytest.mark.parametrize(("modelo", "filing_year", "period", "record_id", "field_id"), _PAGE_INDICATORS)
def test_the_page_indicator_is_the_continuation_marker_at_its_design_position(
    modelo: str, filing_year: int, period: str, record_id: str, field_id: str
) -> None:
    _, _, _, field = _shipped(modelo, filing_year, period, record_id, field_id)

    assert (field.offset, field.length) == (_POSITION, 1)
    assert field.computed_key == "continuation_page_marker"
    assert field.required is False


@pytest.mark.parametrize(("modelo", "filing_year", "period", "record_id", "field_id"), _PAGE_INDICATORS)
@pytest.mark.parametrize(("occurrence", "expected"), [(1, _PRINCIPAL), (2, _CONTINUATION)], ids=("first", "next"))
def test_a_complementaria_writes_blank_on_its_first_page_and_c_on_a_further_one(
    modelo: str, filing_year: int, period: str, record_id: str, field_id: str, occurrence: int, expected: str
) -> None:
    snapshot, layout, record, field = _shipped(modelo, filing_year, period, record_id, field_id)
    context = FilingRecordRenderContext(registry_snapshot=snapshot, layout=layout, record=record, occurrence=occurrence)
    complementaria = _typed_producer_snapshot(complementaria=True)
    assert complementaria.amendment_evidence is not None
    assert complementaria.amendment_evidence.is_complementaria

    marker = continuation_page_marker(_approved_131_draft(("722",)), complementaria, context)

    assert format_field(field, marker) == expected


@pytest.mark.parametrize("illegal", ["CC", 1])
def test_a_value_the_one_byte_indicator_cannot_carry_is_refused(illegal: object) -> None:
    field: ExportFieldDefinition = _shipped(*_PAGE_INDICATORS[2])[3]

    with pytest.raises(FilingExportValidationError, match=field.id):
        format_field(field, illegal)


_M131_RENDIMIENTO_MODULOS = validated_casilla_id("03", surface="test_continuation_page_marker.casilla")
_M131_VOLUME_AGRARIO = validated_casilla_id("05", surface="test_continuation_page_marker.casilla")
_DPA_OPEN = b"<T131DPA00>"


def _approved_131_draft(epigrafes: tuple[str, ...]):
    return build_draft(
        modelo="131",
        period=_PERIOD,
        profile=ModeloOperatorProfile(tax_id="12345678Z", display_name="Export registry test"),
        inputs={
            _M131_RENDIMIENTO_MODULOS: Decimal("1000"),
            _M131_VOLUME_AGRARIO: Decimal("500"),
            "modelo-131.page1.actividad-1-epigrafe": epigrafes[0],
            "modelo-131.page1.actividad-1-rendimiento-neto": Decimal("1200.50"),
            "modelo-131.dpa.epigrafe-iae": list(epigrafes),
            "modelo-131.did.iban": "ES9121000418450200051332",
        },
        schema_provider=_schema_provider(filing_year=2026, period="1T", modelos=("131",)),
    ).model_copy(update={"status": ModeloDraftStatus.APROBADO})


def test_a_modelo_131_complementaria_export_marks_only_its_second_dpa_page(tmp_path: Path) -> None:
    complementaria = _typed_producer_snapshot(complementaria=True)
    snapshot = build_filing_producer_snapshot(
        modelo=Modelo("131"),
        taxpayer_tax_id=complementaria.taxpayer_tax_id,
        taxpayer_identity=complementaria.taxpayer_identity,
        presenter=complementaria.presenter,
        model_profile=GeneralFilingProfileFacts(),
        elections=complementaria.elections,
        amendment_evidence=complementaria.amendment_evidence,
        refund_account=None,
        charge_account=None,
        m303_filing_facts=None,
    )
    output_path = tmp_path / "modelo-131.txt"

    export_draft(
        _approved_131_draft(("722", "845")),
        output_path=output_path,
        producer_snapshot=snapshot,
        product_software_identity=development_mock_software_identity(),
        prior_domiciliation_election=PriorDomiciliationElection.KEEP,
        schema_provider=_schema_provider(filing_year=2026, period="1T", modelos=("131",)),
    )

    payload = output_path.read_bytes()
    starts = [index for index in range(len(payload)) if payload.startswith(_DPA_OPEN, index)]
    assert len(starts) == 2
    indicators = [payload[start + _POSITION - 1 : start + _POSITION].decode("ascii") for start in starts]
    assert indicators == [_PRINCIPAL, _CONTINUATION]
