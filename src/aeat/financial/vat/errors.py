"""Domain errors for the ``aeat.financial.vat`` subpackage.

Every failure mode raised by the VAT substrate inherits from
:class:`VatError`, which in turn inherits from
:class:`aeat.errors.AeatError`. Downstream callers catch the base
class when they want to treat the substrate as an opaque unit, or
the specific subclass when they need to distinguish missing-rate
from missing-category or corpus load failures.
"""

from __future__ import annotations

from aeat.errors import AeatError


class VatError(AeatError):
    """Base error for every ``aeat.financial.vat`` failure mode."""


class VatRateNotFoundError(VatError):
    """Raised when ``lookup_rate`` cannot resolve a rate.

    The lookup fails either because the requested member state is
    absent from :data:`aeat.financial.vat.VAT_RATE_TABLE`, because no
    rate of the requested :class:`VATRateKind` is registered for that
    member state, or because every registered rate's effective window
    excludes the requested date.
    """


class VatCategoryNotFoundError(VatError):
    """Raised when a lookup against :data:`VAT_CATALOGUE_2025` misses."""


class VatCatalogueError(VatError):
    """Raised when a VAT catalogue cannot be loaded or is malformed.

    Used by :func:`aeat.financial.vat.load_vat_rules_from_manual`
    when an explicit year has no in-memory or on-disk catalogue.
    """
