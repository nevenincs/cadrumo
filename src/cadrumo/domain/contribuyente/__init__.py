"""The operator's tax-residence profile.

This package is intentionally separate from financial usage-ratio
profiles, browser profiles, and spending-category profiles. It owns
personal local state needed to parameterize RENTA verification.

:class:`TaxResidenceProfile` and :class:`ResidenceChange` carry the
:class:`CCAA` residence axis; :class:`RentaFamilyProfile` and
:class:`DescendantInfo` carry the Modelo 100 personal/family facts, and
:class:`ProfileKey` exposes the wizard-registered editable profile schema.

The initializer is inert; import contracts from their defining modules.
"""

from __future__ import annotations

__all__: tuple[str, ...] = ()
