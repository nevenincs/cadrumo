"""The activity-asset register serves its own reason, finding, advisory, refusal and filing-handoff sentences.

Each sentence is reached through the register's real operations or the executor
that serves them, in every language, and carries no flag, placeholder or raw token.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from cadrumo.application.actividad_asset.activity_asset_contracts import (
    ActivityAssetOperationPorts,
    ActivityAssetPlanRequest,
)
from cadrumo.application.actividad_asset.activity_asset_executors import (
    ActivityAssetPlanExecutor,
    activity_asset_executors_refusal,
)
from cadrumo.application.actividad_asset.activity_asset_read_models import (
    PLAN_ADVISORY_FAMILY,
    ActivityAssetHandoffLeftOutReason,
    ActivityAssetPlanAdvisory,
    ActivityAssetPlanAdvisoryKind,
    ActivityAssetPlanRow,
    ActivityAssetReasonFact,
    ActivityAssetReasonFactKind,
    activity_asset_label_key,
)
from cadrumo.application.actividad_asset.operation_dtos import ActivityAssetFilingHandoffSnapshot
from cadrumo.application.actividad_asset.operations import ActivityAssetOperations
from cadrumo.application.actividad_asset.schedule_walk import M100GapKind
from cadrumo.application.actividad_asset.served_words import (
    left_out_entry,
    m100_gap_words,
    partial_words,
    reason_words,
    worded_advisory,
)
from cadrumo.core.external_constants import OutputLanguage
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope
from cadrumo.domain.contribuyente.tax_residence import ResidenceTerritory
from cadrumo.domain.renta.actividad_asset.disposal import ActivityAssetDisposalFindingKind
from cadrumo.domain.renta.actividad_asset.election import DirectEstimationRegime
from cadrumo.domain.renta.actividad_asset.errors import ActividadAssetValidationError

from ....domain.calculations.registry.authority import bundled_indexed_authority
from .ledger_support import MemoryLedger
from .operations_support import build_operations, build_revision
from .register_support import MemoryRepository, memory_register_authority
from .test_baja_correction import low_value_forecast, low_value_revision
from .test_method_without_table_minimum import KEY
from .test_register import ACQUISITION, NAME, register_operations, register_revision

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_LANGUAGES = list(OutputLanguage)
_TAX_YEAR = build_revision().in_service_date.year
_PLACEHOLDER = re.compile(r"%\{|\{|\}")
_OPTION = re.compile(r"(?<!\w)--[a-z]")
_TOKEN = re.compile(r"\b[a-z]+_[a-z_]+\b")


@pytest.fixture(autouse=True)
def _pinned_authority() -> Iterator[None]:
    with bundled_indexed_authority().operation():
        yield


def _no_ports(*, bucket_id: str, operation: PinnedAuthorityOperation) -> ActivityAssetOperationPorts:
    raise AssertionError("the plan read takes the operations it is handed")


def _finished(sentence: str | None) -> str:
    assert sentence is not None and sentence.strip() == sentence and sentence
    assert not _PLACEHOLDER.search(sentence), sentence
    assert not _OPTION.search(sentence), sentence
    assert not _TOKEN.search(sentence), sentence
    return sentence


def _differ(sentences: dict[OutputLanguage, str]) -> None:
    assert len(set(sentences.values())) == len(sentences), sentences


@pytest.mark.parametrize("kind", list(ActivityAssetDisposalFindingKind))
def test_every_disposal_finding_is_said_whole_in_every_language(kind: ActivityAssetDisposalFindingKind) -> None:
    key = activity_asset_label_key("disposal_finding", kind)
    _differ({language: _finished(reason_words(key, (), language)) for language in _LANGUAGES})


def test_the_used_element_advisory_is_served_in_every_language() -> None:
    kind = ActivityAssetPlanAdvisoryKind.USED_ELEMENT_GROUP_LIMIT
    advisory = ActivityAssetPlanAdvisory(kind=kind, label_key=activity_asset_label_key(PLAN_ADVISORY_FAMILY, kind))
    said = {language: worded_advisory(advisory, language) for language in _LANGUAGES}
    assert all(item.words_language is language for language, item in said.items())
    _differ({language: _finished(item.words) for language, item in said.items()})


@pytest.mark.parametrize("language", _LANGUAGES)
def test_a_reason_is_filled_with_its_facts_as_the_language_writes_them(language: OutputLanguage) -> None:
    facts = (
        ActivityAssetReasonFact(
            key="tax_year", value=str(filing_year_envelope().horizon), kind=ActivityAssetReasonFactKind.COUNT
        ),
    )
    said = _finished(reason_words("ledger.actividad_asset.errors.tax_year_without_edition", facts, language))
    # A tax year is a count, so it carries no thousands mark in any language.
    assert str(filing_year_envelope().horizon) in said


def test_a_reason_lacking_a_fact_it_needs_is_not_served_half_filled() -> None:
    assert reason_words("ledger.actividad_asset.errors.tax_year_without_edition", (), OutputLanguage.EN) is None
    assert reason_words("not.a.register.key", (), OutputLanguage.EN) is None
    assert reason_words(None, (), OutputLanguage.EN) is None


@pytest.mark.parametrize("language", _LANGUAGES)
def test_the_plan_serves_the_no_table_minimum_as_a_flag_and_a_sentence(language: OutputLanguage) -> None:
    operations = ActivityAssetOperations(
        repository=MemoryRepository(),
        ledger=MemoryLedger(ACQUISITION),
        forecast_operation=low_value_forecast,
        taxpayer_modality=lambda: DirectEstimationRegime.SIMPLIFIED,
        register_authority=memory_register_authority(today=date(low_value_revision().in_service_date.year + 1, 12, 31)),
    )
    operations.create(low_value_revision(), NAME)
    executor = ActivityAssetPlanExecutor(_no_ports)

    served = executor._read(
        operations, ActivityAssetPlanRequest(profile_id=uuid4(), asset_id="laptop-1", output_language=language)
    )
    rows = served["rows"]
    assert isinstance(rows, tuple)
    row = rows[0]
    assert isinstance(row, ActivityAssetPlanRow)
    assert row.minimum_reason_key == KEY
    assert row.minimum_has_no_table is True
    assert row.words_language is language
    _finished(row.minimum_reason_words)


def test_a_table_method_minimum_is_not_flagged_and_has_no_sentence() -> None:
    operations, _ = register_operations()
    operations.create(register_revision(), NAME)
    row = operations.plan("laptop-1")[0]
    assert row.minimum_has_no_table is False
    assert row.minimum_reason_words is None


@pytest.mark.parametrize("language", _LANGUAGES)
def test_the_handoff_names_each_interval_by_the_registers_name_for_the_element(language: OutputLanguage) -> None:
    handoff = build_operations().filing_handoff(tax_year=_TAX_YEAR, language=language)
    snapshot = ActivityAssetFilingHandoffSnapshot.from_domain(handoff)
    (gap,) = snapshot.m100_gaps
    assert gap.words_language is language
    words = _finished(gap.words)
    assert "Office laptop" in words
    assert "laptop-1" not in words
    # It survives the round trip a frontend of this process takes.
    assert snapshot.to_domain().m100_gaps[0].words == gap.words


def test_the_handoff_gap_sentences_differ_by_kind_and_language() -> None:
    for kind in M100GapKind:
        said = {
            language: _finished(
                m100_gap_words(
                    kind,
                    name="Office laptop",
                    covered_from=date(_TAX_YEAR, 1, 1),
                    covered_through=date(_TAX_YEAR, 12, 31),
                    accrued=None if kind is not M100GapKind.ACCRUED else Decimal("520"),
                    language=language,
                )
            )
            for language in _LANGUAGES
        }
        _differ(said)


def test_an_element_without_a_name_is_said_so_and_never_by_its_identifier() -> None:
    for language in _LANGUAGES:
        words = _finished(
            m100_gap_words(
                M100GapKind.FREE_METHOD,
                name=None,
                covered_from=date(_TAX_YEAR, 1, 1),
                covered_through=date(_TAX_YEAR, 12, 31),
                accrued=None,
                language=language,
            )
        )
        assert "laptop-1" not in words


@pytest.mark.parametrize("reason", list(ActivityAssetHandoffLeftOutReason))
def test_what_a_modelo_130_amount_leaves_out_is_named_or_counted(reason: ActivityAssetHandoffLeftOutReason) -> None:
    names = {"a": "Office laptop", "b": "Printer"}
    for language in _LANGUAGES:
        named = left_out_entry(reason, ("a", "b"), names, language)
        assert named.words_language is language
        assert "Office laptop" in named.words and "Printer" in named.words
        _finished(named.words)
        # One element the register does not name makes the sentence count them instead of guessing a name.
        counted = left_out_entry(reason, ("a", "c"), names, language)
        assert "Office laptop" not in counted.words and "2" in _finished(counted.words)
        single = left_out_entry(reason, ("c",), names, language)
        assert single.words != counted.words and "1" in _finished(single.words)
    _differ({language: left_out_entry(reason, ("a",), names, language).words for language in _LANGUAGES})


def test_the_partial_sentence_counts_the_elements_left_out() -> None:
    for language in _LANGUAGES:
        assert partial_words(1, language) != partial_words(3, language)
        assert "3" in _finished(partial_words(3, language))
    _differ({language: partial_words(3, language) for language in _LANGUAGES})


def test_the_handoff_for_a_period_with_nothing_left_out_serves_no_left_out_entry() -> None:
    handoff = build_operations().filing_handoff(
        tax_year=_TAX_YEAR, m130_period=Period.from_year_and_code(_TAX_YEAR, "4T"), language=OutputLanguage.ES
    )
    assert handoff.left_out == ()
    assert handoff.material_m130 is not None and handoff.material_m130.partial_words is None


@pytest.mark.parametrize("language", _LANGUAGES)
def test_a_refusal_is_served_as_a_sentence_in_the_language_the_request_asked(language: OutputLanguage) -> None:
    operations = build_operations(territory=ResidenceTerritory.FORAL)
    with pytest.raises(ActividadAssetValidationError) as caught:
        operations.filing_handoff(tax_year=_TAX_YEAR, language=language)

    refusal = activity_asset_executors_refusal(caught.value, language)

    assert refusal is not None
    assert refusal.refusal_words_language is language
    _finished(refusal.refusal_words)


def test_a_refusal_with_no_reason_of_its_own_is_worded_as_the_operation_error_detail_words_it() -> None:
    refusal = activity_asset_executors_refusal(ActividadAssetValidationError(), OutputLanguage.ES)

    assert refusal is not None
    assert refusal.refusal_words is not None
    assert refusal.refusal_words_language is not None
