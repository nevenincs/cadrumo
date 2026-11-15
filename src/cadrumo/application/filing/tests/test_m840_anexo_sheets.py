"""Modelo 840's Anexo is a run of sheets, each holding nine premises slots.

The DR840 Anexo record prints the Apartado II "Relación de locales" nine times, its
position 10 reads "Blanco (no compl.) ó "C" (Compl.)", the form numbers each Anexo
"Hoja", and every sheet closes with its own partial sums. So a tenth premises opens a
further sheet: the record repeats per sheet, slot ``k`` of a sheet prints the premises
it carries, and the sheet's occurrence decides the marker.

The slot positions are read from the bundled design text itself, not restated here,
and the bytes are rendered by the real record renderer and read back by the real
field parser.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.tests.published_authority import published_snapshot

from ....core.filing_projection_m840 import (
    M840AnexoHojaField,
    M840AnexoHojaProjectionRef,
    M840LocalField,
    M840LocalProjectionRef,
)
from ....core.filing_projection_ref import FilingProjectionRef
from ....core.modelo import Modelo
from ....core.payment_election import PaymentElection
from ....core.period import Period
from ....core.prior_domiciliation_election import PriorDomiciliationElection
from ....core.refund_election import RefundElection
from ....core.result_disposition import ResultDisposition
from ....domain.calculations.registry.export_parse import parse_field_value
from ....domain.calculations.registry.schema import RegistrySnapshot
from ....domain.calculations.registry.schema_exports import ExportLayoutDefinition, ExportRecordDefinition
from ....domain.calculations.registry.schema_references import RegistrySnapshotRef
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.filing.schema import ModeloDraft, registry_schema_version
from ....domain.submission.models import ModeloDraftStatus
from ..m840_projection import build_m840_filing_projection_plan
from ..producer_snapshot import (
    FilingElectionFacts,
    FilingProducerSnapshot,
    PresenterIdentity,
    TaxpayerIdentityFacts,
    build_filing_producer_snapshot,
)
from ..producer_snapshot_m840 import Modelo840LocalRow, Modelo840ProfileFacts
from ..projection import FilingRecordRenderContext
from ..record_field_renderer import continuation_page_marker, format_field, projection_field_value
from ..record_types import ProjectionAddress

pytestmark = [pytest.mark.integration, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_MODELO = "840"
_PERIOD = "0A"
_ANEXO = "m840-anexo"
_DESIGN = (
    Path(__file__).resolve().parents[3]
    / "_data/corpus/aeat_official/disenos_registro/modelo_840/files/01-840-orden-hac-2572-2003-99-kb-pdf.pdf.extracted.md"
)

#: The design's own Apartado II labels, in the order one slot prints them.
_LABELS: dict[str, M840LocalField] = {
    "SG Tabla": M840LocalField.SG_TABLA,
    "Nombre de la vía pública": M840LocalField.NOMBRE_VIA,
    "Núm.": M840LocalField.NUMERO,
    "Km.": M840LocalField.KM,
    "Esc.": M840LocalField.ESCALERA,
    "Piso": M840LocalField.PISO,
    "Pta.": M840LocalField.PUERTA,
    "Cód. Postal": M840LocalField.CODIGO_POSTAL,
    "Provincia Tabla": M840LocalField.PROVINCIA_CODIGO,
    "Municipio Tabla": M840LocalField.MUNICIPIO_CODIGO,
    "Municipio": M840LocalField.MUNICIPIO_NOMBRE,
    "Total": M840LocalField.TOTAL,
    "Rectificada": M840LocalField.RECTIFICADA,
    "Computable": M840LocalField.COMPUTABLE,
}
_SUMS: dict[str, M840AnexoHojaField] = {
    "Total": M840AnexoHojaField.SUMA_PARCIAL_TOTAL,
    "Rectificada": M840AnexoHojaField.SUMA_PARCIAL_RECTIFICADA,
    "Computable": M840AnexoHojaField.SUMA_PARCIAL_COMPUTABLE,
}
_ROW = re.compile(r"^\d+ (?P<offset>\d+) (?P<length>\d+) (?:An|Num) (?P<text>.+)$")


def _design_positions() -> dict[FilingProjectionRef, tuple[int, int]]:
    """Read every Apartado II slot and partial sum position from the DR840 Anexo text."""
    text = _DESIGN.read_text(encoding="utf-8")
    anexo = text[text.index('"<T840030>"') :]
    positions: dict[FilingProjectionRef, tuple[int, int]] = {}
    seen: dict[M840LocalField, int] = {}
    for line in anexo.splitlines():
        row = _ROW.match(line.strip())
        if row is None or row["text"].startswith("Reservado"):
            continue
        offset, length, label = int(row["offset"]), int(row["length"]), row["text"]
        if (sum_label := label.removeprefix("Apartado II: Relación de locales. Suma parcial ")) != label:
            name = sum_label.removeprefix("del ").removeprefix("de ").split(" [")[0]
            ref = M840AnexoHojaProjectionRef(projection_kind="m840_anexo_hoja", field=_SUMS[name])
            positions[ref] = (offset, length)
        elif (slot_label := label.removeprefix("Apartado II: Relación de locales. ")) != label:
            field = _LABELS[slot_label]
            seen[field] = seen.get(field, 0) + 1
            positions[M840LocalProjectionRef(projection_kind="m840_local", slot=seen[field], field=field)] = (
                offset,
                length,
            )
    return positions


def _snapshot(exercise: int) -> tuple[RegistrySnapshot, ExportLayoutDefinition, ExportRecordDefinition]:
    snapshot = published_snapshot(_MODELO, filing_year=exercise, period=_PERIOD)
    (layout,) = snapshot.revision.export_layouts
    (record,) = (record for record in layout.records if str(record.id) == _ANEXO)
    return snapshot, layout, record


#: One open-ended edition governs every supported year, so each is proven.
@pytest.fixture(params=sorted(filing_year_envelope().years), ids=str)
def exercise(request: pytest.FixtureRequest) -> int:
    year = request.param
    assert isinstance(year, int)
    return year


def test_the_anexo_repeats_per_sheet_and_reads_no_declaration_header(exercise: int) -> None:
    _snapshot_value, _layout, record = _snapshot(exercise)

    assert record.repeat == "projection_rows"
    assert [str(field.id) for field in record.fields if field.producer_key is not None] == []
    (marker,) = (field for field in record.fields if field.offset == 10)
    assert marker.computed_key == "continuation_page_marker"


def test_every_slot_and_partial_sum_sits_where_the_design_prints_it(exercise: int) -> None:
    _snapshot_value, _layout, record = _snapshot(exercise)
    design = _design_positions()

    shipped = {
        field.projection_ref: (field.offset, field.length)
        for field in record.fields
        if field.projection_ref is not None
    }

    assert len(design) == 9 * len(M840LocalField) + len(M840AnexoHojaField)
    assert shipped == design


def _producer_snapshot(rows: tuple[Modelo840LocalRow, ...] = ()) -> FilingProducerSnapshot:
    return build_filing_producer_snapshot(
        modelo=Modelo(_MODELO),
        taxpayer_tax_id="12345678Z",
        taxpayer_identity=TaxpayerIdentityFacts(
            legal_name=None, given_name="Ana", surnames="Prueba", full_name="Ana Prueba"
        ),
        presenter=PresenterIdentity(tax_id="00000000T", full_name="Gestoría Prueba"),
        model_profile=Modelo840ProfileFacts(local_rows=rows),
        elections=FilingElectionFacts(
            result_disposition=ResultDisposition.NEGATIVA,
            payment=PaymentElection.INGRESO,
            refund=RefundElection.COMPENSAR,
            prior_domiciliation=PriorDomiciliationElection.KEEP,
        ),
        amendment_evidence=None,
        refund_account=None,
        charge_account=None,
        m303_filing_facts=None,
    )


def _draft(snapshot: RegistrySnapshot, exercise: int) -> ModeloDraft:
    """A synthetic approved draft: the Anexo reads no casilla, so the draft carries no value.

    Modelo 840 is authored at applicability grade, so the filing draft builder refuses
    it; the record renderer under test reads nothing from the draft for these fields.
    """
    stamped = datetime.now(UTC)
    return ModeloDraft(
        draft_id="m840-anexo-sheets",
        modelo=_MODELO,
        period=Period.from_year_and_code(exercise, _PERIOD),
        profile_tax_id="12345678Z",
        subject_tax_id="12345678Z",
        snapshot_ref=RegistrySnapshotRef(
            modelo=_MODELO, revision_id=snapshot.revision.id, modelo_year=exercise, period=_PERIOD
        ),
        status=ModeloDraftStatus.APROBADO,
        values=(),
        created_at=stamped,
        updated_at=stamped,
        schema_version=registry_schema_version(modelo=_MODELO, revision_id=snapshot.revision.id),
    )


def _local(slot: int, field: M840LocalField) -> M840LocalProjectionRef:
    return M840LocalProjectionRef(projection_kind="m840_local", slot=slot, field=field)


def _render_sheet(
    record: ExportRecordDefinition,
    layout: ExportLayoutDefinition,
    snapshot: RegistrySnapshot,
    draft: ModeloDraft,
    occurrence: int,
    values: Mapping[ProjectionAddress, object],
) -> str:
    """Render one Anexo sheet's marker and projected fields at their declared positions.

    The record's literal envelope is left out: the whole record, its closing line break
    included, is proven by the Modelo 840 export round trip.
    """
    context = FilingRecordRenderContext(registry_snapshot=snapshot, layout=layout, record=record, occurrence=occurrence)
    sheet = [" "] * max((field.offset or 0) + (field.length or 0) for field in record.fields)
    for field in record.fields:
        if field.projection_ref is not None:
            value = projection_field_value(field, context, values)
        elif field.computed_key is not None:
            value = continuation_page_marker(draft, _producer_snapshot(), context)
        else:
            continue
        offset = field.offset or 0
        sheet[offset - 1 : offset - 1 + (field.length or 0)] = format_field(field, value, record=record)
    return "".join(sheet)


def test_a_second_sheet_is_marked_c_and_carries_only_its_own_premises(exercise: int) -> None:
    snapshot, layout, record = _snapshot(exercise)
    draft = _draft(snapshot, exercise)
    first_sheet_last = _local(9, M840LocalField.MUNICIPIO_NOMBRE)
    second_sheet_first = _local(1, M840LocalField.NOMBRE_VIA)
    surface = _local(1, M840LocalField.TOTAL)
    partial = M840AnexoHojaProjectionRef(projection_kind="m840_anexo_hoja", field=M840AnexoHojaField.SUMA_PARCIAL_TOTAL)
    values: dict[ProjectionAddress, object] = {
        (record.id, 1, first_sheet_last): "ZARAGOZA",
        (record.id, 2, second_sheet_first): "CALLE MAYOR",
        (record.id, 2, surface): Decimal(120),
        (record.id, 2, partial): Decimal(120),
    }
    for field in record.fields:
        if field.projection_ref is not None:
            for occurrence in (1, 2):
                values.setdefault((record.id, occurrence, field.projection_ref), None)

    sheets = {occurrence: _render_sheet(record, layout, snapshot, draft, occurrence, values) for occurrence in (1, 2)}

    design = _design_positions()

    def wire(occurrence: int, ref: FilingProjectionRef) -> str:
        offset, length = design[ref]
        return sheets[occurrence][offset - 1 : offset - 1 + length]

    assert sheets[1][9] == " "
    assert sheets[2][9] == "C"
    assert wire(1, first_sheet_last).rstrip() == "ZARAGOZA"
    assert wire(2, first_sheet_last).strip() == ""
    assert wire(2, second_sheet_first).rstrip() == "CALLE MAYOR"
    assert wire(1, second_sheet_first).strip() == ""
    (total_field,) = (field for field in record.fields if field.projection_ref == surface)
    assert parse_field_value(total_field, wire(2, surface)) == 120
    (partial_field,) = (field for field in record.fields if field.projection_ref == partial)
    assert parse_field_value(partial_field, wire(2, partial)) == 120


def _premises(count: int) -> tuple[Modelo840LocalRow, ...]:
    return tuple(
        Modelo840LocalRow(nombre_via=f"CALLE {index}", total=index * 10, computable=None if index % 2 else index)
        for index in range(1, count + 1)
    )


@pytest.mark.parametrize(("premises", "sheets"), [(0, 0), (1, 1), (9, 1), (10, 2), (19, 3)])
def test_the_premises_fill_as_many_sheets_as_they_need(exercise: int, premises: int, sheets: int) -> None:
    snapshot, layout, record = _snapshot(exercise)
    rows = _premises(premises)

    plan = build_m840_filing_projection_plan(
        registry_snapshot=snapshot, layout=layout, producer_snapshot=_producer_snapshot(rows)
    )

    assert [context.occurrence for context in plan.contexts] == list(range(1, sheets + 1))
    assert all(context.record.id == record.id for context in plan.contexts)
    by_address = {(value.occurrence, value.projection_ref): value.value for value in plan.values}
    for index, row in enumerate(rows):
        occurrence, slot = divmod(index, 9)
        assert by_address[(occurrence + 1, _local(slot + 1, M840LocalField.NOMBRE_VIA))] == row.nombre_via
        assert by_address[(occurrence + 1, _local(slot + 1, M840LocalField.TOTAL))] == Decimal(row.total or 0)
    if sheets:
        last = rows[(sheets - 1) * 9 :]
        assert by_address[(sheets, _local(9, M840LocalField.NOMBRE_VIA))] == (
            rows[-1].nombre_via if len(last) == 9 else None
        )


def test_each_sheet_sums_only_its_own_stated_surfaces(exercise: int) -> None:
    snapshot, layout, _record = _snapshot(exercise)
    rows = _premises(10)

    plan = build_m840_filing_projection_plan(
        registry_snapshot=snapshot, layout=layout, producer_snapshot=_producer_snapshot(rows)
    )

    sums = {
        (value.occurrence, value.projection_ref.field): value.value
        for value in plan.values
        if isinstance(value.projection_ref, M840AnexoHojaProjectionRef)
    }
    assert sums[(1, M840AnexoHojaField.SUMA_PARCIAL_TOTAL)] == Decimal(sum(index * 10 for index in range(1, 10)))
    assert sums[(2, M840AnexoHojaField.SUMA_PARCIAL_TOTAL)] == Decimal(100)
    assert sums[(1, M840AnexoHojaField.SUMA_PARCIAL_COMPUTABLE)] == Decimal(2 + 4 + 6 + 8)
    assert sums[(2, M840AnexoHojaField.SUMA_PARCIAL_COMPUTABLE)] == Decimal(10)
    assert sums[(1, M840AnexoHojaField.SUMA_PARCIAL_RECTIFICADA)] is None
