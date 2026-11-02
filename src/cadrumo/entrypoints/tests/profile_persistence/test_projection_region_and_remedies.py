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
)
from cadrumo.application.modelo.projection_operation import ModeloProjectOperationProjection
from cadrumo.application.operations.error_detail import OperationErrorDetailV1, build_operation_error_detail
from cadrumo.core.config import override_settings
from cadrumo.core.external_constants import SUPPORTED_OUTPUT_LANGUAGES, OutputLanguage
from cadrumo.core.i18n.render import lookup_translation
from cadrumo.core.operator_action_enums import NoRecoveryOutcome
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.user_profile.values import UserProfileFact

from .projection_m130_seeding_support import PROJECTION_YEAR, QuarterSeeding, run_projection

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
