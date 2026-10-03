"""Typed authority projection for IVA cash-accounting treatment."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from ...iva.schema import IvaCashAccountingTreatment
from .errors import RegistryValidationError
from .facts.resolution import required_mapping_entry, unique_mapping_tokens
from .governed_fact_scope import GovernedFactSource, governed_facts_in_scope
from .iva_schema_vocabulary_source import (
    SCHEMA_VOCABULARY_SUBJECT,
    UNIQUE_TOKENS_REQUIREMENT,
    csv_legal_references,
    resolve_scoped_schema_projections,
)

_CASH_ORDER_KEY = "cash_accounting.order"

_CASH_NONE_KEY = "cash_accounting.none_token"

_CASH_SUPPLIER_KEY = "cash_accounting.supplier_regime_token"

_CASH_PREFIX = "cash_accounting."


@dataclass(frozen=True, slots=True)
class IvaCashAccountingTreatmentDefinition:
    """One registry-declared cash-accounting treatment and its semantics."""

    token: IvaCashAccountingTreatment
    description: str
    legal_refs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class IvaCashAccountingTreatmentCatalogue:
    """Typed projection of the dated cash-accounting vocabulary."""

    definitions: tuple[IvaCashAccountingTreatmentDefinition, ...]
    none_token: IvaCashAccountingTreatment
    supplier_regime_token: IvaCashAccountingTreatment

    @property
    def all_treatments(self) -> frozenset[IvaCashAccountingTreatment]:
        """Return every cash-accounting treatment declared by the registry."""
        return frozenset(definition.token for definition in self.definitions)

    def require(self, value: object) -> IvaCashAccountingTreatment:
        """Validate and return one registry-declared cash-accounting treatment."""
        if isinstance(value, IvaCashAccountingTreatment):
            token = value
        elif isinstance(value, str):
            token = IvaCashAccountingTreatment(value.strip())
        else:
            raise RegistryValidationError("cash-accounting treatment must be a string token")
        if not str(token) or token not in self.all_treatments:
            raise RegistryValidationError(
                f"cash-accounting treatment {str(token)!r} is not declared by the facts registry",
            )
        return token

    def definition(self, value: object) -> IvaCashAccountingTreatmentDefinition:
        """Return the registry definition for one cash-accounting treatment."""
        token = self.require(value)
        return next(definition for definition in self.definitions if definition.token == token)


def resolve_iva_cash_accounting_catalogue(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> IvaCashAccountingTreatmentCatalogue:
    """Resolve the dated IVA cash-accounting vocabulary from governed facts."""
    projections = resolve_scoped_schema_projections(effective_date=effective_date, authority=authority)
    if projections.cash_accounting:
        return projections.cash_accounting[0]
    entries = projections.entries
    definitions: list[IvaCashAccountingTreatmentDefinition] = []
    for raw_token in unique_mapping_tokens(
        entries, _CASH_ORDER_KEY, subject=SCHEMA_VOCABULARY_SUBJECT, requirement=UNIQUE_TOKENS_REQUIREMENT
    ):
        token = IvaCashAccountingTreatment(raw_token)
        prefix = f"{_CASH_PREFIX}{raw_token}"
        if required_mapping_entry(entries, f"{prefix}.value", subject=SCHEMA_VOCABULARY_SUBJECT) != raw_token:
            raise RegistryValidationError(f"cash-accounting token {raw_token!r} declares a mismatched value")
        definitions.append(
            IvaCashAccountingTreatmentDefinition(
                token=token,
                description=required_mapping_entry(entries, f"{prefix}.description", subject=SCHEMA_VOCABULARY_SUBJECT),
                legal_refs=csv_legal_references(entries, f"{prefix}.legal_refs", required=False),
            ),
        )
    catalogue = IvaCashAccountingTreatmentCatalogue(
        definitions=tuple(definitions),
        none_token=IvaCashAccountingTreatment(
            required_mapping_entry(entries, _CASH_NONE_KEY, subject=SCHEMA_VOCABULARY_SUBJECT)
        ),
        supplier_regime_token=IvaCashAccountingTreatment(
            required_mapping_entry(entries, _CASH_SUPPLIER_KEY, subject=SCHEMA_VOCABULARY_SUBJECT)
        ),
    )
    if catalogue.none_token not in catalogue.all_treatments:
        raise RegistryValidationError("cash-accounting none token is not declared in the treatment order")
    if catalogue.supplier_regime_token not in catalogue.all_treatments:
        raise RegistryValidationError("cash-accounting supplier token is not declared in the treatment order")
    projections.cash_accounting[:] = [catalogue]
    return catalogue


def default_iva_cash_accounting_treatment(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> IvaCashAccountingTreatment:
    """Return the registry-declared default cash-accounting treatment."""
    return resolve_iva_cash_accounting_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).none_token


def require_iva_cash_accounting_treatment(
    value: object,
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> IvaCashAccountingTreatment:
    """Validate one value against the dated cash-accounting vocabulary."""
    return resolve_iva_cash_accounting_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).require(value)


def require_registry_declared_iva_cash_accounting_treatment(
    value: object,
    *,
    effective_date: date,
) -> IvaCashAccountingTreatment:
    """Return one treatment token declared by the facts a validation is validating.

    A registry validator resolves its vocabulary from the candidate in scope,
    never from the published authority: the artifact reader validates the
    document it has just decoded while holding the shared-artifact lock, so a
    validator reaching for the bundle asks that lock for the artifact it is in
    the middle of producing. Absence of a scope is a refusal rather than a
    fallback, because the fallback is the deadlock.
    """
    authority = governed_facts_in_scope()
    if authority is None:
        raise RegistryValidationError(
            "IVA cash-accounting validation requires the governed facts being validated to be "
            "in scope; registry validation must not resolve a treatment through the published "
            "authority artifact",
        )
    return resolve_iva_cash_accounting_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).require(value)


__all__ = [
    "IvaCashAccountingTreatmentCatalogue",
    "IvaCashAccountingTreatmentDefinition",
    "default_iva_cash_accounting_treatment",
    "require_iva_cash_accounting_treatment",
    "require_registry_declared_iva_cash_accounting_treatment",
    "resolve_iva_cash_accounting_catalogue",
]
