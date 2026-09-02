"""Invoice payload normalization and validation helpers.

These helpers are the canonical implementation used by :mod:`.models`; the
public invoice record definitions and ``derive_invoice_id`` remain there.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from datetime import date, datetime
from decimal import Decimal
from typing import Final, cast

from ...core.decimal.coercion import coerce_decimal
from ...core.errors.hierarchy import CoreValidationError
from ...core.identity import IdentityError, tax_id_identity_token
from ...core.parsing import normalise_iso_4217_currency
from ...core.parsing.dates import parse_iso8601_date as _parse_iso8601_date
from ...core.type_adapters import OBJECT_TUPLE_ADAPTER
from ..iva.classification import InvoiceKind
from ..iva.identification import identification_state_for_printed_tax_identifier
from .errors import InvoiceValidationError
from .validators import validate_counterparty_tax_id, validate_country_code


def _coerce_date(value: object) -> date:
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            result = _parse_iso8601_date(value)
        except ValueError as exc:
            raise InvoiceValidationError(str(exc)) from exc
        if result is None:
            raise InvoiceValidationError("expected a date or ISO-8601 string")
        return result
    raise InvoiceValidationError("expected a date or ISO-8601 string")


def _coerce_datetime(value: object) -> datetime:
    """Coerce a record-lifecycle stamp, refusing anything that is not one.

    The model is strict, so a stamp serialised to an ISO-8601 string would not
    re-parse on load without this. It refuses rather than falling back: a
    stamp that cannot be read is an unreadable audit fact, and defaulting it
    to ``None`` would turn "this record's history is corrupt" into "this
    record has no history", which reads as normal.
    """
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError as exc:
            raise InvoiceValidationError(f"expected a datetime or ISO-8601 string, got {value!r}") from exc
    raise InvoiceValidationError("expected a datetime or ISO-8601 string")


def _coerce_optional[T](value: object, converter: Callable[[object], T]) -> T | None:
    if value is None:
        return None
    return converter(value)


def _coerce_optional_date(value: object) -> date | None:
    return _coerce_optional(value, _coerce_date)


def _coerce_optional_datetime(value: object) -> datetime | None:
    return _coerce_optional(value, _coerce_datetime)


def normalise_invoice_dates(payload: dict[str, object]) -> dict[str, object]:
    """Coerce every present date and datetime field on ``payload`` in place, and return it."""
    for key, converter in (
        ("issued_at", _coerce_date),
        ("fx_rate_date", _coerce_optional_date),
        ("operation_date", _coerce_optional_date),
        ("created_at", _coerce_optional_datetime),
        ("updated_at", _coerce_optional_datetime),
    ):
        if key in payload:
            payload[key] = converter(payload[key])
    return payload


def _judging[T](field: str, judge: Callable[[], T]) -> T:
    """Run a field validator, and name the field on the way out if it refuses.

    These validators judge a VALUE and say so: "country code must be an
    ISO-3166 alpha-2 value", "tax identifier must be exactly 9 characters".
    None of them names the field, because none of them knows it -- the same
    country validator judges an issuer country elsewhere.

    This normaliser DOES know, and it is the last place that does. It runs
    inside a model-level before-mode validator, so pydantic has no field
    location to attach: the error surfaces at ``root`` with the exception class
    and nothing else, and the operator-facing projection faithfully reports the
    location the raise site never provided. Naming the field further downstream
    would mean guessing it back from the message.

    The raised exception is ANNOTATED IN PLACE rather than rebuilt, and that is
    the load-bearing choice. Rebuilding it as ``type(error)(text)`` looks
    equivalent and is not: these errors carry structured attributes their
    constructor does not take -- a locale key among them -- so a rebuilt
    instance arrives with the message improved and the translation key gone.
    That was not reasoned out; a shipped assertion on the locale key caught it,
    which is the whole reason such an assertion exists.

    Only ``args[0]`` is touched, so the type, the translation key, the
    structured context and the traceback all survive.

    Stated reach, so this is not read as more than it is: the prefix reaches
    whoever reads the message -- a developer, a log, a traceback, and the CLI
    boundaries that render ``str(exc)``. A surface rendering the LOCALISED
    message resolves the translation key instead and is unchanged, so it still
    does not name the field. Carrying the field there means putting it in the
    structured context and giving the key a slot for it, which is a change to a
    localisation contract that is currently mid-migration; nothing here is
    built against a shape that is still moving.
    """
    try:
        return judge()
    except (InvoiceValidationError, IdentityError) as error:
        if error.args and isinstance(error.args[0], str) and not error.args[0].startswith(f"{field}: "):
            error.args = (f"{field}: {error.args[0]}", *error.args[1:])
        raise


def normalise_invoice_counterparty(payload: dict[str, object]) -> dict[str, object]:
    """Validate and normalise the counterparty country, tax id, and identification state in place."""
    country_raw = payload.get("counterparty_country")
    if isinstance(country_raw, str):
        payload["counterparty_country"] = _judging(
            "counterparty_country",
            lambda: validate_country_code(country_raw),
        )
    tax_id = payload.get("counterparty_tax_id")
    if isinstance(tax_id, str):
        tax_id_raw = tax_id_identity_token(tax_id)
        country = payload.get("counterparty_country")
        country_key = country if isinstance(country, str) else None
        payload["counterparty_tax_id"] = _judging(
            "counterparty_tax_id",
            lambda: validate_counterparty_tax_id(tax_id_raw, country=country_key),
        )
    # Every structured creation path -- bulk import, the wizard, the CLI, the
    # ingestion mapper -- reaches this one normaliser, so reading the
    # identification off the identifier HERE is what makes the fact present on
    # all of them rather than on whichever remembered to set it.
    #
    # The source is the printed IVA number's own prefix and nothing else. The
    # country sitting beside it in this same function is an address and is
    # deliberately not consulted: that substitution is the defect this field
    # exists to close. A caller that supplies the fact explicitly wins, because
    # an operator answering for a counterparty knows things a document does not
    # print.
    if payload.get("counterparty_identification_state") is None:
        printed = payload.get("counterparty_tax_id")
        payload["counterparty_identification_state"] = (
            identification_state_for_printed_tax_identifier(printed) if isinstance(printed, str) else None
        )
    return payload


def normalise_invoice_currency(payload: dict[str, object]) -> dict[str, object]:
    """Normalise the ISO 4217 currency field in place, and return the payload."""
    if "currency" in payload and isinstance(payload["currency"], str):
        try:
            payload["currency"] = normalise_iso_4217_currency(payload["currency"])
        except CoreValidationError as exc:
            raise InvoiceValidationError(str(exc)) from exc
    return payload


_REJECTED_VALUE_ECHO_LIMIT: Final[int] = 40
"""How much of an unreadable amount the refusal may quote back.

Echoing the value is what lets an operator find the offending cell, and these
fields are numeric by declared purpose, so what lands here is normally a
malformed number and short. The bound exists for the case where it is not: a
mis-mapped import column can put a name or an address into ``fx_rate``, and
nothing on the error path redacts a message body -- ``redact_for_cli_output`` is
applied at chosen call sites, not as a funnel over every error. A number long
enough to exceed this was never a number, so truncating costs the operator
nothing and bounds what an accident can disclose.
"""


def _bounded_rejected_value(value: object) -> str:
    """Return *value* quoted for an error message, truncated to the echo limit."""
    text = repr(value)
    if len(text) <= _REJECTED_VALUE_ECHO_LIMIT:
        return text
    return f"{text[:_REJECTED_VALUE_ECHO_LIMIT]}... ({len(text)} chars)"


def raise_first_invoice_violation(violations: Iterable[tuple[bool, str]]) -> None:
    """Raise on the first ``(violated, message)`` pair whose flag is true."""
    for violated, message in violations:
        if violated:
            raise InvoiceValidationError(message)


def require_optional_non_negative(value: Decimal | None, message: str) -> None:
    """Raise ``message`` when ``value`` is present and negative."""
    if value is not None and value < Decimal("0"):
        raise InvoiceValidationError(message)


def require_equal(actual: Decimal, expected: Decimal, message: str) -> None:
    """Raise ``message`` when ``actual`` does not equal ``expected``."""
    if actual != expected:
        raise InvoiceValidationError(message)


def normalise_invoice_monetary_fields(payload: dict[str, object]) -> dict[str, object]:
    """Coerce every present monetary field on ``payload`` to Decimal in place, and return it."""
    optional_fields = frozenset({"retention_rate", "retention_amount", "recargo_amount", "suplido_amount", "fx_rate"})
    for key in (
        "grand_total",
        "base_total",
        "iva_total",
        "retention_rate",
        "retention_amount",
        "recargo_amount",
        "suplido_amount",
        "fx_rate",
    ):
        if key not in payload:
            continue
        raw = payload[key]
        coerced = coerce_decimal(raw)
        # An explicit JSON null IS how this model's own model_dump_json()
        # represents "no value" for an Optional[Decimal] field -- the
        # standard persistence roundtrip writes every optional field,
        # unset ones included, rather than omitting them. Treating a
        # present-null the same as an absent key (both mean "no value")
        # is what makes that roundtrip symmetric. What must still raise is
        # a NON-null value that fails to parse (a string, a mis-mapped
        # import column) -- that is genuinely unreadable, not absent, and
        # coerce_decimal collapses both cases to None, so only the RAW
        # value being non-None can tell them apart here.
        if (raw is not None, coerced is None, key in optional_fields) == (True, True, True):
            raise InvoiceValidationError(
                f"{key} could not be parsed as a decimal: {_bounded_rejected_value(raw)}. "
                "Leave it out (or set it to null) to declare it absent; a value that "
                "cannot be read is not the same as no value.",
            )
        payload[key] = coerced
    return payload


_INVOICE_ID_REQUIRED_FIELDS = frozenset(
    {
        "kind",
        "invoice_number",
        "issued_at",
        "counterparty_tax_id",
        "currency",
        "grand_total",
    },
)


_INVOICE_IDENTITY_TYPE_RULES: Final[tuple[tuple[str, type[object], str], ...]] = (
    ("kind", InvoiceKind, "kind must be an InvoiceKind"),
    ("invoice_number", str, "invoice_number must be a string"),
    ("issued_at", date, "issued_at must be a date"),
    ("currency", str, "currency must be a string"),
    ("grand_total", Decimal, "grand_total must be a Decimal"),
)


def _validated_invoice_identity_values(
    payload: dict[str, object],
) -> tuple[InvoiceKind, str, date, str | None, str, Decimal]:
    for field, expected, message in _INVOICE_IDENTITY_TYPE_RULES:
        if not isinstance(payload[field], expected):
            raise InvoiceValidationError(message)
    counterparty_tax_id = payload["counterparty_tax_id"]
    if counterparty_tax_id is not None and not isinstance(counterparty_tax_id, str):
        raise InvoiceValidationError("counterparty_tax_id must be a string or None")
    return (
        cast(InvoiceKind, payload["kind"]),
        cast(str, payload["invoice_number"]),
        cast(date, payload["issued_at"]),
        counterparty_tax_id,
        cast(str, payload["currency"]),
        cast(Decimal, payload["grand_total"]),
    )


def derive_invoice_id_when_complete(
    payload: dict[str, object],
    *,
    derive_invoice_id: Callable[..., str],
) -> dict[str, object]:
    """Derive and set ``invoice_id`` once every identity field is present, or refuse a mismatch.

    Raises:
        InvoiceValidationError: When the payload already carries an
            ``invoice_id`` that disagrees with the derived one.
    """
    # counterparty_tax_id is the one identity-bearing field with a declared
    # default (None, for a factura simplificada outside the RD 1619/2012
    # art. 6.1.d mandatory cases): omitting the key entirely is now a legal
    # way to state "no tax id", not an incomplete payload, so it defaults here
    # before the completeness check rather than short-circuiting derivation.
    payload.setdefault("counterparty_tax_id", None)
    if not _INVOICE_ID_REQUIRED_FIELDS.issubset(payload):
        return payload
    kind, invoice_number, issued_at, counterparty_tax_id, currency, grand_total = _validated_invoice_identity_values(
        payload
    )
    derived = derive_invoice_id(
        kind=kind,
        invoice_number=invoice_number,
        issued_at=issued_at,
        counterparty_tax_id=counterparty_tax_id,
        currency=currency,
        grand_total=grand_total,
    )
    existing = payload.get("invoice_id")
    if existing is not None and str(existing).strip().lower() != derived:
        raise InvoiceValidationError("invoice_id must match the stable hash derived from identity fields")
    payload["invoice_id"] = derived
    return payload


def normalise_invoice_collections(
    payload: dict[str, object],
    *,
    normalise_linked_transaction_ids: Callable[[object], tuple[str, ...]],
) -> dict[str, object]:
    """Normalise the linked-transaction and line collections in place, and return the payload."""
    if "linked_transaction_ids" in payload:
        payload["linked_transaction_ids"] = normalise_linked_transaction_ids(payload["linked_transaction_ids"])
    if "lines" in payload and isinstance(payload["lines"], Sequence) and not isinstance(payload["lines"], str | bytes):
        payload["lines"] = OBJECT_TUPLE_ADAPTER.validate_python(payload["lines"])
    return payload


def normalise_invoice_payment_id(payload: dict[str, object]) -> dict[str, object]:
    """Validate and normalise ``payment_id`` to lowercase hex in place, or raise.

    Raises:
        InvoiceValidationError: When ``payment_id`` is a non-empty string that
            is not a 64-character lowercase hex digest.
    """
    if "payment_id" not in payload or not isinstance(payload["payment_id"], str):
        return payload
    normalized = payload["payment_id"].strip().lower()
    if not normalized:
        payload["payment_id"] = None
        return payload
    if len(normalized) != 64 or any(char not in "0123456789abcdef" for char in normalized):
        raise InvoiceValidationError("payment_id must be a 64-character lowercase hex digest")
    payload["payment_id"] = normalized
    return payload
