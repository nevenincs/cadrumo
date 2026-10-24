"""Where every value in the declaration comes from, grouped the way a filer thinks, and said in words.

Every box sits in exactly one group, so each group counts boxes, never the
bindings behind them: your records, registers you keep, your profile, earlier
declarations, AEAT data, values you entered or confirmed, your values
replacing another origin, assumed values waiting for confirmation, values that
still need you, calculated values, values the form sets, figures shown for
information, and boxes left blank or that do not apply. The group follows the
box's origin and, for a value that comes from elsewhere, the family the form
names for it, so a value the calculation took from imported AEAT data reads as
AEAT data whatever its binding would otherwise fetch.

A group fed by sources names each source and whether it produced anything; a
value carried from an earlier declaration names that declaration when the form
does, and the AEAT data by the day it was imported when the form knows it. A
carry with no earlier declaration to read from names none: the group says
there is none, and its source reads as having found nothing. "None found"
means the last calculation read that source and it gave nothing, which differs
from a source not read yet because nothing has been calculated, and from a
zero the source did give, which the box shows as its value. A declaration
recorded as filed asks nothing more, so its assumed values and the values it
was filed without keep their own groups, named for what they hold rather than
for what they ask.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from types import MappingProxyType
from typing import Final

from ...core.aggregation import BindingSourceKind
from ...core.external_constants import OutputLanguage
from ...core.i18n.render import output_language, tr
from .source_policy import SourceFamily, SourcePolicyV1
from .work_form_models import (
    ModeloFormEarlierFiling,
    ModeloFormEditability,
    ModeloFormField,
    ModeloFormOrigin,
    ModeloFormSourceGroup,
    ModeloFormSourceGroupKind,
    ModeloFormSourceReading,
    ModeloFormSourceState,
    ModeloWorkForm,
)
from .work_form_wording import aeat_imported_on, date_text, modelo_number, no_earlier_filing, period_words

_GROUP_LOCALE_KEYS: Final[Mapping[ModeloFormSourceGroupKind, str]] = MappingProxyType(
    {
        ModeloFormSourceGroupKind.RECORDS: "tui.modelo.workbench.sources.group.records",
        ModeloFormSourceGroupKind.REGISTERS: "tui.modelo.workbench.sources.group.registers",
        ModeloFormSourceGroupKind.PROFILE: "tui.modelo.workbench.sources.group.profile",
        ModeloFormSourceGroupKind.EARLIER_DECLARATIONS: "tui.modelo.workbench.sources.group.earlier_declarations",
        ModeloFormSourceGroupKind.AEAT_DATA: "tui.modelo.workbench.sources.group.aeat_data",
        ModeloFormSourceGroupKind.YOURS: "tui.modelo.workbench.sources.group.yours",
        ModeloFormSourceGroupKind.REPLACED: "tui.modelo.workbench.sources.group.replaced",
        ModeloFormSourceGroupKind.ASSUMED: "tui.modelo.workbench.sources.group.assumed",
        ModeloFormSourceGroupKind.NEEDS_YOU: "tui.modelo.workbench.sources.group.needs_you",
        ModeloFormSourceGroupKind.CALCULATED: "tui.modelo.workbench.sources.group.calculated",
        ModeloFormSourceGroupKind.SET_BY_FORM: "tui.modelo.workbench.sources.group.set_by_form",
        ModeloFormSourceGroupKind.INFORMATION: "tui.modelo.workbench.sources.group.information",
        ModeloFormSourceGroupKind.BLANK: "tui.modelo.workbench.sources.group.blank",
        ModeloFormSourceGroupKind.UNNAMED: "tui.modelo.workbench.sources.group.unnamed",
    }
)
FILED_GROUP_LOCALE_KEYS: Final[Mapping[ModeloFormSourceGroupKind, str]] = MappingProxyType(
    {
        ModeloFormSourceGroupKind.ASSUMED: "tui.modelo.workbench.sources.group_filed.assumed",
        ModeloFormSourceGroupKind.NEEDS_YOU: "tui.modelo.workbench.sources.group_filed.needs_you",
    }
)
"""Names for the groups that ask for a value, on a declaration recorded as filed: what they hold, not a request."""
_AEAT_IMPORTED_ON_LOCALE_KEY: Final[str] = "tui.modelo.workbench.sources.group.aeat_data_imported_on"
_NO_EARLIER_GROUP_LOCALE_KEY: Final[str] = "tui.modelo.workbench.sources.group.earlier_declarations_none"
_STATE_LOCALE_KEYS: Final[Mapping[ModeloFormSourceState, str]] = MappingProxyType(
    {
        ModeloFormSourceState.NONE_FOUND: "tui.modelo.workbench.sources.none_found",
        ModeloFormSourceState.NOT_YET: "tui.modelo.workbench.sources.not_yet",
    }
)
_FAMILY_GROUPS: Final[Mapping[SourceFamily, ModeloFormSourceGroupKind]] = MappingProxyType(
    {
        SourceFamily.RECORDS: ModeloFormSourceGroupKind.RECORDS,
        SourceFamily.REGISTERS: ModeloFormSourceGroupKind.REGISTERS,
        SourceFamily.PROFILE: ModeloFormSourceGroupKind.PROFILE,
        SourceFamily.EARLIER_FILINGS: ModeloFormSourceGroupKind.EARLIER_DECLARATIONS,
        SourceFamily.AEAT_DRAFT: ModeloFormSourceGroupKind.AEAT_DATA,
        SourceFamily.YOUR_ENTRIES: ModeloFormSourceGroupKind.YOURS,
        SourceFamily.FIXED_BY_DESIGN: ModeloFormSourceGroupKind.SET_BY_FORM,
    }
)
_ORIGIN_GROUPS: Final[Mapping[ModeloFormOrigin, ModeloFormSourceGroupKind]] = MappingProxyType(
    {
        ModeloFormOrigin.ENTERED: ModeloFormSourceGroupKind.YOURS,
        ModeloFormOrigin.CLEARED: ModeloFormSourceGroupKind.YOURS,
        ModeloFormOrigin.OVERRIDES_SOURCE: ModeloFormSourceGroupKind.REPLACED,
        ModeloFormOrigin.DEFAULT_TO_CONFIRM: ModeloFormSourceGroupKind.ASSUMED,
        ModeloFormOrigin.NEEDS_INPUT: ModeloFormSourceGroupKind.NEEDS_YOU,
        ModeloFormOrigin.CALCULATED: ModeloFormSourceGroupKind.CALCULATED,
        ModeloFormOrigin.NOT_CALCULATED_YET: ModeloFormSourceGroupKind.CALCULATED,
        ModeloFormOrigin.CALCULATION_FAILED: ModeloFormSourceGroupKind.CALCULATED,
        ModeloFormOrigin.NOT_APPLICABLE: ModeloFormSourceGroupKind.BLANK,
        ModeloFormOrigin.OPTIONAL_EMPTY: ModeloFormSourceGroupKind.BLANK,
    }
)
"""Origins that say by themselves who puts the value there; the rest depend on the source."""

#: Origins whose value, when a source feeds the box, comes from that source.
_SOURCED_ORIGINS: Final[frozenset[ModeloFormOrigin]] = frozenset(
    {ModeloFormOrigin.IMPORTED, ModeloFormOrigin.NOT_IMPORTED_YET, ModeloFormOrigin.INFORMATIONAL}
)
#: Groups that ask something of the filer, so a closed group lists their box numbers.
_BOX_LISTING_GROUPS: Final[frozenset[ModeloFormSourceGroupKind]] = frozenset(
    {ModeloFormSourceGroupKind.REPLACED, ModeloFormSourceGroupKind.ASSUMED, ModeloFormSourceGroupKind.NEEDS_YOU}
)


@dataclass(frozen=True, slots=True)
class SourceReading:
    """One source feeding a group: what it gave, and the boxes listed under it."""

    policy: SourcePolicyV1
    state: ModeloFormSourceState
    fields: tuple[ModeloFormField, ...]
    #: The earlier declarations its boxes are carried from, when the form names them.
    earlier_filings: tuple[ModeloFormEarlierFiling, ...] = ()


@dataclass(frozen=True, slots=True)
class SourceGroup:
    """One group of the map: every box whose value comes from there, and the sources that feed them."""

    kind: ModeloFormSourceGroupKind
    fields: tuple[ModeloFormField, ...]
    readings: tuple[SourceReading, ...] = ()
    #: The declaration is recorded as filed, so the group asks nothing of the filer.
    recorded: bool = False
    #: For the AEAT data group, the day the data was imported, when the form knows it.
    imported_on: date | None = None

    @property
    def none_to_carry(self) -> bool:
        """Whether this is the earlier-declarations group and none of its boxes has an earlier declaration to read."""
        return self.kind is ModeloFormSourceGroupKind.EARLIER_DECLARATIONS and all(
            no_earlier_filing(field) for field in self.fields
        )


def value_family(field: ModeloFormField) -> SourceFamily | None:
    """The kind of place a box's value comes from, as the form names it, or ``None`` when nothing feeds it."""
    if field.source is not None:
        return field.source.family
    return field.bindings[0].policy.family if field.bindings else None


def source_group_kind(field: ModeloFormField) -> ModeloFormSourceGroupKind:
    """Place one box in the one group its origin and, for a sourced value, its source family name.

    A value nobody entered stays in its own group on a declaration recorded as
    filed too: it was never calculated, only held, and the group's name then
    says so without asking for a confirmation.
    """
    if field.editability is ModeloFormEditability.DESIGN_CONSTANT:
        return ModeloFormSourceGroupKind.SET_BY_FORM
    by_origin = _ORIGIN_GROUPS.get(field.origin)
    if by_origin is not None:
        return by_origin
    family = value_family(field)
    if family is not None:
        return _FAMILY_GROUPS[family]
    if field.origin is ModeloFormOrigin.INFORMATIONAL:
        return ModeloFormSourceGroupKind.INFORMATION
    return ModeloFormSourceGroupKind.UNNAMED


def _collect_field_sources(
    field: ModeloFormField,
    family: SourceFamily | None,
    policies: dict[BindingSourceKind, SourcePolicyV1],
    produced: dict[BindingSourceKind, bool],
    led: dict[BindingSourceKind, list[ModeloFormField]],
) -> None:
    matching = [binding for binding in field.bindings if binding.policy.family is family]
    for position, binding in enumerate(matching):
        kind = binding.policy.source_kind
        policies.setdefault(kind, binding.policy)
        produced[kind] = produced.get(kind, False) or binding.resolved
        listed = led.setdefault(kind, [])
        if position == 0:
            listed.append(field)


def _reading_state(
    kind: BindingSourceKind,
    fields: list[ModeloFormField],
    produced: Mapping[BindingSourceKind, bool],
    *,
    calculated: bool,
) -> ModeloFormSourceState:
    if fields and all(no_earlier_filing(field) for field in fields):
        # A carry with no earlier declaration to read produced nothing, whatever zero it resolved to.
        return ModeloFormSourceState.NONE_FOUND
    if produced[kind]:
        return ModeloFormSourceState.PRODUCED
    return ModeloFormSourceState.NONE_FOUND if calculated else ModeloFormSourceState.NOT_YET


def _readings(fields: tuple[ModeloFormField, ...], *, calculated: bool) -> tuple[SourceReading, ...]:
    """Each source of the family a box's value comes from, the boxes it leads for and what it gave.

    A box sits under the first of its sources in that family. A value the AEAT
    data supplied names no source of that family, so its box is listed on its
    own rather than under the source its binding would otherwise read.
    """
    policies: dict[BindingSourceKind, SourcePolicyV1] = {}
    produced: dict[BindingSourceKind, bool] = {}
    led: dict[BindingSourceKind, list[ModeloFormField]] = {}
    for field in fields:
        family = value_family(field)
        _collect_field_sources(field, family, policies, produced, led)
    readings: list[SourceReading] = []
    for kind, policy in policies.items():
        state = _reading_state(kind, led[kind], produced, calculated=calculated)
        readings.append(
            SourceReading(
                policy=policy, state=state, fields=tuple(led[kind]), earlier_filings=earlier_filings(led[kind])
            )
        )
    return tuple(readings)


def earlier_filings(fields: Iterable[ModeloFormField]) -> tuple[ModeloFormEarlierFiling, ...]:
    """The earlier declarations the form names as the origin of these boxes, each once, in form order."""
    named: dict[ModeloFormEarlierFiling, None] = {}
    for field in fields:
        source = field.source
        if source is not None and source.family is SourceFamily.EARLIER_FILINGS:
            named.update(dict.fromkeys(source.earlier_filings))
    return tuple(named)


def source_groups(form: ModeloWorkForm) -> tuple[SourceGroup, ...]:
    """Every box of the form in exactly one group, groups in the filer's order, boxes in form order."""
    recorded = form.filing is not None
    placed: dict[ModeloFormSourceGroupKind, list[ModeloFormField]] = {}
    for field in form.fields():
        placed.setdefault(source_group_kind(field), []).append(field)
    calculated = form.calculation_revision_id is not None
    groups: list[SourceGroup] = []
    for kind in ModeloFormSourceGroupKind:
        fields = tuple(placed.get(kind, ()))
        if not fields:
            continue
        sourced = kind in _FAMILY_GROUPS.values() and any(
            field.origin in _SOURCED_ORIGINS and field.bindings for field in fields
        )
        readings = _readings(fields, calculated=calculated) if sourced else ()
        imported_on = aeat_imported_on(form) if kind is ModeloFormSourceGroupKind.AEAT_DATA else None
        groups.append(
            SourceGroup(kind=kind, fields=fields, readings=readings, recorded=recorded, imported_on=imported_on)
        )
    return tuple(groups)


def group_boxes(group: SourceGroup) -> tuple[str, ...]:
    """The box numbers a closed group lists, for the groups that ask something of the filer."""
    if group.kind not in _BOX_LISTING_GROUPS:
        return ()
    return tuple(field.box for field in group.fields if (field.box is not None and field.box))


def earlier_filing_text(filings: Sequence[ModeloFormEarlierFiling], language: OutputLanguage | None = None) -> str:
    """Name earlier declarations by their modelo and period in words."""
    return ", ".join(
        f"{modelo_number(filing.modelo, language)} · {period_words(filing.period, language)}" for filing in filings
    )


def _locale(language: OutputLanguage | None) -> dict[str, str]:
    return {} if language is None else {"locale": language.value}


def reading_text(reading: SourceReading, language: OutputLanguage | None = None) -> str:
    """Name one source, by the earlier declaration when the form names it, saying when it found nothing yet."""
    label = (
        earlier_filing_text(reading.earlier_filings, language)
        if reading.earlier_filings
        else tr(reading.policy.label_key, **_locale(language))
    )
    state_key = _STATE_LOCALE_KEYS.get(reading.state)
    return label if state_key is None else tr(state_key, source=label, **_locale(language))


def group_summary(group: SourceGroup, language: OutputLanguage | None = None) -> str:
    """The sources of a group in words, or the earlier declarations its boxes are carried from."""
    if group.readings:
        return " · ".join(reading_text(reading, language) for reading in group.readings)
    if group.kind is ModeloFormSourceGroupKind.EARLIER_DECLARATIONS:
        return earlier_filing_text(earlier_filings(group.fields), language)
    return ""


def group_name(
    kind: ModeloFormSourceGroupKind,
    *,
    language: OutputLanguage | None = None,
    recorded: bool = False,
    imported_on: date | None = None,
    none_to_carry: bool = False,
) -> str:
    """A group's name in ``language``, the active output language when not given.

    On a declaration ``recorded`` as filed, a group that would ask names what
    it holds. The AEAT data group names the day ``imported_on`` the data was
    imported, and an earlier-declarations group with ``none_to_carry`` says
    there is no earlier declaration to read.
    """
    locale = _locale(language)
    if recorded and kind in FILED_GROUP_LOCALE_KEYS:
        return tr(FILED_GROUP_LOCALE_KEYS[kind], **locale)
    if kind is ModeloFormSourceGroupKind.EARLIER_DECLARATIONS and none_to_carry:
        return tr(_NO_EARLIER_GROUP_LOCALE_KEY, **locale)
    if kind is ModeloFormSourceGroupKind.AEAT_DATA and imported_on is not None:
        written = date_text(imported_on, OutputLanguage(output_language()) if language is None else language)
        return tr(_AEAT_IMPORTED_ON_LOCALE_KEY, date=written, **locale)
    return tr(_GROUP_LOCALE_KEYS[kind], **locale)


def worded_source_groups(form: ModeloWorkForm) -> tuple[ModeloFormSourceGroup, ...]:
    """Every group of the form said in its language, each box once, sources under the groups they feed."""
    language = form.language
    return tuple(
        ModeloFormSourceGroup(
            kind=group.kind,
            name=group_name(
                group.kind,
                language=language,
                recorded=group.recorded,
                imported_on=group.imported_on,
                none_to_carry=group.none_to_carry,
            ),
            summary=group_summary(group, language),
            boxes=group_boxes(group),
            recorded=group.recorded,
            addresses=tuple(field.address for field in group.fields),
            readings=tuple(
                ModeloFormSourceReading(
                    source_kind=reading.policy.source_kind,
                    surface=reading.policy.surface,
                    state=reading.state,
                    words=reading_text(reading, language),
                    addresses=tuple(field.address for field in reading.fields),
                )
                for reading in group.readings
            ),
        )
        for group in source_groups(form)
    )


def _require_total_tables() -> None:
    """Refuse a group without a name, a source family without a group, or an origin without one."""
    if set(_GROUP_LOCALE_KEYS) != set(ModeloFormSourceGroupKind):
        raise ValueError("every source group needs a name")
    if set(_FAMILY_GROUPS) != set(SourceFamily):
        raise ValueError("every source family needs a group")
    if set(_ORIGIN_GROUPS) | _SOURCED_ORIGINS != set(ModeloFormOrigin):
        raise ValueError("every origin needs a group, or a source to take one from")


_require_total_tables()


__all__ = [
    "FILED_GROUP_LOCALE_KEYS",
    "SourceGroup",
    "SourceReading",
    "earlier_filing_text",
    "earlier_filings",
    "group_boxes",
    "group_name",
    "group_summary",
    "reading_text",
    "source_group_kind",
    "source_groups",
    "value_family",
    "worded_source_groups",
]
