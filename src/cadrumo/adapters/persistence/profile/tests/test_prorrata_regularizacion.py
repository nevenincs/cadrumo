"""Deferred-source advisory projection for the annual prorrata regularización.

See Also:
    :mod:`~application.calculations._prorrata_regularizacion`
        Projection module under test: casilla-44 advisory, M390 feed proposal,
        and declared-volume ledger divergence rollup.
    :func:`~domain.iva.compute_regularizacion_prorrata_anual`
        Pure domain computation whose signed result the projection carries.
    :class:`~domain.calculations.registry.IvaLedgerObservation`
        Typed ledger row used to prove advisory-only annual volume divergence.
    :class:`~application.aggregation.CalculationSourceDiagnostic`
        Diagnostic envelope asserted by the deferred source and divergence tests.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from .....application.calculations.prorrata_regularizacion import (
    build_prorrata_missing_provisional_advisory,
    buildprorrata_regularizacion_advisory,
    derive_prorrata_applicability,
    project_prorrata_regularizacion_feed,
)
from .....application.calculations.tests.filing_evidence import general_m303_filing_evidence
from .....application.modelo.revision_persistence import persist_filed_revision
from .....application.prorrata_register.seed import evaluate_carried_prior_definitiva_seed
from .....core.aggregation import BindingSourceKind
from .....core.casilla_id import CasillaId, validated_casilla_id
from .....core.iva_deduction_fact import IvaDeductionEvidenceAuthority, IvaDeductionFactKind
from .....core.modelo import Modelo
from .....core.period import Period
from .....core.prorrata_register import ProrrataProvisionalProvenance
from .....core.result_disposition import ResultDisposition
from .....domain.calculations.registry.authority import PinnedAuthorityOperation
from .....domain.calculations.registry.authority import bundled_indexed_authority as _indexed_authority_for_test
from .....domain.calculations.registry.binding_targets import casillas_by_binding
from .....domain.calculations.registry.casilla_membership import (
    casilla_noncanonical_reference_targets,
    declared_casilla_ids,
)
from .....domain.calculations.registry.errors import NoRevisionForPeriodError
from .....domain.calculations.registry.governed_fact_scope import validating_governed_facts
from .....domain.calculations.registry.ledger_iva_bindings import IvaLedgerObservation
from .....domain.calculations.registry.prorrata_regularizacion_bindings import (
    ProrrataRegularizacionOutput,
    ProrrataRegularizacionProvider,
)
from .....domain.calculations.registry.schema import ModeloRevision
from .....domain.calculations.registry.tests.registry_observations import registry_grounded_observations
from .....domain.iva.deduction_facts import IvaDeductionClassificationProvenance
from .....domain.iva.flow import IvaFlowDirection
from .....domain.iva.prorrata import RegularizacionProrrataDireccion
from .....domain.iva.schema import IvaCategory, IvaExemptionArticle, IvaLedgerObservationRole, IvaRateKind
from .....domain.modelos.calculation_repository import upsert_calculation_revision
from .....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from .....domain.modelos.codes import ModeloCode
from .....domain.modelos.repository import upsert_work_unit
from .....domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from .....domain.prorrata_register.register import ProrrataProvisionalResolution
from ...storage.tests.secure_sql import isolated_runtime_profile
from ..buckets import BucketEventHistoryRepository
from ..calculation_observations import CalculationObservationRepository
from ..iva_compensation_history import IvaCompensationHistoryRepository
from ..modelos_calculation import CalculationRevisionCatalogueRepository
from ..modelos_filing import ModeloRecordCatalogueRepository
from ..modelos_work_units import WorkUnitCatalogueRepository
from ..participation_index import TransactionParticipationIndexRepository
from ..prorrata_register import ProrrataRegisterRepository
from .published_authority_support import published_authority_operation

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("authority_operation")]

_BUCKET_ID = "52aedff7-7cc1-46ed-a615-afa5e56f6a89"  # was 'prorrata-regularizacion-s27'
_T0 = datetime(2026, 1, 1, 9, 0, 0, tzinfo=UTC)
_SETTLEMENT_YEAR = 2026
_CARRY_YEAR = 2027
_SETTLEMENT_PERIOD = "4T"

_VOLUMEN_TOTAL_ID: CasillaId = validated_casilla_id("iva.prorrata-volumen-total", surface="test casilla id")
_VOLUMEN_CON_DERECHO_ID: CasillaId = validated_casilla_id(
    "iva.prorrata-volumen-con-derecho",
    surface="test casilla id",
)
_PORCENTAJE_ID: CasillaId = validated_casilla_id("iva.prorrata-porcentaje", surface="test casilla id")
_RESULTADO_ID: CasillaId = validated_casilla_id("iva.resultado", surface="test casilla id")


def _periods_2026() -> tuple[Period, ...]:
    return tuple(Period.from_year_and_code(2026, code) for code in ("1T", "2T", "3T", "4T"))


def _ledger_observation(
    ledger_id: str,
    *,
    transaction_date: date,
    category: IvaCategory,
    base: str,
    operation: PinnedAuthorityOperation,
    flow: IvaFlowDirection,
    exemption_article: IvaExemptionArticle | None = None,
) -> IvaLedgerObservation:
    deduction = (
        {
            "deduction_fact_kind": IvaDeductionFactKind.from_registry("domestic_current"),
            "deduction_provenance": IvaDeductionClassificationProvenance(
                authority=IvaDeductionEvidenceAuthority.from_registry("invoice_evidence"),
                source_locator=f"invoice:{ledger_id}",
                evidence_digest="d" * 64,
            ),
        }
        if flow == IvaFlowDirection.from_registry("soportado")
        else {}
    )
    with validating_governed_facts(operation):
        return IvaLedgerObservation(
            ledger_id=ledger_id,
            transaction_date=transaction_date,
            category=category,
            exemption_article=exemption_article,
            rate_kind=IvaRateKind("general"),
            flow_direction=flow,
            base_amount=Decimal(base),
            iva_amount=Decimal("0.00"),
            observation_role=IvaLedgerObservationRole.SETTLEMENT,
            **deduction,
        )


def _m303_revision_id(*, filing_year: int, period: str) -> str:
    snapshot = published_authority_operation().snapshot(Modelo("303").value, filing_year=filing_year, period=period)
    return str(snapshot.revision.id)


def _unresolved_prorrata() -> ProrrataProvisionalResolution:
    return ProrrataProvisionalResolution(percentage=None, provenance=None)


def _seed_verified_m303_settlement(
    *,
    calculation_repository: CalculationRevisionCatalogueRepository,
    work_unit_repository: WorkUnitCatalogueRepository,
    operation: PinnedAuthorityOperation,
) -> tuple[CalculationRevision, WorkUnit]:
    period = Period.from_year_and_code(_SETTLEMENT_YEAR, _SETTLEMENT_PERIOD)
    registry_snapshot = published_authority_operation().snapshot(
        Modelo("303").value,
        filing_year=_SETTLEMENT_YEAR,
        period=_SETTLEMENT_PERIOD,
    )
    revision_id = str(registry_snapshot.revision.id)
    casilla_values = {
        _VOLUMEN_TOTAL_ID: Decimal("200000.00"),
        _VOLUMEN_CON_DERECHO_ID: Decimal("150000.00"),
        _PORCENTAJE_ID: Decimal("75"),
        _RESULTADO_ID: Decimal("0"),
    }
    work_unit_id = derive_work_unit_id(
        bucket_id=_BUCKET_ID,
        modelo=Modelo("303").value,
        filing_year=_SETTLEMENT_YEAR,
        period=period,
        revision_id=revision_id,
    )
    filing_instance_evidence = general_m303_filing_evidence(
        period, reference="test:prorrata-regularizacion", operation=operation
    )
    calculation_revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit_id,
        input_values_by_casilla_id={},
        binding_overrides={},
        casilla_values=casilla_values,
        filing_instance_evidence=filing_instance_evidence,
        source_provenance=(),
    )
    verified_at = _T0 + timedelta(hours=1)
    revision = CalculationRevision(
        calculation_revision_id=calculation_revision_id,
        work_unit_id=work_unit_id,
        registry_snapshot_ref=registry_snapshot.snapshot_ref,
        state=CalculationRevisionState.VERIFICADO_COMPLETO,
        input_values_by_casilla_id={},
        binding_overrides={},
        casilla_values=casilla_values,
        observations=registry_grounded_observations(
            modelo=Modelo("303").value,
            filing_year=_SETTLEMENT_YEAR,
            period=_SETTLEMENT_PERIOD,
            casilla_values=casilla_values,
        ),
        created_at=_T0,
        updated_at=verified_at,
        verified_at=verified_at,
        verified_by="aeat.test.modelo.verify",
        filing_instance_evidence=filing_instance_evidence,
        source_provenance=(),
    )
    work_unit = WorkUnit(
        work_unit_id=work_unit_id,
        bucket_id=_BUCKET_ID,
        modelo=ModeloCode(Modelo("303").value),
        filing_year=_SETTLEMENT_YEAR,
        period=period,
        revision_id=revision_id,
        name="303-2026-4T",
        created_at=_T0,
        updated_at=verified_at,
        current_calculation_revision_id=calculation_revision_id,
    )
    work_unit_repository.save(upsert_work_unit(work_unit_repository.load(), work_unit))
    calculation_repository.save(upsert_calculation_revision(calculation_repository.load(), revision))
    return revision, work_unit


def _settlement_revision() -> ModeloRevision:
    return (
        published_authority_operation()
        .snapshot(Modelo("303").value, filing_year=_SETTLEMENT_YEAR, period=_SETTLEMENT_PERIOD)
        .revision
    )


def test_mixed_trader_in_year_missing_carry_is_visible_not_defaulted_to_100() -> None:
    """Positive sin-derecho volume with no provisional carry emits an in-year advisory."""
    applicability = derive_prorrata_applicability(
        declared_volume_total=Decimal("100000.00"),
        declared_volume_con_derecho=Decimal("80000.00"),
    )

    diagnostic = build_prorrata_missing_provisional_advisory(
        applicability=applicability,
        provisional_resolution=_unresolved_prorrata(),
        ejercicio=2026,
        revision=_settlement_revision(),
    )

    assert applicability.applies is True
    assert "declared_sin_derecho_volume" in applicability.evidence_kinds
    assert diagnostic is not None
    assert diagnostic.binding_source is BindingSourceKind.PRORRATA_REGULARIZACION
    snapshot = published_authority_operation().snapshot(
        Modelo("303").value,
        filing_year=_SETTLEMENT_YEAR,
        period=_SETTLEMENT_PERIOD,
    )
    canonical_target = next(
        casilla_id
        for binding in snapshot.revision.bindings
        if binding.source is BindingSourceKind.PRORRATA_REGULARIZACION
        and isinstance(binding.provider, ProrrataRegularizacionProvider)
        and binding.provider.regularizacion_output is ProrrataRegularizacionOutput.MODELO_303_CASILLA_44
        for casilla_id in casillas_by_binding(snapshot.revision)[binding.id]
    )
    assert diagnostic.casilla_id == canonical_target
    assert "por defecto" in diagnostic.message
    assert "definitiva del ejercicio anterior" in diagnostic.message


def test_advisory_fires_for_casilla_44_when_prorrata_applies_and_percentages_differ() -> None:
    """A trader with sin-derecho volumes and a percentage delta is alerted, not silent."""
    result, diagnostic = buildprorrata_regularizacion_advisory(
        cuotas_soportadas_deducibles=Decimal("20000.00"),
        prorrata_provisional_pct=Decimal("80"),
        prorrata_definitiva_pct=Decimal("90"),
        operaciones_sin_derecho_deduccion=Decimal("10000"),
        regularizacion_year=2025,
        revision=_settlement_revision(),
    )
    assert result.direccion is RegularizacionProrrataDireccion.DEDUCCION
    assert result.importe == Decimal("2000.00")
    assert diagnostic is not None
    assert diagnostic.source_kind == BindingSourceKind.PRORRATA_REGULARIZACION.value
    assert diagnostic.binding_source is BindingSourceKind.PRORRATA_REGULARIZACION
    snapshot = published_authority_operation().snapshot(
        Modelo("303").value,
        filing_year=_SETTLEMENT_YEAR,
        period=_SETTLEMENT_PERIOD,
    )
    prorrata_binding = next(
        binding
        for binding in snapshot.revision.bindings
        if binding.source is BindingSourceKind.PRORRATA_REGULARIZACION
        and isinstance(binding.provider, ProrrataRegularizacionProvider)
        and binding.provider.regularizacion_output is ProrrataRegularizacionOutput.MODELO_303_CASILLA_44
    )
    assert diagnostic.casilla_id in casillas_by_binding(snapshot.revision)[prorrata_binding.id]
    assert "casilla 44" in diagnostic.message
    assert "2000.00" in diagnostic.message


def test_projection_feeds_m303_casilla_44_from_declared_volume_definitive_percentage() -> None:
    """The declared-volume definitive percentage is the percentage projected to casilla 44."""
    declared_volume_total = Decimal("200000.00")
    declared_volume_con_derecho = Decimal("150000.00")
    declared_definitive_percentage = Decimal("75")
    projection = project_prorrata_regularizacion_feed(
        cuotas_soportadas_deducibles=Decimal("20000.00"),
        prorrata_provisional_pct=Decimal("80"),
        prorrata_definitiva_pct=declared_definitive_percentage,
        operaciones_sin_derecho_deduccion=declared_volume_total - declared_volume_con_derecho,
    )

    assert projection.result.prorrata_definitiva_pct == declared_definitive_percentage
    assert projection.operaciones_sin_derecho_deduccion == Decimal("50000.00")
    snapshot = published_authority_operation().snapshot(
        Modelo("303").value,
        filing_year=_SETTLEMENT_YEAR,
        period=_SETTLEMENT_PERIOD,
    )
    prorrata_binding = next(
        binding
        for binding in snapshot.revision.bindings
        if binding.source is BindingSourceKind.PRORRATA_REGULARIZACION
        and isinstance(binding.provider, ProrrataRegularizacionProvider)
        and binding.provider.regularizacion_output is ProrrataRegularizacionOutput.MODELO_303_CASILLA_44
    )
    casilla_44_id = next(casilla.id for casilla in snapshot.revision.casillas if casilla.number == "44")
    assert casillas_by_binding(snapshot.revision)[prorrata_binding.id] == (casilla_44_id,)
    assert projection.proposed_value is not None
    assert projection.proposed_value == projection.result.importe


@pytest.mark.parametrize(
    ("filing_year", "period", "revision_id"),
    (
        (2024, "2T", "2024-hasta-08-y-2t"),
        (2024, "4T", "2024-desde-09-y-3t"),
        (2026, "4T", "2026-y-siguientes"),
    ),
)
def test_modelo_303_registry_has_no_casilla_61_binding_or_compatibility_route(
    filing_year: int,
    period: str,
    revision_id: str,
) -> None:
    """Every shipped M303 revision refuses casilla 61 as a form or binding route.

    One year per shipped revision window, so a newly-shipped revision cannot
    slip past this refusal by simply not being enumerated here.
    """
    snapshot = published_authority_operation().snapshot(Modelo("303").value, filing_year=filing_year, period=period)

    assert str(snapshot.revision.id) == revision_id
    assert "61" not in declared_casilla_ids(snapshot.revision)
    assert casilla_noncanonical_reference_targets(snapshot.revision, "61") == ()
    assert not any("casilla-61" in binding.id for binding in snapshot.revision.bindings)


def test_modelo_303_period_below_the_support_floor_refuses() -> None:
    """A filing year below the registry support floor refuses instead of projecting."""
    with pytest.raises(NoRevisionForPeriodError, match="year=2020"):
        published_authority_operation().snapshot(Modelo("303").value, filing_year=2020, period="4T")


def test_advisory_is_silent_when_no_sin_derecho_operations() -> None:
    """No exempt-without-right volume ⇒ prorrata does not apply ⇒ no advisory noise."""
    result, diagnostic = buildprorrata_regularizacion_advisory(
        cuotas_soportadas_deducibles=Decimal("20000.00"),
        prorrata_provisional_pct=Decimal("80"),
        prorrata_definitiva_pct=Decimal("90"),
        operaciones_sin_derecho_deduccion=Decimal("0"),
        regularizacion_year=2025,
        revision=_settlement_revision(),
    )
    assert diagnostic is None
    assert result.importe == Decimal("2000.00")


def test_advisory_is_silent_when_percentages_coincide() -> None:
    """No regularización is due when provisional equals definitive."""
    _result, diagnostic = buildprorrata_regularizacion_advisory(
        cuotas_soportadas_deducibles=Decimal("20000.00"),
        prorrata_provisional_pct=Decimal("90"),
        prorrata_definitiva_pct=Decimal("90"),
        operaciones_sin_derecho_deduccion=Decimal("10000"),
        regularizacion_year=2025,
        revision=_settlement_revision(),
    )
    assert diagnostic is None


def test_advisory_reports_ingreso_direction_when_definitiva_below_provisional() -> None:
    """A downward regularización is surfaced as an ingreso in the message."""
    result, diagnostic = buildprorrata_regularizacion_advisory(
        cuotas_soportadas_deducibles=Decimal("12000.00"),
        prorrata_provisional_pct=Decimal("85"),
        prorrata_definitiva_pct=Decimal("70"),
        operaciones_sin_derecho_deduccion=Decimal("30000"),
        regularizacion_year=2025,
        revision=_settlement_revision(),
    )
    assert result.direccion is RegularizacionProrrataDireccion.INGRESO
    assert diagnostic is not None
    assert "ingreso" in diagnostic.message


def test_zero_definitive_deduction_side_still_surfaces_casilla_44_advisory() -> None:
    """A 0% definitive prorrata is visible as settlement regularizacion, not silence."""
    result, diagnostic = buildprorrata_regularizacion_advisory(
        cuotas_soportadas_deducibles=Decimal("12000.00"),
        prorrata_provisional_pct=Decimal("80"),
        prorrata_definitiva_pct=Decimal("0"),
        operaciones_sin_derecho_deduccion=Decimal("100000"),
        regularizacion_year=2026,
        revision=_settlement_revision(),
    )

    assert result.prorrata_definitiva_pct == Decimal("0")
    assert result.direccion is RegularizacionProrrataDireccion.INGRESO
    assert diagnostic is not None
    assert diagnostic.binding_source is BindingSourceKind.PRORRATA_REGULARIZACION
    assert "casilla 44" in diagnostic.message


def test_fully_taxable_art94_no_volume_default_stays_quiet() -> None:
    """No prorrata-volume evidence leaves the full-deduction default without advisory noise."""
    applicability = derive_prorrata_applicability()
    missing_carry = build_prorrata_missing_provisional_advisory(
        applicability=applicability,
        provisional_resolution=_unresolved_prorrata(),
        ejercicio=2026,
        revision=_settlement_revision(),
    )
    result, regularizacion = buildprorrata_regularizacion_advisory(
        cuotas_soportadas_deducibles=Decimal("12000.00"),
        prorrata_provisional_pct=Decimal("100"),
        prorrata_definitiva_pct=Decimal("100"),
        operaciones_sin_derecho_deduccion=Decimal("0"),
        regularizacion_year=2026,
        revision=_settlement_revision(),
    )

    assert applicability.applies is False
    assert applicability.evidence_kinds == ()
    assert missing_carry is None
    assert regularizacion is None
    assert result.prorrata_definitiva_pct == Decimal("100")


def test_settlement_writeback_persists_observation_that_seeds_next_year_carried_entry(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    """Filing the settlement writes the register and lets year+1 carry from the stamped observation."""
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
            calculation_repository = CalculationRevisionCatalogueRepository(bucket_id=_BUCKET_ID)
            filing_repository = ModeloRecordCatalogueRepository(bucket_id=_BUCKET_ID)
            work_unit_repository = WorkUnitCatalogueRepository(bucket_id=_BUCKET_ID)
            prorrata_repository = ProrrataRegisterRepository(bucket_id=_BUCKET_ID)
            observation_repository = CalculationObservationRepository(objects=profile.repository)
            revision, work_unit = _seed_verified_m303_settlement(
                calculation_repository=calculation_repository,
                work_unit_repository=work_unit_repository,
                operation=operation,
            )

            persist_filed_revision(
                target=revision,
                work_unit=work_unit,
                work_units=work_unit_repository.load(),
                notes=None,
                actor="aeat.test.modelo.file",
                now=_T0 + timedelta(hours=2),
                calculation_repository=calculation_repository,
                filing_repository=filing_repository,
                work_unit_repository=work_unit_repository,
                bucket_event_repository=BucketEventHistoryRepository(),
                calculation_observation_repository=observation_repository,
                participation_index_repository=TransactionParticipationIndexRepository(bucket_id=_BUCKET_ID),
                prorrata_register_repository=prorrata_repository,
                result_disposition=ResultDisposition.NEGATIVA,
                iva_compensation_history_repository=IvaCompensationHistoryRepository(),
                operation=_authority_operation_for_test,
            )

            settled_entry = prorrata_repository.load().entry_for(_SETTLEMENT_YEAR)
            seed_evaluation = evaluate_carried_prior_definitiva_seed(
                ejercicio=_CARRY_YEAR,
                observation_repository=observation_repository,
                operation=_authority_operation_for_test,
            )

        assert settled_entry is not None
        assert settled_entry.definitive_percentage == Decimal("75")
        assert settled_entry.definitive_volume_con_derecho == Decimal("150000.00")
        assert settled_entry.definitive_volume_sin_derecho == Decimal("50000.00")
        assert seed_evaluation.findings == ()
        seed = seed_evaluation.seed
        assert seed is not None
        assert seed.source_modelo == Modelo("303").value
        assert seed.source_filing_year == _SETTLEMENT_YEAR
        assert seed.source_period == _SETTLEMENT_PERIOD
        assert seed.source_casilla_id == _PORCENTAJE_ID
        assert seed.stamped_revision_id == _m303_revision_id(filing_year=_SETTLEMENT_YEAR, period=_SETTLEMENT_PERIOD)
        assert seed.entry.ejercicio == _CARRY_YEAR
        assert seed.entry.provisional_percentage == Decimal("75")
        assert seed.entry.provisional_provenance == ProrrataProvisionalProvenance.from_registry(
            "carried_prior_definitiva"
        )
        assert seed.entry.source_observation_ref == "303:2026:4T"
