"""Modelo 200 page 002 rows from the taxpayer profile.

The administradores and the other relations of an Impuesto sobre Sociedades declarant
are profile facts that hold across returns. This module is the one mapping from those
profile sections to :class:`Modelo200ProjectionRows`: the registry names each page 002
projection kind's profile section and the rules that decide whether the return must
carry it, the export layout of the edition in force gives the field names and how many
rows fit, and the profile in force at the period end supplies the rows.

A family the return must carry and the profile does not answer refuses with the
profile-readiness refusal and a door to the profile detail that answers it. A family a
stored fact rules out is served as not applicable together with that fact.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum

from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.m200_page_002_rules import (
    M200Page002FamilyRule,
    M200Page002Rules,
    resolve_m200_page_002_rules,
)
from ...domain.calculations.registry.schema_exports import ExportLayoutDefinition
from ...domain.modelos.work_unit import WorkUnit
from ...domain.user_profile.schema import ProfileFieldType, ProfileSchemaDefinition, ProfileSectionDefinition
from ...domain.user_profile.values import UserProfileRecord
from ..filing.m200_projection import (
    m200_projection_families,
    m200_projection_field_widths,
    m200_projection_slot_limits,
)
from ..filing.producer_snapshot_m200 import Modelo200ProfileFacts, Modelo200ProjectionRows
from ..user_profile.completeness import profile_section_rows
from ..user_profile.projections import record_to_path_values
from .action_errors import ModeloProfileReadinessError
from .lifecycle_view_refusal_doors import profile_facts_verdict
from .profile_readiness_gate import open_profile_path_step

_STATED_YES = "true"
_STATED_NO = "false"
_MARKED = "1"
_UNMARKED = "0"
_PROFILE_FACTS_MISSING_MESSAGE = "application.modelo.errors.profile_readiness_missing"


class M200Page002FamilyState(StrEnum):
    """How the profile in force answers one page 002 family."""

    ROWS = "rows"
    STATED_NONE = "stated_none"
    UNANSWERED = "unanswered"
    NOT_APPLICABLE = "not_applicable"


class M200Page002Refusal(StrEnum):
    """Why the profile cannot supply page 002, carried as the refusal's ``reason``."""

    ROWS_REQUIRED = "m200_page_002_rows_required"
    FAMILY_UNANSWERED = "m200_page_002_family_unanswered"
    ROW_INCOMPLETE = "m200_page_002_row_incomplete"
    DECIDING_FACT_MISSING = "m200_page_002_deciding_fact_missing"
    NONE_REFUSED_FOR_FORM = "m200_page_002_none_refused_for_form"
    PERCENTAGE_TOTAL = "m200_page_002_percentage_total"
    ROWS_CONTRADICT_ANSWER = "m200_page_002_rows_contradict_answer"
    ROWS_EXCEED_DESIGN = "m200_page_002_rows_exceed_design"
    VALUE_EXCEEDS_DESIGN = "m200_page_002_value_exceeds_design"


_REFUSAL_LOCALE_KEYS: Mapping[M200Page002Refusal, str] = {
    M200Page002Refusal.ROWS_REQUIRED: _PROFILE_FACTS_MISSING_MESSAGE,
    M200Page002Refusal.FAMILY_UNANSWERED: _PROFILE_FACTS_MISSING_MESSAGE,
    M200Page002Refusal.ROW_INCOMPLETE: _PROFILE_FACTS_MISSING_MESSAGE,
    M200Page002Refusal.DECIDING_FACT_MISSING: _PROFILE_FACTS_MISSING_MESSAGE,
    M200Page002Refusal.NONE_REFUSED_FOR_FORM: "application.modelo.errors.m200_page_002_none_refused_for_form",
    M200Page002Refusal.PERCENTAGE_TOTAL: "application.modelo.errors.m200_page_002_percentage_total",
    M200Page002Refusal.ROWS_CONTRADICT_ANSWER: "application.modelo.errors.m200_page_002_rows_contradict_answer",
    M200Page002Refusal.ROWS_EXCEED_DESIGN: "application.modelo.errors.m200_page_002_rows_exceed_design",
    M200Page002Refusal.VALUE_EXCEEDS_DESIGN: "application.modelo.errors.m200_page_002_value_exceeds_design",
}


@dataclass(frozen=True, slots=True)
class M200Page002FamilyAnswer:
    """One page 002 family as the profile in force answers it, with the fact that decides it.

    ``deciding_fact`` and ``deciding_value`` name the stored fact that made the family
    not applicable, or that a stated answer was read from; they are absent for a family
    answered by its rows or left unanswered.
    """

    projection_kind: str
    section: str
    state: M200Page002FamilyState
    deciding_fact: str | None = None
    deciding_value: str | None = None


@dataclass(frozen=True, slots=True)
class _Coordinates:
    """What every refusal states about the return it refuses."""

    modelo: str
    filing_year: int
    period: str
    as_of: date


def m200_page_002_family_answers(
    record: UserProfileRecord | None,
    *,
    rules: M200Page002Rules,
    as_of: date,
) -> tuple[M200Page002FamilyAnswer, ...]:
    """Serve how the profile in force on ``as_of`` answers each page 002 family.

    A family a stored entity form rules out is not applicable whatever else the
    profile holds; otherwise its rows answer it, then its stated answer, and with
    neither it is unanswered.
    """
    values = record_to_path_values(record, as_of=as_of)
    return tuple(_family_answer(rule, values, rules=rules) for rule in rules.families)


def _family_answer(
    rule: M200Page002FamilyRule, values: Mapping[str, str], *, rules: M200Page002Rules
) -> M200Page002FamilyAnswer:
    form = values.get(rules.entity_form_fact)
    if form is not None and form in rule.not_applicable_forms:
        return M200Page002FamilyAnswer(
            projection_kind=rule.projection_kind,
            section=rule.section,
            state=M200Page002FamilyState.NOT_APPLICABLE,
            deciding_fact=rules.entity_form_fact,
            deciding_value=form,
        )
    if _section_rows(values, rule.section):
        return M200Page002FamilyAnswer(
            projection_kind=rule.projection_kind, section=rule.section, state=M200Page002FamilyState.ROWS
        )
    stated = None if rule.stated_answer is None else values.get(rule.stated_answer)
    if stated == _STATED_NO:
        return M200Page002FamilyAnswer(
            projection_kind=rule.projection_kind,
            section=rule.section,
            state=M200Page002FamilyState.STATED_NONE,
            deciding_fact=rule.stated_answer,
            deciding_value=stated,
        )
    return M200Page002FamilyAnswer(
        projection_kind=rule.projection_kind, section=rule.section, state=M200Page002FamilyState.UNANSWERED
    )


def modelo_200_profile_facts(
    *,
    work_unit: WorkUnit,
    operation: PinnedAuthorityOperation,
    export_layout: ExportLayoutDefinition,
    profile_record: UserProfileRecord | None,
) -> Modelo200ProfileFacts:
    """Build the Modelo 200 profile facts whose page 002 rows the profile in force supplies.

    Raises:
        ModeloProfileReadinessError: When a family the return must carry is not
            answered, a row lacks a fact the design requires of it, a stated answer
            contradicts the rows, the B.2 percentages miss their total, or more rows
            are stored than the edition's design has places for, or a text value is
            wider than the design place that prints it.
    """
    as_of = work_unit.period.end_date
    return Modelo200ProfileFacts(
        projection_rows=_projection_rows(
            profile_record,
            schema=operation.profile_schema(),
            rules=resolve_m200_page_002_rules(operation, effective_date=as_of),
            families=m200_projection_families(as_of, authority=operation),
            slot_limits=m200_projection_slot_limits(export_layout),
            field_widths=m200_projection_field_widths(export_layout),
            coordinates=_Coordinates(
                modelo=str(work_unit.modelo),
                filing_year=work_unit.filing_year,
                period=work_unit.period.registry_token,
                as_of=as_of,
            ),
        ),
    )


def _projection_rows(
    record: UserProfileRecord | None,
    *,
    schema: ProfileSchemaDefinition,
    rules: M200Page002Rules,
    families: Mapping[str, str],
    slot_limits: Mapping[str, int],
    field_widths: Mapping[tuple[str, str], int],
    coordinates: _Coordinates,
) -> Modelo200ProjectionRows:
    """Map the profile's page 002 sections onto the typed projection rows, or refuse."""
    values = record_to_path_values(record, as_of=coordinates.as_of)
    projected: dict[str, tuple[dict[str, str | None], ...]] = {}
    for rule in rules.families:
        rows = _family_rows(
            rule, values, schema=schema, rules=rules, slot_limits=slot_limits, field_widths=field_widths, at=coordinates
        )
        if rows:
            projected[families[rule.projection_kind]] = rows
    return Modelo200ProjectionRows.model_validate(projected)


def _family_rows(
    rule: M200Page002FamilyRule,
    values: Mapping[str, str],
    *,
    schema: ProfileSchemaDefinition,
    rules: M200Page002Rules,
    slot_limits: Mapping[str, int],
    field_widths: Mapping[tuple[str, str], int],
    at: _Coordinates,
) -> tuple[dict[str, str | None], ...]:
    answer = _family_answer(rule, values, rules=rules)
    rows = _section_rows(values, rule.section)
    form = values.get(rules.entity_form_fact)
    stated = None if rule.stated_answer is None else values.get(rule.stated_answer)
    if answer.state is M200Page002FamilyState.NOT_APPLICABLE:
        if rows:
            raise _refusal(
                M200Page002Refusal.ROWS_CONTRADICT_ANSWER,
                _first_required_path(schema.section(rule.section)),
                at,
                section=rule.section,
                deciding_fact=rules.entity_form_fact,
            )
        return ()
    if not rows:
        _require_none_admissible(rule, stated=stated, form=form, schema=schema, rules=rules, at=at)
        return ()
    if stated == _STATED_NO and rule.stated_answer is not None:
        raise _refusal(
            M200Page002Refusal.ROWS_CONTRADICT_ANSWER,
            rule.stated_answer,
            at,
            section=rule.section,
            deciding_fact=rule.stated_answer,
        )
    section = schema.section(rule.section)
    limit = slot_limits.get(rule.projection_kind, 0)
    if len(rows) > limit:
        raise _refusal(
            M200Page002Refusal.ROWS_EXCEED_DESIGN,
            _first_required_path(section),
            at,
            section=rule.section,
            rows=len(rows),
            slots=limit,
        )
    non_resident = _non_resident(rule, values, rules=rules, at=at)
    projected = tuple(
        _row(rule, section, key, populated, values, non_resident=non_resident, field_widths=field_widths, at=at)
        for key, populated in rows.items()
    )
    _require_percentage_total(rule, projected, form=form, rules=rules, at=at)
    return projected


def _require_none_admissible(
    rule: M200Page002FamilyRule,
    *,
    stated: str | None,
    form: str | None,
    schema: ProfileSchemaDefinition,
    rules: M200Page002Rules,
    at: _Coordinates,
) -> None:
    rows_path = _first_required_path(schema.section(rule.section))
    if rule.stated_answer is None or stated == _STATED_YES:
        raise _refusal(M200Page002Refusal.ROWS_REQUIRED, rows_path, at, section=rule.section)
    if stated is None:
        raise _refusal(M200Page002Refusal.FAMILY_UNANSWERED, rule.stated_answer, at, section=rule.section)
    if not rule.rows_required_forms:
        return
    if form is None:
        raise _refusal(M200Page002Refusal.DECIDING_FACT_MISSING, rules.entity_form_fact, at, section=rule.section)
    if form in rule.rows_required_forms:
        raise _refusal(M200Page002Refusal.NONE_REFUSED_FOR_FORM, rows_path, at, section=rule.section, entity_form=form)


def _non_resident(
    rule: M200Page002FamilyRule, values: Mapping[str, str], *, rules: M200Page002Rules, at: _Coordinates
) -> bool:
    if not rule.non_resident_only_fields:
        return False
    residency = values.get(rules.non_resident_fact)
    if residency is None:
        raise _refusal(M200Page002Refusal.DECIDING_FACT_MISSING, rules.non_resident_fact, at, section=rule.section)
    return residency == rules.non_resident_value


def _row(
    rule: M200Page002FamilyRule,
    section: ProfileSectionDefinition,
    key: str,
    populated: frozenset[str],
    values: Mapping[str, str],
    *,
    non_resident: bool,
    field_widths: Mapping[tuple[str, str], int],
    at: _Coordinates,
) -> dict[str, str | None]:
    resident_blank = set() if non_resident else set(rule.non_resident_only_fields)
    required = {field.key for field in section.fields if field.required}
    if non_resident:
        required |= set(rule.non_resident_only_fields)
    missing = sorted(required - populated)
    if missing:
        raise _refusal(
            M200Page002Refusal.ROW_INCOMPLETE,
            f"{rule.section}.{missing[0]}",
            at,
            section=rule.section,
            row=key,
            missing_fields=", ".join(missing),
        )
    prefix = f"{rule.section}.{key}." if key else f"{rule.section}."
    row: dict[str, str | None] = {}
    for field in section.fields:
        if field.key in resident_blank:
            row[field.key] = None
            continue
        value = _design_value(field.type, values.get(f"{prefix}{field.key}"))
        _require_fits(rule, key, field.key, value, width=field_widths.get((rule.projection_kind, field.key)), at=at)
        row[field.key] = value
    return row


def _require_fits(
    rule: M200Page002FamilyRule, key: str, field_key: str, value: str | None, *, width: int | None, at: _Coordinates
) -> None:
    """Refuse a value wider than the design place that prints it, naming the place, never the value."""
    if value is None or width is None or len(value) <= width:
        return
    raise _refusal(
        M200Page002Refusal.VALUE_EXCEEDS_DESIGN,
        f"{rule.section}.{field_key}",
        at,
        section=rule.section,
        row=key,
        field=field_key,
        limit=width,
        length=len(value),
    )


def _design_value(field_type: ProfileFieldType, stored: str | None) -> str | None:
    """Spell one stored profile value as the projection row carries it to the design."""
    if stored is None:
        return None
    if field_type is ProfileFieldType.BOOLEAN:
        return _MARKED if stored == _STATED_YES else _UNMARKED
    if field_type in {ProfileFieldType.DECIMAL, ProfileFieldType.MONEY}:
        return format(Decimal(stored), "f")
    if field_type is ProfileFieldType.DATE:
        return date.fromisoformat(stored).strftime("%Y%m%d")
    return stored.strip()


def _require_percentage_total(
    rule: M200Page002FamilyRule,
    rows: tuple[dict[str, str | None], ...],
    *,
    form: str | None,
    rules: M200Page002Rules,
    at: _Coordinates,
) -> None:
    percentage = rule.percentage_total
    if percentage is None:
        return
    total = sum((Decimal(row[percentage.field] or "0") for row in rows), Decimal(0))
    if total == percentage.total:
        return
    if form is None:
        raise _refusal(M200Page002Refusal.DECIDING_FACT_MISSING, rules.entity_form_fact, at, section=rule.section)
    if form in percentage.entity_forms:
        raise _refusal(
            M200Page002Refusal.PERCENTAGE_TOTAL,
            f"{rule.section}.{percentage.field}",
            at,
            section=rule.section,
            entity_form=form,
            percentage_sum=format(total, "f"),
            percentage_total=format(percentage.total, "f"),
        )


def _section_rows(values: Mapping[str, str], section_key: str) -> dict[str, frozenset[str]]:
    return profile_section_rows(section_key, values)


def _first_required_path(section: ProfileSectionDefinition) -> str:
    required = next((field.key for field in section.fields if field.required), section.fields[0].key)
    return f"{section.key}.{required}"


def _refusal(
    reason: M200Page002Refusal,
    profile_path: str,
    at: _Coordinates,
    *,
    section: str,
    **facts: str | int,
) -> ModeloProfileReadinessError:
    return ModeloProfileReadinessError(
        translated_message=_REFUSAL_LOCALE_KEYS[reason],
        context={
            "modelo": at.modelo,
            "filing_year": at.filing_year,
            "period": at.period,
            "as_of": at.as_of.isoformat(),
            "reason": reason.value,
            "profile_section": section,
            "profile_path": profile_path,
            "profile_requirements": profile_path,
            **facts,
        },
        profile_precondition_verdict=profile_facts_verdict((profile_path,), modelo=at.modelo),
        next_step=open_profile_path_step(profile_path),
    )


__all__ = [
    "M200Page002FamilyAnswer",
    "M200Page002FamilyState",
    "M200Page002Refusal",
    "m200_page_002_family_answers",
    "modelo_200_profile_facts",
]
