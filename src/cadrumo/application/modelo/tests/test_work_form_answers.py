"""Every answer the edit surface admits is a field of the form, once, with words of its own.

The admission admits an override for every binding whose source an operator may
replace. Each one the calculation reads for the period is taken by a field: a
box or binding input of the layout, a repeating group's rows, or the form's own
answers, a list kept apart from the pages with an outline group of its own.
Every revision a filer can open is checked, so a binding override no field
takes cannot hide in a revision this test does not name.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ....core.external_constants import OutputLanguage
from ....core.i18n.render import lookup_translation
from ....core.period import Period, accepted_filing_period_codes
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.errors import EjercicioOrdenNotYetPublishedError, NoRevisionForPeriodError
from ....domain.calculations.registry.modelo_localization import binding_locale_key, resolve_modelo_localization
from ....domain.calculations.registry.schema import RegistrySnapshot
from ....domain.calculations.registry.schema_form_layouts import (
    FormBindingInputsBlock,
    FormLayoutDefinition,
    FormRepeatingGroupBlock,
)
from ....domain.modelos.calculation_revision import CalculationRevisionState
from ....domain.modelos.codes import ModeloCode
from ..edit_admission import permitted_binding_entry
from ..edit_models import ModeloEditWritableBindingOverrideSurfaceEntryV1
from ..row_filled_bindings import row_filled_binding_ids
from ..work_form import build_modelo_work_form
from ..work_form_field_vocabulary import (
    ModeloFormBindingAddressV1,
    ModeloFormEditability,
    ModeloFormOrigin,
    ModeloFormStanding,
    ModeloFormTextDisclosure,
)
from ..work_form_models import (
    ModeloFormField,
    ModeloFormOutlineKind,
    ModeloWorkForm,
)
from ..work_form_service import modelo_form_snapshot
from .work_form_fixture import built_form, uncalculated_review

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

#: The first quarter's answers about earlier filings that no box of its layout takes.
_PREVIOUS_YEAR_INCOME = "irpf.previous_year_economic_activity_net_income"
_EARLIER_NEGATIVE_RESULTS = "modelo-130-resultados-negativos-anteriores"
#: The earlier quarters' payments, which box 05 takes as its own carried value.
_EARLIER_PAYMENTS = "modelo-130-pagos-fraccionados-anteriores"


def _reachable(operation: PinnedAuthorityOperation) -> dict[tuple[str, str], tuple[int, str]]:
    contexts: dict[tuple[str, str], tuple[int, str]] = {}
    for modelo in operation.modelo_ids():
        for year in operation.supported_filing_years().years:
            for code in accepted_filing_period_codes():
                try:
                    revision = operation.revision_for_context(modelo, filing_year=year, period=code)
                except (NoRevisionForPeriodError, EjercicioOrdenNotYetPublishedError):
                    continue
                contexts.setdefault((modelo, str(revision.id)), (year, code))
    return contexts


def _form(
    operation: PinnedAuthorityOperation,
    modelo: str,
    year: int,
    code: str,
    language: OutputLanguage = OutputLanguage.EN,
    *,
    layout: FormLayoutDefinition | None = None,
) -> tuple[ModeloWorkForm, RegistrySnapshot]:
    period = Period.from_year_and_code(year, code)
    revision_id = str(operation.revision_for_context(modelo, filing_year=year, period=code).id)
    snapshot = modelo_form_snapshot(operation, ModeloCode(modelo), year, period, revision_id)
    review = uncalculated_review(snapshot, operation, modelo=modelo, filing_year=year, period=period)
    form = build_modelo_work_form(
        review=review,
        snapshot=snapshot,
        layout=layout if layout is not None else operation.form_layout(modelo, snapshot.revision.id),
        revision=None,
        permitted_surface=None,
        entered_casilla_ids=frozenset(),
        overridden_binding_ids=frozenset(),
        language=language,
    )
    return form, snapshot


def _admitted_overrides(snapshot: RegistrySnapshot, code: str, layout: FormLayoutDefinition | None) -> set[str]:
    """The bindings the admission lets an operator override for ``code`` on a form laid out as ``layout``."""
    revision = snapshot.revision
    row_filled = row_filled_binding_ids(revision, layout)
    return {
        str(binding.id)
        for binding in revision.bindings
        if isinstance(
            permitted_binding_entry(binding, revision=revision, period=code, row_filled=row_filled),
            ModeloEditWritableBindingOverrideSurfaceEntryV1,
        )
    }


def _row_bindings(layout: FormLayoutDefinition, snapshot: RegistrySnapshot) -> set[str]:
    """The bindings a repeating group of ``layout`` opens row by row, read from the layout and its export records."""
    groups = [
        block
        for page in layout.pages
        for section in page.sections
        for block in section.blocks
        if isinstance(block, FormRepeatingGroupBlock)
    ]
    found = {str(group.binding_id) for group in groups if group.binding_id is not None}
    found |= {str(column.binding_id) for group in groups for column in group.columns if column.binding_id is not None}
    found |= {
        str(cell.binding_id)
        for group in groups
        for grid in group.grids
        for row in grid.rows
        for cell in row.cells
        if cell.binding_id is not None
    }
    records = {group.export_record_id for group in groups}
    found |= {
        str(field.binding)
        for export_layout in snapshot.revision.export_layouts
        for record in export_layout.records
        if record.id in records
        for field in record.fields
        if field.binding is not None
    }
    return found


def _takers(form: ModeloWorkForm, binding_id: str) -> list[ModeloFormField]:
    address = ModeloFormBindingAddressV1(binding_id=binding_id)
    return [
        field
        for field in form.fields()
        if address in (field.address, field.edit_address)
        or (field.bindings and str(field.bindings[0].binding_id) == binding_id)
    ]


def _answer(form: ModeloWorkForm, binding_id: str) -> ModeloFormField:
    return next(field for field in form.answers if field.address == ModeloFormBindingAddressV1(binding_id=binding_id))


def test_every_admitted_override_of_every_revision_is_taken_by_a_field(operation: PinnedAuthorityOperation) -> None:
    contexts = _reachable(operation)
    assert contexts, "the support envelope reaches no revision, so this proves nothing"

    untaken: list[str] = []
    answered = 0
    for (modelo, revision_id), (year, code) in sorted(contexts.items()):
        layout = operation.form_layout(modelo, revision_id)
        if layout is None:
            continue
        form, snapshot = _form(operation, modelo, year, code)
        rows = _row_bindings(layout, snapshot)
        admitted = _admitted_overrides(snapshot, code, layout)
        # A column of repeated lines has no single override to give, however the registry spells its source.
        assert not admitted & rows, f"{modelo}/{revision_id}: {sorted(admitted & rows)}"
        for binding_id in sorted(admitted):
            if not _takers(form, binding_id):
                untaken.append(f"{modelo}/{revision_id}: {binding_id}")
        answered += len(form.answers)
        # An answer is one the admission lets the filer give for this period.
        assert {
            str(field.address.binding_id)
            for field in form.answers
            if isinstance(field.address, ModeloFormBindingAddressV1)
        } <= admitted, f"{modelo}/{revision_id}"
    assert not untaken, "\n".join(untaken)
    assert answered, "no revision needed an answer of its own, so the answers were never exercised"


@pytest.mark.parametrize("language", list(OutputLanguage))
def test_every_answer_of_every_revision_is_named_in_words(
    operation: PinnedAuthorityOperation, language: OutputLanguage
) -> None:
    unnamed: list[str] = []
    for (modelo, revision_id), (year, code) in sorted(_reachable(operation).items()):
        period = Period.from_year_and_code(year, code)
        snapshot = modelo_form_snapshot(operation, ModeloCode(modelo), year, period, revision_id)
        # A revision that admits no override for the period can serve no answer, so its form is not built.
        layout = operation.form_layout(modelo, revision_id)
        if layout is None or not _admitted_overrides(snapshot, code, layout):
            continue
        form, _snapshot = _form(operation, modelo, year, code, language)
        unnamed.extend(
            f"{modelo}/{revision_id}: {field.address} {field.label.text!r}"
            for field in form.answers
            if field.label.disclosure is not ModeloFormTextDisclosure.LOCALIZED
            or not isinstance(field.address, ModeloFormBindingAddressV1)
            # Named by its own words, not only as additional data for the box it feeds.
            or resolve_modelo_localization(
                (binding_locale_key(modelo, str(field.address.binding_id), "label"),), locale=language.value
            )
            != field.label.text
        )
    assert not unnamed, "\n".join(unnamed)


@pytest.mark.parametrize("language", list(OutputLanguage))
def test_the_first_quarter_serves_its_earlier_filing_answers_with_their_words(
    operation: PinnedAuthorityOperation, language: OutputLanguage
) -> None:
    form, _snapshot = _form(operation, "130", 2025, "1T", language)

    assert [
        str(field.address.binding_id) for field in form.answers if isinstance(field.address, ModeloFormBindingAddressV1)
    ] == [
        _EARLIER_NEGATIVE_RESULTS,
        _PREVIOUS_YEAR_INCOME,
    ]
    income = _answer(form, _PREVIOUS_YEAR_INCOME)
    assert income.data_type == "money"
    assert income.edit_address == income.address
    assert income.value is None and income.origin is not ModeloFormOrigin.CALCULATED
    assert income.help is not None and "13" in income.help and income.help not in income.label.text
    # Words of their own, not the fallback naming only the box they feed.
    for field in form.answers:
        assert isinstance(field.address, ModeloFormBindingAddressV1)
        own = binding_locale_key("130", str(field.address.binding_id), "label")
        assert field.label.text == lookup_translation(own, locale=language.value)
    # The earlier quarters' payments are box 05's own carried value, so box 05 takes them and no answer repeats it.
    assert len(_takers(form, _EARLIER_PAYMENTS)) == 1
    assert _takers(form, _EARLIER_PAYMENTS)[0].box == "05"


def test_the_answers_group_counts_what_the_answers_ask_and_the_outline_still_sums_to_the_form(
    operation: PinnedAuthorityOperation,
) -> None:
    form, _snapshot = _form(operation, "130", 2025, "1T")

    groups = [group for group in form.outline if group.kind is ModeloFormOutlineKind.ANSWERS]
    assert len(groups) == 1
    (group,) = groups
    assert group.section_ids == () and group.applies is True
    assert group.heading.disclosure is ModeloFormTextDisclosure.LOCALIZED and group.heading.text != group.id
    assert group.counts.total == len(form.answers) == 2
    assert group.counts.needs_you == sum(1 for field in form.answers if field.standing is ModeloFormStanding.NEEDS_YOU)
    for tally in ("total", "needs_you", "could_not_calculate", "blocked"):
        assert getattr(form.counts, tally) == sum(getattr(each.counts, tally) for each in form.outline), tally
    assert form.fields()[-len(form.answers) :] == form.answers


def test_a_form_without_an_untaken_override_has_no_answers_group(operation: PinnedAuthorityOperation) -> None:
    form, _snapshot = _form(operation, "303", 2026, "1T")

    assert form.answers == ()
    assert all(group.kind is not ModeloFormOutlineKind.ANSWERS for group in form.outline)


def test_an_override_the_layout_already_places_is_not_answered_again(operation: PinnedAuthorityOperation) -> None:
    revision_id = str(operation.revision_for_context("130", filing_year=2025, period="1T").id)
    layout = operation.form_layout("130", revision_id)
    assert layout is not None
    first_page = layout.pages[0]
    first_section = first_page.sections[0]
    placed = first_section.model_copy(
        update={
            "blocks": (
                *first_section.blocks,
                FormBindingInputsBlock(id="earlier-year-income", binding_ids=(_PREVIOUS_YEAR_INCOME,)),
            )
        }
    )
    moved = layout.model_copy(
        update={
            "pages": (
                first_page.model_copy(update={"sections": (placed, *first_page.sections[1:])}),
                *layout.pages[1:],
            )
        }
    )

    form, _snapshot = _form(operation, "130", 2025, "1T", layout=moved)

    assert [field.address for field in form.answers] == [
        ModeloFormBindingAddressV1(binding_id=_EARLIER_NEGATIVE_RESULTS)
    ]
    takers = _takers(form, _PREVIOUS_YEAR_INCOME)
    assert len(takers) == 1 and takers[0] not in form.answers


def test_a_filed_quarter_still_shows_its_answers_but_offers_none_for_editing(
    operation: PinnedAuthorityOperation,
) -> None:
    form = built_form(operation, "130", 2025, "1T", lifecycle=CalculationRevisionState.PRESENTADO, held={"19": "0.00"})

    assert {field.address for field in form.answers} == {
        ModeloFormBindingAddressV1(binding_id=_PREVIOUS_YEAR_INCOME),
        ModeloFormBindingAddressV1(binding_id=_EARLIER_NEGATIVE_RESULTS),
    }
    assert all(field.editability is ModeloFormEditability.NO_ADMISSION for field in form.answers)
    assert all(field.standing is not ModeloFormStanding.NEEDS_YOU for field in form.answers)


@pytest.mark.parametrize("repeat", ["an_answer", "a_box"])
def test_an_answer_the_form_takes_elsewhere_is_refused(operation: PinnedAuthorityOperation, repeat: str) -> None:
    form, _snapshot = _form(operation, "130", 2025, "1T")
    repeated = form.answers[0] if repeat == "an_answer" else next(field for field in form.fields() if field.box == "05")

    with pytest.raises(ValidationError, match="no other field of the form takes"):
        form.model_validate({**dict(form), "answers": (*form.answers, repeated)})


def test_an_empty_answer_whose_box_could_not_be_worked_out_needs_the_filer(operation: PinnedAuthorityOperation) -> None:
    before = built_form(operation, "130", 2025, "1T")
    after = built_form(operation, "130", 2025, "1T", calculated=True)

    # Before any calculation nothing says the boxes they feed failed, so the answers read optional.
    assert {field.origin for field in before.answers} == {ModeloFormOrigin.OPTIONAL_EMPTY}
    # Once boxes 13 and 15 could not be worked out, the empty answers feeding them are what is missing.
    assert {field.box: field.origin for field in after.fields() if field.box in {"13", "15"}} == {
        "13": ModeloFormOrigin.CALCULATION_FAILED,
        "15": ModeloFormOrigin.CALCULATION_FAILED,
    }
    assert {field.origin for field in after.answers} == {ModeloFormOrigin.NEEDS_INPUT}
    assert {field.standing for field in after.answers} == {ModeloFormStanding.NEEDS_YOU}
    answers_group = next(group for group in after.outline if group.kind is ModeloFormOutlineKind.ANSWERS)
    assert answers_group.counts.needs_input == len(after.answers)
