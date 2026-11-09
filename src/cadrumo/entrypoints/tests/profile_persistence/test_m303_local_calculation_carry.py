"""A calculated, unfiled prior Modelo 303 feeds the next quarter at calculation grade.

The carried amount is the prior revision's ``iva.compensacion-disponible-fin-periodo``.
A negative prior result carries in full only where the law leaves compensation as its
one disposition: LIVA art. 115.Uno allows no refund before the last period of the year
for a taxpayer outside REDEME (RIVA art. 30). Where a refund is allowed, or REDEME is
unstated, the carry refuses with the reason. The carry is never wallet or filed
evidence, so it reaches calculation grade only.

The quarterly figures follow one synthetic year: 21 % output cuotas of 1260, 840, 210
and 1260 against 535.50 input cuota each quarter, which leaves 724.50, 304.50, -325.50
and, after the 3T credit, 399.00.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.calculation_observations import (
    CalculationObservationRepository,
    IvaWalletDecisionRepository,
)
from cadrumo.adapters.persistence.profile.iva_compensation_history import IvaCompensationHistoryRepository
from cadrumo.application.calculations.tests.filing_evidence import general_m303_filing_evidence
from cadrumo.application.modelo.calculation_bucket_actions import (
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
)
from cadrumo.application.modelo.iva_wallet_gate import (
    ModeloIvaWalletReconciliationBlocked,
    require_persisted_iva_compensation_decision_matches_revision,
)
from cadrumo.application.operations.next_step import OperationOpenIvaWalletStepV1
from cadrumo.application.user_profile.tests.persona_profile_facts import persona_facts_beneath
from cadrumo.core.external_constants import PROVENANCE_SOURCE_MANUAL_CLI, OutputLanguage
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.calculations.registry.tests.published_authority import published_supported_filing_years
from cadrumo.domain.modelos.calculation_revision import CalculationRevision
from cadrumo.domain.modelos.work_unit import WorkUnit
from cadrumo.domain.user_profile.tests.profile_creation_authority import profile_creation_context_for_test
from cadrumo.entrypoints.tests.profile_persistence.file_flow_test_support import calculation_ports_for_test
from cadrumo.entrypoints.tests.profile_persistence.iva_wallet_engine_support import (
    BUCKET_ID,
    M303_COMPENSACION_PENDIENTE_ANTERIORES_CASILLA,
    M303_DISPONIBLE_CASILLA,
    M303_RESULTADO_CASILLA,
    create_modelo_303_work_unit,
    period,
    secure_backend,
    snapshot_303,
    work_unit_repositories,
)
from cadrumo.entrypoints.tests.profile_persistence.m303_annual_ledger_support import seed_m303_period_cuotas

from ....adapters.persistence.storage.tests.profile_capsule_runtime import seed_test_profile_record
from ....domain.deadlines.errors import ProfileError
from ....domain.deadlines.models import IVARegime
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, create_user_profile_record

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("authority_operation")]

_SUPPORT = published_supported_filing_years()
assert _SUPPORT is not None, "the published authority declares no supported filing years"
SUPPORTED_YEARS = tuple(_SUPPORT.years)

_SOPORTADO = Decimal("535.50")
_REPERCUTIDO = {"1T": Decimal("1260.00"), "2T": Decimal("840.00"), "3T": Decimal("210.00"), "4T": Decimal("1260.00")}
_QUARTER_END = {"1T": (3, 31), "2T": (6, 30), "3T": (9, 30), "4T": (12, 31)}
_TAXPAYER_NIF = "X0001500M"


def _store_profile(filing_year: int, *, without: tuple[str, ...] = (), activity_start: date | None = None) -> None:
    stamped = datetime(filing_year, 1, 2, 9, 0, tzinfo=UTC)
    seed_test_profile_record(
        create_user_profile_record(
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=BUCKET_ID,
            facts=persona_facts_beneath(
                (
                    UserProfileFact(path="identity.tax_id", value=_TAXPAYER_NIF),
                    UserProfileFact(path="identity.name", value="Test"),
                    UserProfileFact(path="identity.surnames", value="Operator"),
                    UserProfileFact(
                        path="censo.activity_start_date",
                        value=(activity_start or date(filing_year, 1, 1)).isoformat(),
                    ),
                    UserProfileFact(path="activities.description", value="economic activity"),
                    UserProfileFact(path="iva.regime", value=IVARegime("GENERAL")),
                    UserProfileFact(path="provenance.source", value=PROVENANCE_SOURCE_MANUAL_CLI),
                ),
                without=without,
            ),
            created_at=stamped,
            updated_at=stamped,
            context=profile_creation_context_for_test(),
        ),
    )


class _Quarters:
    """Calculate one taxpayer's quarters in order against one set of repositories."""

    def __init__(self, *, operation: PinnedAuthorityOperation) -> None:
        self._operation = operation
        self._repositories = work_unit_repositories()
        self._work_units: dict[tuple[int, str], WorkUnit] = {}
        self._recalculations = 0

    def work_unit(self, filing_year: int, quarter: str) -> WorkUnit:
        return self._work_units[filing_year, quarter]

    def calculate(
        self, filing_year: int, quarter: str, *, repercutido: Decimal, soportado: Decimal
    ) -> CalculationRevision:
        """Calculate ``quarter``, recording its cuotas where the ledger does not hold them yet."""
        work_repo, calc_repo, event_repo = self._repositories
        month, day = _QUARTER_END[quarter]
        quarter_end = date(filing_year, month, day)
        clock = datetime(filing_year, month, day, 18, 0, tzinfo=UTC)
        work_unit = self._work_units.get((filing_year, quarter))
        if work_unit is None:
            work_unit = create_modelo_303_work_unit(
                snapshot_303(filing_year=filing_year, period=quarter),
                work_unit_repository=work_repo,
                clock=clock,
                operation=self._operation,
            )
            self._work_units[filing_year, quarter] = work_unit
        else:
            self._recalculations += 1
            clock += timedelta(minutes=self._recalculations)
        with calculation_ports_for_test(
            bucket_id=work_unit.bucket_id,
            work_unit_repository=work_repo,
            calculation_repository=calc_repo,
            bucket_event_repository=event_repo,
        ) as ports:
            seed_m303_period_cuotas(work_unit.work_unit_id, repercutido=repercutido, soportado=soportado)
            return calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
                work_unit.work_unit_id,
                actor="operator",
                casilla_inputs={},
                binding_values={"modelo-303-profile-state-attribution-ratio": Decimal("100")},
                iva_compensation_decision=None,
                filing_period_date=quarter_end,
                ports=ports,
                clock=clock,
                filing_instance_evidence=general_m303_filing_evidence(
                    work_unit.period, reference="test:m303-local-calculation-carry", operation=self._operation
                ),
            ).revision


@pytest.mark.parametrize("filing_year", SUPPORTED_YEARS)
def test_a_calculated_prior_quarter_feeds_the_next_at_calculation_grade(
    tmp_path: Path, filing_year: int, *, operation: PinnedAuthorityOperation
) -> None:
    with secure_backend(tmp_path):
        _store_profile(filing_year)
        quarters = _Quarters(operation=operation)
        revisions = {
            quarter: quarters.calculate(filing_year, quarter, repercutido=_REPERCUTIDO[quarter], soportado=_SOPORTADO)
            for quarter in ("1T", "2T", "3T", "4T")
        }
        decision_4t = IvaWalletDecisionRepository().load_decision(_TAXPAYER_NIF, period(filing_year, "4T"))

    expected_result = {"1T": "724.50", "2T": "304.50", "3T": "-325.50", "4T": "399.00"}
    expected_carry_in = {"1T": "0", "2T": "0", "3T": "0", "4T": "325.50"}
    for quarter, revision in revisions.items():
        assert revision.casilla_values[M303_RESULTADO_CASILLA] == Decimal(expected_result[quarter]), quarter
        assert revision.casilla_values[M303_COMPENSACION_PENDIENTE_ANTERIORES_CASILLA] == Decimal(
            expected_carry_in[quarter]
        ), quarter
    assert revisions["3T"].casilla_values[M303_DISPONIBLE_CASILLA] == Decimal("325.50")

    assert decision_4t is not None
    assert decision_4t.selected_authority == "local_calculation"
    assert decision_4t.blocked is False
    assert decision_4t.selected_amount == Decimal("325.50")
    assert any(
        source.source_locator == f"calculation-revision:303:{filing_year}:3T:{revisions['3T'].calculation_revision_id}"
        for source in decision_4t.authority_sources
    )


def test_an_unstated_redeme_inscription_refuses_before_any_carry_is_read(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    # Whether a credit may be carried rests on the REDEME inscription (LIVA
    # art. 115.Dos), so the Modelo 303 readiness gate asks for it before the
    # first quarter is calculated: no carry is ever read on an unstated answer.
    filing_year = SUPPORTED_YEARS[0]
    with secure_backend(tmp_path):
        _store_profile(filing_year, without=("iva.redeme_enrolled",))
        quarters = _Quarters(operation=operation)
        with pytest.raises(ProfileError, match=r"iva\.redeme_enrolled"):
            quarters.calculate(filing_year, "1T", repercutido=Decimal("210.00"), soportado=_SOPORTADO)


def test_a_negative_last_quarter_refuses_because_a_refund_is_allowed(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    # The last period of the year may be refunded (LIVA art. 115.Uno), so the
    # taxpayer's choice, not the calculation, decides what reaches January.
    filing_year = next(year for year in SUPPORTED_YEARS if year + 1 in SUPPORTED_YEARS)
    with secure_backend(tmp_path):
        # Activity starts in October, so the fourth quarter is the first.
        _store_profile(filing_year, activity_start=date(filing_year, 10, 1))
        quarters = _Quarters(operation=operation)
        quarters.calculate(filing_year, "4T", repercutido=Decimal("210.00"), soportado=_SOPORTADO)
        with pytest.raises(ModeloIvaWalletReconciliationBlocked, match="local_calculation_refund_undecided"):
            quarters.calculate(filing_year + 1, "1T", repercutido=Decimal("840.00"), soportado=_SOPORTADO)


def test_a_positive_prior_quarter_carries_nothing(tmp_path: Path, *, operation: PinnedAuthorityOperation) -> None:
    filing_year = SUPPORTED_YEARS[-1]
    with secure_backend(tmp_path):
        _store_profile(filing_year)
        quarters = _Quarters(operation=operation)
        quarters.calculate(filing_year, "1T", repercutido=_REPERCUTIDO["1T"], soportado=_SOPORTADO)
        revision_2t = quarters.calculate(filing_year, "2T", repercutido=_REPERCUTIDO["2T"], soportado=_SOPORTADO)
        decision = IvaWalletDecisionRepository().load_decision(_TAXPAYER_NIF, period(filing_year, "2T"))

    assert revision_2t.casilla_values[M303_COMPENSACION_PENDIENTE_ANTERIORES_CASILLA] == Decimal("0")
    assert decision is not None
    assert decision.selected_authority == "local_calculation"
    assert decision.selected_amount == Decimal("0")


def test_checking_a_quarter_carried_from_a_calculation_refuses_with_the_iva_balance_door(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    # Checking, filing and exporting need the wallet, the filed return or the
    # amount it declared; the taxpayer's own calculation of 3T is none of them.
    filing_year = SUPPORTED_YEARS[-1]
    with secure_backend(tmp_path):
        _store_profile(filing_year)
        quarters = _Quarters(operation=operation)
        for quarter in ("1T", "2T", "3T"):
            quarters.calculate(filing_year, quarter, repercutido=_REPERCUTIDO[quarter], soportado=_SOPORTADO)
        revision_4t = quarters.calculate(filing_year, "4T", repercutido=_REPERCUTIDO["4T"], soportado=_SOPORTADO)
        with pytest.raises(ModeloIvaWalletReconciliationBlocked, match="local_calculation_only") as refused:
            require_persisted_iva_compensation_decision_matches_revision(
                quarters.work_unit(filing_year, "4T"),
                revision_4t,
                repository=IvaWalletDecisionRepository(),
                observation_repository=CalculationObservationRepository(),
                history_repository=IvaCompensationHistoryRepository(),
                operation=operation,
                subject_leaf_key="modelo.work.verify",
            )
        kept = IvaWalletDecisionRepository().load_decision(_TAXPAYER_NIF, period(filing_year, "4T"))

    step = refused.value.operation_next_step(OutputLanguage.ES)
    assert isinstance(step, OperationOpenIvaWalletStepV1)
    assert step.work_unit_id == quarters.work_unit(filing_year, "4T").work_unit_id
    assert kept is not None
    assert kept.selected_authority == "local_calculation"
    assert kept.selected_amount == Decimal("325.50")


def test_recalculating_the_prior_quarter_refreshes_the_carry(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    filing_year = SUPPORTED_YEARS[-1]
    with secure_backend(tmp_path):
        _store_profile(filing_year)
        quarters = _Quarters(operation=operation)
        for quarter in ("1T", "2T"):
            quarters.calculate(filing_year, quarter, repercutido=_REPERCUTIDO[quarter], soportado=_SOPORTADO)
        # 3T first holds only its purchase, so it leaves the whole 535.50 input cuota.
        quarters.calculate(filing_year, "3T", repercutido=Decimal("0"), soportado=_SOPORTADO)
        first_4t = quarters.calculate(filing_year, "4T", repercutido=_REPERCUTIDO["4T"], soportado=_SOPORTADO)
        # The 3T sale is then recorded and 3T recalculated, leaving 325.50.
        quarters.calculate(filing_year, "3T", repercutido=_REPERCUTIDO["3T"], soportado=_SOPORTADO)
        second_4t = quarters.calculate(filing_year, "4T", repercutido=_REPERCUTIDO["4T"], soportado=_SOPORTADO)
        decision = IvaWalletDecisionRepository().load_decision(_TAXPAYER_NIF, period(filing_year, "4T"))

    assert first_4t.casilla_values[M303_COMPENSACION_PENDIENTE_ANTERIORES_CASILLA] == Decimal("535.50")
    assert second_4t.casilla_values[M303_COMPENSACION_PENDIENTE_ANTERIORES_CASILLA] == Decimal("325.50")
    assert second_4t.casilla_values[M303_RESULTADO_CASILLA] == Decimal("399.00")
    assert decision is not None
    assert decision.selected_amount == Decimal("325.50")
