"""Read an AEAT SII or VERI*FACTU submission as a BATCH of ledger records.

Separate from :func:`~._parsers.parse_einvoice_document` on purpose, and the
separation is the design rather than an accident of layering. A Facturae, CII or
UBL file is ONE commercial invoice a counterparty issued. A SII or VERI*FACTU
file is a STREAM of records the taxpayer has already declared to AEAT -- the
schemas declare their collections at ``maxOccurs=10000`` and ``1000``. Returning
one invoice from either would keep the first record and silently discard the
rest, which is the defect class this whole reader exists to prevent, so the two
readers have different return types and neither pretends to be the other.

Three things the schema forces, none of which a sample would have shown:

**Classification is per RECORD, never per file.** VERI*FACTU's
``RegistroFactura`` is a ``<choice>`` of ``RegistroAlta`` or
``RegistroAnulacion`` repeated to 1000, so one submission may MIX registrations
and cancellations.

**A cancellation is not an invoice.** ``RegistroFacturacionAnulacionType``
declares no parties, no amounts and no ``Desglose`` -- only an identity. It is
identified and refused, never turned into an invoice.

**Zero recipients is valid.** ``Destinatarios`` is ``[0..1]``, so a factura
simplificada legitimately names nobody. Recipients are carried losslessly, and
the decision about how many a downstream single-counterparty record can accept
belongs to that projection, not here.

Intended consumer
-----------------
This reader has NO caller yet, and that is a recorded gap rather than an open
question. Its intended consumer is a **declared-versus-recorded reconciliation**
surface: comparing what the taxpayer has already DECLARED to AEAT through SII or
VERI*FACTU against what the ledger RECORDS. That is the only thing a
filing-artefact reader is for, and it is the reason this must not be wired into
evidence extraction -- a record the filer produced is not evidence of what a
counterparty billed, so admitting it there would let a taxpayer's own
declaration stand in for the document it was derived from.

A REQUIREMENT WHOEVER BUILDS THAT PROJECTION INHERITS: a record may name more
than one recipient (``IDDestinatario`` is ``[1..1000]``), and nothing refuses
that today, because the refusal belongs to the projection onto a
single-counterparty record and no such projection exists. The reader carrying
every recipient is deliberate -- a party set cannot be split once discarded --
but it means the >1 case is UNGUARDED the moment a consumer appears. The
projection must refuse it instructively, naming each recipient with its
identifier scheme, rather than silently taking the first.

A note on the shape of this module's refusals, which is not decoration: every
record family outside the claimed boundary is mapped EXPLICITLY and refused by
name. An unmapped family is silently skipped, and a submission of records we do
not read then presents as an empty batch reporting nothing wrong -- which an
operator cannot distinguish from a submission we read successfully and found
empty. Reading fewer records than a document contains, without saying so, is the
failure mode this whole module is arranged against.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from xml.etree.ElementTree import Element

from ....core.decimal._coerce import coerce_decimal
from ....core.document_shape import DocumentShape
from ._aeat_record_schema import mandatory_child_elements
from ._shape import probe_document_shape
from ._xml import EInvoiceXmlParseError, parse_hardened_xml

__all__ = [
    "AeatRecordBatch",
    "AeatRecordFamily",
    "ParsedAeatRecord",
    "RefusedAeatRecord",
    "parse_aeat_record_batch",
]


class AeatRecordFamily(StrEnum):
    """The record families this reader distinguishes.

    The four CLAIMED families are read. Everything else is identified and
    refused by name -- declaring the boundary is support; silently ignoring a
    family we do not handle is not.
    """

    SII_FACTURAS_EMITIDAS = "sii_facturas_emitidas"
    SII_FACTURAS_RECIBIDAS = "sii_facturas_recibidas"
    VERIFACTU_ALTA = "verifactu_alta"
    VERIFACTU_ANULACION = "verifactu_anulacion"
    SII_BAJA_EMITIDAS = "sii_baja_emitidas"
    SII_BAJA_RECIBIDAS = "sii_baja_recibidas"
    OTHER = "other"


#: Families carrying an invoice this reader turns into a record. The two
#: cancellation/deregistration families are deliberately absent: they carry an
#: identity and nothing else.
_READABLE = frozenset(
    {
        AeatRecordFamily.SII_FACTURAS_EMITIDAS,
        AeatRecordFamily.SII_FACTURAS_RECIBIDAS,
        AeatRecordFamily.VERIFACTU_ALTA,
    },
)

#: Record-element local name -> family. The SII record elements sit inside their
#: envelope's payload element; the VERI*FACTU ones may appear bare.
_RECORD_ELEMENTS: dict[str, AeatRecordFamily] = {
    "RegistroLRFacturasEmitidas": AeatRecordFamily.SII_FACTURAS_EMITIDAS,
    "RegistroLRFacturasRecibidas": AeatRecordFamily.SII_FACTURAS_RECIBIDAS,
    "RegistroLRBajaExpedidas": AeatRecordFamily.SII_BAJA_EMITIDAS,
    "RegistroLRBajaRecibidas": AeatRecordFamily.SII_BAJA_RECIBIDAS,
    "RegistroAlta": AeatRecordFamily.VERIFACTU_ALTA,
    "RegistroAnulacion": AeatRecordFamily.VERIFACTU_ANULACION,
    # The thirteen SII record families outside the claimed boundary. Listed
    # EXPLICITLY rather than left to fall off the end of the map: an unmapped
    # element is silently skipped, so a submission of, say, bienes de inversion
    # would read as an empty batch and report nothing wrong. Declaring the
    # boundary is support; silently ignoring a family is not, and the two are
    # indistinguishable to an operator unless the refusal names the family.
    "RegistroLRBienesInversion": AeatRecordFamily.OTHER,
    "RegistroLRBajaBienesInversion": AeatRecordFamily.OTHER,
    "RegistroLRAgenciasViajes": AeatRecordFamily.OTHER,
    "RegistroLRBajaAgenciasViajes": AeatRecordFamily.OTHER,
    "RegistroLRCobrosMetalico": AeatRecordFamily.OTHER,
    "RegistroLRBajaCobrosMetalico": AeatRecordFamily.OTHER,
    "RegistroLROperacionesSeguros": AeatRecordFamily.OTHER,
    "RegistroLRBajaOperacionesSeguros": AeatRecordFamily.OTHER,
    "RegistroLRDetOperacionIntracomunitaria": AeatRecordFamily.OTHER,
    "RegistroLRBajaDetOperacionIntracomunitaria": AeatRecordFamily.OTHER,
    "RegistroLRCobros": AeatRecordFamily.OTHER,
    "RegistroLRInmueblesAdicionales": AeatRecordFamily.OTHER,
    "RegistroLRPagos": AeatRecordFamily.OTHER,
}

#: The complexType backing each readable family, for the schema-derived
#: mandatory-element check. Keyed by family so the check cannot be pointed at
#: the wrong type by a caller.
_FAMILY_TYPE: dict[AeatRecordFamily, tuple[str, str]] = {
    AeatRecordFamily.SII_FACTURAS_EMITIDAS: ("sii", "FacturaExpedidaType"),
    AeatRecordFamily.SII_FACTURAS_RECIBIDAS: ("sii", "FacturaRecibidaType"),
    AeatRecordFamily.VERIFACTU_ALTA: ("verifactu", "RegistroFacturacionAltaType"),
}

#: The element holding each readable family's invoice body.
_FAMILY_BODY: dict[AeatRecordFamily, str | None] = {
    AeatRecordFamily.SII_FACTURAS_EMITIDAS: "FacturaExpedida",
    AeatRecordFamily.SII_FACTURAS_RECIBIDAS: "FacturaRecibida",
    AeatRecordFamily.VERIFACTU_ALTA: None,
}


@dataclass(frozen=True, slots=True)
class AeatParty:
    """One named party, with whichever identifier scheme the record states."""

    name: str | None = None
    tax_id: str | None = None
    #: Populated only for a foreign party stated through ``IDOtro``; carries the
    #: country and AEAT id-type code so a refusal can name WHICH identifier a
    #: party was given, not merely that one exists.
    country_code: str | None = None
    id_type: str | None = None


@dataclass(frozen=True, slots=True)
class ParsedAeatRecord:
    """One invoice record read from a submission batch."""

    family: AeatRecordFamily
    invoice_number: str | None = None
    issue_date: str | None = None
    operation_date: str | None = None
    issuer: AeatParty | None = None
    #: Every recipient the record names. EMPTY is valid and meaningful: a
    #: factura simplificada names nobody. More than one is likewise valid in the
    #: schema and is carried here rather than refused, because the constraint
    #: that only one counterparty fits belongs to the projection downstream.
    recipients: tuple[AeatParty, ...] = ()
    invoice_total: Decimal | None = None
    tax_breakdown: tuple[tuple[Decimal | None, Decimal | None, Decimal | None], ...] = ()


@dataclass(frozen=True, slots=True)
class RefusedAeatRecord:
    """A record identified but deliberately not read, with the reason."""

    family: AeatRecordFamily
    element_name: str
    reason: str
    #: The invoice the record refers to, when the record states one. A
    #: cancellation or a baja is far more useful to an operator as "a
    #: cancellation of invoice X" than as "an unsupported record".
    invoice_number: str | None = None


@dataclass(frozen=True, slots=True)
class AeatRecordBatch:
    """Every record in one submission, read or refused, in document order."""

    shape: DocumentShape
    records: tuple[ParsedAeatRecord, ...] = ()
    refusals: tuple[RefusedAeatRecord, ...] = field(default=())

    @property
    def record_count(self) -> int:
        """Total records seen, whether read or refused."""
        return len(self.records) + len(self.refusals)


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _child(parent: Element, name: str) -> Element | None:
    """Return *parent*'s own child by local name, never a deeper descendant."""
    for node in parent:
        if _local(node.tag) == name:
            return node
    return None


def _text(parent: Element | None, name: str) -> str | None:
    if parent is None:
        return None
    node = _child(parent, name)
    if node is None or node.text is None or not node.text.strip():
        return None
    return node.text.strip()


def _party_from(node: Element | None) -> AeatParty | None:
    """Read a party from the element that OWNS it, never by name search.

    Callers pass the specific ``Titular``, ``Contraparte`` or ``IDDestinatario``
    element. That is the whole safety property: ``NombreRazon`` is declared by
    four different types in these schemas -- the party types AND
    ``SistemaInformatico``, which names the BILLING SOFTWARE VENDOR. A
    namespace-agnostic search for the local name ``NombreRazon`` cannot tell a
    software vendor from an invoice party, and in a real captured record the
    three carry three different values.
    """
    if node is None:
        return None
    otro = _child(node, "IDOtro")
    return AeatParty(
        name=_text(node, "NombreRazon"),
        tax_id=_text(node, "NIF") or _text(otro, "ID"),
        country_code=_text(otro, "CodigoPais"),
        id_type=_text(otro, "IDType"),
    )


def _sii_breakdown(body: Element) -> tuple[tuple[Decimal | None, Decimal | None, Decimal | None], ...]:
    """Collect every ``DetalleIVA`` (rate, base, cuota) the record states."""
    rows: list[tuple[Decimal | None, Decimal | None, Decimal | None]] = []
    for detalle in body.iter():
        if _local(detalle.tag) != "DetalleIVA":
            continue
        rows.append(
            (
                coerce_decimal(_text(detalle, "TipoImpositivo")),
                coerce_decimal(_text(detalle, "BaseImponible")),
                coerce_decimal(_text(detalle, "CuotaRepercutida")) or coerce_decimal(_text(detalle, "CuotaSoportada")),
            ),
        )
    return tuple(rows)


def _verifactu_breakdown(record: Element) -> tuple[tuple[Decimal | None, Decimal | None, Decimal | None], ...]:
    desglose = _child(record, "Desglose")
    if desglose is None:
        return ()
    rows: list[tuple[Decimal | None, Decimal | None, Decimal | None]] = []
    for detalle in desglose:
        if _local(detalle.tag) != "DetalleDesglose":
            continue
        rows.append(
            (
                coerce_decimal(_text(detalle, "TipoImpositivo")),
                # VERI*FACTU names the base differently from SII; it is not
                # `BaseImponible` here and a shared lookup silently reads none.
                coerce_decimal(_text(detalle, "BaseImponibleOimporteNoSujeto")),
                coerce_decimal(_text(detalle, "CuotaRepercutida")),
            ),
        )
    return tuple(rows)


def _missing_mandatory(family: AeatRecordFamily, node: Element) -> frozenset[str]:
    """Return the schema-mandatory children *node* does not declare.

    The expected set is DERIVED from the bundled XSD on every call rather than
    transcribed here, so it cannot drift from the schema it claims to enforce.
    """
    schema_family, type_name = _FAMILY_TYPE[family]
    required = mandatory_child_elements(schema_family, type_name)
    present = {_local(child.tag) for child in node}
    return frozenset(required - present)


def _sii_identity(record: Element) -> tuple[str | None, str | None]:
    """Return ``(numero de serie + factura, fecha de expedicion)``.

    Scoped to the record's own ``IDFactura``. SII states the series and number
    CONCATENATED in one ``NumSerieFacturaEmisor`` field -- the schema documents
    it as "Nº Serie+Nº Factura" -- so there is no separate series to recover
    here, unlike Facturae.
    """
    id_factura = _child(record, "IDFactura")
    return (
        _text(id_factura, "NumSerieFacturaEmisor"),
        _text(id_factura, "FechaExpedicionFacturaEmisor"),
    )


def _verifactu_identity(record: Element) -> tuple[str | None, str | None]:
    """Return ``(NumSerieFactura, FechaExpedicionFactura)`` from ``IDFactura``.

    Scoped to the record's own ``IDFactura`` and never searched, because
    ``Encadenamiento/RegistroAnterior`` restates ``IDEmisorFactura``,
    ``NumSerieFactura`` AND ``FechaExpedicionFactura`` for the PREVIOUS invoice
    in the hash chain, under identical local names. A descendant search lands on
    the right one only by document order.
    """
    id_factura = _child(record, "IDFactura")
    return (
        _text(id_factura, "NumSerieFactura"),
        _text(id_factura, "FechaExpedicionFactura"),
    )


def _verifactu_cancelled_identity(record: Element) -> str | None:
    """Return the invoice number a ``RegistroAnulacion`` voids.

    A cancellation names its subject with DIFFERENT element names from a
    registration: ``NumSerieFacturaAnulada`` rather than ``NumSerieFactura``.
    Reusing the registration lookup silently returns nothing, so the operator
    is told a cancellation exists without being told what it cancels.

    Scoped to ``IDFactura`` for the usual reason, and this record type makes the
    hazard concrete: its ``Encadenamiento/RegistroAnterior`` carries a
    ``NumSerieFactura`` -- the registration spelling -- so a search that fell
    back to that name would read the hash chain's predecessor and present it as
    the cancelled invoice.
    """
    return _text(_child(record, "IDFactura"), "NumSerieFacturaAnulada")


def _read_verifactu_alta(record: Element) -> ParsedAeatRecord:
    number, issued = _verifactu_identity(record)
    destinatarios = _child(record, "Destinatarios")
    recipients: tuple[AeatParty, ...] = ()
    if destinatarios is not None:
        recipients = tuple(
            party
            for child in destinatarios
            if _local(child.tag) == "IDDestinatario" and (party := _party_from(child)) is not None
        )
    issuer_id = _text(_child(record, "IDFactura"), "IDEmisorFactura")
    return ParsedAeatRecord(
        family=AeatRecordFamily.VERIFACTU_ALTA,
        invoice_number=number,
        issue_date=issued,
        operation_date=_text(record, "FechaOperacion"),
        # NombreRazonEmisor is a FLAT sibling of IDFactura, not nested in it,
        # and is the issuer's own name -- distinct from SistemaInformatico's.
        issuer=AeatParty(name=_text(record, "NombreRazonEmisor"), tax_id=issuer_id),
        recipients=recipients,
        invoice_total=coerce_decimal(_text(record, "ImporteTotal")),
        tax_breakdown=_verifactu_breakdown(record),
    )


def _read_sii_invoice(family: AeatRecordFamily, record: Element, titular: Element | None) -> ParsedAeatRecord:
    """Read one SII invoice record, assigning parties by DIRECTION.

    The direction inverts which side the header party is, and getting it wrong
    inverts the whole record:

    * **Emitidas** -- ``Cabecera/Titular`` IS the issuer (the declarant issued
      the invoice) and ``Contraparte`` is the customer.
    * **Recibidas** -- ``Titular`` is the RECIPIENT (the declarant received it)
      and ``Contraparte`` is the SUPPLIER, i.e. the issuer.
    """
    body = _child(record, _FAMILY_BODY[family] or "")
    number, issued = _sii_identity(record)
    contraparte = _party_from(_child(body, "Contraparte")) if body is not None else None
    header = _party_from(titular)

    if family is AeatRecordFamily.SII_FACTURAS_EMITIDAS:
        issuer, recipients = header, (contraparte,) if contraparte else ()
    else:
        issuer, recipients = contraparte, (header,) if header else ()

    return ParsedAeatRecord(
        family=family,
        invoice_number=number,
        issue_date=issued,
        operation_date=_text(body, "FechaOperacion"),
        issuer=issuer,
        recipients=recipients,
        invoice_total=coerce_decimal(_text(body, "ImporteTotal")),
        tax_breakdown=_sii_breakdown(body) if body is not None else (),
    )


def _refuse_unreadable(family: AeatRecordFamily, element_name: str, record: Element) -> RefusedAeatRecord:
    """Identify a record we do not read, naming the invoice where it states one."""
    if family in {AeatRecordFamily.VERIFACTU_ANULACION}:
        number = _verifactu_cancelled_identity(record)
        reason = (
            "a VERI*FACTU cancellation record (RegistroAnulacion) voids a previously declared invoice. "
            "It states no parties and no amounts, so it cannot yield an invoice"
        )
    elif family in {AeatRecordFamily.SII_BAJA_EMITIDAS, AeatRecordFamily.SII_BAJA_RECIBIDAS}:
        number, _ = _sii_identity(record)
        reason = (
            "a SII baja record is a request to DEREGISTER a previously supplied invoice, not a record of an invoice"
        )
    else:
        number = None
        reason = (
            f"{element_name} is an AEAT record family this reader does not read; "
            "only facturas emitidas and recibidas are read from a SII submission"
        )
    return RefusedAeatRecord(family=family, element_name=element_name, reason=reason, invoice_number=number)


def parse_aeat_record_batch(data: bytes) -> AeatRecordBatch:
    """Read every record in an AEAT SII or VERI*FACTU submission.

    Args:
        data: The submission's full bytes, SOAP-wrapped or bare.

    Returns:
        Every record in document order, split into those read and those
        identified and refused. A batch whose records are ALL refused is still a
        successful read of a document we correctly decline to interpret; the
        caller distinguishes that from a parse failure, which raises.

    Raises:
        EInvoiceXmlParseError: The bytes are not a recognised AEAT record
            submission, or are not parseable XML at all.
    """
    shape = probe_document_shape(data)
    if shape not in {DocumentShape.XML_AEAT_SII, DocumentShape.XML_AEAT_VERIFACTU}:
        message = f"document shape {shape.value!r} is not an AEAT SII or VERI*FACTU record submission"
        raise EInvoiceXmlParseError(message)

    root = parse_hardened_xml(data)
    # The header party is stated ONCE per submission, above the records, and is
    # needed to assign parties on every SII record inside it.
    titular = None
    for node in root.iter():
        if _local(node.tag) == "Cabecera":
            titular = _child(node, "Titular")
            break

    records: list[ParsedAeatRecord] = []
    refusals: list[RefusedAeatRecord] = []
    for node in root.iter():
        family = _RECORD_ELEMENTS.get(_local(node.tag))
        if family is None:
            continue
        element_name = _local(node.tag)
        if family not in _READABLE:
            refusals.append(_refuse_unreadable(family, element_name, node))
            continue
        subject = node if family is AeatRecordFamily.VERIFACTU_ALTA else _child(node, _FAMILY_BODY[family] or "")
        missing = _missing_mandatory(family, subject) if subject is not None else frozenset({"(record body)"})
        if missing:
            refusals.append(
                RefusedAeatRecord(
                    family=family,
                    element_name=element_name,
                    reason=(f"record omits elements the AEAT schema declares mandatory: {', '.join(sorted(missing))}"),
                ),
            )
            continue
        if family is AeatRecordFamily.VERIFACTU_ALTA:
            records.append(_read_verifactu_alta(node))
        else:
            records.append(_read_sii_invoice(family, node, titular))

    return AeatRecordBatch(shape=shape, records=tuple(records), refusals=tuple(refusals))
