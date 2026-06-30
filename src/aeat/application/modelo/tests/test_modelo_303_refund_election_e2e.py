"""E2E: the non-REDEME last-period refund opt-in election (LIVA art. 116).

Task 3 / single-disposition-fact extension: a taxpayer NOT inscribed in the
Registro de devolución mensual (REDEME) may, in the LAST filing period of the
year (the annual liquidación), elect to request a negative Modelo 303 result back
as a refund (devolución, Tipo de declaración ``D``) instead of carrying the credit
forward (compensación, ``C``). The election defaults OFF (``COMPENSAR``); it is
honoured only in an eligible period and refused otherwise — never silently carried,
never silently refunded.

The election flows through the ONE shared disposition resolver
(``resolve_modelo_result_disposition``) that both the export fichero "Tipo de
declaración" and the cross-period carry persistence read, so a refunded
last-period filing requests the credit back AND carries ZERO into the next period.

Real-behaviour, real-adapter: real encrypted-SQLite secure store via
``isolated_runtime_profile``, the real registry authority, the real calculation
engine, the real wallet reconciliation, the real verify + workflow + cross-period
clean-state gates, the real ``relation_prefill`` carry resolver, and the real
``file_modelo_revision`` filing path. No mocks, stubs, skips, or xfail.

Non-tautological: the period's negative ``iva.resultado`` and its generated
compensación saldo are produced by the REAL engine from a credit scenario
(soportado > repercutido), never hand-computed against the formula. The disposition
is read from the REAL ``resolve_modelo_result_disposition`` against the REAL filed
revision (never asserted by passing ``refunded=True``); the zero-carry is the
structural refund invariant; the control asserts the carried value equals the SAME
engine-produced saldo. Legal basis: Ley 37/1992 (LIVA) art. 116.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import SecretStr

from ....core import Period, RefundElection, ResultDisposition
from ....core.config import AuthProviderKindSetting, Settings
from ....core.resources import resources
from ....domain.buckets import BucketEventHistoryRepository
from ....domain.calculations.registry import CasillaId, RelationId, validated_casilla_id
from ....domain.deadlines import IVARegime, ModeloIVAProfile, TaxpayerProfile
from ....domain.modelos._calculation_repository import CalculationRevisionCatalogueRepository
from ....domain.modelos._filing_repository import ModeloRecordCatalogueRepository
from ....domain.modelos._repository import WorkUnitCatalogueRepository
from ....domain.user_profile import UserProfileFact, UserProfileRecord
from ....tests.secure_sql import isolated_runtime_profile
from ...calculations import CalculationObservationRepository, reconcile_modelo_303_iva_compensation
from ...calculations._relation_prefill import resolve_relations_from_local_store
from ...user_profile import UserProfileLifecycleRepository
from .. import (
    ModeloRefundElectionNotEligibleError,
    calculate_modelo_revision,
    create_work_unit,
    file_modelo_revision,
    verify_modelo_revision,
)
from .._result_disposition_resolution import resolve_modelo_result_disposition

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_TAX_ID = "X1234567L"
_YEAR = 2025
_LAST_PERIOD = "4T"
_MID_PERIOD = "2T"

#: The carry chain casilla/relation: the prior period's end-of-period available
#: compensación flows into the next period's casilla 110.
_CARRY_RELATION: RelationId = "modelo-303-rel-self-compensacion-anteriores"


def _casilla_id(value: object) -> CasillaId:
    try:
        return validated_casilla_id(value, surface="test casilla id")
    except ValueError as exc:
        raise AssertionError(f"M303 refund election fixture casilla key {value!r} is not a CasillaId") from exc


_M303_RESULTADO_CASILLA: CasillaId = _casilla_id("iva.resultado")
_SALDO_CASILLA: CasillaId = _casilla_id("iva.compensacion-disponible-fin-periodo")

#: A negative-result M303 credit scenario: cuota soportada (interiores) exceeds
#: cuota repercutida, so the régimen-general result is negative — the IVA credit
#: that is refunded (election) or carried (compensar).
_NEGATIVE_CREDIT_ENGINE_INPUTS = {
    "modelo-303-iva-repercutido-general-cuota": Decimal("0.00"),
    "modelo-303-iva-repercutido-reducido-cuota": Decimal("0.00"),
    "modelo-303-iva-repercutido-super-reducido-cuota": Decimal("0.00"),
    "modelo-303-iva-soportado-interiores-cuota": Decimal("1000.00"),
    "modelo-303-iva-autorepercutido-intracomunitaria-cuota": Decimal("0.00"),
    "modelo-303-profile-state-attribution-ratio": Decimal("100"),
}


@contextmanager
def _secure_backend(tmp_path: Path) -> Iterator[None]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="operator"):
        yield


def _store_operator_profile(*, created_at: datetime) -> None:
    activity_start_date = _activity_start_date_for_period(_LAST_PERIOD if created_at.month == 12 else _MID_PERIOD)
    UserProfileLifecycleRepository(bucket_id="operator").save(
        UserProfileRecord(
            profile_id="11111111-1111-4111-8111-111111111111",
            display_name="Test runtime profile",
            facts=(
                UserProfileFact(path="identity.tax_id", value=_TAX_ID),
                UserProfileFact(path="identity.name", value="Test"),
                UserProfileFact(path="identity.surnames", value="Operator"),
                UserProfileFact(path="activities.description", value="economic activity"),
                UserProfileFact(path="tax_residence.ccaa", value="madrid"),
                UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
                UserProfileFact(path="iva.regime", value="GENERAL"),
                UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
                UserProfileFact(path="taxpayer_type.irpf_income_categories", value="actividad_economica"),
                UserProfileFact(path="irpf.estimation_regime", value="directa_normal"),
                UserProfileFact(path="censo.activity_start_date", value=activity_start_date),
            ),
            created_at=created_at,
            updated_at=created_at,
        ),
    )


def _activity_start_date_for_period(period_token: str) -> date:
    return date(_YEAR, 10, 1) if period_token == _LAST_PERIOD else date(_YEAR, 4, 1)


def _workflow_profile(*, redeme_enrolled: bool, activity_start_date: date) -> TaxpayerProfile:
    return TaxpayerProfile(
        tax_id=_TAX_ID,
        iva_regime=IVARegime.GENERAL,
        has_employees=False,
        pays_rent_with_retencion=False,
        does_intracomunitario=False,
        bienes_extranjero_above_threshold=False,
        activity_start_date=activity_start_date,
        iva=ModeloIVAProfile(redeme_enrolled=redeme_enrolled),
    )


def _period_end(period_code: str) -> date:
    return date(_YEAR, 12, 31) if period_code == "4T" else date(_YEAR, 6, 30)


def _decision_clock(period_code: str) -> datetime:
    return (
        datetime(_YEAR, 12, 19, 12, 0, 0, tzinfo=UTC)
        if period_code == "4T"
        else datetime(_YEAR, 6, 19, 12, 0, 0, tzinfo=UTC)
    )


def _verify_clock(period_code: str) -> datetime:
    return (
        datetime(_YEAR + 1, 1, 20, 9, 0, 0, tzinfo=UTC)
        if period_code == "4T"
        else datetime(_YEAR, 7, 20, 9, 0, 0, tzinfo=UTC)
    )


def _file_clock(period: Period) -> datetime:
    return (
        datetime(period.filing_year + 1, 1, 20, 10, 0, 0, tzinfo=UTC)
        if period.code == "4T"
        else datetime(period.filing_year, 7, 20, 10, 0, 0, tzinfo=UTC)
    )


def _calculate_negative_period(
    *,
    period_token: str,
    redeme_enrolled: bool,
) -> tuple[str, Decimal]:
    """Calculate + verify a negative-credit M303 period; return (revision_id, saldo).

    Drives the REAL first-period wallet reconciliation, calculate and verify path.
    Returns the verified-complete revision id (ready to file) and the engine-produced
    ``iva.compensacion-disponible-fin-periodo`` saldo (read back from the revision,
    never hand-derived from the formula — anti-tautology).
    """
    decided_at = _decision_clock(period_token)
    verified_at = _verify_clock(period_token)
    _store_operator_profile(created_at=decided_at)
    work_repo = WorkUnitCatalogueRepository()
    calc_repo = CalculationRevisionCatalogueRepository()
    filing_repo = ModeloRecordCatalogueRepository()
    event_repo = BucketEventHistoryRepository()

    snapshot = resources().modelos.authority.snapshot("303", filing_year=_YEAR, period=period_token)
    report = reconcile_modelo_303_iva_compensation(
        snapshot,
        taxpayer_nif=_TAX_ID,
        wallet=None,
        repository=CalculationObservationRepository(),
        decided_at=decided_at,
        treat_absent_recurrence_as_first_period=True,
    )
    assert report.decision.divergence == "first_period_zero"

    work_unit = create_work_unit(
        bucket_id="operator",
        modelo="303",
        filing_year=_YEAR,
        period=Period.from_year_and_code(_YEAR, period_token),
        revision_id=snapshot.revision.id,
        repository=work_repo,
        clock=decided_at,
    )
    revision = calculate_modelo_revision(
        work_unit.work_unit_id,
        actor="operator",
        casilla_inputs={},
        binding_values={"modelo-303-profile-state-attribution-ratio": Decimal("100")},
        backend_binding_values=_NEGATIVE_CREDIT_ENGINE_INPUTS,
        iva_compensation_decision=report.decision,
        filing_period_date=_period_end(period_token),
        work_unit_repository=work_repo,
        calculation_repository=calc_repo,
        bucket_event_repository=event_repo,
        clock=decided_at,
    )
    assert revision.casilla_values[_M303_RESULTADO_CASILLA] < Decimal("0")
    saldo = revision.casilla_values[_SALDO_CASILLA]
    assert saldo > Decimal("0")

    verification = verify_modelo_revision(
        revision.calculation_revision_id,
        actor="operator",
        workflow_profile=_workflow_profile(
            redeme_enrolled=redeme_enrolled,
            activity_start_date=_activity_start_date_for_period(period_token),
        ),
        work_unit_repository=work_repo,
        calculation_repository=calc_repo,
        filing_repository=filing_repo,
        bucket_event_repository=event_repo,
        clock=verified_at,
    )
    assert verification.granted_verificado_completo is True
    return revision.calculation_revision_id, saldo


def _file_period(
    *,
    calculation_revision_id: str,
    redeme_enrolled: bool,
    refund_election: RefundElection,
) -> ResultDisposition:
    """File the verified revision under ``refund_election`` and return its resolved disposition.

    The filing path determines the devolución/compensación disposition itself from
    the same shared resolver — NO ``refunded`` flag is passed. The disposition is
    then read back from the REAL resolver against the REAL filed work unit/revision.
    """
    work_repo = WorkUnitCatalogueRepository()
    calc_repo = CalculationRevisionCatalogueRepository()
    filing_repo = ModeloRecordCatalogueRepository()
    event_repo = BucketEventHistoryRepository()
    revision = calc_repo.load().get(calculation_revision_id)
    assert revision is not None
    work_unit = work_repo.load().get(revision.work_unit_id)
    assert work_unit is not None

    file_modelo_revision(
        calculation_revision_id,
        actor="operator",
        workflow_profile=_workflow_profile(
            redeme_enrolled=redeme_enrolled,
            activity_start_date=_activity_start_date_for_period(work_unit.period.code),
        ),
        refund_election=refund_election,
        work_unit_repository=work_repo,
        calculation_repository=calc_repo,
        filing_repository=filing_repo,
        bucket_event_repository=event_repo,
        settings=Settings(
            aeat_auth_provider=AuthProviderKindSetting.CLAVE_MOVIL,
            aeat_clave_movil_dni_nie=SecretStr(_TAX_ID),
        ),
        clock=_file_clock(work_unit.period),
    )

    return resolve_modelo_result_disposition(
        work_unit=work_unit,
        revision=revision,
        workflow_profile=_workflow_profile(
            redeme_enrolled=redeme_enrolled,
            activity_start_date=_activity_start_date_for_period(work_unit.period.code),
        ),
        period=work_unit.period,
        refund_election=refund_election,
    )


def _next_period_carry_in(*, next_year: int, next_period: str) -> Decimal | None:
    """Resolve the next period's casilla-110 carry-in from whatever carry the filing persisted."""
    snapshot_next = resources().modelos.authority.snapshot("303", filing_year=next_year, period=next_period)
    relation_values = resolve_relations_from_local_store(
        snapshot_next,
        repository=CalculationObservationRepository(),
    )
    resolved: dict[RelationId, Decimal] = {
        item.relation: item.value for item in relation_values.values if item.value is not None
    }
    return resolved.get(_CARRY_RELATION)


def test_non_redeme_last_period_refund_election_yields_devolucion_and_zero_carry(tmp_path: Path) -> None:
    """A non-REDEME autónomo who ELECTS ``devolver`` in the last period files ``D`` and carries ZERO.

    4T is the year's last filing period, so the refund election is lawful for a
    non-REDEME taxpayer (LIVA art. 116). The resolved disposition is devolución
    (``D``), and the next period (1T of the following year) auto-resolves a casilla-110
    carry-in of zero — the refunded credit is requested back, not double-claimed.
    """
    with _secure_backend(tmp_path):
        revision_id, saldo = _calculate_negative_period(period_token=_LAST_PERIOD, redeme_enrolled=False)
        assert saldo > Decimal("0")  # the engine produced a credit to refund
        disposition = _file_period(
            calculation_revision_id=revision_id,
            redeme_enrolled=False,
            refund_election=RefundElection.DEVOLVER,
        )
        carry_in = _next_period_carry_in(next_year=_YEAR + 1, next_period="1T")

    assert disposition is ResultDisposition.DEVOLUCION
    assert carry_in == Decimal("0")


def test_non_redeme_last_period_without_election_carries_credit_forward(tmp_path: Path) -> None:
    """CONTROL: the SAME last period filed without the election stays ``C`` and carries the credit.

    The only difference from the refund test is the default ``COMPENSAR`` election —
    the disposition is compensación (``C``), so the engine-produced saldo carries into
    the next period's casilla 110 normally. Proves the refund is the gated opt-in and
    the carry-forward path is behaviour-preserving for a non-REDEME taxpayer.
    """
    with _secure_backend(tmp_path):
        revision_id, saldo = _calculate_negative_period(period_token=_LAST_PERIOD, redeme_enrolled=False)
        disposition = _file_period(
            calculation_revision_id=revision_id,
            redeme_enrolled=False,
            refund_election=RefundElection.COMPENSAR,
        )
        carry_in = _next_period_carry_in(next_year=_YEAR + 1, next_period="1T")

    assert disposition is ResultDisposition.COMPENSACION
    assert carry_in is not None
    assert carry_in == saldo
    assert carry_in > Decimal("0")


def test_non_redeme_mid_period_refund_election_is_refused(tmp_path: Path) -> None:
    """A non-REDEME autónomo who elects ``devolver`` MID-year (2T) is REFUSED, not silently carried.

    2T is not the year's last filing period, so a non-REDEME refund is not lawful
    (LIVA art. 116). Electing ``devolver`` raises the instructive refusal rather than
    silently downgrading to compensación (which would discard the operator's request)
    or silently filing an unlawful refund.
    """
    with _secure_backend(tmp_path):
        revision_id, saldo = _calculate_negative_period(period_token=_MID_PERIOD, redeme_enrolled=False)
        assert saldo > Decimal("0")
        with pytest.raises(ModeloRefundElectionNotEligibleError) as excinfo:
            _file_period(
                calculation_revision_id=revision_id,
                redeme_enrolled=False,
                refund_election=RefundElection.DEVOLVER,
            )

    assert excinfo.value.context is not None
    assert excinfo.value.context["period"] == _MID_PERIOD
    assert excinfo.value.context["modelo"] == "303"


def test_redeme_taxpayer_refunds_without_election_regression_guard(tmp_path: Path) -> None:
    """REGRESSION: a REDEME taxpayer still refunds its eligible period under the standing election.

    REDEME inscription is the always-on refund election; it does not depend on the
    per-filing flag. A REDEME filer's negative 4T period resolves to devolución (``D``)
    even with the default ``COMPENSAR`` election, and carries ZERO forward — proving
    the new per-filing opt-in did not regress the standing REDEME path.
    """
    with _secure_backend(tmp_path):
        revision_id, saldo = _calculate_negative_period(period_token=_LAST_PERIOD, redeme_enrolled=True)
        assert saldo > Decimal("0")
        disposition = _file_period(
            calculation_revision_id=revision_id,
            redeme_enrolled=True,
            refund_election=RefundElection.COMPENSAR,
        )
        carry_in = _next_period_carry_in(next_year=_YEAR + 1, next_period="1T")

    assert disposition is ResultDisposition.DEVOLUCION
    assert carry_in == Decimal("0")
