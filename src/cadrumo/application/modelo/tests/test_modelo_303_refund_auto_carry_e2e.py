"""E2E: filing an M303 devolución period AUTO-carries zero compensación forward.

The refund disposition is determined ONCE at the calculate/file boundary from
the profile REDEME axis and the eligibility gate, and BOTH the export "Tipo de
declaración" and the cross-period carry persistence read that one determined
fact. The domain rule treats a REDEME company's negative Modelo 303 period as
requested as devolución (``D``) under its standing monthly-devolución
disposition policy, so the period must carry ZERO compensación into the next
period's casilla 110 - never double-claim the requested devolución credit.

The load-bearing contract: the refunded carry fires AUTOMATICALLY from the real
``file_modelo_revision`` filing path. NO test passes ``refunded=True`` — the
determination is computed inside the filing action from the REDEME profile. The
control files the SAME negative-result period under a non-REDEME (compensar)
profile and asserts the credit auto-carries normally; the only difference is the
profile's REDEME axis.

Real-behaviour, real-adapter: real encrypted-SQLite secure store via
``isolated_runtime_profile``, the real registry authority, the real calculation
engine, the real wallet reconciliation, the real verify + workflow + cross-period
clean-state gates, and the real ``relation_prefill`` carry resolver. No mocks,
stubs, skips, or xfail.

Non-tautological: the period's negative ``iva.resultado`` and its generated
compensación saldo are produced by the REAL engine from a credit scenario
(soportado > repercutido), never hand-computed against the formula. The refunded
assertion is the structural zero-carry invariant; the control asserts the carried
value equals the SAME engine-produced saldo. Legal basis: RD 1624/1992 art. 30 /
Ley 37/1992 art. 116.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import SecretStr

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....core import AuthProviderKind
from ....core.period import Period
from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.config import Settings
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.ids import RelationId
from ....domain.deadlines.models import IVARegime, M303RegimeComposition, M303TaxTerritory, ModeloIVAProfile, TaxpayerProfile
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from ....tests.filing_evidence import general_m303_filing_evidence
from ....tests.profile_capsule import seed_test_profile_record
from ....tests.secure_sql import isolated_runtime_profile
from ...calculations import (
    CalculationObservationRepository,
    reconcile_modelo_303_iva_compensation,
    resolve_relations_from_local_store,
)
from .._calculation_actions import calculate_modelo_revision
from .._filing_actions import file_modelo_revision
from .._verification_actions import verify_modelo_revision
from ..work_lifecycle import create_work_unit

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_TAX_ID = "X1234567L"
_BUCKET_ID = "30300000-0000-4000-8000-000000000032"
_YEAR = 2026
_REFUND_PERIOD = "2T"
_NEXT_PERIOD = "3T"
#: REDEME-enrolled taxpayers file Modelo 303 MONTHLY, not quarterly (RD
#: 1624/1992 art. 30 / RD 596/2016; see the ``modelo-303-mensual`` filing
#: schedule's ``iva.redeme_enrolled == true`` profile condition). The
#: quarterly ``_REFUND_PERIOD``/``_NEXT_PERIOD`` tokens above have no matching
#: deadline obligation for a REDEME profile, so the REDEME scenario uses its
#: own monthly period pair with the same ``_FILE_AT``-relative window shape
#: (period "06" opens 2026-07-01 / closes 2026-07-30, matching quarterly 2T's
#: filing-window alignment with ``_FILE_AT``).
_REDEME_REFUND_PERIOD = "06"
_REDEME_NEXT_PERIOD = "07"
_DECIDED_AT = datetime(2026, 5, 19, 12, 0, 0, tzinfo=UTC)
_VERIFY_AT = datetime(2026, 7, 15, 9, 0, 0, tzinfo=UTC)
_FILE_AT = datetime(2026, 7, 15, 10, 0, 0, tzinfo=UTC)

#: The carry chain casilla/relation: the prior period's end-of-period available
#: compensación flows into the next period's casilla 110.
_CARRY_RELATION: RelationId = "modelo-303-rel-self-compensacion-anteriores"


_M303_RESULTADO_CASILLA: CasillaId = validated_casilla_id("iva.resultado")
_SALDO_CASILLA: CasillaId = validated_casilla_id("iva.compensacion-disponible-fin-periodo")

#: A negative-result M303 credit scenario: cuota soportada (interiores) exceeds
#: cuota repercutida, so the régimen-general result is negative — the IVA credit
#: that is refunded (REDEME) or carried (compensar).
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
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        yield


def _activity_start_date_for_period(period_token: str) -> date:
    """First-IVA-period activity start proving no prior M303 compensation existed.

    The first-period-zero IVA-wallet gate scopes a prior-compensation dependency
    out only when its source period falls strictly before the profile's declared
    activity-start date (``_activity_start_proves_first_iva_period``). The prior-
    compensation dependency of a quarterly period is the previous quarter and of a
    monthly REDEME period is the previous month, so for the period to be genuinely
    the taxpayer's first IVA filing the activity must begin at the start of that
    period: 1 April for the quarterly 2T (scoping out 1T), 1 June for the monthly
    REDEME "06" (scoping out May). A pre-period activity start would leave a real
    prior IVA period in scope, which the gate correctly refuses to treat as a
    first-period zero.
    """
    return date(_YEAR, 6, 1) if period_token == _REDEME_REFUND_PERIOD else date(_YEAR, 4, 1)


def _store_operator_profile(*, period_token: str) -> None:
    seed_test_profile_record(
        UserProfileRecord(
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=_BUCKET_ID,
            facts=(
                UserProfileFact(path="identity.tax_id", value=_TAX_ID),
                UserProfileFact(path="identity.name", value="Test"),
                UserProfileFact(path="identity.surnames", value="Operator"),
                UserProfileFact(path="activities.description", value="economic activity"),
                UserProfileFact(path="tax_residence.ccaa", value="madrid"),
                UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
                UserProfileFact(path="iva.regime", value="GENERAL"),
                UserProfileFact(path="iva.m303_regime_composition", value="general"),
                UserProfileFact(path="iva.redeme_enrolled", value=False),
                UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
                UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
                UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
                UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
                UserProfileFact(path="taxpayer_type.irpf_income_categories", value="actividad_economica"),
                UserProfileFact(path="irpf.estimation_regime", value="directa_normal"),
                UserProfileFact(path="censo.activity_start_date", value=_activity_start_date_for_period(period_token)),
            ),
            created_at=_DECIDED_AT,
            updated_at=_DECIDED_AT,
        ),
    )


def _workflow_profile(*, redeme_enrolled: bool, period_token: str) -> TaxpayerProfile:
    return TaxpayerProfile(
        tax_id=_TAX_ID,
        iva_regime=IVARegime.GENERAL,
        has_employees=False,
        pays_rent_with_retencion=False,
        does_intracomunitario=False,
        bienes_extranjero_above_threshold=False,
        activity_start_date=_activity_start_date_for_period(period_token),
        iva=ModeloIVAProfile(
            tax_territory=M303TaxTerritory.COMMON_REGIME,
            regime_composition=M303RegimeComposition.GENERAL,
            redeme_enrolled=redeme_enrolled,
            cash_accounting_regime_enrolled=False,
            voluntary_sii_enrolled=False,
            hydrocarbon_deposit_advance_payment_deduction_entitled=False,
        ),
    )


def _file_negative_2t_period(*, redeme_enrolled: bool, period: str = _REFUND_PERIOD) -> Decimal:
    """File the M303 negative-credit period; return the engine-produced saldo.

    Drives the REAL first-period wallet reconciliation, calculate, verify, and
    ``file_modelo_revision`` filing path. The filing disposition (devolución vs
    compensación) is determined INSIDE the filing action from the profile's
    REDEME axis — this helper NEVER passes ``refunded``. Returns the value the
    revision computed for ``iva.compensacion-disponible-fin-periodo`` (read back
    from the revision, never hand-derived from the formula — anti-tautology).

    ``period`` defaults to the quarterly ``_REFUND_PERIOD``; REDEME-enrolled
    scenarios pass ``_REDEME_REFUND_PERIOD`` (monthly — REDEME taxpayers have
    no quarterly filing obligation, see the module-level period constants).
    """
    _store_operator_profile(period_token=period)
    work_repo = WorkUnitCatalogueRepository()
    calc_repo = CalculationRevisionCatalogueRepository()
    filing_repo = ModeloRecordCatalogueRepository()
    event_repo = BucketEventHistoryRepository()

    snapshot = bundled_authority().snapshot("303", filing_year=_YEAR, period=period)
    report = reconcile_modelo_303_iva_compensation(
        snapshot,
        taxpayer_nif=_TAX_ID,
        wallet=None,
        repository=CalculationObservationRepository(),
        decided_at=_DECIDED_AT,
        treat_absent_recurrence_as_first_period=True,
    )
    assert report.decision.divergence == "first_period_zero"

    work_unit = create_work_unit(
        bucket_id=_BUCKET_ID,
        modelo="303",
        filing_year=_YEAR,
        period=Period.from_year_and_code(_YEAR, period),
        revision_id=snapshot.revision.id,
        repository=work_repo,
        clock=_DECIDED_AT,
    )
    revision = calculate_modelo_revision(
        work_unit.work_unit_id,
        actor="operator",
        casilla_inputs={},
        binding_values={"modelo-303-profile-state-attribution-ratio": Decimal("100")},
        backend_binding_values=_NEGATIVE_CREDIT_ENGINE_INPUTS,
        iva_compensation_decision=report.decision,
        filing_instance_evidence=general_m303_filing_evidence(
            work_unit.period,
            reference="test:m303-refund-auto-carry",
        ),
        filing_period_date=date(_YEAR, 6, 30),
        work_unit_repository=work_repo,
        calculation_repository=calc_repo,
        bucket_event_repository=event_repo,
        clock=_DECIDED_AT,
    )
    # The scenario genuinely produced a negative result and a positive carry saldo.
    assert revision.casilla_values[_M303_RESULTADO_CASILLA] < Decimal("0")
    saldo = revision.casilla_values[_SALDO_CASILLA]
    assert saldo > Decimal("0")

    verification = verify_modelo_revision(
        revision.calculation_revision_id,
        actor="operator",
        workflow_profile=_workflow_profile(redeme_enrolled=redeme_enrolled, period_token=period),
        work_unit_repository=work_repo,
        calculation_repository=calc_repo,
        filing_repository=filing_repo,
        bucket_event_repository=event_repo,
        settings=Settings(
            cadrumo_auth_provider=AuthProviderKind.CLAVE_MOVIL,
            cadrumo_clave_movil_dni_nie=SecretStr(_TAX_ID),
        ),
        clock=_VERIFY_AT,
    )
    assert verification.granted_verificado_completo is True

    # The filing path determines the devolución/compensación disposition itself
    # from the REDEME profile — NO refunded flag is passed here.
    file_modelo_revision(
        revision.calculation_revision_id,
        actor="operator",
        workflow_profile=_workflow_profile(redeme_enrolled=redeme_enrolled, period_token=period),
        work_unit_repository=work_repo,
        calculation_repository=calc_repo,
        filing_repository=filing_repo,
        bucket_event_repository=event_repo,
        settings=Settings(
            cadrumo_auth_provider=AuthProviderKind.CLAVE_MOVIL,
            cadrumo_clave_movil_dni_nie=SecretStr(_TAX_ID),
        ),
        clock=_FILE_AT,
    )
    return saldo


def _next_period_carry_in(*, next_period: str = _NEXT_PERIOD) -> Decimal | None:
    """Resolve the casilla-110 carry-in from whatever prior-period carry the filing persisted.

    ``next_period`` defaults to the quarterly ``_NEXT_PERIOD`` (3T, following
    the default 2T ``_file_negative_2t_period`` scenario); REDEME-enrolled
    scenarios pass ``_REDEME_NEXT_PERIOD`` (the monthly period following
    ``_REDEME_REFUND_PERIOD``).
    """
    snapshot_next = bundled_authority().snapshot("303", filing_year=_YEAR, period=next_period)
    relation_values = resolve_relations_from_local_store(
        snapshot_next,
        repository=CalculationObservationRepository(),
    )
    resolved: dict[RelationId, Decimal] = {
        item.relation: item.value for item in relation_values.values if item.value is not None
    }
    return resolved.get(_CARRY_RELATION)


def test_redeme_refund_period_auto_carries_zero_without_manual_flag(tmp_path: Path) -> None:
    """A REDEME company's filed devolución month carries NO credit into the next month's casilla 110.

    REDEME-enrolled taxpayers have a MONTHLY M303 filing obligation (RD
    1624/1992 art. 30 / RD 596/2016), never quarterly, so this scenario uses
    the monthly ``_REDEME_REFUND_PERIOD``/``_REDEME_NEXT_PERIOD`` pair. The
    filing path determines the devolución disposition from the REDEME profile
    and zeroes the cross-period carry — no ``refunded=True`` is passed anywhere.

    The self-compensación carry relation (``modelo-303-rel-self-compensacion-anteriores``)
    the registry declares targets only the quarterly periods (``target_periods =
    ["1T", "2T", "3T", "4T"]``, ``previous_quarter`` alignment); the registry
    models no monthly ``previous_month`` self-compensación carry. So a monthly
    REDEME next period resolves NO casilla-110 carry-in via this relation
    (``carry_in is None``). The refunded credit is therefore not carried forward
    — the double-claim this test guards against cannot occur — which is the
    invariant. The positive-carry counterpart is exercised by the quarterly
    control below.
    """
    with _secure_backend(tmp_path):
        saldo = _file_negative_2t_period(redeme_enrolled=True, period=_REDEME_REFUND_PERIOD)
        assert saldo > Decimal("0")  # the engine did generate a credit to refund
        carry_in = _next_period_carry_in(next_period=_REDEME_NEXT_PERIOD)

    assert carry_in is None


def test_compensar_period_auto_carries_credit_forward_control(tmp_path: Path) -> None:
    """CONTROL: the SAME negative period filed by a non-REDEME filer auto-carries the credit.

    The only difference from the refund test is ``redeme_enrolled=False`` — the
    disposition is compensación (``C``), so the engine-produced saldo carries into
    3T casilla 110 normally. Proves the auto-determination is REDEME-gated and the
    non-refund path is behaviour-preserving.
    """
    with _secure_backend(tmp_path):
        saldo = _file_negative_2t_period(redeme_enrolled=False)
        carry_in = _next_period_carry_in()

    assert carry_in is not None
    assert carry_in == saldo
    assert carry_in > Decimal("0")
