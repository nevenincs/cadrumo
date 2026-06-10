"""Pure parsing / validation / error-formatting helpers for the ledger CLI.

Split from :mod:`_ledger` to keep each module within the line budget. These are
stateless input-coercion and error-shaping utilities consumed by the
``aeat app ledger`` command bodies.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

import typer
from pydantic import ValidationError
from pydantic_core import ErrorDetails

from ...core.i18n import tr
from ...domain.categories import SpendingCategory
from ._common import _bad


def _invoice_link_error_bad_parameter() -> typer.BadParameter:
    return _bad(tr("errors.error.error_financial_invoices_invoice_link"))


def _parse_decimal(raw: str | None, *, label: str) -> Decimal | None:
    if raw is None:
        return None
    try:
        return Decimal(raw.strip())
    except (InvalidOperation, ValueError) as exc:
        raise _bad(tr("cli.ledger.errors.invalid_decimal", label=label, raw=raw)) from exc


def _parse_required_decimal(raw: str, *, label: str) -> Decimal:
    parsed = _parse_decimal(raw, label=label)
    assert parsed is not None
    return parsed


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
    """Render a 0..1 proportion as its percentage for operator context."""
    # ``format(..., "f")`` avoids scientific notation (e.g. ``5E+3``);
    # trim trailing zeros only when a fractional part is present.
    text = format(value * Decimal(100), "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return f"{text}%"


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
                value=format(value.normalize(), "f"),
                percent=_format_percent(value),
            )
        )
    return value


def _category_catalogue_text() -> str:
    """Return the comma-joined recognised spending-category ids."""
    return ", ".join(category.value for category in SpendingCategory)


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
            )
        ) from exc


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
        )
    )


def _format_validation_error(item: ErrorDetails) -> str:
    """Render one pydantic error entry as ``field: message`` text."""
    location = item.get("loc", ())
    message = str(item.get("msg", "")).removeprefix("Value error, ").strip()
    field_path = ".".join(str(part) for part in location if part != "__root__")
    if field_path:
        return f"{field_path}: {message}"
    return message

