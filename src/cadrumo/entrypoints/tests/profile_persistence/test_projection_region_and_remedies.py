"""The real Modelo 100 projection defaults its region from the profile and refuses with served remedies.

Each case runs the production projection service over an isolated encrypted profile, and
the refusals are published through the same error-detail builder the supervisor uses for a
stopped operation. A refusal serves finished words in every language, and the way to put
it right travels as a typed catalogue action, never as a command inside the sentence.
"""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

import pytest

from cadrumo.application.modelo.projection import (
    ModeloProjectNoM130RevisionsError,
    ModeloProjectNoM130UnitsError,
    ModeloProjectRegionUnstatedError,
    ModeloProjectRevisionNotMappedError,
)
from cadrumo.application.modelo.projection_declaration import modelo_projection_available
from cadrumo.application.modelo.projection_operation import ModeloProjectOperationProjection
from cadrumo.application.operations.error_detail import OperationErrorDetailV1, build_operation_error_detail
from cadrumo.application.operations.next_step import OperationCalculateWorkStepV1, OperationCreateWorkStepV1
from cadrumo.core.config import override_settings
from cadrumo.core.external_constants import SUPPORTED_OUTPUT_LANGUAGES, OutputLanguage
from cadrumo.core.i18n.render import lookup_translation
from cadrumo.core.operator_action_enums import NoRecoveryOutcome
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.user_profile.values import UserProfileFact

from .projection_m130_seeding_support import (
    PROJECTION_YEAR,
    QuarterSeeding,
    follow_projection_steps,
    run_projection,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_CATALAN_RESIDENCE = UserProfileFact(path="tax_residence.ccaa", value="cataluna")


def _served(refusal: BaseException, language: str) -> OperationErrorDetailV1:
    with override_settings(cadrumo_output_language=language):
        detail = build_operation_error_detail(refusal)
    assert detail is not None
    assert detail.refusal_words is not None and detail.refusal_words_language is OutputLanguage(language)
    return detail


def _words_by_language(refusal: BaseException) -> dict[str, str]:
    words = {language: _served(refusal, language).refusal_words for language in SUPPORTED_OUTPUT_LANGUAGES}
    assert all(sentence for sentence in words.values())
    return {language: sentence for language, sentence in words.items() if sentence is not None}


def _step_words_by_language(refusal: BaseException) -> dict[str, str]:
    words: dict[str, str] = {}
    for language in SUPPORTED_OUTPUT_LANGUAGES:
        step = _served(refusal, language).next_step
        assert step is not None
        words[language] = step.words
    return words


def _names_no_command(words: str) -> bool:
    return "aeat" not in words.lower() and "`" not in words and "--" not in words


def test_an_omitted_region_is_the_one_the_profile_states(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    named = run_projection(tmp_path / "named", operation, ccaa="madrid")
    defaulted = run_projection(tmp_path / "defaulted", operation, ccaa=None)

    assert defaulted.ccaa == "madrid"
    assert defaulted.m100_projection == named.m100_projection
    assert defaulted.casilla_observations == named.casilla_observations


def test_a_region_the_request_names_overrides_the_profiles(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    """The autonomous-community scale follows the named region, and the result reports that region.

    The expected figures are the projections of profiles that state each region themselves.
    """
    madrid_filer = run_projection(tmp_path / "madrid", operation, ccaa=None)
    catalan_filer = run_projection(tmp_path / "catalan", operation, ccaa=None, profile_facts=(_CATALAN_RESIDENCE,))
    assert madrid_filer.m100_projection != catalan_filer.m100_projection

    catalan_filer_asking_for_madrid = run_projection(
        tmp_path / "override", operation, ccaa="madrid", profile_facts=(_CATALAN_RESIDENCE,)
    )

    assert catalan_filer_asking_for_madrid.ccaa == "madrid"
    assert catalan_filer_asking_for_madrid.m100_projection == madrid_filer.m100_projection


def test_a_profile_that_states_no_region_is_refused_and_no_region_is_guessed(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    with pytest.raises(ModeloProjectRegionUnstatedError) as refused:
        run_projection(tmp_path / "silent", operation, ccaa=None, states_region=False)

    words = _words_by_language(refused.value)
    assert len(set(words.values())) == len(SUPPORTED_OUTPUT_LANGUAGES)
    assert all(_names_no_command(sentence) for sentence in words.values())
    detail = _served(refused.value, "en")
    assert detail.error_code == "REFUSED_MODELO_PROJECT_REGION_UNSTATED"
    verdict = detail.precondition_verdict()
    assert verdict is not None
    # The region is the filer's own fact, so no catalogue action can state it for them.
    assert verdict.action is None and verdict.no_recovery_outcome is NoRecoveryOutcome.OPERATOR_DECISION


def test_a_region_the_request_names_serves_a_profile_that_states_none(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    result = run_projection(tmp_path, operation, ccaa="madrid", states_region=False)

    assert result.ccaa == "madrid"
    assert result.quarters_filed == 1


def test_a_year_with_no_quarterly_declaration_serves_the_creation_as_an_action(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    with pytest.raises(ModeloProjectNoM130UnitsError) as refused:
        run_projection(tmp_path, operation, ccaa=None, quarter=QuarterSeeding.NONE)

    words = _words_by_language(refused.value)
    assert len(set(words.values())) == len(SUPPORTED_OUTPUT_LANGUAGES)
    for sentence in words.values():
        assert str(PROJECTION_YEAR) in sentence
        assert _names_no_command(sentence)
    detail = _served(refused.value, "es")
    assert detail.error_code == "ERROR_MODELO_PROJECT_NO_M130_UNITS"
    verdict = detail.precondition_verdict()
    assert verdict is not None and verdict.action is not None
    assert verdict.action.action_id == "operator.modelo.work.create"
    assert {item.argument_name: item.value for item in verdict.argument_bindings} == {
        "modelo": "130",
        "period": "1T",
        "year": PROJECTION_YEAR,
    }
    # The same remedy travels as a typed step, so a frontend runs it without knowing an action identifier.
    step = detail.next_step
    assert isinstance(step, OperationCreateWorkStepV1)
    assert (step.modelo, step.filing_year, step.period_code) == ("130", PROJECTION_YEAR, "1T")
    offers = _step_words_by_language(refused.value)
    assert len(set(offers.values())) == len(SUPPORTED_OUTPUT_LANGUAGES)
    for sentence in offers.values():
        assert "130" in sentence and str(PROJECTION_YEAR) in sentence
        assert _names_no_command(sentence)
    # The step survives the stored detail's round trip, as the relay releases it.
    assert OperationErrorDetailV1.model_validate_json(detail.model_dump_json()).next_step == step


def test_a_drafted_quarter_nobody_calculated_serves_its_calculation_as_an_action(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    with pytest.raises(ModeloProjectNoM130RevisionsError) as refused:
        run_projection(tmp_path, operation, ccaa=None, quarter=QuarterSeeding.DRAFT_ONLY)

    words = _words_by_language(refused.value)
    assert len(set(words.values())) == len(SUPPORTED_OUTPUT_LANGUAGES)
    for sentence in words.values():
        assert str(PROJECTION_YEAR) in sentence
        assert _names_no_command(sentence)
    verdict = _served(refused.value, "ca").precondition_verdict()
    assert verdict is not None and verdict.action is not None
    assert verdict.action.action_id == "operator.modelo.work.calculate"
    (binding,) = verdict.argument_bindings
    assert binding.argument_name == "work_unit_id" and isinstance(binding.value, str) and binding.value
    step = _served(refused.value, "ca").next_step
    assert isinstance(step, OperationCalculateWorkStepV1)
    # The step addresses the very declaration the verdict's action does.
    assert step.work_unit_id == binding.value
    offers = _step_words_by_language(refused.value)
    assert len(set(offers.values())) == len(SUPPORTED_OUTPUT_LANGUAGES)
    for sentence in offers.values():
        assert "130" in sentence and _names_no_command(sentence)


def test_creating_the_declaration_a_step_names_leads_to_the_step_that_calculates_it(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    """Following the first refusal's step from its address alone makes the second refusal name that declaration."""
    followed = follow_projection_steps(tmp_path, operation)

    assert (followed.create.modelo, followed.create.filing_year, followed.create.period_code) == (
        "130",
        PROJECTION_YEAR,
        "1T",
    )
    assert followed.calculate.work_unit_id == followed.created_work_unit_id


def test_a_refusal_no_action_can_put_right_serves_no_step(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    with pytest.raises(ModeloProjectRegionUnstatedError) as unstated:
        run_projection(tmp_path / "silent", operation, ccaa=None, states_region=False)
    with pytest.raises(ModeloProjectRevisionNotMappedError) as unnamed:
        run_projection(tmp_path / "unnamed", operation, ccaa=None, year=PROJECTION_YEAR - 1)

    for refused in (unstated.value, unnamed.value):
        assert all(_served(refused, language).next_step is None for language in SUPPORTED_OUTPUT_LANGUAGES)


def test_each_figure_of_the_projection_is_named_in_every_language(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    result = run_projection(tmp_path, operation, ccaa=None)
    generation = operation.generation.logical_generation
    served: dict[str, ModeloProjectOperationProjection] = {}
    for language in SUPPORTED_OUTPUT_LANGUAGES:
        with override_settings(cadrumo_output_language=language):
            served[language] = ModeloProjectOperationProjection.from_service(
                _PROFILE, result, authority_generation=generation
            )

    for language, projection in served.items():
        prefix = "application.modelo.projection_words.figure"
        quarterly = projection.m130_accumulated.words.model_dump()
        annual = projection.m100_projection.words.model_dump()
        assert set(quarterly) == {"ingresos", "gastos", "rendimiento_neto", "pagos_fraccionados"}
        assert len(annual) == 7
        for name, label in quarterly.items():
            assert label == lookup_translation(f"{prefix}.m130.{name}", locale=language)
        for name, label in annual.items():
            assert label == lookup_translation(f"{prefix}.m100.{name}", locale=language)
        labels = [*quarterly.values(), *annual.values()]
        assert all(label.strip() and "_" not in label and "%" not in label for label in labels)
        assert len(set(labels)) == len(labels)
    # Words in a language read as that language, not as the English fallback.
    english = {*served["en"].m130_accumulated.words.model_dump().values()}
    assert not english & {*served["hu"].m130_accumulated.words.model_dump().values()}
    assert not english & {*served["es"].m130_accumulated.words.model_dump().values()}


@pytest.mark.parametrize(("year", "named"), [(2022, False), (2023, False), (2024, False), (PROJECTION_YEAR, True)])
def test_the_projection_runs_only_for_a_year_the_registry_mapping_names(
    year: int, named: bool, tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    """The mapping names the 2025 annual return; the operation follows the capability the form serves.

    The expected answer is read from the mapping's own revision, not from the
    check: the 2022 to 2024 returns are other revisions than the one named.
    """
    revision = operation.revision_for_context("100", filing_year=year, period="0A")
    assert (str(revision.id) == "2025") is named
    served = modelo_projection_available(
        modelo="100",
        period=Period.from_year_and_code(year, "0A"),
        filing_year=year,
        registry_revision_id=str(revision.id),
        operation=operation,
    )
    assert served is named

    if named:
        assert run_projection(tmp_path, operation, ccaa=None, year=year).year == year
        return
    with pytest.raises(ModeloProjectRevisionNotMappedError) as refused:
        run_projection(tmp_path, operation, ccaa=None, year=year)

    words = _words_by_language(refused.value)
    assert len(set(words.values())) == len(SUPPORTED_OUTPUT_LANGUAGES)
    for sentence in words.values():
        assert str(year) in sentence
        assert _names_no_command(sentence)
    detail = _served(refused.value, "hu")
    assert detail.error_code == "REFUSED_MODELO_PROJECT_REVISION_NOT_MAPPED"
    verdict = detail.precondition_verdict()
    assert verdict is not None
    # The registry decides what it names, so no catalogue action can put this right.
    assert verdict.action is None and verdict.no_recovery_outcome is NoRecoveryOutcome.TERMINAL


def test_a_target_the_mapping_does_not_name_is_refused_before_any_quarter_is_read(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    """A 2025 quarter is stored and none exists for 2024, yet the refusal is the mapping's, not a missing quarter."""
    with pytest.raises(ModeloProjectRevisionNotMappedError):
        run_projection(tmp_path, operation, ccaa=None, year=PROJECTION_YEAR - 1, quarter=QuarterSeeding.NONE)
