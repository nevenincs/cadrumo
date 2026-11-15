"""A Modelo 840 declaration renders to the DR840 records and reads back to its stored facts.

DR840 numbers each page's last two positions "Salto de línea. Constante CRLF": the
record is the design's fields followed by that line break, so every emitted line is
the design's length with CRLF as its final two bytes, and the registry parser reads
each field back from the same bytes.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from cadrumo.domain.calculations.registry.tests.published_authority import published_snapshot

from ....core.filing_producer_key import FilingProducerKey
from ....core.filing_projection_m840 import M840LocalField, M840LocalProjectionRef
from ....core.modelo import Modelo
from ....core.payment_election import PaymentElection
from ....core.period import Period
from ....core.prior_domiciliation_election import PriorDomiciliationElection
from ....core.refund_election import RefundElection
from ....core.result_disposition import ResultDisposition
from ....domain.calculations.registry.errors import FixedWidthValueOverflowError
from ....domain.calculations.registry.export_parse import parse_export_payload
from ....domain.calculations.registry.fixed_width_codec import render_fixed_width_export_field
from ....domain.calculations.registry.schema import RegistrySnapshot
from ....domain.calculations.registry.schema_exports import ExportFieldDefinition, ExportLayoutDefinition
from ....domain.calculations.registry.schema_references import RegistrySnapshotRef
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.contribuyente.iae_local_record import SuperficieRegla14Clase
from ....domain.filing.schema import ModeloDraft, registry_schema_version
from ....domain.submission.models import ModeloDraftStatus
from ..export import render_filing_layout
from ..export_producer import filing_producer_values
from ..producer_snapshot import (
    FilingElectionFacts,
    FilingProducerSnapshot,
    PresenterIdentity,
    TaxpayerIdentityFacts,
    build_filing_producer_snapshot,
)
from ..producer_snapshot_m840 import (
    Modelo840ElementoLinea,
    Modelo840LocalRow,
    Modelo840ProfileFacts,
    Modelo840SuperficieClase,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_MODELO = "840"
_PERIOD = "0A"
_CRLF = b"\r\n"

#: (page, DR840 position, length) of every page's "Salto de línea. Constante CRLF" row.
_DESIGN_LINE_BREAK = {
    "m840-pagina01": (1131, 2),
    "m840-pagina02": (1164, 2),
    "m840-anexo": (1066, 2),
}

_PROFILE = Modelo840ProfileFacts(
    delegacion_codigo="28",
    administracion_codigo="286",
    administracion_nombre="MADRID CENTRO",
    sujeto_pasivo_municipio="ALCALA DE HENARES",
    actividad_provincia_codigo="50",
    actividad_municipio="ZARAGOZA",
    local_indirecto_municipio="UTEBO",
    elementos=(Modelo840ElementoLinea(linea=1, codigo="OB", descripcion="OBREROS", numero=Decimal("3.00")),),
    maquinas_tipo_b=2,
    superficies=(Modelo840SuperficieClase(clase=SuperficieRegla14Clase.SIN_REDUCCION, total=120, computable=114),),
    local_rows=tuple(Modelo840LocalRow(nombre_via=f"CALLE {index}", total=index * 10) for index in range(1, 10)),
)


@pytest.fixture(params=sorted(filing_year_envelope().years), ids=str)
def exercise(request: pytest.FixtureRequest) -> int:
    year = request.param
    assert isinstance(year, int)
    return year


def _producer_snapshot(profile: Modelo840ProfileFacts = _PROFILE) -> FilingProducerSnapshot:
    return build_filing_producer_snapshot(
        modelo=Modelo(_MODELO),
        taxpayer_tax_id="12345678Z",
        taxpayer_identity=TaxpayerIdentityFacts(
            legal_name=None, given_name="Ana", surnames="Prueba", full_name="Ana Prueba"
        ),
        presenter=PresenterIdentity(tax_id="00000000T", full_name="Gestoría Prueba"),
        model_profile=profile,
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
    """A synthetic approved draft carrying no casilla: every value here is a stored profile fact.

    Modelo 840 is authored at applicability grade, so the filing draft builder refuses
    it; the layout renderer reads the profile facts through the producer snapshot.
    """
    stamped = datetime.now(UTC)
    return ModeloDraft(
        draft_id="m840-round-trip",
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


def _render(
    exercise: int, profile: Modelo840ProfileFacts = _PROFILE
) -> tuple[RegistrySnapshot, ExportLayoutDefinition, dict[FilingProducerKey, object], bytes]:
    snapshot = published_snapshot(_MODELO, filing_year=exercise, period=_PERIOD)
    (layout,) = snapshot.revision.export_layouts
    producer_snapshot = _producer_snapshot(profile)
    headers = filing_producer_values(producer_snapshot)
    payload = render_filing_layout(
        layout,
        registry_snapshot=snapshot,
        draft=_draft(snapshot, exercise),
        headers=headers,
        producer_snapshot=producer_snapshot,
        prior_domiciliation_election=PriorDomiciliationElection.KEEP,
        product_software_identity=None,
    )
    return snapshot, layout, headers, payload


def test_every_page_is_its_design_length_ending_in_the_designed_line_break(exercise: int) -> None:
    _snapshot, layout, _headers, payload = _render(exercise)
    records = {str(record.id): record for record in layout.records}

    lines = payload.split(_CRLF)
    assert lines[-1] == b""
    widths = [len(line) + len(_CRLF) for line in lines[:-1]]
    # Pages 1 and 2, then the one Anexo sheet that holds nine premises.
    record_order = ["m840-pagina01", "m840-pagina02", "m840-anexo"]
    assert widths == [sum(_DESIGN_LINE_BREAK[record_id]) - 1 for record_id in record_order]
    for record_id, (offset, length) in _DESIGN_LINE_BREAK.items():
        record = records[record_id]
        assert record.line_ending == "crlf"
        assert max((field.offset or 0) + (field.length or 0) for field in record.fields) == offset
        assert length == len(_CRLF)


def test_the_rendered_declaration_reads_back_to_its_stored_facts(exercise: int) -> None:
    snapshot, layout, headers, payload = _render(exercise)

    parsed = parse_export_payload(layout, payload, sources=snapshot.sources)

    producer_fields = {
        str(field.id): field.producer_key
        for record in layout.records
        for field in record.fields
        if field.producer_key is not None
    }
    read_back = {
        producer_fields[str(item.field_id)]: item.value
        for item in parsed.fields
        if str(item.field_id) in producer_fields
    }
    expected = {key: value for key, value in headers.items() if key in read_back and value is not None}
    assert expected
    for key, value in expected.items():
        assert read_back[key] == value, key
    sheets = [str(item.record_id) for item in parsed.fields if str(item.field_id).endswith(".f001")]
    assert sheets == ["m840-pagina01", "m840-pagina02", "m840-anexo"]

    slots = {
        str(field.id): field.projection_ref
        for record in layout.records
        for field in record.fields
        if isinstance(field.projection_ref, M840LocalProjectionRef)
    }
    premises = {
        (ref.slot, ref.field): item.value
        for item in parsed.fields
        if (ref := slots.get(str(item.field_id))) is not None
    }
    for slot, row in enumerate(_PROFILE.local_rows, start=1):
        assert premises[(slot, M840LocalField.NOMBRE_VIA)] == row.nombre_via
        assert premises[(slot, M840LocalField.TOTAL)] == row.total


def test_premises_beyond_one_sheet_open_a_second_anexo_sheet_that_reads_back_in_order(exercise: int) -> None:
    rows = tuple(Modelo840LocalRow(nombre_via=f"CALLE {index}", total=index) for index in range(1, 12))
    snapshot, layout, _headers, payload = _render(exercise, _PROFILE.model_copy(update={"local_rows": rows}))

    parsed = parse_export_payload(layout, payload, sources=snapshot.sources)

    sheets = [str(item.record_id) for item in parsed.fields if str(item.field_id).endswith(".f001")]
    assert sheets == ["m840-pagina01", "m840-pagina02", "m840-anexo", "m840-anexo"]
    names = {
        str(field.id)
        for record in layout.records
        for field in record.fields
        if isinstance(field.projection_ref, M840LocalProjectionRef)
        and field.projection_ref.field is M840LocalField.NOMBRE_VIA
    }
    read_names = [
        item.value
        for item in parsed.fields
        if str(item.field_id) in names and item.value is not None and item.value != ""
    ]
    assert read_names == [row.nombre_via for row in rows]


def _producer_field(layout: ExportLayoutDefinition, key: FilingProducerKey) -> ExportFieldDefinition:
    (field,) = (field for record in layout.records for field in record.fields if field.producer_key == key)
    return field


def _page_two(payload: bytes) -> bytes:
    (line,) = (line for line in payload.split(_CRLF) if line.startswith(b"<T840020>"))
    return line


def _slot(line: bytes, field: ExportFieldDefinition) -> bytes:
    assert field.offset is not None
    assert field.length is not None
    return line[field.offset - 1 : field.offset - 1 + field.length]


def test_a_short_apartado_vi_b_count_prints_right_aligned_and_reads_back(exercise: int) -> None:
    """DR840 types each Apartado VI B "Número" "Num" over 7 positions, so 2 machines is 0000002."""
    snapshot, layout, _headers, payload = _render(exercise)

    field = _producer_field(layout, FilingProducerKey.M840_ELEMENTOS_TRIBUTARIOS_MAQUINAS_TIPO_B_NUMERO)
    assert _slot(_page_two(payload), field) == b"0000002"
    parsed = parse_export_payload(layout, payload, sources=snapshot.sources)
    (value,) = (item.value for item in parsed.fields if item.field_id == field.id)
    assert value == Decimal(2)


def test_an_apartado_vi_b_count_wider_than_its_field_is_refused(exercise: int) -> None:
    _snapshot, layout, _headers, _payload = _render(exercise)

    field = _producer_field(layout, FilingProducerKey.M840_ELEMENTOS_TRIBUTARIOS_EXPOSITORES_AUTOVENTA_NUMERO)
    assert render_fixed_width_export_field(field, Decimal(9_999_999)) == "9999999"
    with pytest.raises(FixedWidthValueOverflowError):
        render_fixed_width_export_field(field, Decimal(10_000_000))


def test_absent_apartado_vi_quantities_print_the_numeric_fields_zero_fill(exercise: int) -> None:
    """DR840 states no fill of its own for an empty "Num" field, so the codec's zero fill applies."""
    _snapshot, layout, headers, payload = _render(exercise)
    line = _page_two(payload)

    absent = (
        FilingProducerKey.M840_ELEMENTOS_TRIBUTARIOS_GRUPO_A2_NUMERO,
        FilingProducerKey.M840_ELEMENTOS_TRIBUTARIOS_MAQUINAS_TIPO_A_NUMERO,
        FilingProducerKey.M840_ELEMENTOS_TRIBUTARIOS_LOCAL_C0_1_RECTIFICADA,
    )
    for key in absent:
        assert headers[key] is None
        field = _producer_field(layout, key)
        assert field.absent_fill is None
        assert _slot(line, field) == b"0" * (field.length or 0), key


def test_a_declaration_without_premises_has_no_anexo_sheet_and_reads_back(exercise: int) -> None:
    """DR840 prints the Anexo as the relación de locales; without premises there is no sheet."""
    snapshot, layout, headers, payload = _render(exercise, _PROFILE.model_copy(update={"local_rows": ()}))
    (anexo,) = (record for record in layout.records if str(record.id) == "m840-anexo")
    assert not anexo.required

    parsed = parse_export_payload(layout, payload, sources=snapshot.sources)

    sheets = [str(item.record_id) for item in parsed.fields if str(item.field_id).endswith(".f001")]
    assert sheets == ["m840-pagina01", "m840-pagina02"]
    field = _producer_field(layout, FilingProducerKey.M840_ELEMENTOS_TRIBUTARIOS_MAQUINAS_TIPO_B_NUMERO)
    (value,) = (item.value for item in parsed.fields if item.field_id == field.id)
    assert value == headers[FilingProducerKey.M840_ELEMENTOS_TRIBUTARIOS_MAQUINAS_TIPO_B_NUMERO]
