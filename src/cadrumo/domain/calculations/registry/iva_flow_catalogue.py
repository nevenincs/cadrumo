"""Typed projection of the governed IVA flow-direction vocabulary.

Flow direction and settlement-side membership are legal facts.  This module is
the only production boundary that turns the free-form values in fact 0083
into the opaque domain tokens used by IVA consumers.  Keeping the projection
here also makes an incomplete or stale fact fail closed instead of silently
falling back to a Python catalogue.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import Final

from ....core.time.clock import today_madrid
from ...iva.flow import IvaFlowDirection, IvaSettlementSide
from .errors import RegistryValidationError
from .facts.resolution import required_mapping_entry, unique_mapping_tokens
from .facts.string_mapping import (
    MappingValueWhitespace,
    StringMappingFact,
    StringMappingPolicy,
    unique_mapping_legal_refs,
)
from .governed_fact_scope import GovernedFactSource, governed_facts_in_scope
from .schema_base import DateAxis

_ENTRY_SUBJECT: Final = "IVA flow catalogue"

_FACT_ID = "iva-invoice-classification-catalogue"
_FLOW_ORDER_KEY = "flow_direction.order"
_SETTLEMENT_ORDER_KEY = "flow_direction.settlement_side_order"
_NO_SETTLEMENT_KEY = "flow_direction.no_settlement_token"
_ISSUED_KEY = "flow_direction.issued_token"
_RECEIVED_KEY = "flow_direction.received_token"
_RECIPIENT_REVERSE_CHARGE_KEY = "flow_direction.recipient_reverse_charge_token"
_SUPPLIER_REVERSE_CHARGE_KEY = "flow_direction.supplier_reverse_charge_token"
_FLOW_PREFIX = "flow_direction."
_SETTLEMENT_PREFIX = "flow_direction.settlement_side."


@dataclass(frozen=True, slots=True)
class IvaSettlementSideDefinition:
    """One registry-declared IVA settlement-side token and its semantics."""

    token: IvaSettlementSide
    description: str
    legal_refs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class IvaFlowDirectionDefinition:
    """One registry-declared IVA flow token and its settlement projection."""

    token: IvaFlowDirection
    description: str
    legal_refs: tuple[str, ...]
    settlement_sides: frozenset[IvaSettlementSide]


@dataclass(frozen=True, slots=True)
class IvaFlowDirectionCatalogue:
    """Complete dated projection of fact 0083's flow vocabulary."""

    declarations: Mapping[str, str]
    definitions: tuple[IvaFlowDirectionDefinition, ...]
    settlement_definitions: tuple[IvaSettlementSideDefinition, ...]
    no_settlement_token: str
    issued_token: IvaFlowDirection
    received_token: IvaFlowDirection
    recipient_reverse_charge_token: IvaFlowDirection
    supplier_reverse_charge_token: IvaFlowDirection
    devengada_token: IvaSettlementSide
    deducible_token: IvaSettlementSide

    @property
    def choices(self) -> tuple[IvaFlowDirection, ...]:
        """Return flow tokens in the order authored by the facts registry."""
        return tuple(item.token for item in self.definitions)

    @property
    def settlement_choices(self) -> tuple[IvaSettlementSide, ...]:
        """Return settlement-side tokens in the authored registry order."""
        return tuple(item.token for item in self.settlement_definitions)

    def require(self, value: object) -> IvaFlowDirection:
        """Project one flow token only when the selected fact declares it."""
        if isinstance(value, IvaFlowDirection):
            token = value
        elif isinstance(value, str):
            raw = value.strip()
            if not raw:
                raise RegistryValidationError("IVA flow direction must be a non-empty string token")
            try:
                token = IvaFlowDirection.from_registry(raw)
            except (TypeError, ValueError) as exc:
                raise RegistryValidationError("IVA flow direction must be a non-empty string token") from exc
        else:
            raise RegistryValidationError("IVA flow direction must be a string token")
        if token not in self.choices:
            raise RegistryValidationError(
                f"IVA flow direction {str(token)!r} is not declared by fact {_FACT_ID!r}",
            )
        return token

    def settlement_side(self, value: object) -> IvaSettlementSide:
        """Project one settlement-side token only when fact 0083 declares it."""
        if isinstance(value, IvaSettlementSide):
            token = value
        elif isinstance(value, str):
            raw = value.strip()
            if not raw:
                raise RegistryValidationError("IVA settlement side must be a non-empty string token")
            try:
                token = IvaSettlementSide.from_registry(raw)
            except (TypeError, ValueError) as exc:
                raise RegistryValidationError("IVA settlement side must be a non-empty string token") from exc
        else:
            raise RegistryValidationError("IVA settlement side must be a string token")
        if token not in self.settlement_choices:
            raise RegistryValidationError(
                f"IVA settlement side {str(token)!r} is not declared by fact {_FACT_ID!r}",
            )
        return token

    def definition(self, value: object) -> IvaFlowDirectionDefinition:
        """Return the full registry definition for a flow token."""
        token = self.require(value)
        for definition in self.definitions:
            if definition.token == token:
                return definition
        # ``require`` and the immutable definitions are validated together;
        # this branch keeps a malformed in-memory projection fail closed.
        raise RegistryValidationError(f"IVA flow direction {str(token)!r} has no registry definition")

    def settlement_sides_for(self, value: object) -> frozenset[IvaSettlementSide]:
        """Return the registry-declared settlement sides for one flow."""
        return self.definition(value).settlement_sides

    def is_devengada(self, value: object) -> bool:
        """Return whether a flow contributes to the devengada side."""
        return self.devengada_token in self.settlement_sides_for(value)

    def is_deducible(self, value: object) -> bool:
        """Return whether a flow contributes to the deducible side."""
        return self.deducible_token in self.settlement_sides_for(value)


_ENTRIES_POLICY = StringMappingPolicy(subject=_ENTRY_SUBJECT, value_whitespace=MappingValueWhitespace.PRESERVE)


_ENTRIES_FACT = StringMappingFact(fact_id=_FACT_ID, date_axis=DateAxis.FILING_PERIOD, policy=_ENTRIES_POLICY)


def _settlement_definitions(
    entries: Mapping[str, str],
) -> tuple[list[IvaSettlementSideDefinition], tuple[str, ...]]:
    settlement_definitions: list[IvaSettlementSideDefinition] = []
    settlement_tokens = unique_mapping_tokens(entries, _SETTLEMENT_ORDER_KEY, subject=_ENTRY_SUBJECT)
    for raw_token in settlement_tokens:
        token = IvaSettlementSide.from_registry(raw_token)
        prefix = f"{_SETTLEMENT_PREFIX}{raw_token}."
        if required_mapping_entry(entries, f"{prefix}value", subject=_ENTRY_SUBJECT) != raw_token:
            raise RegistryValidationError(f"IVA settlement side {raw_token!r} declares a mismatched value")
        settlement_definitions.append(
            IvaSettlementSideDefinition(
                token=token,
                description=required_mapping_entry(entries, f"{prefix}description", subject=_ENTRY_SUBJECT),
                legal_refs=unique_mapping_legal_refs(entries, f"{prefix}legal_refs", subject=_ENTRY_SUBJECT),
            ),
        )
    if len({item.token for item in settlement_definitions}) != len(settlement_definitions):
        raise RegistryValidationError("IVA flow catalogue contains duplicate settlement sides")
    return settlement_definitions, settlement_tokens


def _settlement_predicates(
    entries: Mapping[str, str],
    settlement_definitions: list[IvaSettlementSideDefinition],
) -> tuple[IvaSettlementSide, IvaSettlementSide]:
    settlement_choice_set = frozenset(item.token for item in settlement_definitions)
    devengada_token = IvaSettlementSide.from_registry(
        required_mapping_entry(entries, f"{_SETTLEMENT_PREFIX}devengada.value", subject=_ENTRY_SUBJECT),
    )
    deducible_token = IvaSettlementSide.from_registry(
        required_mapping_entry(entries, f"{_SETTLEMENT_PREFIX}deducible.value", subject=_ENTRY_SUBJECT),
    )
    if devengada_token not in settlement_choice_set or deducible_token not in settlement_choice_set:
        raise RegistryValidationError("IVA flow catalogue names an undeclared settlement-side predicate")
    return devengada_token, deducible_token


def _no_settlement_token(entries: Mapping[str, str], settlement_tokens: tuple[str, ...]) -> str:
    no_settlement_token = required_mapping_entry(entries, _NO_SETTLEMENT_KEY, subject=_ENTRY_SUBJECT)
    if no_settlement_token in settlement_tokens:
        raise RegistryValidationError("IVA flow catalogue no-settlement token collides with a settlement side")
    return no_settlement_token


def _flow_settlement_sides(
    raw_token: str,
    raw_sides: str,
    *,
    no_settlement_token: str,
    settlement_choice_set: frozenset[IvaSettlementSide],
) -> frozenset[IvaSettlementSide]:
    if raw_sides == no_settlement_token:
        return frozenset[IvaSettlementSide]()
    side_tokens = tuple(token.strip() for token in raw_sides.split(",") if token.strip())
    if not side_tokens or len(side_tokens) != len(set(side_tokens)):
        raise RegistryValidationError(
            f"IVA flow direction {raw_token!r} must declare unique settlement sides",
        )
    typed_sides: list[IvaSettlementSide] = []
    for side in side_tokens:
        projected_side = IvaSettlementSide.from_registry(side)
        if not isinstance(projected_side, IvaSettlementSide):
            raise RegistryValidationError("IVA flow catalogue projected an invalid settlement side")
        typed_sides.append(projected_side)
    settlement_sides = frozenset(typed_sides)
    if not settlement_sides.issubset(settlement_choice_set):
        raise RegistryValidationError(
            f"IVA flow direction {raw_token!r} names an undeclared settlement side",
        )
    return settlement_sides


def _flow_definitions(
    entries: Mapping[str, str],
    *,
    no_settlement_token: str,
    settlement_choice_set: frozenset[IvaSettlementSide],
) -> list[IvaFlowDirectionDefinition]:
    flow_definitions: list[IvaFlowDirectionDefinition] = []
    for raw_token in unique_mapping_tokens(entries, _FLOW_ORDER_KEY, subject=_ENTRY_SUBJECT):
        token = IvaFlowDirection.from_registry(raw_token)
        prefix = f"{_FLOW_PREFIX}{raw_token}."
        if required_mapping_entry(entries, f"{prefix}value", subject=_ENTRY_SUBJECT) != raw_token:
            raise RegistryValidationError(f"IVA flow direction {raw_token!r} declares a mismatched value")
        raw_sides = required_mapping_entry(entries, f"{prefix}settlement_sides", subject=_ENTRY_SUBJECT)
        flow_definitions.append(
            IvaFlowDirectionDefinition(
                token=token,
                description=required_mapping_entry(entries, f"{prefix}description", subject=_ENTRY_SUBJECT),
                legal_refs=unique_mapping_legal_refs(entries, f"{prefix}legal_refs", subject=_ENTRY_SUBJECT),
                settlement_sides=_flow_settlement_sides(
                    raw_token,
                    raw_sides,
                    no_settlement_token=no_settlement_token,
                    settlement_choice_set=settlement_choice_set,
                ),
            ),
        )
    if len({item.token for item in flow_definitions}) != len(flow_definitions):
        raise RegistryValidationError("IVA flow catalogue contains duplicate flow directions")
    return flow_definitions


def _flow_pointer(
    entries: Mapping[str, str], key: str, declared_flows: frozenset[IvaFlowDirection]
) -> IvaFlowDirection:
    token = IvaFlowDirection.from_registry(required_mapping_entry(entries, key, subject=_ENTRY_SUBJECT))
    if token not in declared_flows:
        raise RegistryValidationError(f"IVA flow catalogue pointer {key!r} names an undeclared flow")
    return token


def _require_distinct_flow_pointers(catalogue: IvaFlowDirectionCatalogue) -> None:
    pointers = {
        catalogue.issued_token,
        catalogue.received_token,
        catalogue.recipient_reverse_charge_token,
        catalogue.supplier_reverse_charge_token,
    }
    if len(pointers) < 4:
        raise RegistryValidationError("IVA flow catalogue pointers must identify four distinct flow directions")


def _catalogue(entries: Mapping[str, str]) -> IvaFlowDirectionCatalogue:
    settlement_definitions, settlement_tokens = _settlement_definitions(entries)
    devengada_token, deducible_token = _settlement_predicates(entries, settlement_definitions)
    no_settlement_token = _no_settlement_token(entries, settlement_tokens)
    settlement_choice_set = frozenset(item.token for item in settlement_definitions)
    flow_definitions = _flow_definitions(
        entries,
        no_settlement_token=no_settlement_token,
        settlement_choice_set=settlement_choice_set,
    )
    declared_flows = frozenset(item.token for item in flow_definitions)
    catalogue = IvaFlowDirectionCatalogue(
        declarations=entries,
        definitions=tuple(flow_definitions),
        settlement_definitions=tuple(settlement_definitions),
        no_settlement_token=no_settlement_token,
        issued_token=_flow_pointer(entries, _ISSUED_KEY, declared_flows),
        received_token=_flow_pointer(entries, _RECEIVED_KEY, declared_flows),
        recipient_reverse_charge_token=_flow_pointer(entries, _RECIPIENT_REVERSE_CHARGE_KEY, declared_flows),
        supplier_reverse_charge_token=_flow_pointer(entries, _SUPPLIER_REVERSE_CHARGE_KEY, declared_flows),
        devengada_token=devengada_token,
        deducible_token=deducible_token,
    )
    _require_distinct_flow_pointers(catalogue)
    return catalogue


def resolve_iva_flow_direction_catalogue(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> IvaFlowDirectionCatalogue:
    """Resolve the dated IVA flow and settlement vocabulary from fact 0083."""
    return _catalogue(_ENTRIES_FACT.resolve_scoped_entries(effective_date=effective_date, authority=authority))


def require_iva_flow_direction(
    value: object,
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> IvaFlowDirection:
    """Return a flow token only when the selected registry declares it."""
    return resolve_iva_flow_direction_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).require(value)


def require_registry_declared_iva_flow_direction(value: object) -> IvaFlowDirection:
    """Return one flow token declared by the facts a validation is validating.

    Like the rate-kind check, a registry validator resolves this vocabulary from
    the candidate in scope and refuses when none is: reading the published bundle
    while that bundle is being decoded is the deadlock this avoids.
    """
    authority = governed_facts_in_scope()
    if authority is None:
        raise RegistryValidationError(
            "IVA flow validation requires the governed facts being validated to be in "
            "scope; registry validation must not resolve a flow direction through the "
            "published authority artifact",
        )
    return resolve_iva_flow_direction_catalogue(effective_date=today_madrid(), authority=authority).require(value)


__all__ = [
    "IvaFlowDirectionCatalogue",
    "IvaFlowDirectionDefinition",
    "IvaSettlementSideDefinition",
    "require_iva_flow_direction",
    "require_registry_declared_iva_flow_direction",
    "resolve_iva_flow_direction_catalogue",
]
