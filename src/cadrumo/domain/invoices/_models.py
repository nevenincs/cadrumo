"""Strict immutable models for the invoice catalogue.

Defines the pydantic v2 records that back :mod:`cadrumo.domain.invoices`:
:class:`InvoiceLine`, :class:`Invoice`, and the keyed
:class:`InvoiceCatalogue`. Every model is strict, frozen, and forbids
extra fields; identity-bearing fields on :class:`Invoice` are
canonicalised in a ``model_validator`` and the stable
:attr:`Invoice.invoice_id` is derived via :func:`derive_invoice_id`.
Counterparty identity validation is delegated to
:mod:`cadrumo.domain.invoices._validators`.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from datetime import date, datetime
from decimal import Decimal
from types import MappingProxyType
from typing import TYPE_CHECKING, Final, Self, cast, override

from pydantic import BaseModel, Field, field_serializer, field_validator, model_validator

from ...core import OBJECT_TUPLE_ADAPTER, STR_KEYED_MAPPING_ADAPTER, IntracomOperationType
from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core.decimal import coerce_decimal
from ...core.errors import CoreValidationError
from ...core.external_constants import DEFAULT_CURRENCY
from ...core.hashing import content_hash_hex
from ...core.identity import (
    BucketId,
    IdentityError,
    InvoiceId,
    TaxIdIdentityToken,
    tax_id_identity_token,
    validate_spanish_tax_id,
)
from ...core.money import CENT, round_to_cents
from ...core.parsing import normalise_iso_4217_currency
from ...core.parsing import parse_iso8601_date as _parse_iso8601_date
from ..identifiers import canonical_decimal_string
from ..iva import (
    EUMemberState,
    InvoiceKind,
    IvaCategory,
    IvaRateKind,
    IvaRateNotFoundError,
    OssIossRegime,
    TransactionKind,
    identification_state_for_printed_tax_identifier,
)
from ._enums import (
    InvoiceClass,
    InvoiceLegalMention,
    InvoiceOperationDateRole,
    IvaRate,
    PaymentStatus,
    iva_rate_percentage,
    iva_rate_slot_percentage,
)
from .errors import InvoiceValidationError
from ._payload_normalisation import normalise_invoice_enum_fields, normalise_invoice_string_fields

if TYPE_CHECKING:
    pass
from ._validators import (
    is_eu_member_state_code,
    validate_country_code,
    validate_iva_number,
)

"""Rounding slack allowed between a declared retención amount and rate.

The invoice-level totals are compared *exactly* because each is a sum of
line figures that were themselves already rounded to the cent. A retención
amount is not a sum: it is a rate applied to the base, so the recorded figure
legitimately differs from the recomputed product in the last cent depending on
where the issuer rounded. One cent is the same slack
:data:`~core.money.CENT` grants the line-level ``subtotal * iva_rate``
product, for the same reason.
"""

_SIMPLIFICADA_MANDATORY_TAX_ID_CATEGORIES: Final[frozenset[IvaCategory]] = frozenset(
    {
        # RD 1619/2012 art. 6.1.d, 1.º: entrega intracomunitaria exenta (LIVA art. 25).
        IvaCategory.INTRA_COMMUNITY_SUPPLY,
        # RD 1619/2012 art. 6.1.d, 2.º: the destinatario is the sujeto pasivo.
        IvaCategory.DOMESTIC_REVERSE_CHARGE,
    },
)
"""Categories where a factura simplificada's counterparty tax id stays mandatory.

Case 3.º of art. 6.1.d (a domestic operation where the issuer is established
in the territorio de aplicación del impuesto) is deliberately absent: this
record carries no field naming where its issuer is established, so that case
cannot be read from an :class:`Invoice` and is not modelled here.
"""

_COLLECTED_PAYMENT_STATUSES: Final[frozenset[PaymentStatus]] = frozenset(
    {PaymentStatus.PAID, PaymentStatus.PARTIALLY_PAID},
)
"""Payment states consistent with LIVA art. 75.Dos's "cobro total o parcial"."""


def derive_invoice_id(
    *,
    kind: InvoiceKind,
    invoice_number: str,
    issued_at: date,
    counterparty_tax_id: str | None,
    currency: str,
    grand_total: Decimal,
) -> str:
    """Return the stable invoice hash for one invoice record.

    The digest is computed over a canonical JSON payload so that two
    invoices with equal logical identity produce identical IDs regardless
    of whitespace or numeric formatting.

    Args:
        kind: Invoice direction (issued / received).
        invoice_number: AEAT-significant invoice number as printed on the
            document.
        issued_at: ISO calendar date printed on the invoice.
        counterparty_tax_id: Counterparty NIF / NIE / CIF / IVA number
            already validated and uppercased, or ``None`` for a factura
            simplificada issued outside the RD 1619/2012 art. 6.1.d cases
            that make the counterparty's tax id mandatory.
        currency: ISO-4217 currency code already uppercased.
        grand_total: Invoice grand total.

    Returns:
        A lowercase SHA-256 digest that uniquely identifies the invoice.
    """
    return content_hash_hex(
        {
            "counterparty_tax_id": counterparty_tax_id or "",
            "currency": currency,
            "grand_total": canonical_decimal_string(grand_total),
            "invoice_number": invoice_number,
            "issued_at": issued_at.isoformat(),
            "kind": kind.value,
        }
    )


def _is_hex_digest(value: str, *, length: int) -> bool:
    return len(value) == length and all(char in "0123456789abcdef" for char in value)


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


def _normalise_invoice_dates(payload: dict[str, object]) -> dict[str, object]:
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


def _normalise_invoice_counterparty(payload: dict[str, object]) -> dict[str, object]:
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
        validators: Mapping[str | None, Callable[[str], str]] = {
            None: lambda value: value,
            "ES": validate_spanish_tax_id,
        }
        validator = validators.get(
            country_key,
            lambda value: validate_iva_number(value, cast(str, country_key)),
        )
        payload["counterparty_tax_id"] = _judging("counterparty_tax_id", lambda: validator(tax_id_raw))
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


def _normalise_invoice_currency(payload: dict[str, object]) -> dict[str, object]:
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


def _raise_first_invoice_violation(violations: Iterable[tuple[bool, str]]) -> None:
    for violated, message in violations:
        if violated:
            raise InvoiceValidationError(message)


def _require_optional_non_negative(value: Decimal | None, message: str) -> None:
    if value is not None and value < Decimal("0"):
        raise InvoiceValidationError(message)


def _require_equal(actual: Decimal, expected: Decimal, message: str) -> None:
    if actual != expected:
        raise InvoiceValidationError(message)


def _normalise_invoice_monetary_fields(payload: dict[str, object]) -> dict[str, object]:
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


def _derive_invoice_id_when_complete(payload: dict[str, object]) -> dict[str, object]:
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


def _normalise_invoice_collections(payload: dict[str, object]) -> dict[str, object]:
    if "linked_transaction_ids" in payload:
        payload["linked_transaction_ids"] = _normalise_linked_transaction_ids(payload["linked_transaction_ids"])
    if "lines" in payload and isinstance(payload["lines"], Sequence) and not isinstance(payload["lines"], str | bytes):
        payload["lines"] = OBJECT_TUPLE_ADAPTER.validate_python(payload["lines"])
    return payload


def _normalise_invoice_payment_id(payload: dict[str, object]) -> dict[str, object]:
    if "payment_id" not in payload or not isinstance(payload["payment_id"], str):
        return payload
    normalized = payload["payment_id"].strip().lower()
    if not normalized:
        payload["payment_id"] = None
        return payload
    if not _is_hex_digest(normalized, length=64):
        raise InvoiceValidationError("payment_id must be a 64-character lowercase hex digest")
    payload["payment_id"] = normalized
    return payload


class InvoiceLine(BaseModel):
    """Immutable line item on an invoice."""

    model_config = _STRICT_FROZEN

    description: str = Field(min_length=1)
    quantity: Decimal
    unit_price: Decimal
    subtotal: Decimal
    iva_rate: IvaRate
    iva_amount: Decimal
    # Named for the taxonomy it belongs to, not "category" bare. This aggregate
    # already carries `Invoice.iva_category`, a completely unrelated axis: one
    # is the IVA TREATMENT of the operation, the other a SPENDING classification
    # of the line. Two fields called "category" on one aggregate is how a reader
    # reaches for the wrong one, and how a grep for either finds both.
    #
    # Currently written and persisted but read by no production consumer. Kept
    # rather than removed because per-line spending classification is a real
    # capability the aggregate is shaped for; the honest state is recorded here
    # so a reader does not infer from its presence that aggregation consumes it.
    spending_category_id: str | None = None
    oss_rate_kind: IvaRateKind | None = None

    @model_validator(mode="before")
    @classmethod
    def _coerce_inputs(cls, data: object) -> object:
        """Coerce JSON-decoded strings into their strict pydantic types."""
        if isinstance(data, cls):
            return data
        if not isinstance(data, Mapping):
            return data
        payload = STR_KEYED_MAPPING_ADAPTER.validate_python(data)
        for key in ("quantity", "unit_price", "subtotal", "iva_amount"):
            if key in payload:
                payload[key] = coerce_decimal(payload[key])
        if "iva_rate" in payload and isinstance(payload["iva_rate"], str):
            payload["iva_rate"] = IvaRate(payload["iva_rate"])
        if "oss_rate_kind" in payload and isinstance(payload["oss_rate_kind"], str):
            stripped = payload["oss_rate_kind"].strip()
            payload["oss_rate_kind"] = IvaRateKind(stripped) if stripped else None
        return payload

    @field_validator("description")
    @classmethod
    def _trim_description(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise InvoiceValidationError("description must not be blank")
        return trimmed

    @field_validator("spending_category_id")
    @classmethod
    def _validate_spending_category_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        if not trimmed:
            raise InvoiceValidationError("spending_category_id must not be blank")
        return trimmed

    @field_validator("quantity")
    @classmethod
    def _require_positive_quantity(cls, value: Decimal) -> Decimal:
        if value <= Decimal("0"):
            raise InvoiceValidationError("quantity must be strictly positive")
        return value

    @field_validator("unit_price", "subtotal", "iva_amount")
    @classmethod
    def _require_non_negative(cls, value: Decimal) -> Decimal:
        if value < Decimal("0"):
            raise InvoiceValidationError("monetary value must be non-negative")
        return value

    @model_validator(mode="after")
    def _validate_arithmetic(self) -> Self:
        expected_subtotal = (self.quantity * self.unit_price).quantize(Decimal("0.0001"))
        if abs(self.subtotal - expected_subtotal) > CENT:
            raise InvoiceValidationError("subtotal must equal quantity * unit_price within 1 cent")
        # The undated helper: this checks the line's ARITHMETIC, which needs the
        # number the operator applied, not whether the statute still offers it.
        # A line carries no date of its own, so the dated helper would resolve a
        # 2024 transitional-rate line against today and refuse to build it. The
        # in-force question is asked by the invoice-level validator below, which
        # has the operation date to ask it against.
        rate = iva_rate_slot_percentage(self.iva_rate)
        if self.oss_rate_kind is not None:
            return self
        if rate is None:
            if self.iva_amount != Decimal("0"):
                raise InvoiceValidationError("iva_amount must be zero for EXEMPT / NOT_SUBJECT lines")
        else:
            expected_iva = (self.subtotal * rate).quantize(Decimal("0.0001"))
            if abs(self.iva_amount - expected_iva) > CENT:
                raise InvoiceValidationError("iva_amount must equal subtotal * iva_rate within 1 cent")
        return self


class Invoice(BaseModel):
    """Strict frozen record for one issued or received invoice."""

    model_config = _STRICT_FROZEN

    invoice_id: InvoiceId
    bucket_id: BucketId | None = Field(default=None)
    kind: InvoiceKind
    invoice_class: InvoiceClass = InvoiceClass.ORDINARIA
    series: str | None = Field(default=None, min_length=1)
    invoice_number: str = Field(min_length=1)
    issued_at: date
    operation_date: date | None = None
    operation_date_role: InvoiceOperationDateRole | None = None
    counterparty_name: str = Field(min_length=1)
    counterparty_tax_id: TaxIdIdentityToken | None = None
    counterparty_country: str = Field(min_length=2, max_length=2)
    # Which Member State IVA-IDENTIFIES the counterparty, read from the prefix
    # of the IVA number the document printed. A DIFFERENT fact from
    # `counterparty_country` above, which is an address -- establishment -- and
    # never a source for this one: a Spanish-established acquirer can hold a
    # German IVA number, and a German-established one can purchase under a
    # Spanish NIF-IVA. Ley 37/1992 art. 25 exempts on this fact, not on the
    # address, so deriving one from the other lands in money in both
    # directions. `None` means the identification was not established -- never
    # that the party is identified nowhere, and above all never that it is
    # identified in Spain.
    counterparty_identification_state: EUMemberState | None = None
    # RD 1619/2012 art. 6.1.e: "Domicilio, tanto del obligado a expedir
    # factura como del destinatario de las operaciones." Named by legal role,
    # not by party-relative-to-us like `counterparty_*` above, because the
    # two roles swap sides with `kind`: for an ISSUED invoice the issuer is
    # self and the recipient is the counterparty; for a RECEIVED invoice the
    # issuer is the counterparty and the recipient is self. Each field is
    # what that document actually PRINTED -- never derived from a current
    # profile domicilio, which may differ from what an older invoice states.
    issuer_address: str | None = Field(default=None, min_length=1)
    recipient_address: str | None = Field(default=None, min_length=1)
    # RD 1619/2012 art. 6.1.j / .l / .m / .n / .o / .p: the fixed legal
    # notices ("menciones") the reglamento requires printed under specific
    # regimes. `exemption_reference` is art. 6.1.j's REFERENCE (a Directiva
    # 2006/112/CE provision, a LIVA article, or a bare "operación exenta"
    # statement) -- free text because the reglamento does not fix its
    # wording. `legal_mentions` carries the CLOSED, literally-quoted phrases
    # of art. 6.1.l/.m/.n/.o/.p (see `InvoiceLegalMention`). Both are
    # evidence of what the issuer printed; neither is derived from
    # `iva_category` below -- that would manufacture evidence of compliance
    # nobody observed on the document.
    exemption_reference: str | None = Field(default=None, min_length=1)
    legal_mentions: tuple[InvoiceLegalMention, ...] = ()
    base_total: Decimal
    iva_total: Decimal
    grand_total: Decimal
    currency: str = Field(min_length=3, max_length=3)
    lines: tuple[InvoiceLine, ...]
    payment_status: PaymentStatus
    linked_transaction_ids: tuple[str, ...] = ()
    notes: str = ""
    iva_category: IvaCategory | None = None
    operation_type: IntracomOperationType | None = None
    oss_ioss_regime: OssIossRegime | None = None
    oss_transaction_kind: TransactionKind | None = None
    retention_rate: Decimal | None = None
    retention_amount: Decimal | None = None
    recargo_amount: Decimal | None = None
    suplido_amount: Decimal | None = None
    rectifies_invoice_number: str | None = Field(default=None, min_length=1)
    payment_id: str | None = None
    fx_rate: Decimal | None = None
    fx_rate_date: date | None = None
    # WHO quoted the rate, at parity with the ledger transaction's own
    # `rate_source`. The rate and its date said what was applied and when, but
    # not on whose published series, so a stored euro total on a foreign invoice
    # could not be re-derived or challenged years later -- while the very same
    # conversion recorded on a bank row could. Set together with the rate, for
    # the same reason the rate and its date are: half a provenance is a claim
    # nothing can check.
    fx_rate_source: str | None = Field(default=None, min_length=1)
    # When this RECORD was entered and last amended, which is a different fact
    # from `issued_at` (when the document was issued) and from `operation_date`
    # (when the operation occurred). Both are outside the identity derived by
    # `derive_invoice_id`: folding a clock into the id would mint a new record
    # on every retry, which `aeat-cli-contract`
    # bars. They are last-seen body fields, not identity.
    #
    # Optional rather than required on purpose. A record that genuinely carries
    # no recorded entry time must say so, because the alternative is stamping
    # `now()` at load and manufacturing an audit fact nobody observed. `None`
    # here means "not recorded", never "recorded as now".
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @override
    def __hash__(self) -> int:
        return hash(self.invoice_id)

    @property
    def base_total_eur(self) -> Decimal | None:
        """``base_total`` in euro, or ``None`` when the invoice is unconverted."""
        return self._in_eur(self.base_total)

    @property
    def iva_total_eur(self) -> Decimal | None:
        """``iva_total`` in euro, or ``None`` when the invoice is unconverted."""
        return self._in_eur(self.iva_total)

    @property
    def grand_total_eur(self) -> Decimal | None:
        """``grand_total`` in euro, or ``None`` when the invoice is unconverted."""
        return self._in_eur(self.grand_total)

    @property
    def retention_amount_eur(self) -> Decimal | None:
        """The declared retención in euro, or ``None`` when there is none to convert.

        Returns ``None`` both when no retención was declared and when the
        invoice is unconverted, so a caller that needs to tell those apart must
        read :attr:`retention_amount` alongside it -- the same shape the three
        total accessors already have.
        """
        if self.retention_amount is None:
            return None
        return self._in_eur(self.retention_amount)

    @property
    def recargo_amount_eur(self) -> Decimal | None:
        """The recargo de equivalencia in euro, or ``None`` when there is none to convert.

        Same shape as :attr:`retention_amount_eur`: ``None`` covers both "no
        recargo was declared" and "the invoice is unconverted", so a caller
        needing to tell those apart reads :attr:`recargo_amount` alongside it.
        """
        if self.recargo_amount is None:
            return None
        return self._in_eur(self.recargo_amount)

    @property
    def suplido_amount_eur(self) -> Decimal | None:
        """The suplido (LIVA art. 78.Tres.3.º) in euro, or ``None`` when there is none to convert.

        Same shape as :attr:`recargo_amount_eur` and :attr:`retention_amount_eur`:
        ``None`` covers both "no suplido was declared" and "the invoice is
        unconverted".
        """
        if self.suplido_amount is None:
            return None
        return self._in_eur(self.suplido_amount)

    def _in_eur(self, amount: Decimal) -> Decimal | None:
        """Convert *amount* to euro using the stored rate.

        A euro invoice is already euro and converts to itself. A foreign
        invoice converts only when :attr:`fx_rate` was resolved at ingest;
        without it the euro value is genuinely unknown and is reported as
        ``None`` so the caller gates the invoice, rather than returning the
        face value and silently declaring foreign units as euro.
        """
        if self.currency == DEFAULT_CURRENCY:
            return amount
        if self.fx_rate is None:
            return None
        return round_to_cents(amount * self.fx_rate)

    def line_amount_eur(self, amount: Decimal) -> Decimal | None:
        """Convert a LINE-level native-currency amount to euro, or ``None`` if unconverted.

        :class:`InvoiceLine` carries no currency of its own -- every line on
        an invoice is denominated in that invoice's own :attr:`currency`
        (a single document states one currency for all its lines), so a line
        amount (``line.subtotal``, ``line.iva_amount``) converts through the
        SAME rate resolution as the invoice-level totals
        (:attr:`base_total_eur` and siblings), not a separate per-line
        mechanism. Delegating to :meth:`_in_eur` keeps that arithmetic
        consistent: summing ``line_amount_eur(line.subtotal)`` over every line
        equals :attr:`base_total_eur` exactly, the same way summing
        ``line.subtotal`` natively already equals :attr:`base_total`.

        Args:
            amount: A native-currency line amount, e.g. ``line.subtotal`` or
                ``line.iva_amount`` for one of this invoice's own
                :attr:`lines`.

        Returns:
            The euro-equivalent amount, or ``None`` when this invoice is
            foreign-currency with no resolved :attr:`fx_rate`.
        """
        return self._in_eur(amount)

    @model_validator(mode="before")
    @classmethod
    def _normalise_and_derive_invoice_id(cls, data: object) -> object:
        """Canonicalise identity-bearing fields and derive ``invoice_id``."""
        if isinstance(data, cls):
            return data
        if not isinstance(data, Mapping):
            return data
        payload = STR_KEYED_MAPPING_ADAPTER.validate_python(data)
        for normalise in (
            normalise_invoice_enum_fields,
            normalise_invoice_string_fields,
            _normalise_invoice_dates,
            _normalise_invoice_counterparty,
            _normalise_invoice_currency,
            _normalise_invoice_monetary_fields,
            _derive_invoice_id_when_complete,
            _normalise_invoice_collections,
            _normalise_invoice_payment_id,
        ):
            payload = normalise(payload)
        return payload

    @field_validator("base_total", "iva_total", "grand_total")
    @classmethod
    def _require_non_negative_totals(cls, value: Decimal) -> Decimal:
        if value < Decimal("0"):
            raise InvoiceValidationError("invoice totals must be non-negative")
        return value

    @field_validator("lines")
    @classmethod
    def _require_lines(cls, value: tuple[InvoiceLine, ...]) -> tuple[InvoiceLine, ...]:
        if not value:
            raise InvoiceValidationError("invoice must carry at least one line")
        return value

    @model_validator(mode="after")
    def _validate_fx_conversion_coherence(self) -> Self:
        """Reject an incoherent conversion stamp.

        The triple is all-or-nothing so a stored rate is always auditable: a
        rate without its date cannot be located in a published series, a rate
        without its source does not say whose series to look in, and a date or
        source without a rate converts nothing. A euro invoice carries none of
        them -- a stamp there would imply a conversion that never happened.
        """
        stamp_flags = (
            self.fx_rate is not None,
            self.fx_rate_date is not None,
            self.fx_rate_source is not None,
        )
        stamp_present = any(stamp_flags)
        fx_rate = self.fx_rate if self.fx_rate is not None else Decimal("0")
        _raise_first_invoice_violation(
            (
                (
                    (self.currency == DEFAULT_CURRENCY, stamp_present) == (True, True),
                    "a EUR invoice must not carry an fx conversion stamp",
                ),
                (
                    stamp_flags not in ((False, False, False), (True, True, True)),
                    "fx_rate, fx_rate_date and fx_rate_source must be set together",
                ),
                (
                    (stamp_flags[0], fx_rate <= Decimal("0")) == (True, True),
                    "fx_rate must be strictly positive",
                ),
            ),
        )
        return self

    @model_validator(mode="after")
    def _validate_line_rates_were_in_force(self) -> Self:
        """Refuse a line naming a rate the statute did not offer on the devengo date.

        The invoice is the first object that knows WHEN the operation happened,
        so it is the first that can ask whether each line's rate was legally
        available. The question is live because the taxonomy carries the RD-ley
        4/2024 food rates: 2 % and 4 % were both correct super-reducido rates in
        late 2024, so a slot cannot be checked against its tier alone, and a
        2025 invoice claiming 2 % is naming a rate already withdrawn.

        Checked against the operation date when one is recorded and the issue
        date otherwise -- RD 1619/2012 art. 6.1.i records the operation date
        precisely when it differs from expedition, and both readings are the
        LIVA art. 75 devengo date the rate binds to (art. 90.Dos).
        """
        devengo_date = self.operation_date or self.issued_at
        for line in self.lines:
            try:
                iva_rate_percentage(line.iva_rate, devengo_date)
            except IvaRateNotFoundError as exc:
                raise InvoiceValidationError(
                    f"line rate {line.iva_rate.name} was not in force on {devengo_date.isoformat()}: {exc}",
                ) from exc
        return self

    @model_validator(mode="after")
    def _validate_totals_and_exempt_invariants(self) -> Self:
        line_subtotal_sum = sum((line.subtotal for line in self.lines), start=Decimal("0"))
        line_iva_sum = sum((line.iva_amount for line in self.lines), start=Decimal("0"))
        _require_equal(self.base_total, line_subtotal_sum, "base_total must equal the exact sum of line subtotals")
        _require_equal(self.iva_total, line_iva_sum, "iva_total must equal the exact sum of line iva amounts")
        recargo = self.recargo_amount or Decimal("0")
        suplido = self.suplido_amount or Decimal("0")
        _require_equal(
            self.grand_total,
            self.base_total + self.iva_total + recargo + suplido,
            "grand_total must equal base_total + iva_total + recargo_amount + suplido_amount exactly",
        )
        all_non_numeric = all(iva_rate_slot_percentage(line.iva_rate) is None for line in self.lines)
        if all_non_numeric:
            # Checked before the grand-total equality below so the operator is
            # told which component is impossible, rather than being handed a
            # totals mismatch they would have to decompose themselves. The
            # recargo rides on the cuota of a taxable supply (LIVA art. 161),
            # so a supply bearing no cuota by law bears no recargo either. A
            # suplido is unrelated to whether the underlying supply is taxable
            # -- it is a disbursement made in the client's name (LIVA
            # art. 78.Tres.3.º) -- so it stays permitted here.
            _raise_first_invoice_violation(
                (
                    (
                        self.iva_total != Decimal("0"),
                        "iva_total must be zero when every line is EXEMPT or NOT_SUBJECT",
                    ),
                    (
                        recargo != Decimal("0"),
                        "recargo_amount must be zero when every line is EXEMPT or NOT_SUBJECT",
                    ),
                    (
                        self.grand_total != self.base_total + suplido,
                        "grand_total must equal base_total + suplido_amount when every line is EXEMPT or NOT_SUBJECT",
                    ),
                ),
            )
        return self

    @model_validator(mode="after")
    def _validate_retencion_consistency(self) -> Self:
        """Enforce the retención invariants, holding retención outside the totals.

        Retención is an IRPF settlement-side deduction, not a price component.
        The canonical per-invoice identity is
        ``total (contraprestación) = base_total + iva_total + recargo_amount
        + suplido_amount`` and, separately, ``cash = total - retención``: the withholding changes
        what the payer *transfers*, never what the operation *costs*. So
        :attr:`grand_total` stays retención-inclusive, and an issuer who nets
        the withholding out of the grand total is refused by
        :meth:`_validate_totals_and_exempt_invariants` above, whose equality is
        exact. Nothing here re-checks that; this validator governs only the two
        retención fields themselves. Recargo sits on the opposite side of that
        identity for the reason :meth:`_validate_recargo_consistency` gives.

        The retención base is the **base imponible**, not the grand total: RIRPF
        art. 95.1 withholds "sobre los ingresos íntegros satisfechos", and the
        IVA repercutido is not an ingreso of the issuer (PGC NRV 12.ª/14.ª). A
        rate checked against :attr:`grand_total` would therefore over-state the
        expected withholding by the whole cuota.

        :attr:`retention_rate` is a **fraction**, matching
        :func:`~cadrumo.domain.invoices.iva_rate_percentage` and the registry
        RIRPF art. 95 rates, both of which express a rate as ``pct / 100``. The
        upper bound is what catches a percentage written into a fractional
        field: ``15`` for "15 %" is refused rather than silently read as
        1500 %.

        An amount may stand alone -- the invoice records what was withheld
        without recording which rate produced it, which is how many issued
        invoices actually read. A rate may not: on its own it declares a
        proportion of nothing, and inferring the amount from it would
        manufacture a figure the document never stated.
        """
        _require_optional_non_negative(self.retention_amount, "retention_amount must be non-negative")
        if self.retention_rate is not None:
            if self.retention_rate < Decimal("0") or self.retention_rate > Decimal("1"):
                raise InvoiceValidationError(
                    "retention_rate must be a fraction between 0 and 1 (0.15 for a 15 % retención), not a percentage",
                )
            if self.retention_amount is None:
                raise InvoiceValidationError(
                    "retention_rate requires retention_amount; a rate alone declares no withheld figure",
                )
        if self.retention_amount is not None and self.retention_amount > self.base_total:
            raise InvoiceValidationError(
                "retention_amount must not exceed base_total; the retención base is the "
                "base imponible (ingresos íntegros), not the IVA-inclusive total",
            )
        if self.retention_rate is not None and self.retention_amount is not None:
            expected_retencion = (self.base_total * self.retention_rate).quantize(Decimal("0.0001"))
            if abs(self.retention_amount - expected_retencion) > CENT:
                raise InvoiceValidationError(
                    "retention_amount must equal base_total * retention_rate within 1 cent",
                )
        return self

    @model_validator(mode="after")
    def _validate_recargo_consistency(self) -> Self:
        """Enforce the recargo de equivalencia invariants, holding it inside the total.

        Recargo is the mirror image of retención and is deliberately modelled
        as its opposite. Retención is settlement-side: it reduces what the
        payer transfers without changing what the operation cost, so it sits
        *outside* :attr:`grand_total`. Recargo is a price component: LIVA
        art. 161 has the supplier repercutir it on the entrega alongside the
        cuota, and the comerciante minorista genuinely owes it, so it sits
        *inside* :attr:`grand_total`. Recording it outside would understate
        what the customer was actually invoiced.

        ``None`` and ``Decimal("0")`` are both accepted and mean different
        things. ``None`` is "this invoice makes no statement about recargo",
        which is the ordinary case for the overwhelming majority of invoices
        whose customer is not a comerciante minorista. An explicit zero is a
        positive declaration that the régimen was considered and does not
        apply. Neither is treated as evidence of the other, which is the whole
        reason the field is nullable rather than defaulted to zero -- an
        unrecorded surcharge must stay distinguishable from one that does not
        arise.

        The upper bound is :attr:`iva_total`. Every statutory recargo rate is
        far below its companion IVA rate (5.2 % against 21 %, 1.4 % against
        10 %, 0.5 % against 4 %), so a recargo exceeding the cuota it rides on
        is arithmetically impossible under any tier and is far more likely to
        be the cuota written into the wrong field. The bound is deliberately
        loose rather than a per-tier rate check: no recargo rate table ships in
        the registry, and inventing rate literals here would put regulatory
        values in a feature module.
        """
        if self.recargo_amount is None:
            return self
        _require_optional_non_negative(self.recargo_amount, "recargo_amount must be non-negative")
        if self.recargo_amount > self.iva_total:
            raise InvoiceValidationError(
                "recargo_amount must not exceed iva_total; every recargo tier is a smaller "
                "percentage than the IVA rate it accompanies (LIVA art. 161)",
            )
        return self

    @model_validator(mode="after")
    def _validate_suplido_consistency(self) -> Self:
        """Enforce the suplido invariant, holding it inside the total alongside recargo.

        A suplido (LIVA art. 78.Tres.3.º) is a sum paid by the issuer in the
        client's name and on their behalf under an explicit mandate --
        typically a third-party fee or disbursement passed through unchanged.
        It is excluded from the base imponible by law, so it cannot join
        :attr:`base_total` or :attr:`iva_total`; it is nonetheless something
        the client owes the issuer, so -- like recargo -- it joins
        :attr:`grand_total` and, through it, ``cash``. It takes a third
        position on the identity rather than becoming a second recargo: unlike
        recargo it carries no statutory rate and so no upper bound tied to
        another figure on the invoice, and unlike recargo it is not restricted
        to a taxable supply -- a suplido may accompany an exempt operation.

        ``None`` and ``Decimal("0")`` are both accepted and mean different
        things, for the same reason :meth:`_validate_recargo_consistency`
        keeps the two apart on recargo: ``None`` is "this invoice makes no
        statement about a suplido"; an explicit zero is "one was considered
        and none arose".
        """
        if self.suplido_amount is None:
            return self
        _require_optional_non_negative(self.suplido_amount, "suplido_amount must be non-negative")
        return self

    @model_validator(mode="after")
    def _validate_invoice_class_consistency(self) -> Self:
        """Enforce the RD 1619/2012 art. 6.1 invoice-class axis.

        A rectificativa is coupled to two facts art. 6.1 makes mandatory only
        for that class: a specific issuing series (art. 6.1.a.2.º) and the
        invoice it corrects (LIVA art. 89 requires a rectificativa to
        rectify a named prior invoice). Neither field is meaningful outside
        that class, so both are refused on any other one -- a stray
        ``rectifies_invoice_number`` on an ordinaria would silently assert a
        correction the invoice's own class denies.

        A factura simplificada's counterparty tax id is optional under art. 6
        UNLESS one of the three art. 6.1.d cases this table can read from the
        invoice's own data applies: an entrega intracomunitaria exenta (case
        1.º) or an operation where the destinatario is the sujeto pasivo
        (case 2.º, ``domestic_reverse_charge``). Case 3.º -- a domestic
        operation where the issuer is established in the territorio de
        aplicación del impuesto -- is NOT modelled here: this record carries
        no field stating where its issuer is established, so it is a declared
        gap rather than a guessed default. An ordinaria or rectificativa keeps
        the tax id mandatory unconditionally, unchanged from before this
        class axis existed.

        The simplificada relief applies to the ISSUED side only.
        :attr:`counterparty_tax_id` names a different party depending on
        :attr:`kind`: on an ISSUED invoice it is the destinatario's NIF --
        the fact art. 6.1.d's three cases actually govern -- but on a
        RECEIVED invoice it is the ISSUER's OWN identification, which
        art. 6.1.d's opening clause (and art. 7.1.d for a simplificada
        specifically) keeps mandatory regardless of class. A received
        simplificada with no supplier NIF is not a relieved case 3.º
        scenario; it is a document missing its own issuer's identity, so
        the relief must never fire for :attr:`kind` ``RECEIVED``.

        An entrega intracomunitaria exenta is refused SIMPLIFICADA outright,
        independent of the tax id question above: RD 1619/2012 art. 4.4.a)
        forbids a factura simplificada for this category altogether, so a
        document naming this category must never carry this class at all --
        it is not merely a case where the tax id relief does not apply. Art. 4
        also carries amount-based eligibility (the 400 EUR general and 3.000
        EUR sector-specific ceilings) and a closed sector list neither this
        record nor any field on it can express; that axis is a declared,
        documented gap, not modelled here or anywhere on this class.
        """
        category = self.iva_category
        missing_tax_id = self.counterparty_tax_id is None
        category_value = getattr(category, "value", "")
        relief_case = (self.invoice_class, self.kind) == (InvoiceClass.SIMPLIFICADA, InvoiceKind.ISSUED)
        _raise_first_invoice_violation(
            (
                (
                    (self.invoice_class is InvoiceClass.RECTIFICATIVA, not self.series) == (True, True),
                    "a factura rectificativa must be issued in a specific series (RD 1619/2012 art. 6.1.a.2.º)",
                ),
                (
                    (self.invoice_class is InvoiceClass.RECTIFICATIVA, not self.rectifies_invoice_number)
                    == (True, True),
                    "a factura rectificativa must name the invoice it rectifies (LIVA art. 89)",
                ),
                (
                    (self.invoice_class is not InvoiceClass.RECTIFICATIVA, self.rectifies_invoice_number is not None)
                    == (True, True),
                    "rectifies_invoice_number only applies to a factura rectificativa",
                ),
                (
                    (self.invoice_class, category) == (InvoiceClass.SIMPLIFICADA, IvaCategory.INTRA_COMMUNITY_SUPPLY),
                    "a factura simplificada must not be issued for an entrega intracomunitaria exenta "
                    "(RD 1619/2012 art. 4.4.a); issue an ordinaria or rectificativa instead",
                ),
                (
                    (missing_tax_id, not relief_case) == (True, True),
                    "counterparty_tax_id is required unless invoice_class is SIMPLIFICADA and kind is ISSUED; "
                    "on a RECEIVED invoice it names the issuer's own identity, which stays mandatory",
                ),
                (
                    (missing_tax_id, category in _SIMPLIFICADA_MANDATORY_TAX_ID_CATEGORIES) == (True, True),
                    "counterparty_tax_id is required on a factura simplificada whose iva_category is "
                    f"{category_value!r} (RD 1619/2012 art. 6.1.d)",
                ),
            ),
        )
        return self

    @model_validator(mode="after")
    def _validate_intracommunity_acquirer_identification(self) -> Self:
        """Refuse an entrega intracomunitaria exenta to a Spanish-IDENTIFIED acquirer.

        RD 1619/2012 art. 6.1.d requires the invoice state "el Número de
        Identificación Fiscal ... atribuido por la Administración ... de otro
        Estado miembro", and LIVA art. 25 exempts on that identification. A
        counterparty purchasing under a Spanish IVA identification therefore
        contradicts the declared category outright, and the contradiction is
        what this refuses.

        It reads the identification and NOT
        :attr:`counterparty_country`, which is an address. The two diverge in
        real trade, and keying this on the address refused a supply art. 25
        exempts: a Spanish-established acquirer holding a French IVA number is
        an intra-community acquirer, and could not previously be recorded at
        all. Establishment is a question about where a party IS, and it does
        not answer this one.

        ABSENT identification is NOT refused here. It is not a contradiction --
        it is a fact not yet recorded, and inferring it from the address is the
        substitution this whole field exists to remove. The aggregation gate
        withholds such a row with a resolvable review item naming the fact to
        supply, which is where an unanswered question belongs.

        Deliberately not an EU-membership check: Northern Ireland (``XI``) and
        a non-EU destination are both legitimate declared facts a later
        M349/export classification decides between; this guard only refuses the
        one identification the category can never legitimately name.
        """
        if (
            self.iva_category is IvaCategory.INTRA_COMMUNITY_SUPPLY
            and self.counterparty_identification_state is EUMemberState.ES
        ):
            raise InvoiceValidationError(
                "an entrega intracomunitaria exenta cannot name an acquirer purchasing under a "
                "Spanish IVA identification (LIVA art. 25); its country of establishment does not "
                "change that",
            )
        return self

    @model_validator(mode="after")
    def _validate_operation_date_consistency(self) -> Self:
        """Enforce the LIVA art. 75 devengo-date axis art. 6.1.i lets an invoice state.

        ``operation_date`` and ``operation_date_role`` travel together: a date
        with no stated role would leave a reader guessing which of art. 6.1.i's
        two clauses it answers, and a role with no date states nothing.

        A pago anticipado devengo (``ADVANCE_PAYMENT_RECEIVED``, LIVA
        art. 75.Dos) requires money to have actually been received -- "el
        cobro total o parcial del precio" -- so it is refused against a
        ``payment_status`` that states none was. It is also refused outright
        on ``INTRA_COMMUNITY_SUPPLY``: art. 75.Dos, párrafo segundo, excludes
        "las entregas de bienes comprendidas en el artículo 25" from the
        pagos-anticipados rule, so that category always devengues under
        art. 75.Uno.8.º regardless of any advance received.
        """
        if (self.operation_date is None) != (self.operation_date_role is None):
            raise InvoiceValidationError("operation_date and operation_date_role must be set together")
        if self.operation_date_role is InvoiceOperationDateRole.ADVANCE_PAYMENT_RECEIVED:
            if self.iva_category is IvaCategory.INTRA_COMMUNITY_SUPPLY:
                raise InvoiceValidationError(
                    "a pago anticipado devengo does not apply to an entrega intracomunitaria exenta "
                    "(LIVA art. 75.Dos, párrafo segundo, excludes art. 25 entregas)",
                )
            if self.payment_status not in _COLLECTED_PAYMENT_STATUSES:
                raise InvoiceValidationError(
                    "operation_date_role ADVANCE_PAYMENT_RECEIVED requires a collected payment_status "
                    "(PAID or PARTIALLY_PAID); LIVA art. 75.Dos devengues on actual cobro",
                )
        return self

    @model_validator(mode="after")
    def _validate_oss_ioss_axes(self) -> Self:
        """Validate the optional OSS/IOSS projection axes used by Modelo 369."""
        has_oss_line_rate = any(line.oss_rate_kind is not None for line in self.lines)
        axis_flags = (self.oss_ioss_regime is None, self.oss_transaction_kind is None)
        if axis_flags != (False, False):
            _raise_first_invoice_violation(
                (
                    (
                        (axis_flags, has_oss_line_rate) == ((True, True), True),
                        "oss_rate_kind requires invoice-level OSS/IOSS axes",
                    ),
                    (
                        axis_flags not in ((True, True), (False, False)),
                        "oss_ioss_regime and oss_transaction_kind must be supplied together",
                    ),
                ),
            )
            return self
        regime = cast(OssIossRegime, self.oss_ioss_regime)
        transaction_kind = cast(TransactionKind, self.oss_transaction_kind)

        allowed_kinds_by_regime: Mapping[OssIossRegime, frozenset[TransactionKind]] = {
            OssIossRegime.EXTERNAL_SCHEME: frozenset({TransactionKind.EXTERNAL_SCHEME_SERVICES}),
            OssIossRegime.UNION_SCHEME: frozenset(
                {
                    TransactionKind.OSS_UNION_GOODS_DISTANCE_SALE,
                    TransactionKind.OSS_UNION_GOODS_INTERFACE_FACILITATED,
                    TransactionKind.OSS_UNION_SERVICES,
                },
            ),
            OssIossRegime.IMPORT_SCHEME: frozenset({TransactionKind.IOSS_DISTANCE_SALE_LOW_VALUE}),
        }
        _raise_first_invoice_violation(
            (
                (
                    self.kind is not InvoiceKind.ISSUED,
                    "OSS/IOSS invoice projection only applies to issued invoices",
                ),
                (
                    self.counterparty_eu_member_state is None,
                    "OSS/IOSS invoice projection requires an EU destination member state",
                ),
                (
                    transaction_kind not in allowed_kinds_by_regime[regime],
                    "oss_transaction_kind is not valid for the supplied oss_ioss_regime",
                ),
            ),
        )
        return self

    @property
    def counterparty_eu_member_state(self) -> EUMemberState | None:
        """Return the substrate-typed EUMemberState for the counterparty, or ``None`` for non-EU.

        :attr:`counterparty_country` carries the raw uppercase ISO-3166-1
        alpha-2 code (validated at construction time). This typed
        accessor lets downstream consumers (Modelo 369 OSS bindings,
        intra-community classification, OSS classifier dispatch) work
        with the closed substrate enum without a per-call lowercase /
        membership check. Anchored to
        :data:`domain.invoices._validators.EU_MEMBER_STATE_CODES` which
        derives from :class:`cadrumo.domain.iva.EUMemberState`.
        """
        if not is_eu_member_state_code(self.counterparty_country):
            return None
        return EUMemberState(self.counterparty_country.lower())

    @property
    def counterparty_is_eu_member(self) -> bool:
        """Return ``True`` iff the counterparty is in one of the 27 EU Member States.

        Convenience predicate keyed off the substrate enum; equivalent
        to ``invoice.counterparty_eu_member_state is not None``.
        Modelo classification routes (OSS / IOSS / intra-community)
        gate on this predicate to decide which substrate flow path
        applies.
        """
        return self.counterparty_eu_member_state is not None


def _normalise_linked_transaction_ids(value: object) -> tuple[str, ...]:
    """Deduplicate-preserve-order and validate the shape of linked transaction IDs."""
    _raise_first_invoice_violation(
        (
            (
                isinstance(value, str | bytes),
                "linked_transaction_ids must be a sequence of IDs, not a single string",
            ),
            (not isinstance(value, Iterable), "linked_transaction_ids must be iterable"),
        ),
    )
    seen: dict[str, None] = {}
    for item in OBJECT_TUPLE_ADAPTER.validate_python(value):
        _raise_first_invoice_violation(
            ((not isinstance(item, str), "each linked_transaction_id must be a string"),),
        )
        normalized = cast(str, item).strip().lower()
        _raise_first_invoice_violation(
            (
                (
                    not _is_hex_digest(normalized, length=64),
                    "each linked_transaction_id must be a 64-character lowercase hex digest",
                ),
            ),
        )
        seen.setdefault(normalized, None)
    return tuple(seen.keys())


class InvoiceCatalogue(BaseModel):
    """Immutable invoice catalogue keyed by ``invoice_id``."""

    model_config = _STRICT_FROZEN

    invoices: Mapping[str, Invoice] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _coerce_catalogue_input(cls, data: object) -> object:
        """Accept a catalogue, its canonical payload, or an iterable of invoices.

        A mapping arrives here as one of two things: the canonical serialized
        payload, which carries its entries under ``invoices``, or the field
        kwargs of a direct construction, which for a catalogue with no entries
        is empty. A NON-EMPTY mapping with no ``invoices`` key is neither. It
        is a catalogue serialized without its wrapper -- a shape nothing in
        this codebase writes -- and it is refused rather than wrapped: wrapping
        promotes an arbitrary mapping into a catalogue whose keys no writer
        ever established to be invoice ids, and the resulting record is
        indistinguishable afterwards from one that was written correctly.
        """
        if isinstance(data, cls):
            return data
        if isinstance(data, Mapping):
            payload = STR_KEYED_MAPPING_ADAPTER.validate_python(data)
            if payload and "invoices" not in payload:
                raise InvoiceValidationError(
                    "invoice catalogue payload must carry its entries under the 'invoices' key; "
                    f"got a bare mapping of {len(payload)} top-level entries",
                )
            return payload
        if isinstance(data, Iterable) and not isinstance(data, str | bytes):
            invoices: dict[str, Invoice] = {}
            for item in OBJECT_TUPLE_ADAPTER.validate_python(data):
                invoice = item if isinstance(item, Invoice) else Invoice.model_validate(item)
                if invoice.invoice_id in invoices:
                    raise InvoiceValidationError(f"duplicate invoice_id: {invoice.invoice_id}")
                invoices[invoice.invoice_id] = invoice
            return {"invoices": invoices}
        return data

    @model_validator(mode="after")
    def _validate_mapping_keys(self) -> Self:
        for key, invoice in self.invoices.items():
            if key != invoice.invoice_id:
                raise InvoiceValidationError(f"catalogue key {key!r} does not match invoice_id {invoice.invoice_id!r}")
        return self

    @field_validator("invoices")
    @classmethod
    def _freeze_invoices(cls, value: Mapping[str, Invoice]) -> Mapping[str, Invoice]:
        return MappingProxyType(dict(value))

    @field_serializer("invoices")
    def _serialize_invoices(self, value: Mapping[str, Invoice]) -> dict[str, Invoice]:
        return dict(value)

    @classmethod
    def from_invoices(cls, invoices: Iterable[Invoice | Mapping[str, object]]) -> Self:
        """Build an immutable catalogue from an iterable of invoices.

        Args:
            invoices: Invoices or invoice payloads to load.

        Returns:
            A validated immutable invoice catalogue.
        """
        return cls.model_validate(tuple(invoices))

    @override
    def __iter__(self) -> Iterator[Invoice]:  # pyright: ignore[reportIncompatibleMethodOverride]  # ty: ignore[invalid-method-override]  # pyrefly: ignore[bad-override]  # reason: intentional Pydantic catalogue iteration adapter; the established public API yields Invoice records, not BaseModel field-value tuples
        """Iterate over catalogue invoices."""
        return iter(self.invoices.values())

    def __len__(self) -> int:
        """Return the number of invoices in the catalogue."""
        return len(self.invoices)

    def __contains__(self, invoice_id: object) -> bool:
        """Return whether the catalogue contains ``invoice_id``."""
        if isinstance(invoice_id, Invoice):
            return invoice_id.invoice_id in self.invoices
        if isinstance(invoice_id, str):
            return invoice_id in self.invoices
        return False

    def get(self, invoice_id: str) -> Invoice | None:
        """Fetch one invoice by ID if present.

        Args:
            invoice_id: Stable invoice identifier.

        Returns:
            The matching :class:`Invoice`, or ``None`` when absent.
        """
        return self.invoices.get(invoice_id)

    def values(self) -> Iterator[Invoice]:
        """Iterate over catalogue :class:`Invoice` records."""
        return iter(self.invoices.values())
