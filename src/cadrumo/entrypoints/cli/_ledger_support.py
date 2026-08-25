"""Shared parsing, validation, and mutation-output helpers for the ledger CLI.

Split from :mod:`_ledger` to keep each module within the line budget. These are
stateless input-coercion and error-shaping utilities consumed by the
``aeat app ledger`` command bodies, including :class:`TransactionCatalogueRepository`
id resolution. Mutation emitters validate their result through the supplied
:class:`OutputSchema` subtype.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import Protocol

import typer
from pydantic import ValidationError
from pydantic_core import ErrorDetails

from ...adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ...application.cli_exception_preconditions import CliExceptionPrecondition, cli_exception_no_recovery_verdict
from ...application.ledger import (
    ledger_transaction_payload,
    ledger_transaction_review_status,
    list_manual_transactions,
    resolve_transaction_id,
)
from ...core.decimal import format_decimal
from ...core.errors import CadrumoError
from ...core.i18n import tr
from ...core.json_contract import Notice, OutputSchema
from ...domain.categories import SpendingCategory
from ...domain.contribuyente import FiscalResidency
from ...domain.deadlines import IrpfSpecialRegime
from ...domain.invoices import InvoiceValidationError
from ...domain.transactions import Transaction, TransactionIdPrefixError, TransactionValidationError
from ._common import (
    _bad,
    attach_cli_policy_verdict,
    parse_decimal_amount,
    parse_optional_decimal_amount,
)


class _TransactionRepo(Protocol):
    """Structural interface consumed by :func:`_bucket_transaction_ids` and :func:`_resolve_id`."""

    @property
    def bucket_id(self) -> str: ...


def _emit_update_result(
    ctx: typer.Context,
    result_transaction: Transaction,
    bucket_id: str,
    events: tuple[str, ...],
    *,
    command: str,
    result_cls: type[OutputSchema],
    notices: list[Notice] | None = None,
    prepend_lines: Sequence[str] = (),
    extra_lines: Sequence[str] = (),
) -> None:
    """Emit the canonical single-transaction ledger mutation result.

    ``notices`` rides the shared envelope notices channel
    (``aeat-cli-contract``); mutation verbs pass any
    non-blocking advisory here rather than re-modelling it as a bespoke result
    field.

    ``prepend_lines`` and ``extra_lines`` carry the text a verb needs around the
    five quintet lines -- a ``reaffirmed`` marker ahead of them, an
    idempotent-noop or prorrata note after them. They exist so a verb with
    something extra to say still emits the quintet from here: without them the
    only way to add a line was to rebuild the whole payload and call
    :func:`emit_envelope` directly, which is how two verbs ended up
    hand-maintaining a copy of the shape this function owns. The same idiom as
    ``_emit_llm_single_classify``'s ``extra_lines``.
    """
    transaction_payload = ledger_transaction_payload(result_transaction)
    review_status = ledger_transaction_review_status(result_transaction)
    result = result_cls.model_validate(
        {
            "bucket_id": bucket_id,
            "transaction_id": result_transaction.transaction_id,
            "bucket_event_ids": list(events),
            "review_status": review_status,
            "transaction": transaction_payload.model_dump(mode="json"),
        },
    )
    emit_envelope(
        ctx,
        command=command,
        result=result,
        lines=[
            *prepend_lines,
            f"{tr('cli.ledger.labels.id')}\t{result_transaction.transaction_id}",
            f"{tr('cli.ledger.labels.date')}\t{transaction_payload.date}",
            f"{tr('cli.ledger.labels.amount')}\t{transaction_payload.amount}",
            f"{tr('cli.ledger.labels.description')}\t{transaction_payload.description}",
            f"{tr('cli.ledger.labels.review_status')}\t{review_status}",
            *extra_lines,
        ],
        notices=notices,
    )


def _bucket_transaction_ids(transaction_repository: _TransactionRepo) -> tuple[str, ...]:
    """Return the full transaction ids known to the active bucket."""
    bucket_id = transaction_repository.bucket_id
    results = list_manual_transactions(
        bucket_id=bucket_id,
        transaction_repository=transaction_repository
        if isinstance(transaction_repository, TransactionCatalogueRepository)
        else None,
    )
    return tuple(result.transaction.transaction_id for result in results)


def _ledger_cli_no_recovery[ErrorT: CadrumoError](
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


def _resolve_id(transaction_repository: _TransactionRepo, prefix: str) -> str:
    """Resolve a CLI-supplied id or unambiguous prefix to a live transaction id.

    The single shared CLI-boundary wrapper over the canonical
    :func:`resolve_transaction_id`. Used by the *mutation*
    verbs (update, classify, allocate, link, attach, doclink, archive, stash,
    restore, remove, split, merge). It matches only ids of rows still in the
    catalogue, because a mutation always targets a live row. Read verbs use the
    lineage-following ``_resolve_read_id`` in :mod:`_ledger` instead.
    """
    try:
        return resolve_transaction_id(prefix, _bucket_transaction_ids(transaction_repository))
    except TransactionIdPrefixError as exc:
        raise _ledger_cli_no_recovery(
            exc,
            condition=CliExceptionPrecondition.LEDGER_TRANSACTION_ID_RESOLVES,
            facts={"transaction_id_resolves": False},
        ) from None


def _invoice_link_error_bad_parameter() -> typer.BadParameter:
    return _bad(tr("errors.error.error_financial_invoices_invoice_link"))


def _parse_decimal(raw: str | None, *, label: str) -> Decimal | None:
    return parse_optional_decimal_amount(raw, label=label)


def _parse_required_decimal(raw: str, *, label: str) -> Decimal:
    return parse_decimal_amount(raw, label=label)


def _parse_amount_magnitude(raw: str) -> Decimal:
    """Parse ``--amount`` as a non-negative magnitude.

    Flow is carried by ``--direction``, not by the sign of the amount. A
    negative input is refused at the CLI boundary with an instructive,
    localised error that names the accepted form (a non-negative amount plus
    ``--direction``) rather than a bare invalid, per the
    ``aeat-architecture-boundaries`` instructive-refusal rule.
    """
    parsed = _parse_required_decimal(raw, label="amount")
    if parsed < Decimal("0"):
        raise _bad(tr("cli.ledger.errors.negative_amount", raw=raw))
    return parsed


def _format_percent(value: Decimal) -> str:
    """Render a 0..1 proportion as its percentage for operator context.

    The trailing-zero trim is :meth:`~decimal.Decimal.normalize` inside
    :func:`~cadrumo.core.decimal.format_decimal` rather than a local
    ``rstrip("0").rstrip(".")``. The string form needs a guard the
    numeric form does not: stripping zeros from ``"100"`` yields ``"1"``,
    so the local spelling was only correct because it first tested for a
    decimal point. Normalising the value instead removes the trap rather
    than restating the guard, and the canonical helper is also what keeps
    a small proportion out of scientific notation.
    """
    return f"{format_decimal(value * Decimal(100), normalize=True)}%"


def _validate_business_pct_range(value: Decimal | None) -> Decimal | None:
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
    if not Decimal("0") <= value <= Decimal("1"):
        raise _bad(
            tr(
                "cli.ledger.errors.business_pct_out_of_range",
                value=format_decimal(value, normalize=True),
                percent=_format_percent(value),
            ),
        )
    return value


def _validate_category_id(category_id: str | None) -> str | None:
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
        return SpendingCategory(trimmed).value
    except ValueError as exc:
        # Show one concrete valid id inline: operators repeatedly
        # guessed compound keys (`office:material_oficina`,
        # `office_material_oficina`); only the bare enum value is
        # accepted, so the refusal must demonstrate the exact shape.
        example = next(iter(SpendingCategory)).value
        raise _bad(
            tr(
                "cli.ledger.errors.unknown_category",
                category=category_id,
                example=example,
            ),
        ) from exc


def _resolve_source_jurisdiction(
    operator_value: str | None,
    *,
    fiscal_residency: FiscalResidency | None,
    irpf_special_regime: IrpfSpecialRegime | None,
) -> str | None:
    """Stamp the profile-conditional default for ``--source-jurisdiction``.

    Defaults to ``ES`` only on a DECLARED residency. An undeclared residency
    resolves to ``None`` — the unresolved state the impatriado aggregation
    already handles explicitly, segregating such a row out of the base with a
    typed unresolved-jurisdiction issue rather than admitting it.

    That aggregation documents the invariant this function must not break: an
    unresolved jurisdiction "is NEVER silently coerced to ``ES``". Returning
    ``ES`` here for a profile that has declared no residency performed exactly
    that coercion at the boundary, so the ``None`` never reached the layer built
    to refuse it, and foreign-source income folded into the Spanish base. The
    stamp is persisted on the transaction, so it outlived the profile later
    being completed.
    """
    if operator_value is not None:
        return operator_value
    if fiscal_residency is FiscalResidency.NON_RESIDENT_IRNR:
        raise _bad(tr("cli.ledger.add.source_jurisdiction_required_irnr"))
    if irpf_special_regime is IrpfSpecialRegime.IMPATRIADO:
        raise _bad(tr("cli.ledger.add.source_jurisdiction_required_beckham"))
    if fiscal_residency is None:
        return None
    return "ES"


def _resolve_business_pct_with_censo(
    *,
    bucket_id: str,
    active_profile: str | None,
    category_id: str | None,
    operator_supplied: Decimal | None,
) -> Decimal | None:
    """Stamp the censo-derived business_pct when the operator omits one."""
    from ...application.ledger import censo_business_pct_for
    from ...application.user_profile import CensoSyncService

    if operator_supplied is not None:
        return operator_supplied
    if category_id is None or active_profile is None:
        return operator_supplied
    try:
        category_enum = SpendingCategory(category_id.strip())
    except ValueError:
        return operator_supplied
    sync_service = CensoSyncService(bucket_id=bucket_id)
    raw_afectacion: Decimal | None = sync_service.bound_raw_afectacion_ratio(profile_id=active_profile)
    if raw_afectacion is None:
        return operator_supplied
    return censo_business_pct_for(category_enum, raw_afectacion)


def _ledger_validation_bad(error: ValidationError) -> typer.BadParameter:
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
    return _bad(
        tr(
            "cli.ledger.errors.command_input_invalid",
            details=details or tr("cli.ledger.errors.command_input_invalid_fallback"),
        ),
    )


def _ledger_transaction_validation_no_recovery(error: TransactionValidationError) -> TransactionValidationError:
    """Preserve a typed transaction failure with a fact-only terminal verdict."""
    return _ledger_cli_no_recovery(
        error,
        condition=CliExceptionPrecondition.LEDGER_TRANSACTION_VALID,
        facts={"error_type": type(error).__name__},
    )


def _ledger_invoice_validation_no_recovery(
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
        from ._errors import CliValidationBoundaryError

        terminal_error = CliValidationBoundaryError(error)
    else:
        return None
    return _ledger_cli_no_recovery(
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
        if not isinstance(nested, InvoiceValidationError):
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
