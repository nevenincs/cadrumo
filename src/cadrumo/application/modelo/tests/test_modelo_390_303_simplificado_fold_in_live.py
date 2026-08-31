"""Live 303/4T -> 390/0A immutable annual-summary handoff behaviour.

The annual simplificado values are a single frozen calculation input.  This
module uses the encrypted production catalogues, official registry snapshots,
and the live calculation mesh: no observation-backed scalar relation, mock, or
hand-authored calculation result is involved.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy import select

from ....adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....adapters.persistence.storage.secure_object_namespaces import MODELO_CALCULATION_REVISION_CATALOGUE_NAMESPACE
from ....adapters.persistence.storage.sql._orm import SecureObjectRow
from ....adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from ....application.calculations._m303_regimen_simplificado_annual_summary import (
    M303RegimenSimplificadoAnnualSummaryHandoffError,
)
from ....core.aggregation import BindingSourceKind
from ....core.casilla_id import CasillaId
from ....core.filing_projection_ref import M303RegimenSimplificadoFact
from ....core.period import Period
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.binding_selector_utils import selector_as_dict
from ....domain.calculations.registry.m303_orden_resolution import resolve_m303_regimen_simplificado_snapshot
from ....domain.calculations.registry.m303_regimen_simplificado_annual_summary_bindings import (
    m303_regimen_simplificado_annual_summary_requirement,
)
from ....domain.deadlines.models import IVARegime, TaxpayerProfile
from ....domain.filing_evidence import FilingEvidenceReference
from ....domain.iva.regimen_simplificado_rows import (
    ActividadAgricolaSimplificado,
    ActividadNoAgricolaSimplificado,
    EntradaModuloSimplificado,
    HechoActividadSimplificado,
    M303RegimenSimplificadoScope,
    M303RegimenSimplificadoScopeDecision,
    RegimenSimplificadoFilingRows,
)
from ....domain.modelos.calculation_repository import upsert_calculation_revision
from ....domain.modelos.calculation_revision import (
    M390_REGIMEN_SIMPLIFICADO_ANNUAL_SUMMARY_CASILLA_IDS,
    CalculationRevision,
    CalculationRevisionState,
    FilingInstanceEvidence,
    derive_calculation_revision_id,
)
from ....domain.modelos.filing_record import (
    ModeloRecord,
    ModeloRecordCatalogue,
    ModeloRecordStatus,
    derive_filing_record_id,
)
from ....domain.modelos.repository import upsert_work_unit
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from ....tests.filing_evidence import general_m303_filing_evidence, regimen_simplificado_filing_evidence
from ....tests.profile_capsule import seed_test_profile_record
from ....tests.registry_observations import registry_grounded_observations
from ....tests.secure_sql import mutate_encrypted_secure_object_json
from .._calculation_actions import calculate_modelo_revision_from_bucket_aggregation_with_diagnostics
from .._export import (
    ModeloExportCommand,
    export_modelo_revision,
)
from .._filing_actions import file_modelo_revision
from .._registry_helpers import assert_revision_content_integrity
from .._verification_actions import verify_modelo_revision
from ..work_lifecycle import create_work_unit

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "39000000-0000-4000-8000-000000000391"
_YEAR = 2025
_T0 = datetime(2026, 8, 14, 9, 0, tzinfo=UTC)
_T1 = datetime(2026, 8, 14, 10, 0, tzinfo=UTC)
_T2 = datetime(2026, 8, 14, 11, 0, tzinfo=UTC)
_TAX_ID = "12345678Z"
_SOURCE_CASILLA_IDS: tuple[CasillaId, ...] = ("51", "53", "52", "54", "55", "56", "57", "58")


def _store_ready_profile(secure_objects: SecureObjectRepository) -> None:
    seed_test_profile_record(
        UserProfileRecord(
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=_BUCKET_ID,
            facts=(
                UserProfileFact(path="identity.tax_id", value=_TAX_ID),
                UserProfileFact(path="identity.name", value="Test"),
                UserProfileFact(path="identity.surnames", value="Operator"),
                UserProfileFact(path="activities.description", value="activity"),
                UserProfileFact(path="tax_residence.ccaa", value="madrid"),
                UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
                UserProfileFact(path="iva.regime", value="SIMPLIFICADO"),
                UserProfileFact(path="iva.m303_regime_composition", value="simplified"),
                UserProfileFact(path="iva.redeme_enrolled", value=False),
                UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
                UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
                UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
                UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
                UserProfileFact(path="taxpayer_type.irpf_income_categories", value="actividad_economica"),
                UserProfileFact(path="irpf.estimation_regime", value="objetiva"),
                UserProfileFact(path="censo.activity_start_date", value=date(2020, 1, 1)),
            ),
            created_at=_T0,
            updated_at=_T0,
        )
    )


def _non_agricultural_source_evidence(*, declared_quantity: Decimal = Decimal("1")) -> FilingInstanceEvidence:
    period = Period.from_year_and_code(_YEAR, "4T")
    registry_snapshot = bundled_authority().snapshot("303", filing_year=_YEAR, period="4T")
    scope = M303RegimenSimplificadoScopeDecision(
        scope=M303RegimenSimplificadoScope.REGIMEN_SIMPLIFICADO_EVIDENCE_REQUIRED,
    )
    regimen_snapshot = resolve_m303_regimen_simplificado_snapshot(
        registry_snapshot=registry_snapshot,
        scope_decision=scope,
    )
    annual_activity = regimen_snapshot.orden.activities[0]
    assert annual_activity.kind == "no_agricola"
    assert annual_activity.iae_epigrafe is not None
    reference = FilingEvidenceReference(reference=regimen_snapshot.orden.source_ref)
    rows = RegimenSimplificadoFilingRows(
        ejercicio=_YEAR,
        activities=(
            ActividadNoAgricolaSimplificado(
                orden_id=annual_activity.orden_id,
                ejercicio=_YEAR,
                activity_id=annual_activity.orden_id,
                iae_epigrafe=annual_activity.iae_epigrafe,
                auxiliary_activity_indicator=annual_activity.auxiliary_activity_indicator,
                modulos=tuple(
                    EntradaModuloSimplificado(
                        module_identity=module.identity,
                        declared_quantity=declared_quantity,
                        evidence_reference=reference,
                    )
                    for module in annual_activity.modulos
                ),
                facts=tuple(
                    HechoActividadSimplificado(
                        fact=M303RegimenSimplificadoFact.CUOTA_DEVENGADA_OPERACIONES_CORRIENTES,
                        value=Decimal("1"),
                        evidence_reference=reference,
                    )
                    for _identity in annual_activity.applicable_fact_identities
                ),
                evidence_reference=reference,
            ),
        ),
    )
    regimen_evidence = regimen_simplificado_filing_evidence(
        period=period,
        scope_decision=scope,
        rows=rows,
        regimen_snapshot=regimen_snapshot,
        dana_2024_eligibility=None,
    )
    baseline = general_m303_filing_evidence(period, reference="test:s84:source")
    return baseline.model_copy(
        update={
            "m303": baseline.m303.model_copy(
                update={"regimen_simplificado": regimen_evidence},
            ),
        },
    )


def _source_values(evidence: FilingInstanceEvidence) -> Mapping[CasillaId, Decimal]:
    result = evidence.m303.regimen_simplificado.calculation_result
    assert len(result.activities) == 1
    cuota_resultante = result.activities[0].cuota_resultante
    return {
        "51": Decimal("11"),
        "53": Decimal("7"),
        "52": Decimal("5"),
        "54": cuota_resultante + Decimal("23"),
        "55": Decimal("4"),
        "56": Decimal("2"),
        "57": Decimal("6"),
        "58": cuota_resultante + Decimal("17"),
    }


def _workflow_profile() -> TaxpayerProfile:
    return TaxpayerProfile(
        tax_id=_TAX_ID,
        iva_regime=IVARegime.SIMPLIFICADO,
        has_employees=False,
        pays_rent_with_retencion=False,
        does_intracomunitario=False,
        bienes_extranjero_above_threshold=False,
        activity_start_date=date(_YEAR, 1, 1),
    )


def _persist_presentado_source(
    secure_objects: SecureObjectRepository,
) -> tuple[
    WorkUnitCatalogueRepository,
    CalculationRevisionCatalogueRepository,
    ModeloRecordCatalogueRepository,
    CalculationRevision,
]:
    """Persist the exact one 303/4T source with its current filed pointer."""
    wu_repo = WorkUnitCatalogueRepository(objects=secure_objects)
    cr_repo = CalculationRevisionCatalogueRepository(objects=secure_objects)
    filing_repo = ModeloRecordCatalogueRepository(objects=secure_objects)
    snapshot = bundled_authority().snapshot("303", filing_year=_YEAR, period="4T")
    source_work_unit = create_work_unit(
        bucket_id=_BUCKET_ID,
        modelo="303",
        filing_year=_YEAR,
        period=Period.from_year_and_code(_YEAR, "4T"),
        revision_id=snapshot.revision.id,
        repository=wu_repo,
        clock=_T0,
    )
    evidence = _non_agricultural_source_evidence()
    casilla_values = _source_values(evidence)
    calculation_revision_id = derive_calculation_revision_id(
        work_unit_id=source_work_unit.work_unit_id,
        input_values_by_casilla_id={},
        binding_overrides={},
        casilla_values=casilla_values,
        filing_instance_evidence=evidence,
        source_provenance=(),
    )
    source_revision = CalculationRevision(
        calculation_revision_id=calculation_revision_id,
        work_unit_id=source_work_unit.work_unit_id,
        state=CalculationRevisionState.PRESENTADO,
        casilla_values=casilla_values,
        observations=registry_grounded_observations(
            modelo="303",
            filing_year=_YEAR,
            period="4T",
            casilla_values=casilla_values,
        ),
        filing_instance_evidence=evidence,
        created_at=_T0,
        updated_at=_T2,
        verified_at=_T1,
        verified_by="operator",
        filed_at=_T2,
        filed_by="operator",
        source_provenance=(),
    )
    filing_record_id = derive_filing_record_id(
        work_unit_id=source_work_unit.work_unit_id,
        calculation_revision_id=source_revision.calculation_revision_id,
        filed_by="operator",
    )
    filing = ModeloRecord(
        filing_record_id=filing_record_id,
        work_unit_id=source_work_unit.work_unit_id,
        calculation_revision_id=source_revision.calculation_revision_id,
        bucket_id=_BUCKET_ID,
        modelo="303",
        filing_year=_YEAR,
        period=Period.from_year_and_code(_YEAR, "4T"),
        filed_at=_T2,
        filed_by="operator",
        status=ModeloRecordStatus.VIGENTE,
    )
    cr_repo.save(upsert_calculation_revision(cr_repo.load(), source_revision))
    filing_repo.save(ModeloRecordCatalogue(records={filing.filing_record_id: filing}))
    source_work_unit = source_work_unit.model_copy(
        update={
            "current_calculation_revision_id": source_revision.calculation_revision_id,
            "filed_calculation_revision_id": source_revision.calculation_revision_id,
            "current_filing_record_id": filing.filing_record_id,
            "updated_at": _T2,
        },
    )
    wu_repo.save(upsert_work_unit(wu_repo.load(), source_work_unit))
    return wu_repo, cr_repo, filing_repo, source_revision


def _replace_source_with_new_filed_revision(
    *,
    work_units: WorkUnitCatalogueRepository,
    calculations: CalculationRevisionCatalogueRepository,
    filings: ModeloRecordCatalogueRepository,
    previous: CalculationRevision,
) -> CalculationRevision:
    """Replace the live 303 source through the real revision and filing catalogues."""
    source_work_unit = work_units.load().get(previous.work_unit_id)
    assert source_work_unit is not None
    previous_filing_id = source_work_unit.current_filing_record_id
    assert previous_filing_id is not None
    evidence = _non_agricultural_source_evidence(declared_quantity=Decimal("2"))
    casilla_values = _source_values(evidence)
    replacement_id = derive_calculation_revision_id(
        work_unit_id=source_work_unit.work_unit_id,
        input_values_by_casilla_id={},
        binding_overrides={},
        casilla_values=casilla_values,
        filing_instance_evidence=evidence,
        source_provenance=(),
    )
    replacement = CalculationRevision(
        calculation_revision_id=replacement_id,
        work_unit_id=source_work_unit.work_unit_id,
        state=CalculationRevisionState.PRESENTADO,
        casilla_values=casilla_values,
        observations=registry_grounded_observations(
            modelo="303",
            filing_year=_YEAR,
            period="4T",
            casilla_values=casilla_values,
        ),
        filing_instance_evidence=evidence,
        created_at=_T0,
        updated_at=_T2,
        verified_at=_T1,
        verified_by="operator",
        filed_at=_T2,
        filed_by="operator-replacement",
        source_provenance=(),
    )
    replacement_filing_id = derive_filing_record_id(
        work_unit_id=source_work_unit.work_unit_id,
        calculation_revision_id=replacement.calculation_revision_id,
        filed_by="operator-replacement",
    )
    replacement_filing = ModeloRecord(
        filing_record_id=replacement_filing_id,
        work_unit_id=source_work_unit.work_unit_id,
        calculation_revision_id=replacement.calculation_revision_id,
        bucket_id=_BUCKET_ID,
        modelo="303",
        filing_year=_YEAR,
        period=Period.from_year_and_code(_YEAR, "4T"),
        filed_at=_T2,
        filed_by="operator-replacement",
        status=ModeloRecordStatus.VIGENTE,
    )
    previous_filing = filings.load().get(previous_filing_id)
    assert previous_filing is not None
    superseded = previous_filing.model_copy(
        update={
            "status": ModeloRecordStatus.SUPERSEDIDO,
            "superseded_at": _T2,
            "superseded_by_filing_record_id": replacement_filing_id,
        },
    )
    calculations.save(upsert_calculation_revision(calculations.load(), replacement))
    filings.save(
        ModeloRecordCatalogue(
            records={
                superseded.filing_record_id: superseded,
                replacement_filing.filing_record_id: replacement_filing,
            },
        )
    )
    work_units.save(
        upsert_work_unit(
            work_units.load(),
            source_work_unit.model_copy(
                update={
                    "current_calculation_revision_id": replacement.calculation_revision_id,
                    "filed_calculation_revision_id": replacement.calculation_revision_id,
                    "current_filing_record_id": replacement_filing.filing_record_id,
                    "updated_at": _T2,
                },
            ),
        )
    )
    return replacement


def _calculate_m390_annual(
    secure_objects: SecureObjectRepository,
    *,
    work_units: WorkUnitCatalogueRepository,
    calculations: CalculationRevisionCatalogueRepository,
    filings: ModeloRecordCatalogueRepository,
):
    snapshot = bundled_authority().snapshot("390", filing_year=_YEAR, period="0A")
    work_unit = create_work_unit(
        bucket_id=_BUCKET_ID,
        modelo="390",
        filing_year=_YEAR,
        period=Period.from_year_and_code(_YEAR, "0A"),
        revision_id=snapshot.revision.id,
        repository=work_units,
        clock=_T0,
    )
    return calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
        work_unit.work_unit_id,
        binding_values={},
        work_unit_repository=work_units,
        calculation_repository=calculations,
        filing_repository=filings,
        transaction_repository=TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects),
        invoice_repository=InvoiceCatalogueRepository(objects=secure_objects),
        clock=_T2,
    )


def test_m390_persists_exact_ten_value_handoff_from_one_filed_current_m303_4t_revision(
    secure_objects: SecureObjectRepository,
) -> None:
    """A real PRESENTADO M303/4T source arrives as boxes 74--83, once only."""
    _store_ready_profile(secure_objects)
    work_units, calculations, filings, source = _persist_presentado_source(secure_objects)

    result = _calculate_m390_annual(
        secure_objects,
        work_units=work_units,
        calculations=calculations,
        filings=filings,
    )
    handoff = result.revision.m303_regimen_simplificado_annual_summary_handoff
    assert handoff is not None
    assert handoff.source_calculation_revision_id == source.calculation_revision_id
    assert handoff.target_calculation_revision_id == result.revision.calculation_revision_id
    assert CalculationRevision.model_validate_json(result.revision.model_dump_json()) == result.revision
    persisted = calculations.load().get(result.revision.calculation_revision_id)
    assert persisted is not None
    assert persisted == result.revision
    assert_revision_content_integrity(persisted)

    source_values = source.casilla_values
    source_evidence = source.filing_instance_evidence
    assert source_evidence is not None
    source_result = source_evidence.m303.regimen_simplificado.calculation_result
    expected = {
        M390_REGIMEN_SIMPLIFICADO_ANNUAL_SUMMARY_CASILLA_IDS[0]: source_result.activities[0].cuota_resultante,
        M390_REGIMEN_SIMPLIFICADO_ANNUAL_SUMMARY_CASILLA_IDS[1]: Decimal("0"),
        M390_REGIMEN_SIMPLIFICADO_ANNUAL_SUMMARY_CASILLA_IDS[2]: source_values["51"],
        M390_REGIMEN_SIMPLIFICADO_ANNUAL_SUMMARY_CASILLA_IDS[3]: source_values["53"],
        M390_REGIMEN_SIMPLIFICADO_ANNUAL_SUMMARY_CASILLA_IDS[4]: source_values["52"],
        M390_REGIMEN_SIMPLIFICADO_ANNUAL_SUMMARY_CASILLA_IDS[5]: source_values["54"],
        M390_REGIMEN_SIMPLIFICADO_ANNUAL_SUMMARY_CASILLA_IDS[6]: source_values["55"],
        M390_REGIMEN_SIMPLIFICADO_ANNUAL_SUMMARY_CASILLA_IDS[7]: source_values["56"],
        M390_REGIMEN_SIMPLIFICADO_ANNUAL_SUMMARY_CASILLA_IDS[8]: source_values["57"],
        M390_REGIMEN_SIMPLIFICADO_ANNUAL_SUMMARY_CASILLA_IDS[9]: source_values["58"],
    }
    assert dict(handoff.values) == expected
    assert {casilla_id: result.revision.casilla_values[casilla_id] for casilla_id in expected} == expected
    assert not result.revision.relation_overrides
    target_snapshot = bundled_authority().snapshot("390", filing_year=_YEAR, period="0A")
    requirement = m303_regimen_simplificado_annual_summary_requirement(target_snapshot.revision)
    assert requirement is not None
    assert {
        binding_id: Decimal(result.revision.binding_overrides[binding_id])
        for binding_id in requirement.binding_ids_by_summary_casilla_id.values()
    } == {
        binding_id: expected[casilla_id]
        for casilla_id, binding_id in requirement.binding_ids_by_summary_casilla_id.items()
    }
    provenance = tuple(
        item
        for item in result.revision.source_provenance
        if item.binding_source is BindingSourceKind.M303_REGIMEN_SIMPLIFICADO_ANNUAL_SUMMARY
    )
    assert len(provenance) == 1
    assert provenance[0].fingerprint == handoff.digest


@pytest.mark.parametrize("corruption", ("alter_value", "delete_digest"))
def test_m390_encrypted_calculation_catalogue_refuses_a_corrupted_populated_handoff(
    secure_objects: SecureObjectRepository,
    corruption: str,
) -> None:
    """Deleting or changing persisted non-default handoff data fails on real load.

    This is the persistence-boundary anti-tautology proof for the immutable
    annual-summary carrier: the calculation catalogue is saved through the
    production encrypted SQLite repository, then one encrypted JSON payload is
    changed under its actual AEAD binding.  The next repository load must not
    silently accept the altered typed handoff.
    """
    _store_ready_profile(secure_objects)
    work_units, calculations, filings, _source = _persist_presentado_source(secure_objects)
    target = _calculate_m390_annual(
        secure_objects,
        work_units=work_units,
        calculations=calculations,
        filings=filings,
    ).revision
    handoff = target.m303_regimen_simplificado_annual_summary_handoff
    assert handoff is not None
    assert handoff.target_calculation_revision_id == target.calculation_revision_id
    assert handoff.values[M390_REGIMEN_SIMPLIFICADO_ANNUAL_SUMMARY_CASILLA_IDS[0]] != Decimal("0")

    definition = MODELO_CALCULATION_REVISION_CATALOGUE_NAMESPACE
    statement = select(SecureObjectRow).where(
        SecureObjectRow.namespace == definition.namespace,
        SecureObjectRow.object_key == definition.require_default_object_key(),
    )

    def mutate(document: dict[str, object]) -> None:
        payload = document["payload"]
        assert isinstance(payload, dict), "calculation catalogue envelope must carry an object payload"
        revisions = payload["revisions"]
        assert isinstance(revisions, dict), "calculation catalogue payload must carry its revision mapping"
        stored_target = revisions[target.calculation_revision_id]
        assert isinstance(stored_target, dict), "fixture must persist the calculated Modelo 390 revision"
        stored_handoff = stored_target["m303_regimen_simplificado_annual_summary_handoff"]
        assert isinstance(stored_handoff, dict), "fixture must persist the populated annual-summary handoff"
        if corruption == "alter_value":
            values = stored_handoff["values"]
            assert isinstance(values, dict), "fixture must persist the handoff's ten-value mapping"
            casilla_id = M390_REGIMEN_SIMPLIFICADO_ANNUAL_SUMMARY_CASILLA_IDS[0]
            assert values[casilla_id] != "999999", "corruption value must differ from the stored handoff"
            values[casilla_id] = "999999"
            return
        assert corruption == "delete_digest"
        assert "digest" in stored_handoff, "fixture must persist the handoff digest for this proof"
        del stored_handoff["digest"]

    mutate_encrypted_secure_object_json(
        secure_objects._engine,
        row_statement=statement,
        mutate=mutate,
    )

    with pytest.raises(ValidationError):
        calculations.load()


def test_m390_refuses_a_source_when_current_calculation_pointer_diverges_from_filed(
    secure_objects: SecureObjectRepository,
) -> None:
    """A filed source is invalid as soon as the live pointer no longer names it."""
    _store_ready_profile(secure_objects)
    work_units, calculations, filings, source = _persist_presentado_source(secure_objects)
    target = _calculate_m390_annual(
        secure_objects,
        work_units=work_units,
        calculations=calculations,
        filings=filings,
    ).revision
    source_work_unit = work_units.load().get(source.work_unit_id)
    assert source_work_unit is not None
    work_units.save(
        upsert_work_unit(
            work_units.load(),
            source_work_unit.model_copy(
                update={"current_calculation_revision_id": "d" * 64, "updated_at": _T2},
            ),
        )
    )

    with pytest.raises(M303RegimenSimplificadoAnnualSummaryHandoffError, match="current calculation pointer"):
        verify_modelo_revision(
            target.calculation_revision_id,
            actor="operator",
            workflow_profile=_workflow_profile(),
            work_unit_repository=work_units,
            calculation_repository=calculations,
            filing_repository=filings,
        )


def test_m390_refuses_a_non_presentado_source_calculation_revision(
    secure_objects: SecureObjectRepository,
) -> None:
    """VERIFICADO_COMPLETO is not a substitute for the filed PRESENTADO source."""
    _store_ready_profile(secure_objects)
    work_units, calculations, filings, source = _persist_presentado_source(secure_objects)
    target = _calculate_m390_annual(
        secure_objects,
        work_units=work_units,
        calculations=calculations,
        filings=filings,
    ).revision
    non_presentado = source.model_copy(
        update={
            "state": CalculationRevisionState.VERIFICADO_COMPLETO,
            "updated_at": _T1,
            "filed_at": None,
            "filed_by": None,
        },
    )
    calculations.save(upsert_calculation_revision(calculations.load(), non_presentado))

    with pytest.raises(M303RegimenSimplificadoAnnualSummaryHandoffError, match="PRESENTADO"):
        verify_modelo_revision(
            target.calculation_revision_id,
            actor="operator",
            workflow_profile=_workflow_profile(),
            work_unit_repository=work_units,
            calculation_repository=calculations,
            filing_repository=filings,
        )


def test_m390_refuses_post_calculate_non_vigente_source_filing_record(
    secure_objects: SecureObjectRepository,
) -> None:
    """A target draft cannot be verified after its filed source receipt is superseded."""
    _store_ready_profile(secure_objects)
    work_units, calculations, filings, source = _persist_presentado_source(secure_objects)
    target = _calculate_m390_annual(
        secure_objects,
        work_units=work_units,
        calculations=calculations,
        filings=filings,
    ).revision
    source_work_unit = work_units.load().get(source.work_unit_id)
    assert source_work_unit is not None
    original_filing_id = source_work_unit.current_filing_record_id
    assert original_filing_id is not None
    original_filing = filings.load().get(original_filing_id)
    assert original_filing is not None
    successor_id = derive_filing_record_id(
        work_unit_id=source.work_unit_id,
        calculation_revision_id=source.calculation_revision_id,
        filed_by="operator-successor",
    )
    successor = ModeloRecord(
        filing_record_id=successor_id,
        work_unit_id=source.work_unit_id,
        calculation_revision_id=source.calculation_revision_id,
        bucket_id=_BUCKET_ID,
        modelo="303",
        filing_year=_YEAR,
        period=Period.from_year_and_code(_YEAR, "4T"),
        filed_at=_T2,
        filed_by="operator-successor",
        status=ModeloRecordStatus.VIGENTE,
    )
    filings.save(
        ModeloRecordCatalogue(
            records={
                original_filing_id: original_filing.model_copy(
                    update={
                        "status": ModeloRecordStatus.SUPERSEDIDO,
                        "superseded_at": _T2,
                        "superseded_by_filing_record_id": successor_id,
                    },
                ),
                successor_id: successor,
            },
        )
    )

    with pytest.raises(M303RegimenSimplificadoAnnualSummaryHandoffError, match="VIGENTE filing record"):
        verify_modelo_revision(
            target.calculation_revision_id,
            actor="operator",
            workflow_profile=_workflow_profile(),
            work_unit_repository=work_units,
            calculation_repository=calculations,
            filing_repository=filings,
        )


def test_m390_revalidates_source_result_and_evidence_replacement_before_verify_file_and_export(
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
) -> None:
    """No later action trusts a stale carrier after source result/evidence replacement."""
    _store_ready_profile(secure_objects)
    work_units, calculations, filings, source = _persist_presentado_source(secure_objects)
    target = _calculate_m390_annual(
        secure_objects,
        work_units=work_units,
        calculations=calculations,
        filings=filings,
    ).revision
    replacement = _replace_source_with_new_filed_revision(
        work_units=work_units,
        calculations=calculations,
        filings=filings,
        previous=source,
    )
    replacement_evidence = replacement.filing_instance_evidence
    source_evidence = source.filing_instance_evidence
    assert replacement_evidence is not None
    assert source_evidence is not None
    assert replacement_evidence.m303.regimen_simplificado.calculation_result.digest != (
        source_evidence.m303.regimen_simplificado.calculation_result.digest
    )

    with pytest.raises(M303RegimenSimplificadoAnnualSummaryHandoffError, match="no longer matches"):
        verify_modelo_revision(
            target.calculation_revision_id,
            actor="operator",
            workflow_profile=_workflow_profile(),
            work_unit_repository=work_units,
            calculation_repository=calculations,
            filing_repository=filings,
        )

    verified_target = target.model_copy(
        update={
            "state": CalculationRevisionState.VERIFICADO_COMPLETO,
            "verified_at": _T2,
            "verified_by": "operator",
            "updated_at": _T2,
        },
    )
    calculations.save(upsert_calculation_revision(calculations.load(), verified_target))
    with pytest.raises(M303RegimenSimplificadoAnnualSummaryHandoffError, match="no longer matches"):
        file_modelo_revision(
            verified_target.calculation_revision_id,
            actor="operator",
            workflow_profile=_workflow_profile(),
            work_unit_repository=work_units,
            calculation_repository=calculations,
            filing_repository=filings,
        )
    with pytest.raises(M303RegimenSimplificadoAnnualSummaryHandoffError, match="no longer matches"):
        export_modelo_revision(
            ModeloExportCommand(
                calculation_revision_id=verified_target.calculation_revision_id,
                output_path=tmp_path / "m390-stale-source.txt",
                actor="operator",
            ),
            workflow_profile=_workflow_profile(),
            work_unit_repository=work_units,
            calculation_repository=calculations,
            filing_repository=filings,
        )


def test_m390_registry_requires_all_ten_endpoints_and_rejects_the_retired_scalar_path() -> None:
    """The registry has one typed value-arrival family, never a box-79 bridge."""
    snapshot = bundled_authority().snapshot("390", filing_year=_YEAR, period="0A")
    requirement = m303_regimen_simplificado_annual_summary_requirement(snapshot.revision)
    assert requirement is not None
    assert set(requirement.binding_ids_by_summary_casilla_id) == set(
        M390_REGIMEN_SIMPLIFICADO_ANNUAL_SUMMARY_CASILLA_IDS,
    )
    assert requirement.source_casilla_ids == _SOURCE_CASILLA_IDS
    assert "modelo-390-rel-303-cuota-devengada-simplificado" not in {
        relation.id for relation in snapshot.revision.relations
    }
    assert "modelo-390-prev-303-cuota-devengada-simplificado" not in {
        binding.id for binding in snapshot.revision.bindings
    }
    assert not any(
        binding.source is BindingSourceKind.RELATION_PREFILL
        and selector_as_dict(binding).get("source_modelo") == "303"
        and selector_as_dict(binding).get("source_casilla_id") == "54"
        for binding in snapshot.revision.bindings
    )


def test_agricultural_rows_remain_an_evidence_bearing_refusal_while_empty_cohort_is_zero() -> None:
    """An unavailable official crosswalk cannot be turned into a zero default."""
    period = Period.from_year_and_code(_YEAR, "4T")
    empty = general_m303_filing_evidence(period, reference="test:s84:proven-empty")
    assert empty.m303.regimen_simplificado.calculation_result.activities == ()

    snapshot = bundled_authority().snapshot("303", filing_year=_YEAR, period="4T")
    scope = M303RegimenSimplificadoScopeDecision(
        scope=M303RegimenSimplificadoScope.REGIMEN_SIMPLIFICADO_EVIDENCE_REQUIRED,
    )
    regimen_snapshot = resolve_m303_regimen_simplificado_snapshot(
        registry_snapshot=snapshot,
        scope_decision=scope,
    )
    agricultural = ActividadAgricolaSimplificado(
        orden_id="test:s84:agricultural",
        ejercicio=_YEAR,
        activity_id="test:s84:agricultural",
        activity_code=regimen_snapshot.orden.agricultural_authority.quota_indexes[0].activity_name,
        facts=(
            HechoActividadSimplificado(
                fact=M303RegimenSimplificadoFact.CUOTA_DEVENGADA,
                value=Decimal("1"),
                evidence_reference=FilingEvidenceReference(reference=regimen_snapshot.orden.source_ref),
            ),
        ),
        evidence_reference=FilingEvidenceReference(reference=regimen_snapshot.orden.source_ref),
    )
    from ....application.calculations._m303_regimen_simplificado import M303RegimenSimplificadoCalculationError

    with pytest.raises(M303RegimenSimplificadoCalculationError, match="two_digit_agricultural_crosswalk"):
        regimen_simplificado_filing_evidence(
            period=period,
            scope_decision=scope,
            rows=RegimenSimplificadoFilingRows(ejercicio=_YEAR, activities=(agricultural,)),
            regimen_snapshot=regimen_snapshot,
            dana_2024_eligibility=None,
        )


def test_handoff_digest_and_post_identity_stamp_refuse_tampering() -> None:
    """Carrier bytes survive a round trip but reject altered values or target id."""
    evidence = _non_agricultural_source_evidence()
    values = _source_values(evidence)
    source_result = evidence.m303.regimen_simplificado.calculation_result
    from ....domain.modelos.calculation_revision import M303RegimenSimplificadoAnnualSummaryHandoff

    handoff = M303RegimenSimplificadoAnnualSummaryHandoff.assembled(
        source_bucket_id=_BUCKET_ID,
        source_work_unit_id="a" * 64,
        source_calculation_revision_id="b" * 64,
        source_registry_revision_id="2010-y-siguientes",
        source_filing_year=_YEAR,
        source_result_digest=source_result.digest,
        source_evidence_references=tuple(
            reference for activity in source_result.activities for reference in activity.evidence_references
        ),
        target_bucket_id=_BUCKET_ID,
        target_work_unit_id="c" * 64,
        target_registry_revision_id="2010-y-siguientes",
        target_filing_year=_YEAR,
        values={
            M390_REGIMEN_SIMPLIFICADO_ANNUAL_SUMMARY_CASILLA_IDS[0]: source_result.activities[0].cuota_resultante,
            M390_REGIMEN_SIMPLIFICADO_ANNUAL_SUMMARY_CASILLA_IDS[1]: Decimal("0"),
            M390_REGIMEN_SIMPLIFICADO_ANNUAL_SUMMARY_CASILLA_IDS[2]: values["51"],
            M390_REGIMEN_SIMPLIFICADO_ANNUAL_SUMMARY_CASILLA_IDS[3]: values["53"],
            M390_REGIMEN_SIMPLIFICADO_ANNUAL_SUMMARY_CASILLA_IDS[4]: values["52"],
            M390_REGIMEN_SIMPLIFICADO_ANNUAL_SUMMARY_CASILLA_IDS[5]: values["54"],
            M390_REGIMEN_SIMPLIFICADO_ANNUAL_SUMMARY_CASILLA_IDS[6]: values["55"],
            M390_REGIMEN_SIMPLIFICADO_ANNUAL_SUMMARY_CASILLA_IDS[7]: values["56"],
            M390_REGIMEN_SIMPLIFICADO_ANNUAL_SUMMARY_CASILLA_IDS[8]: values["57"],
            M390_REGIMEN_SIMPLIFICADO_ANNUAL_SUMMARY_CASILLA_IDS[9]: values["58"],
        },
    )
    assert type(handoff).model_validate_json(handoff.model_dump_json()) == handoff
    tampered = handoff.model_dump(mode="python")
    tampered["values"][M390_REGIMEN_SIMPLIFICADO_ANNUAL_SUMMARY_CASILLA_IDS[2]] = Decimal("12")
    with pytest.raises(ValidationError, match="digest"):
        type(handoff).model_validate(tampered)
