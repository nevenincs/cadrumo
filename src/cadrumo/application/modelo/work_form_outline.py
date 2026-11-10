"""Serve a form's navigation outline: its sections in groups, with what each group asks of the filer.

The outline is the layout's declared one where the revision declares it, and
otherwise one group per page, headed as the page is. Either way every section of
the form's pages stands in exactly one group. The lists the form keeps apart
from its pages, the casillas the layout could not position, the working
figures and the answers no page takes, each stand in a group of their own when
they are not empty. A
navigator drawn from the outline can therefore neither hide nor repeat a part
of the form, and the form's counts are the sum of the groups' counts: the outline
reaches every box any tally counts, and the outline counts nothing else.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Final

from ...core.external_constants import OutputLanguage
from ...domain.calculations.registry.schema_form_layouts import FormOutlineGroup
from .work_form_counts import count_work_form_fields
from .work_form_field_vocabulary import ModeloFormText
from .work_form_localization import localized_heading
from .work_form_models import (
    ModeloFormField,
    ModeloFormOutlineGroup,
    ModeloFormOutlineKind,
    ModeloFormPage,
    ModeloFormSection,
    ModeloFormUnplacedField,
    section_fields,
)

#: The headings of the lists kept apart from the pages, which the form's window also names its pages by.
_UNPLACED_HEADING_LOCALE_KEY: Final[str] = "workspace.modelo.page.unplaced"
_WORKING_FIGURES_HEADING_LOCALE_KEY: Final[str] = "workspace.modelo.page.calculation_details"
_ANSWERS_HEADING_LOCALE_KEY: Final[str] = "workspace.modelo.page.answers"


def form_outline(
    declared: tuple[FormOutlineGroup, ...],
    pages: tuple[ModeloFormPage, ...],
    language: OutputLanguage,
    *,
    filed: bool,
    unplaced: tuple[ModeloFormUnplacedField, ...] = (),
    working_figures: tuple[ModeloFormField, ...] = (),
    answers: tuple[ModeloFormField, ...] = (),
) -> tuple[ModeloFormOutlineGroup, ...]:
    """Group ``pages``' sections by the ``declared`` outline, or by page when the layout declares none.

    The ``unplaced`` casillas, the ``working_figures`` and the ``answers`` follow
    as a group each, in the order the form draws them, when they are not empty.
    """
    grouped = (
        _declared_groups(declared, pages, language, filed=filed)
        if declared
        else tuple(_group(page.id, page.heading, page.sections, filed=filed) for page in pages if page.sections)
    )
    return grouped + _kept_apart_groups(unplaced, working_figures, answers, language, filed=filed)


def _declared_groups(
    declared: tuple[FormOutlineGroup, ...], pages: tuple[ModeloFormPage, ...], language: OutputLanguage, *, filed: bool
) -> tuple[ModeloFormOutlineGroup, ...]:
    sections = {section.id: section for page in pages for section in page.sections}
    return tuple(
        _group(
            group.id,
            localized_heading(group.heading_key, group.official_heading, group.id, language),
            tuple(sections[f"{item.page_id}.{item.section_id}"] for item in group.sections),
            filed=filed,
        )
        for group in declared
    )


def _kept_apart_groups(
    unplaced: tuple[ModeloFormUnplacedField, ...],
    working_figures: tuple[ModeloFormField, ...],
    answers: tuple[ModeloFormField, ...],
    language: OutputLanguage,
    *,
    filed: bool,
) -> tuple[ModeloFormOutlineGroup, ...]:
    kept_apart = (
        (ModeloFormOutlineKind.UNPLACED, _UNPLACED_HEADING_LOCALE_KEY, tuple(item.field for item in unplaced)),
        (ModeloFormOutlineKind.WORKING_FIGURES, _WORKING_FIGURES_HEADING_LOCALE_KEY, working_figures),
        (ModeloFormOutlineKind.ANSWERS, _ANSWERS_HEADING_LOCALE_KEY, answers),
    )
    return tuple(
        ModeloFormOutlineGroup(
            id=kind.value,
            heading=localized_heading(key, None, kind.value, language),
            kind=kind,
            section_ids=(),
            counts=count_work_form_fields(fields, filed=filed),
            applies=True,
        )
        for kind, key, fields in kept_apart
        if fields
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
