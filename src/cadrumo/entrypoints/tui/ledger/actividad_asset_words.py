"""The words the activity-asset screen reads the register's served results in.

The application serves tokens, catalogue keys and the facts that fill them; this
module words them for the operator and does no tax arithmetic. A token or key the
catalogue has no word for reads as a generic word, never as the raw token.
"""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal
from typing import Final, Literal

from ....application.actividad_asset.activity_asset_read_models import (
    ACTIVITY_ASSET_LABEL_NAMESPACE,
    ActivityAssetClaimState,
    ActivityAssetElectionLimits,
    ActivityAssetFormOptionsView,
    ActivityAssetListDisposal,
    ActivityAssetListRow,
    ActivityAssetPlanRow,
    ActivityAssetReasonFact,
    ActivityAssetReasonFactKind,
    ActivityAssetTimelineChange,
    ActivityAssetTimelineEvent,
    activity_asset_label_key,
)
from ....application.modelo.edit_value_grammar import ModeloEditRatioUnit
from ....application.modelo.value_presentation import format_casilla_value
from ....core.external_constants import OutputLanguage
from ....core.i18n.render import lookup_translation, output_language, tr

#: The glyph a year's claim state is drawn with; the state's word stands beside it.
_CLAIM_STATE_GLYPH: Final = {
    ActivityAssetClaimState.CLAIMED: "✓",
    ActivityAssetClaimState.SUPERSEDED: "✓",
    ActivityAssetClaimState.MISSING: "!",
    ActivityAssetClaimState.PARTIAL: "▲",
    ActivityAssetClaimState.NOT_DUE: "○",
    ActivityAssetClaimState.EDITION_UNAVAILABLE: "?",
}

_UNFILLED: Final = re.compile(r"%\{\w+\}|\{\w+\}")
_ISO_DATE: Final = re.compile(r"\d{4}-\d{2}-\d{2}")
_LOOKS_INTERNAL: Final = re.compile(r"(?i)[a-z0-9]+(?:[_.:-][a-z0-9]+)+|[0-9a-f]{16,}")

#: Fact names a sentence is never filled with; they identify records for a screen to act on.
_NOT_SAID_FACTS: Final = frozenset({"conflicting_claim_ids"})

_ASSET_KEYS: Final = {
    "no_name": "desktop.ledger.assets.list.no_name",
    "not_known": "desktop.ledger.assets.not_known",
    "not_applicable": "desktop.ledger.assets.mark.not_applicable",
    "nothing_recorded": "desktop.ledger.assets.mark.nothing_recorded",
    "opening_unknown": "desktop.ledger.assets.opening_unknown",
    "baja": "desktop.ledger.assets.plan.baja",
    "planned_missing": "desktop.ledger.assets.plan.planned_missing",
    "minimum_missing": "desktop.ledger.assets.plan.minimum_missing",
    "claimable_none": "desktop.ledger.assets.plan.claimable_none",
    "edition": "desktop.ledger.assets.plan.edition",
    "year_estimated": "desktop.ledger.assets.year_estimated",
    "limits_ends_on": "desktop.ledger.assets.plan.limits.ends_on",
    "time_not_recorded": "desktop.ledger.assets.timeline.time_not_recorded",
    "not_in_calculation": "desktop.ledger.assets.timeline.not_in_calculation",
    "effect_missing": "desktop.ledger.assets.timeline.effect_missing",
    "claim_span": "desktop.ledger.assets.timeline.claim_span",
    "no_changes": "desktop.ledger.assets.timeline.no_changes",
    "value_changed": "desktop.ledger.assets.timeline.value_changed",
    "change_added": "desktop.ledger.assets.timeline.change_added",
    "change_cleared": "desktop.ledger.assets.timeline.change_cleared",
    "change_to": "desktop.ledger.assets.timeline.change_to",
    "field_other": "desktop.ledger.assets.field.other",
    "unrecognised": "desktop.ledger.assets.unrecognised",
    "quarter": "desktop.ledger.assets.quarter",
}


def _text(name: str, **fields: object) -> str:
    return tr(_ASSET_KEYS[name], **fields)


def _language() -> OutputLanguage:
    return OutputLanguage(output_language())


def date_text(value: date | str) -> str:
    """Write a day the way the interface language does."""
    return format_casilla_value(
        value if isinstance(value, date) else date.fromisoformat(value), data_type="date", language=_language()
    )


def amount_text(value: str) -> str:
    """Write an amount served as a plain decimal to the cent, as the interface language does."""
    return format_casilla_value(Decimal(value), data_type="money", language=_language())


def _fact_text(fact: ActivityAssetReasonFact) -> str:
    kind = fact.kind
    if kind is ActivityAssetReasonFactKind.DATE:
        return date_text(fact.value)
    if kind is ActivityAssetReasonFactKind.AMOUNT:
        return amount_text(fact.value)
    if kind is ActivityAssetReasonFactKind.PERCENT:
        return format_casilla_value(
            Decimal(fact.value), data_type="ratio", language=_language(), ratio_unit=ModeloEditRatioUnit.FRACTION
        )
    return fact.value


def word_of_key(key: str | None) -> str | None:
    """Say a register catalogue key, or ``None`` when it is outside the register's words or has none."""
    if key is None or not key.startswith(ACTIVITY_ASSET_LABEL_NAMESPACE):
        return None
    if lookup_translation(key, locale=output_language()) is None:
        return None
    return tr(key)


def reason_text(key: str | None, facts: tuple[ActivityAssetReasonFact, ...] = ()) -> str | None:
    """Say a reason as its sentence filled in with its facts, or ``None`` when it cannot be said whole."""
    if word_of_key(key) is None or key is None:
        return None
    said = tr(key, **{fact.key: _fact_text(fact) for fact in facts if fact.key not in _NOT_SAID_FACTS})
    return None if _UNFILLED.search(said) else said


def token_word(family: str, token: str | None) -> str:
    """Say a token of one of the register's families, or the generic word the catalogue has for an unknown one."""
    if token is None:
        return _text("unrecognised")
    word = word_of_key(f"{ACTIVITY_ASSET_LABEL_NAMESPACE}{family}.{token}")
    return word if word is not None else _text("unrecognised")


def opening_remedy(field_key: str | None) -> str | None:
    """Say which entry settles an unknown opening amount, or ``None`` when the field has no word."""
    field = word_of_key(field_key)
    return None if field is None else _text("opening_unknown", field=field)


def baja_text(disposal: ActivityAssetListDisposal) -> str:
    """Say the baja an element records by its day and its reason."""
    reason = word_of_key(disposal.reason_key) or token_word("disposal_reason", disposal.reason.value)
    return _text("baja", date=date_text(disposal.disposal_date), reason=reason)


def claim_state_text(state: ActivityAssetClaimState) -> str:
    """Say a year's claim state as a glyph and its word."""
    word = word_of_key(activity_asset_label_key("claim_state", state))
    return f"{_CLAIM_STATE_GLYPH[state]} {word if word is not None else _text('unrecognised')}"


#: The glyph and the finding count it stands for, in the order the list shows them.
_FINDING_GLYPHS: Final = (
    ("missing", "!"),
    ("incomplete", "?"),
    ("conflict", "×"),
    ("unsupported", "—"),
    ("without_tables", "○"),
    ("stale", "▲"),
)


def list_row_line(row: ActivityAssetListRow) -> str:
    """Say one element of the register: its name, state, what is still to amortise and what needs attention."""
    state = word_of_key(activity_asset_label_key("register_state", row.state)) or _text("unrecognised")
    if not row.pending_applies:
        # After a baja nothing is left to amortise, so the figure is not drawn and the mark says why.
        pending = _text("not_applicable")
        if row.disposal is not None:
            pending = f"{pending} ({baja_text(row.disposal)})"
    elif row.pending is None:
        remedy = opening_remedy(row.opening_remedy_field_key)
        pending = _text("not_known") if remedy is None else f"{_text('not_known')} ({remedy})"
    else:
        pending = amount_text(row.pending.decimal)
    attention = " ".join(
        f"[{glyph}] {count}" for name, glyph in _FINDING_GLYPHS if (count := getattr(row.findings, name)) > 0
    )
    fields = [row.name or _text("no_name"), state, pending]
    if attention:
        fields.append(attention)
    # The id comes last: it is only what the asset field needs to address the element.
    fields.append(row.asset_id)
    return "\t".join(fields)


def limits_line(limits: ActivityAssetElectionLimits) -> str | None:
    """Say what the registry allows the election: its table class and when the maximum period ends."""
    fields: list[str] = []
    if limits.class_label is not None:
        fields.append(limits.class_label)
    word = word_of_key(
        None if limits.not_table_bound is None else activity_asset_label_key("not_table_bound", limits.not_table_bound),
    )
    if word is not None:
        fields.append(word)
    unavailable = reason_text(limits.unavailable_reason_key, limits.unavailable_reason_facts)
    if unavailable is not None:
        fields.append(unavailable)
    if limits.maximum_period_last_day is not None:
        fields.append(f"{_text('limits_ends_on')}: {date_text(limits.maximum_period_last_day)}")
    return "\t".join(fields) if fields else None


def _planned_text(row: ActivityAssetPlanRow) -> str:
    if row.planned is not None:
        return amount_text(row.planned.decimal)
    if not row.applies:
        return _text("not_applicable")
    parts = [token_word("plan_absence", row.absence.value)] if row.absence is not None else []
    reason = reason_text(row.absence_reason_key, row.absence_reason_facts)
    if reason is not None:
        parts.append(reason)
    remedy = opening_remedy(row.absence_remedy_field_key)
    if remedy is not None:
        parts.append(remedy)
    return " ".join(parts) if parts else _text("planned_missing")


def _recorded_text(row: ActivityAssetPlanRow) -> str:
    if row.claims or Decimal(row.claimed.decimal) != 0:
        return amount_text(row.claimed.decimal)
    # A year that applies has nothing recorded; one that does not apply says so.
    return _text("nothing_recorded" if row.applies else "not_applicable")


def minimum_text(label: str, incomplete: str, row: ActivityAssetPlanRow) -> str:
    """Say the minimum amortisation to a year's end, naming a year without authority rather than hiding it."""
    if row.minimum_through is None:
        return f"{label}: {reason_text(row.minimum_reason_key) or _text('minimum_missing')}"
    figure = f"{label}: {amount_text(row.minimum_through.decimal)}"
    return figure if row.minimum_complete else f"{figure} ({incomplete})"


def _nothing_open_text(row: ActivityAssetPlanRow) -> str | None:
    """Say why no span is open to record in a year, with the entry to fill in when that is the remedy."""
    if row.claimable_intervals:
        return None
    refusal = reason_text(row.claimable_refusal_key, row.claimable_refusal_facts)
    if refusal is not None:
        remedy = opening_remedy(row.claimable_refusal_remedy_field_key)
        return refusal if remedy is None else f"{refusal} {remedy}"
    return None if row.claim_state is ActivityAssetClaimState.NOT_DUE else _text("claimable_none")


def plan_row_line(row: ActivityAssetPlanRow, *, minimum_label: str, minimum_incomplete: str) -> str:
    """Say one tax year of the plan: its state, planned and recorded figures, minimum and why nothing is open."""
    year = str(row.tax_year)
    if row.edition is not None and row.edition.projected:
        year = _text("year_estimated", year=year)
    fields = [
        year,
        claim_state_text(row.claim_state),
        _planned_text(row),
        _recorded_text(row),
        minimum_text(minimum_label, minimum_incomplete, row),
    ]
    nothing_open = _nothing_open_text(row)
    if nothing_open is not None:
        fields.append(nothing_open)
    return "\t".join(fields)


def form_options_text(options: ActivityAssetFormOptionsView) -> str:
    """Say what the registry admits for the kind and year: the methods, table groups and the tables' edition."""
    fields = [
        f"{tr('desktop.ledger.assets.field.method')}: "
        + ", ".join(token_word("method", method.value) for method in options.methods),
    ]
    if options.table_groups:
        groups = ", ".join(group.class_label for group in options.table_groups)
        fields.append(f"{tr('desktop.ledger.assets.field.class')}: {groups}")
    fields.append(_text("edition", edition=options.edition.authored_filing_year))
    if options.m130_periods:
        fields.append(quarters_text(options.m130_periods))
    return "\t".join(fields)


def quarters_text(periods: tuple[str, ...]) -> str:
    """Say the Modelo 130 periods the registry serves for the year."""
    return f"{_text('quarter')}: {', '.join(periods)}"


def _change_value(change: ActivityAssetTimelineChange, side: Literal["before", "after"]) -> str:
    """Say one side of a change: the register's own label, then the word of its key, then the value by its look."""
    value = change.before if side == "before" else change.after
    label = change.before_label if side == "before" else change.after_label
    key = change.before_key if side == "before" else change.after_key
    return _change_value_text(value, label, key)


def _change_value_text(value: str | None, label: str | None, key: str | None) -> str:
    if value is None:
        return _text("value_changed")
    if label is not None and label.strip():
        return label
    if key is not None:
        return word_of_key(key) or _text("value_changed")
    if _ISO_DATE.fullmatch(value):
        return date_text(value)
    return _text("value_changed") if _LOOKS_INTERNAL.fullmatch(value) else value


def _change_text(change: ActivityAssetTimelineChange) -> str:
    field = word_of_key(change.field_key) or _text("field_other")
    if change.before is None:
        return _text("change_added", field=field, after=_change_value(change, "after"))
    if change.after is None:
        return _text("change_cleared", field=field, before=_change_value(change, "before"))
    return f"{field}: {_change_value(change, 'before')} {_text('change_to')} {_change_value(change, 'after')}"


def timeline_line(event: ActivityAssetTimelineEvent) -> str:
    """Say one record of an element's history: when, what it did, its effective day and what it changed."""
    recorded = _text("time_not_recorded") if event.recorded_at is None else date_text(event.recorded_at.date())
    what = token_word("event_kind", None if event.event_kind is None else event.event_kind.value)
    fields = [
        str(event.sequence),
        recorded,
        what,
        _text("effect_missing") if event.effect_date is None else date_text(event.effect_date),
    ]
    if not event.affects_calculation:
        fields.append(_text("not_in_calculation"))
    claim_span = _timeline_claim_span(event)
    if claim_span is not None:
        fields.append(claim_span)
    fields.extend(_change_text(change) for change in event.changes)
    if not event.changes:
        fields.append(_text("no_changes"))
    return "\t".join(fields)


def _timeline_claim_span(event: ActivityAssetTimelineEvent) -> str | None:
    claim = event.claim
    if claim is not None and claim.tax_year is not None and claim.covered_from and claim.covered_through:
        return _text(
            "claim_span",
            year=claim.tax_year,
            **{"from": date_text(claim.covered_from)},
            through=date_text(claim.covered_through),
        )
    return None


__all__ = [
    "amount_text",
    "baja_text",
    "claim_state_text",
    "date_text",
    "form_options_text",
    "limits_line",
    "list_row_line",
    "minimum_text",
    "opening_remedy",
    "plan_row_line",
    "quarters_text",
    "reason_text",
    "timeline_line",
    "token_word",
    "word_of_key",
]
