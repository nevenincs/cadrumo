"""Guided, non-blocking manual-entry path for one catalogue :class:`~domain.invoices.Invoice`.

``aeat app ledger invoice wizard`` is the fallback entry point for
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
(``aeat-architecture-boundaries``); this module never persists a
row itself. Because :class:`~domain.invoices.Invoice` identity is a
content-derived hash, a retry that resolves to an already-catalogued identity
is a guarded no-op (``aeat-cli-contract``): the
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
    :func:`~application.ledger.invoice_draft_extraction.extract_invoice_draft_from_evidence`
        Automated evidence extraction path this non-interactive wizard
        complements when OCR is unavailable or insufficient.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import ClassVar

from pydantic import BaseModel, ValidationError

from ...adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ...core.aggregation import IntracomOperationType
from ...core.decimal.grammar import try_parse_canonical_decimal
from ...core.errors.error_codes import resolve_error_message
from ...core.errors.hierarchy import CoreValidationError
from ...core.identity import IdentityError, validate_spanish_tax_id
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.parsing import normalise_iso_4217_currency, parse_iso8601_date
from ...domain.invoices.enums import numeric_iva_rate_slots
from ...domain.invoices.errors import InvoiceValidationError
from ...domain.invoices.models import Invoice
from ...domain.invoices.protocols import InvoiceCatalogueRepositoryProtocol
from ...domain.invoices.validators import validate_country_code, validate_iva_number
from ...domain.iva.classification import InvoiceKind, domestic_categories_by_rate_kind
from ...domain.iva.lookup import rate_kinds_for_declared_rate
from ...domain.iva.schema import EUMemberState, IvaCategory
from ._creation import build_catalogue_invoice, create_catalogue_invoice

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

    model_config = STRICT_FROZEN_CONFIG

    field: str
    reason: str


class InvoiceWizardResult(BaseModel):
    """Outcome of one guided manual-entry invoice creation.

    ``already_existed`` is ``True`` when the derived identity already named a
    catalogued invoice -- the guarded idempotent no-op path
    (``aeat-cli-contract``): ``invoice`` is the
    pre-existing record and nothing was written.
    """

    model_config = STRICT_FROZEN_CONFIG

    invoice: Invoice
    already_existed: bool


@dataclass(frozen=True, slots=True)
class _WizardFieldError(Exception):
    """Internal control-flow carrier for one field-validation failure."""

    __bare_base_rationale__: ClassVar[str] = (
        "private wizard field-validation carrier; converted to InvoiceValidationError before leaving the module"
    )

    field: str
    reason: str


def _collect_wizard_field[T](
    field_errors: list[InvoiceWizardFieldError],
    validate: Callable[[], T],
    *,
    fallback: T,
) -> T:
    """Run one field validator while retaining its attributed refusal.

    The wizard deliberately evaluates every independent input before refusing.
    This keeps that accumulation policy in one place while each validator remains
    the sole owner of its field-specific grammar and reason.
    """
    try:
        return validate()
    except _WizardFieldError as exc:
        field_errors.append(InvoiceWizardFieldError(field=exc.field, reason=exc.reason))
        return fallback


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


def _validate_operation_date(raw: str) -> date:
    """Validate the declared devengo date, reported under its own field name.

    Named separately from the invoice date rather than sharing that validator
    so a malformed value is reported against ``operation_date``. The guided
    verb's whole contract is that every field failure is attributed and
    accumulated; a refusal naming the wrong field would send the operator to
    correct a value that was already correct.
    """
    try:
        value = parse_iso8601_date(raw)
    except ValueError as exc:
        raise _WizardFieldError(
            field="operation_date",
            reason=f"must be an ISO-8601 date (YYYY-MM-DD), got {raw!r}",
        ) from exc
    if value is None:
        raise _WizardFieldError(
            field="operation_date",
            reason=f"must be an ISO-8601 date (YYYY-MM-DD), got {raw!r}",
        )
    return value


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
    """Validate the operator-typed taxable base against the canonical euro grammar.

    The two-fractional-digit cap is what makes the Spanish thousands shape
    ``1.000`` refuse instead of silently becoming ``Decimal("1.0")`` — a one-euro
    base for an operator who meant one thousand. The grammar also subsumes the
    finiteness guard and closes ``1e3``, a leading ``+``, an underscore digit
    separator, and a comma decimal, all of which the bare
    :class:`~decimal.Decimal` call accepted. The negative refusal stays separate
    so it keeps naming its own reason rather than collapsing into the grammar
    message.
    """
    value = try_parse_canonical_decimal(raw, max_fraction_digits=2)
    if value is None:
        raise _WizardFieldError(field="taxable_base", reason=f"invalid decimal amount: {raw!r}")
    if value < 0:
        raise _WizardFieldError(field="taxable_base", reason="must not be negative")
    return value


def _validate_iva_rate(raw: str | None) -> Decimal | None:
    """Validate the operator-typed IVA percentage against the canonical grammar.

    Uncapped fractional digits: this is a percentage, not a euro amount, and the
    registry's declared rate slots are the authority on which values exist. The
    grammar refuses the forms a bare :class:`~decimal.Decimal` call admitted
    (scientific notation, a leading ``+``, an underscore separator, a comma
    decimal, ``NaN``/``Infinity``) so a malformed token reports as a decimal
    failure rather than reaching the slot check and reporting the misleading "not
    a recognised IVA percentage".
    """
    if raw is None:
        return None
    if not raw.strip():
        return None
    value = try_parse_canonical_decimal(raw)
    if value is None:
        raise _WizardFieldError(field="iva_rate", reason=f"invalid decimal percentage: {raw!r}")
    accepted_slots = numeric_iva_rate_slots()
    if value not in accepted_slots:
        accepted = ", ".join(format(rate, "f") for rate in sorted(accepted_slots))
        raise _WizardFieldError(
            field="iva_rate",
            reason=f"{format(value, 'f')} is not a recognised IVA percentage; use one of: {accepted}",
        )
    return value


def _validate_retention_amount(raw: str | None) -> Decimal | None:
    """Validate the operator-typed RIRPF art. 95 retención amount.

    A blank or absent value is a legitimate "no retención" declaration, not a
    refusal: most catalogue invoices carry none. Never derived from a rate --
    :class:`Invoice`'s own ``_validate_retencion_consistency`` is the single
    place that checks amount-vs-rate-vs-base_total consistency; this helper
    only rejects a malformed or negative token.
    """
    if raw is None:
        return None
    if not raw.strip():
        return None
    value = try_parse_canonical_decimal(raw, max_fraction_digits=2)
    if value is None:
        raise _WizardFieldError(field="retention_amount", reason=f"invalid decimal amount: {raw!r}")
    if value < 0:
        raise _WizardFieldError(field="retention_amount", reason="must not be negative")
    return value


def _validate_retention_rate(raw: str | None) -> Decimal | None:
    """Validate the operator-typed RIRPF art. 95 retención rate.

    A fraction, matching :attr:`Invoice.retention_rate` (0.15 for the general
    15 %, 0.07 during the RIRPF art. 95.1 párrafo 2 inicio-de-actividad
    window) -- never a percentage. The upper bound catches a percentage
    written into this fractional field.
    """
    if raw is None:
        return None
    if not raw.strip():
        return None
    value = try_parse_canonical_decimal(raw)
    if value is None:
        raise _WizardFieldError(field="retention_rate", reason=f"invalid decimal fraction: {raw!r}")
    if value < 0 or value > 1:
        raise _WizardFieldError(
            field="retention_rate",
            reason="must be a fraction between 0 and 1 (0.15 for a 15 % retención), not a percentage",
        )
    return value


def _validate_country_code(raw: str) -> str:
    try:
        return validate_country_code(raw)
    except InvoiceValidationError as exc:
        raise _WizardFieldError(field="country_code", reason=str(exc)) from exc


def _validate_currency(raw: str) -> str:
    try:
        return normalise_iso_4217_currency(raw)
    except CoreValidationError as exc:
        raise _WizardFieldError(field="currency", reason=resolve_error_message(exc)) from exc


#: The one country code that establishes domesticity. Named rather than inlined
#: because the Modelo 303 invoice screen decides the same fact the same way, and
#: two spellings of one discriminator is how they drift apart.
_DOMESTIC_COUNTRY = "ES"


def _derived_domestic_category(
    *,
    country_code: str,
    iva_rate: Decimal | None,
    on_date: date,
) -> IvaCategory | None:
    """Return the domestic category the rate denotes, or ``None`` to leave it unset.

    The rate-to-category mapping is DOMESTIC-ONLY, so deriving from the rate
    slot alone would stamp a domestic category on an export or an
    intra-community supply. Domesticity is therefore established first, on
    ``counterparty_country``, which is the same discriminator the Modelo 303
    invoice screen already uses -- adopting the incumbent leaves one
    discriminator where a second would have to agree with it.

    Returns ``None`` -- leaving the category unset -- in every case where
    domesticity or the tier is not affirmatively established. That is the safe
    direction and not a shortfall: an absent category is refused downstream,
    while a wrong one is believed.

    Three distinct silences, none of them a guess:

    * the counterparty is not domestic, or its country was never stated;
    * the line carries no rate at all;
    * the rate resolves to no tier, or to more than one, on that date. A rate
      outside its force window resolves to none, and an ambiguous rate must not
      be collapsed by picking the first.
    """
    if country_code != _DOMESTIC_COUNTRY or iva_rate is None:
        return None
    tiers = rate_kinds_for_declared_rate(EUMemberState.ES, iva_rate / Decimal("100"), on_date)
    if len(tiers) != 1:
        return None
    return domestic_categories_by_rate_kind().get(tiers[0])


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
    operation_date: str | None = None,
    # Required, never defaulted. The country routes both informativas and
    # decides domesticity for the Modelo 303 invoice screen, so assuming Spain
    # for an unstated counterparty would silently widen the domestic population
    # -- an undeclared fact resolving to the value that declares more. The CLI
    # option that feeds this is already required and says so in its own help;
    # this closes the same door on the application entry point, where a default
    # would have been reachable by any future caller that simply omitted it.
    country_code: str,
    notes: str = "",
    iva_category: IvaCategory | None = None,
    operation_type: IntracomOperationType | None = None,
    retention_rate: str | None = None,
    retention_amount: str | None = None,
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
        operation_date: Raw ISO-8601 date the operation was performed, when it
            differs from the issue date. Supplying it lets the record reach a
            DECLARED devengo rank; omitting it leaves the issue date standing
            as a proxy, which is a weaker basis for period attribution.
        taxable_base: Raw non-negative decimal taxable base string.
        iva_rate: Raw decimal IVA percentage string, or ``None``/blank for a
            base-only (exempt) invoice.
        currency: Raw ISO-4217 currency code (defaults are the caller's
            concern; this function validates whatever is passed).
        country_code: Raw ISO-3166 alpha-2 counterparty country code.
        notes: Free-text notes.
        iva_category: Optional intra-community IVA classification.
        operation_type: Optional Modelo 349 operation-type clave.
        retention_rate: Raw RIRPF art. 95 retención fraction string (0.15 /
            0.07), or ``None``/blank for no declared rate. Requires
            ``retention_amount``; never derives it.
        retention_amount: Raw RIRPF art. 95 retención euro amount string, or
            ``None``/blank for no declared retención.
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
    # A pre-validation placeholder, never an output. It is read below by the NIF
    # check, so a malformed country makes that check run under Spanish rules and
    # report a second, misleading error -- but the function raises whenever any
    # field error accumulated, so this value cannot escape. Do not "fix" it to
    # None: the NIF check needs a country, and the accumulate-then-refuse shape
    # is what lets one call name every failing field instead of the first.
    resolved_country = _collect_wizard_field(field_errors, lambda: _validate_country_code(country_code), fallback="ES")
    resolved_nif = _collect_wizard_field(
        field_errors,
        lambda: _validate_counterparty_nif(counterparty_nif, country=resolved_country),
        fallback="",
    )
    resolved_name = _collect_wizard_field(
        field_errors,
        lambda: _validate_counterparty_name(counterparty_name),
        fallback="",
    )
    resolved_number = _collect_wizard_field(
        field_errors,
        lambda: _validate_invoice_number(invoice_number),
        fallback="",
    )
    resolved_date = _collect_wizard_field(
        field_errors,
        lambda: _validate_invoice_date(invoice_date),
        fallback=None,
    )
    resolved_operation_date = (
        _collect_wizard_field(
            field_errors,
            lambda: _validate_operation_date(operation_date),
            fallback=None,
        )
        if operation_date is not None
        else None
    )
    resolved_base = _collect_wizard_field(
        field_errors,
        lambda: _validate_taxable_base(taxable_base),
        fallback=None,
    )
    resolved_rate = _collect_wizard_field(
        field_errors,
        lambda: _validate_iva_rate(iva_rate),
        fallback=None,
    )
    resolved_currency = _collect_wizard_field(
        field_errors,
        lambda: _validate_currency(currency),
        fallback="",
    )
    resolved_retention_amount = _collect_wizard_field(
        field_errors,
        lambda: _validate_retention_amount(retention_amount),
        fallback=None,
    )
    resolved_retention_rate = _collect_wizard_field(
        field_errors,
        lambda: _validate_retention_rate(retention_rate),
        fallback=None,
    )

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
        # Derived once, before both construction sites, so the built candidate
        # and the persisted record cannot disagree about the category. An
        # operator-supplied value always wins: this only fills a silence.
        effective_category = iva_category or _derived_domestic_category(
            country_code=resolved_country,
            iva_rate=resolved_rate,
            on_date=resolved_operation_date or resolved_date,
        )
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
            iva_category=effective_category,
            operation_type=operation_type,
            retention_rate=resolved_retention_rate,
            retention_amount=resolved_retention_amount,
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
        # Guarded idempotent retry (aeat-cli-contract):
        # the same fields were already submitted and catalogued under this
        # content-derived identity. Return the existing record; nothing is
        # re-written and no duplicate is raised.
        return InvoiceWizardResult(invoice=existing, already_existed=True)

    result = create_catalogue_invoice(
        invoice=candidate,
        repository=repo,
    )
    return InvoiceWizardResult(invoice=result.invoice, already_existed=False)
