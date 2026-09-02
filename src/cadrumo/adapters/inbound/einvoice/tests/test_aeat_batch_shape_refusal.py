"""AEAT filing batches stay outside the single-invoice reader."""

from __future__ import annotations

import pytest

from .....core.document_shape import STRUCTURED_DOCUMENT_SHAPES, DocumentShape
from ..parsers import parse_einvoice_document
from ..shape import probe_document_shape
from ..xml import EInvoiceXmlParseError

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]

_SII_LR_NAMESPACE = (
    "https://www2.agenciatributaria.gob.es/static_files/common/internet/dep/"
    "aplicaciones/es/aeat/ssii/fact/ws/SuministroLR.xsd"
)
_SII_INFORMATION_NAMESPACE = (
    "https://www2.agenciatributaria.gob.es/static_files/common/internet/dep/"
    "aplicaciones/es/aeat/ssii/fact/ws/SuministroInformacion.xsd"
)
_VERIFACTU_LR_NAMESPACE = (
    "https://www2.agenciatributaria.gob.es/static_files/common/internet/dep/"
    "aplicaciones/es/aeat/tike/cont/ws/SuministroLR.xsd"
)
_VERIFACTU_INFORMATION_NAMESPACE = (
    "https://www2.agenciatributaria.gob.es/static_files/common/internet/dep/"
    "aplicaciones/es/aeat/tike/cont/ws/SuministroInformacion.xsd"
)

# These are small, schema-shaped submissions rather than malformed markers:
# each carries the official root, namespaces, header, and one record. They are
# deliberately kept inline so this regression coverage cannot resurrect the
# retired record-batch fixture pipeline.
_SII_SUBMISSION = f"""<?xml version="1.0" encoding="UTF-8"?>
<siiLR:SuministroLRFacturasEmitidas
    xmlns:siiLR="{_SII_LR_NAMESPACE}"
    xmlns:sii="{_SII_INFORMATION_NAMESPACE}">
  <sii:Cabecera>
    <sii:IDVersionSii>1.1</sii:IDVersionSii>
    <sii:Titular>
      <sii:NombreRazon>Example Taxpayer</sii:NombreRazon>
      <sii:NIF>B12345674</sii:NIF>
    </sii:Titular>
    <sii:TipoComunicacion>A0</sii:TipoComunicacion>
  </sii:Cabecera>
  <siiLR:RegistroLRFacturasEmitidas>
    <sii:PeriodoLiquidacion>
      <sii:Ejercicio>2026</sii:Ejercicio>
      <sii:Periodo>01</sii:Periodo>
    </sii:PeriodoLiquidacion>
    <sii:IDFactura>
      <sii:IDEmisorFactura><sii:NIF>B12345674</sii:NIF></sii:IDEmisorFactura>
      <sii:NumSerieFacturaEmisor>F-1</sii:NumSerieFacturaEmisor>
      <sii:FechaExpedicionFacturaEmisor>31-01-2026</sii:FechaExpedicionFacturaEmisor>
    </sii:IDFactura>
    <sii:FacturaExpedida>
      <sii:TipoFactura>F1</sii:TipoFactura>
      <sii:ClaveRegimenEspecialOTrascendencia>01</sii:ClaveRegimenEspecialOTrascendencia>
      <sii:DescripcionOperacion>Consulting service</sii:DescripcionOperacion>
      <sii:TipoDesglose><sii:DesgloseFactura/></sii:TipoDesglose>
    </sii:FacturaExpedida>
  </siiLR:RegistroLRFacturasEmitidas>
</siiLR:SuministroLRFacturasEmitidas>
""".encode()

_VERIFACTU_SUBMISSION = f"""<?xml version="1.0" encoding="UTF-8"?>
<sfLR:RegFactuSistemaFacturacion
    xmlns:sfLR="{_VERIFACTU_LR_NAMESPACE}"
    xmlns:sf="{_VERIFACTU_INFORMATION_NAMESPACE}">
  <sf:Cabecera>
    <sf:ObligadoEmision>
      <sf:NombreRazon>Example Taxpayer</sf:NombreRazon>
      <sf:NIF>B12345674</sf:NIF>
    </sf:ObligadoEmision>
  </sf:Cabecera>
  <sfLR:RegistroFactura>
    <sf:RegistroAnulacion>
      <sf:IDVersion>1.0</sf:IDVersion>
      <sf:IDFactura>
        <sf:IDEmisorFacturaAnulada>B12345674</sf:IDEmisorFacturaAnulada>
        <sf:NumSerieFacturaAnulada>F-1</sf:NumSerieFacturaAnulada>
        <sf:FechaExpedicionFacturaAnulada>31-01-2026</sf:FechaExpedicionFacturaAnulada>
      </sf:IDFactura>
      <sf:Encadenamiento><sf:PrimerRegistro>S</sf:PrimerRegistro></sf:Encadenamiento>
      <sf:SistemaInformatico>
        <sf:NombreRazon>Example Software</sf:NombreRazon>
        <sf:NIF>B12345674</sf:NIF>
        <sf:NombreSistemaInformatico>Emitter</sf:NombreSistemaInformatico>
        <sf:IdSistemaInformatico>01</sf:IdSistemaInformatico>
        <sf:Version>1.0</sf:Version>
        <sf:NumeroInstalacion>1</sf:NumeroInstalacion>
        <sf:TipoUsoPosibleSoloVerifactu>S</sf:TipoUsoPosibleSoloVerifactu>
        <sf:TipoUsoPosibleMultiOT>N</sf:TipoUsoPosibleMultiOT>
        <sf:IndicadorMultiplesOT>N</sf:IndicadorMultiplesOT>
      </sf:SistemaInformatico>
      <sf:FechaHoraHusoGenRegistro>2026-01-31T12:00:00+01:00</sf:FechaHoraHusoGenRegistro>
      <sf:TipoHuella>01</sf:TipoHuella>
      <sf:Huella>0123456789ABCDEF0123456789ABCDEF0123456789ABCDEF0123456789ABCDEF</sf:Huella>
    </sf:RegistroAnulacion>
  </sfLR:RegistroFactura>
</sfLR:RegFactuSistemaFacturacion>
""".encode()

_AEAT_SUBMISSIONS = (
    pytest.param(_SII_SUBMISSION, DocumentShape.XML_AEAT_SII, id="sii"),
    pytest.param(_VERIFACTU_SUBMISSION, DocumentShape.XML_AEAT_VERIFACTU, id="verifactu"),
)


@pytest.mark.parametrize(("document", "expected_shape"), _AEAT_SUBMISSIONS)
def test_aeat_submission_shape_is_classified_but_not_a_single_invoice(
    document: bytes,
    expected_shape: DocumentShape,
) -> None:
    """Recognise each valid filing batch while keeping it out of invoice routing."""
    assert probe_document_shape(document) is expected_shape
    assert expected_shape not in STRUCTURED_DOCUMENT_SHAPES


@pytest.mark.parametrize(("document", "expected_shape"), _AEAT_SUBMISSIONS)
def test_single_invoice_parser_refuses_aeat_submission(
    document: bytes,
    expected_shape: DocumentShape,
) -> None:
    """The retired batch reader cannot be reached through invoice parsing."""
    assert probe_document_shape(document) is expected_shape
    with pytest.raises(EInvoiceXmlParseError, match=expected_shape.value):
        parse_einvoice_document(document)
