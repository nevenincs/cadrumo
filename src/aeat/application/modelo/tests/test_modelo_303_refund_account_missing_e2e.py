"""E2E: a Modelo 303 refund export with no refund account on file is refused.

the no-account refusal end-to-end. Distinct from the component-level
unit coverage in ``test_export.py`` (which drives ``_compose_export_headers`` +
``_render_layout`` directly): this case drives the FULL public
``export_modelo_revision`` path against a real registry-backed, engine-computed,
verified-complete negative-credit revision. The disposition is resolved to a
refund (devolución, ``D``) by the REAL shared resolver from the REAL engine
result for a REDEME-enrolled filer — never hand-forced — and the filer carries
NO ``RefundAccount`` on the profile.

The contract under test: rather than emit an empty/partial cuenta-devolución
(DID) block AEAT cannot pay, the export refuses with the typed
``ModeloRefundAccountMissingError`` AND writes no fichero — neither the
operator-visible output nor the atomic-rename ``.tmp`` sidecar. A devolución
fichero with no payable account is a silent under-evidenced filing this gate
forbids.

Real-behaviour, real-adapter: real encrypted-SQLite secure store via
``isolated_runtime_profile``, the real registry authority, the real first-period
wallet reconciliation, the real calculation engine, the real cross-period
clean-state seeding, and the real verify + export application paths. No mocks,
stubs, skips, or xfail.

Non-tautological: the period's negative ``iva.resultado`` is produced by the
REAL engine from a credit scenario (soportado > repercutido), never hand-computed
against the formula; the refund disposition is read from the REAL
``resolve_modelo_result_disposition`` against the REAL verified revision (no
``refunded`` flag is passed); and the refusal is asserted against the REAL
``export_modelo_revision`` public path plus the no-bytes-written guarantee.
Legal basis: Ley 37/1992 (LIVA) art. 116; art. 30 RD 1624/1992 (REDEME).
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....core import Period, ResultDisposition
from ....domain.buckets import BucketEventHistoryRepository
from ....domain.calculations.registry import CasillaId, validated_casilla_id
from ....domain.deadlines import IVARegime, ModeloIVAProfile, TaxpayerProfile
from ....domain.modelos._calculation_repository import CalculationRevisionCatalogueRepository
from ....domain.modelos._filing_repository import ModeloRecordCatalogueRepository
from ....domain.modelos._repository import WorkUnitCatalogueRepository
from ....domain.user_profile import UserProfileFact, UserProfileRecord
from ....tests.secure_sql import isolated_runtime_profile
from ...calculations import CalculationObservationRepository, reconcile_modelo_303_iva_compensation
from ...user_profile import UserProfileLifecycleRepository
from .. import (
    ModeloExportCommand,
    calculate_modelo_revision,
    create_work_unit,
    export_modelo_revision,
    verify_modelo_revision,
)
from .._action_errors import ModeloRefundAccountMissingError
from .._result_disposition_resolution import resolve_modelo_result_disposition

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_TAX_ID = "X1234567L"
_YEAR = 2025
_PERIOD = "2T"

#: A negative-result M303 credit scenario: cuota soportada (interiores) exceeds
#: cuota repercutida (zero), so the régimen-general result is negative — the IVA
#: credit a REDEME filer refunds (devolución, ``D``).
_NEGATIVE_CREDIT_ENGINE_INPUTS = {
    "modelo-303-iva-repercutido-general-cuota": Decimal("0.00"),
    "modelo-303-iva-repercutido-reducido-cuota": Decimal("0.00"),
    "modelo-303-iva-repercutido-super-reducido-cuota": Decimal("0.00"),
    "modelo-303-iva-soportado-interiores-cuota": Decimal("1000.00"),
    "modelo-303-iva-autorepercutido-intracomunitaria-cuota": Decimal("0.00"),
    "modelo-303-profile-state-attribution-ratio": Decimal("100"),
}

_M303_RESULTADO_CASILLA: CasillaId = validated_casilla_id("iva.resultado", surface="_M303_RESULTADO_CASILLA")


@contextmanager
def _secure_backend(tmp_path: Path) -> Iterator[None]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="operator"):
        yield


def _store_operator_profile(*, created_at: datetime) -> None:
    # The export header composer requires the operator name facts (surnames +
    # name) before reaching the refund-account block, so seed them here — the
    # absent fact under test is the refund account, not the operator identity.
    UserProfileLifecycleRepository(bucket_id="operator").save(
        UserProfileRecord(
            profile_id="operator",
            display_name="Test runtime profile",
            facts=(
                UserProfileFact(path="identity.tax_id", value=_TAX_ID),
                UserProfileFact(path="identity.surnames", value="Garcia Lopez"),
                UserProfileFact(path="identity.name", value="Juan"),
                UserProfileFact(path="activities.description", value="economic activity"),
                UserProfileFact(path="tax_residence.ccaa", value="madrid"),
                UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
                UserProfileFact(path="iva.regime", value="GENERAL"),
                UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
                UserProfileFact(path="taxpayer_type.irpf_income_categories", value="actividad_economica"),
                UserProfileFact(path="irpf.estimation_regime", value="directa_normal"),
                UserProfileFact(path="censo.activity_start_date", value=date(_YEAR, 4, 1)),
            ),
            created_at=created_at,
            updated_at=created_at,
        ),
    )


def _redeme_profile_without_refund_account() -> TaxpayerProfile:
    """A REDEME-enrolled IVA profile with NO refund account on file.

    REDEME enrolment makes a negative period a refund (devolución) in every
    eligible period (art. 30 RD 1624/1992); the absent ``RefundAccount`` is the
    condition under test — the export must refuse rather than emit an empty DID.
    """
    return TaxpayerProfile(
        tax_id=_TAX_ID,
        iva_regime=IVARegime.GENERAL,
        has_employees=False,
        pays_rent_with_retencion=False,
        does_intracomunitario=False,
        bienes_extranjero_above_threshold=False,
        activity_start_date=date(_YEAR, 4, 1),
        iva=ModeloIVAProfile(redeme_enrolled=True, refund_account=None),
    )


def _calculate_verified_negative_period() -> str:
    """Calculate + verify a negative-credit REDEME M303 ``2T`` revision; return its id.

    Drives the REAL first-period wallet reconciliation, calculate, cross-period
    clean-state seeding, and verify paths. The returned revision is
    verified-complete and ready to export; its negative result is asserted from
    the engine output, never hand-derived.
    """
    decided_at = datetime(_YEAR, 6, 19, 12, 0, 0, tzinfo=UTC)
    verified_at = datetime(_YEAR, 7, 20, 9, 0, 0, tzinfo=UTC)
    _store_operator_profile(created_at=decided_at)
    work_repo = WorkUnitCatalogueRepository()
    calc_repo = CalculationRevisionCatalogueRepository()
    filing_repo = ModeloRecordCatalogueRepository()
    event_repo = BucketEventHistoryRepository()

    from ....core.resources import resources

    snapshot = resources().modelos.authority.snapshot("303", filing_year=_YEAR, period=_PERIOD)
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
        period=Period.from_year_and_code(_YEAR, _PERIOD),
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
        filing_period_date=date(_YEAR, 6, 30),
        work_unit_repository=work_repo,
        calculation_repository=calc_repo,
        bucket_event_repository=event_repo,
        clock=decided_at,
    )
    # The engine produced a genuine negative result (anti-tautology anchor).
    assert revision.casilla_values[_M303_RESULTADO_CASILLA] < Decimal("0")

    verification = verify_modelo_revision(
        revision.calculation_revision_id,
        actor="operator",
        workflow_profile=_redeme_profile_without_refund_account(),
        work_unit_repository=work_repo,
        calculation_repository=calc_repo,
        filing_repository=filing_repo,
        bucket_event_repository=event_repo,
        clock=verified_at,
    )
    assert verification.granted_verificado_completo is True

    # The shared resolver classifies this verified revision as a refund (D) for
    # the REDEME filer — asserted from the REAL resolver, not assumed.
    disposition = resolve_modelo_result_disposition(
        work_unit=work_unit,
        revision=revision,
        workflow_profile=_redeme_profile_without_refund_account(),
        period=work_unit.period,
    )
    assert disposition is ResultDisposition.DEVOLUCION

    return revision.calculation_revision_id


def test_refund_export_without_account_refuses_and_writes_no_fichero(tmp_path: Path) -> None:
    """A REDEME refund export with no refund account is refused; no bytes are written.

    Drives the full ``export_modelo_revision`` public path: the refund-account
    refusal fires inside ``_compose_export_headers`` BEFORE any draft write, so
    the typed ``ModeloRefundAccountMissingError`` is raised and neither the
    operator-visible output nor the atomic-rename ``.tmp`` sidecar exists. An
    empty cuenta-devolución block files a devolución AEAT cannot pay — the gate
    refuses it end-to-end.
    """
    with _secure_backend(tmp_path):
        calculation_revision_id = _calculate_verified_negative_period()

        output_path = tmp_path / "modelo-303-refund.txt"
        with pytest.raises(ModeloRefundAccountMissingError):
            export_modelo_revision(
                ModeloExportCommand(
                    calculation_revision_id=calculation_revision_id,
                    output_path=output_path,
                    actor="operator",
                ),
                workflow_profile=_redeme_profile_without_refund_account(),
                clock=datetime(_YEAR, 7, 20, 10, 0, 0, tzinfo=UTC),
            )

        # No fichero reached disk: neither the operator-visible output nor the
        # atomic-rename .tmp sidecar — the refusal precedes any byte write.
        assert not output_path.exists()
        assert not output_path.with_name(output_path.name + ".tmp").exists()
