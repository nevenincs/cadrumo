"""The dated legal windows a rectificativa's elected period must fall inside.

LIVA art. 89.Cinco and art. 114.Dos both bound the period a taxpayer may elect,
and each bound is a duration the law states rather than a number this
application knows. They are declared as dated scalar facts in years, so a
change in the statute is an edition of that fact and not an edit to Python.

Three windows, because the law states three:

* art. 89.Cinco letter b) lets the issuer regularise a minoración "en las
  posteriores hasta el plazo de un año a contar desde el momento en que debió
  efectuarse la mencionada rectificación";
* art. 114.Dos.1.º lets the recipient take an increase in a later
  declaración-liquidación "siempre que no hubiesen transcurrido cuatro años
  desde el devengo de la operación o, en su caso, desde la fecha en que se
  hayan producido las circunstancias que determinan la modificación";
* and the same apartado cuts that to one year where the rectification rests on
  "causa distinta de las previstas en el artículo 80", so a cause outside
  art. 80 carries its own shorter window rather than the four-year one.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING

from .errors import RegistryValidationError
from .facts.resolution import ResolvedScalarFact, ScalarFactQuery
from .governed_fact_scope import require_governed_fact_authority
from .schema_base import DateAxis

if TYPE_CHECKING:
    from .governed_fact_scope import GovernedFactSource

__all__ = [
    "RectificationPeriodWindows",
    "resolve_rectification_period_windows",
]

_ISSUER_MINORACION_WINDOW_FACT_ID = "liva-art-89-cinco-minoracion-regularisation-window-years"
_RECIPIENT_INCREASE_WINDOW_FACT_ID = "liva-art-114-dos-deduction-rectification-window-years"
_RECIPIENT_NON_ART_80_WINDOW_FACT_ID = "liva-art-114-dos-non-art-80-deduction-rectification-window-years"


@dataclass(frozen=True, slots=True)
class RectificationPeriodWindows:
    """The three elected-period windows, in whole years, for one filing-period date."""

    #: Art. 89.Cinco letter b): how long after the rectification was due the
    #: issuer may still regularise a minoración in a declaración-liquidación.
    issuer_minoracion_regularisation_years: int
    #: Art. 114.Dos.1.º: how long the recipient's elected increase period may
    #: run from the circumstances that modify the base.
    recipient_increase_years: int
    #: Art. 114.Dos.1.º, second paragraph: the shorter bound that replaces it
    #: when the rectification rests on a cause outside art. 80.
    recipient_increase_non_art_80_years: int


def resolve_rectification_period_windows(
    *,
    effective_date: date,
    authority: GovernedFactSource | None = None,
) -> RectificationPeriodWindows:
    """Resolve the three dated windows for ``effective_date``.

    ``authority`` is any governed-fact source, so a caller inside a pinned
    operation hands that operation in and the durations come from the
    generation it leased.

    Core types:
    :class:`~cadrumo.domain.calculations.registry.governed_fact_scope.GovernedFactSource`.
    """
    selected = require_governed_fact_authority(authority, subject="rectification period windows")
    return RectificationPeriodWindows(
        issuer_minoracion_regularisation_years=_window_years(
            _ISSUER_MINORACION_WINDOW_FACT_ID,
            effective_date=effective_date,
            authority=selected,
        ),
        recipient_increase_years=_window_years(
            _RECIPIENT_INCREASE_WINDOW_FACT_ID,
            effective_date=effective_date,
            authority=selected,
        ),
        recipient_increase_non_art_80_years=_window_years(
            _RECIPIENT_NON_ART_80_WINDOW_FACT_ID,
            effective_date=effective_date,
            authority=selected,
        ),
    )


def _window_years(fact_id: str, *, effective_date: date, authority: GovernedFactSource) -> int:
    """Resolve one window fact to its whole-year payload, refusing anything else."""
    resolved = authority.resolve_governed_fact(
        ScalarFactQuery(fact_id=fact_id, date_axis=DateAxis.FILING_PERIOD, effective_date=effective_date),
    )
    if not isinstance(resolved, ResolvedScalarFact):
        raise RegistryValidationError(f"rectification window fact {fact_id!r} must resolve as a scalar fact")
    value = resolved.payload.value
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise RegistryValidationError(
            f"rectification window fact {fact_id!r} resolved invalid years payload {value!r}",
        )
    return value
