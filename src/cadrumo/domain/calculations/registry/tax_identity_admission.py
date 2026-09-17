"""Registry-backed admission of tax identities for redaction.

Answers the redaction gate from the published authority: the Spanish
control-character format decides a NIF/NIE/CIF, and the dated NIF-IVA country
catalogue decides a prefixed Member State number. A prefix the catalogue does
not declare admits nothing.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date

from ....core.errors.hierarchy import CadrumoError
from ....core.identity.documents import IdentityError, SpanishTaxIdFormat, validate_identity
from .authority import bundled_indexed_authority
from .governed_fact_scope import GovernedFactSource, governed_facts_in_scope
from .nif_iva_catalogue import NifIvaCatalogue, resolve_nif_iva_catalogue
from .tax_id_format import tax_id_format


def _with_authority[T](resolve: Callable[[GovernedFactSource], T]) -> T | None:
    """Resolve under the scoped authority, else a lease on the published one.

    Returns ``None`` when no authority can answer, so redaction applies its own
    fail-safe instead of logging or raising from inside a log funnel.
    """
    try:
        scoped = governed_facts_in_scope()
        if scoped is not None:
            return resolve(scoped)
        with bundled_indexed_authority().operation() as operation:
            return resolve(operation)
    except (CadrumoError, OSError, ValueError):
        return None


def _catalogue(authority: GovernedFactSource) -> NifIvaCatalogue:
    return resolve_nif_iva_catalogue(effective_date=date.today(), authority=authority)


def _spanish_format(authority: GovernedFactSource) -> SpanishTaxIdFormat:
    return tax_id_format(authority, effective_date=date.today())


class RegistryTaxIdentityAdmission:
    """Admit redaction candidates against the published registry authority."""

    def admits_spanish_identity(self, normalised: str) -> bool | None:
        """Return whether ``normalised`` validates against the Spanish tax-ID format."""
        spanish_format = _with_authority(_spanish_format)
        if spanish_format is None:
            return None
        try:
            validate_identity(normalised, spanish_format)
        except IdentityError:
            return False
        return True

    def admits_nif_iva(self, normalised: str) -> bool | None:
        """Return whether ``normalised`` matches its declared Member State format."""
        catalogue = _with_authority(_catalogue)
        if catalogue is None:
            return None
        spec = catalogue.format_for_country(normalised[:2])
        return spec is not None and spec.pattern.match(normalised) is not None


__all__ = ["RegistryTaxIdentityAdmission"]
