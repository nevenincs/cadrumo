"""Behavior handlers for the unified ledger business invoice command.

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

import typer
from pydantic import ValidationError

from ...application.invoices.bulk_import import import_invoices_from_rows, read_bulk_invoice_import_source
from ...application.invoices.catalogue_creation import build_catalogue_invoice, create_catalogue_invoice
from ...application.invoices.catalogue_lifecycle import (
    CatalogueInvoicePatch,
    remove_catalogue_invoice,
    resolve_catalogue_invoice_from_repository,
    update_catalogue_invoice,
)
from ...application.invoices.source_resolver import iva_category_for_operation_type
from ...core.aggregation import IntracomOperationType
from ...core.external_constants import DEFAULT_CURRENCY
from ...core.field_role import FieldRole
from ...core.i18n.render import tr
from ...core.json_contract import Notice, NoticeSeverity
from ...core.type_guards import is_object_list_or_tuple
from ...domain.invoices.enums import InvoiceClass
from ...domain.invoices.errors import InvoiceValidationError
from ...domain.invoices.models import Invoice
from ...domain.iva.classification import InvoiceKind
from ...domain.iva.schema import IvaCategory
from ._common import (
    active_bucket_id_or_refuse as _business_invoice_bucket_id,
)
from ._common import bad, emit_envelope
from ._date_parsing import _parse_iso_date
from ._decimal_parsing import parse_decimal_amount, parse_optional_decimal_amount
from ._ledger_catalogue_invoice_payloads import (
    CatalogueInvoiceCreatePayload,
    CatalogueInvoiceImportResult,
    CatalogueInvoiceListResult,
    CatalogueInvoiceRemovePayload,
    CatalogueInvoiceUpdatePayload,
    CatalogueInvoiceViewResult,
    CatalogueInvoiceWizardResult,
)
from ._ledger_support import ledger_invoice_validation_no_recovery

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
    if is_object_list_or_tuple(value):
        return list(value)
    return value


def catalogue_invoice_shared_fields(invoice: Invoice) -> dict[str, object]:
    """Project the :class:`Invoice` identity/total fields in their string wire form.

    Consumed by the evidence-confirm verb, whose envelope is all-``str``. Shares
    :data:`_SHARED_INVOICE_FIELDS` with :func:`_catalogue_invoice_payload`, so
    the two operator surfaces cannot carry different field sets.
    """
    return {name: _wire_scalar(getattr(invoice, name)) for name in _SHARED_INVOICE_FIELDS}


def _catalogue_invoice_payload(invoice: Invoice) -> dict[str, object]:
    """Project the :class:`Invoice` in native typed form for the catalogue envelopes.

    Same field set as :func:`catalogue_invoice_shared_fields` plus the two
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
    from ...application.invoices.issuer_establishment import simplificada_requires_tax_id_for_domestic_issuer
    from ...application.user_profile.profile_record_repository import ProfileRecordRepository
    from ...application.user_profile.projections import projection_for_taxpayer
    from ...core.bucket_pointer import resolve_active_bucket_id
    from ...domain.user_profile.errors import ProfileNotFoundError

    bucket_id = resolve_active_bucket_id()
    if bucket_id is None:
        return []
    try:
        record = ProfileRecordRepository.for_current_session(bucket_id).load(bucket_id)
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
            message=tr("cli.app.ledger.invoice.simplificada_tax_id_expected_message"),
            context={
                "invoice_id": invoice.invoice_id,
                "invoice_class": invoice.invoice_class.value,
                "legal_ref": "rd-1619-2012:art-6.1.d",
            },
        ),
    ]


def _catalogue_invoice_lines(invoice: Invoice) -> list[str]:
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
#: The destinatario's NIF. Optional because RD 1619/2012 art. 7 does not require
#: it on a factura simplificada -- that relief is the point of the simplified
#: form. The domain has always accepted its absence for an ISSUED SIMPLIFICADA;
#: only this option forced one, so the state the art. 6.1.d advisory evaluates
#: could not be reached through the CLI at all. Every other class still refuses
#: an absent id at the domain boundary, with the accepted set named.

#: The wizard keeps the NIF REQUIRED. It is a guided flow that assembles a
#: complete record field by field and validates the id as it goes, so an absent
#: one is an unanswered question rather than the deliberate omission that a
#: simplificada represents on the direct `add` path.


def invoice_add(
    ctx: typer.Context,
    kind: InvoiceKind,
    counterparty_name: str,
    invoice_number: str,
    invoice_date: str,
    taxable_base: str,
    country_code: str,
    iva_rate: str | None = None,
    currency: str = DEFAULT_CURRENCY,
    operation_type: IntracomOperationType | None = None,
    operation_date: str | None = None,
    retention_rate: str | None = None,
    retention_amount: str | None = None,
    invoice_class: InvoiceClass | None = None,
    counterparty_nif: str | None = None,
    series: str | None = None,
    rectifies_invoice_number: str | None = None,
    recargo: str | None = None,
    iva_category: IvaCategory | None = None,
    notes: str = "",
) -> None:
    """Create a rich linkable invoice in the reconciliation catalogue.

    The slim ``invoice add`` record cannot be linked to a transaction; this
    verb mints the rich :class:`Invoice` whose
    content-addressed ``invoice_id`` is the value the canonical ledger-link
    action resolves. Supplying an intra-community
    ``--operation-type`` stamps the invoice so the Modelo 349 recapitulative
    calculation can read it. Supplying ``--retention-amount`` (optionally with
    ``--retention-rate``) records a RIRPF art. 95 withholding, which
    ``modelo aggregate --received-invoice-retencion`` routes to Modelo 111 for
    a received invoice.
    """
    bucket_id = _business_invoice_bucket_id()
    # An explicitly stated treatment WINS over the one derived from the M349
    # clave. The derivation exists so an intracomunitaria is not left
    # ungrounded when the operator only states the clave; it is a fallback, and
    # silently overriding a value the operator did state would be the reverse.
    resolved_iva_category = iva_category or iva_category_for_operation_type(
        operation_type,
    )
    try:
        invoice = build_catalogue_invoice(
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
        result = create_catalogue_invoice(invoice=invoice)
    except (InvoiceValidationError, ValidationError) as exc:
        if (refusal := ledger_invoice_validation_no_recovery(exc)) is not None:
            raise refusal from None
        raise

    emit_envelope(
        ctx,
        command="ledger.invoice.add",
        result=CatalogueInvoiceCreatePayload.model_validate(_catalogue_invoice_payload(result.invoice)),
        lines=_catalogue_invoice_lines(result.invoice),
        notices=_simplificada_tax_id_notices(result.invoice),
    )


def invoice_wizard(
    ctx: typer.Context,
    kind: InvoiceKind,
    counterparty_nif: str,
    counterparty_name: str,
    invoice_number: str,
    invoice_date: str,
    taxable_base: str,
    country_code: str,
    iva_rate: str | None = None,
    currency: str = DEFAULT_CURRENCY,
    operation_type: IntracomOperationType | None = None,
    operation_date: str | None = None,
    retention_rate: str | None = None,
    retention_amount: str | None = None,
    invoice_class: InvoiceClass | None = None,
    series: str | None = None,
    rectifies_invoice_number: str | None = None,
    recargo: str | None = None,
    iva_category: IvaCategory | None = None,
    notes: str = "",
) -> None:
    """Guided manual-entry invoice creation for when extraction is unavailable.

    A non-interactive, step-wise validated entry point: every field is
    supplied up front as an option (a non-interactive caller
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
    from ...application.invoices.creation_wizard import create_invoice_via_wizard

    bucket_id = _business_invoice_bucket_id()
    resolved_iva_category = iva_category or iva_category_for_operation_type(operation_type)
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
    except (InvoiceValidationError, ValidationError) as exc:
        if (refusal := ledger_invoice_validation_no_recovery(exc)) is not None:
            raise refusal from None
        raise

    payload = _catalogue_invoice_payload(wizard_result.invoice)
    payload["already_existed"] = wizard_result.already_existed
    lines = _catalogue_invoice_lines(wizard_result.invoice)
    lines.append(f"already_existed\t{wizard_result.already_existed}")

    notices: list[Notice] = []
    if wizard_result.already_existed:
        noop_message = tr(
            "cli.app.ledger.invoice.wizard_idempotent_noop",
            invoice_id=wizard_result.invoice.invoice_id,
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

    emit_envelope(
        ctx,
        command="ledger.invoice.wizard",
        result=CatalogueInvoiceWizardResult.model_validate(payload),
        lines=lines,
        notices=notices,
    )


def invoice_import(
    ctx: typer.Context,
    file: Path,
    kind: InvoiceKind,
    country: str | None = None,
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
    bucket_id = _business_invoice_bucket_id()
    if not file.exists():
        raise bad(
            tr("cli.app.ledger.invoice.import_file_not_found", path=str(file)),
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
    except (InvoiceValidationError, ValidationError) as exc:
        if (refusal := ledger_invoice_validation_no_recovery(exc)) is not None:
            raise refusal from None
        raise

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
                ),
                context={"detail": reason, "index": str(index)},
            ),
        )
    every_row_refused = result.rows > 0 and result.created == 0 and bool(result.refused)
    if every_row_refused:
        message = tr(
            "cli.app.ledger.invoice.import_all_refused",
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
    emit_envelope(
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
        from ...core.errors.hierarchy import CadrumoError

        try:
            from ...llm.column_role_mapping import map_column_roles
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


def invoice_list(
    ctx: typer.Context,
    kind: InvoiceKind | None = None,
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

    emit_envelope(
        ctx,
        command="ledger.invoice.list",
        result=CatalogueInvoiceListResult.model_validate(payload),
        lines=lines,
    )


def invoice_view(
    ctx: typer.Context,
    invoice_id: str,
) -> None:
    """Show one rich catalogue invoice, resolving a full id or unambiguous prefix.

    The catalogue invoice carries a long content-addressed id that the
    canonical ledger-link action resolves; this verb lets an operator
    confirm that id and inspect the invoice's linked transactions before
    linking or removing it. A not-found id, or a prefix matching more than one
    invoice, is a typed refusal naming the candidates — never a silent miss.
    """
    bucket_id = _business_invoice_bucket_id()
    invoice = resolve_catalogue_invoice_from_repository(bucket_id=bucket_id, invoice_id=invoice_id)
    emit_envelope(
        ctx,
        command="ledger.invoice.view",
        result=CatalogueInvoiceViewResult.model_validate(_catalogue_invoice_payload(invoice)),
        lines=_catalogue_invoice_lines(invoice),
    )


def invoice_remove(
    ctx: typer.Context,
    invoice_id: str,
    yes: bool = False,
) -> None:
    """Delete one rich catalogue invoice, resolving a full id or unambiguous prefix.

    Removal is refused while the invoice still carries linked transactions:
    deleting it from the catalogue alone would leave the transaction side
    citing a vanished invoice — the operator must ``link``-unlink first. The
    write rides the sanctioned :class:`InvoiceCatalogueRepository`.
    """
    if not yes:
        raise bad(
            tr("cli.app.ledger.invoice.yes_required"),
        )
    bucket_id = _business_invoice_bucket_id()
    result = remove_catalogue_invoice(bucket_id=bucket_id, invoice_id=invoice_id)
    emit_envelope(
        ctx,
        command="ledger.invoice.remove",
        result=CatalogueInvoiceRemovePayload.model_validate(_catalogue_invoice_payload(result.invoice)),
        lines=_catalogue_invoice_lines(result.invoice),
    )


def invoice_update(
    ctx: typer.Context,
    invoice_id: str,
    counterparty_name: str | None = None,
    counterparty_country: str | None = None,
    notes: str | None = None,
    iva_category: IvaCategory | None = None,
    operation_type: IntracomOperationType | None = None,
    operation_date: str | None = None,
    retention_rate: str | None = None,
    retention_amount: str | None = None,
    invoice_class: InvoiceClass | None = None,
    series: str | None = None,
    rectifies_invoice_number: str | None = None,
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
    except (InvoiceValidationError, ValidationError) as exc:
        if (refusal := ledger_invoice_validation_no_recovery(exc)) is not None:
            raise refusal from None
        raise

    payload = _catalogue_invoice_payload(result.invoice)
    payload["bucket_event_ids"] = list(result.bucket_event_ids)
    lines = _catalogue_invoice_lines(result.invoice)
    lines.append(f"bucket_event_ids	{','.join(result.bucket_event_ids)}")
    emit_envelope(
        ctx,
        command="ledger.invoice.update",
        result=CatalogueInvoiceUpdatePayload.model_validate(payload),
        lines=lines,
    )
