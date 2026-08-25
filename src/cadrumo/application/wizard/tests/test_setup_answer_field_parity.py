"""The setup wizard and the core answer table must describe the same fields.

The core :data:`SETUP_ANSWER_FIELDS` table is what the deadline engine
projects a taxpayer profile through, and it is deliberately independent of
this package: a schedule is computed from stored facts and must not need an
interactive surface to exist. While the wizard still ships, both
declarations are live, and two live declarations of the same mapping drift.

This gate is the bridge that makes the drift impossible, and it belongs to
the wizard rather than to core precisely because it is temporary: when the
setup wizard is retired the table is the sole surviving authority, and this
file is deleted with the package it checks. Until then, adding a question
here without its table row — or changing a path or default on one side
only — fails loudly.
"""

from __future__ import annotations

import pytest

from ....core.setup_answers import (
    PROFILE_OUTPUT_LANGUAGE_PATH,
    SETUP_ANSWER_FIELDS,
    SetupAnswers,
    project_setup_answers,
)
from .._catalogue import SETUP_FLOW
from .._models import WizardQuestion
from .._persistence import project_answers

pytestmark = [
    pytest.mark.unit,
    pytest.mark.hex_application,
]

_QUESTIONS = tuple(question for section in SETUP_FLOW.sections for question in section.questions)

_TABLE_ONLY_FIELDS = frozenset(
    {"professional_income_withholding_ge_70pct", "irpf_activity_kind", "colegio_concertado"},
)
"""Table rows the wizard deliberately never asked for.

The Modelo 130 exemption flag has a declared schema path and a declared
model selector, but no setup question ever collected it, so the engine
read the model default and could not see a taxpayer who had recorded the
fact by any other route. The table reads it; the retired wizard did not.

``irpf_activity_kind`` is derived from a taxpayer's declared ledger
``tipo_actividad`` rows (see :func:`domain.transactions.irpf_activity_kind_for`),
never from an interactive answer, so no wizard question exists for it either.

``colegio_concertado`` is the Modelo 111 header declaration. It is deliberately
NOT a setup question: a CONFIRM question carries a default, and the only
defaults available are "yes" or "no" -- either of which would answer on behalf
of an operator who was never asked, which is exactly what the producer refuses
to do (``_validate_modelo_111_snapshot``). It has a declared schema path and a
declared model selector, so an operator states it through the profile-fact
surface, and until they do, filing the modelo refuses rather than assuming.
"""


def test_every_question_has_a_matching_table_row() -> None:
    """Path, type and default must agree field by field."""
    mismatches: list[str] = []
    for question in _QUESTIONS:
        field = question.id.replace("-", "_")
        spec = SETUP_ANSWER_FIELDS.get(field)
        if spec is None:
            mismatches.append(f"{field}: no row in SETUP_ANSWER_FIELDS")
            continue
        actual = (spec.path, spec.answer_type, spec.default)
        expected = (question.profile_key, question.answer_type, question.default)
        if actual != expected:
            mismatches.append(f"{field}: table={actual} catalogue={expected}")
    assert not mismatches, "\n".join(mismatches)


def test_the_table_adds_nothing_beyond_the_documented_rows() -> None:
    """A row with no question must be a deliberate, named addition."""
    asked = {question.id.replace("-", "_") for question in _QUESTIONS}
    assert set(SETUP_ANSWER_FIELDS) - asked == _TABLE_ONLY_FIELDS


def test_every_table_field_exists_on_the_answers_model() -> None:
    """A row naming a field the model does not declare would be silently dropped."""
    assert set(SETUP_ANSWER_FIELDS) <= set(SetupAnswers.model_fields)


def test_both_projections_agree_on_a_populated_record() -> None:
    """The relocation is behaviour-preserving on every field the wizard collected.

    Values are chosen to differ from each field's default so a projection
    that silently fell back to defaults could not pass: a blank record
    would make the two implementations agree for the wrong reason.
    """
    values = {
        question.profile_key: _non_default_token(question)
        for question in _QUESTIONS
        if question.profile_key is not None
    }
    values["identity.tax_id"] = "12345678Z"
    values["iva.regime"] = "GENERAL"
    values[PROFILE_OUTPUT_LANGUAGE_PATH] = "en"
    values["taxpayer_type.entity_type"] = ""
    values["taxpayer_type.legal_entity_form"] = ""
    values["renta_filing.declaration_type"] = ""
    values["taxpayer_type.fiscal_residency"] = ""
    values["tax_residence.ccaa"] = "madrid"
    values["taxpayer_type.irpf_income_categories"] = ""
    values["irpf.estimation_regime"] = ""
    values["irpf.special_regime"] = ""
    values["renta_family.situacion_familiar"] = ""
    values["renta_taxpayer.sex"] = ""
    values["renta_spouse.sex"] = ""
    values["renta_taxpayer.marital_status"] = ""
    values["renta_taxpayer.disability_grade"] = ""
    values["renta_spouse.disability_grade"] = ""
    for date_path in (
        "censo.activity_start_date",
        "irpf.special_regime_start_date",
        "renta_taxpayer.birth_date",
        "renta_taxpayer.death_date",
        "renta_taxpayer.marriage_date",
        "renta_spouse.birth_date",
        "taxpayer_type.ley_49_2002_special_regime_option_date",
        "taxpayer_type.ley_49_2002_special_regime_renunciation_date",
    ):
        values[date_path] = "2024-03-01"
    for decimal_path in (
        "taxpayer_type.incn_prior_12_months",
        *(f"irpf.objective_estimation_modulos_module_{index}_units" for index in range(1, 8)),
    ):
        values[decimal_path] = "12.5"

    from_table = project_setup_answers(values)
    from_catalogue = project_answers(SETUP_FLOW, values)

    ignored = {*_TABLE_ONLY_FIELDS}
    assert from_table.model_dump(exclude=ignored) == from_catalogue.model_dump(exclude=ignored)
    assert from_table.has_employees is True, "the fixture must not be all-defaults"


def test_the_table_reads_the_modelo_130_exemption_flag_the_wizard_never_asked_for() -> None:
    """The under-declaration this relocation closed, pinned.

    A profile that records the art. 109 professional-withholding fact now
    reaches the engine with it set. Before, the value was unreachable and
    every taxpayer looked like they had never declared it.
    """
    declared = {"identity.tax_id": "12345678Z", "irpf.professional_income_withholding_ge_70pct": "true"}
    from_catalogue = project_answers(SETUP_FLOW, declared)
    assert isinstance(from_catalogue, SetupAnswers)

    assert project_setup_answers(declared).professional_income_withholding_ge_70pct is True
    assert from_catalogue.professional_income_withholding_ge_70pct is False


def _non_default_token(question: WizardQuestion) -> str:
    """Return a token that is valid for the type and differs from ``default``."""
    if question.answer_type is bool:
        return "false" if question.default == "true" else "true"
    if question.choices:
        return next(choice.value for choice in question.choices if choice.value != question.default)
    return "sample"
