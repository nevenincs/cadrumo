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
from ....domain.calculations.registry.export_parse import parse_export_payload
from ....domain.calculations.registry.schema import RegistrySnapshot
from ....domain.calculations.registry.schema_exports import ExportLayoutDefinition
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
    maquinas_tipo_b=1234567,
    superficies=(Modelo840SuperficieClase(clase=SuperficieRegla14Clase.SIN_REDUCCION, total=120, computable=114),),
    local_rows=tuple(Modelo840LocalRow(nombre_via=f"CALLE {index}", total=index * 10) for index in range(1, 10)),
)


@pytest.fixture(params=sorted(filing_year_envelope().years), ids=str)
def exercise(request: pytest.FixtureRequest) -> int:
    year = request.param
    assert isinstance(year, int)
    return year


def _producer_snapshot() -> FilingProducerSnapshot:
    return build_filing_producer_snapshot(
        modelo=Modelo(_MODELO),
        taxpayer_tax_id="12345678Z",
        taxpayer_identity=TaxpayerIdentityFacts(
            legal_name=None, given_name="Ana", surnames="Prueba", full_name="Ana Prueba"
        ),
        presenter=PresenterIdentity(tax_id="00000000T", full_name="Gestoría Prueba"),
        model_profile=_PROFILE,
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


def _render(exercise: int) -> tuple[RegistrySnapshot, ExportLayoutDefinition, dict[FilingProducerKey, object], bytes]:
    snapshot = published_snapshot(_MODELO, filing_year=exercise, period=_PERIOD)
    (layout,) = snapshot.revision.export_layouts
    producer_snapshot = _producer_snapshot()
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
