"""Shared parsing, validation, and mutation-output helpers for the ledger CLI.

Split from :mod:`_ledger` to keep each module within the line budget. These are
stateless input-coercion and error-shaping utilities consumed by the
``aeat app ledger`` command bodies, including :class:`TransactionCatalogueRepository`
id resolution. Mutation emitters validate their result through the supplied
:class:`OutputSchema` subtype.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import Final

import typer
from pydantic import ValidationError
from pydantic_core import ErrorDetails

from ...application.cli_exception_preconditions import CliExceptionPrecondition, cli_exception_no_recovery_verdict
from ...application.ledger.source_jurisdiction import (
    SourceJurisdictionOutcome,
)
from ...application.ledger.source_jurisdiction import (
    resolve_source_jurisdiction as resolve_source_jurisdiction_requirement,
)
from ...core.decimal.formatting import format_decimal
from ...core.errors.hierarchy import CadrumoError
from ...core.i18n.render import tr
from ...core.unit_proportion import is_unit_proportion
from ...domain.calculations.registry.errors import RegistryValidationError
from ...domain.categories.spending_category_catalogue import require_spending_category, spending_category_tokens
from ...domain.contribuyente.renta_codes import FiscalResidency
from ...domain.deadlines.models import IrpfSpecialRegime
from ...domain.invoices.errors import InvoiceValidationError
from ...domain.transactions.errors import TransactionValidationError
from ._decimal_parsing import parse_decimal_amount, parse_optional_decimal_amount
from .common import attach_cli_policy_verdict, bad


def ledger_cli_no_recovery[ErrorT: CadrumoError](
    error: ErrorT,
    *,
    condition: CliExceptionPrecondition,
    facts: dict[str, str | int | bool],
) -> ErrorT:
    """Attach one typed, explicit no-recovery projection without flattening the error."""
    return attach_cli_policy_verdict(
        error,
        verdict=cli_exception_no_recovery_verdict(condition, facts=facts),
    )


def invoice_link_error_bad_parameter() -> typer.BadParameter:
    return bad(tr("errors.error.error_financial_invoices_invoice_link"))


def parse_decimal_option(raw: str | None, *, label: str) -> Decimal | None:
    return parse_optional_decimal_amount(raw, label=label)


def parse_required_decimal(raw: str, *, label: str) -> Decimal:
    return parse_decimal_amount(raw, label=label)


def parse_amount_magnitude(raw: str) -> Decimal:
    """Parse ``--amount`` as a non-negative magnitude.

    Flow is carried by ``--direction``, not by the sign of the amount. A
    negative input is refused at the CLI boundary with an instructive,
    localised error that names the accepted form (a non-negative amount plus
    ``--direction``) rather than a bare invalid, per the
    ``aeat-architecture-boundaries`` instructive-refusal rule.
    """
    parsed = parse_required_decimal(raw, label="amount")
    if parsed < Decimal("0"):
        raise bad(tr("cli.ledger.errors.negative_amount", raw=raw))
    return parsed


def _format_percent(value: Decimal) -> str:
    """Render a 0..1 proportion as its percentage for operator context.

    The trailing-zero trim is :meth:`~decimal.Decimal.normalize` inside
    :func:`~cadrumo.core.decimal.formatting.format_decimal` rather than a local
    ``rstrip("0").rstrip(".")``. The string form needs a guard the
    numeric form does not: stripping zeros from ``"100"`` yields ``"1"``,
    so the local spelling was only correct because it first tested for a
    decimal point. Normalising the value instead removes the trap rather
    than restating the guard, and the canonical helper is also what keeps
    a small proportion out of scientific notation.
    """
    return f"{format_decimal(value * Decimal(100), normalize=True)}%"


def validate_business_pct_range(value: Decimal | None) -> Decimal | None:
    """Refuse a business proportion outside the inclusive 0..1 range.

    The domain validator rejects an out-of-range proportion but its
    message ("business_pct must be within 0..1") names neither the
    offending value nor its percentage. An operator who types ``50``
    (meaning 50 %) or ``1.5`` then sees a bare invalid. Surface the
    value with its percent context here at the CLI boundary — the
    operator's first instructive surface — so the share is
    self-explanatory and the 0.5-for-50 % convention is shown.
    """
    if value is None:
        return None
    if not is_unit_proportion(value):
        raise bad(
            tr(
                "cli.ledger.errors.business_pct_out_of_range",
                value=format_decimal(value, normalize=True),
                percent=_format_percent(value),
            ),
        )
    return value


def validate_category_id(category_id: str | None) -> str | None:
    """Reject a `--category-id` value outside the closed spending taxonomy.

    The canonical category set is :class:`SpendingCategory` — the
    closed enum of deductible autónomo expense classes whose members
    map one-to-one onto the modelo registry bindings. Free text such
    as ``ventas_actividad`` is silently accepted by the bare string
    field, so an operator can miscategorise rows all year and only
    discover the drift when modelo calculations are wrong. Validating
    here refuses an unknown id immediately and points at
    ``aeat app ledger categories`` for the recognised catalogue.
    """
    if category_id is None:
        return None
    trimmed = category_id.strip()
    if not trimmed:
        return None
    try:
        return require_spending_category(trimmed).value
    except RegistryValidationError as exc:
        # Show one concrete valid id inline: operators repeatedly
        # guessed compound keys (`office:material_oficina`,
        # `office_material_oficina`); only the bare enum value is
        # accepted, so the refusal must demonstrate the exact shape.
        example = spending_category_tokens()[0].value
        raise bad(
            tr(
                "cli.ledger.errors.unknown_category",
                category=category_id,
                example=example,
            ),
        ) from exc


#: How this command words each condition that obliges the operator to state a
#: source jurisdiction. The rule lives in the application layer; only the
#: sentence is CLI-owned.
_SOURCE_JURISDICTION_REFUSAL_LOCALE_KEYS: Final[dict[SourceJurisdictionOutcome, str]] = {
    SourceJurisdictionOutcome.REQUIRED_NON_RESIDENT_IRNR: "cli.ledger.add.source_jurisdiction_required_irnr",
    SourceJurisdictionOutcome.REQUIRED_IMPATRIADO: "cli.ledger.add.source_jurisdiction_required_beckham",
}


def resolve_source_jurisdiction(
    operator_value: str | None,
    *,
    fiscal_residency: FiscalResidency | None,
    irpf_special_regime: IrpfSpecialRegime | None,
) -> str | None:
    """Word the application's source-jurisdiction decision for this command.

    Which conditions oblige a statement, and when Spain may be defaulted, is
    tax law about the taxpayer and is decided by
    :func:`~application.ledger.source_jurisdiction.resolve_source_jurisdiction`.
    What is left here is the part that is genuinely a property of this surface:
    the two refusals an operator can act on, and returning the value in the
    shape ``--source-jurisdiction`` is stamped from.

    ``None`` is returned unchanged and is not a refusal: it is the unresolved
    state the impatriado aggregation segregates rather than admitting, on the
    invariant that an unresolved jurisdiction is never coerced to ``ES``.
    """
    resolution = resolve_source_jurisdiction_requirement(
        operator_value,
        fiscal_residency=fiscal_residency,
        irpf_special_regime=irpf_special_regime,
    )
    refusal_key = _SOURCE_JURISDICTION_REFUSAL_LOCALE_KEYS.get(resolution.outcome)
    if refusal_key is not None:
        raise bad(tr(refusal_key))
    # Anything still demanding a statement has no sentence here, and the
    # default for an unworded obligation is to refuse rather than to stamp:
    # falling through would persist a jurisdiction the taxpayer's conditions
    # said had to be stated, and the stamp outlives the profile.
    if resolution.requires_operator_statement:
        raise bad(tr("cli.ledger.add.source_jurisdiction_required_irnr"))
    return resolution.jurisdiction


def ledger_validation_bad(error: ValidationError) -> typer.BadParameter:
    """Convert a leaked pydantic `ValidationError` into a specific refusal.

    The generic CLI error boundary wraps every leaked
    :exc:`pydantic.ValidationError` into the opaque "command input
    failed validation. Run ``aeat config repair``" message, discarding
    the real cause. The ledger command models raise precise validator
    messages (for example "business_pct must be None unless
    classification is MIXED"); this helper extracts those messages so
    the operator sees the actual illegal field combination rather than
    a misleading repair hint.
    """
    details = "; ".join(_format_validation_error(item) for item in error.errors())
    return bad(
        tr(
            "cli.ledger.errors.command_input_invalid",
            details=details or tr("cli.ledger.errors.command_input_invalid_fallback"),
        ),
    )


def ledger_transaction_validation_no_recovery(error: TransactionValidationError) -> TransactionValidationError:
    """Preserve a typed transaction failure with a fact-only terminal verdict."""
    return ledger_cli_no_recovery(
        error,
        condition=CliExceptionPrecondition.LEDGER_TRANSACTION_VALID,
        facts={"error_type": type(error).__name__},
    )


def ledger_invoice_validation_no_recovery(
    error: InvoiceValidationError | ValidationError,
) -> CadrumoError | None:
    """Project an operator invoice refusal without flattening other validation owners.

    Pydantic preserves an invoice validator's exception in ``ctx.error``.  A
    ledger command may therefore receive either the direct domain error or its
    pydantic transport wrapper.  Catalogue deserialisation also uses pydantic,
    but its corruption remains a persistence failure rather than an operator
    invoice-input refusal, so only an ``Invoice`` or ``InvoiceLine`` wrapper
    structurally carrying the invoice family is admitted here.
    """
    if isinstance(error, InvoiceValidationError):
        terminal_error: CadrumoError = error
    elif _is_pydantic_invoice_validation(error):
        from ...domain.invoices.models import Invoice, InvoiceLine
        from .errors import CliValidationBoundaryError

        record = Invoice if error.title == "Invoice" else InvoiceLine
        terminal_error = CliValidationBoundaryError(error, record=record)
    else:
        return None
    return ledger_cli_no_recovery(
        terminal_error,
        condition=CliExceptionPrecondition.LEDGER_INVOICE_VALID,
        facts={"invoice_valid": False},
    )


def _is_pydantic_invoice_validation(error: ValidationError) -> bool:
    """Return whether a validation wrapper carries an ``InvoiceValidationError``.

    The title admits the two model records the ledger commands construct; every
    detail must carry the nested domain error rather than an ordinary pydantic
    coercion refusal.  An invoice catalogue or envelope must retain its
    persistence owner even if it contains an invoice error.
    """
    if error.title not in {"Invoice", "InvoiceLine"}:
        return False
    details = error.errors(include_url=False)
    if not details:
        return False
    for detail in details:
        context = detail.get("ctx")
        nested = context.get("error") if isinstance(context, Mapping) else None
        if not (
            isinstance(nested, InvoiceValidationError)
            or isinstance(getattr(nested, "__cause__", None), InvoiceValidationError)
        ):
            return False
    return True


def _format_validation_error(item: ErrorDetails) -> str:
    """Render one pydantic error entry as ``field: message`` text."""
    location = item.get("loc", ())
    message = str(item.get("msg", "")).removeprefix("Value error, ").strip()
    field_path = ".".join(str(part) for part in location if part != "__root__")
    if field_path:
        return f"{field_path}: {message}"
    return message
