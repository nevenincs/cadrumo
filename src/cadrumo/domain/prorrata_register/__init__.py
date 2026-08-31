"""Per-ejercicio cross-period IVA prorrata register (LIVA arts. 102-106).

The provisional-to-definitive IVA prorrata lifecycle is inherently cross-year:
under prorrata general only the deduction percentage of soportado is deductible
in each liquidation period (art. 104.Uno); the percentage provisionally
applicable each year is the prior year's definitive (art. 105.Uno), with the
regulated alternatives of an AEAT-authorised provisional (art. 105.Dos) and the
inicio-de-actividades proposed percentage (art. 105.Tres via art. 111.Dos); the
last liquidation of the year computes the definitive prorrata from the year's
actual operations and regularises the provisional deductions (art. 105.Cuatro).

This module is the CARRY HOME for that lifecycle: a durable per-ejercicio
:class:`ProrrataRegister`, one :class:`ProrrataRegisterEntry` per
``(ejercicio, sector)`` carrying the regime, the provisional percentage in force
with its regulated :class:`~core.ProrrataProvisionalProvenance`, and — once
settled — the definitive percentage with the annual volume inputs it derived
from. The pure precedence-ladder resolver
(:func:`resolve_provisional_percentage`) selects the in-force provisional
percentage among candidate provenances (authorised/inicio outranking the carried
prior definitive) and returns a visible unresolved state rather than any
fabricated default — no percentage is ever assumed.

This is a taxpayer-fact store, sibling to :mod:`domain.bienes_inversion`: it
holds the per-ejercicio percentages and their provenance, never the regulatory
constants. The prorrata compute substrate (:mod:`domain.iva`:
``compute_prorrata_definitiva_anual``, ``compute_regularizacion_prorrata_anual``)
is consumed at settlement, not re-implemented here, and this module reads no
secure-object store — the seed, in-year apportionment, and settlement write-back
live in the application layer.

See Also:
    :mod:`adapters.persistence.profile.prorrata_register`
        FINANCIAL secure-object repository that stores the register singleton.
    :mod:`domain.iva`
        Legal prorrata substrate that computes the definitive percentage from
        annual volumes and the art. 105.Cuatro regularisation cuota.
    :mod:`domain.bienes_inversion`
        Sibling per-taxpayer-fact register whose shape this mirrors.
"""

from __future__ import annotations

__all__: tuple[str, ...] = ()
