"""Render a persona's generated invoice documents from the ledger rows they evidence.

A persona document declared with ``generator = "facturae"`` is the invoice its
single attached ledger row states. This module turns that row and the identity
catalogue into a Facturae 3.2.2 invoice, so the document agrees with its row by
construction: number, issue date, parties, taxable base, IVA rate and cuota,
any recargo de equivalencia, and any IRPF retención. The text is deterministic, so a consumer may commit it
and check it for drift.

A row that self-assesses its cuota under inversión del sujeto pasivo (LIVA
art. 84.Uno.2.º) evidences a supplier invoice that repercutes none: the invoice
states the base at a zero rate and the legal literal, and the row's cuota stays
the recipient's own. A seller identified by a NIF-IVA intracomunitario is resident in
another Member State and is stated by that number as it stands.

The persona states no postal addresses, so the parties carry none: the document
holds only what the persona states. The output is read back by the product's own
Facturae reader in the tests that guard this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from xml.sax.saxutils import escape

from .personas import Identity, LedgerRow, Persona, PersonaCatalogueError, PersonaDocument, YearEnvelope

_CENT = Decimal("0.01")
_FACTURAE_NAMESPACE = "http://www.facturae.gob.es/formato/Versiones/Facturaev3_2_2.xml"
_IVA_TAX_TYPE = "01"
_IRPF_TAX_TYPE = "04"
_LEGAL_ENTITY_KINDS = frozenset({"cif", "nif_iva"})
_REVERSE_CHARGE_LITERAL = "Inversión del sujeto pasivo, art. 84.Uno.2.º LIVA"


@dataclass(frozen=True, slots=True)
class GeneratedDocument:
    """One generated document: its persona document id, file name, media type and text."""

    document_id: str
    file_name: str
    media_type: str
    text: str


def _money(value: Decimal) -> str:
    return str(value.quantize(_CENT))


def _percentage(fraction: Decimal) -> str:
    return str((fraction * 100).quantize(_CENT))


def _tax_identification(identity: Identity) -> str:
    """The identifier as Facturae states it: a NIF-IVA intracomunitario as it stands, a Spanish one behind ``ES``."""
    return identity.value if identity.kind == "nif_iva" else f"ES{identity.value}"


def _party(identity: Identity, role_tag: str) -> list[str]:
    legal_entity = identity.kind in _LEGAL_ENTITY_KINDS
    lines = [
        f"    <{role_tag}>",
        "      <TaxIdentification>",
        f"        <PersonTypeCode>{'J' if legal_entity else 'F'}</PersonTypeCode>",
        f"        <ResidenceTypeCode>{'U' if identity.kind == 'nif_iva' else 'R'}</ResidenceTypeCode>",
        f"        <TaxIdentificationNumber>{escape(_tax_identification(identity))}</TaxIdentificationNumber>",
        "      </TaxIdentification>",
    ]
    if legal_entity:
        lines.extend(
            (
                "      <LegalEntity>",
                f"        <CorporateName>{escape(identity.field('razon_social'))}</CorporateName>",
                "      </LegalEntity>",
            )
        )
    else:
        lines.extend(("      <Individual>", f"        <Name>{escape(identity.field('nombre'))}</Name>"))
        lines.append(f"        <FirstSurname>{escape(identity.field('primer_apellido'))}</FirstSurname>")
        if identity.segundo_apellido is not None:
            lines.append(f"        <SecondSurname>{escape(identity.segundo_apellido)}</SecondSurname>")
        lines.append("      </Individual>")
    lines.append(f"    </{role_tag}>")
    return lines


def _tax(
    type_code: str,
    rate: Decimal,
    base: Decimal,
    amount: Decimal,
    indent: str,
    *,
    surcharge: tuple[Decimal, Decimal] | None = None,
) -> list[str]:
    """One ``Tax`` element; ``surcharge`` is the recargo de equivalencia rate and amount beside the cuota."""
    surcharge_lines = (
        []
        if surcharge is None
        else [
            f"{indent}  <EquivalenceSurcharge>{_percentage(surcharge[0])}</EquivalenceSurcharge>",
            f"{indent}  <EquivalenceSurchargeAmount>",
            f"{indent}    <TotalAmount>{_money(surcharge[1])}</TotalAmount>",
            f"{indent}  </EquivalenceSurchargeAmount>",
        ]
    )
    return [
        f"{indent}<Tax>",
        f"{indent}  <TaxTypeCode>{type_code}</TaxTypeCode>",
        f"{indent}  <TaxRate>{_percentage(rate)}</TaxRate>",
        f"{indent}  <TaxableBase>",
        f"{indent}    <TotalAmount>{_money(base)}</TotalAmount>",
        f"{indent}  </TaxableBase>",
        f"{indent}  <TaxAmount>",
        f"{indent}    <TotalAmount>{_money(amount)}</TotalAmount>",
        f"{indent}  </TaxAmount>",
        *surcharge_lines,
        f"{indent}</Tax>",
    ]


@dataclass(frozen=True, slots=True)
class _InvoiceFacts:
    seller_role: str
    number: str
    issued_on: date
    currency: str
    description: str
    base: Decimal
    rate: Decimal
    cuota: Decimal
    recargo_rate: Decimal | None
    recargo: Decimal | None
    retencion_rate: Decimal | None
    retencion: Decimal | None
    reverse_charge: bool


def _facts(row: LedgerRow, envelope: YearEnvelope, where: str) -> _InvoiceFacts:
    if row.invoice_kind != "received":
        raise PersonaCatalogueError(f"{where}: a generated invoice evidences a received invoice only")
    if row.invoice_number is None or row.counterparty is None:
        raise PersonaCatalogueError(f"{where}: the row states no invoice number or counterparty")
    if row.taxable_base is None or row.iva_rate is None or row.iva_amount is None:
        raise PersonaCatalogueError(f"{where}: the row states no taxable base, IVA rate or cuota")
    recargo_rate = None
    if row.recargo_amount is not None:
        # The row states the recargo amount only; its rate is the one that yields it on the base.
        recargo_rate = (row.recargo_amount / row.taxable_base).quantize(Decimal("0.0001"))
        if (row.taxable_base * recargo_rate).quantize(_CENT) != row.recargo_amount:
            raise PersonaCatalogueError(f"{where}: the recargo {row.recargo_amount} is no whole rate of the base")
    if (row.retencion_rate is None) != (row.retencion_amount is None):
        raise PersonaCatalogueError(f"{where}: the row states a retención rate without its amount, or the reverse")
    cuota = Decimal(0) if row.reverse_charge else row.iva_amount
    total = row.taxable_base + cuota + (row.recargo_amount or Decimal(0)) - (row.retencion_amount or Decimal(0))
    if total != abs(row.amount):
        raise PersonaCatalogueError(f"{where}: base + cuota + recargo - retención {total} differs from the movement")
    return _InvoiceFacts(
        seller_role=row.counterparty,
        number=row.invoice_number,
        issued_on=row.operation_date(envelope),
        currency=row.currency,
        description=row.description,
        base=row.taxable_base,
        rate=Decimal(0) if row.reverse_charge else row.iva_rate,
        cuota=cuota,
        recargo_rate=recargo_rate,
        recargo=row.recargo_amount,
        retencion_rate=row.retencion_rate,
        retencion=row.retencion_amount,
        reverse_charge=row.reverse_charge,
    )


def render_facturae(persona: Persona, document: PersonaDocument, envelope: YearEnvelope) -> GeneratedDocument:
    """Render ``document`` as the Facturae 3.2.2 invoice its single attached row states.

    Raises:
        PersonaCatalogueError: When the document is not a generated Facturae, or
            its row states no complete received invoice whose figures add up to
            the movement.
    """
    where = f"{persona.id} document {document.id}"
    if document.generator != "facturae" or len(document.attach_to) != 1:
        raise PersonaCatalogueError(f"{where}: not a generated Facturae of one row")
    (ref,) = document.attach_to
    row = next(row for row in persona.ledger if row.ref == ref)
    facts = _facts(row, envelope, where)
    seller = persona.identities.role(facts.seller_role)
    buyer = persona.identities.role(persona.taxpayer)
    withheld = facts.retencion if facts.retencion is not None else Decimal(0)
    surcharge = None if facts.recargo is None or facts.recargo_rate is None else (facts.recargo_rate, facts.recargo)
    output_tax = facts.cuota + (facts.recargo or Decimal(0))
    invoice_total = facts.base + output_tax - withheld
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<fe:Facturae xmlns:fe="{_FACTURAE_NAMESPACE}">',
        "  <FileHeader>",
        "    <SchemaVersion>3.2.2</SchemaVersion>",
        "    <Modality>I</Modality>",
        "    <InvoiceIssuerType>EM</InvoiceIssuerType>",
        "    <Batch>",
        f"      <BatchIdentifier>{escape(_tax_identification(seller))}{escape(facts.number)}</BatchIdentifier>",
        "      <InvoicesCount>1</InvoicesCount>",
        "      <TotalInvoicesAmount>",
        f"        <TotalAmount>{_money(invoice_total)}</TotalAmount>",
        "      </TotalInvoicesAmount>",
        "      <TotalOutstandingAmount>",
        f"        <TotalAmount>{_money(invoice_total)}</TotalAmount>",
        "      </TotalOutstandingAmount>",
        "      <TotalExecutableAmount>",
        f"        <TotalAmount>{_money(invoice_total)}</TotalAmount>",
        "      </TotalExecutableAmount>",
        f"      <InvoiceCurrencyCode>{escape(facts.currency)}</InvoiceCurrencyCode>",
        "    </Batch>",
        "  </FileHeader>",
        "  <Parties>",
        *_party(seller, "SellerParty"),
        *_party(buyer, "BuyerParty"),
        "  </Parties>",
        "  <Invoices>",
        "    <Invoice>",
        "      <InvoiceHeader>",
        f"        <InvoiceNumber>{escape(facts.number)}</InvoiceNumber>",
        "        <InvoiceDocumentType>FC</InvoiceDocumentType>",
        "        <InvoiceClass>OO</InvoiceClass>",
        "      </InvoiceHeader>",
        "      <InvoiceIssueData>",
        f"        <IssueDate>{facts.issued_on.isoformat()}</IssueDate>",
        f"        <InvoiceCurrencyCode>{escape(facts.currency)}</InvoiceCurrencyCode>",
        f"        <TaxCurrencyCode>{escape(facts.currency)}</TaxCurrencyCode>",
        "        <LanguageName>es</LanguageName>",
        "      </InvoiceIssueData>",
        "      <TaxesOutputs>",
        *_tax(_IVA_TAX_TYPE, facts.rate, facts.base, facts.cuota, "        ", surcharge=surcharge),
        "      </TaxesOutputs>",
    ]
    if facts.retencion is not None and facts.retencion_rate is not None:
        lines.extend(
            (
                "      <TaxesWithheld>",
                *_tax(_IRPF_TAX_TYPE, facts.retencion_rate, facts.base, facts.retencion, "        "),
                "      </TaxesWithheld>",
            )
        )
    lines.extend(
        (
            "      <InvoiceTotals>",
            f"        <TotalGrossAmount>{_money(facts.base)}</TotalGrossAmount>",
            f"        <TotalGrossAmountBeforeTaxes>{_money(facts.base)}</TotalGrossAmountBeforeTaxes>",
            f"        <TotalTaxOutputs>{_money(output_tax)}</TotalTaxOutputs>",
            f"        <TotalTaxesWithheld>{_money(withheld)}</TotalTaxesWithheld>",
            f"        <InvoiceTotal>{_money(invoice_total)}</InvoiceTotal>",
            f"        <TotalOutstandingAmount>{_money(invoice_total)}</TotalOutstandingAmount>",
            f"        <TotalExecutableAmount>{_money(invoice_total)}</TotalExecutableAmount>",
            "      </InvoiceTotals>",
            "      <Items>",
            "        <InvoiceLine>",
            f"          <ItemDescription>{escape(facts.description)}</ItemDescription>",
            "          <Quantity>1</Quantity>",
            f"          <UnitPriceWithoutTax>{_money(facts.base)}</UnitPriceWithoutTax>",
            f"          <TotalCost>{_money(facts.base)}</TotalCost>",
            f"          <GrossAmount>{_money(facts.base)}</GrossAmount>",
            "          <TaxesOutputs>",
            *_tax(_IVA_TAX_TYPE, facts.rate, facts.base, facts.cuota, "            ", surcharge=surcharge),
            "          </TaxesOutputs>",
            "        </InvoiceLine>",
            "      </Items>",
        )
    )
    if facts.reverse_charge:
        lines.extend(
            (
                "      <LegalLiterals>",
                f"        <LegalReference>{escape(_REVERSE_CHARGE_LITERAL)}</LegalReference>",
                "      </LegalLiterals>",
            )
        )
    lines.extend(
        (
            "    </Invoice>",
            "  </Invoices>",
            "</fe:Facturae>",
        )
    )
    return GeneratedDocument(
        document_id=document.id,
        file_name=f"{document.id}.xml",
        media_type=document.media_type,
        text="\n".join(lines) + "\n",
    )


def generated_documents(persona: Persona, envelope: YearEnvelope) -> tuple[GeneratedDocument, ...]:
    """Render every generated document of ``persona``, in ``documents.toml`` order."""
    return tuple(
        render_facturae(persona, document, envelope) for document in persona.documents if document.generator is not None
    )


__all__ = ["GeneratedDocument", "generated_documents", "render_facturae"]
