"""The operator's tax-residence profile.

This package is intentionally separate from financial usage-ratio
profiles, browser profiles, and spending-category profiles. It owns
personal local state needed to parameterize RENTA verification.

:class:`TaxResidenceProfile` and :class:`ResidenceChange` carry the
:class:`CCAA` residence axis; :class:`RentaFamilyProfile` and
:class:`DescendantInfo` carry the Modelo 100 personal/family facts, and
:class:`ProfileKey` exposes the wizard-registered editable profile schema.

Consumers import from the owning module -- :mod:`tax_residence`, :mod:`keys`,
:mod:`renta_codes`, :mod:`family_types`, :mod:`marriage_facts`,
:mod:`descendant_facts`, :mod:`constants`, :mod:`guarderia_mensual`,
:mod:`meses_trabajo`, :mod:`ccaa`, :mod:`errors` -- rather than from this
package root, which is inert.

The root previously DEFINED the tax-residence models and the region parser as
well as re-exporting fifty-odd names, which is why deleting an export map could
not make it inert. Those now live in :mod:`tax_residence`.

PROFILE_KEYS keeps its lazy resolution, which lives in :mod:`keys` and raises
until the wizard catalogue registers the compiled keys -- a deliberate
ordering contract, not an export map.
"""

from __future__ import annotations

__all__: tuple[str, ...] = ()
"""Inert namespace: every contract is reached at the module that defines it."""
