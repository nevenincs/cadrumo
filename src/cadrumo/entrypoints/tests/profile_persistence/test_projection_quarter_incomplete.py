"""The real Modelo 100 estimate names what a calculated quarter still lacks and serves the step that opens it.

A first-quarter Modelo 130 calculated without the answers about earlier filings cannot produce its final
result, so the estimate has nothing to read from it. Each case runs the production calculation and the
production projection service over an isolated encrypted profile, and the refusal is published through the
same error-detail builder the supervisor uses for a stopped operation. What the sentence names is checked
against the labels the quarter's own form serves, read independently in each language.
"""

from __future__ import annotations

import re
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

import pytest

from cadrumo.application.modelo.edit_models import (
    ModeloBindingEditIntentV1,
    ModeloEditBindingAddressV1,
    ModeloEditBindingIntentKind,
)
from cadrumo.application.modelo.projection import (
    ModeloProjectQuarterIncompleteError,
    ModeloProjectServiceResult,
    project_modelo_100_from_m130,
)
from cadrumo.application.modelo.work_form_field_vocabulary import (
    ModeloFormOrigin,
    address_key,
)
from cadrumo.application.modelo.work_form_service import load_modelo_work_form
from cadrumo.application.operations.error_detail import OperationErrorDetailV1, build_operation_error_detail
from cadrumo.application.operations.next_step import OperationOpenWorkStepV1
from cadrumo.core.config import override_settings
from cadrumo.core.external_constants import SUPPORTED_OUTPUT_LANGUAGES, OutputLanguage
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.user_profile.tests.general_regime_facts import RENTA_UNMARRIED_TAXPAYER_FACTS
from cadrumo.domain.user_profile.values import UserProfileFact
from cadrumo.entrypoints.adapter_composition import profile_adapter_composition
from cadrumo.entrypoints.tests.modelo_operator_work_storage import SeededOperatorWork, seeded_operator_work

from .projection_m130_seeding_support import QuarterSeeding, run_projection

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_YEAR = 2025
#: The answers about earlier filings the first quarter refuses without, by binding.
_EARLIER_FILING_ANSWERS = (
    ("irpf.previous_year_economic_activity_net_income", "13000"),
    ("modelo-130-resultados-negativos-anteriores", "0"),
    ("modelo-130-pagos-fraccionados-anteriores", "0"),
)
#: What the form asks the filer for in the bare quarter, by address: the negative results of earlier quarters, behind
#: box 15, and the previous year's net income, behind the reduction for net yields, which has no box of its own.
_OPEN_ADDRESSES = (
    ("binding", "modelo-130-resultados-negativos-anteriores"),
    ("binding", "irpf.previous_year_economic_activity_net_income"),
)
_FACTS = (
    UserProfileFact(path="taxpayer_type.irpf_income_categories", value="actividad_economica"),
    UserProfileFact(path="tax_residence.ccaa", value="madrid"),
    *RENTA_UNMARRIED_TAXPAYER_FACTS,
)


@contextmanager
def _bare_quarter(tmp_path: Path) -> Generator[SeededOperatorWork]:
    """The 2025 first-quarter Modelo 130 of a profile, calculated with none of the earlier-filing answers."""
    with (
        profile_adapter_composition(),
        seeded_operator_work(
            tmp_path, modelo="130", filing_year=_YEAR, period_code="1T", extra_facts=_FACTS
        ) as quarter,
    ):
        quarter.recalculate()
        yield quarter


def _estimate(work: SeededOperatorWork) -> ModeloProjectServiceResult:
    return project_modelo_100_from_m130(
        year=_YEAR, ccaa=None, bucket_id=work.work_unit.bucket_id, ports=work.ports, operation=work.operation
    )


def _refusal(work: SeededOperatorWork) -> ModeloProjectQuarterIncompleteError:
    with pytest.raises(ModeloProjectQuarterIncompleteError) as refused:
        _estimate(work)
    return refused.value


def _served(refusal: BaseException, language: str) -> OperationErrorDetailV1:
    with override_settings(cadrumo_output_language=language):
        detail = build_operation_error_detail(refusal)
    assert detail is not None
    assert detail.refusal_words is not None and detail.refusal_words_language is OutputLanguage(language)
    return detail


def _refused_in(work: SeededOperatorWork, language: str) -> OperationErrorDetailV1:
    """The refusal the estimate raises when asked in ``language``, as the supervisor publishes it."""
    with override_settings(cadrumo_output_language=language):
        refusal = _refusal(work)
        return _served(refusal, language)


def _open_fields(work: SeededOperatorWork, language: str) -> dict[tuple[str, str], tuple[str, str | None]]:
    """The label and printed box of each value the quarter's form asks the filer for, in ``language``."""
    loaded = load_modelo_work_form(
        work.work_unit.bucket_id,
        work.work_unit.modelo,
        work.work_unit.filing_year,
        work.work_unit.period,
        operation=work.operation,
        work_unit_repository=work.ports.work_unit_repository,
        calculation_repository=work.ports.calculation_repository,
        verification_repository=work.ports.verification_repository,
        admission=None,
        language=OutputLanguage(language),
    )
    return {
        address_key(field.address): (field.label.text, field.box)
        for field in loaded.form.fields()
        if field.origin is ModeloFormOrigin.NEEDS_INPUT
    }


def _answer(work: SeededOperatorWork) -> None:
    applied = work.apply(
        binding=tuple(
            ModeloBindingEditIntentV1(
                address=ModeloEditBindingAddressV1(binding_id=binding_id),
                kind=ModeloEditBindingIntentKind.SET_OVERRIDE_VALUE,
                value=value,
            )
            for binding_id, value in _EARLIER_FILING_ANSWERS
        )
    )
    assert applied.refusal is None
    work.recalculate()


def test_a_quarter_calculated_without_its_earlier_filing_answers_names_what_is_open(tmp_path: Path) -> None:
    with _bare_quarter(tmp_path) as quarter:
        # The quarter really lacks the box the estimate reads, so the refusal is not a stand-in.
        head = quarter.require_head()
        assert "19" not in head.casilla_values

        words: dict[str, str] = {}
        for language in SUPPORTED_OUTPUT_LANGUAGES:
            detail = _refused_in(quarter, language)
            asked = _open_fields(quarter, language)
            assert detail.error_code == "REFUSED_MODELO_PROJECT_QUARTER_INCOMPLETE"
            sentence = detail.refusal_words
            assert sentence is not None
            # Each value the form asks for is named by the label the form serves and its printed number.
            assert set(_OPEN_ADDRESSES) <= set(asked)
            for label, box in asked.values():
                assert label in sentence
                assert box is None or re.search(rf"@BS@b{box}@BS@b", sentence)
            # Nothing else of the quarter is named: no amount, only the declaration, its year and the numbers the
            # served labels and boxes print.
            printed = {*re.findall(r"@BS@d+", " ".join(f"{label} {box or ''}" for label, box in asked.values()))}
            assert {*re.findall(r"@BS@d+", sentence)} <= {"130", str(_YEAR), "1", *printed}
            assert "`" not in sentence and "--" not in sentence and "aeat" not in sentence.lower()
            words[language] = sentence
        assert len(set(words.values())) == len(SUPPORTED_OUTPUT_LANGUAGES)
        # Not the generic failure it replaces.
        generic = {_refused_in(quarter, language).refusal_words for language in SUPPORTED_OUTPUT_LANGUAGES}
        assert generic == set(words.values())
        assert all("projection failed" not in sentence.lower() for sentence in words.values())


def test_the_refusal_serves_the_step_that_opens_the_quarter(tmp_path: Path) -> None:
    with _bare_quarter(tmp_path) as quarter:
        offers: dict[str, str] = {}
        for language in SUPPORTED_OUTPUT_LANGUAGES:
            detail = _refused_in(quarter, language)
            step = detail.next_step
            assert isinstance(step, OperationOpenWorkStepV1)
            # The very declaration whose form states what is open.
            assert step.work_unit_id == quarter.work_unit_id
            assert "130" in step.words and "2025" in step.words
            assert "`" not in step.words and "--" not in step.words
            offers[language] = step.words
            # The step survives the stored detail's round trip, as the relay releases it.
            assert OperationErrorDetailV1.model_validate_json(detail.model_dump_json()).next_step == step
        assert len(set(offers.values())) == len(SUPPORTED_OUTPUT_LANGUAGES)


def test_the_refusal_names_the_earliest_quarter_that_lacks_a_box(tmp_path: Path) -> None:
    with _bare_quarter(tmp_path) as first:
        second = first.sibling("2T")
        _answer(second)
        assert "19" in second.require_head().casilla_values
        detail = _refused_in(first, "en")
        step = detail.next_step
        assert isinstance(step, OperationOpenWorkStepV1)
        assert step.work_unit_id == first.work_unit_id != second.work_unit_id
        assert "1st quarter" in step.words


def test_giving_the_open_values_lets_the_estimate_run(tmp_path: Path) -> None:
    with _bare_quarter(tmp_path) as quarter:
        assert isinstance(_refusal(quarter), ModeloProjectQuarterIncompleteError)

        _answer(quarter)

        result = _estimate(quarter)
        assert result.quarters_filed == 1 and result.quarters_available == ("1T",)
        # The quarter's own final result is the paid instalment the estimate carries, not a stand-in zero.
        assert quarter.require_head().casilla_values["19"] == result.m130_accumulated.pagos_fraccionados


def test_a_stored_quarter_whose_form_names_nothing_open_is_still_refused_with_the_step_that_opens_it(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    """A calculation stored without its result box, over a form that marks nothing failed, names no box."""
    with pytest.raises(ModeloProjectQuarterIncompleteError) as refused:
        run_projection(tmp_path, operation, ccaa=None, quarter=QuarterSeeding.WITHOUT_RESULT)

    words: dict[str, str] = {}
    for language in SUPPORTED_OUTPUT_LANGUAGES:
        detail = _served(refused.value, language)
        assert detail.error_code == "REFUSED_MODELO_PROJECT_QUARTER_INCOMPLETE"
        assert detail.message_key == "application.modelo.projection_words.quarter_incomplete_unnamed"
        assert isinstance(detail.next_step, OperationOpenWorkStepV1)
        assert detail.refusal_words is not None
        words[language] = detail.refusal_words
    assert len(set(words.values())) == len(SUPPORTED_OUTPUT_LANGUAGES)
