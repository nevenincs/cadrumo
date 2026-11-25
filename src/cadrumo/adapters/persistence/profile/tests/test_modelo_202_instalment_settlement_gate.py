"""A Modelo 200 settles the year's Modelo 202 instalments: filed, not owed, or still open.

Below the LIS art. 40.3 threshold a Modelo 202 is presented only in an instalment
where an ingreso results (Orden HFP/227/2017 art. 1.3). The October and December
instalments read the cuota of the Modelo 200 one year back (LIS art. 40.2), so
when that cuota was 0.00 no ingreso resulted, no Modelo 202 was presented, and
the settlement credits nothing for them: a proven zero, not an absent filing. An
instalment whose own verdict is undecided or owed, or whose modality says every
instalment is owed, still blocks the settlement. Every case runs the real
observation store, the real instalment verdict and the real clean-state gate.
"""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal
from pathlib import Path

import pytest

from .....application.calculations.cross_period_clean_state import evaluate_cross_period_clean_state
from .....application.calculations.cross_period_models import (
    CrossPeriodCleanStateVerdict,
    CrossPeriodDependencyEvidence,
)
from .....application.calculations.modelo_202_instalment_resolution import (
    Modelo202InstalmentResolutionKind,
    Modelo202InstalmentUnresolvedReason,
)
from .....application.calculations.observations_repository import ObservationSourceKind
from .....application.overview.modelo202_instalment_evidence import (
    Modelo202InstalmentStores,
    bind_modelo_202_instalment_resolver,
)
from .....core.authority_grade import RegistryAuthorityGrade
from .....core.casilla_id import CasillaId, validated_casilla_id
from .....core.period import Period
from .....domain.calculations.registry.applicability_modelo202 import (
    Modelo202BaseBasis,
    Modelo202InstalmentOutcome,
    Modelo202Modality,
)
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
from ..justificante import JustificanteRepository
from ..modelos_calculation import CalculationRevisionCatalogueRepository
from ..modelos_filing import ModeloRecordCatalogueRepository
from ..modelos_verification_reports import VerificationReportCatalogueRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_MODELO_200 = "200"
_MODELO_202 = "202"
_ANNUAL = "0A"
_CUOTA_BASE_CASILLA = validated_casilla_id("DP200014B:00599")
_CUOTA_INSTALMENT_CASILLA: CasillaId = validated_casilla_id("03")
_LATER_INSTALMENTS = ("2P", "3P")


def _ejercicio() -> int:
    """The settled ejercicio: the one before the horizon, whose Modelo 200 is filed in the horizon."""
    return filing_year_envelope().horizon - 1


def _save(
    repository: CalculationObservationRepository,
    *,
    modelo: str,
    filing_year: int,
    period: str,
    casilla_values: dict[CasillaId, Decimal],
) -> None:
    observation = registry_grounded_modelo_observation(
        modelo=modelo,
        filing_year=filing_year,
        period=period,
        casilla_values=casilla_values,
        grade=RegistryAuthorityGrade.CALCULATION,
    )
    repository.save(
        repository.prepare_observation_envelope(
            observation,
            source_kind=ObservationSourceKind.APP_FILING,
            stamped_revision_id=revision_id_for_observation(observation),
        )
    )


def _file_april_instalment(repository: CalculationObservationRepository) -> None:
    """The April instalment, 18 % of a 300.00 cuota, presented locally at 54.00."""
    _save(
        repository,
        modelo=_MODELO_202,
        filing_year=_ejercicio(),
        period="1P",
        casilla_values={_CUOTA_INSTALMENT_CASILLA: Decimal("54.00")},
    )


def _file_previous_modelo_200(repository: CalculationObservationRepository, cuota: Decimal) -> None:
    """The Modelo 200 one year back, whose cuota is the October and December base."""
    _save(
        repository,
        modelo=_MODELO_200,
        filing_year=_ejercicio() - 1,
        period=_ANNUAL,
        casilla_values={_CUOTA_BASE_CASILLA: cuota},
    )


def _evaluate(
    repository: CalculationObservationRepository,
    operation: PinnedAuthorityOperation,
    *,
    bucket_id: str,
    modality: Modelo202Modality | None = Modelo202Modality.ART_40_2_OPTIONAL,
    election_for: Callable[[Period], bool | None] = lambda _instalment: False,
) -> CrossPeriodCleanStateVerdict:
    calculations = CalculationRevisionCatalogueRepository()
    resolver = bind_modelo_202_instalment_resolver(
        Modelo202InstalmentStores(
            bucket_id=bucket_id,
            observations=repository,
            work_units=WorkUnitCatalogue,
            calculations=calculations,
            transactions=TransactionCatalogue,
            activity_start_date=None,
            election_for=election_for,
        ),
        modality=modality,
        operation=operation,
    )
    snapshot = operation.snapshot(
        _MODELO_200, filing_year=_ejercicio(), period=_ANNUAL, grade=RegistryAuthorityGrade.CALCULATION
    )
    return evaluate_cross_period_clean_state(
        snapshot,
        operation=operation,
        bucket_id=bucket_id,
        observation_repository=repository,
        filing_repository=ModeloRecordCatalogueRepository(),
        calculation_repository=calculations,
        verification_repository=VerificationReportCatalogueRepository(),
        justificante_repository=JustificanteRepository(),
        modelo_202_modality=modality,
        modelo_202_instalment_resolver=resolver,
    )


def _instalment_rows(verdict: CrossPeriodCleanStateVerdict, token: str) -> tuple[CrossPeriodDependencyEvidence, ...]:
    rows = tuple(
        item
        for item in verdict.dependencies
        if item.requirement.source_modelo == _MODELO_202 and item.requirement.period.registry_token == token
    )
    assert rows, f"the Modelo 200 reads no Modelo 202 {token}"
    return rows


def test_unowed_instalments_settle_at_zero_beside_the_filed_one(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        repository = CalculationObservationRepository()
        _file_april_instalment(repository)
        _file_previous_modelo_200(repository, Decimal("0.00"))
        verdict = _evaluate(repository, authority_operation, bucket_id=profile.bucket_id)

    # The presented April instalment follows its filing, never the not-owed path.
    for row in _instalment_rows(verdict, "1P"):
        assert row.modelo_202_instalment_not_owed is None
        assert row.observation_source_kind is ObservationSourceKind.APP_FILING
    for token in _LATER_INSTALMENTS:
        for row in _instalment_rows(verdict, token):
            assert row.clean
            provenance = row.modelo_202_instalment_not_owed
            assert provenance is not None
            assert provenance.grounds.outcome is Modelo202InstalmentOutcome.BASE_NOT_POSITIVE
            assert provenance.grounds.reason
            assert provenance.base_value == Decimal("0.00")
            assert provenance.base_basis is Modelo202BaseBasis.LOCAL_FILING
            assert provenance.base_source_period == Period.from_year_and_code(_ejercicio() - 1, _ANNUAL)
    assert not [
        item
        for item in verdict.dependencies
        if item.requirement.source_modelo == _MODELO_202
        and item.requirement.period.registry_token in _LATER_INSTALMENTS
        and not item.clean
    ]


def test_the_resolution_reads_filed_and_not_owed_amounts(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        repository = CalculationObservationRepository()
        _file_april_instalment(repository)
        _file_previous_modelo_200(repository, Decimal("0.00"))
        resolve = bind_modelo_202_instalment_resolver(
            Modelo202InstalmentStores(
                bucket_id=profile.bucket_id,
                observations=repository,
                work_units=WorkUnitCatalogue,
                calculations=CalculationRevisionCatalogueRepository(),
                transactions=TransactionCatalogue,
                activity_start_date=None,
                election_for=lambda _instalment: False,
            ),
            modality=Modelo202Modality.ART_40_2_OPTIONAL,
            operation=authority_operation,
        )
        resolutions = {
            token: resolve(Period.from_year_and_code(_ejercicio(), token)) for token in ("1P", *_LATER_INSTALMENTS)
        }

    assert resolutions["1P"].kind is Modelo202InstalmentResolutionKind.FILED
    assert resolutions["1P"].amount == Decimal("54.00")
    assert sum((resolutions[token].amount or Decimal(0) for token in resolutions), Decimal(0)) == Decimal("54.00")
    for token in _LATER_INSTALMENTS:
        assert resolutions[token].kind is Modelo202InstalmentResolutionKind.NOT_OWED
        assert resolutions[token].amount == Decimal("0.00")


@pytest.mark.parametrize(
    ("previous_cuota", "modality", "election", "reason"),
    [
        pytest.param(None, Modelo202Modality.ART_40_2_OPTIONAL, False, "verdict_undecided", id="base-never-held"),
        pytest.param(
            Decimal("0.00"), Modelo202Modality.ART_40_2_OPTIONAL, None, "verdict_undecided", id="election-unstated"
        ),
        pytest.param(Decimal("0.00"), None, False, "verdict_undecided", id="modality-unknown"),
        pytest.param(Decimal("500.00"), Modelo202Modality.ART_40_2_OPTIONAL, False, "owed_unfiled", id="base-positive"),
        pytest.param(
            Decimal("0.00"), Modelo202Modality.ART_40_3_MANDATORY, False, "owed_unfiled", id="above-threshold"
        ),
    ],
)
def test_an_unfiled_instalment_not_shown_unowed_still_blocks(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
    previous_cuota: Decimal | None,
    modality: Modelo202Modality | None,
    election: bool | None,
    reason: str,
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        repository = CalculationObservationRepository()
        _file_april_instalment(repository)
        if previous_cuota is not None:
            _file_previous_modelo_200(repository, previous_cuota)
        verdict = _evaluate(
            repository,
            authority_operation,
            bucket_id=profile.bucket_id,
            modality=modality,
            election_for=lambda _i: election,
        )
        resolve = bind_modelo_202_instalment_resolver(
            Modelo202InstalmentStores(
                bucket_id=profile.bucket_id,
                observations=repository,
                work_units=WorkUnitCatalogue,
                calculations=CalculationRevisionCatalogueRepository(),
                transactions=TransactionCatalogue,
                activity_start_date=None,
                election_for=lambda _i: election,
            ),
            modality=modality,
            operation=authority_operation,
        )
        resolution = resolve(Period.from_year_and_code(_ejercicio(), "2P"))

    assert resolution.kind is Modelo202InstalmentResolutionKind.UNRESOLVED
    assert resolution.unresolved_reason is Modelo202InstalmentUnresolvedReason(reason)
    for token in _LATER_INSTALMENTS:
        for row in _instalment_rows(verdict, token):
            assert row.modelo_202_instalment_not_owed is None
            assert not row.clean
    for row in _instalment_rows(verdict, "1P"):
        assert row.modelo_202_instalment_not_owed is None
