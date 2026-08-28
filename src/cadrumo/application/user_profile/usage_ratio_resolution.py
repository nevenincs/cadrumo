"""Resolve the usage ratios a deduction runs on, completing them from the censo.

LIRPF art. 30.2.5.b, verbatim from the bundled consolidated corpus:

    b) En los casos en que el contribuyente afecte parcialmente su vivienda habitual
    al desarrollo de la actividad económica, los gastos de suministros de dicha
    vivienda, tales como agua, gas, electricidad, telefonía e Internet, en el
    porcentaje resultante de aplicar el 30 por ciento a la proporción existente entre
    los metros cuadrados de la vivienda destinados a la actividad respecto a su
    superficie total, salvo que se pruebe un porcentaje superior o inferior.

The second factor is the taxpayer's own measurement, and the taxpayer has already
declared it: ``vivienda_office.office_m2`` and ``vivienda_office.total_m2`` are censo
036 facts on their profile. Until this module existed nothing carried that declaration
into the calculation. The ratio had to be typed a second time through
``aeat app ledger ratios set``, and a filer who declared their m² and never did that
deducted NOTHING on utilities -- silently, with no preflight reason for it, where the
law gave them thirty per cent of their declared proportion.

**Deriving here is not new policy.** The censo guard already refuses any stored
home-office ratio that is not exactly the censo-derived one, and a mismatch blocks
calculation. So the stored value carries no information the censo does not already
have, and filling an absent one from the censo produces precisely the number the guard
would have insisted on. What it changes is that the taxpayer no longer has to say the
same thing twice for the deduction to exist at all.

**It is also not the defect that was just removed.** The retired ``default_ratio``
was a REGISTRY constant standing in for a measurement the registry cannot know. This
is the OPERATOR'S OWN declared measurement, read from the facts they filed. The
distinction is the whole point: one invents the taxpayer's second factor, the other
reads it.

A stored override still wins where one exists, so the escape clause the article ends
on ("salvo que se pruebe un porcentaje superior o inferior") keeps whatever room the
censo guard allows it -- today, none, which is recorded as an open finding rather than
settled here.
"""

from __future__ import annotations

from decimal import Decimal

from ...adapters.persistence.profile.usage_ratios import load_usage_ratios
from ...domain.categories import SpendingCategory
from ...domain.usage_ratios import derive_home_office_ratios_from_censo
from .censo_sync import bound_raw_afectacion_ratio_for_bucket

__all__ = ["resolve_effective_usage_ratios"]


def resolve_effective_usage_ratios(
    *,
    bucket_id: str,
    year: int,
) -> dict[SpendingCategory, Decimal]:
    """Return the effective usage ratio per category for one bucket and filing year.

    Stored overrides are authoritative where they exist. Every home-office category
    the operator has NOT overridden is completed from the censo-declared afectación,
    when the profile carries the m² to compute it.

    Args:
        bucket_id: Profile bucket whose stored ratios and censo facts are read.
        year: Filing year whose proportionality rules supply the statutory factor
            (thirty per cent for suministros, none for the ownership costs, which
            take the raw area proportion under art. 29.2).

    Returns:
        Category-to-effective-ratio mapping, ready for
        :class:`~domain.renta.RentaDeductibilityContext`. Empty when the operator has
        stored nothing and declared no dwelling m².
    """
    stored = dict(load_usage_ratios(bucket_id=bucket_id).ratios)
    raw_afectacion_ratio = bound_raw_afectacion_ratio_for_bucket(bucket_id)
    if raw_afectacion_ratio is None:
        return stored
    derived = derive_home_office_ratios_from_censo(raw_afectacion_ratio, year=year).ratios
    # Stored last: an operator override wins over the derivation, and the censo guard
    # separately holds the two to agreement, so this ordering never silently replaces
    # a deliberate value with a computed one.
    return {**derived, **stored}
