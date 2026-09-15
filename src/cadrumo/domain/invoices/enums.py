"""Registry-projected enumerations and tokens for invoice records.

Defines :class:`IvaRate` and :class:`PaymentStatus`.  ``IvaRate`` is a
registry-validated token only: the legal number behind a numeric slot is
resolved from the IVA governed-fact authority at the explicit devengo date
held by the composition boundary.

:class:`IvaRate` keeps the typed token role for invoice records, and the IVA
facade is the sole legal-grade authority for which rates existed when.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING, Self

from pydantic import GetCoreSchemaHandler
from pydantic_core import CoreSchema, core_schema

from ...core.errors.hierarchy import CoreValidationError
from ..calculations.registry.errors import RegistryValidationError
from ..calculations.registry.facts.resolution import MappingFactQuery, ResolvedMappingFact
from ..calculations.registry.governed_fact_scope import GovernedFactSource, governed_facts_in_scope
from ..calculations.registry.iva_rate_kind_catalogue import (
    require_iva_rate_kind,
    resolve_iva_rate_kind_catalogue,
)
from ..calculations.registry.schema_base import DateAxis
from ..iva.errors import IvaRateNotFoundError
from ..iva.lookup import rate_kinds_for_declared_rate, rate_table_covers, resolve_iva_rate
from ..iva.rates import iva_rate_record_from_fact
from ..iva.schema import IvaRateKind, spanish_eu_member_state

if TYPE_CHECKING:
    from ..calculations.registry.authority import PinnedAuthorityOperation


class IvaRate(str):
    """Opaque invoice-rate token projected from the dated slot catalogue.

    The slot membership and its substrate semantics are governed by the IVA
    rate-slot fact. A token can only be constructed by the registry projection;
    the numeric rate itself remains a separate dated schedule fact.
    """

    __slots__ = ()

    def __new__(cls, value: str, *, _registry_validated: bool = False) -> Self:
        """Construct a token only after registry membership is established."""
        if not _registry_validated:
            raise TypeError("IvaRate tokens must be projected from the registry")
        if not isinstance(value, str) or not value:
            raise ValueError("IvaRate token must be a non-empty string")
        return str.__new__(cls, value)

    @classmethod
    def from_registry(cls, value: str) -> Self:
        """Materialise one token from the typed facts projection."""
        return cls(value, _registry_validated=True)

    @classmethod
    def _require_registry_token(cls, value: object) -> Self:
        """Resolve Pydantic input through the scoped rate-slot fact."""
        if isinstance(value, cls):
            return value
        if isinstance(value, str):
            try:
                resolved = resolve_iva_rate_token(value, date.today())
                return cls.from_registry(str(resolved))
            except RegistryValidationError as exc:
                raise ValueError("IvaRate token is not declared by the scoped facts registry") from exc
        raise TypeError("IvaRate must be a registry-projected token or string")

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        _source_type: object,
        _handler: GetCoreSchemaHandler,
    ) -> CoreSchema:
        """Expose a scoped, resolver-backed token schema with string serialization."""
        return core_schema.no_info_plain_validator_function(
            cls._require_registry_token,
            json_schema_input_schema=core_schema.str_schema(),
            serialization=core_schema.to_string_ser_schema(),
        )

    @property
    def name(self) -> str:
        """Return the persisted token for diagnostics and structured context."""
        return str(self)

    @property
    def value(self) -> str:
        """Return the persisted token for serialization boundaries."""
        return str(self)


class PaymentStatus(StrEnum):
    """Lifecycle states for an invoice payment.

    Attributes:
        PAID: Settled in full.
        PENDING: Awaiting payment within agreed terms.
        PARTIALLY_PAID: Partially settled; remainder outstanding.
        OVERDUE: Past the due date and still outstanding.
        CANCELLED: Cancelled, regardless of whether previously paid.
    """

    PAID = "PAID"
    PENDING = "PENDING"
    PARTIALLY_PAID = "PARTIALLY_PAID"
    OVERDUE = "OVERDUE"
    CANCELLED = "CANCELLED"


class InvoiceClass(str):
    """Opaque invoice-class token projected from the dated facts registry."""

    __slots__ = ()

    def __new__(cls, value: str, *, _registry_validated: bool = False) -> Self:
        """Construct an invoice-class token after registry validation."""
        if not _registry_validated:
            raise TypeError("InvoiceClass tokens must be projected from the facts registry")
        if not isinstance(value, str) or not value:
            raise ValueError("InvoiceClass token must be a non-empty string")
        return str.__new__(cls, value)

    @classmethod
    def from_registry(cls, value: str) -> Self:
        """Construct the typed value from its canonical registry token."""
        return cls(value, _registry_validated=True)

    @classmethod
    def _require_registry_token(cls, value: object) -> Self:
        if isinstance(value, cls):
            return value
        raise CoreValidationError("InvoiceClass must be a registry-projected token")

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        _source_type: object,
        _handler: GetCoreSchemaHandler,
    ) -> CoreSchema:
        """Expose registry-only validation and string serialization to Pydantic."""
        return core_schema.no_info_plain_validator_function(
            cls._require_registry_token,
            json_schema_input_schema=core_schema.str_schema(),
            serialization=core_schema.to_string_ser_schema(),
        )

    @property
    def value(self) -> str:
        """Return the canonical registry token for serialization."""
        return str(self)

    @property
    def name(self) -> str:
        """Return the canonical registry token for diagnostics."""
        return str(self)


class InvoiceOperationDateRole(str):
    """Opaque operation-date role projected from the dated facts registry."""

    __slots__ = ()

    def __new__(cls, value: str, *, _registry_validated: bool = False) -> Self:
        """Construct an operation-date role token after registry validation."""
        if not _registry_validated:
            raise TypeError("InvoiceOperationDateRole tokens must be projected from the facts registry")
        if not isinstance(value, str) or not value:
            raise ValueError("InvoiceOperationDateRole token must be a non-empty string")
        return str.__new__(cls, value)

    @classmethod
    def from_registry(cls, value: str) -> Self:
        """Construct the typed value from its canonical registry token."""
        return cls(value, _registry_validated=True)

    @classmethod
    def _require_registry_token(cls, value: object) -> Self:
        if isinstance(value, cls):
            return value
        raise CoreValidationError("InvoiceOperationDateRole must be a registry-projected token")

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        _source_type: object,
        _handler: GetCoreSchemaHandler,
    ) -> CoreSchema:
        """Expose registry-only validation and string serialization to Pydantic."""
        return core_schema.no_info_plain_validator_function(
            cls._require_registry_token,
            json_schema_input_schema=core_schema.str_schema(),
            serialization=core_schema.to_string_ser_schema(),
        )

    @property
    def value(self) -> str:
        """Return the canonical registry token for serialization."""
        return str(self)

    @property
    def name(self) -> str:
        """Return the canonical registry token for diagnostics."""
        return str(self)


def require_invoice_class(value: object, *, effective_date: date | None = None) -> InvoiceClass:
    """Resolve an invoice-class token through the dated facts authority."""
    from ..calculations.registry.invoice_legal_classification import require_invoice_class as _require

    return _require(value, effective_date=effective_date)


def require_invoice_operation_date_role(
    value: object,
    *,
    effective_date: date | None = None,
) -> InvoiceOperationDateRole:
    """Resolve an operation-date role through the dated facts authority."""
    from ..calculations.registry.invoice_legal_classification import (
        require_invoice_operation_date_role as _require,
    )

    return _require(value, effective_date=effective_date)


def invoice_class_ordinaria(*, effective_date: date | None = None) -> InvoiceClass:
    """Return the registry-declared ordinary invoice-class token."""
    from ..calculations.registry.invoice_legal_classification import invoice_class_ordinaria as _token

    return _token(effective_date=effective_date)


def invoice_class_simplificada(*, effective_date: date | None = None) -> InvoiceClass:
    """Return the registry-declared simplified invoice-class token."""
    from ..calculations.registry.invoice_legal_classification import invoice_class_simplificada as _token

    return _token(effective_date=effective_date)


def invoice_class_rectificativa(*, effective_date: date | None = None) -> InvoiceClass:
    """Return the registry-declared corrective invoice-class token."""
    from ..calculations.registry.invoice_legal_classification import invoice_class_rectificativa as _token

    return _token(effective_date=effective_date)


def operation_performed_role(*, effective_date: date | None = None) -> InvoiceOperationDateRole:
    """Return the registry-declared performed-operation date role."""
    from ..calculations.registry.invoice_legal_classification import operation_performed_role as _token

    return _token(effective_date=effective_date)


def advance_payment_received_role(*, effective_date: date | None = None) -> InvoiceOperationDateRole:
    """Return the registry-declared advance-payment date role."""
    from ..calculations.registry.invoice_legal_classification import advance_payment_received_role as _token

    return _token(effective_date=effective_date)


def default_invoice_class(*, effective_date: date | None = None) -> InvoiceClass:
    """Return the registry-declared default invoice-class token."""
    return invoice_class_ordinaria(effective_date=effective_date)


@dataclass(frozen=True, slots=True)
class InvoiceLegalMentionDeclaration:
    """One registry-projected fixed legal notice for an invoice."""

    token: str
    phrase: str
    provision: str
    legal_refs: tuple[str, ...]
    declares: str | None
    expects_repercutido_line: bool


class InvoiceLegalMention(str):
    """Opaque token for a printed notice validated against the dated registry.

    The legal-mention vocabulary is not a Python enum. A token can only be
    created by :func:`resolve_invoice_legal_mention`, after the selected
    registry variant has proved that its exact token is governed. This keeps
    invoice evidence typed while making missing or stale registry data fail
    closed instead of silently accepting an invented member.
    """

    __slots__ = ()

    def __new__(cls, value: str, *, _registry_validated: bool = False) -> Self:
        """Construct a token only after registry membership is established."""
        if not _registry_validated:
            raise TypeError("InvoiceLegalMention tokens must be projected from the registry")
        if not isinstance(value, str) or not value:
            raise ValueError("InvoiceLegalMention token must be a non-empty string")
        return str.__new__(cls, value)

    @classmethod
    def from_registry(cls, value: str) -> Self:
        """Materialise one token from the typed facts projection."""
        return cls(value, _registry_validated=True)

    @classmethod
    def _require_registry_token(cls, value: object) -> Self:
        """Resolve Pydantic input through the scoped legal-mention fact."""
        if isinstance(value, cls):
            return value
        if isinstance(value, str):
            try:
                resolved = resolve_invoice_legal_mention(value, date.today())
                return cls.from_registry(str(resolved))
            except RegistryValidationError as exc:
                raise ValueError("InvoiceLegalMention is not declared by the scoped facts registry") from exc
        raise TypeError("InvoiceLegalMention must be a registry-projected token or string")

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        _source_type: object,
        _handler: GetCoreSchemaHandler,
    ) -> CoreSchema:
        """Expose a scoped, resolver-backed token schema with string serialization."""
        return core_schema.no_info_plain_validator_function(
            cls._require_registry_token,
            json_schema_input_schema=core_schema.str_schema(),
            serialization=core_schema.to_string_ser_schema(),
        )


_INVOICE_LEGAL_MENTION_FACT_ID = "iva-regime-legend-catalogue"


def invoice_legal_mention_declarations(
    on_date: date,
    *,
    authority: GovernedFactSource | None = None,
) -> tuple[InvoiceLegalMentionDeclaration, ...]:
    """Project the dated legal-mention vocabulary and semantics from the registry."""
    if authority is None:
        authority = governed_facts_in_scope()
    if authority is None:
        raise RegistryValidationError(
            "invoice legal-mention catalogue requires an explicit authority operation or scope"
        )
    selected = authority
    resolved = selected.resolve_governed_fact(
        MappingFactQuery(
            fact_id=_INVOICE_LEGAL_MENTION_FACT_ID,
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=on_date,
        ),
    )
    if not isinstance(resolved, ResolvedMappingFact):
        raise RegistryValidationError("invoice legal-mention catalogue must resolve as a mapping fact")
    values = {str(entry.key): str(entry.value) for entry in resolved.payload.entries}
    try:
        order = tuple(token.strip() for token in values["legal_mention_order"].split(",") if token.strip())
    except KeyError as exc:
        raise RegistryValidationError("invoice legal-mention catalogue is missing legal_mention_order") from exc
    if not order or len(order) != len(set(order)):
        raise RegistryValidationError("invoice legal-mention catalogue has an empty or duplicate token order")

    declarations: list[InvoiceLegalMentionDeclaration] = []
    for token in order:
        prefix = f"legal_mention.{token}."
        try:
            declared_value = values[f"{prefix}value"]
            phrase = values[f"{prefix}phrase"]
            provision = values[f"{prefix}provision"]
            references = tuple(ref.strip() for ref in values[f"{prefix}legal_refs"].split(",") if ref.strip())
            expects_line = values[f"{prefix}expects_repercutido_line"]
        except KeyError as exc:
            raise RegistryValidationError(f"invoice legal-mention catalogue is missing {prefix}{exc.args[0]}") from exc
        if declared_value != token or not phrase or not provision or not references:
            raise RegistryValidationError(f"invoice legal-mention catalogue has invalid declaration for {token}")
        if expects_line not in {"true", "false"}:
            raise RegistryValidationError(f"invoice legal-mention catalogue has invalid line expectation for {token}")
        declares = values.get(f"{prefix}declares")
        declarations.append(
            InvoiceLegalMentionDeclaration(
                token=token,
                phrase=phrase,
                provision=provision,
                legal_refs=references,
                declares=None if declares in {None, "none"} else declares,
                expects_repercutido_line=expects_line == "true",
            ),
        )
    return tuple(declarations)


def resolve_invoice_legal_mention(
    value: str,
    on_date: date,
    *,
    authority: GovernedFactSource | None = None,
) -> InvoiceLegalMention:
    """Return a typed invoice-mention token only when the registry accepts it."""
    if not isinstance(value, str):
        raise RegistryValidationError("invoice legal-mention token must be a string")
    for declaration in invoice_legal_mention_declarations(on_date, authority=authority):
        if declaration.token == value:
            return InvoiceLegalMention.from_registry(value)
    raise RegistryValidationError(f"invoice legal-mention token is not governed: {value}")


_IVA_RATE_SLOT_FACT_ID = "iva-rate-slot-catalogue"


def _iva_rate_slot_registry_values(
    on_date: date,
    *,
    authority: GovernedFactSource | None = None,
) -> Mapping[str, str]:
    """Resolve the dated slot membership and declarations from the registry."""
    if authority is None:
        authority = governed_facts_in_scope()
    if authority is None:
        raise RegistryValidationError("IVA rate-slot catalogue requires an explicit authority operation or scope")
    selected = authority
    resolved = selected.resolve_governed_fact(
        MappingFactQuery(
            fact_id=_IVA_RATE_SLOT_FACT_ID,
            date_axis=DateAxis.DEVENGO_DATE,
            effective_date=on_date,
        ),
    )
    if not isinstance(resolved, ResolvedMappingFact):
        raise RegistryValidationError("IVA rate slot catalogue must resolve as a mapping fact")
    return {str(entry.key): str(entry.value) for entry in resolved.payload.entries}


def _iva_rate_slot_registry_order(values: Mapping[str, str]) -> tuple[str, ...]:
    try:
        order = tuple(token.strip() for token in values["slot_order"].split(",") if token.strip())
    except KeyError as exc:
        raise RegistryValidationError("IVA rate slot catalogue is missing slot_order") from exc
    if not order or len(order) != len(set(order)):
        raise RegistryValidationError("IVA rate slot catalogue has an empty or duplicate slot order")
    for token in order:
        try:
            declared_value = values[f"slot.{token}.value"]
        except KeyError as exc:
            raise RegistryValidationError(f"IVA rate slot catalogue is missing slot.{token}.value") from exc
        if declared_value != token:
            raise RegistryValidationError(f"IVA rate slot catalogue has an invalid value for slot {token}")
    return order


def _iva_rate_slot_registry_declarations(rate: IvaRate, on_date: date) -> Mapping[str, str]:
    """Resolve one registry-validated slot's taxonomy."""
    values = _iva_rate_slot_registry_values(on_date)
    order = _iva_rate_slot_registry_order(values)
    token = str(rate)
    if token not in order:
        raise RegistryValidationError(f"IVA rate slot is not governed: {token}")
    prefix = f"slot.{token}."
    required = ("category", "substrate_kind", "numeric", "rate_role")
    try:
        return {key: values[f"{prefix}{key}"] for key in required}
    except KeyError as exc:
        raise RegistryValidationError(f"IVA rate slot catalogue is missing {prefix}{exc.args[0]}") from exc


def resolve_iva_rate_token(
    value: str,
    on_date: date,
    *,
    authority: GovernedFactSource | None = None,
) -> IvaRate:
    """Project one persisted rate token only when its registry membership exists."""
    if not isinstance(value, str):
        raise RegistryValidationError("IVA rate token must be a string")
    values = _iva_rate_slot_registry_values(on_date, authority=authority)
    if value not in _iva_rate_slot_registry_order(values):
        raise RegistryValidationError(f"IVA rate slot is not governed: {value}")
    return IvaRate.from_registry(value)


def iva_rate_slots_on(on_date: date) -> tuple[IvaRate, ...]:
    values = _iva_rate_slot_registry_values(on_date)
    return tuple(IvaRate.from_registry(token) for token in _iva_rate_slot_registry_order(values))


def _iva_rate_slot_kind(declarations: Mapping[str, str], on_date: date) -> IvaRateKind:
    """Parse the registry-declared substrate kind without a Python fallback."""
    try:
        return require_iva_rate_kind(declarations["substrate_kind"], effective_date=on_date)
    except (KeyError, ValueError) as exc:
        raise RegistryValidationError("IVA rate slot catalogue has an invalid substrate kind") from exc


def _pinned_iva_rate_operation() -> PinnedAuthorityOperation:
    """Require the enclosing rate projection to use one pinned generation."""
    from ..calculations.registry.authority import PinnedAuthorityOperation

    operation = governed_facts_in_scope()
    if not isinstance(operation, PinnedAuthorityOperation):
        raise RegistryValidationError("IVA rate resolution requires a generation-pinned authority operation")
    return operation


def resolve_iva_rate_slot_fact(rate: IvaRate, on_date: date):
    """Resolve a numeric slot's exact authority fact with its provenance.

    Zero is a permanent semantic slot whose IVA facade accepts the fraction on
    every date but which no flat rate fact can fully model; it consequently has
    no single rate-fact variant to return.  Registry-declared nonnumeric slots
    likewise have no rate-fact variant.
    """
    declarations = _iva_rate_slot_registry_declarations(rate, on_date)
    if declarations["numeric"] != "true":
        return None
    operation = _pinned_iva_rate_operation()
    kind = _iva_rate_slot_kind(declarations, on_date)
    if kind == resolve_iva_rate_kind_catalogue(effective_date=on_date, authority=operation).zero_token:
        return None
    return resolve_iva_rate(
        spanish_eu_member_state(effective_date=on_date, authority=operation),
        kind,
        on_date,
        rate_role=declarations["rate_role"],
        operation=operation,
    )


def iva_rate_percentage(rate: IvaRate, on_date: date) -> Decimal | None:
    """Resolve ``rate`` to its fractional authority value at ``on_date``.

    The result is projected from the exact Spanish member-state, tier, role,
    and devengo-date fact. No rate is parsed from the persisted token.

    Resolving through :func:`cadrumo.domain.iva.lookup_rate` instead would
    answer a different question and silently return a different number. That
    function deliberately skips ``supersedes_tier_default`` records, because a
    rate applying to only part of a tier's supplies cannot say what the tier
    means -- so a coexisting transitional line never computes from the ordinary
    tier default.
    :func:`cadrumo.domain.iva.rate_kinds_for_declared_rate` is the inverse
    authority built for this direction and does see those records.

    Args:
        rate: IVA rate slot.
        on_date: The explicit devengo date at which the slot is resolved.

    Returns:
        The slot's own percentage as a fractional Decimal; ``None`` for
        registry-declared nonnumeric slots, which carry no percentage.

    Raises:
        IvaRateNotFoundError: If the slot's rate was not in force for its tier
            on ``on_date`` -- a transitional slot used outside its statutory
            window, or a standing slot the registry no longer serves. Refusing
            is the point: substituting whatever the tier happens to mean that
            day would record a number the invoice never carried. When the rate
            table does not reach ``on_date`` FOR THAT TIER the refusal says so
            instead, because "not in force" would be a false claim about the law
            rather than a true one about our coverage. The reach differs between
            tiers, so the question is never whether the table reaches a date at
            all: it carries the general and reducido records well before the
            super-reducido ones.
            The registry-declared zero slot is never refused, because
            :func:`~cadrumo.domain.iva.rate_kinds_for_declared_rate` answers
            ZERO on every date -- Spain zero-rates on three permanent grounds
            the rate table cannot express, so its silence there is incomplete
            coverage rather than a statement that zero-rating was unlawful.
    """
    declarations = _iva_rate_slot_registry_declarations(rate, on_date)
    if declarations["numeric"] != "true":
        return None
    operation = _pinned_iva_rate_operation()
    kind = _iva_rate_slot_kind(declarations, on_date)
    if kind == resolve_iva_rate_kind_catalogue(effective_date=on_date, authority=operation).zero_token:
        if kind not in rate_kinds_for_declared_rate(
            spanish_eu_member_state(effective_date=on_date, authority=operation),
            Decimal("0"),
            on_date,
            operation=operation,
        ):
            raise IvaRateNotFoundError("zero IVA slot is not accepted by the IVA authority")
        return Decimal("0")
    try:
        resolved = resolve_iva_rate_slot_fact(rate, on_date)
        if resolved is None:
            raise RegistryValidationError("numeric IVA slot resolved without an authority fact")
        return iva_rate_record_from_fact(resolved, authority=operation).pct / Decimal("100")
    except RegistryValidationError as exc:
        # Coverage and legality are different facts and must not share a
        # message. The registry's reach differs PER TIER -- the general and
        # reducido records run from 2012, the super-reducido ones only from
        # 2024 -- so a line can fail on OUR reach while the table carries other
        # tiers that same day. Saying "not in force" there sends a filer to
        # correct a figure that was right, and invites widening the table with
        # a guessed value rather than an authored, corpus-backed one.
        if not rate_table_covers(
            spanish_eu_member_state(effective_date=on_date, authority=operation),
            on_date,
            kind,
            operation=operation,
        ):
            raise IvaRateNotFoundError(
                translated_message="errors.iva.rate_registry_coverage_gap",
                context={
                    "iva_rate_slot": rate.name,
                    "rate_kind": kind.value,
                    "member_state": spanish_eu_member_state(effective_date=on_date, authority=operation).value,
                    "on_date": on_date.isoformat(),
                    "rate_registry_covers_date": False,
                },
            ) from exc
        raise IvaRateNotFoundError(
            translated_message="errors.iva.rate_slot_not_in_force",
            context={
                "iva_rate_slot": rate.name,
                "rate_kind": kind.value,
                "member_state": spanish_eu_member_state(effective_date=on_date, authority=operation).value,
                "on_date": on_date.isoformat(),
                "rate_registry_covers_date": True,
                "rate_in_force": False,
            },
        ) from exc


def iva_rate_kind(rate: IvaRate) -> IvaRateKind | None:
    """Return the substrate rate tier for an invoice line rate slot.

    The out-of-scope slot has no OSS/IOSS rate tier because it is outside the
    taxable-supply universe; callers that need a Modelo 369 candidate should
    skip or reject it explicitly. Numeric and exempt slots return their
    corresponding :class:`IvaRateKind`; nonnumeric slots return ``None``.
    """
    declarations = _iva_rate_slot_registry_declarations(rate, date.today())
    if declarations["numeric"] != "true":
        return None
    return _iva_rate_slot_kind(declarations, date.today())


def resolve_iva_rate_slot(percentage: Decimal | None, on_date: date) -> IvaRate:
    """Resolve a printed percentage to its persisted slot at an explicit date."""
    if percentage is None:
        for rate in iva_rate_slots_on(on_date):
            declarations = _iva_rate_slot_registry_declarations(rate, on_date)
            if (
                declarations["numeric"] != "true"
                and declarations["substrate_kind"]
                == resolve_iva_rate_kind_catalogue(effective_date=on_date).exempt_token.value
            ):
                return rate
        raise RegistryValidationError("IVA rate slot catalogue has no exempt slot")
    resolved_rates: list[tuple[Decimal, IvaRate]] = []
    for rate in iva_rate_slots_on(on_date):
        try:
            resolved = iva_rate_percentage(rate, on_date)
        except IvaRateNotFoundError:
            continue
        if resolved is not None:
            resolved_rates.append((resolved, rate))
    matches = tuple(rate for resolved, rate in resolved_rates if resolved * Decimal("100") == percentage)
    if len(matches) == 1:
        return matches[0]
    accepted = ", ".join(format(resolved * Decimal("100"), "f") for resolved, _ in resolved_rates)
    raise IvaRateNotFoundError(
        "IVA percentage has no unique persisted rate slot at the supplied devengo date",
        context={"iva_rate": format(percentage, "f"), "on_date": on_date.isoformat(), "accepted": accepted},
    )


__all__ = [
    "InvoiceClass",
    "InvoiceLegalMention",
    "InvoiceLegalMentionDeclaration",
    "InvoiceOperationDateRole",
    "IvaRate",
    "IvaRateNotFoundError",
    "PaymentStatus",
    "advance_payment_received_role",
    "default_invoice_class",
    "invoice_class_ordinaria",
    "invoice_class_rectificativa",
    "invoice_class_simplificada",
    "invoice_legal_mention_declarations",
    "iva_rate_kind",
    "iva_rate_percentage",
    "operation_performed_role",
    "require_invoice_class",
    "require_invoice_operation_date_role",
    "resolve_invoice_legal_mention",
    "resolve_iva_rate_slot",
    "resolve_iva_rate_slot_fact",
    "resolve_iva_rate_token",
]
