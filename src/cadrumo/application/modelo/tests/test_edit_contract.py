"""Full-journey contract proofs for the Modelo Edit Contract V1 facade.

Complements the per-module tests (`test_edit_models.py`, `test_edit_services.py`,
`test_edit_execution.py`, `test_revision_persistence_guarded_writes.py`,
`test_modelos_edit_receipts.py`) rather than repeating them: this module
covers the facade's own new logic (the UNMEASURED mutation-capability
projection) and the end-to-end properties that only show up across a full
admit-parse-preflight-apply journey -- duplicate-result confirmation,
redeclaration, and sensitive non-retention.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_edit_receipts import ModeloEditReceiptRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from ....core.period import Period
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.modelos.calculation_revision import CalculationRevisionCatalogue
from ....domain.modelos.codes import ModeloCode
from ....domain.modelos.work_unit import WorkUnit, WorkUnitCatalogue, derive_work_unit_id
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from ....tests.profile_capsule import seed_test_profile_record
from ....tests.secure_sql import isolated_runtime_profile
from ...operations.registry import OperationSchemaIdentityV1
from .._edit_execution import apply_modelo_edit
from .._edit_facade import project_modelo_edit_mutation_capability
from .._edit_models import (
    ModeloEditAdmissionRequestV1,
    ModeloEditAdmittedV1,
    ModeloEditApplyRequestV1,
    ModeloEditExecutionUpdatedV1,
    ModeloEditMutationFamily,
    ModeloEditScalarAddressV1,
    ModeloEditScalarIntentKind,
    ModeloEditSubmissionV1,
    ModeloEditWritableScalarSurfaceEntryV1,
    ModeloMutationCapabilityRequestV1,
    ModeloScalarEditIntentV1,
)
from .._edit_services import admit_modelo_edit, modelo_edit_request_schema_identity, modelo_edit_result_schema_identity
from ..edit_contract import ModeloEditCompatibilityTupleV1
from ..work_addressing import ModeloExactWorkUnitTarget
from ..workspace_models import (
    ModeloWorkspaceCapabilityDisposition,
    ModeloWorkspaceExactWorkUnitTargetV1,
    ModeloWorkspaceTargetV1,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_BUCKET_ID = "0f629c46-1dc8-4cb1-8d02-aa0ee4f45a44"
_MODELO = "131"
_FILING_YEAR = 2025
_PERIOD_CODE = "1T"
_DIGEST = "a" * 64
_OPERATION_ID = "0" * 64
_CLOCK = datetime(2026, 1, 10, tzinfo=UTC)


def _seed_minimal_profile(objects: SecureObjectRepository) -> None:
    seed_test_profile_record(
        UserProfileRecord(
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=_BUCKET_ID,
            facts=(
                UserProfileFact(path="identity.tax_id", value="12345678Z"),
                UserProfileFact(path="activities.description", value="Spanish rental income"),
                UserProfileFact(path="iva.regime", value="GENERAL"),
                UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
                UserProfileFact(path="iva.m303_regime_composition", value="general"),
                UserProfileFact(path="iva.redeme_enrolled", value=False),
                UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
                UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
                UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
            ),
            created_at=_CLOCK,
            updated_at=_CLOCK,
        )
    )


def _schema_identity() -> OperationSchemaIdentityV1:
    return OperationSchemaIdentityV1(schema_id="modelo.edit.contract", schema_version=1, schema_fingerprint=_DIGEST)


def _compatibility() -> ModeloEditCompatibilityTupleV1:
    return ModeloEditCompatibilityTupleV1(
        contract_set_digest=_DIGEST,
        operation_definition_id="modelo.calculate",
        definition_contract_digest=_DIGEST,
        request_schema=modelo_edit_request_schema_identity(),
        result_schema=modelo_edit_result_schema_identity(),
        review_projection_contract_version=None,
        review_schema=None,
        workspace_refresh_target_schema=_schema_identity(),
        financial_operand_schema=_schema_identity(),
    )


def _period() -> Period:
    return Period.from_year_and_code(_FILING_YEAR, _PERIOD_CODE)


def _work_unit() -> WorkUnit:
    period = _period()
    revision_id = (
        bundled_authority().snapshot(_MODELO, filing_year=_FILING_YEAR, period=period.registry_token).revision.id
    )
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=_BUCKET_ID, modelo=_MODELO, filing_year=_FILING_YEAR, period=period, revision_id=revision_id
        ),
        bucket_id=_BUCKET_ID,
        modelo=ModeloCode(_MODELO),
        filing_year=_FILING_YEAR,
        period=period,
        revision_id=revision_id,
        name=f"{_MODELO}-{_FILING_YEAR}-{period.registry_token}",
        created_at=_CLOCK,
        updated_at=_CLOCK,
    )


def _target_for(work_unit: WorkUnit) -> ModeloWorkspaceTargetV1:
    return ModeloWorkspaceExactWorkUnitTargetV1(
        target=ModeloExactWorkUnitTarget(work_unit_id=work_unit.work_unit_id, bucket_id=work_unit.bucket_id)
    )


def _admit(
    work_unit: WorkUnit,
    *,
    work_catalogue: WorkUnitCatalogue,
    calculation_catalogue: CalculationRevisionCatalogue | None = None,
) -> ModeloEditAdmittedV1:
    calculation_catalogue = (
        calculation_catalogue if calculation_catalogue is not None else CalculationRevisionCatalogue()
    )
    result = admit_modelo_edit(
        ModeloEditAdmissionRequestV1(target=_target_for(work_unit), mutation_family=ModeloEditMutationFamily.CALCULATE),
        bucket_id=_BUCKET_ID,
        work_catalogue=work_catalogue,
        calculation_catalogue=calculation_catalogue,
        compatibility=_compatibility(),
    )
    assert isinstance(result, ModeloEditAdmittedV1)
    return result


def test_mutation_capability_is_unmeasured_for_a_resolvable_target() -> None:
    """The V1 facade never advertises AVAILABLE without a green C3 receipt."""
    work_unit = _work_unit()
    work_catalogue = WorkUnitCatalogue.from_work_units((work_unit,))
    projection = project_modelo_edit_mutation_capability(
        ModeloMutationCapabilityRequestV1(target=_target_for(work_unit)),
        bucket_id=_BUCKET_ID,
        work_catalogue=work_catalogue,
    )
    assert len(projection.rows) == 1
    assert projection.rows[0].disposition is ModeloWorkspaceCapabilityDisposition.UNMEASURED
    assert projection.rows[0].operation_definition_id is None


def test_mutation_capability_is_empty_for_an_unresolvable_target() -> None:
    """An absent target projects no fabricated row, just an empty set."""
    target = ModeloWorkspaceExactWorkUnitTargetV1(
        target=ModeloExactWorkUnitTarget(work_unit_id="0" * 64, bucket_id=_BUCKET_ID)
    )
    projection = project_modelo_edit_mutation_capability(
        ModeloMutationCapabilityRequestV1(target=target),
        bucket_id=_BUCKET_ID,
        work_catalogue=WorkUnitCatalogue(),
    )
    assert projection.rows == ()


def _apply(
    *,
    work_unit_repository: WorkUnitCatalogueRepository,
    calculation_repository: CalculationRevisionCatalogueRepository,
    bucket_event_repository: BucketEventHistoryRepository,
    receipt_repository: ModeloEditReceiptRepository,
    value: str,
):
    admitted = _admit(
        _work_unit(),
        work_catalogue=work_unit_repository.load(),
        calculation_catalogue=calculation_repository.load(),
    )
    baseline = admitted.baseline
    scalar_entry = next(e for e in baseline.permitted_surface if isinstance(e, ModeloEditWritableScalarSurfaceEntryV1))
    submission = ModeloEditSubmissionV1(
        baseline=baseline,
        mutation_family=ModeloEditMutationFamily.CALCULATE,
        scalar_intents=(
            ModeloScalarEditIntentV1(
                address=ModeloEditScalarAddressV1(casilla_id=scalar_entry.casilla_id),
                kind=ModeloEditScalarIntentKind.SET_TYPED_VALUE,
                value=value,
            ),
        ),
    )
    return apply_modelo_edit(
        ModeloEditApplyRequestV1(operation_id=_OPERATION_ID, submission=submission),
        work_unit_repository=work_unit_repository,
        calculation_repository=calculation_repository,
        bucket_event_repository=bucket_event_repository,
        receipt_repository=receipt_repository,
        now=datetime(2026, 1, 10, 6, 0, tzinfo=UTC),
        result_destination="modelo/131/2025/1T/edit-result",
    ), scalar_entry.casilla_id


def test_a_duplicate_resubmission_confirms_the_pointer_without_a_fresh_bucket_event(tmp_path: Path) -> None:
    """Resubmitting the identical edit twice is the duplicate-result path, not a second write."""
    work_unit = _work_unit()

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        _seed_minimal_profile(profile.repository)
        work_unit_repository = WorkUnitCatalogueRepository(objects=profile.repository)
        calculation_repository = CalculationRevisionCatalogueRepository(objects=profile.repository)
        bucket_event_repository = BucketEventHistoryRepository(objects=profile.repository)
        receipt_repository = ModeloEditReceiptRepository(objects=profile.repository)
        work_unit_repository.save(WorkUnitCatalogue.from_work_units((work_unit,)))

        first, _ = _apply(
            work_unit_repository=work_unit_repository,
            calculation_repository=calculation_repository,
            bucket_event_repository=bucket_event_repository,
            receipt_repository=receipt_repository,
            value="150.00",
        )
        second, _ = _apply(
            work_unit_repository=work_unit_repository,
            calculation_repository=calculation_repository,
            bucket_event_repository=bucket_event_repository,
            receipt_repository=receipt_repository,
            value="150.00",
        )

    assert isinstance(first, ModeloEditExecutionUpdatedV1)
    assert isinstance(second, ModeloEditExecutionUpdatedV1)
    assert first.receipt.calculation_revision_id == second.receipt.calculation_revision_id
    assert first.receipt.bucket_event_id is not None
    assert second.receipt.bucket_event_id is None
    assert first.receipt.receipt_id != second.receipt.receipt_id


def test_redeclaring_a_different_value_produces_a_new_distinct_revision(tmp_path: Path) -> None:
    """Changing a previously declared value reaches the engine as a genuinely new revision."""
    work_unit = _work_unit()

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        _seed_minimal_profile(profile.repository)
        work_unit_repository = WorkUnitCatalogueRepository(objects=profile.repository)
        calculation_repository = CalculationRevisionCatalogueRepository(objects=profile.repository)
        bucket_event_repository = BucketEventHistoryRepository(objects=profile.repository)
        receipt_repository = ModeloEditReceiptRepository(objects=profile.repository)
        work_unit_repository.save(WorkUnitCatalogue.from_work_units((work_unit,)))

        first, casilla_id = _apply(
            work_unit_repository=work_unit_repository,
            calculation_repository=calculation_repository,
            bucket_event_repository=bucket_event_repository,
            receipt_repository=receipt_repository,
            value="150.00",
        )
        second, _ = _apply(
            work_unit_repository=work_unit_repository,
            calculation_repository=calculation_repository,
            bucket_event_repository=bucket_event_repository,
            receipt_repository=receipt_repository,
            value="275.00",
        )

        final_work_unit = work_unit_repository.load().get(work_unit.work_unit_id)

    assert isinstance(first, ModeloEditExecutionUpdatedV1)
    assert isinstance(second, ModeloEditExecutionUpdatedV1)
    assert first.receipt.calculation_revision_id != second.receipt.calculation_revision_id
    assert second.receipt.bucket_event_id is not None
    assert final_work_unit is not None
    assert final_work_unit.current_calculation_revision_id == second.receipt.calculation_revision_id
    assert casilla_id  # the redeclared casilla was resolved from the real registry surface


def test_no_declared_value_or_raw_lexeme_reaches_the_receipt_or_baseline(tmp_path: Path) -> None:
    """The sensitive amount reaches only memory and the encrypted store, never the receipt."""
    work_unit = _work_unit()
    sentinel_value = "999999.99"

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        _seed_minimal_profile(profile.repository)
        work_unit_repository = WorkUnitCatalogueRepository(objects=profile.repository)
        calculation_repository = CalculationRevisionCatalogueRepository(objects=profile.repository)
        bucket_event_repository = BucketEventHistoryRepository(objects=profile.repository)
        receipt_repository = ModeloEditReceiptRepository(objects=profile.repository)
        work_unit_repository.save(WorkUnitCatalogue.from_work_units((work_unit,)))

        admitted = _admit(work_unit, work_catalogue=work_unit_repository.load())
        baseline_dump = admitted.baseline.model_dump_json()

        result, _ = _apply(
            work_unit_repository=work_unit_repository,
            calculation_repository=calculation_repository,
            bucket_event_repository=bucket_event_repository,
            receipt_repository=receipt_repository,
            value=sentinel_value,
        )

    assert isinstance(result, ModeloEditExecutionUpdatedV1)
    assert sentinel_value not in baseline_dump
    assert sentinel_value not in result.receipt.model_dump_json()
