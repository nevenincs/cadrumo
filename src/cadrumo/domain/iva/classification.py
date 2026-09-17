"""Generic IVA classification mechanics (issuer / customer / kind / direction).

Layered on top of the :mod:`cadrumo.domain.iva` substrate (the
:class:`cadrumo.domain.iva.IvaCategory` enum, :class:`cadrumo.domain.iva.IvaRateRecord`
records, and :func:`cadrumo.domain.iva.lookup_rate`), this module adds the
classification axes needed to tag a transaction deterministically based on
the parties' tax residency, the customer's IVA status, the transaction kind,
and the invoice direction.

The legal decision table is registry-owned. This module supplies only the
typed criteria/result records and the first-match evaluator that consumes a
registry-projected sequence of rule definitions. No legal rows, labels,
priorities, or fallback treatment are authored here.

Examples:
    >>> from datetime import date
    >>> from . import (
    ...     EUMemberState,
    ...     InvoiceKind,
    ...     TransactionKind,
    ...     IvaRateKind,
    ...     IvaInvoiceClassificationCriteria,
    ...     customer_tax_status_alias,
    ...     iva_territorial_scope_alias,
    ...     require_eu_member_state,
    ...     classify_iva,
    ... )
    >>> criteria = IvaInvoiceClassificationCriteria(
    ...     transaction_date=date(2025, 6, 15),
    ...     issuer_residency=iva_territorial_scope_alias("mainland"),
    ...     customer_residency=iva_territorial_scope_alias("eu_member"),
    ...     customer_identification_state=require_eu_member_state("DE"),
    ...     customer_tax_status=customer_tax_status_alias("b2b_registered"),
    ...     kind=registry_transaction_kind,
    ...     direction=InvoiceKind.ISSUED,
    ... )
    >>> classify_iva(criteria, rules=registry_rules).category
    'intra_community_supply'
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from types import MappingProxyType
from typing import TYPE_CHECKING, NamedTuple, TypeGuard

from pydantic import Field, model_validator
from pydantic_core import core_schema

from ...core.logging import get_logger
from ...core.registry_token import StrictRegistryToken
from ..calculations.registry.iva_category_catalogue import (
    IvaCategoryCatalogue,
    resolve_iva_category_catalogue,
)
from ..calculations.registry.iva_rate_kind_catalogue import (
    IvaRateKindCatalogue,
    resolve_iva_rate_kind_catalogue,
)
from .errors import IvaRateNotFoundError, IvaValidationError
from .lookup import lookup_rate
from .place_of_supply import IvaPlaceOfSupplyRule, place_of_supply_rule
from .schema import (
    EUMemberState,
    IvaArt69DosService,
    IvaCategory,
    IvaExemptionArticle,
    IvaRateKind,
    IvaRateRecord,
    IvaStrictFrozen,
    spanish_eu_member_state,
)

_logger = get_logger(__name__)

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation
    from ...domain.calculations.registry.facts.resolution import ResolvedMappingFact


# -- Registry-projected classification vocabulary ------------------------


class _RegistryProjectedToken(StrictRegistryToken):
    """Opaque token whose membership is established by a facts projection."""

    __slots__ = ()

    _refusal_error = IvaValidationError


class IvaTerritorialScope(_RegistryProjectedToken):
    """Registry-projected territorial scope token for an invoice party."""


class PartyFact(StrEnum):
    """The two legally distinct facts a rule may need about a party.

    They were one output before they were two, and the conflation had a
    direction. A printed foreign IVA prefix was read as decisive EVIDENCE OF
    PLACE, so a German-identified entity actually established in Spain resolved
    silently to a registry-projected EU-member token and fed the table as
    settled fact — while the mirror case, a non-resident holding a Spanish
    registration, was correctly refused. Every Member State registers
    non-residents on the same terms Spain does, so the two are one situation seen
    from two sides; splitting the fact restores the symmetry at the principle
    instead of patching it at one rung.

    Naming them lets a branch DECLARE which it consumes, so an operator is asked
    only for what the branch it lands on actually turns on. The domestic and
    territorial rules need the place and not the identification. The
    intra-community families need the identification, and need the place only
    narrowly beside it — not to say which Member State a party belongs to, which
    is the conflation, but to place the supply in the peninsula and keep the
    Spanish territories out of "otro Estado miembro". A row that reads a
    residency is not thereby reading it as a registration.

    Attributes:
        IVA_IDENTIFICATION_STATE: The Member State under whose IVA
            identification the party operates, carried as
            :class:`cadrumo.domain.iva.EUMemberState`. Registration evidence
            settles it decisively, because registration is precisely what it
            asserts.
        TERRITORIAL_ESTABLISHMENT: Where the party has its *sede de actividad
            económica* or an *establecimiento permanente* (Ley 37/1992
            arts. 69-70), carried as :class:`IvaTerritorialScope`. NO
            registration evidences it, foreign or Spanish.
    """

    IVA_IDENTIFICATION_STATE = "iva_identification_state"
    TERRITORIAL_ESTABLISHMENT = "territorial_establishment"


class InvoiceKind(StrEnum):
    """Whether the autónomo issued or received the invoice.

    Single canonical enum spanning both the substrate classifier
    (``IvaInvoiceClassificationCriteria.direction``) and ledger / invoice
    records (``Invoice.kind``). Replaces the prior split between
    ``InvoiceDirection`` (substrate) and :class:`InvoiceKind` (invoices)
    that carried identical semantics with mismatched lowercase / uppercase
    string values. Values are lowercase to align with TOML registry selectors
    (``invoice_direction = "issued"``).

    Attributes:
        ISSUED: The autónomo is the issuer (sale).
        RECEIVED: The autónomo is the recipient (purchase).
    """

    ISSUED = "issued"
    RECEIVED = "received"


class CustomerTaxStatus(_RegistryProjectedToken):
    """Registry-projected customer IVA-status token."""


@dataclass(frozen=True, slots=True)
class IvaClassificationCatalogue:
    """Typed projection of the 0083 territorial/status vocabularies."""

    territorial_scopes: tuple[IvaTerritorialScope, ...]
    customer_tax_statuses: tuple[CustomerTaxStatus, ...]
    territorial_aliases: Mapping[str, IvaTerritorialScope]
    customer_status_aliases: Mapping[str, CustomerTaxStatus]

    @property
    def territorial_scope_set(self) -> frozenset[IvaTerritorialScope]:
        """Return all territorial tokens declared by the selected fact."""
        return frozenset(self.territorial_scopes)

    @property
    def customer_tax_status_set(self) -> frozenset[CustomerTaxStatus]:
        """Return all customer-status tokens declared by the selected fact."""
        return frozenset(self.customer_tax_statuses)

    def require_territorial_scope(self, value: object) -> IvaTerritorialScope:
        """Validate and return one registry-projected territorial token."""
        if isinstance(value, IvaTerritorialScope):
            token = value
        elif isinstance(value, str):
            raw = value.strip()
            if not raw:
                raise IvaValidationError("IVA territorial scope token must not be blank")
            if raw not in {str(item) for item in self.territorial_scopes}:
                raise IvaValidationError(f"IVA territorial scope {raw!r} is not registry-declared")
            token = IvaTerritorialScope(raw, _registry_validated=True)
        else:
            raise IvaValidationError("IVA territorial scope must be a string token")
        if token not in self.territorial_scope_set:
            raise IvaValidationError(f"IVA territorial scope {str(token)!r} is not registry-declared")
        return token

    def require_customer_tax_status(self, value: object) -> CustomerTaxStatus:
        """Validate and return one registry-projected customer-status token."""
        if isinstance(value, CustomerTaxStatus):
            token = value
        elif isinstance(value, str):
            raw = value.strip()
            if not raw:
                raise IvaValidationError("customer tax status token must not be blank")
            if raw not in {str(item) for item in self.customer_tax_statuses}:
                raise IvaValidationError(f"customer tax status {raw!r} is not registry-declared")
            token = CustomerTaxStatus(raw, _registry_validated=True)
        else:
            raise IvaValidationError("customer tax status must be a string token")
        if token not in self.customer_tax_status_set:
            raise IvaValidationError(f"customer tax status {str(token)!r} is not registry-declared")
        return token

    def territorial_scope_alias(self, alias: str) -> IvaTerritorialScope:
        """Return a named territorial alias from the selected fact."""
        try:
            return self.territorial_aliases[alias]
        except KeyError as exc:
            raise IvaValidationError(f"IVA territorial scope alias {alias!r} is not registry-declared") from exc

    def customer_tax_status_alias(self, alias: str) -> CustomerTaxStatus:
        """Return a named customer-status alias from the selected fact."""
        try:
            return self.customer_status_aliases[alias]
        except KeyError as exc:
            raise IvaValidationError(f"customer tax status alias {alias!r} is not registry-declared") from exc


class TransactionKind(str):
    """Opaque registry-projected kind-of-supply token."""

    __slots__ = ()

    @classmethod
    def __get_pydantic_core_schema__(cls, _source_type: object, _handler: object) -> object:
        """Expose the opaque token as a string to Pydantic without a catalogue."""
        return core_schema.no_info_after_validator_function(cls, core_schema.str_schema())

    @property
    def value(self) -> str:
        """Return the opaque token for string-oriented serialization."""
        return str(self)


@dataclass(frozen=True, slots=True)
class TransactionKindDefinition:
    """One registry-declared transaction-kind token and its semantics."""

    token: TransactionKind
    description: str
    legal_refs: str | None = None
    supply_nature: str | None = None
    oss_regime: str | None = None
    default_rate_kind: str | None = None


@dataclass(frozen=True, slots=True)
class TransactionKindCatalogue:
    """Typed projection of the dated IVA classification kind vocabulary."""

    definitions: tuple[TransactionKindDefinition, ...]
    common_semantics: str
    union_scheme_semantics: str

    @property
    def all_kinds(self) -> frozenset[TransactionKind]:
        """Return every registry-declared transaction-kind token."""
        return frozenset(definition.token for definition in self.definitions)

    def require(self, value: object) -> TransactionKind:
        """Validate one opaque token against this registry projection."""
        if isinstance(value, TransactionKind):
            token = value
        elif isinstance(value, str):
            token = TransactionKind(value.strip())
        else:
            raise IvaValidationError("transaction kind must be a string token")
        if not str(token):
            raise IvaValidationError("transaction kind token must not be blank")
        if token not in self.all_kinds:
            raise IvaValidationError(f"transaction kind {str(token)!r} is not registry-declared")
        return token

    def for_supply_nature(self, supply_nature: str) -> TransactionKind:
        """Return the unique kind projection for a registry supply-nature token."""
        matches = tuple(
            definition.token for definition in self.definitions if definition.supply_nature == supply_nature
        )
        if len(matches) != 1:
            raise IvaValidationError(
                f"supply nature {supply_nature!r} must map to exactly one transaction kind",
            )
        return matches[0]

    def kinds_for_oss_regime(self, oss_regime: str) -> frozenset[TransactionKind]:
        """Return registry kinds routed through one OSS regime token."""
        matches = frozenset(definition.token for definition in self.definitions if definition.oss_regime == oss_regime)
        if not matches:
            raise IvaValidationError(
                f"OSS regime {oss_regime!r} must map to at least one transaction kind",
            )
        return matches


def _classification_mapping_entries(resolved: ResolvedMappingFact) -> Mapping[str, str]:
    """Narrow the classification fact payload to a unique string map."""
    entries: dict[str, str] = {}
    for entry in resolved.payload.entries:
        if not isinstance(entry.key, str) or not isinstance(entry.value, str):
            raise IvaValidationError("IVA classification mapping entries must be string-to-string")
        if entry.key in entries:
            raise IvaValidationError(f"duplicate IVA classification mapping key {entry.key!r}")
        entries[entry.key] = entry.value
    return MappingProxyType(entries)


def _required_classification_entry(entries: Mapping[str, str], key: str) -> str:
    value = entries.get(key)
    if value is None or not value.strip():
        raise IvaValidationError(f"IVA classification mapping is missing {key!r}")
    return value.strip()


def _classification_csv(entries: Mapping[str, str], key: str) -> tuple[str, ...]:
    tokens = tuple(token.strip() for token in _required_classification_entry(entries, key).split(",") if token.strip())
    if not tokens or len(set(tokens)) != len(tokens):
        raise IvaValidationError(f"IVA classification mapping {key!r} must declare unique tokens")
    return tokens


_TERRITORIAL_SCOPE_ALIAS_NAMES = frozenset({"mainland", "canarias", "ceuta_melilla", "eu_member", "third_country"})
_CUSTOMER_STATUS_ALIAS_NAMES = frozenset(
    {"b2b_registered", "b2b_not_registered", "b2c_consumer", "public_administration", "unknown"},
)


def _classification_vocabulary_group[T: _RegistryProjectedToken](
    entries: Mapping[str, str],
    *,
    prefix: str,
    order_key: str,
    token_type: type[T],
    alias_names: frozenset[str],
) -> tuple[tuple[T, ...], Mapping[str, T]]:
    """Project one membership order and its named aliases from fact 0083."""
    raw_tokens = _classification_csv(entries, order_key)
    tokens: list[T] = []
    for raw_token in raw_tokens:
        declared = _required_classification_entry(entries, f"{prefix}.{raw_token}.value")
        if declared != raw_token:
            raise IvaValidationError(
                f"IVA classification mapping {prefix}.{raw_token!s}.value declares {declared!r}, not {raw_token!r}",
            )
        tokens.append(token_type(raw_token, _registry_validated=True))
    declared_set = frozenset(str(token) for token in tokens)
    aliases: dict[str, T] = {}
    alias_prefix = f"{prefix}.alias."
    for key, value in entries.items():
        if not key.startswith(alias_prefix):
            continue
        alias = key.removeprefix(alias_prefix)
        if not alias or alias in aliases:
            raise IvaValidationError(f"duplicate IVA classification alias {alias!r}")
        raw_value = value.strip()
        if raw_value not in declared_set:
            raise IvaValidationError(
                f"IVA classification alias {key!r} names undeclared token {raw_value!r}",
            )
        aliases[alias] = token_type(raw_value, _registry_validated=True)
    if aliases.keys() != alias_names:
        missing = sorted(alias_names - aliases.keys())
        extra = sorted(aliases.keys() - alias_names)
        raise IvaValidationError(
            f"IVA classification aliases for {prefix!r} do not match the required projection "
            f"(missing={missing!r}, extra={extra!r})",
        )
    return tuple(tokens), MappingProxyType(aliases)


def resolve_iva_classification_catalogue(
    effective_date: date | None = None,
    *,
    operation: PinnedAuthorityOperation,
) -> IvaClassificationCatalogue:
    """Resolve the territorial and customer-status vocabulary from fact 0083."""
    resolved = _registry_iva_classification_catalogue(effective_date or date.today(), operation=operation)
    entries = _classification_mapping_entries(resolved)
    territorial_scopes, territorial_aliases = _classification_vocabulary_group(
        entries,
        prefix="territorial_scope",
        order_key="territorial_scope.order",
        token_type=IvaTerritorialScope,
        alias_names=_TERRITORIAL_SCOPE_ALIAS_NAMES,
    )
    customer_statuses, customer_status_aliases = _classification_vocabulary_group(
        entries,
        prefix="customer_tax_status",
        order_key="customer_tax_status.order",
        token_type=CustomerTaxStatus,
        alias_names=_CUSTOMER_STATUS_ALIAS_NAMES,
    )
    return IvaClassificationCatalogue(
        territorial_scopes=territorial_scopes,
        customer_tax_statuses=customer_statuses,
        territorial_aliases=territorial_aliases,
        customer_status_aliases=customer_status_aliases,
    )


def require_iva_territorial_scope(
    value: object,
    *,
    effective_date: date | None = None,
    operation: PinnedAuthorityOperation,
) -> IvaTerritorialScope:
    """Return a territorial scope only when 0083 declares it."""
    return resolve_iva_classification_catalogue(effective_date, operation=operation).require_territorial_scope(value)


def require_customer_tax_status(
    value: object,
    *,
    effective_date: date | None = None,
    operation: PinnedAuthorityOperation,
) -> CustomerTaxStatus:
    """Return a customer status only when 0083 declares it."""
    return resolve_iva_classification_catalogue(effective_date, operation=operation).require_customer_tax_status(value)


def iva_territorial_scope_alias(
    alias: str,
    *,
    effective_date: date | None = None,
    operation: PinnedAuthorityOperation,
) -> IvaTerritorialScope:
    """Return one named territorial projection from fact 0083."""
    return resolve_iva_classification_catalogue(effective_date, operation=operation).territorial_scope_alias(alias)


def customer_tax_status_alias(
    alias: str,
    *,
    effective_date: date | None = None,
    operation: PinnedAuthorityOperation,
) -> CustomerTaxStatus:
    """Return one named customer-status projection from fact 0083."""
    return resolve_iva_classification_catalogue(effective_date, operation=operation).customer_tax_status_alias(alias)


def resolve_transaction_kind_catalogue(
    effective_date: date,
    *,
    operation: PinnedAuthorityOperation,
) -> TransactionKindCatalogue:
    """Resolve all transaction-kind membership through the 0083 fact query."""
    resolved = _registry_iva_classification_catalogue(effective_date, operation=operation)
    entries = _classification_mapping_entries(resolved)
    definitions: list[TransactionKindDefinition] = []
    for token in _classification_csv(entries, "transaction_kind.order"):
        prefix = f"transaction_kind.{token}"
        declared_token = _required_classification_entry(entries, f"{prefix}.value")
        if declared_token != token:
            raise IvaValidationError(
                f"IVA classification mapping {prefix!r} declares value {declared_token!r}, not {token!r}",
            )
        definitions.append(
            TransactionKindDefinition(
                token=TransactionKind(token),
                description=_required_classification_entry(entries, f"{prefix}.description"),
                legal_refs=entries.get(f"{prefix}.legal_refs"),
                supply_nature=entries.get(f"{prefix}.supply_nature"),
                oss_regime=entries.get(f"{prefix}.oss_regime"),
                default_rate_kind=entries.get(f"{prefix}.default_rate_kind"),
            ),
        )
    return TransactionKindCatalogue(
        definitions=tuple(definitions),
        common_semantics=_required_classification_entry(entries, "transaction_kind.common_semantics"),
        union_scheme_semantics=_required_classification_entry(entries, "transaction_kind.union_scheme_semantics"),
    )


def require_transaction_kind(
    value: object,
    *,
    effective_date: date,
    operation: PinnedAuthorityOperation,
) -> TransactionKind:
    """Return one registry-declared transaction-kind token or refuse it."""
    return resolve_transaction_kind_catalogue(effective_date, operation=operation).require(value)


# -- Criteria and classification records ----------------------------------


def domestic_rate_tier_is_required(
    *,
    issuer_residency: IvaTerritorialScope,
    customer_residency: IvaTerritorialScope,
    kind: TransactionKind,
    transaction_date: date | None = None,
    customer_tax_status: CustomerTaxStatus | None = None,
    art_69_dos_service: IvaArt69DosService | None = None,
    exempt_kinds: frozenset[TransactionKind] = frozenset(),
    outside_territories: frozenset[IvaTerritorialScope] = frozenset(),
    operation: PinnedAuthorityOperation,
) -> bool:
    """Return whether the supplied axes require a rate tier.

    Any registry-declared exceptions and outside territories are supplied by
    the caller, keeping this reusable predicate free of a second legal table.
    """
    if kind in exempt_kinds:
        return False
    vocabulary = resolve_iva_classification_catalogue(transaction_date, operation=operation)
    mainland = vocabulary.territorial_scope_alias("mainland")
    if issuer_residency == mainland and customer_residency == mainland:
        return True
    services_kind = resolve_transaction_kind_catalogue(
        transaction_date or date.today(),
        operation=operation,
    ).for_supply_nature("services")
    return (
        issuer_residency == mainland
        and customer_residency in outside_territories
        and kind == services_kind
        and (customer_tax_status is None or customer_tax_status == vocabulary.customer_tax_status_alias("b2c_consumer"))
        and art_69_dos_service is None
    )


class IvaInvoiceClassificationCriteria(IvaStrictFrozen):
    """Input record for :func:`classify_iva`.

    Carries every axis the closed decision table inspects. The record is
    strict and frozen so it can be used as a dict key in upstream caches.

    **The two party facts are carried separately and are never derived from each
    other** (:class:`PartyFact`). The residency fields are the TERRITORIAL
    ESTABLISHMENT fact; the identification-state fields are the IVA
    IDENTIFICATION STATE fact. A party may hold a German identification while
    being established in Spain, or a Spanish one while established abroad — both
    are ordinary, and a model that could not express them forced the reader to
    pick one meaning for a value that had two.

    Attributes:
        transaction_date: When the supply takes place.
        issuer_residency: Where the issuer is ESTABLISHED — its sede or
            establecimiento permanente under Ley 37/1992 arts. 69-70. Never a
            statement about where it is registered. The field name keeps the
            role label; the type carries the territorial framing.
        customer_residency: The same for the customer.
        customer_tax_status: Customer's IVA status.
        kind: Kind of supply.
        direction: ``ISSUED`` or ``RECEIVED``.
        issuer_identification_state: The
            :class:`cadrumo.domain.iva.EUMemberState` under whose IVA
            identification the issuer operates, where established. Optional
            independently of :attr:`issuer_residency`: an EU establishment does
            not supply an identification and an identification does not supply
            an establishment, so demanding one because of the other would be the
            conflation :class:`PartyFact` exists to end. Branches that need it
            declare so, and the producer demands it only for those.
        customer_identification_state: The same for the customer.
        rate_tier: Explicit rate-tier axis for ES-to-ES domestic rules.
    """

    transaction_date: date = Field(description="When the supply takes place.")
    issuer_residency: IvaTerritorialScope = Field(description="Where the issuer is established (LIVA arts. 69-70).")
    customer_residency: IvaTerritorialScope = Field(
        description="Where the customer is established (LIVA arts. 69-70).",
    )
    customer_tax_status: CustomerTaxStatus = Field(description="Customer's IVA status.")
    kind: TransactionKind = Field(description="Kind of supply.")
    direction: InvoiceKind = Field(description="ISSUED or RECEIVED.")
    issuer_identification_state: EUMemberState | None = Field(
        default=None,
        description="Member State of the issuer's IVA identification; independent of its establishment.",
    )
    customer_identification_state: EUMemberState | None = Field(
        default=None,
        description="Member State of the customer's IVA identification; independent of its establishment.",
    )
    art_69_dos_service: IvaArt69DosService | None = Field(
        default=None,
        description=(
            "The lettered item of Ley 37/1992 art. 69.Dos this service is, "
            "stated by the operator. Absent by default, and absence is not "
            "evidence that no item applies: an unstated service stays taxed in "
            "the TAI rather than being lifted out of it on a fact nobody gave."
        ),
    )
    rate_tier: IvaRateKind | None = Field(
        default=None,
        description=(
            "Explicit rate-tier axis the caller resolves at invoice "
            "generation time. The classifier consults the registry-resolved "
            "rate/category mapping for ES-to-ES domestic rules. Ignored for "
            "non-domestic rules."
        ),
    )

    @model_validator(mode="after")
    def _validate_member_state_consistency(self) -> IvaInvoiceClassificationCriteria:
        """Keep criteria construction free of ambient registry access.

        Governed membership is checked by :func:`classify_iva`, where the
        caller-owned operation is available.  Pydantic model validators do not
        receive that operation, so validating through an ambient scope here
        would violate the composition boundary.
        """
        return self


class IvaClassificationResult(IvaStrictFrozen):
    """Output record returned by :func:`classify_iva`.

    Exposes the matched :class:`cadrumo.domain.iva.IvaCategory`, the resolved
    :class:`cadrumo.domain.iva.IvaRateRecord` (or ``None`` for rate-irrelevant
    categories), a reverse-charge flag, the matched rule identifier, and any
    free-form note the resolver emits (typically used for fall-through
    documentation).

    Attributes:
        category: Resolved IVA category.
        rate: Applicable :class:`cadrumo.domain.iva.IvaRateRecord`, when relevant.
        requires_reverse_charge: ``True`` when the rule triggers
            *inversión del sujeto pasivo*.
        matched_rule_id: Stable rule identifier (e.g.
            supplied by the selected registry revision.
        notes: Free-form explanatory note.
        consumes_party_facts: Which :class:`PartyFact` values the matched branch
            actually turns on. This is how a producer assembling the criteria
            learns what to demand without holding a second copy of the law: it
            asks the table which facts the branch consumes rather than
            hand-writing a rule about the territorial scopes, which is the
            duplication the lazy-requirement mechanism already refuses
            elsewhere. Defaults to BOTH facts, so a row or result that forgets
            to declare demands everything — the fail-toward-asking direction,
            and the one where forgetting costs a question rather than a silent
            classification on a fact nobody supplied.
        place_of_supply: The registry row that grounds the matched rule's
            placement in the operation's filing year — which provision locates
            the operation, and whether that provision fixes the nature of the
            supply. :func:`classify_iva` always stamps it; ``None`` survives
            only on a result assembled by hand, and therefore means "no
            placement was resolved", never "the resolution failed". A lookup
            that fails raises out of :func:`classify_iva` instead of arriving
            here as an absence.

            Read the nature off
            :attr:`~cadrumo.domain.iva.place_of_supply.IvaPlaceOfSupplyRule.supply_nature`:
            a ``None`` there is the third state, and it is a statement about
            the statute — the cited provisions are silent on whether goods or
            services were supplied. It is never an unfilled row.

            What this carries is registry-declared authority for the rule the
            table matched. It is not an AEAT ruling on the specific operation,
            and a consumer must not present it as one.
    """

    category: IvaCategory = Field(description="Resolved IVA category.")
    rate: IvaRateRecord | None = Field(default=None, description="Applicable :class:`IvaRateRecord`, when relevant.")
    requires_reverse_charge: bool = Field(default=False, description="True ⇒ inversión del sujeto pasivo.")
    matched_rule_id: str = Field(description="Stable rule id supplied by registry authority.")
    notes: str = Field(default="", description="Free-form explanatory note.")
    consumes_party_facts: frozenset[PartyFact] = Field(
        default=frozenset(PartyFact),
        description="Which :class:`PartyFact` values the matched branch turns on.",
    )
    exemption_article: IvaExemptionArticle | None = Field(
        default=None,
        description=(
            "Optional Ley 37/1992 Art. 20 sub-article discriminator. Stamped"
            " only when ``category`` is the registry-declared domestic-exempt token"
            " and the classification chain (or operator) has determined the"
            " specific sub-article. It adds classification context without"
            " creating a separate Modelo 303 route."
        ),
    )
    place_of_supply: IvaPlaceOfSupplyRule | None = Field(
        default=None,
        description=(
            "Registry-declared grounding of the matched rule's placement:"
            " which provision locates the operation, and whether that"
            " provision fixes the supply's nature. Stamped by"
            " :func:`classify_iva`; ``None`` means no placement was resolved,"
            " not that resolving one failed. A ``supply_nature`` of ``None``"
            " inside the row means the cited articles are silent on the"
            " nature. Registry authority, not an AEAT ruling on the"
            " operation."
        ),
    )


def domestic_categories_by_rate_kind(
    mapping: Mapping[IvaRateKind, IvaCategory] | None = None,
) -> Mapping[IvaRateKind, IvaCategory]:
    """Expose a registry-projected rate/category mapping as a read-only view."""
    if mapping is None:
        raise IvaValidationError("IVA rate/category mapping must be supplied by registry authority")
    return MappingProxyType(dict(mapping))


def rate_kind_for_domestic_category(
    category: IvaCategory,
    mapping: Mapping[IvaRateKind, IvaCategory] | None = None,
) -> IvaRateKind | None:
    """Resolve a domestic category through a caller-supplied registry mapping."""
    if mapping is None:
        raise IvaValidationError("IVA rate/category mapping must be supplied by registry authority")
    return next((tier for tier, mapped_category in mapping.items() if mapped_category == category), None)


class IvaClassificationRule(NamedTuple):
    """One registry-projected classification row consumed by the evaluator."""

    rule_id: str
    predicate: Callable[[IvaInvoiceClassificationCriteria], bool]
    category: IvaCategory | None = None
    description: str = ""
    consumes: frozenset[PartyFact] = frozenset[PartyFact]()
    requires_reverse_charge: bool = False


@dataclass(frozen=True, slots=True)
class IvaClassificationInputs:
    """Complete typed projection consumed by the IVA classifier.

    The fact registry stores rule predicates as a small declarative language.
    This record is the only boundary that turns that language into executable
    predicates and rate/category mappings; the evaluator itself remains a
    generic first-match consumer.
    """

    rules: tuple[IvaClassificationRule, ...]
    rate_categories: Mapping[IvaRateKind, IvaCategory]
    rate_territories: frozenset[IvaTerritorialScope]


def _scope_predicate_values(
    value: str,
    *,
    vocabulary: IvaClassificationCatalogue,
) -> frozenset[IvaTerritorialScope]:
    """Resolve one registry scope selector to its declared members."""
    all_scopes = frozenset(vocabulary.territorial_scopes)
    mainland = vocabulary.territorial_scope_alias("mainland")
    canarias = vocabulary.territorial_scope_alias("canarias")
    ceuta_melilla = vocabulary.territorial_scope_alias("ceuta_melilla")
    third_country = vocabulary.territorial_scope_alias("third_country")
    if value == "non_spanish_eu":
        return all_scopes - {mainland, canarias, ceuta_melilla}
    if value == "outside_tai":
        return all_scopes - {mainland}
    if value == "outside_comunidad":
        return frozenset({canarias, ceuta_melilla, third_country})
    try:
        return frozenset({vocabulary.territorial_scope_alias(value)})
    except IvaValidationError:
        return frozenset({vocabulary.require_territorial_scope(value)})


def _status_predicate_values(
    value: str,
    *,
    vocabulary: IvaClassificationCatalogue,
) -> frozenset[CustomerTaxStatus]:
    """Resolve one registry customer-status selector to its members."""
    aliases = vocabulary.customer_status_aliases
    if value == "b2b_or_public":
        return frozenset(
            {
                aliases["b2b_registered"],
                aliases["b2b_not_registered"],
                aliases["public_administration"],
            },
        )
    if value == "b2c_or_public":
        return frozenset({aliases["b2c_consumer"], aliases["public_administration"]})
    if value == "b2c":
        return frozenset({aliases["b2c_consumer"]})
    try:
        return frozenset({aliases[value]})
    except KeyError:
        return frozenset({vocabulary.require_customer_tax_status(value)})


def _kind_predicate_values(
    value: str,
    *,
    catalogue: TransactionKindCatalogue,
) -> frozenset[TransactionKind]:
    """Resolve one registry kind selector to its declared members."""
    if value == "domestic_default":
        return frozenset(
            definition.token
            for definition in catalogue.definitions
            if not definition.token.value.endswith("_reverse_charge")
        )
    return frozenset({catalogue.require(value)})


def _issuer_identification_state(criteria: IvaInvoiceClassificationCriteria) -> EUMemberState | None:
    """Read the issuer's identification axis for a compiled predicate."""
    return criteria.issuer_identification_state


def _customer_identification_state(criteria: IvaInvoiceClassificationCriteria) -> EUMemberState | None:
    """Read the customer's identification axis for a compiled predicate."""
    return criteria.customer_identification_state


def _compile_classification_predicate(
    expression: str,
    *,
    vocabulary: IvaClassificationCatalogue,
    kind_catalogue: TransactionKindCatalogue,
    effective_date: date,
    operation: PinnedAuthorityOperation,
) -> Callable[[IvaInvoiceClassificationCriteria], bool]:
    """Compile one registry predicate without introducing a second rule table."""
    if expression.strip() == "no_match":
        return lambda _criteria: False
    clauses = tuple(part.strip() for part in expression.split(";") if part.strip())
    if not clauses:
        raise IvaValidationError("IVA classification predicate must not be empty")
    conditions: list[Callable[[IvaInvoiceClassificationCriteria], bool]] = []
    seen: set[str] = set()
    spanish_state: EUMemberState = spanish_eu_member_state(effective_date=effective_date, authority=operation)
    third_country = vocabulary.territorial_scope_alias("third_country")
    for clause in clauses:
        if "=" not in clause:
            raise IvaValidationError(f"IVA classification predicate clause {clause!r} is malformed")
        field, value = (part.strip() for part in clause.split("=", 1))
        if not field or not value or field in seen:
            raise IvaValidationError(f"IVA classification predicate clause {clause!r} is malformed")
        seen.add(field)
        if field in {"issuer", "customer"}:
            allowed = _scope_predicate_values(value, vocabulary=vocabulary)
            if field == "issuer":
                conditions.append(lambda criteria, allowed=allowed: criteria.issuer_residency in allowed)
            else:
                conditions.append(lambda criteria, allowed=allowed: criteria.customer_residency in allowed)
            continue
        if field == "status":
            allowed = _status_predicate_values(value, vocabulary=vocabulary)
            conditions.append(lambda criteria, allowed=allowed: criteria.customer_tax_status in allowed)
            continue
        if field == "kind":
            allowed = _kind_predicate_values(value, catalogue=kind_catalogue)
            conditions.append(lambda criteria, allowed=allowed: criteria.kind in allowed)
            continue
        if field == "direction":
            try:
                direction = InvoiceKind(value)
            except ValueError as exc:
                raise IvaValidationError(f"IVA classification predicate names unknown direction {value!r}") from exc
            conditions.append(lambda criteria, direction=direction: criteria.direction is direction)
            continue
        if field in {"issuer_identification", "customer_identification"}:
            state_reader: Callable[[IvaInvoiceClassificationCriteria], EUMemberState | None]
            if field == "issuer_identification":
                state_reader = _issuer_identification_state
            else:
                state_reader = _customer_identification_state

            if value == "other_member_state":
                conditions.append(
                    lambda criteria, state_reader=state_reader, spanish_state=spanish_state: (
                        (state := state_reader(criteria)) is not None and state != spanish_state
                    ),
                )
            elif value == "present":
                conditions.append(lambda criteria, state_reader=state_reader: state_reader(criteria) is not None)
            elif value == "absent":
                conditions.append(lambda criteria, state_reader=state_reader: state_reader(criteria) is None)
            elif value == "spanish":
                conditions.append(
                    lambda criteria, state_reader=state_reader, spanish_state=spanish_state: (
                        state_reader(criteria) == spanish_state
                    )
                )
            else:
                raise IvaValidationError(
                    f"IVA classification predicate names unknown identification selector {value!r}"
                )
            continue
        if field == "art_69_dos_service":
            if value == "present":
                conditions.append(lambda criteria: criteria.art_69_dos_service is not None)
            elif value == "absent_or_excepted":
                conditions.append(
                    lambda criteria, third_country=third_country: (
                        not (criteria.art_69_dos_service is not None and criteria.customer_residency == third_country)
                    ),
                )
            elif value == "absent":
                conditions.append(lambda criteria: criteria.art_69_dos_service is None)
            else:
                raise IvaValidationError(f"IVA classification predicate names unknown Art. 69.Dos selector {value!r}")
            continue
        raise IvaValidationError(f"IVA classification predicate names unknown field {field!r}")

    return lambda criteria: all(condition(criteria) for condition in conditions)


def _is_object_mapping(value: object) -> TypeGuard[Mapping[object, object]]:
    """Narrow one runtime component to an object-keyed mapping before validation."""
    return isinstance(value, Mapping)


def _registry_reverse_charge_by_category(operation: PinnedAuthorityOperation) -> Mapping[str, bool]:
    """Read each IVA category's inversión-del-sujeto-pasivo flag from the published regulations."""
    from ..calculations.registry.runtime_catalogues import PublishedIvaRegulation

    loaded = operation.runtime_catalogue("iva_regulations")
    if not _is_object_mapping(loaded):
        raise IvaValidationError("indexed authority IVA regulation component has an invalid shape")
    flags: dict[str, bool] = {}
    for category, regulation in loaded.items():
        if not isinstance(category, str) or not isinstance(regulation, PublishedIvaRegulation):
            raise IvaValidationError("indexed authority IVA regulation component has an invalid shape")
        flags[category] = regulation.requires_reverse_charge
    return MappingProxyType(flags)


def _requires_reverse_charge(flags: Mapping[str, bool], category: IvaCategory) -> bool:
    """Return the registry's reverse-charge flag, refusing a rule category with no regulation."""
    flag = flags.get(category.value)
    if flag is None:
        raise IvaValidationError(f"IVA classification category {category.value!r} has no published regulation")
    return flag


def resolve_iva_classification_inputs(
    *,
    effective_date: date,
    operation: PinnedAuthorityOperation,
) -> IvaClassificationInputs:
    """Project the dated classification fact into typed evaluator inputs."""
    resolved = _registry_iva_classification_catalogue(effective_date, operation=operation)
    entries = _classification_mapping_entries(resolved)
    vocabulary = resolve_iva_classification_catalogue(effective_date, operation=operation)
    kind_catalogue = resolve_transaction_kind_catalogue(effective_date, operation=operation)
    category_catalogue: IvaCategoryCatalogue = resolve_iva_category_catalogue(
        effective_date=effective_date,
        authority=operation,
    )
    rate_catalogue: IvaRateKindCatalogue = resolve_iva_rate_kind_catalogue(
        effective_date=effective_date,
        authority=operation,
    )

    rate_categories: dict[IvaRateKind, IvaCategory] = {}
    for key, raw_category in entries.items():
        if not key.startswith("rate_categories."):
            continue
        raw_rate_kind = key.removeprefix("rate_categories.")
        if not raw_rate_kind:
            raise IvaValidationError("IVA classification mapping contains a blank rate-kind selector")
        rate_kind = rate_catalogue.require(raw_rate_kind)
        if rate_kind in rate_categories:
            raise IvaValidationError(f"IVA classification mapping repeats rate kind {raw_rate_kind!r}")
        rate_categories[rate_kind] = category_catalogue.require(raw_category)
    if not rate_categories:
        raise IvaValidationError("IVA classification mapping must declare rate categories")
    rate_territories = frozenset(
        vocabulary.require_territorial_scope(raw_value)
        for raw_value in _required_classification_entry(entries, "rate_territories").split(",")
        if raw_value.strip()
    )
    if not rate_territories:
        raise IvaValidationError("IVA classification mapping rate_territories must not be empty")

    reverse_charge_by_category = _registry_reverse_charge_by_category(operation)
    rules: list[IvaClassificationRule] = []
    for rule_id in _classification_csv(entries, "rule_order"):
        prefix = f"rule.{rule_id}"
        expression = _required_classification_entry(entries, f"{prefix}.predicate")
        raw_category = _required_classification_entry(entries, f"{prefix}.category")
        category = None if raw_category == "rate_categories[rate_tier]" else category_catalogue.require(raw_category)
        raw_consumes = entries.get(f"{prefix}.consumes")
        if raw_consumes is None:
            consumes = frozenset(PartyFact)
        else:
            consume_tokens = tuple(token.strip() for token in raw_consumes.split(",") if token.strip())
            if not consume_tokens or len(consume_tokens) != len(set(consume_tokens)):
                raise IvaValidationError(f"IVA classification rule {rule_id!r} has invalid party-fact membership")
            try:
                consumes = frozenset(PartyFact(token) for token in consume_tokens)
            except ValueError as exc:
                raise IvaValidationError(f"IVA classification rule {rule_id!r} names an unknown party fact") from exc
        rules.append(
            IvaClassificationRule(
                rule_id=rule_id,
                predicate=_compile_classification_predicate(
                    expression,
                    vocabulary=vocabulary,
                    kind_catalogue=kind_catalogue,
                    effective_date=effective_date,
                    operation=operation,
                ),
                category=category,
                description=_required_classification_entry(entries, f"{prefix}.label"),
                consumes=consumes,
                requires_reverse_charge=(
                    category is not None and _requires_reverse_charge(reverse_charge_by_category, category)
                ),
            ),
        )
    return IvaClassificationInputs(
        rules=tuple(rules),
        rate_categories=MappingProxyType(rate_categories),
        rate_territories=rate_territories,
    )


# -- Public resolver ------------------------------------------------------


def _registry_iva_classification_catalogue(
    effective_date: date,
    *,
    operation: PinnedAuthorityOperation,
) -> ResolvedMappingFact:
    """Resolve the dated IVA catalogue consumed by the generic evaluator."""
    from ...domain.calculations.registry.facts.resolution import MappingFactQuery, ResolvedMappingFact
    from ...domain.calculations.registry.schema_base import DateAxis

    resolved = operation.resolve_governed_fact(
        MappingFactQuery(
            fact_id="iva-invoice-classification-catalogue",
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=effective_date,
        ),
    )
    if not isinstance(resolved, ResolvedMappingFact):
        raise IvaValidationError("IVA classification catalogue must resolve as a mapping fact")
    return resolved


def classify_iva(
    criteria: IvaInvoiceClassificationCriteria,
    *,
    rules: Iterable[IvaClassificationRule] | None = None,
    rate_categories: Mapping[IvaRateKind, IvaCategory] | None = None,
    rate_territories: frozenset[IvaTerritorialScope] | None = None,
    operation: PinnedAuthorityOperation,
) -> IvaClassificationResult:
    """Evaluate registry-projected rows in their supplied order.

    This function intentionally has no module-owned table or fallthrough row.
    Callers must project the selected registry revision into ``rules`` and,
    when a matched row derives a category from a rate tier, provide the
    registry-owned ``rate_categories`` and ``rate_territories`` mappings.
    """
    _registry_iva_classification_catalogue(criteria.transaction_date, operation=operation)
    vocabulary = resolve_iva_classification_catalogue(criteria.transaction_date, operation=operation)
    category_catalogue = resolve_iva_category_catalogue(
        effective_date=criteria.transaction_date,
        authority=operation,
    )
    rate_catalogue = resolve_iva_rate_kind_catalogue(
        effective_date=criteria.transaction_date,
        authority=operation,
    )
    vocabulary.require_territorial_scope(criteria.issuer_residency)
    vocabulary.require_territorial_scope(criteria.customer_residency)
    vocabulary.require_customer_tax_status(criteria.customer_tax_status)
    resolve_transaction_kind_catalogue(
        criteria.transaction_date,
        operation=operation,
    ).require(criteria.kind)
    if criteria.rate_tier is not None:
        rate_catalogue.require(criteria.rate_tier)
    if rules is None:
        raise IvaValidationError("IVA classification rows must be supplied by registry authority")
    projected_rules = tuple(rules)
    for rule in projected_rules:
        if rule.category is not None:
            category_catalogue.require(rule.category)
        if not rule.predicate(criteria):
            continue
        category = rule.category
        if category is None:
            if criteria.rate_tier is None or rate_categories is None:
                raise IvaValidationError("matched IVA row requires a registry rate/category mapping")
            try:
                category = rate_categories[criteria.rate_tier]
            except KeyError as exc:
                raise IvaValidationError("registry rate/category mapping has no matched rate tier") from exc
        rate = _resolve_rate_for_category(
            criteria,
            category,
            rate_categories=rate_categories,
            rate_territories=rate_territories,
            operation=operation,
        )
        category = category_catalogue.require(category)
        if category == category_catalogue.require("domestic_exempt") and criteria.rate_tier is not None:
            rate_catalogue.require(criteria.rate_tier)
        return IvaClassificationResult(
            category=category,
            rate=rate,
            requires_reverse_charge=rule.requires_reverse_charge,
            matched_rule_id=rule.rule_id,
            notes=rule.description,
            consumes_party_facts=rule.consumes,
            place_of_supply=place_of_supply_rule(
                rule.rule_id,
                on=criteria.transaction_date,
                operation=operation,
                projected_year=criteria.transaction_date.year,
            ),
        )
    fallback = next((rule for rule in projected_rules if rule.rule_id == "R99_fallthrough"), None)
    if fallback is None:
        raise IvaValidationError("no registry IVA classification row matched the supplied criteria")
    fallback_category = category_catalogue.require(fallback.category or "unknown")
    return IvaClassificationResult(
        category=fallback_category,
        rate=None,
        requires_reverse_charge=fallback.requires_reverse_charge,
        matched_rule_id=fallback.rule_id,
        notes=fallback.description,
        consumes_party_facts=fallback.consumes,
        place_of_supply=place_of_supply_rule(
            fallback.rule_id,
            on=criteria.transaction_date,
            operation=operation,
            projected_year=criteria.transaction_date.year,
        ),
    )


def _resolve_rate_for_category(
    criteria: IvaInvoiceClassificationCriteria,
    category: IvaCategory,
    *,
    rate_categories: Mapping[IvaRateKind, IvaCategory] | None,
    rate_territories: frozenset[IvaTerritorialScope] | None,
    operation: PinnedAuthorityOperation,
) -> IvaRateRecord | None:
    """Resolve a rate through caller-supplied registry mappings."""
    if rate_categories is None or rate_territories is None:
        return None
    tier = next((candidate for candidate, mapped in rate_categories.items() if mapped == category), None)
    if tier is None:
        return None
    if criteria.issuer_residency not in rate_territories:
        return None
    member_state = spanish_eu_member_state(effective_date=criteria.transaction_date, authority=operation)
    try:
        return lookup_rate(member_state, tier, criteria.transaction_date, operation=operation)
    except IvaRateNotFoundError:
        _logger.debug(
            "classify_iva: lookup_rate(%s, %s, %s) failed; returning rate=None",
            member_state.value,
            tier.value,
            criteria.transaction_date.isoformat(),
        )
        return None


__all__ = [
    "CustomerTaxStatus",
    "InvoiceKind",
    "IvaClassificationCatalogue",
    "IvaClassificationInputs",
    "IvaClassificationResult",
    "IvaClassificationRule",
    "IvaInvoiceClassificationCriteria",
    "IvaTerritorialScope",
    "PartyFact",
    "TransactionKind",
    "TransactionKindCatalogue",
    "TransactionKindDefinition",
    "classify_iva",
    "customer_tax_status_alias",
    "domestic_categories_by_rate_kind",
    "iva_territorial_scope_alias",
    "rate_kind_for_domestic_category",
    "require_customer_tax_status",
    "require_iva_territorial_scope",
    "require_transaction_kind",
    "resolve_iva_classification_catalogue",
    "resolve_iva_classification_inputs",
    "resolve_transaction_kind_catalogue",
]
