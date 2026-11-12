"""A local observation refused before it touches the profile is the operator's decision, naming no command.

No catalogued action records a local observation, so each refusal states its
words and the decision stays with the operator. The refusals are raised by the
real owning functions over a real isolated profile.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.buckets import BucketEventHistoryRepository
from cadrumo.adapters.persistence.profile.calculation_observations import CalculationObservationRepository
from cadrumo.adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.cli_exception_preconditions import nested_terminal_precondition_verdict
from cadrumo.application.modelo.action_errors import ModeloLocalObservationError
from cadrumo.application.modelo.local_observation_actions import (
    LocalObservationPorts,
    clear_operator_local_observation,
    record_operator_local_observation,
)
from cadrumo.core.operator_action_enums import NoRecoveryOutcome
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from cadrumo.domain.calculations.registry.form_codes import form_for_role
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_BUCKET_ID = "13000000-0000-4000-8000-0000000000c1"
_YEAR = filing_year_envelope().horizon
_PERIOD = Period.from_year_and_code(_YEAR, "1T")


@pytest.fixture
def operation() -> Iterator[PinnedAuthorityOperation]:
    with bundled_indexed_authority().operation() as pinned:
        yield pinned


@pytest.fixture
def ports(tmp_path: Path) -> Iterator[LocalObservationPorts]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as runtime:
        yield LocalObservationPorts(
            bucket_id=_BUCKET_ID,
            observation_repository=CalculationObservationRepository(),
            bucket_event_repository=BucketEventHistoryRepository(objects=runtime.repository),
            work_unit_repository=WorkUnitCatalogueRepository(objects=runtime.repository),
        )


def _refusal_of(call: Callable[[], object]) -> ModeloLocalObservationError:
    with pytest.raises(ModeloLocalObservationError) as caught:
        call()
    return caught.value


def _assert_operator_decision(error: BaseException) -> None:
    verdict = nested_terminal_precondition_verdict(error)
    assert verdict is not None
    assert verdict.action is None
    assert verdict.no_recovery_outcome is NoRecoveryOutcome.OPERATOR_DECISION


def test_a_blank_actor_is_the_operators_decision(ports: LocalObservationPorts) -> None:
    error = _refusal_of(
        lambda: clear_operator_local_observation("130", _YEAR, _PERIOD, reason="why", actor=" ", ports=ports)
    )

    _assert_operator_decision(error)


def test_a_blank_reason_is_the_operators_decision(ports: LocalObservationPorts) -> None:
    error = _refusal_of(
        lambda: clear_operator_local_observation("130", _YEAR, _PERIOD, reason=" ", actor="operator", ports=ports)
    )

    _assert_operator_decision(error)


def test_a_filing_year_that_is_not_the_periods_is_the_operators_decision(ports: LocalObservationPorts) -> None:
    error = _refusal_of(
        lambda: clear_operator_local_observation("130", _YEAR - 1, _PERIOD, reason="why", actor="operator", ports=ports)
    )

    _assert_operator_decision(error)


def test_clearing_an_override_that_is_not_there_is_the_operators_decision(ports: LocalObservationPorts) -> None:
    error = _refusal_of(
        lambda: clear_operator_local_observation("130", _YEAR, _PERIOD, reason="why", actor="operator", ports=ports)
    )

    _assert_operator_decision(error)


def test_a_modelo_303_observation_is_the_operators_decision(
    operation: PinnedAuthorityOperation, ports: LocalObservationPorts
) -> None:
    error = _refusal_of(
        lambda: record_operator_local_observation(
            modelo=str(form_for_role("iva.periodic")),
            filing_year=_YEAR,
            period=_PERIOD,
            casilla_values={"0001": Decimal(1)},
            reason="why",
            actor="operator",
            ports=ports,
            operation=operation,
        )
    )

    _assert_operator_decision(error)
