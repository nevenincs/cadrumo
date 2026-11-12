"""The Modelo 202 instalment facts one overview read gathers from the real observation store.

The art. 40.2 base is the cuota of the last periodo impositivo whose declaration
deadline had passed on the first day of the instalment's payment window (LIS
art. 40.2): the Modelo 200 two years back for the April instalment and one year
back for the October and December ones. Only a presented filing decides it: a
local filing or captured AEAT evidence. An operator-entered observation is not a
filing and leaves the base absent.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from .....application.calculations.observations_repository import ObservationSourceKind
from .....application.overview.modelo202_instalment import (
    Modelo202InstalmentFacts,
    decide_modelo_202_instalment,
)
from .....application.overview.modelo202_instalment_evidence import (
    Modelo202InstalmentStores,
    bind_modelo_202_instalment_facts,
)
from .....core.casilla_id import validated_casilla_id
from .....core.period import Period
from .....domain.calculations.registry.applicability_modelo202 import Modelo202BaseBasis, Modelo202InstalmentOutcome
from .....domain.calculations.registry.authority import PinnedAuthorityOperation
from .....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from .....domain.calculations.registry.tests.registry_observations import (
    registry_grounded_modelo_observation,
    revision_id_for_observation,
)
from .....domain.modelos.work_unit import WorkUnitCatalogue
from .....domain.transactions.models import TransactionCatalogue
from ...storage.tests.secure_sql import isolated_runtime_profile
from ..calculation_observations import CalculationObservationRepository
from ..modelos_calculation import CalculationRevisionCatalogueRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_MODELO_200 = "200"
_MODELO_200_ANNUAL = "0A"
_CUOTA_BASE_CASILLA = validated_casilla_id("DP200014B:00599")
_BUCKET_ID = "modelo-202-instalment-facts"


def _year() -> int:
    return filing_year_envelope().horizon


def _save_modelo_200(
    repository: CalculationObservationRepository,
    *,
    filing_year: int,
    cuota: Decimal,
    source_kind: ObservationSourceKind,
) -> None:
    observation = registry_grounded_modelo_observation(
        modelo=_MODELO_200,
        filing_year=filing_year,
        period=_MODELO_200_ANNUAL,
        casilla_values={_CUOTA_BASE_CASILLA: cuota},
    )
    repository.save(
        repository.prepare_observation_envelope(
            observation,
            source_kind=source_kind,
            stamped_revision_id=revision_id_for_observation(observation),
        )
    )


def _read(
    repository: CalculationObservationRepository,
    instalment: Period,
    operation: PinnedAuthorityOperation,
    *,
    activity_start_date: date | None = None,
) -> Modelo202InstalmentFacts:
    stores = Modelo202InstalmentStores(
        bucket_id=_BUCKET_ID,
        observations=repository,
        work_units=WorkUnitCatalogue,
        calculations=CalculationRevisionCatalogueRepository(),
        transactions=TransactionCatalogue,
        activity_start_date=activity_start_date,
        election_for=lambda _instalment: False,
    )
    return bind_modelo_202_instalment_facts(stores, operation=operation)(instalment)


@pytest.mark.parametrize(("token", "years_back"), [("1P", 2), ("2P", 1), ("3P", 1)])
def test_each_instalment_reads_the_last_modelo_200_due_before_its_window(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation, token: str, years_back: int
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path):
        facts = _read(
            CalculationObservationRepository(), Period.from_year_and_code(_year(), token), authority_operation
        )
    assert facts.base_source is not None
    assert facts.base_source.modelo == _MODELO_200
    assert facts.base_source.period == Period.from_year_and_code(_year() - years_back, _MODELO_200_ANNUAL)
    assert facts.base is None
    assert decide_modelo_202_instalment(facts) is Modelo202InstalmentOutcome.BASE_ABSENT


@pytest.mark.parametrize(
    ("source_kind", "basis"),
    [
        (ObservationSourceKind.APP_FILING, Modelo202BaseBasis.LOCAL_FILING),
        (ObservationSourceKind.AEAT_CSV_REGISTER, Modelo202BaseBasis.AEAT_EVIDENCE),
    ],
)
def test_a_presented_modelo_200_decides_the_base_and_names_its_record(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
    source_kind: ObservationSourceKind,
    basis: Modelo202BaseBasis,
) -> None:
    instalment = Period.from_year_and_code(_year(), "2P")
    with isolated_runtime_profile(tmp_path=tmp_path):
        repository = CalculationObservationRepository()
        _save_modelo_200(repository, filing_year=_year() - 1, cuota=Decimal("840.00"), source_kind=source_kind)
        facts = _read(repository, instalment, authority_operation)
    assert facts.base is not None
    assert facts.base.value == Decimal("840.00")
    assert facts.base.basis is basis
    assert decide_modelo_202_instalment(facts) is Modelo202InstalmentOutcome.BASE_POSITIVE


def test_a_zero_cuota_excuses_the_instalment(tmp_path: Path, authority_operation: PinnedAuthorityOperation) -> None:
    instalment = Period.from_year_and_code(_year(), "3P")
    with isolated_runtime_profile(tmp_path=tmp_path):
        repository = CalculationObservationRepository()
        _save_modelo_200(
            repository, filing_year=_year() - 1, cuota=Decimal("0"), source_kind=ObservationSourceKind.APP_FILING
        )
        facts = _read(repository, instalment, authority_operation)
    assert decide_modelo_202_instalment(facts) is Modelo202InstalmentOutcome.BASE_NOT_POSITIVE


def test_an_operator_entered_modelo_200_is_not_a_filing(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation
) -> None:
    instalment = Period.from_year_and_code(_year(), "2P")
    with isolated_runtime_profile(tmp_path=tmp_path):
        repository = CalculationObservationRepository()
        _save_modelo_200(
            repository,
            filing_year=_year() - 1,
            cuota=Decimal("840.00"),
            source_kind=ObservationSourceKind.OPERATOR_MANUAL,
        )
        facts = _read(repository, instalment, authority_operation)
    assert facts.base is None
    assert decide_modelo_202_instalment(facts) is Modelo202InstalmentOutcome.BASE_ABSENT


def test_an_activity_start_after_the_source_period_leaves_no_prior_return(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation
) -> None:
    """The April instalment of the second year reads a periodo impositivo that never existed."""
    second_year = _year()
    with isolated_runtime_profile(tmp_path=tmp_path):
        repository = CalculationObservationRepository()
        first = _read(
            repository,
            Period.from_year_and_code(second_year, "1P"),
            authority_operation,
            activity_start_date=date(second_year - 1, 1, 1),
        )
        second = _read(
            repository,
            Period.from_year_and_code(second_year, "2P"),
            authority_operation,
            activity_start_date=date(second_year - 1, 1, 1),
        )
    assert decide_modelo_202_instalment(first) is Modelo202InstalmentOutcome.NO_PRIOR_RETURN
    assert decide_modelo_202_instalment(second) is Modelo202InstalmentOutcome.BASE_ABSENT
