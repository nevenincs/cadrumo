"""Guided, non-blocking manual-entry path for one catalogue :class:`~domain.invoices.Invoice`.

``aeat app ledger invoice catalogue wizard`` is the fallback entry point for
when automated extraction (``ledger evidence extract`` / vision OCR) is
unavailable or insufficient: the operator (an autonomous LLM agent that cannot
answer an interactive prompt) supplies every invoice field as CLI options in
one call. This module validates each field independently -- reusing the same
grounded heuristics :func:`~core.identity.validate_spanish_tax_id` and the
ISO-8601 / canonical-decimal parsers already enforce on the extract/confirm
path -- and accumulates every failing field into one refusal
(``no-silent-under-declaration``: a malformed field is named, never silently
dropped or reported one-at-a-time when several are wrong).

The write itself delegates to :func:`~application.invoices.create_catalogue_invoice`
-- the sole sanctioned :class:`~domain.invoices.Invoice` writer
(``composition-service-no-parallel-write-path``); this module never persists a
row itself. Because :class:`~domain.invoices.Invoice` identity is a
content-derived hash, a retry that resolves to an already-catalogued identity
is a guarded no-op (``single-subject-mutation-is-idempotent-guarded``): the
existing record is returned, not re-written or raised as an error, mirroring
the re-import-of-an-unchanged-file semantics
:func:`~application.invoices.import_invoices_from_rows` already implements for
the bulk path.

See Also:
    :func:`~application.invoices.create_invoice_via_wizard`
        Public application facade for this guided manual-entry path.
    :func:`~application.invoices.create_catalogue_invoice`
        Single catalogue writer used after field validation succeeds.
    :func:`~application.invoices.import_invoices_from_rows`
        Spreadsheet-oriented sibling path with matching idempotency semantics.
    :func:`~application.ledger.extract_invoice_draft_from_evidence`
        Automated evidence extraction path this non-interactive wizard
        complements when OCR is unavailable or insufficient.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

from pydantic import BaseModel, ConfigDict, ValidationError

from ...adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ...core import IntracomOperationType
from ...core.errors import CoreValidationError, resolve_error_message
from ...core.identity import IdentityError, validate_spanish_tax_id
from ...core.parsing import parse_iso8601_date
from ...domain.invoices import (
    Invoice,
    InvoiceCatalogueRepositoryProtocol,
    InvoiceValidationError,
    validate_country_code,
    validate_iva_number,
)
from ...domain.iva import InvoiceKind, IvaCategory
from ._creation import build_catalogue_invoice, create_catalogue_invoice, numeric_iva_rate_slots

__all__ = [
    "InvoiceWizardFieldError",
    "InvoiceWizardResult",
    "create_invoice_via_wizard",
]


class InvoiceWizardFieldError(BaseModel):
    """One field that failed the wizard's guided validation.

    Mirrors :class:`~application.invoices.BulkInvoiceImportRowFailure`'s
    ``field``/``reason`` shape so a manual-entry refusal reads consistently
    with the bulk-import refusal surface, minus the row number a single-invoice
    wizard has no use for.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    field: str
    reason: str


class InvoiceWizardResult(BaseModel):
    """Outcome of one guided manual-entry invoice creation.

    ``already_existed`` is ``True`` when the derived identity already named a
    catalogued invoice -- the guarded idempotent no-op path
    (``single-subject-mutation-is-idempotent-guarded``): ``invoice`` is the
    pre-existing record and nothing was written.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    invoice: Invoice
    already_existed: bool


@dataclass(frozen=True, slots=True)
class _WizardFieldError(Exception):
    """Internal control-flow carrier for one field-validation failure."""

    field: str
    reason: str


def _validate_counterparty_nif(raw: str, *, country: str) -> str:
    stripped = raw.strip()
    if not stripped:
        raise _WizardFieldError(field="counterparty_nif", reason="must not be blank")
    try:
        if country == "ES":
            return validate_spanish_tax_id(stripped)
        return validate_iva_number(stripped, country)
    except (IdentityError, InvoiceValidationError) as exc:
        raise _WizardFieldError(field="counterparty_nif", reason=resolve_error_message(exc)) from exc


def _validate_counterparty_name(raw: str) -> str:
    stripped = raw.strip()
    if not stripped:
        raise _WizardFieldError(field="counterparty_name", reason="must not be blank")
    return stripped


def _validate_invoice_number(raw: str) -> str:
    stripped = raw.strip()
    if not stripped:
        raise _WizardFieldError(field="invoice_number", reason="must not be blank")
    return stripped


def _validate_invoice_date(raw: str) -> date:
    try:
        value = parse_iso8601_date(raw)
    except ValueError as exc:
        raise _WizardFieldError(
            field="invoice_date",
            reason=f"must be an ISO-8601 date (YYYY-MM-DD), got {raw!r}",
        ) from exc
    if value is None:
        raise _WizardFieldError(
            field="invoice_date",
            reason=f"must be an ISO-8601 date (YYYY-MM-DD), got {raw!r}",
        )
    return value


def _validate_taxable_base(raw: str) -> Decimal:
    stripped = raw.strip()
    try:
        value = Decimal(stripped)
    except InvalidOperation as exc:
        raise _WizardFieldError(field="taxable_base", reason=f"invalid decimal amount: {raw!r}") from exc
    if not value.is_finite():
        raise _WizardFieldError(field="taxable_base", reason=f"invalid decimal amount: {raw!r}")
    if value < 0:
        raise _WizardFieldError(field="taxable_base", reason="must not be negative")
    return value


def _validate_iva_rate(raw: str | None) -> Decimal | None:
    if raw is None:
        return None
    stripped = raw.strip()
    if not stripped:
        return None
    try:
        value = Decimal(stripped)
    except InvalidOperation as exc:
        raise _WizardFieldError(field="iva_rate", reason=f"invalid decimal percentage: {raw!r}") from exc
    accepted_slots = numeric_iva_rate_slots()
    if value not in accepted_slots:
        accepted = ", ".join(format(rate, "f") for rate in sorted(accepted_slots))
        raise _WizardFieldError(
            field="iva_rate",
            reason=f"{format(value, 'f')} is not a recognised IVA percentage; use one of: {accepted}",
        )
    return value


def _validate_country_code(raw: str) -> str:
    try:
        return validate_country_code(raw)
    except InvoiceValidationError as exc:
        raise _WizardFieldError(field="country_code", reason=str(exc)) from exc


def _validate_currency(raw: str) -> str:
    stripped = raw.strip().upper()
    if len(stripped) != 3 or not stripped.isalpha():
        raise _WizardFieldError(field="currency", reason="must be a three-letter ISO 4217 code")
    return stripped


def create_invoice_via_wizard(
    *,
    bucket_id: str,
    kind: InvoiceKind,
    counterparty_nif: str,
    counterparty_name: str,
    invoice_number: str,
    invoice_date: str,
    taxable_base: str,
    iva_rate: str | None,
    currency: str,
    country_code: str = "ES",
    notes: str = "",
    iva_category: IvaCategory | None = None,
    operation_type: IntracomOperationType | None = None,
    repository: InvoiceCatalogueRepositoryProtocol | None = None,
) -> InvoiceWizardResult:
    """Validate every field, then create (or resolve) one catalogue invoice.

    Every field is validated independently and every failure is accumulated
    before raising, so a malformed NIF and a malformed date are BOTH reported
    in one refusal rather than the first field masking the second
    (``no-silent-under-declaration``). This is a step-wise, non-interactive
    entry point: it never blocks on stdin -- every field is supplied up front
    as a keyword argument, matching the CLI's all-options-up-front shape.

    Args:
        bucket_id: Active profile bucket the invoice is scoped to.
        kind: Invoice direction (issued / received).
        counterparty_nif: Raw counterparty NIF/NIE/CIF or EU IVA number.
        counterparty_name: Raw counterparty display name.
        invoice_number: Raw AEAT-significant invoice number.
        invoice_date: Raw ISO-8601 invoice date string.
        taxable_base: Raw non-negative decimal taxable base string.
        iva_rate: Raw decimal IVA percentage string, or ``None``/blank for a
            base-only (exempt) invoice.
        currency: Raw ISO-4217 currency code (defaults are the caller's
            concern; this function validates whatever is passed).
        country_code: Raw ISO-3166 alpha-2 counterparty country code.
        notes: Free-text notes.
        iva_category: Optional intra-community IVA classification.
        operation_type: Optional Modelo 349 operation-type clave.
        repository: Optional injected catalogue repository (tests).

    Returns:
        :class:`InvoiceWizardResult` naming the resolved invoice and whether
        it was newly created or already existed under the same derived
        identity (the guarded idempotent no-op).

    Raises:
        InvoiceValidationError: naming every failing field in one message when
            one or more fields are malformed.
    """
    field_errors: list[InvoiceWizardFieldError] = []
    resolved_country = "ES"
    try:
        resolved_country = _validate_country_code(country_code)
    except _WizardFieldError as exc:
        field_errors.append(InvoiceWizardFieldError(field=exc.field, reason=exc.reason))

    resolved_nif = ""
    try:
        resolved_nif = _validate_counterparty_nif(counterparty_nif, country=resolved_country)
    except _WizardFieldError as exc:
        field_errors.append(InvoiceWizardFieldError(field=exc.field, reason=exc.reason))

    resolved_name = ""
    try:
        resolved_name = _validate_counterparty_name(counterparty_name)
    except _WizardFieldError as exc:
        field_errors.append(InvoiceWizardFieldError(field=exc.field, reason=exc.reason))

    resolved_number = ""
    try:
        resolved_number = _validate_invoice_number(invoice_number)
    except _WizardFieldError as exc:
        field_errors.append(InvoiceWizardFieldError(field=exc.field, reason=exc.reason))

    resolved_date: date | None = None
    try:
        resolved_date = _validate_invoice_date(invoice_date)
    except _WizardFieldError as exc:
        field_errors.append(InvoiceWizardFieldError(field=exc.field, reason=exc.reason))

    resolved_base: Decimal | None = None
    try:
        resolved_base = _validate_taxable_base(taxable_base)
    except _WizardFieldError as exc:
        field_errors.append(InvoiceWizardFieldError(field=exc.field, reason=exc.reason))

    resolved_rate: Decimal | None = None
    try:
        resolved_rate = _validate_iva_rate(iva_rate)
    except _WizardFieldError as exc:
        field_errors.append(InvoiceWizardFieldError(field=exc.field, reason=exc.reason))

    resolved_currency = ""
    try:
        resolved_currency = _validate_currency(currency)
    except _WizardFieldError as exc:
        field_errors.append(InvoiceWizardFieldError(field=exc.field, reason=exc.reason))

    if field_errors:
        joined = "; ".join(f"{err.field}: {err.reason}" for err in field_errors)
        raise InvoiceValidationError(
            f"invoice wizard refused {len(field_errors)} field(s): {joined}",
            translated_message="application.invoices.wizard.errors.field_errors",
            context={
                "field_count": str(len(field_errors)),
                "fields": ", ".join(err.field for err in field_errors),
                "detail": joined,
            },
        )

    assert resolved_date is not None
    assert resolved_base is not None

    repo = repository or InvoiceCatalogueRepository(bucket_id=bucket_id)

    try:
        candidate = build_catalogue_invoice(
            bucket_id=bucket_id,
            kind=kind,
            counterparty_name=resolved_name,
            counterparty_tax_id=resolved_nif,
            counterparty_country=resolved_country,
            invoice_number=resolved_number,
            issued_at=resolved_date,
            taxable_base=resolved_base,
            iva_rate=resolved_rate,
            currency=resolved_currency,
            notes=notes,
            iva_category=iva_category,
            operation_type=operation_type,
        )
    except (InvoiceValidationError, ValidationError, CoreValidationError) as exc:
        reason = str(exc.errors()[0].get("msg", str(exc))) if isinstance(exc, ValidationError) else str(exc)
        raise InvoiceValidationError(
            f"invoice wizard refused: {reason}",
            translated_message="application.invoices.wizard.errors.build_failed",
            context={"detail": reason},
        ) from exc

    catalogue = repo.load()
    existing = catalogue.get(candidate.invoice_id)
    if existing is not None:
        # Guarded idempotent retry (single-subject-mutation-is-idempotent-guarded):
        # the same fields were already submitted and catalogued under this
        # content-derived identity. Return the existing record; nothing is
        # re-written and no duplicate is raised.
        return InvoiceWizardResult(invoice=existing, already_existed=True)

    result = create_catalogue_invoice(
        bucket_id=bucket_id,
        kind=kind,
        counterparty_name=resolved_name,
        counterparty_tax_id=resolved_nif,
        counterparty_country=resolved_country,
        invoice_number=resolved_number,
        issued_at=resolved_date,
        taxable_base=resolved_base,
        iva_rate=resolved_rate,
        currency=resolved_currency,
        notes=notes,
        iva_category=iva_category,
        operation_type=operation_type,
        repository=repo,
    )
    return InvoiceWizardResult(invoice=result.invoice, already_existed=False)
