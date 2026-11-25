"""Typed projection of the Modelo 200 page 002 profile rules.

The registry names, per projection kind of the page 002 and 002 bis records, the
profile section holding its rows, the profile fact on which the entity states it has
none, and the rules keyed by legal entity form and by IRNR residence that decide which
families a return must carry. The design keeps the fields and the slot counts; this
projection carries only what the registry says about who must fill them.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Final

from .entity_type import resolve_entity_vocabulary
from .errors import RegistryValidationError
from .facts.resolution import optional_unique_mapping_tokens, required_mapping_entry, unique_mapping_tokens
from .facts.string_mapping import MappingValueWhitespace, StringMappingFact, StringMappingPolicy
from .governed_fact_scope import GovernedFactSource
from .schema_base import DateAxis

_FACT_ID: Final = "m200-page-002-profile-rules"
_SUBJECT: Final = "Modelo 200 page 002 profile rules"
_KIND_PREFIX: Final = "kind."

_ENTRIES_FACT = StringMappingFact(
    fact_id=_FACT_ID,
    date_axis=DateAxis.FILING_PERIOD,
    policy=StringMappingPolicy(subject=_SUBJECT, value_whitespace=MappingValueWhitespace.STRIP),
)


@dataclass(frozen=True, slots=True)
class M200Page002PercentageTotal:
    """The total the rows' percentages must reach for the named entity forms."""

    field: str
    total: Decimal
    entity_forms: frozenset[str]


@dataclass(frozen=True, slots=True)
class M200Page002FamilyRule:
    """What the registry requires of one page 002 projection kind.

    ``stated_answer`` is the ``section.field`` path on which the entity states whether
    it has rows of the family; a family without one (the administradores) can never be
    stated empty. ``non_resident_only_fields`` are filled only when the declarant is an
    IRNR contribuyente and are left blank otherwise.
    """

    projection_kind: str
    section: str
    stated_answer: str | None
    rows_required_forms: frozenset[str]
    not_applicable_forms: frozenset[str]
    non_resident_only_fields: tuple[str, ...]
    percentage_total: M200Page002PercentageTotal | None


@dataclass(frozen=True, slots=True)
class M200Page002Rules:
    """The page 002 families the profile supplies and the facts that decide them."""

    families: tuple[M200Page002FamilyRule, ...]
    entity_form_fact: str
    non_resident_fact: str
    non_resident_value: str

    def family(self, projection_kind: str) -> M200Page002FamilyRule:
        """Return the rule of one projection kind, refusing a kind the registry does not name."""
        for rule in self.families:
            if rule.projection_kind == projection_kind:
                return rule
        raise RegistryValidationError(f"{_SUBJECT} name no projection kind {projection_kind!r}")


def resolve_m200_page_002_rules(authority: GovernedFactSource, *, effective_date: date) -> M200Page002Rules:
    """Resolve the page 002 profile rules in force on ``effective_date``.

    Raises:
        RegistryValidationError: When the fact is missing, malformed or names one
            projection kind twice.
    """
    entries = _ENTRIES_FACT.resolve_entries(authority, effective_date=effective_date)
    kinds = unique_mapping_tokens(entries, "kinds", subject=_SUBJECT)
    families = tuple(_family_rule(entries, kind) for kind in kinds)
    vocabulary = resolve_entity_vocabulary(effective_date=effective_date, authority=authority)
    for family in families:
        named = family.rows_required_forms | family.not_applicable_forms
        if family.percentage_total is not None:
            named |= family.percentage_total.entity_forms
        for form in sorted(named):
            vocabulary.require_legal_entity_form(form)
    return M200Page002Rules(
        families=families,
        entity_form_fact=required_mapping_entry(entries, "entity_form_fact", subject=_SUBJECT),
        non_resident_fact=required_mapping_entry(entries, "non_resident_fact", subject=_SUBJECT),
        non_resident_value=required_mapping_entry(entries, "non_resident_value", subject=_SUBJECT),
    )


def _family_rule(entries: Mapping[str, str], kind: str) -> M200Page002FamilyRule:
    prefix = f"{_KIND_PREFIX}{kind}."
    stated_answer = entries.get(f"{prefix}stated_answer", "").strip() or None
    return M200Page002FamilyRule(
        projection_kind=kind,
        section=required_mapping_entry(entries, f"{prefix}section", subject=_SUBJECT),
        stated_answer=stated_answer,
        rows_required_forms=_forms(entries, f"{prefix}rows_required_forms"),
        not_applicable_forms=_forms(entries, f"{prefix}not_applicable_forms"),
        non_resident_only_fields=optional_unique_mapping_tokens(
            entries, f"{prefix}non_resident_only_fields", subject=_SUBJECT
        ),
        percentage_total=_percentage_total(entries, prefix),
    )


def _forms(entries: Mapping[str, str], key: str) -> frozenset[str]:
    return frozenset(optional_unique_mapping_tokens(entries, key, subject=_SUBJECT))


def _percentage_total(entries: Mapping[str, str], prefix: str) -> M200Page002PercentageTotal | None:
    field = entries.get(f"{prefix}percentage_field", "").strip()
    if not field:
        return None
    raw_total = required_mapping_entry(entries, f"{prefix}percentage_total", subject=_SUBJECT)
    try:
        total = Decimal(raw_total)
    except InvalidOperation as exc:
        raise RegistryValidationError(f"{_SUBJECT} {prefix}percentage_total must be a decimal") from exc
    forms = _forms(entries, f"{prefix}percentage_total_forms")
    if not forms:
        raise RegistryValidationError(f"{_SUBJECT} {prefix}percentage_total names no entity form")
    return M200Page002PercentageTotal(field=field, total=total, entity_forms=forms)


__all__ = [
    "M200Page002FamilyRule",
    "M200Page002PercentageTotal",
    "M200Page002Rules",
    "resolve_m200_page_002_rules",
]
