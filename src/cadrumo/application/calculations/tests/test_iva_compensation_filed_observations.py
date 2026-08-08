"""Filed-observation IVA compensation history tests."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.outbound.aeat.sede import ObservedCasillaValue
from ....core import CasillaValueKind, Period
from ....core.errors import ERROR_REGISTRY, build_error_envelope
from ....domain.iva_compensation import (
    IvaCompensationCasillaReferenceError,
    IvaCompensationDecimalParseError,
    IvaCompensationExpiryReviewState,
    IvaCompensationSeedConflictError,
    IvaCompensationYearRangeError,
    build_iva_compensation_carry_forward_report,
    enforce_iva_compensation_four_year_window,
)
from ....tests.secure_sql import isolated_runtime_profile
from .._errors import IvaCompensationModeloError
from .._iva_compensation_history import (
    IvaCompensationHistoryRepository,
    iva_compensation_annual_summary_from_filed_observation,
    iva_compensation_period_key,
    iva_compensation_state_from_filed_observation,
    seed_iva_compensation_period,
)
from ._iva_compensation_history_support import (
    _M303_POSTERIOR_CASILLA,
    _M303_PRINTED_NUMBER_REFERENCE_CASES,
    _M303_PRINTED_PERIOD_RESULT_REFERENCE_CASILLA,
    _M303_RESULTADO_CASILLA,
    _M390_PRINTED_LAST_PERIOD_COMPENSATION_REFERENCE_CASILLA,
    _TAXPAYER_REF,
    _filed_303_compensation_observation,
    _filed_390_observation,
    _filed_observation,
    _M303PrintedNumberSourceKind,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_HISTORY_BUCKET_ID = "30330300-0000-4000-8000-000000000303"
_CONFLICT_BUCKET_ID = "30330300-0000-4000-8000-000000000304"


def test_three_year_filed_history_repository_projects_compensation_lots(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_HISTORY_BUCKET_ID):
        repository = IvaCompensationHistoryRepository()
        observations = (
            _filed_303_compensation_observation(
                filing_year=2024,
                period="4T",
                resultado=Decimal("-100.00"),
            ),
            _filed_303_compensation_observation(
                filing_year=2025,
                period="2T",
                resultado=Decimal("25.00"),
                applied=Decimal("40.00"),
                posterior=Decimal("60.00"),
            ),
            _filed_303_compensation_observation(
                filing_year=2025,
                period="4T",
                resultado=Decimal("-75.00"),
            ),
            _filed_303_compensation_observation(
                filing_year=2026,
                period="1T",
                resultado=Decimal("10.00"),
                applied=Decimal("20.00"),
                posterior=Decimal("115.00"),
            ),
        )

        for observation in observations:
            repository.save_period(iva_compensation_state_from_filed_observation(observation))

        reloaded = IvaCompensationHistoryRepository().list_periods()
        report = build_iva_compensation_carry_forward_report(reloaded, as_of_year=2026)
        enforce_iva_compensation_four_year_window(report)

    assert tuple(state.source_observation_key for state in reloaded) == (
        "303:2024:4T:20243034T000001",
        "303:2025:2T:20253032T000001",
        "303:2025:4T:20253034T000001",
        "303:2026:1T:20263031T000001",
    )
    assert [(state.filing_year, state.period) for state in reloaded] == [
        (2024, Period.from_year_and_code(2024, "4T")),
        (2025, Period.from_year_and_code(2025, "2T")),
        (2025, Period.from_year_and_code(2025, "4T")),
        (2026, Period.from_year_and_code(2026, "1T")),
    ]
    assert [
        (
            lot.source_filing_year,
            lot.source_period,
            lot.generated_amount,
            lot.applied_amount,
            lot.remaining_amount,
            lot.expiry_review_state,
        )
        for lot in report.lots
    ] == [
        (
            2024,
            Period.from_year_and_code(2024, "4T"),
            Decimal("100.00"),
            Decimal("60.00"),
            Decimal("40.00"),
            IvaCompensationExpiryReviewState.ACTIVE,
        ),
        (
            2025,
            Period.from_year_and_code(2025, "4T"),
            Decimal("75.00"),
            Decimal("0"),
            Decimal("75.00"),
            IvaCompensationExpiryReviewState.ACTIVE,
        ),
    ]
    assert report.unallocated_applied_amount == Decimal("0")


def test_iva_compensation_modelo_error_is_registered_in_error_registry() -> None:
    assert "REFUSED_IVA_COMPENSATION_MODELO" in ERROR_REGISTRY


def test_iva_compensation_modelo_error_round_trips_through_build_error_envelope() -> None:
    exc = IvaCompensationModeloError(
        translated_message="application.calculations.iva_compensation.errors.modelo_303_only",
        context={"modelo": "130"},
    )
    envelope = build_error_envelope(exc, trace_id=None)
    assert envelope.code == "REFUSED_IVA_COMPENSATION_MODELO"
    assert envelope.retryable is False
    assert envelope.suggestion == "aeat app live iva-wallet history"
    assert envelope.message != "IVA compensation history only accepts Modelo 303 observations"


def test_a_filing_with_no_posterior_casilla_still_carries_the_credit_it_generated() -> None:
    """A negative result generates carry-forward whether or not casilla 87 was declared.

    The canonical filed-casilla derivation declines a filing that declares no
    ``iva.compensacion-pendiente-periodos-posteriores``, because its two
    AEAT-fetched callers read that as "do not stamp the availability casilla".
    This projection has no such choice to make: both amount fields of the
    period state are non-optional, and a period that declared a quota a
    compensar generated that credit regardless. Losing it here under-states the
    carry, which over-taxes the taxpayer one period later -- the direction
    nothing else in the chain watches.
    """
    observation = _filed_303_compensation_observation(
        filing_year=2025,
        period="4T",
        resultado=Decimal("-100.00"),
    )
    without_posterior = observation.model_copy(
        update={
            "casillas": tuple(
                casilla for casilla in observation.casillas if casilla.casilla_id != _M303_POSTERIOR_CASILLA
            ),
        },
    )
    assert len(without_posterior.casillas) == len(observation.casillas) - 1, "the fixture still declares a posterior"

    state = iva_compensation_state_from_filed_observation(without_posterior)

    assert state.pending_for_later_amount is None
    assert state.generated_amount == Decimal("100.00")
    assert state.available_end_amount == Decimal("100.00")


def test_iva_compensation_state_from_filed_observation_raises_for_non_303_modelo() -> None:
    observation = _filed_observation(modelo="130")
    with pytest.raises(IvaCompensationModeloError) as excinfo:
        iva_compensation_state_from_filed_observation(observation)

    assert excinfo.value.translated_message == "application.calculations.iva_compensation.errors.modelo_303_only"
    assert excinfo.value.context == {"modelo": "130"}


def test_iva_compensation_period_key_raises_localized_year_range_error() -> None:
    with pytest.raises(IvaCompensationYearRangeError) as excinfo:
        iva_compensation_period_key(Period.from_year_and_code(1999, "1T"))

    assert excinfo.value.translated_message == "errors.refused.refused_iva_compensation_year_range"
    assert excinfo.value.context == {"filing_year": 1999, "min_year": 2000, "max_year": 2099}


def test_iva_compensation_state_from_filed_observation_raises_localized_decimal_parse_error() -> None:
    observation = _filed_observation(modelo="303").model_copy(
        update={
            "casillas": (
                ObservedCasillaValue(
                    casilla_id=_M303_RESULTADO_CASILLA,
                    value="not-decimal",
                    value_kind=CasillaValueKind.NUMERIC,
                    source_artefact_kind="submitted_file",
                    source_locator="submitted-file:casilla-69",
                    confidence=1.0,
                ),
            ),
        },
    )

    with pytest.raises(IvaCompensationDecimalParseError) as excinfo:
        iva_compensation_state_from_filed_observation(observation)

    assert excinfo.value.translated_message == "errors.refused.refused_iva_compensation_decimal_parse"
    # Modelo 390 reaches this refusal too, so the context names which filing refused
    # and not only the casilla. It must never carry the observed VALUE: the carrier
    # holds the artefact's own token and this context is rendered to the operator.
    assert excinfo.value.context == {
        "casilla_id": _M303_RESULTADO_CASILLA,
        "modelo": "303",
        "filing_year": "2024",
        "period": "4T",
    }
    assert "not-decimal" not in str(excinfo.value.context)


def test_iva_compensation_refuses_a_casilla_whose_declared_kind_is_not_numeric() -> None:
    """A carry-forward balance is never read from a casilla that is not an amount.

    Modelo 303 and Modelo 390 declare only money casillas today, so this cannot
    arise from current registry data. It is asserted because these values carry
    IVA balances between filings: the day a revision adds a text casilla, the
    refusal must already exist rather than a wrong balance moving silently.
    """
    observation = _filed_observation(modelo="303").model_copy(
        update={
            "casillas": (
                ObservedCasillaValue(
                    casilla_id=_M303_RESULTADO_CASILLA,
                    value="15",
                    value_kind=CasillaValueKind.TEXT,
                    source_artefact_kind="submitted_file",
                    source_locator="submitted-file:casilla-69",
                    confidence=1.0,
                ),
            ),
        },
    )

    with pytest.raises(IvaCompensationDecimalParseError) as excinfo:
        iva_compensation_state_from_filed_observation(observation)

    # '15' converts cleanly, so nothing but the declared kind can refuse it.
    assert excinfo.value.context is not None
    assert excinfo.value.context["casilla_id"] == _M303_RESULTADO_CASILLA
    assert "15" not in str(excinfo.value.context["modelo"])


def test_seed_iva_compensation_period_raises_localized_conflict_error(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_CONFLICT_BUCKET_ID):
        seed_iva_compensation_period(
            taxpayer_nif=_TAXPAYER_REF,
            period=Period.from_year_and_code(2024, "2T"),
            amount=Decimal("100.00"),
        )

        with pytest.raises(IvaCompensationSeedConflictError) as excinfo:
            seed_iva_compensation_period(
                taxpayer_nif=_TAXPAYER_REF,
                period=Period.from_year_and_code(2024, "2T"),
                amount=Decimal("50.00"),
            )

        assert excinfo.value.translated_message == "application.calculations.iva_compensation.errors.seed_conflict"
        assert excinfo.value.context == {"filing_year": 2024, "period": "2T", "existing_status": "seeded"}


@pytest.mark.parametrize(
    ("source_artefact_kind", "source_locator"),
    _M303_PRINTED_NUMBER_REFERENCE_CASES,
    ids=("submitted-file", "justificante-pdf"),
)
def test_iva_compensation_state_from_filed_observation_refuses_printed_number_references(
    source_artefact_kind: _M303PrintedNumberSourceKind,
    source_locator: str,
) -> None:
    observation = _filed_observation(modelo="303").model_copy(
        update={
            "casillas": (
                ObservedCasillaValue(
                    casilla_id=_M303_PRINTED_PERIOD_RESULT_REFERENCE_CASILLA,
                    value="-25.00",
                    value_kind=CasillaValueKind.NUMERIC,
                    source_artefact_kind=source_artefact_kind,
                    source_locator=source_locator,
                    confidence=1.0,
                ),
            ),
        },
    )

    with pytest.raises(IvaCompensationCasillaReferenceError) as excinfo:
        iva_compensation_state_from_filed_observation(observation)

    assert excinfo.value.context == {
        "modelo": "303",
        "revision": "2023-y-siguientes",
        "period": "4T",
        "casilla_ids": (_M303_PRINTED_PERIOD_RESULT_REFERENCE_CASILLA,),
    }


def test_iva_compensation_annual_summary_refuses_printed_number_references() -> None:
    observation = _filed_390_observation(
        last_period_compensation=Decimal("100.00"),
        generated_not_in_last_period=Decimal("50.00"),
    ).model_copy(
        update={
            "casillas": (
                ObservedCasillaValue(
                    casilla_id=_M390_PRINTED_LAST_PERIOD_COMPENSATION_REFERENCE_CASILLA,
                    value="100.00",
                    value_kind=CasillaValueKind.NUMERIC,
                    source_artefact_kind="submitted_file",
                    source_locator="submitted-file:390:97",
                    confidence=1.0,
                ),
            ),
        },
    )

    with pytest.raises(IvaCompensationCasillaReferenceError) as excinfo:
        iva_compensation_annual_summary_from_filed_observation(observation)

    assert excinfo.value.context == {
        "modelo": "390",
        "revision": "2010-y-siguientes",
        "period": "0A",
        "casilla_ids": (_M390_PRINTED_LAST_PERIOD_COMPENSATION_REFERENCE_CASILLA,),
    }
