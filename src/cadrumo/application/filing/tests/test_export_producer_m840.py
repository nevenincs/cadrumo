"""Modelo 840's pages print the stored facts at the positions DR840 gives them.

The producer values come from the real resolver over a synthetic profile, and each value is
rendered by the real field codec of the published layout and read back at the position
transcribed from DR840 (Orden HAC/2572/2003). An unstated fact reaches the codec as an
absent value, never as a zero, and prints the slot's declared absent fill: spaces on an
alphanumeric slot, the codec's zero fill on a numeric one.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from cadrumo.domain.calculations.registry.tests.published_authority import published_snapshot

from ....core.filing_producer_key import FilingProducerKey
from ....core.modelo import Modelo
from ....core.payment_election import PaymentElection
from ....core.prior_domiciliation_election import PriorDomiciliationElection
from ....core.refund_election import RefundElection
from ....core.result_disposition import ResultDisposition
from ....domain.calculations.registry.export_parse import parse_field_value
from ....domain.calculations.registry.fixed_width_codec import render_empty_block_slot
from ....domain.calculations.registry.schema_exports import ExportRecordDefinition
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.contribuyente.iae_local_record import SuperficieRegla14Clase
from ..export_producer import filing_producer_values
from ..export_producer_m840 import M840_PRODUCER_KEYS, m840_producer_values
from ..producer_snapshot import (
    FilingElectionFacts,
    GeneralFilingProfileFacts,
    PresenterIdentity,
    TaxpayerIdentityFacts,
    build_filing_producer_snapshot,
)
from ..producer_snapshot_m840 import Modelo840ElementoLinea, Modelo840ProfileFacts, Modelo840SuperficieClase
from ..record_field_renderer import format_field, header_field_value

pytestmark = [pytest.mark.integration, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_MODELO = "840"
_PERIOD = "0A"

_PROFILE = Modelo840ProfileFacts(
    delegacion_codigo="28",
    administracion_codigo="286",
    administracion_nombre="MADRID CENTRO",
    sujeto_pasivo_municipio="ALCALA DE HENARES",
    actividad_provincia_codigo="50",
    actividad_municipio="ZARAGOZA",
    local_indirecto_municipio="UTEBO",
    elementos=(
        Modelo840ElementoLinea(linea=1, codigo="OB", descripcion="OBREROS", numero=Decimal("3.00")),
        Modelo840ElementoLinea(linea=3, codigo="KW", numero=Decimal("12.50")),
    ),
    maquinas_tipo_b=1234567,
    superficies=(
        Modelo840SuperficieClase(clase=SuperficieRegla14Clase.SIN_REDUCCION, total=120, computable=114),
        Modelo840SuperficieClase(clase=SuperficieRegla14Clase.ALMACEN, total=40, rectificada=22, computable=21),
    ),
)

#: (record, DR840 position, length) -> the rendered text, transcribed from the design and the profile above.
_EXPECTED_WIRE: dict[tuple[str, int, int], str] = {
    ("m840-pagina01", 11, 2): "28",
    ("m840-pagina01", 13, 23): "286MADRID CENTRO".ljust(23),
    ("m840-pagina01", 220, 30): "ALCALA DE HENARES".ljust(30),
    ("m840-pagina01", 531, 2): "50",
    ("m840-pagina01", 588, 30): "ZARAGOZA".ljust(30),
    ("m840-pagina01", 1025, 30): "UTEBO".ljust(30),
    ("m840-pagina02", 24, 32): "OBOBREROS".ljust(32),
    ("m840-pagina02", 56, 9): "000000300",
    ("m840-pagina02", 91, 32): " " * 32,
    ("m840-pagina02", 123, 9): "0" * 9,
    ("m840-pagina02", 158, 32): "KW".ljust(32),
    ("m840-pagina02", 190, 9): "000001250",
    ("m840-pagina02", 573, 7): "0" * 7,
    ("m840-pagina02", 606, 7): "1234567",
    ("m840-pagina02", 685, 5): "00120",
    ("m840-pagina02", 690, 5): "0" * 5,
    ("m840-pagina02", 695, 5): "00114",
    ("m840-pagina02", 700, 5): "0" * 5,
    ("m840-pagina02", 820, 5): "00040",
    ("m840-pagina02", 825, 5): "00022",
    ("m840-pagina02", 830, 5): "00021",
}


@pytest.fixture(params=sorted(filing_year_envelope().years), ids=str)
def exercise(request: pytest.FixtureRequest) -> int:
    year = request.param
    assert isinstance(year, int)
    return year


def _headers(profile: Modelo840ProfileFacts) -> dict[FilingProducerKey, object]:
    snapshot = build_filing_producer_snapshot(
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
    return filing_producer_values(snapshot)


def _pages(exercise: int) -> dict[str, ExportRecordDefinition]:
    snapshot = published_snapshot(_MODELO, filing_year=exercise, period=_PERIOD)
    (layout,) = snapshot.revision.export_layouts
    return {str(record.id): record for record in layout.records}


def _wire(record: ExportRecordDefinition, headers: dict[FilingProducerKey, object], offset: int) -> str:
    (field,) = (field for field in record.fields if field.offset == offset)
    assert field.producer_key is not None, f"DR840 position {offset} is not a producer field"
    return format_field(field, header_field_value(field, headers), record=record)


def test_the_resolver_owns_exactly_the_modelo_840_namespace() -> None:
    assert {key.value for key in M840_PRODUCER_KEYS} == {
        key.value for key in FilingProducerKey if key.value.startswith("m840.")
    }


def test_every_page_position_prints_its_stored_fact(exercise: int) -> None:
    pages = _pages(exercise)
    headers = _headers(_PROFILE)

    wire = {
        (record_id, offset, length): _wire(pages[record_id], headers, offset)
        for record_id, offset, length in _EXPECTED_WIRE
    }

    assert wire == _EXPECTED_WIRE


def test_a_surface_figure_reads_back_as_the_stored_square_metres(exercise: int) -> None:
    record = _pages(exercise)["m840-pagina02"]
    headers = _headers(_PROFILE)
    (field,) = (field for field in record.fields if field.offset == 820)

    assert parse_field_value(field, _wire(record, headers, 820)) == 40


def test_an_empty_profile_hands_every_producer_field_an_absent_value(exercise: int) -> None:
    headers = _headers(Modelo840ProfileFacts())

    assert {headers[key] for key in M840_PRODUCER_KEYS} == {None}
    for record in _pages(exercise).values():
        for field in record.fields:
            if field.producer_key is not None:
                assert _wire(record, headers, field.offset or 0) == render_empty_block_slot(field), field.id


def test_a_machine_count_is_its_whole_number() -> None:
    values = m840_producer_values(Modelo840ProfileFacts(maquinas_tipo_a=0, expositores_autoventa=12))

    assert values[FilingProducerKey.M840_ELEMENTOS_TRIBUTARIOS_MAQUINAS_TIPO_A_NUMERO] == Decimal(0)
    assert values[FilingProducerKey.M840_ELEMENTOS_TRIBUTARIOS_EXPOSITORES_AUTOVENTA_NUMERO] == Decimal(12)
    assert values[FilingProducerKey.M840_ELEMENTOS_TRIBUTARIOS_MAQUINAS_TIPO_B_NUMERO] is None


def test_an_administracion_without_its_code_prints_nothing() -> None:
    values = m840_producer_values(Modelo840ProfileFacts(administracion_nombre="MADRID CENTRO"))

    assert values[FilingProducerKey.M840_ADMINISTRACION_CODIGO] is None


def test_another_modelos_profile_resolves_every_key_absent() -> None:
    assert set(m840_producer_values(GeneralFilingProfileFacts()).values()) == {None}
