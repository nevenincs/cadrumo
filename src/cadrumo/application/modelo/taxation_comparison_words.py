"""The words a taxation comparison serves for its recommendation and its scope caveat."""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING, Final

from ...core.i18n.render import tr
from .taxation_comparison import MATERIALITY_THRESHOLD, TaxationRecommendationReason
from .value_presentation import format_casilla_value

if TYPE_CHECKING:
    from collections.abc import Mapping
    from decimal import Decimal

    from ...core.external_constants import OutputLanguage

_REASON_LOCALE_KEYS: Final[Mapping[TaxationRecommendationReason, str]] = MappingProxyType(
    {
        TaxationRecommendationReason.CONJUNTA_LOWER_RESULT: (
            "application.modelo.taxation_comparison_words.conjunta_lower_result"
        ),
        TaxationRecommendationReason.INDIVIDUAL_LOWER_RESULT: (
            "application.modelo.taxation_comparison_words.individual_lower_result"
        ),
        TaxationRecommendationReason.BELOW_MATERIALITY: (
            "application.modelo.taxation_comparison_words.below_materiality"
        ),
    }
)
"""The catalogue sentence of each reason; every reason has one."""

_INDIVIDUAL_BRANCH_CAVEAT_LOCALE_KEY: Final = "application.modelo.taxation_comparison_words.individual_branch_caveat"


def _money(value: Decimal, language: OutputLanguage) -> str:
    return format_casilla_value(value, data_type="money", language=language)


def recommendation_reason_words(
    reason: TaxationRecommendationReason,
    *,
    conjunta_resultado: Decimal,
    individual_resultado: Decimal,
    delta_resultado: Decimal,
    language: OutputLanguage,
) -> str:
    """State the recommendation's reason in ``language``, naming the results it compares.

    The amounts are the comparison's own results, written as a box writes them.
    ``delta_resultado`` is the individual result minus the joint one, so its
    magnitude is the saving of whichever mode comes out lower.
    """
    return tr(
        _REASON_LOCALE_KEYS[reason],
        locale=language.value,
        conjunta=_money(conjunta_resultado, language),
        individual=_money(individual_resultado, language),
        difference=_money(abs(delta_resultado), language),
        threshold=_money(MATERIALITY_THRESHOLD, language),
    )


def individual_branch_caveat_words(language: OutputLanguage) -> str:
    """State in ``language`` the scope limit of the individual figure.

    The individual run reuses the single input set assembled for the unidad
    familiar, so it models only a single-earner household and does not work out
    two separate spouse returns. A two-earner comparison needs a per-spouse
    income axis that does not exist yet, so this disclosure accompanies every
    comparison and keeps the individual figure from being read as authoritative.
    """
    return tr(_INDIVIDUAL_BRANCH_CAVEAT_LOCALE_KEY, locale=language.value)


__all__ = ["individual_branch_caveat_words", "recommendation_reason_words"]
