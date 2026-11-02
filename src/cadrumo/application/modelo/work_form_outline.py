"""Serve a form's navigation outline: its sections in groups, with what each group asks of the filer.

The outline is the layout's declared one where the revision declares it, and
otherwise one group per page, headed as the page is. Either way every section of
the form's pages stands in exactly one group, so a navigator drawn from it can
neither hide nor repeat a part of the form, and it counts nothing itself: each
group carries its boxes' counts and whether any of its sections applies.
"""

from __future__ import annotations

from collections.abc import Iterable

from ...core.external_constants import OutputLanguage
from ...domain.calculations.registry.schema_form_layouts import FormOutlineGroup
from .work_form_counts import count_work_form_fields
from .work_form_localization import localized_heading
from .work_form_models import (
    ModeloFormOutlineGroup,
    ModeloFormPage,
    ModeloFormSection,
    ModeloFormText,
    section_fields,
)


def form_outline(
    declared: tuple[FormOutlineGroup, ...],
    pages: tuple[ModeloFormPage, ...],
    language: OutputLanguage,
    *,
    filed: bool,
) -> tuple[ModeloFormOutlineGroup, ...]:
    """Group ``pages``' sections by the ``declared`` outline, or by page when the layout declares none."""
    sections = {section.id: section for page in pages for section in page.sections}
    if not declared:
        return tuple(_group(page.id, page.heading, page.sections, filed=filed) for page in pages if page.sections)
    return tuple(
        _group(
            group.id,
            localized_heading(group.heading_key, group.official_heading, group.id, language),
            tuple(sections[f"{item.page_id}.{item.section_id}"] for item in group.sections),
            filed=filed,
        )
        for group in declared
    )


def _group(
    group_id: str, heading: ModeloFormText, members: tuple[ModeloFormSection, ...], *, filed: bool
) -> ModeloFormOutlineGroup:
    return ModeloFormOutlineGroup(
        id=group_id,
        heading=heading,
        section_ids=tuple(section.id for section in members),
        counts=count_work_form_fields((field for section in members for field in section_fields(section)), filed=filed),
        applies=_any_applies(section.applies for section in members),
    )


def _any_applies(answers: Iterable[bool | None]) -> bool | None:
    """``True`` when any section applies, ``False`` when none does, ``None`` when none is known to."""
    seen = tuple(answers)
    if any(answer is True for answer in seen):
        return True
    if all(answer is False for answer in seen):
        return False
    return None


__all__ = ["form_outline"]
