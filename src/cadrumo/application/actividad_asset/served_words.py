"""The sentences the activity-asset register serves for its reasons, findings, advisories and filing handoff.

The register's reasons arrive as catalogue keys with the facts that fill them,
and a frontend that holds no tax vocabulary cannot finish them. This module says
each one whole in the language a request names: dates, amounts and percentages
as that language writes them, and an element by the name the register holds for
it. A sentence that cannot be finished, because the catalogue has no word for its
key or a fact it needs was not given, is not served: the record carries none
rather than a half-filled template or a bare key.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from datetime import date
from decimal import Decimal
from typing import Final

from ...core.errors.hierarchy import CadrumoError
from ...core.external_constants import OutputLanguage
from ...core.i18n.render import lookup_translation, tr
from ..modelo.edit_value_grammar import ModeloEditRatioUnit
from ..modelo.value_presentation import format_casilla_value, group_decimal_text
from ..operations.error_detail import operation_refusal_words
from .activity_asset_read_models import (
    ACTIVITY_ASSET_LABEL_NAMESPACE,
    ActivityAssetDisposalCalculationView,
    ActivityAssetDisposalFindingView,
    ActivityAssetElectionLimits,
    ActivityAssetHandoffLeftOut,
    ActivityAssetHandoffLeftOutReason,
    ActivityAssetListRow,
    ActivityAssetPlanAdvisory,
    ActivityAssetPlanRow,
    ActivityAssetReasonFact,
    ActivityAssetReasonFactKind,
    ServedWords,
)
from .schedule_walk import M100GapKind

_UNFILLED: Final = re.compile(r"%\{\w+\}|\{\w+\}")

#: Fact names a sentence is never filled with; they identify records for a screen to act on.
_NOT_SAID_FACTS: Final = frozenset({"conflicting_claim_ids"})

_UNNAMED_ELEMENT_LOCALE_KEY: Final = "application.actividad_asset.served.handoff.unnamed_element"
_OPENING_REMEDY_LOCALE_KEY: Final = "application.actividad_asset.served.opening_remedy"
_NAME_SEPARATOR: Final = ", "

_GAP_LOCALE_KEYS: Final[Mapping[M100GapKind, str]] = {
    M100GapKind.ACCRUED: "application.actividad_asset.served.handoff.gap_accrued",
    M100GapKind.FREE_METHOD: "application.actividad_asset.served.handoff.gap_free",
    M100GapKind.UNAVAILABLE: "application.actividad_asset.served.handoff.gap_unavailable",
    M100GapKind.BOX_UNBOUND: "application.actividad_asset.served.handoff.gap_box_unbound",
}
"""What Modelo 100 leaves out of an element, by what can be said of the interval."""

_LEFT_OUT_LOCALE_KEYS: Final[Mapping[ActivityAssetHandoffLeftOutReason, tuple[str, str, str]]] = {
    ActivityAssetHandoffLeftOutReason.FREE_GAP: (
        "application.actividad_asset.served.handoff.left_out.free_named",
        "application.actividad_asset.served.handoff.left_out.free_count_one",
        "application.actividad_asset.served.handoff.left_out.free_count",
    ),
    ActivityAssetHandoffLeftOutReason.AGRARIAN_EXCLUDED: (
        "application.actividad_asset.served.handoff.left_out.agrarian_named",
        "application.actividad_asset.served.handoff.left_out.agrarian_count_one",
        "application.actividad_asset.served.handoff.left_out.agrarian_count",
    ),
    ActivityAssetHandoffLeftOutReason.UNAVAILABLE: (
        "application.actividad_asset.served.handoff.left_out.unavailable_named",
        "application.actividad_asset.served.handoff.left_out.unavailable_count_one",
        "application.actividad_asset.served.handoff.left_out.unavailable_count",
    ),
}
"""The sentence of each reason a Modelo 130 amount leaves elements out: by name, for one, for several."""

_PARTIAL_ONE_LOCALE_KEY: Final = "application.actividad_asset.served.handoff.partial_one"
_PARTIAL_LOCALE_KEY: Final = "application.actividad_asset.served.handoff.partial"


def _date_text(value: date | str, language: OutputLanguage) -> str:
    return format_casilla_value(
        value if isinstance(value, date) else date.fromisoformat(value), data_type="date", language=language
    )


def _amount_text(value: str | Decimal, language: OutputLanguage) -> str:
    """Write an amount to the cent with the language's marks and no currency sign: a sentence names its currency."""
    number = Decimal(value)
    exponent = number.as_tuple().exponent
    places = max(2, -exponent) if isinstance(exponent, int) else 2
    grouped = group_decimal_text(f"{number:.{places}f}", language)
    return grouped if grouped is not None else str(value)


def _fact_text(fact: ActivityAssetReasonFact, language: OutputLanguage) -> str:
    kind = fact.kind
    if kind is ActivityAssetReasonFactKind.DATE:
        return _date_text(fact.value, language)
    if kind is ActivityAssetReasonFactKind.AMOUNT:
        return _amount_text(fact.value, language)
    if kind is ActivityAssetReasonFactKind.PERCENT:
        return format_casilla_value(
            Decimal(fact.value), data_type="ratio", language=language, ratio_unit=ModeloEditRatioUnit.FRACTION
        )
    return fact.value


def _catalogue_word(key: str | None, language: OutputLanguage) -> str | None:
    """The register catalogue's word for ``key``, or ``None`` when it is outside the register's words or has none."""
    if key is None or not key.startswith(ACTIVITY_ASSET_LABEL_NAMESPACE):
        return None
    if lookup_translation(key, locale=language.value) is None:
        return None
    return tr(key, locale=language.value)


def reason_words(
    key: str | None, facts: Iterable[ActivityAssetReasonFact], language: OutputLanguage
) -> ServedWords | None:
    """Say a reason as its sentence filled in with its facts, or ``None`` when it cannot be said whole."""
    if key is None or _catalogue_word(key, language) is None:
        return None
    said = tr(
        key,
        locale=language.value,
        **{fact.key: _fact_text(fact, language) for fact in facts if fact.key not in _NOT_SAID_FACTS},
    ).strip()
    return None if not said or _UNFILLED.search(said) else said


def remedy_words(field_key: str | None, language: OutputLanguage) -> ServedWords | None:
    """Say which entry settles what a reason lacks, or ``None`` when the field has no word."""
    field = _catalogue_word(field_key, language)
    if field is None:
        return None
    return tr(_OPENING_REMEDY_LOCALE_KEY, locale=language.value, field=field)


def worded_list_row(row: ActivityAssetListRow, language: OutputLanguage) -> ActivityAssetListRow:
    """Serve the sentence of an element's unknown opening amount in ``language``."""
    words = remedy_words(row.opening_remedy_field_key, language)
    return row if words is None else row.model_copy(update={"opening_remedy_words": words, "words_language": language})


def worded_plan_row(row: ActivityAssetPlanRow, language: OutputLanguage) -> ActivityAssetPlanRow:
    """Serve every sentence of one tax year of the plan in ``language``."""
    return row.model_copy(
        update={
            "absence_reason_words": reason_words(row.absence_reason_key, row.absence_reason_facts, language),
            "absence_remedy_words": remedy_words(row.absence_remedy_field_key, language),
            "claimable_refusal_words": reason_words(row.claimable_refusal_key, row.claimable_refusal_facts, language),
            "claimable_refusal_remedy_words": remedy_words(row.claimable_refusal_remedy_field_key, language),
            "minimum_reason_words": reason_words(row.minimum_reason_key, (), language),
            "words_language": language,
        }
    )


def worded_limits(limits: ActivityAssetElectionLimits, language: OutputLanguage) -> ActivityAssetElectionLimits:
    """Serve the sentence for why the registry's limits are not available, in ``language``."""
    return limits.model_copy(
        update={
            "unavailable_reason_words": reason_words(
                limits.unavailable_reason_key, limits.unavailable_reason_facts, language
            ),
            "words_language": language,
        }
    )


def worded_advisory(advisory: ActivityAssetPlanAdvisory, language: OutputLanguage) -> ActivityAssetPlanAdvisory:
    """Serve an advisory of the plan whole in ``language``."""
    return advisory.model_copy(
        update={"words": reason_words(advisory.label_key, (), language), "words_language": language}
    )


def _worded_finding(
    finding: ActivityAssetDisposalFindingView, language: OutputLanguage
) -> ActivityAssetDisposalFindingView:
    return finding.model_copy(
        update={"words": reason_words(finding.label_key, (), language), "words_language": language}
    )


def worded_disposal_calculation(
    view: ActivityAssetDisposalCalculationView, language: OutputLanguage
) -> ActivityAssetDisposalCalculationView:
    """Serve every finding of a baja's calculation whole in ``language``."""
    return view.model_copy(update={"findings": tuple(_worded_finding(item, language) for item in view.findings)})


def refusal_words(
    error: BaseException,
    *,
    key: str | None,
    facts: Iterable[ActivityAssetReasonFact],
    language: OutputLanguage | None,
) -> tuple[ServedWords, OutputLanguage] | None:
    """Say a refusal: its reason in the language asked when it can be said whole, else the error's own sentence.

    The error's own sentence is worded as the operation error detail words it, in the language the worker's
    catalogue renders, which is the language returned with it. ``None`` for an error that has no public sentence.
    """
    if language is not None:
        said = reason_words(key, facts, language)
        if said is not None:
            return said, language
    if isinstance(error, CadrumoError):
        return operation_refusal_words(error)
    return None


def unnamed_element_words(language: OutputLanguage) -> str:
    """How a sentence says an element the register holds no name for."""
    return tr(_UNNAMED_ELEMENT_LOCALE_KEY, locale=language.value)


def m100_gap_words(
    kind: M100GapKind,
    *,
    name: str | None,
    covered_from: date,
    covered_through: date,
    accrued: Decimal | None,
    language: OutputLanguage,
) -> ServedWords:
    """Say an interval of an element that Modelo 100 leaves out, by the element's name and its last day."""
    unworked = kind is M100GapKind.ACCRUED and accrued is None
    return tr(
        _GAP_LOCALE_KEYS[M100GapKind.UNAVAILABLE if unworked else kind],
        locale=language.value,
        name=name if name is not None else unnamed_element_words(language),
        start=_date_text(covered_from, language),
        end=_date_text(covered_through, language),
        amount="" if accrued is None else format_casilla_value(accrued, data_type="money", language=language),
    )


def partial_words(count: int, language: OutputLanguage) -> ServedWords:
    """Say that a Modelo 130 amount leaves out ``count`` elements that could not be worked out."""
    return tr(_PARTIAL_ONE_LOCALE_KEY if count == 1 else _PARTIAL_LOCALE_KEY, locale=language.value, count=count)


def left_out_entry(
    reason: ActivityAssetHandoffLeftOutReason,
    asset_ids: Sequence[str],
    names: Mapping[str, str],
    language: OutputLanguage,
) -> ActivityAssetHandoffLeftOut:
    """Say what one reason leaves out: the elements by name when the register names every one, else how many."""
    named_key, one_key, many_key = _LEFT_OUT_LOCALE_KEYS[reason]
    known = [names[asset_id] for asset_id in asset_ids if asset_id in names]
    if len(known) == len(asset_ids):
        words = tr(named_key, locale=language.value, names=_NAME_SEPARATOR.join(known))
    else:
        words = tr(one_key if len(asset_ids) == 1 else many_key, locale=language.value, count=len(asset_ids))
    return ActivityAssetHandoffLeftOut(reason=reason, asset_ids=tuple(asset_ids), words=words, words_language=language)


__all__ = [
    "left_out_entry",
    "m100_gap_words",
    "partial_words",
    "reason_words",
    "refusal_words",
    "remedy_words",
    "unnamed_element_words",
    "worded_advisory",
    "worded_disposal_calculation",
    "worded_limits",
    "worded_list_row",
    "worded_plan_row",
]
