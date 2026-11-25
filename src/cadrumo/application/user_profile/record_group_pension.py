"""The pension contribution certificates served as record groups, one group per ejercicio.

A certificate has no stored reference to another row, so the relation the grouped
read serves is the year: the group is an ejercicio and each certificate of that
year is a member under it. A year with no certificate is not a group. Each member
carries its stored projection, which holds the keyed issuer and plan references,
the box the pinned edition places it in and the revision its correct and remove
doors submit, and no tax identifier.

Facts read here are private; nothing in this module logs them.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final
from uuid import UUID

from ...core.i18n.render import tr
from ..aggregation.prevision_social_contribution_repository import prevision_social_contribution_record_key
from ..prevision_social_contribution.rows import contribution_rows
from .record_group_contracts import (
    PENSION_CONTRIBUTION_SECTION_KEY,
    ProfileRecordGroupItem,
    ProfileRecordGroupKind,
    ProfileRecordMemberItem,
)
from .record_group_words import group_kind_words, member_kind_words, row_actions

if TYPE_CHECKING:
    from collections.abc import Iterable

    from ...core.external_constants import OutputLanguage
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation
    from ...domain.renta.prevision_social_contribution import PrevisionSocialContributionIdentity
    from ..prevision_social_contribution.ports import PrevisionSocialPortsFactory
    from ..prevision_social_contribution.results import PrevisionSocialRowProjection
    from .record_group_contracts import ProfileRecordGroupStreamItem

GROUP_SUMMARY_LOCALE_KEY: Final = "application.user_profile.record_groups.prevision_social_contribution.group_summary"
PLACED_SUMMARY_LOCALE_KEY: Final = "application.user_profile.record_groups.prevision_social_contribution.summary_placed"
UNPLACED_SUMMARY_LOCALE_KEY: Final = (
    "application.user_profile.record_groups.prevision_social_contribution.summary_unplaced"
)
UNNAMED_HOLDER_LOCALE_KEY: Final = "application.user_profile.record_groups.prevision_social_contribution.holder_unnamed"
EJERCICIO_RELATION_LOCALE_KEY: Final = "application.user_profile.record_groups.relation.prevision_social_contribution"
EJERCICIO_RELATION_TOKEN: Final = f"{PENSION_CONTRIBUTION_SECTION_KEY}.ejercicio"
"""The ``section.field`` token that says a certificate names its year; the year is not a stored reference."""


def _identity(row: PrevisionSocialRowProjection) -> PrevisionSocialContributionIdentity:
    """Return the identity a stored certificate is keyed under."""
    return (row.ejercicio, row.issuer_ref, row.plan_ref, row.clave, row.subclave)


def _holder(row: PrevisionSocialRowProjection) -> str:
    """Name a certificate by its plan, else its issuer, else by the words for an unnamed holder."""
    return row.plan_name or row.issuer_legal_name or tr(UNNAMED_HOLDER_LOCALE_KEY)


def contribution_summary_words(row: PrevisionSocialRowProjection) -> str:
    """Return the sentence that names one certificate, its amount and the box it reaches, or that it reaches none."""
    clave = row.clave.value if row.subclave is None else f"{row.clave.value}/{row.subclave.value}"
    common = {"holder": _holder(row), "amount": row.amount.decimal, "clave": clave}
    if row.casilla_id is None:
        return tr(UNPLACED_SUMMARY_LOCALE_KEY, **common)
    return tr(PLACED_SUMMARY_LOCALE_KEY, box=str(row.casilla_id), **common)


def _member(group_key: str, row: PrevisionSocialRowProjection, language: OutputLanguage) -> ProfileRecordMemberItem:
    row_key = prevision_social_contribution_record_key(_identity(row))
    return ProfileRecordMemberItem(
        group_key=group_key,
        row_ref=f"{PENSION_CONTRIBUTION_SECTION_KEY}.{row_key}",
        parent_ref=group_key,
        section_key=PENSION_CONTRIBUTION_SECTION_KEY,
        row_key=row_key,
        relation=EJERCICIO_RELATION_TOKEN,
        relation_words=tr(EJERCICIO_RELATION_LOCALE_KEY),
        relation_words_language=language,
        summary_words=contribution_summary_words(row),
        summary_words_language=language,
        kind_words=member_kind_words(PENSION_CONTRIBUTION_SECTION_KEY),
        kind_words_language=language,
        actions=row_actions(PENSION_CONTRIBUTION_SECTION_KEY, language),
        contribution=row,
    )


def _group(
    ejercicio: int, rows: tuple[PrevisionSocialRowProjection, ...], language: OutputLanguage
) -> tuple[ProfileRecordGroupStreamItem, ...]:
    group_key = f"{PENSION_CONTRIBUTION_SECTION_KEY}.{ejercicio}"
    head = ProfileRecordGroupItem(
        group_key=group_key,
        payload_kind=ProfileRecordGroupKind.PENSION_CONTRIBUTION,
        section_key=PENSION_CONTRIBUTION_SECTION_KEY,
        row_key=str(ejercicio),
        summary_words=tr(GROUP_SUMMARY_LOCALE_KEY, ejercicio=ejercicio, count=len(rows)),
        summary_words_language=language,
        member_count=len(rows),
        ledger_row_count=0,
        kind_words=group_kind_words(ProfileRecordGroupKind.PENSION_CONTRIBUTION),
        kind_words_language=language,
        actions=(),
    )
    return (head, *(_member(group_key, row, language) for row in rows))


def pension_group_items(
    rows: Iterable[PrevisionSocialRowProjection], *, language: OutputLanguage
) -> tuple[ProfileRecordGroupStreamItem, ...]:
    """Return one group per ejercicio that holds a certificate: its head, then its certificates, oldest year first."""
    by_year: dict[int, list[PrevisionSocialRowProjection]] = {}
    for row in rows:
        by_year.setdefault(row.ejercicio, []).append(row)
    return tuple(
        item for ejercicio in sorted(by_year) for item in _group(ejercicio, tuple(by_year[ejercicio]), language)
    )


def read_pension_group_items(
    profile_id: str,
    *,
    authority_operation: PinnedAuthorityOperation,
    ports_factory: PrevisionSocialPortsFactory,
    language: OutputLanguage,
) -> tuple[ProfileRecordGroupStreamItem, ...]:
    """Read every stored certificate of every supported ejercicio and serve them grouped by year."""
    ports = ports_factory(profile_id=UUID(profile_id), operation=authority_operation)
    return pension_group_items(
        (
            row
            for ejercicio in sorted(authority_operation.supported_filing_years().years)
            for row in contribution_rows(ports, ejercicio, operation=authority_operation)
        ),
        language=language,
    )


__all__ = [
    "EJERCICIO_RELATION_LOCALE_KEY",
    "GROUP_SUMMARY_LOCALE_KEY",
    "PLACED_SUMMARY_LOCALE_KEY",
    "UNNAMED_HOLDER_LOCALE_KEY",
    "UNPLACED_SUMMARY_LOCALE_KEY",
    "contribution_summary_words",
    "pension_group_items",
    "read_pension_group_items",
]
