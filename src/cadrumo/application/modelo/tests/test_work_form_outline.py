"""The form serves a navigation outline and readable part headings, both drawn from the registry layout.

The 2025 Modelo 100 declares its outline and the headings of its technical
parts in reviewed generator input; every other layout falls back to one group
per page. Either way the outline names every section once and rolls up the
attention its boxes ask for. The casillas the layout could not position and the
working figures each stand in a group of their own, and so do the answers no
page takes, so that every tally of the form is the sum of its outline groups'
tallies.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ....core.external_constants import OutputLanguage
from ....core.modelo_work_progress_state import ModeloWorkProgressState
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.schema_form_layouts import (
    FormLayoutDefinition,
    FormOutlineGroup,
    FormOutlineSection,
)
from ....domain.modelos.calculation_revision import CalculationRevisionState
from ..work_form import build_modelo_work_form
from ..work_form_field_vocabulary import (
    ModeloFormOrigin,
    ModeloFormStanding,
    ModeloFormTextDisclosure,
)
from ..work_form_layout import section_applies
from ..work_form_models import (
    ModeloFormCounts,
    ModeloFormField,
    ModeloFormFieldBlock,
    ModeloFormOutlineGroup,
    ModeloFormOutlineKind,
    ModeloWorkForm,
    section_fields,
)
from ..work_review import ModeloWorkProgress, ModeloWorkReview, build_modelo_work_review_casillas
from .work_form_fixture import built_form, form_snapshot

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]


def _fields(form: ModeloWorkForm) -> tuple[ModeloFormField, ...]:
    return tuple(field for page in form.pages for section in page.sections for field in section_fields(section))


def _section_groups(form: ModeloWorkForm) -> tuple[ModeloFormOutlineGroup, ...]:
    return tuple(group for group in form.outline if group.kind is ModeloFormOutlineKind.SECTIONS)


@pytest.mark.parametrize("language", list(OutputLanguage))
def test_the_2025_renta_names_every_page_section_and_group_in_words(
    operation: PinnedAuthorityOperation, language: OutputLanguage
) -> None:
    form = built_form(operation, "100", 2025, "0A", language=language)

    technical = [page.id for page in form.pages if page.heading.disclosure is ModeloFormTextDisclosure.TECHNICAL]
    technical += [
        section.id
        for page in form.pages
        for section in page.sections
        if section.heading.disclosure is ModeloFormTextDisclosure.TECHNICAL
    ]
    technical += [group.id for group in form.outline if group.heading.disclosure is ModeloFormTextDisclosure.TECHNICAL]
    assert technical == []
    assert {group.kind for group in form.outline} == set(ModeloFormOutlineKind)
    assert {group.heading.text for group in form.outline}.isdisjoint({group.id for group in form.outline})


def test_the_2025_headings_do_not_name_another_editions_part_of_the_same_id(
    operation: PinnedAuthorityOperation,
) -> None:
    current = built_form(operation, "100", 2025, "0A")
    earlier = built_form(operation, "100", 2023, "0A")

    def heading(form: ModeloWorkForm, section_id: str) -> tuple[str, ModeloFormTextDisclosure]:
        section = next(
            section for page in form.pages for section in page.sections if section.id.endswith(f".{section_id}")
        )
        return section.heading.text, section.heading.disclosure

    assert heading(current, "calculoimpuestores-4")[1] is ModeloFormTextDisclosure.LOCALIZED
    assert heading(earlier, "calculoimpuestores-4")[1] is ModeloFormTextDisclosure.LOCALIZED
    assert heading(earlier, "calculoimpuestores-4")[0] != heading(current, "calculoimpuestores-4")[0]
    assert heading(earlier, "calculoimpuestores-4") == heading(current, "calculoimpuestores-5")
    assert [group.id for group in _section_groups(earlier)] == [page.id for page in earlier.pages if page.sections]


@pytest.mark.parametrize(("modelo", "year", "code"), [("100", 2025, "0A"), ("303", 2026, "1T"), ("130", 2025, "1T")])
def test_the_outline_names_every_section_once_and_counts_what_it_holds(
    operation: PinnedAuthorityOperation, modelo: str, year: int, code: str
) -> None:
    form = built_form(operation, modelo, year, code)
    sections = {section.id: section for page in form.pages for section in page.sections}

    named = [section_id for group in form.outline for section_id in group.section_ids]
    assert sorted(named) == sorted(sections)
    assert len(named) == len(set(named))
    for group in _section_groups(form):
        members = [field for section_id in group.section_ids for field in section_fields(sections[section_id])]
        assert group.counts.total == len(members)
        assert group.counts.needs_you == sum(1 for field in members if field.standing is ModeloFormStanding.NEEDS_YOU)
        assert group.counts.could_not_calculate == sum(
            1 for field in members if field.origin is ModeloFormOrigin.CALCULATION_FAILED
        )
    assert sum(group.counts.total for group in form.outline) == len(form.fields())


def test_a_layout_without_an_outline_groups_its_sections_by_page(operation: PinnedAuthorityOperation) -> None:
    form = built_form(operation, "303", 2026, "1T")

    assert _layout(operation, "303", form.registry_revision_id).outline == ()
    assert [(group.id, group.heading) for group in _section_groups(form)] == [
        (page.id, page.heading) for page in form.pages if page.sections
    ]


def test_the_renta_outline_follows_the_declared_groups(operation: PinnedAuthorityOperation) -> None:
    form = built_form(operation, "100", 2025, "0A")
    declared = _layout(operation, "100", form.registry_revision_id).outline

    groups = _section_groups(form)
    assert [group.id for group in groups] == [group.id for group in declared]
    assert groups[-1].id == "result"
    result = next(group for group in groups if group.id == "result")
    assert "datoseconomicos-resultados.ingresodevolucionres" in result.section_ids


def _calculated_renta(
    operation: PinnedAuthorityOperation, lifecycle: CalculationRevisionState | None
) -> ModeloWorkForm:
    """The 2025 Renta after a calculation that left every computed box empty, so each one could not be worked out."""
    snapshot = form_snapshot(operation, "100", 2025, "0A")
    rows = build_modelo_work_review_casillas(snapshot=snapshot, revision=None, operation=operation)
    review = ModeloWorkReview(
        bucket_id="13000000-0000-4000-8000-000000000100",
        modelo="100",
        filing_year=2025,
        period=Period.from_year_and_code(2025, "0A"),
        registry_revision_id=snapshot.revision.id,
        work_unit_id="e" * 64,
        calculation_revision_id="f" * 64,
        lifecycle_state=lifecycle,
        verification_outcome=None,
        progress=ModeloWorkProgress(state=ModeloWorkProgressState.UNDEFINED),
        casillas=rows,
        findings=(),
        blockers=(),
    )
    return build_modelo_work_form(
        review=review,
        snapshot=snapshot,
        layout=operation.form_layout("100", snapshot.revision.id),
        revision=None,
        permitted_surface=None,
        entered_casilla_ids=frozenset(),
        overridden_binding_ids=frozenset(),
        language=OutputLanguage.EN,
    )


def test_boxes_the_calculation_could_not_work_out_need_the_filer_until_the_declaration_is_filed(
    operation: PinnedAuthorityOperation,
) -> None:
    draft = _calculated_renta(operation, None)
    filed = _calculated_renta(operation, CalculationRevisionState.PRESENTADO)
    failed = [field for field in _fields(draft) if field.origin is ModeloFormOrigin.CALCULATION_FAILED]

    assert failed
    assert draft.counts.could_not_calculate == sum(
        1 for field in draft.fields() if field.origin is ModeloFormOrigin.CALCULATION_FAILED
    )
    assert draft.counts.needs_you == sum(
        1 for field in draft.fields() if field.standing is ModeloFormStanding.NEEDS_YOU
    )
    assert sum(group.counts.could_not_calculate for group in _section_groups(draft)) == len(failed)
    assert any(group.counts.could_not_calculate for group in draft.outline)
    assert filed.counts.needs_you == 0
    assert all(group.counts.needs_you == 0 for group in filed.outline)
    assert filed.counts.could_not_calculate == draft.counts.could_not_calculate


def test_a_section_applies_as_its_page_does_unless_every_box_is_proven_not_to(
    operation: PinnedAuthorityOperation,
) -> None:
    form = built_form(operation, "303", 2026, "1T")
    pages = {page.id: page for page in form.pages}
    section = next(
        section
        for page in form.pages
        for section in page.sections
        if section.blocks and all(isinstance(block, ModeloFormFieldBlock) for block in section.blocks)
    )
    proven_not_to = section.model_copy(
        update={
            "blocks": tuple(
                block.model_copy(
                    update={"field": block.field.model_copy(update={"origin": ModeloFormOrigin.NOT_APPLICABLE})}
                )
                for block in section.blocks
                if isinstance(block, ModeloFormFieldBlock)
            )
        }
    )

    assert section_applies(section, page_applies=True) is True
    assert section_applies(section, page_applies=None) is None
    assert section_applies(section, page_applies=False) is False
    assert section_applies(proven_not_to, page_applies=True) is False
    not_applying = [page for page in form.pages if page.applies is False and page.sections]
    assert not_applying, "the first-quarter Modelo 303 has no page that does not apply"
    assert all(section.applies is False for page in not_applying for section in page.sections)
    for group in _section_groups(form):
        assert group.applies is pages[group.id].applies
    assert all(group.applies is True for group in form.outline if group.kind is not ModeloFormOutlineKind.SECTIONS)


def _layout(operation: PinnedAuthorityOperation, modelo: str, revision_id: str) -> FormLayoutDefinition:
    layout = operation.form_layout(modelo, revision_id)
    assert layout is not None
    return layout


def _with_outline(layout: FormLayoutDefinition, outline: tuple[FormOutlineGroup, ...]) -> FormLayoutDefinition:
    groups = tuple(group.model_dump(mode="python") for group in outline)
    return FormLayoutDefinition.model_validate({**layout.model_dump(mode="python"), "outline": groups})


def test_the_layout_refuses_an_outline_that_hides_repeats_or_invents_a_section(
    operation: PinnedAuthorityOperation,
) -> None:
    layout = _layout(operation, "100", "2025")
    groups = layout.outline
    assert _with_outline(layout, groups).outline == groups

    first, last = groups[0], groups[-1]
    nowhere = FormOutlineSection.model_validate({"page_id": "nowhere", "section_id": "nothing"})
    refused = (
        (*groups[:-1], last.model_copy(update={"sections": last.sections[:-1]})),
        (*groups[:-1], last.model_copy(update={"sections": (*last.sections, first.sections[0])})),
        (*groups, last.model_copy(update={"id": "nowhere", "sections": (nowhere,)})),
        (*groups, first),
    )
    for outline in refused:
        with pytest.raises(ValidationError):
            _with_outline(layout, outline)


_PARITY_CONTEXTS = (
    ("100", 2025, "0A"),
    ("100", 2024, "0A"),
    ("130", 2025, "1T"),
    ("131", 2025, "1T"),
    ("182", 2025, "0A"),
    ("184", 2025, "0A"),
    ("303", 2026, "1T"),
    ("303", 2025, "1T"),
    ("390", 2025, "0A"),
)


def _tallies(counts: ModeloFormCounts) -> dict[str, int]:
    return {name: getattr(counts, name) for name in ModeloFormCounts.model_fields}


@pytest.mark.parametrize(("modelo", "year", "code"), _PARITY_CONTEXTS)
@pytest.mark.parametrize("state", ["uncalculated", "calculated", "filed"])
def test_every_tally_of_the_form_is_the_sum_of_its_outline_groups(
    operation: PinnedAuthorityOperation, modelo: str, year: int, code: str, state: str
) -> None:
    """A navigator drawn from the outline reaches each box any tally counts, and none it does not."""
    form = built_form(
        operation,
        modelo,
        year,
        code,
        calculated=state != "uncalculated",
        lifecycle=CalculationRevisionState.PRESENTADO if state == "filed" else None,
    )

    summed = {name: sum(_tallies(group.counts)[name] for group in form.outline) for name in _tallies(form.counts)}
    assert _tallies(form.counts) == summed
    kept_apart = {group.kind: group for group in form.outline if group.kind is not ModeloFormOutlineKind.SECTIONS}
    assert set(kept_apart) == {
        kind
        for kind, listed in (
            (ModeloFormOutlineKind.WORKING_FIGURES, form.working_figures),
            (ModeloFormOutlineKind.UNPLACED, form.unplaced),
            (ModeloFormOutlineKind.ANSWERS, form.answers),
        )
        if listed
    }
    if form.working_figures:
        assert kept_apart[ModeloFormOutlineKind.WORKING_FIGURES].counts.total == len(form.working_figures)
    if form.unplaced:
        assert kept_apart[ModeloFormOutlineKind.UNPLACED].counts.total == len(form.unplaced)
    if form.answers:
        assert kept_apart[ModeloFormOutlineKind.ANSWERS].counts.total == len(form.answers)


def test_a_failed_working_figure_is_counted_and_reached_through_the_working_figures_group(
    operation: PinnedAuthorityOperation,
) -> None:
    """Figures no placed box reads still count as could-not-calculate, in a group the navigator can open."""
    form = built_form(operation, "100", 2025, "0A", calculated=True)
    failed = [field for field in form.working_figures if field.origin is ModeloFormOrigin.CALCULATION_FAILED]
    group = next(group for group in form.outline if group.kind is ModeloFormOutlineKind.WORKING_FIGURES)

    assert len(failed) == 6
    assert group.counts.could_not_calculate == len(failed)
    assert group.counts.needs_you == len(failed)
    assert group.section_ids == ()
    assert form.counts.could_not_calculate == sum(item.counts.could_not_calculate for item in form.outline)


def test_unplaced_casillas_that_ask_for_a_value_are_reached_through_the_unplaced_group(
    operation: PinnedAuthorityOperation,
) -> None:
    form = built_form(operation, "182", 2025, "0A")
    group = next(group for group in form.outline if group.kind is ModeloFormOutlineKind.UNPLACED)

    asked = sum(1 for item in form.unplaced if item.field.origin is ModeloFormOrigin.NEEDS_INPUT)
    assert asked >= 1
    assert group.counts.needs_input == asked
    assert form.counts.needs_input == asked + sum(item.counts.needs_input for item in _section_groups(form))


def test_a_group_of_a_list_kept_apart_names_no_section_and_the_form_holds_one_only_for_a_non_empty_list(
    operation: PinnedAuthorityOperation,
) -> None:
    form = built_form(operation, "182", 2025, "0A")
    group = next(group for group in form.outline if group.kind is ModeloFormOutlineKind.UNPLACED)

    with pytest.raises(ValidationError):
        ModeloFormOutlineGroup.model_validate({**group.model_dump(), "section_ids": ["page.section"]})
    with pytest.raises(ValidationError):
        ModeloWorkForm.model_validate({**form.model_dump(), "unplaced": []})
    with pytest.raises(ValidationError):
        ModeloWorkForm.model_validate(
            {**form.model_dump(), "outline": [item.model_dump() for item in _section_groups(form)]}
        )
