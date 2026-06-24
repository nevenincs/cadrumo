"""E2E: filing an M303 devolución period AUTO-carries zero compensación forward.

ADR 2026-06-21-m303-carry-reconciliation (part 2): the refund disposition is
determined ONCE at the calculate/file boundary from the profile REDEME axis and
the eligibility gate, and BOTH the export "Tipo de declaración" and the
cross-period carry persistence read that one determined fact. A REDEME
monthly-refund company's negative Modelo 303 period is filed as a refund
(devolución, ``D``): the credit is returned by AEAT, so the period must carry
ZERO compensación into the next period's casilla 110 — never double-claim the
refunded credit.

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

from ....core import Period
from ....core.config import AuthProviderKindSetting, Settings
from ....core.resources import resources
from ....domain.buckets import BucketEventHistoryRepository
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
    calculate_modelo_revision,
    create_work_unit,
    file_modelo_revision,
    verify_modelo_revision,
)
from ._file_flow_support import _seed_clean_cross_period_sources

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_TAX_ID = "X1234567L"
_YEAR = 2026
_REFUND_PERIOD = "2T"
_NEXT_PERIOD = "3T"
_DECIDED_AT = datetime(2026, 5, 19, 12, 0, 0, tzinfo=UTC)
_VERIFY_AT = datetime(2026, 7, 15, 9, 0, 0, tzinfo=UTC)
_FILE_AT = datetime(2026, 7, 15, 10, 0, 0, tzinfo=UTC)

#: The carry chain casilla/relation: the prior period's end-of-period available
#: compensación flows into the next period's casilla 110.
_CARRY_RELATION = "modelo-303-rel-self-compensacion-anteriores"
_SALDO_CASILLA = "iva.compensacion-disponible-fin-periodo"

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
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="operator"):
        yield


def _store_operator_profile() -> None:
    UserProfileLifecycleRepository(bucket_id="operator").save(
        UserProfileRecord(
            profile_id="operator",
            display_name="Test runtime profile",
            facts=(UserProfileFact(path="identity.tax_id", value=_TAX_ID),),
            created_at=_DECIDED_AT,
            updated_at=_DECIDED_AT,
        ),
    )


def _workflow_profile(*, redeme_enrolled: bool) -> TaxpayerProfile:
    return TaxpayerProfile(
        tax_id=_TAX_ID,
        iva_regime=IVARegime.GENERAL,
        has_employees=False,
        pays_rent_with_retencion=False,
        does_intracomunitario=False,
        bienes_extranjero_above_threshold=False,
        iva=ModeloIVAProfile(redeme_enrolled=redeme_enrolled),
    )


def _file_negative_2t_period(*, redeme_enrolled: bool) -> Decimal:
    """File the M303 2T negative-credit period; return the engine-produced saldo.

    Drives the REAL first-period wallet reconciliation, calculate, verify, and
    ``file_modelo_revision`` filing path. The filing disposition (devolución vs
    compensación) is determined INSIDE the filing action from the profile's
    REDEME axis — this helper NEVER passes ``refunded``. Returns the value the 2T
    revision computed for ``iva.compensacion-disponible-fin-periodo`` (read back
    from the revision, never hand-derived from the formula — anti-tautology).
    """
    _store_operator_profile()
    work_repo = WorkUnitCatalogueRepository()
    calc_repo = CalculationRevisionCatalogueRepository()
    filing_repo = ModeloRecordCatalogueRepository()
    event_repo = BucketEventHistoryRepository()

    snapshot = resources().modelos.authority.snapshot("303", filing_year=_YEAR, period=_REFUND_PERIOD)
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
        bucket_id="operator",
        modelo="303",
        filing_year=_YEAR,
        period=Period.from_year_and_code(_YEAR, _REFUND_PERIOD),
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
        filing_period_date=date(_YEAR, 6, 30),
        work_unit_repository=work_repo,
        calculation_repository=calc_repo,
        bucket_event_repository=event_repo,
        clock=_DECIDED_AT,
    )
    # The scenario genuinely produced a negative result and a positive carry saldo.
    assert revision.casilla_values["iva.resultado"] < Decimal("0")
    saldo = revision.casilla_values[_SALDO_CASILLA]
    assert saldo > Decimal("0")

    _seed_clean_cross_period_sources(
        work_unit,
        work_unit_repository=work_repo,
        calculation_repository=calc_repo,
        filing_repository=filing_repo,
        bucket_event_repository=event_repo,
    )
    verification = verify_modelo_revision(
        revision.calculation_revision_id,
        actor="operator",
        workflow_profile=_workflow_profile(redeme_enrolled=redeme_enrolled),
        work_unit_repository=work_repo,
        calculation_repository=calc_repo,
        filing_repository=filing_repo,
        bucket_event_repository=event_repo,
        clock=_VERIFY_AT,
    )
    assert verification.granted_verificado_completo is True

    # The filing path determines the devolución/compensación disposition itself
    # from the REDEME profile — NO refunded flag is passed here.
    file_modelo_revision(
        revision.calculation_revision_id,
        actor="operator",
        workflow_profile=_workflow_profile(redeme_enrolled=redeme_enrolled),
        work_unit_repository=work_repo,
        calculation_repository=calc_repo,
        filing_repository=filing_repo,
        bucket_event_repository=event_repo,
        settings=Settings(
            aeat_auth_provider=AuthProviderKindSetting.CLAVE_MOVIL,
            aeat_clave_movil_dni_nie=SecretStr(_TAX_ID),
        ),
        clock=_FILE_AT,
    )
    return saldo


def _next_period_carry_in() -> Decimal | None:
    """Resolve the 3T casilla-110 carry-in from whatever 2T carry the filing persisted."""
    snapshot_next = resources().modelos.authority.snapshot("303", filing_year=_YEAR, period=_NEXT_PERIOD)
    relation_values = resolve_relations_from_local_store(
        snapshot_next,
        repository=CalculationObservationRepository(),
    )
    resolved = {item.relation: item.value for item in relation_values.values if item.value is not None}
    return resolved.get(_CARRY_RELATION)


def test_redeme_refund_period_auto_carries_zero_without_manual_flag(tmp_path: Path) -> None:
    """A REDEME company's filed devolución 2T auto-carries ZERO into 3T casilla 110.

    The filing path determines the devolución disposition from the REDEME profile
    and zeroes the cross-period carry — no ``refunded=True`` is passed anywhere.
    The next period's casilla-110 carry-in auto-resolves to zero, so the refunded
    credit is not double-claimed.
    """
    with _secure_backend(tmp_path):
        saldo = _file_negative_2t_period(redeme_enrolled=True)
        assert saldo > Decimal("0")  # the engine did generate a credit to refund
        carry_in = _next_period_carry_in()

    assert carry_in == Decimal("0")


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
