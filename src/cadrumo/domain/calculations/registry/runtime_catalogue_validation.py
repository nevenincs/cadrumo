"""Validation predicates shared by the published runtime catalogue models."""

from __future__ import annotations

from collections.abc import Mapping
from itertools import pairwise
from typing import TYPE_CHECKING

from ....core.text_fold import fold_printed_phrase
from .errors import RegistryValidationError

if TYPE_CHECKING:
    from .runtime_catalogues import PublishedIvaPlaceOfSupplyRule, RuntimeRegistryCatalogues


def require_place_of_supply_grounding(rule: PublishedIvaPlaceOfSupplyRule) -> None:
    """Validate the legal grounding and validity window of a place-of-supply rule."""
    if len(rule.legal_references) != len(set(rule.legal_references)):
        raise RegistryValidationError(f"place-of-supply rule {rule.rule_id!r} repeats legal references")
    if rule.legal_basis_exempt:
        _require_exempt_place_of_supply(rule)
        return
    _require_grounded_place_of_supply(rule)


def _require_exempt_place_of_supply(rule: PublishedIvaPlaceOfSupplyRule) -> None:
    if rule.legal_references or rule.establishing_reference or rule.supply_nature is not None:
        raise RegistryValidationError("exempt place-of-supply rule must carry no legal disposition")
    if rule.valid_from is not None or rule.valid_to is not None:
        raise RegistryValidationError("exempt place-of-supply rule must carry no validity window")


def _require_grounded_place_of_supply(rule: PublishedIvaPlaceOfSupplyRule) -> None:
    if rule.valid_from is None or rule.valid_to is None or rule.valid_to < rule.valid_from:
        raise RegistryValidationError("grounded place-of-supply rule requires an ordered closed window")
    if not rule.legal_references or rule.establishing_reference not in rule.legal_references:
        raise RegistryValidationError("place-of-supply establishing reference must be among its legal refs")


def require_catalogue_record_keys(catalogues: RuntimeRegistryCatalogues) -> None:
    """Require catalogue mapping keys to match each record identity."""
    collections = (
        (catalogues.countries, "code"),
        (catalogues.territory_carve_outs, "code"),
        (catalogues.recargo_bands, "id"),
        (catalogues.apoderamientos_scopes, "code"),
    )
    for records, identity_name in collections:
        _require_record_keys(records, identity_name)


def _require_record_keys(records: Mapping[str, object], identity_name: str) -> None:
    for key, record in records.items():
        if key != getattr(record, identity_name):
            raise RegistryValidationError(f"runtime catalogue key {key!r} does not match record identity")


def require_postal_territory_keys(catalogues: RuntimeRegistryCatalogues) -> None:
    """Require each postal-territory key to belong to its declared prefixes."""
    for prefix, record in catalogues.spanish_postal_territories.items():
        if prefix not in record.postal_prefixes:
            raise RegistryValidationError(f"postal-territory key {prefix!r} is not declared by its record")


def require_tax_catalogue_keys(catalogues: RuntimeRegistryCatalogues) -> None:
    """Require tax catalogue keys to match category and rule identities."""
    if any(key != record.category for key, record in catalogues.iva_regulations.items()):
        raise RegistryValidationError("IVA regulation key does not match its category")
    if any(key != record.rule_id for key, record in catalogues.iva_place_of_supply.items()):
        raise RegistryValidationError("place-of-supply key does not match its rule id")


def require_unique_country_alpha3(catalogues: RuntimeRegistryCatalogues) -> None:
    """Refuse repeated alpha-3 codes across the country vocabulary."""
    alpha3 = tuple(record.alpha3 for record in catalogues.countries.values())
    if len(alpha3) != len(set(alpha3)):
        raise RegistryValidationError("country vocabulary repeats an alpha-3 code")


def require_unique_country_names(catalogues: RuntimeRegistryCatalogues) -> None:
    """Refuse blank country names or names shared by different countries."""
    names: dict[str, str] = {}
    for code, record in catalogues.countries.items():
        for name in record.names:
            folded = fold_printed_phrase(name)
            if not folded:
                raise RegistryValidationError(f"country {code!r} carries a blank printed name")
            previous = names.setdefault(folded, code)
            if previous != code:
                raise RegistryValidationError(f"printed country name {name!r} belongs to multiple countries")


def require_complete_recargo_bands(catalogues: RuntimeRegistryCatalogues) -> None:
    """Require contiguous recargo bands from zero through an open-ended tail."""
    ordered_bands = sorted(catalogues.recargo_bands.values(), key=lambda band: band.min_completed_months)
    if not ordered_bands:
        return
    if ordered_bands[0].min_completed_months != 0 or ordered_bands[-1].max_completed_months is not None:
        raise RegistryValidationError("recargo bands must cover from zero through one open-ended tail")
    for previous, current in pairwise(ordered_bands):
        if previous.max_completed_months is None:
            raise RegistryValidationError("only the final recargo band may be open-ended")
        if current.min_completed_months != previous.max_completed_months + 1:
            raise RegistryValidationError("recargo bands must be contiguous and non-overlapping")
