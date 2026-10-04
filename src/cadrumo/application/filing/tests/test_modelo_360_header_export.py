"""Modelo 360's página 1 header renders from typed producer facts at DR360's own positions.

The published layout cites seventy ``m360.*`` producer keys -- the solicitud header, the
solicitante, the representante and the account holder. The published página 1 record is
rendered here by the real record renderer, from a draft built by the real draft builder and
producer values resolved by ``filing_producer_values``, and read back at the position and
width the record design prints. Página 2, the operations page, is built from casillas rather
than producer facts and is not rendered here.

The oracle is ``_DR360_PAGINA_1`` below, transcribed campo by campo from DR360 página 1
(``aeat-dr-360-2010``), never read from the layout under test, and the expected bytes are
written out by hand: alphanumeric left-aligned and space-filled, the numeric identifiers at
their full digit width.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....core.casilla_id import CasillaId
from ....core.modelo import Modelo
from ....core.payment_election import PaymentElection
from ....core.period import Period
from ....core.prior_domiciliation_election import PriorDomiciliationElection
from ....core.refund_election import RefundElection
from ....core.result_disposition import ResultDisposition
from ....domain.deadlines.models import RefundAccount
from ....domain.filing.protocols import ModeloInputValue
from ....domain.submission.models import ModeloDraftStatus
from ..draft_construction import build_draft
from ..export_producer import filing_producer_values
from ..producer_snapshot import (
    FilingElectionFacts,
    FilingProducerSnapshot,
    FilingProducerSnapshotError,
    GeneralFilingProfileFacts,
    PresenterIdentity,
    TaxpayerIdentityFacts,
    build_filing_producer_snapshot,
)
from ..producer_snapshot_m360 import (
    M360AmbitoEstablecimiento,
    M360CausaPresentacion,
    M360DelegacionCanariasCeutaMelilla,
    M360HaciendaForal,
    M360NivelCalidadDatos,
    M360TitularEnCalidadDe,
    Modelo360ApartadoCorreos,
    Modelo360CuentaTitularFacts,
    Modelo360DireccionExtranjero,
    Modelo360DomicilioEspana,
    Modelo360EstablecimientoFacts,
    Modelo360ProfileFacts,
    Modelo360RepresentanteFacts,
    Modelo360SolicitanteFacts,
    Modelo360SolicitudFacts,
)
from ..projection import FilingRecordRenderContext
from ..record_field_renderer import render_record
from ..record_renderer import record_render_rows
from ..runtime import ModeloOperatorProfile
from .export_support import _schema_provider

pytestmark = [pytest.mark.integration, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_YEAR = 2025
_PERIOD_CODE = "AD-HOC"
_TAX_ID = "12345678Z"
_REPRESENTANTE_TAX_ID = "00000000T"
#: DR360 página 1, "TOTAL 3400 Posiciones".
_PAGINA_1_LENGTH = 3400

#: DR360 página 1 (aeat-dr-360-2010): campo -> (posición, longitud), as printed.
_DR360_PAGINA_1: dict[int, tuple[int, int]] = {
    4: (17, 1),
    5: (18, 1),
    6: (19, 2),
    8: (25, 1),
    9: (26, 1),
    10: (27, 16),
    12: (60, 9),
    13: (69, 125),
    14: (194, 100),
    15: (294, 15),
    16: (309, 5),
    17: (314, 50),
    18: (364, 3),
    19: (367, 5),
    20: (372, 3),
    21: (375, 3),
    22: (378, 3),
    23: (381, 3),
    24: (384, 3),
    25: (387, 3),
    26: (390, 40),
    27: (430, 30),
    28: (460, 5),
    29: (465, 30),
    30: (495, 2),
    31: (497, 148),
    32: (645, 30),
    33: (675, 10),
    34: (685, 30),
    35: (715, 2),
    36: (717, 10),
    37: (727, 30),
    38: (757, 5),
    39: (762, 30),
    40: (792, 2),
    41: (794, 1),
    42: (795, 2),
    43: (797, 2),
    74: (1119, 9),
    75: (1128, 125),
    76: (1253, 100),
    77: (1353, 15),
    78: (1368, 5),
    79: (1373, 50),
    80: (1423, 3),
    81: (1426, 5),
    82: (1431, 3),
    83: (1434, 3),
    84: (1437, 3),
    85: (1440, 3),
    86: (1443, 3),
    87: (1446, 3),
    88: (1449, 40),
    89: (1489, 30),
    90: (1519, 5),
    91: (1524, 30),
    92: (1554, 2),
    93: (1556, 148),
    94: (1704, 30),
    95: (1734, 10),
    96: (1744, 30),
    97: (1774, 2),
    98: (1776, 10),
    99: (1786, 30),
    100: (1816, 5),
    101: (1821, 30),
    102: (1851, 2),
    113: (1912, 25),
    114: (1937, 1),
    115: (1938, 34),
    116: (1972, 11),
    117: (1983, 3),
}


def _campo(pagina_1: str, campo: int) -> str:
    position, length = _DR360_PAGINA_1[campo]
    return pagina_1[position - 1 : position - 1 + length]


def _an(value: str, length: int) -> str:
    """An alphanumeric DR360 value: left-aligned, filled with spaces."""
    return value + " " * (length - len(value))


def _blank(campo: int) -> str:
    return " " * _DR360_PAGINA_1[campo][1]


def _pagina_1(snapshot: FilingProducerSnapshot) -> str:
    """Render the published página 1 record for ``snapshot`` and return its 3400 characters."""
    provider = _schema_provider(filing_year=_YEAR, period=_PERIOD_CODE, modelos=("360",))
    registry_snapshot = provider.get_snapshot("360")
    (layout,) = registry_snapshot.revision.export_layouts
    (record,) = (record for record in layout.records if str(record.id) == "m360-solicitud")
    inputs: dict[str, ModeloInputValue] = {
        "decl.ejercicio": str(_YEAR),
        "decl.estado-miembro": "EL",
        "devolucion.importe-solicitado": Decimal("38.00"),
        "devolucion.divisa": "EUR",
    }
    draft = build_draft(
        modelo="360",
        period=Period.from_year_and_code(_YEAR, _PERIOD_CODE),
        profile=ModeloOperatorProfile(tax_id=_TAX_ID, display_name="SOLICITANTE PRUEBA"),
        inputs=inputs,
        schema_provider=provider,
    ).model_copy(update={"status": ModeloDraftStatus.APROBADO})
    casilla_values: dict[CasillaId, object] = {value.casilla_id: value.value for value in draft.values}
    (row,) = record_render_rows(record, {}, casilla_values)
    pagina_1 = render_record(
        record,
        draft=draft,
        producer_values=filing_producer_values(snapshot),
        producer_snapshot=snapshot,
        casilla_values=casilla_values,
        binding_values={},
        row=row,
        render_context=FilingRecordRenderContext(
            registry_snapshot=registry_snapshot,
            layout=layout,
            record=record,
            occurrence=1,
        ),
        projection_values={},
    )
    assert len(pagina_1.encode(record.encoding)) == _PAGINA_1_LENGTH
    assert pagina_1.startswith("<T360010>")
    assert pagina_1.endswith("</T360010>")
    return pagina_1


def _refund_account(*, swift_bic: str = "CAIXESBBXXX") -> RefundAccount:
    return RefundAccount(iban="ES9121000418450200051332", swift_bic=swift_bic)


def _snapshot(
    profile: Modelo360ProfileFacts | GeneralFilingProfileFacts,
    *,
    identity: TaxpayerIdentityFacts | None = None,
    refund_account: RefundAccount | None = None,
    disposition: ResultDisposition = ResultDisposition.DEVOLUCION,
) -> FilingProducerSnapshot:
    return build_filing_producer_snapshot(
        modelo=Modelo("360"),
        taxpayer_tax_id=_TAX_ID,
        taxpayer_identity=identity
        or TaxpayerIdentityFacts(legal_name=None, given_name="Ana", surnames="Prueba Ejemplo", full_name=None),
        presenter=PresenterIdentity(tax_id=_REPRESENTANTE_TAX_ID, full_name="Gestoria Prueba"),
        model_profile=profile,
        elections=FilingElectionFacts(
            result_disposition=disposition,
            payment=PaymentElection.INGRESO,
            refund=RefundElection.DEVOLVER,
            prior_domiciliation=PriorDomiciliationElection.KEEP,
        ),
        amendment_evidence=None,
        refund_account=refund_account if refund_account is not None else _refund_account(),
        charge_account=None,
        m303_filing_facts=None,
    )


def _domicilio(nombre_via: str) -> Modelo360DomicilioEspana:
    return Modelo360DomicilioEspana(
        tipo_via="CALLE",
        nombre_via=nombre_via,
        tipo_numeracion="NUM",
        numero_casa="00012",
        calificador_numero="BIS",
        bloque="B1",
        portal="P2",
        escalera="E3",
        planta="04",
        puerta="IZ",
        datos_complementarios="POLIGONO INDUSTRIAL",
        localidad="BARRIO ALTO",
        codigo_postal="31001",
        nombre_municipio="PAMPLONA",
        provincia="31",
    )


def _apartado(numero: str) -> Modelo360ApartadoCorreos:
    return Modelo360ApartadoCorreos(
        numero=numero,
        localidad="CENTRO",
        codigo_postal="31002",
        nombre_municipio="PAMPLONA",
        provincia="31",
    )


def _full_profile() -> Modelo360ProfileFacts:
    return Modelo360ProfileFacts(
        solicitud=Modelo360SolicitudFacts(
            nivel_calidad_datos=M360NivelCalidadDatos.MAXIMA,
            pais_destino="EL",
            causa_presentacion=M360CausaPresentacion.MODIFICACION,
            numero_registro_declaracion_anterior="3600000000001ABC",
            comunicacion_prorrata_definitiva=True,
            presentacion_en_pruebas=False,
        ),
        solicitante=Modelo360SolicitanteFacts(
            email="solicitante@example.es",
            phone="948000000",
            establecimiento=Modelo360EstablecimientoFacts(
                ambito=M360AmbitoEstablecimiento.HACIENDA_FORAL,
                hacienda_foral=M360HaciendaForal.NAVARRA,
            ),
            domicilio=_domicilio("MAYOR"),
            apartado_correos=_apartado("0000001234"),
        ),
        representante=Modelo360RepresentanteFacts(
            tax_id=_REPRESENTANTE_TAX_ID,
            full_name="ASESORES PRUEBA SL",
            email="representante@example.es",
            phone="+33100000000",
            domicilio=_domicilio("NUEVA"),
            foreign_address=Modelo360DireccionExtranjero(
                street="1 RUE DE PRUEBA",
                city="PARIS",
                postal_code="75001",
                region="ILE DE FRANCE",
                country_code="FR",
            ),
            apartado_correos=_apartado("0000005678"),
        ),
        cuenta=Modelo360CuentaTitularFacts(
            titular_nombre="ASESORES PRUEBA SL",
            titular_en_calidad_de=M360TitularEnCalidadDe.REPRESENTANTE,
            divisa="EUR",
        ),
    )


def _minimal_profile() -> Modelo360ProfileFacts:
    return Modelo360ProfileFacts(
        solicitud=Modelo360SolicitudFacts(
            nivel_calidad_datos=M360NivelCalidadDatos.MEDIA,
            pais_destino="DE",
            causa_presentacion=M360CausaPresentacion.INICIAL,
        ),
        solicitante=Modelo360SolicitanteFacts(
            email="solicitante@example.es",
            establecimiento=Modelo360EstablecimientoFacts(ambito=M360AmbitoEstablecimiento.TERRITORIO_COMUN),
        ),
        cuenta=Modelo360CuentaTitularFacts(
            titular_nombre="PRUEBA EJEMPLO ANA",
            titular_en_calidad_de=M360TitularEnCalidadDe.SOLICITANTE,
            divisa="EUR",
        ),
    )


def test_a_fully_declared_solicitud_renders_every_header_at_its_design_position() -> None:
    pagina_1 = _pagina_1(_snapshot(_full_profile()))

    assert len(pagina_1) == _PAGINA_1_LENGTH
    expected = {
        4: "0",
        5: "2",
        6: "EL",
        8: "1",
        9: "1",
        10: "3600000000001ABC",
        12: "12345678Z",
        13: _an("Prueba Ejemplo Ana", 125),
        14: _an("solicitante@example.es", 100),
        15: _an("948000000", 15),
        16: "CALLE",
        17: _an("MAYOR", 50),
        18: "NUM",
        19: "00012",
        20: "BIS",
        21: "B1 ",
        22: "P2 ",
        23: "E3 ",
        24: "04 ",
        25: "IZ ",
        26: _an("POLIGONO INDUSTRIAL", 40),
        27: _an("BARRIO ALTO", 30),
        28: "31001",
        29: _an("PAMPLONA", 30),
        30: "31",
        36: "0000001234",
        37: _an("CENTRO", 30),
        38: "31002",
        39: _an("PAMPLONA", 30),
        40: "31",
        41: "0",
        42: "31",
        43: "  ",
        74: "00000000T",
        75: _an("ASESORES PRUEBA SL", 125),
        76: _an("representante@example.es", 100),
        77: _an("+33100000000", 15),
        78: "CALLE",
        79: _an("NUEVA", 50),
        81: "00012",
        90: "31001",
        92: "31",
        93: _an("1 RUE DE PRUEBA", 148),
        94: _an("PARIS", 30),
        95: _an("75001", 10),
        96: _an("ILE DE FRANCE", 30),
        97: "FR",
        98: "0000005678",
        100: "31002",
        113: _an("ASESORES PRUEBA SL", 25),
        114: "R",
        115: _an("ES9121000418450200051332", 34),
        116: "CAIXESBBXXX",
        117: "EUR",
    }
    assert {campo: _campo(pagina_1, campo) for campo in expected} == expected


def test_the_solicitante_foreign_address_is_always_spaces() -> None:
    """DR360 campos 31-35 read "espacios": a full profile still leaves them blank."""
    pagina_1 = _pagina_1(_snapshot(_full_profile()))

    assert {campo: _campo(pagina_1, campo) for campo in range(31, 36)} == {
        campo: _blank(campo) for campo in range(31, 36)
    }


def test_absent_optional_facts_render_as_spaces_not_as_zero_or_default() -> None:
    """An undeclared representante, address or answer is a blank, never a fabricated value."""
    entity = TaxpayerIdentityFacts(legal_name="EMPRESA PRUEBA SA", given_name=None, surnames=None, full_name=None)
    pagina_1 = _pagina_1(_snapshot(_minimal_profile(), identity=entity))

    blank_campos = (4, 9, 10, 15, *range(16, 41), 42, 43, *range(74, 103))
    assert {campo: _campo(pagina_1, campo) for campo in blank_campos} == {
        campo: _blank(campo) for campo in blank_campos
    }
    assert _campo(pagina_1, 5) == "1"
    assert _campo(pagina_1, 6) == "DE"
    assert _campo(pagina_1, 8) == "0"
    assert _campo(pagina_1, 13) == _an("EMPRESA PRUEBA SA", 125)
    assert _campo(pagina_1, 41) == "1"
    assert _campo(pagina_1, 114) == "A"


def test_a_canarias_solicitante_writes_its_delegacion_and_may_address_spain() -> None:
    profile = Modelo360ProfileFacts(
        solicitud=Modelo360SolicitudFacts(
            nivel_calidad_datos=M360NivelCalidadDatos.MEDIA,
            pais_destino="ES",
            causa_presentacion=M360CausaPresentacion.INICIAL,
        ),
        solicitante=Modelo360SolicitanteFacts(
            email="solicitante@example.es",
            establecimiento=Modelo360EstablecimientoFacts(
                ambito=M360AmbitoEstablecimiento.CANARIAS_CEUTA_MELILLA,
                delegacion_canarias_ceuta_melilla=M360DelegacionCanariasCeutaMelilla.TENERIFE,
            ),
        ),
        cuenta=_minimal_profile().cuenta,
    )
    pagina_1 = _pagina_1(_snapshot(profile))

    assert (_campo(pagina_1, 6), _campo(pagina_1, 41), _campo(pagina_1, 42), _campo(pagina_1, 43)) == (
        "ES",
        "0",
        "  ",
        "38",
    )


def test_a_person_known_only_by_full_name_leaves_campo_13_blank_rather_than_guessing_its_order() -> None:
    identity = TaxpayerIdentityFacts(legal_name=None, given_name=None, surnames=None, full_name="Ana Prueba")
    pagina_1 = _pagina_1(_snapshot(_minimal_profile(), identity=identity))

    assert _campo(pagina_1, 12) == _TAX_ID
    assert _campo(pagina_1, 13) == _blank(13)


def test_a_360_without_its_typed_facts_is_refused() -> None:
    with pytest.raises(FilingProducerSnapshotError, match="modelo 360 requires Modelo360ProfileFacts"):
        _snapshot(GeneralFilingProfileFacts())


def test_a_360_without_a_refund_account_is_refused() -> None:
    """DR360 campos 113-117, datos bancarios, are obligatorio."""
    with pytest.raises(FilingProducerSnapshotError, match="modelo 360 requires a selected refund account"):
        _snapshot(_minimal_profile(), disposition=ResultDisposition.NEGATIVA)


def test_a_360_refund_account_without_a_bic_is_refused() -> None:
    """DR360 campo 116, banco-BIC, is obligatorio."""
    with pytest.raises(FilingProducerSnapshotError, match="banco-BIC"):
        _snapshot(_minimal_profile(), refund_account=_refund_account(swift_bic=""))


def test_another_modelo_resolves_every_m360_key_to_nothing() -> None:
    """The resolver runs for every modelo; outside 360 it must contribute no value at all."""
    snapshot = build_filing_producer_snapshot(
        modelo=Modelo("151"),
        taxpayer_tax_id=_TAX_ID,
        taxpayer_identity=TaxpayerIdentityFacts(legal_name=None, given_name="Ana", surnames="Prueba", full_name=None),
        presenter=PresenterIdentity(tax_id=_REPRESENTANTE_TAX_ID, full_name="Gestoria Prueba"),
        model_profile=GeneralFilingProfileFacts(),
        elections=FilingElectionFacts(
            result_disposition=ResultDisposition.INGRESO,
            payment=PaymentElection.INGRESO,
            refund=RefundElection.COMPENSAR,
            prior_domiciliation=PriorDomiciliationElection.KEEP,
        ),
        amendment_evidence=None,
        refund_account=None,
        charge_account=None,
        m303_filing_facts=None,
    )
    m360 = {key: value for key, value in filing_producer_values(snapshot).items() if key.value.startswith("m360.")}

    assert len(m360) == 70
    assert set(m360.values()) == {None}
