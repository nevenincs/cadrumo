"""Typer registration for the unified ledger business invoice command.

One ``aeat app ledger invoice`` noun-group gated by ``--kind issued|received``
replaces the prior payable-invoice / collectible-invoice split. Every verb
reads and writes the sole invoice aggregate — the
:class:`Invoice` records held in the
:class:`InvoiceCatalogue` — through the
application-layer lifecycle functions in
:mod:`~application.invoices`, so the operator surface has exactly one invoice
record behind it and ``link --invoice-id`` resolves against that same identity.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import date
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Annotated

import typer

from ...application.invoices import (
    CatalogueInvoicePatch,
    create_catalogue_invoice,
    import_invoices_from_rows,
    read_bulk_invoice_import_source,
    remove_catalogue_invoice,
    resolve_catalogue_invoice_from_repository,
    update_catalogue_invoice,
)
from ...core import FieldRole, IntracomOperationType
from ...core.external_constants import DEFAULT_CURRENCY
from ...core.i18n import tr
from ...core.json_contract import Notice, NoticeSeverity
from ...domain.invoices import Invoice, InvoiceClass, InvoiceValidationError
from ...domain.iva import InvoiceKind, IvaCategory
from ._common import (
    _bad,
    _emit_envelope,
    _parse_iso_date,
    case_insensitive_choice,
    parse_decimal_amount,
    parse_optional_decimal_amount,
)
from ._common import (
    active_bucket_id_or_refuse as _business_invoice_bucket_id,
)
from ._ledger_catalogue_invoice_payloads import (
    CatalogueInvoiceCreateResult,
    CatalogueInvoiceImportResult,
    CatalogueInvoiceListResult,
    CatalogueInvoiceRemoveResult,
    CatalogueInvoiceUpdateResult,
    CatalogueInvoiceViewResult,
    CatalogueInvoiceWizardResult,
)


def register_business_invoice_commands(app: typer.Typer) -> None:
    """Mount the unified invoice command group on the ledger app."""
    app.add_typer(invoice_app, name="invoice")


_OPERATION_TYPE_TO_IVA_CATEGORY: dict[IntracomOperationType, IvaCategory] = {
    IntracomOperationType.E: IvaCategory.INTRA_COMMUNITY_SUPPLY,
    IntracomOperationType.A: IvaCategory.INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE,
    IntracomOperationType.T: IvaCategory.INTRA_COMMUNITY_TRIANGULATION,
    # The service claves. Before these existed the operator could pick S or I
    # and the record came back with NO category at all, so an ordinary
    # intracomunitaria de servicios was ungrounded to every consumer that reads
    # the IVA treatment. They map to the service categories, not to the goods
    # ones: a service is no sujeta by the art. 69 localisation rule, where an
    # entrega de bienes is exempt under art. 25.
    IntracomOperationType.S: IvaCategory.INTRA_COMMUNITY_SERVICE_SUPPLY,
    IntracomOperationType.ADQUISICION_SERVICIOS: (IvaCategory.INTRA_COMMUNITY_SERVICE_ACQUISITION_REVERSE_CHARGE),
}


def _catalogue_iva_category_for_operation_type(
    operation_type: IntracomOperationType | None,
) -> IvaCategory | None:
    if operation_type is None:
        return None
    return _OPERATION_TYPE_TO_IVA_CATEGORY.get(operation_type)


invoice_app = typer.Typer(
    name="invoice",
    help=tr(
        "cli.app.ledger.invoice.group_help",
        default="Business invoice records (issued or received).",
    ),
    no_args_is_help=True,
)


# The invoice fields every operator surface renders, declared once. Both
# projections below read this tuple, so a field added to one surface cannot go
# missing from the other -- which is exactly how the two drifted apart before.
_SHARED_INVOICE_FIELDS: tuple[str, ...] = (
    "invoice_id",
    "kind",
    "invoice_number",
    "issued_at",
    "counterparty_name",
    "counterparty_tax_id",
    "counterparty_country",
    "base_total",
    "iva_total",
    "grand_total",
    "currency",
    "payment_status",
    "linked_transaction_ids",
    "notes",
    # The euro conversion and its provenance. A foreign-currency invoice
    # rendered as totals plus a currency code told the operator nothing about
    # whether those figures had reached euro at all -- and an unconverted
    # invoice is precisely the one held back from the modelo totals, so the
    # surface stayed silent on the fact that most needed saying. All six are
    # ``None`` on a euro invoice (nothing was converted) and the eur trio is
    # ``None`` on a foreign invoice with no resolvable rate, which is what makes
    # the refusal visible rather than merely correct.
    "fx_rate",
    "fx_rate_date",
    "fx_rate_source",
    "base_total_eur",
    "iva_total_eur",
    "grand_total_eur",
)


def _wire_scalar(value: object) -> object:
    """Render one invoice field in its string wire form.

    The evidence-confirm envelope declares every field as ``str``, so its
    projection needs the rendered form where the catalogue envelope wants the
    native typed value. Keeping the rendering here means the two differ only in
    FORM, never in which fields they carry.
    """
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, tuple | list):
        return list(value)
    return value


def _catalogue_invoice_shared_fields(invoice) -> dict[str, object]:
    """Project the :class:`Invoice` identity/total fields in their string wire form.

    Consumed by the evidence-confirm verb, whose envelope is all-``str``. Shares
    :data:`_SHARED_INVOICE_FIELDS` with :func:`_catalogue_invoice_payload`, so
    the two operator surfaces cannot carry different field sets.
    """
    return {name: _wire_scalar(getattr(invoice, name)) for name in _SHARED_INVOICE_FIELDS}


def _catalogue_invoice_payload(invoice) -> dict[str, object]:
    """Project the :class:`Invoice` in native typed form for the catalogue envelopes.

    Same field set as :func:`_catalogue_invoice_shared_fields` plus the two
    fields only the catalogue surface carries; values stay native because
    :class:`CatalogueInvoiceRecordPayload` is strict and declares real
    ``Decimal`` / ``date`` / enum types.
    """
    payload: dict[str, object] = {name: getattr(invoice, name) for name in _SHARED_INVOICE_FIELDS}
    payload["linked_transaction_ids"] = list(invoice.linked_transaction_ids)
    payload["bucket_id"] = invoice.bucket_id
    payload["operation_type"] = invoice.operation_type
    return payload


def _simplificada_tax_id_notices(invoice: Invoice) -> list[Notice]:
    """Surface RD 1619/2012 art. 6.1.d case 3.º as an advisory, never a refusal.

    Case 3.º asks for the destinatario's NIF on a DOMESTIC factura simplificada
    whose issuer is established in the TAI. The predicate that evaluates it has
    shipped, tested and exported, with no production caller -- so the operator
    was never told. This is that caller.

    Deliberately advisory. An ordinary domestic ticket with no identified
    customer is common and legitimate practice, and the predicate rests on a
    residency approximation that is over-strict for a Canarias, Ceuta or
    Melilla issuer. Refusing here would block lawful invoices; saying nothing
    leaves a filer unaware of a real requirement. The Notice channel is the one
    that fits, which is what the predicate's own docstring instructs.

    Returns no notice when the profile cannot be resolved: an advisory whose
    premise could not be evaluated must not be asserted.
    """
    if invoice.counterparty_tax_id is not None:
        return []
    # Function-local for the cycle reason the sibling profile-backed advisories
    # document: the profile package reaches back into this layer.
    from ...application.invoices import simplificada_requires_tax_id_for_domestic_issuer
    from ...application.user_profile import UserProfileLifecycleRepository, projection_for_taxpayer
    from ...core import resolve_active_bucket_id
    from ...domain.user_profile import ProfileNotFoundError

    bucket_id = resolve_active_bucket_id()
    if bucket_id is None:
        return []
    try:
        record = UserProfileLifecycleRepository(bucket_id=bucket_id).load(bucket_id)
    except ProfileNotFoundError:
        return []
    except (OSError, ValueError):
        # A degraded profile read must not fail an invoice that is already
        # recorded; the advisory simply goes unsaid.
        return []
    if not simplificada_requires_tax_id_for_domestic_issuer(invoice, projection_for_taxpayer(record)):
        return []
    return [
        Notice(
            severity=NoticeSeverity.WARNING,
            code="ledger.invoice.simplificada_tax_id_expected",
            message=(
                "This factura simplificada names no counterparty NIF. For a domestic "
                "operation issued by a taxpayer established in the TAI, RD 1619/2012 "
                "art. 6.1.d case 3.o expects the destinatario's NIF. The invoice was "
                "recorded; add the NIF with `aeat app ledger invoice update` if the "
                "customer identified themselves."
            ),
            suggestion=f"aeat app ledger invoice update {invoice.invoice_id} --counterparty-nif <NIF>",
            context={
                "invoice_id": invoice.invoice_id,
                "invoice_class": invoice.invoice_class.value,
                "legal_ref": "rd-1619-2012:art-6.1.d",
            },
        ),
    ]


def _catalogue_invoice_lines(invoice) -> list[str]:
    return [
        f"invoice_id\t{invoice.invoice_id}",
        f"kind\t{invoice.kind.value}",
        f"counterparty_name\t{invoice.counterparty_name}",
        f"counterparty_tax_id\t{invoice.counterparty_tax_id}",
        f"invoice_number\t{invoice.invoice_number}",
        f"issued_at\t{invoice.issued_at.isoformat()}",
        # Base and cuota alongside the total: the grand total alone cannot be
        # checked against a factura, and an operator reconciling a recargo or a
        # reverse-charge line needs to see which part is base and which is IVA.
        f"base_total\t{format(invoice.base_total, 'f')}",
        f"iva_total\t{format(invoice.iva_total, 'f')}",
        f"grand_total\t{format(invoice.grand_total, 'f')}",
        f"currency\t{invoice.currency}",
        f"operation_type\t{'' if invoice.operation_type is None else invoice.operation_type.value}",
        # The regime axes an operator can now set. Echoed back because a
        # setting the surface does not confirm is one the operator cannot tell
        # they failed to apply -- and a rectificativa silently recorded as
        # ordinaria is a filing error, not a display one.
        f"invoice_class\t{invoice.invoice_class.value}",
        f"series\t{invoice.series or ''}",
        f"rectifies_invoice_number\t{invoice.rectifies_invoice_number or ''}",
        f"recargo_amount\t{'' if invoice.recargo_amount is None else format(invoice.recargo_amount, 'f')}",
        f"iva_category\t{'' if invoice.iva_category is None else invoice.iva_category.value}",
        f"linked_transaction_ids\t{','.join(invoice.linked_transaction_ids)}",
    ]


# Shared Typer option aliases for the two catalogue entry verbs (``create`` and
# ``wizard``), which carry a byte-identical 11-option signature. Declaring them
# once keeps the ``cli.app.ledger.invoice.*`` help keys in one home so ``--help``
# renders identically for both verbs from one ``tr`` lookup.
_CatalogueKindOpt = Annotated[
    InvoiceKind,
    typer.Option(
        "--kind",
        help=tr(
            "cli.app.ledger.invoice.kind_help",
            default="Invoice kind: issued (a customer owes us) or received (we owe a vendor).",
        ),
    ),
]
#: The destinatario's NIF. Optional because RD 1619/2012 art. 7 does not require
#: it on a factura simplificada -- that relief is the point of the simplified
#: form. The domain has always accepted its absence for an ISSUED SIMPLIFICADA;
#: only this option forced one, so the state the art. 6.1.d advisory evaluates
#: could not be reached through the CLI at all. Every other class still refuses
#: an absent id at the domain boundary, with the accepted set named.
_CatalogueCounterpartyNifOpt = Annotated[str | None, typer.Option("--counterparty-nif")]

#: The wizard keeps the NIF REQUIRED. It is a guided flow that assembles a
#: complete record field by field and validates the id as it goes, so an absent
#: one is an unanswered question rather than the deliberate omission that a
#: simplificada represents on the direct `add` path.
_WizardCounterpartyNifOpt = Annotated[str, typer.Option("--counterparty-nif")]
_CatalogueCounterpartyNameOpt = Annotated[str, typer.Option("--counterparty-name")]
_CatalogueInvoiceNumberOpt = Annotated[str, typer.Option("--invoice-number")]
_CatalogueInvoiceDateOpt = Annotated[
    str,
    typer.Option(
        "--invoice-date",
        help=tr("cli.app.ledger.invoice.invoice_date_help", default="Invoice date (YYYY-MM-DD)."),
    ),
]
_CatalogueTaxableBaseOpt = Annotated[str, typer.Option("--taxable-base")]
_CatalogueIvaRateOpt = Annotated[str | None, typer.Option("--iva-rate")]
_CatalogueCurrencyOpt = Annotated[str, typer.Option("--currency")]
_CatalogueCountryCodeOpt = Annotated[
    str,
    typer.Option(
        "--country-code",
        help=tr(
            "cli.app.ledger.invoice.country_code_help",
            default=(
                "Counterparty ISO 3166-1 alpha-2 country code. Required:"
                " it routes both informativas, so it is never assumed."
            ),
        ),
    ),
]
_CatalogueOperationDateOpt = Annotated[
    str | None,
    typer.Option(
        "--operation-date",
        help=tr(
            "cli.app.ledger.invoice.operation_date_help",
            default=(
                "Date the entrega or prestacion took place (YYYY-MM-DD). This is the"
                " LIVA art. 75 devengo date that decides which period declares the"
                " cuota; without it the invoice date stands in for it."
            ),
        ),
    ),
]
_CatalogueOperationTypeOpt = Annotated[
    IntracomOperationType | None,
    typer.Option(
        "--operation-type",
        click_type=case_insensitive_choice(IntracomOperationType),
        help=tr(
            "cli.app.ledger.invoice.operation_type_help",
            default=(
                "M349 operation type: E entrega, S servicios, T triangular,"
                " R rectificación, A adquisición bienes, I adquisición servicios,"
                " M miscelánea."
            ),
        ),
    ),
]
_CatalogueNotesOpt = Annotated[str, typer.Option("--notes")]
_CatalogueInvoiceClassOpt = Annotated[
    InvoiceClass | None,
    typer.Option(
        "--invoice-class",
        help=tr(
            "cli.app.ledger.invoice.invoice_class_help",
            default=(
                "Invoice class. A rectificativa also requires"
                " --rectifies-invoice-number naming the invoice it corrects."
            ),
        ),
    ),
]

_CatalogueSeriesOpt = Annotated[
    str | None,
    typer.Option(
        "--series",
        help=tr(
            "cli.app.ledger.invoice.series_help",
            default="Invoice numbering series, when the issuer uses one.",
        ),
    ),
]

_CatalogueRectifiesOpt = Annotated[
    str | None,
    typer.Option(
        "--rectifies-invoice-number",
        help=tr(
            "cli.app.ledger.invoice.rectifies_help",
            default="Number of the invoice this rectificativa corrects.",
        ),
    ),
]

_CatalogueRecargoOpt = Annotated[
    str | None,
    typer.Option(
        "--recargo",
        help=tr(
            "cli.app.ledger.invoice.recargo_help",
            default=(
                "Recargo de equivalencia charged on top of the cuota (LIVA art. 161)."
                " It rides inside the invoice total, unlike a retención."
            ),
        ),
    ),
]

_CatalogueIvaCategoryOpt = Annotated[
    IvaCategory | None,
    typer.Option(
        "--iva-category",
        help=tr(
            "cli.app.ledger.invoice.iva_category_help",
            default="IVA treatment of the operation. Required for a renta income calculation to ground it.",
        ),
    ),
]

_CatalogueRetentionRateOpt = Annotated[
    str | None,
    typer.Option(
        "--retention-rate",
        help=tr(
            "cli.app.ledger.invoice.retention_rate_help",
            default=(
                "RIRPF art. 95.1 retención fraction withheld by the payer"
                " (0.15 for the general 15%, or 0.07 during the inicio-de-actividad"
                " window). Requires --retention-amount; a rate alone is refused."
            ),
        ),
    ),
]
_CatalogueRetentionAmountOpt = Annotated[
    str | None,
    typer.Option(
        "--retention-amount",
        help=tr(
            "cli.app.ledger.invoice.retention_amount_help",
            default=(
                "Amount of IRPF retención withheld by the payer, in euros."
                " May be supplied alone, or alongside --retention-rate."
            ),
        ),
    ),
]


@invoice_app.command(
    "add",
    help=tr(
        "cli.app.ledger.invoice.add_help",
        default="Create a linkable reconciliation invoice in the catalogue.",
    ),
)
def invoice_add(
    ctx: typer.Context,
    kind: _CatalogueKindOpt,
    counterparty_name: _CatalogueCounterpartyNameOpt,
    invoice_number: _CatalogueInvoiceNumberOpt,
    invoice_date: _CatalogueInvoiceDateOpt,
    taxable_base: _CatalogueTaxableBaseOpt,
    country_code: _CatalogueCountryCodeOpt,
    iva_rate: _CatalogueIvaRateOpt = None,
    currency: _CatalogueCurrencyOpt = DEFAULT_CURRENCY,
    operation_type: _CatalogueOperationTypeOpt = None,
    operation_date: _CatalogueOperationDateOpt = None,
    retention_rate: _CatalogueRetentionRateOpt = None,
    retention_amount: _CatalogueRetentionAmountOpt = None,
    invoice_class: _CatalogueInvoiceClassOpt = None,
    counterparty_nif: _CatalogueCounterpartyNifOpt = None,
    series: _CatalogueSeriesOpt = None,
    rectifies_invoice_number: _CatalogueRectifiesOpt = None,
    recargo: _CatalogueRecargoOpt = None,
    iva_category: _CatalogueIvaCategoryOpt = None,
    notes: _CatalogueNotesOpt = "",
) -> None:
    """Create a rich linkable invoice in the reconciliation catalogue.

    The slim ``invoice add`` record cannot be linked to a transaction; this
    verb mints the rich :class:`Invoice` whose
    content-addressed ``invoice_id`` is the value
    ``aeat app ledger link --invoice-id`` resolves. Supplying an intra-community
    ``--operation-type`` stamps the invoice so the Modelo 349 recapitulative
    calculation can read it. Supplying ``--retention-amount`` (optionally with
    ``--retention-rate``) records a RIRPF art. 95 withholding, which
    ``modelo aggregate --received-invoice-retencion`` routes to Modelo 111 for
    a received invoice.
    """
    from pydantic import ValidationError

    from ...domain.invoices import InvoiceValidationError

    bucket_id = _business_invoice_bucket_id()
    # An explicitly stated treatment WINS over the one derived from the M349
    # clave. The derivation exists so an intracomunitaria is not left
    # ungrounded when the operator only states the clave; it is a fallback, and
    # silently overriding a value the operator did state would be the reverse.
    resolved_iva_category = iva_category or _catalogue_iva_category_for_operation_type(
        operation_type,
    )
    try:
        result = create_catalogue_invoice(
            bucket_id=bucket_id,
            kind=kind,
            counterparty_name=counterparty_name,
            counterparty_tax_id=counterparty_nif,
            counterparty_country=country_code,
            invoice_number=invoice_number,
            issued_at=_parse_iso_date(invoice_date, label="invoice-date"),
            taxable_base=parse_decimal_amount(taxable_base, label="taxable-base"),
            iva_rate=parse_optional_decimal_amount(iva_rate, label="iva-rate"),
            currency=currency,
            notes=notes,
            iva_category=resolved_iva_category,
            operation_type=operation_type,
            operation_date=(
                None if operation_date is None else _parse_iso_date(operation_date, label="operation-date")
            ),
            retention_rate=parse_optional_decimal_amount(retention_rate, label="retention-rate"),
            retention_amount=parse_optional_decimal_amount(retention_amount, label="retention-amount"),
            invoice_class=invoice_class or InvoiceClass.ORDINARIA,
            series=series,
            rectifies_invoice_number=rectifies_invoice_number,
            recargo_amount=parse_optional_decimal_amount(recargo, label="recargo"),
        )
    except InvoiceValidationError as exc:
        raise _bad(str(exc)) from exc
    except ValidationError as exc:
        first = exc.errors()[0] if exc.errors() else {"msg": "invalid invoice input"}
        raise _bad(str(first.get("msg", "invalid invoice input"))) from exc

    _emit_envelope(
        ctx,
        command="ledger.invoice.add",
        result=CatalogueInvoiceCreateResult.model_validate(_catalogue_invoice_payload(result.invoice)),
        lines=_catalogue_invoice_lines(result.invoice),
        notices=_simplificada_tax_id_notices(result.invoice),
    )


@invoice_app.command(
    "wizard",
    help=tr(
        "cli.app.ledger.invoice.wizard_help",
        default="Guided, non-interactive manual entry when extraction is unavailable.",
    ),
)
def invoice_wizard(
    ctx: typer.Context,
    kind: _CatalogueKindOpt,
    counterparty_nif: _WizardCounterpartyNifOpt,
    counterparty_name: _CatalogueCounterpartyNameOpt,
    invoice_number: _CatalogueInvoiceNumberOpt,
    invoice_date: _CatalogueInvoiceDateOpt,
    taxable_base: _CatalogueTaxableBaseOpt,
    country_code: _CatalogueCountryCodeOpt,
    iva_rate: _CatalogueIvaRateOpt = None,
    currency: _CatalogueCurrencyOpt = DEFAULT_CURRENCY,
    operation_type: _CatalogueOperationTypeOpt = None,
    operation_date: _CatalogueOperationDateOpt = None,
    retention_rate: _CatalogueRetentionRateOpt = None,
    retention_amount: _CatalogueRetentionAmountOpt = None,
    invoice_class: _CatalogueInvoiceClassOpt = None,
    series: _CatalogueSeriesOpt = None,
    rectifies_invoice_number: _CatalogueRectifiesOpt = None,
    recargo: _CatalogueRecargoOpt = None,
    iva_category: _CatalogueIvaCategoryOpt = None,
    notes: _CatalogueNotesOpt = "",
) -> None:
    """Guided manual-entry invoice creation for when extraction is unavailable.

    A non-interactive, step-wise validated entry point: every field is
    supplied up front as an option (the operator is an autonomous agent that
    cannot answer an interactive prompt), and every field is validated
    independently before any write is attempted — a malformed NIF and a
    malformed date are BOTH reported in one refusal, never just the first one
    found (``no-silent-under-declaration``). The write delegates to the same
    :func:`cadrumo.application.invoices.create_catalogue_invoice` primitive
    ``catalogue create`` uses (``aeat-architecture-boundaries``).
    A retry with identical fields resolves to the already-catalogued
    content-derived identity and is reported as a guarded idempotent no-op
    rather than re-written or raised as a duplicate
    (``aeat-cli-contract``).
    """
    from ...application.invoices import create_invoice_via_wizard
    from ...domain.invoices import InvoiceValidationError

    bucket_id = _business_invoice_bucket_id()
    resolved_iva_category = iva_category or _catalogue_iva_category_for_operation_type(operation_type)
    try:
        wizard_result = create_invoice_via_wizard(
            bucket_id=bucket_id,
            kind=kind,
            counterparty_nif=counterparty_nif,
            counterparty_name=counterparty_name,
            invoice_number=invoice_number,
            invoice_date=invoice_date,
            taxable_base=taxable_base,
            iva_rate=iva_rate,
            currency=currency,
            country_code=country_code,
            notes=notes,
            iva_category=resolved_iva_category,
            operation_type=operation_type,
            operation_date=operation_date,
            retention_rate=retention_rate,
            retention_amount=retention_amount,
        )
    except InvoiceValidationError as exc:
        message = tr(exc.translated_message, **(exc.context or {})) if exc.translated_message else str(exc)
        raise _bad(message) from exc

    payload = _catalogue_invoice_payload(wizard_result.invoice)
    payload["already_existed"] = wizard_result.already_existed
    lines = _catalogue_invoice_lines(wizard_result.invoice)
    lines.append(f"already_existed\t{wizard_result.already_existed}")

    notices: list[Notice] = []
    if wizard_result.already_existed:
        noop_message = tr(
            "cli.app.ledger.invoice.wizard_idempotent_noop",
            invoice_id=wizard_result.invoice.invoice_id,
            default=(
                "Idempotent no-op: an invoice with this identity already exists "
                f"({wizard_result.invoice.invoice_id}); nothing was created."
            ),
        )
        notices.append(
            Notice(
                severity=NoticeSeverity.INFO,
                code="ledger.invoice.catalogue.wizard.idempotent_noop",
                message=noop_message,
                context={"invoice_id": wizard_result.invoice.invoice_id},
            ),
        )
        lines.append(noop_message)

    _emit_envelope(
        ctx,
        command="ledger.invoice.wizard",
        result=CatalogueInvoiceWizardResult.model_validate(payload),
        lines=lines,
        notices=notices,
    )


@invoice_app.command(
    "import",
    help=tr(
        "cli.app.ledger.invoice.import_help",
        default="Bulk-create catalogue invoices from a CSV or XLSX file.",
    ),
)
def invoice_import(
    ctx: typer.Context,
    file: Path = typer.Option(
        ...,
        "--file",
        help=tr(
            "cli.app.ledger.invoice.import_file_help",
            default=(
                "Path to a CSV or XLSX file of invoice rows (counterparty_nif, "
                "counterparty_name, invoice_number, invoice_date, taxable_base, "
                "and optional iva_rate/currency/country_code/notes)."
            ),
        ),
    ),
    kind: InvoiceKind = typer.Option(
        ...,
        "--kind",
        help=tr(
            "cli.app.ledger.invoice.kind_help",
            default="Invoice kind: issued (a customer owes us) or received (we owe a vendor).",
        ),
    ),
    country: str | None = typer.Option(
        None,
        "--country",
        help=tr(
            "cli.app.ledger.invoice.import_country_help",
            default=(
                "Counterparty country (ISO 3166-1 alpha-2) for the whole import. "
                "Required only when the file carries no country_code column; "
                "ignored when it does, because those rows state their own."
            ),
        ),
    ),
) -> None:
    """Bulk-create reconciliation catalogue invoices from a CSV/XLSX file.

    Each row is handed one at a time to
    :func:`cadrumo.application.invoices.create_catalogue_invoice` -- the same sole
    write path ``catalogue create`` uses for a single invoice; this verb never
    writes the catalogue itself. A row whose content-derived identity already
    exists in the catalogue (a re-import of an unchanged file) is reported
    ``skipped_duplicate`` rather than re-written or raised. A malformed row
    (missing field, bad date, unsupported IVA rate) is reported in ``refused``
    with its row number and the failing field; the remaining valid rows still
    import.
    """
    from ...domain.invoices import InvoiceValidationError

    bucket_id = _business_invoice_bucket_id()
    if not file.exists():
        raise _bad(
            tr(
                "cli.app.ledger.invoice.import_file_not_found",
                path=str(file),
                default=f"File not found: {file}",
            ),
        )
    try:
        mapper, mapping_reasons = _invoice_column_role_mapper()
        source = read_bulk_invoice_import_source(file, mapper=mapper)
        result = import_invoices_from_rows(
            source,
            bucket_id=bucket_id,
            kind=kind,
            declared_country=country.strip().upper() if country else None,
        )
    except InvoiceValidationError as exc:
        raise _bad(str(exc)) from exc

    lines = [
        f"bucket\t{bucket_id}",
        f"rows\t{result.rows}",
        f"created\t{result.created}",
        f"skipped_duplicate\t{result.skipped_duplicate}",
        f"refused\t{len(result.refused)}",
    ]
    notices: list[Notice] = []
    for failure in result.refused:
        lines.append(f"  refused\trow={failure.row_number}\tfield={failure.field}\treason={failure.reason}")
    unmapped = source.resolution.unmapped_columns
    if unmapped:
        # Reported, never a refusal: a book carrying a column the importer has
        # no slot for still imports every row, and the operator is told which
        # columns went unused rather than handed back a rejected file.
        headers = ", ".join(column.header for column in unmapped)
        message = tr(
            "cli.app.ledger.invoice.import_unmapped_columns",
            columns=headers,
            default=f"columns not imported because no invoice field matched them: {headers}",
        )
        lines.append(f"unmapped_columns\t{headers}")
        notices.append(
            Notice(
                severity=NoticeSeverity.INFO,
                code="ledger.invoice.catalogue.import.unmapped_columns",
                message=message,
                context={"columns": headers, "count": str(len(unmapped))},
            ),
        )
    for index, reason in enumerate(mapping_reasons):
        # The positional mapping carries roles only, so a token the allow-list
        # refused would otherwise reach the operator as nothing more than
        # "column not imported". The reason is the difference between an
        # unrecognised column and a mapping that named a role which does not
        # exist, and only one of those is worth an operator's attention.
        lines.append(f"mapping_note\t{reason}")
        notices.append(
            Notice(
                severity=NoticeSeverity.INFO,
                code="ledger.invoice.catalogue.import.column_role_not_applied",
                message=tr(
                    "cli.app.ledger.invoice.import_column_role_not_applied",
                    detail=reason,
                    default=f"a proposed column role was not applied: {reason}",
                ),
                context={"detail": reason, "index": str(index)},
            ),
        )
    every_row_refused = result.rows > 0 and result.created == 0 and bool(result.refused)
    if every_row_refused:
        message = tr(
            "cli.app.ledger.invoice.import_all_refused",
            default="bulk invoice import failed: every row was refused; no invoices were created",
        )
        lines.insert(1, message)
        notices.append(
            Notice(
                severity=NoticeSeverity.WARNING,
                code="ledger.invoice.catalogue.import.all_refused",
                message=message,
                context={"rows": str(result.rows), "refused": str(len(result.refused))},
            ),
        )
    payload = {
        "bucket_id": bucket_id,
        "rows": result.rows,
        "created": result.created,
        "skipped_duplicate": result.skipped_duplicate,
        "refused": [f.model_dump(mode="json") for f in result.refused],
        "created_invoice_ids": list(result.created_invoice_ids),
    }
    _emit_envelope(
        ctx,
        command="ledger.invoice.import",
        result=CatalogueInvoiceImportResult.model_validate(payload),
        lines=lines,
        notices=notices,
    )
    # Only a failed import exits non-zero. The unmapped-column report is an
    # observation about a SUCCESSFUL import, so keying the exit on "any notice"
    # would turn every book carrying an extra column into a failure -- exactly
    # the refuse-whole behaviour this path exists to remove.
    if every_row_refused:
        raise typer.Exit(code=1)


def _invoice_column_role_mapper() -> tuple[Callable[[Sequence[str]], Sequence[FieldRole] | None], list[str]]:
    """Return the invoice-book column-role mapper, and the reasons it collects.

    Bound here rather than inside the importer so the application layer keeps no
    dependency on the language-model package: the CLI already reaches it, and the
    importer only needs something callable. A host that cannot map -- the extra
    absent, no model configured, an unusable reply -- resolves to ``None``, and
    every column then reports as unmapped instead of the file being refused.

    The mapping the importer consumes is positional roles and nothing else, so
    *why* a column ended up unmapped cannot travel with it. The reasons are
    accumulated in the returned list instead, and the command turns them into
    notices -- which is the only sanctioned channel for them, and the difference
    between telling an operator "this column was not imported" and telling them
    the mapping proposed a role that is not a permitted one.
    """
    reasons: list[str] = []

    def resolve(headers: Sequence[str]) -> Sequence[FieldRole] | None:
        from ...core.errors import CadrumoError

        try:
            from ...llm import map_column_roles
        except ImportError:
            return None
        try:
            proposal = map_column_roles(headers)
        except CadrumoError:
            return None
        reasons.extend(
            f"column {item.column_index} {item.header!r}: proposed role {item.proposed_role!r} is not a permitted role"
            for item in proposal.rejected_role_proposals
        )
        reasons.extend(
            f"column {item.column_index} {item.header!r}: role {item.role.value!r} was already taken by column "
            f"{item.kept_column_index}"
            for item in proposal.discarded_duplicate_claims
        )
        reasons.extend(
            f"a role {item.proposed_role!r} was claimed for column {item.column_index}, which the table does not carry"
            for item in proposal.unknown_column_claims
        )
        return proposal.roles

    return resolve, reasons


@invoice_app.command(
    "list",
    help=tr(
        "cli.app.ledger.invoice.list_help",
        default="List reconciliation catalogue invoices.",
    ),
)
def invoice_list(
    ctx: typer.Context,
    kind: InvoiceKind | None = typer.Option(
        None,
        "--kind",
        help=tr(
            "cli.app.ledger.invoice.kind_help",
            default="Invoice kind: issued (a customer owes us) or received (we owe a vendor).",
        ),
    ),
) -> None:
    """List the rich reconciliation catalogue invoices for the active bucket."""
    from ...adapters.persistence.profile.invoices import InvoiceCatalogueRepository

    bucket_id = _business_invoice_bucket_id()
    catalogue = InvoiceCatalogueRepository(bucket_id=bucket_id).load()
    wanted = None if kind is None else kind
    rows = tuple(invoice for invoice in catalogue.values() if wanted is None or invoice.kind is wanted)
    payload = {
        "bucket_id": bucket_id,
        "rows": [_catalogue_invoice_payload(invoice) for invoice in rows],
        "count": len(rows),
    }
    lines = [f"bucket\t{bucket_id}", f"count\t{len(rows)}"]
    for invoice in rows:
        lines.append(
            f"{invoice.invoice_id}\t{invoice.kind.value}\t{invoice.counterparty_tax_id}\t"
            f"{invoice.invoice_number}\t{invoice.issued_at.isoformat()}\t{format(invoice.grand_total, 'f')}",
        )

    _emit_envelope(
        ctx,
        command="ledger.invoice.list",
        result=CatalogueInvoiceListResult.model_validate(payload),
        lines=lines,
    )


@invoice_app.command(
    "view",
    help=tr(
        "cli.app.ledger.invoice.view_help",
        default="Show one reconciliation catalogue invoice by id or unambiguous prefix.",
    ),
)
def invoice_view(
    ctx: typer.Context,
    invoice_id: str = typer.Argument(
        ...,
        help=tr(
            "cli.app.ledger.invoice.invoice_id_help",
            default="Catalogue invoice id (or unambiguous prefix).",
        ),
    ),
) -> None:
    """Show one rich catalogue invoice, resolving a full id or unambiguous prefix.

    The catalogue invoice carries a long content-addressed id that
    ``aeat app ledger link --invoice-id`` resolves; this verb lets an operator
    confirm that id and inspect the invoice's linked transactions before
    linking or removing it. A not-found id, or a prefix matching more than one
    invoice, is a typed refusal naming the candidates — never a silent miss.
    """
    bucket_id = _business_invoice_bucket_id()
    invoice = resolve_catalogue_invoice_from_repository(bucket_id=bucket_id, invoice_id=invoice_id)
    _emit_envelope(
        ctx,
        command="ledger.invoice.view",
        result=CatalogueInvoiceViewResult.model_validate(_catalogue_invoice_payload(invoice)),
        lines=_catalogue_invoice_lines(invoice),
    )


@invoice_app.command(
    "remove",
    help=tr(
        "cli.app.ledger.invoice.remove_help",
        default="Delete one reconciliation catalogue invoice.",
    ),
)
def invoice_remove(
    ctx: typer.Context,
    invoice_id: str = typer.Argument(
        ...,
        help=tr(
            "cli.app.ledger.invoice.invoice_id_help",
            default="Catalogue invoice id (or unambiguous prefix).",
        ),
    ),
    yes: bool = typer.Option(
        False,
        "--yes",
        help=tr("cli.app.ledger.invoice.yes_help", default="Confirm removal."),
    ),
) -> None:
    """Delete one rich catalogue invoice, resolving a full id or unambiguous prefix.

    Removal is refused while the invoice still carries linked transactions:
    deleting it from the catalogue alone would leave the transaction side
    citing a vanished invoice — the operator must ``link``-unlink first. The
    write rides the sanctioned :class:`InvoiceCatalogueRepository`.
    """
    if not yes:
        raise _bad(
            tr(
                "cli.app.ledger.invoice.yes_required",
                default="--yes is required to remove an invoice record",
            ),
        )
    bucket_id = _business_invoice_bucket_id()
    result = remove_catalogue_invoice(bucket_id=bucket_id, invoice_id=invoice_id)
    _emit_envelope(
        ctx,
        command="ledger.invoice.remove",
        result=CatalogueInvoiceRemoveResult.model_validate(_catalogue_invoice_payload(result.invoice)),
        lines=_catalogue_invoice_lines(result.invoice),
    )


@invoice_app.command(
    "update",
    help=tr(
        "cli.app.ledger.invoice.update_help",
        default="Correct fields on one invoice record.",
    ),
)
def invoice_update(
    ctx: typer.Context,
    invoice_id: str = typer.Argument(
        ...,
        help=tr("cli.app.ledger.invoice.invoice_id_help", default="Invoice id (or unambiguous prefix)."),
    ),
    counterparty_name: _CatalogueCounterpartyNameOpt | None = None,
    counterparty_country: _CatalogueCountryCodeOpt | None = None,
    notes: _CatalogueNotesOpt | None = None,
    iva_category: _CatalogueIvaCategoryOpt = None,
    operation_type: _CatalogueOperationTypeOpt = None,
    operation_date: _CatalogueOperationDateOpt = None,
    retention_rate: _CatalogueRetentionRateOpt = None,
    retention_amount: _CatalogueRetentionAmountOpt = None,
    invoice_class: _CatalogueInvoiceClassOpt = None,
    series: _CatalogueSeriesOpt = None,
    rectifies_invoice_number: _CatalogueRectifiesOpt = None,
) -> None:
    """Correct one persisted invoice without re-keying it.

    The identity fields -- kind, number, issue date, counterparty tax id,
    currency and the totals -- are deliberately absent. The invoice id is
    derived from them, so changing one would mint a different record and
    strand every transaction already linked to the old id. An identity
    correction is a remove followed by a create, which the remove verb guards
    by refusing to delete a linked record.
    """
    bucket_id = _business_invoice_bucket_id()
    patch = CatalogueInvoicePatch(
        counterparty_name=counterparty_name,
        counterparty_country=counterparty_country,
        notes=notes,
        iva_category=iva_category,
        operation_type=operation_type,
        operation_date=(None if operation_date is None else _parse_iso_date(operation_date, label="operation-date")),
        retention_rate=parse_optional_decimal_amount(retention_rate, label="retention-rate"),
        retention_amount=parse_optional_decimal_amount(retention_amount, label="retention-amount"),
        invoice_class=invoice_class,
        series=series,
        rectifies_invoice_number=rectifies_invoice_number,
    )
    try:
        result = update_catalogue_invoice(bucket_id=bucket_id, invoice_id=invoice_id, patch=patch)
    except InvoiceValidationError as exc:
        raise _bad(str(exc)) from exc

    payload = _catalogue_invoice_payload(result.invoice)
    payload["bucket_event_ids"] = list(result.bucket_event_ids)
    lines = _catalogue_invoice_lines(result.invoice)
    lines.append(f"bucket_event_ids	{','.join(result.bucket_event_ids)}")
    _emit_envelope(
        ctx,
        command="ledger.invoice.update",
        result=CatalogueInvoiceUpdateResult.model_validate(payload),
        lines=lines,
    )
