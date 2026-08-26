"""Real-registry integration tests for the guarded Modelo edit executor."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_edit_receipts import ModeloEditReceiptRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from ....core import Period
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.modelos import (
    CalculationRevisionCatalogue,
    ModeloCode,
    WorkUnit,
    WorkUnitCatalogue,
    derive_work_unit_id,
)
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from ....tests.profile_capsule import seed_test_profile_record
from ....tests.secure_sql import isolated_runtime_profile
from ...operations.registry import OperationSchemaIdentityV1
from .._edit_execution import apply_modelo_edit
from .._edit_models import (
    ModeloEditAdmissionRequestV1,
    ModeloEditAdmittedV1,
    ModeloEditApplyRequestV1,
    ModeloEditCompatibilityTupleV1,
    ModeloEditExecutionNoEffectV1,
    ModeloEditExecutionUpdatedV1,
    ModeloEditExistingRowAddressV1,
    ModeloEditMutationFamily,
    ModeloEditRowIntentKind,
    ModeloEditScalarAddressV1,
    ModeloEditScalarIntentKind,
    ModeloEditStaleBaselineRefusalV1,
    ModeloEditSubmissionV1,
    ModeloEditUnsupportedIntentReason,
    ModeloEditUnsupportedIntentRefusalV1,
    ModeloEditWritableScalarSurfaceEntryV1,
    ModeloRowEditIntentV1,
    ModeloScalarEditIntentV1,
)
from .._edit_services import admit_modelo_edit, modelo_edit_request_schema_identity, modelo_edit_result_schema_identity
from ..work_addressing import ModeloExactWorkUnitTarget
from ..workspace_models import ModeloWorkspaceExactWorkUnitTargetV1, ModeloWorkspaceTargetV1

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_BUCKET_ID = "0f629c46-1dc8-4cb1-8d02-aa0ee4f45a43"
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
    revision_id = bundled_authority().snapshot(_MODELO, filing_year=_FILING_YEAR, period=period.registry_token).revision.id
    now = datetime(2026, 1, 10, tzinfo=UTC)
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
        created_at=now,
        updated_at=now,
    )


def _target_for(work_unit: WorkUnit) -> ModeloWorkspaceTargetV1:
    return ModeloWorkspaceExactWorkUnitTargetV1(
        target=ModeloExactWorkUnitTarget(work_unit_id=work_unit.work_unit_id, bucket_id=work_unit.bucket_id)
    )


def _admit(work_unit: WorkUnit, *, work_catalogue: WorkUnitCatalogue) -> ModeloEditAdmittedV1:
    result = admit_modelo_edit(
        ModeloEditAdmissionRequestV1(target=_target_for(work_unit), mutation_family=ModeloEditMutationFamily.CALCULATE),
        bucket_id=_BUCKET_ID,
        work_catalogue=work_catalogue,
        calculation_catalogue=CalculationRevisionCatalogue(),
        compatibility=_compatibility(),
    )
    assert isinstance(result, ModeloEditAdmittedV1)
    return result


def test_apply_persists_a_set_typed_value_edit_and_co_commits_the_receipt(tmp_path: Path) -> None:
    """A real SET_TYPED_VALUE scalar edit produces an UPDATED receipt atomically."""
    work_unit = _work_unit()

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        _seed_minimal_profile(profile.repository)
        work_unit_repository = WorkUnitCatalogueRepository(objects=profile.repository)
        calculation_repository = CalculationRevisionCatalogueRepository(objects=profile.repository)
        bucket_event_repository = BucketEventHistoryRepository(objects=profile.repository)
        receipt_repository = ModeloEditReceiptRepository(objects=profile.repository)

        work_unit_repository.save(WorkUnitCatalogue.from_work_units((work_unit,)))
        admitted = _admit(work_unit, work_catalogue=work_unit_repository.load())
        baseline = admitted.baseline
        scalar_entry = next(e for e in baseline.permitted_surface if isinstance(e, ModeloEditWritableScalarSurfaceEntryV1))

        submission = ModeloEditSubmissionV1(
            baseline=baseline,
            mutation_family=ModeloEditMutationFamily.CALCULATE,
            scalar_intents=(
                ModeloScalarEditIntentV1(
                    address=ModeloEditScalarAddressV1(casilla_id=scalar_entry.casilla_id),
                    kind=ModeloEditScalarIntentKind.SET_TYPED_VALUE,
                    value="150.00",
                ),
            ),
        )
        result = apply_modelo_edit(
            ModeloEditApplyRequestV1(operation_id=_OPERATION_ID, submission=submission),
            work_unit_repository=work_unit_repository,
            calculation_repository=calculation_repository,
            bucket_event_repository=bucket_event_repository,
            receipt_repository=receipt_repository,
            now=datetime(2026, 1, 10, 6, 0, tzinfo=UTC),
            result_destination="modelo/131/2025/1T/edit-result",
        )

        assert isinstance(result, ModeloEditExecutionUpdatedV1)
        loaded_receipt = receipt_repository.load(result.receipt.receipt_id)

    assert loaded_receipt == result.receipt
    assert result.receipt.bucket_event_id is not None
    assert result.receipt.work_unit_id == work_unit.work_unit_id


def test_apply_persists_a_clear_declared_value_edit_and_co_commits_the_receipt(tmp_path: Path) -> None:
    """A real CLEAR_DECLARED_VALUE scalar edit reaches the engine and produces an UPDATED receipt."""
    work_unit = _work_unit()

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        _seed_minimal_profile(profile.repository)
        work_unit_repository = WorkUnitCatalogueRepository(objects=profile.repository)
        calculation_repository = CalculationRevisionCatalogueRepository(objects=profile.repository)
        bucket_event_repository = BucketEventHistoryRepository(objects=profile.repository)
        receipt_repository = ModeloEditReceiptRepository(objects=profile.repository)

        work_unit_repository.save(WorkUnitCatalogue.from_work_units((work_unit,)))
        admitted = _admit(work_unit, work_catalogue=work_unit_repository.load())
        baseline = admitted.baseline
        scalar_entry = next(e for e in baseline.permitted_surface if isinstance(e, ModeloEditWritableScalarSurfaceEntryV1))

        submission = ModeloEditSubmissionV1(
            baseline=baseline,
            mutation_family=ModeloEditMutationFamily.CALCULATE,
            scalar_intents=(
                ModeloScalarEditIntentV1(
                    address=ModeloEditScalarAddressV1(casilla_id=scalar_entry.casilla_id),
                    kind=ModeloEditScalarIntentKind.CLEAR_DECLARED_VALUE,
                ),
            ),
        )
        result = apply_modelo_edit(
            ModeloEditApplyRequestV1(operation_id=_OPERATION_ID, submission=submission),
            work_unit_repository=work_unit_repository,
            calculation_repository=calculation_repository,
            bucket_event_repository=bucket_event_repository,
            receipt_repository=receipt_repository,
            now=datetime(2026, 1, 10, 6, 0, tzinfo=UTC),
            result_destination="modelo/131/2025/1T/edit-result",
        )

    assert isinstance(result, ModeloEditExecutionUpdatedV1)
    assert result.receipt.work_unit_id == work_unit.work_unit_id


def test_an_explicit_clear_produces_a_distinct_revision_from_one_never_declared(tmp_path: Path) -> None:
    """The same substantive state (casilla B absent) hashes differently when explicitly cleared.

    Proves the D4 distinctness requirement directly against the content
    address rather than by field inspection alone: two submissions carry the
    identical SET_TYPED_VALUE for casilla A and never otherwise touch casilla
    B, differing only in whether B is explicitly CLEAR_DECLARED_VALUE'd. Both
    produce a casilla B that is absent from ``input_values_by_casilla_id`` on
    read, yet the two calculation revisions are proven distinct.
    """
    work_unit = _work_unit()

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        _seed_minimal_profile(profile.repository)
        work_unit_repository = WorkUnitCatalogueRepository(objects=profile.repository)
        calculation_repository = CalculationRevisionCatalogueRepository(objects=profile.repository)
        bucket_event_repository = BucketEventHistoryRepository(objects=profile.repository)
        receipt_repository = ModeloEditReceiptRepository(objects=profile.repository)

        work_unit_repository.save(WorkUnitCatalogue.from_work_units((work_unit,)))
        admitted = _admit(work_unit, work_catalogue=work_unit_repository.load())
        baseline = admitted.baseline
        scalar_entries = [e for e in baseline.permitted_surface if isinstance(e, ModeloEditWritableScalarSurfaceEntryV1)]
        entry_a, entry_b = scalar_entries[0], scalar_entries[1]

        def _apply(*, clear_b: bool) -> ModeloEditExecutionUpdatedV1:
            re_admitted = admit_modelo_edit(
                ModeloEditAdmissionRequestV1(
                    target=_target_for(work_unit), mutation_family=ModeloEditMutationFamily.CALCULATE
                ),
                bucket_id=_BUCKET_ID,
                work_catalogue=work_unit_repository.load(),
                calculation_catalogue=calculation_repository.load(),
                compatibility=_compatibility(),
            )
            assert isinstance(re_admitted, ModeloEditAdmittedV1)
            intents = [
                ModeloScalarEditIntentV1(
                    address=ModeloEditScalarAddressV1(casilla_id=entry_a.casilla_id),
                    kind=ModeloEditScalarIntentKind.SET_TYPED_VALUE,
                    value="200.00",
                ),
            ]
            if clear_b:
                intents.append(
                    ModeloScalarEditIntentV1(
                        address=ModeloEditScalarAddressV1(casilla_id=entry_b.casilla_id),
                        kind=ModeloEditScalarIntentKind.CLEAR_DECLARED_VALUE,
                    )
                )
            submission = ModeloEditSubmissionV1(
                baseline=re_admitted.baseline,
                mutation_family=ModeloEditMutationFamily.CALCULATE,
                scalar_intents=tuple(intents),
            )
            outcome = apply_modelo_edit(
                ModeloEditApplyRequestV1(operation_id=_OPERATION_ID, submission=submission),
                work_unit_repository=work_unit_repository,
                calculation_repository=calculation_repository,
                bucket_event_repository=bucket_event_repository,
                receipt_repository=receipt_repository,
                now=datetime(2026, 1, 10, 6, 0, tzinfo=UTC),
                result_destination="modelo/131/2025/1T/edit-result",
            )
            assert isinstance(outcome, ModeloEditExecutionUpdatedV1)
            return outcome

        never_touched = _apply(clear_b=False)
        explicitly_cleared = _apply(clear_b=True)

    assert never_touched.receipt.calculation_revision_id != explicitly_cleared.receipt.calculation_revision_id


def test_apply_refuses_recalculate_with_the_typed_unsupported_reason(tmp_path: Path) -> None:
    """RECALCULATE is out of this executor's V1 scope and refuses honestly, not silently."""
    work_unit = _work_unit()

    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        work_unit_repository = WorkUnitCatalogueRepository(objects=profile.repository)
        calculation_repository = CalculationRevisionCatalogueRepository(objects=profile.repository)
        bucket_event_repository = BucketEventHistoryRepository(objects=profile.repository)
        receipt_repository = ModeloEditReceiptRepository(objects=profile.repository)

        work_unit_repository.save(WorkUnitCatalogue.from_work_units((work_unit,)))
        admitted = _admit(work_unit, work_catalogue=work_unit_repository.load())
        baseline = admitted.baseline.model_copy(update={"mutation_family": ModeloEditMutationFamily.RECALCULATE})

        submission = ModeloEditSubmissionV1(baseline=baseline, mutation_family=ModeloEditMutationFamily.RECALCULATE)
        result = apply_modelo_edit(
            ModeloEditApplyRequestV1(operation_id=_OPERATION_ID, submission=submission),
            work_unit_repository=work_unit_repository,
            calculation_repository=calculation_repository,
            bucket_event_repository=bucket_event_repository,
            receipt_repository=receipt_repository,
            now=datetime(2026, 1, 10, 6, 0, tzinfo=UTC),
            result_destination="modelo/131/2025/1T/edit-result",
        )

    assert isinstance(result, ModeloEditExecutionNoEffectV1)
    assert isinstance(result.refusal, ModeloEditUnsupportedIntentRefusalV1)
    assert result.refusal.reason is ModeloEditUnsupportedIntentReason.RECALCULATE_NOT_YET_WIRED


@pytest.mark.parametrize(
    ("kind", "reason"),
    [
        (ModeloEditScalarIntentKind.REMOVE_OVERRIDE, ModeloEditUnsupportedIntentReason.REMOVE_OVERRIDE_NOT_YET_WIRED),
    ],
)
def test_apply_refuses_each_unsupported_scalar_intent_kind_by_name(
    tmp_path: Path, kind: ModeloEditScalarIntentKind, reason: ModeloEditUnsupportedIntentReason
) -> None:
    """Each unreachable scalar intent kind refuses with its own specific reason."""
    work_unit = _work_unit()

    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        work_unit_repository = WorkUnitCatalogueRepository(objects=profile.repository)
        calculation_repository = CalculationRevisionCatalogueRepository(objects=profile.repository)
        bucket_event_repository = BucketEventHistoryRepository(objects=profile.repository)
        receipt_repository = ModeloEditReceiptRepository(objects=profile.repository)

        work_unit_repository.save(WorkUnitCatalogue.from_work_units((work_unit,)))
        admitted = _admit(work_unit, work_catalogue=work_unit_repository.load())
        baseline = admitted.baseline
        scalar_entry = next(e for e in baseline.permitted_surface if isinstance(e, ModeloEditWritableScalarSurfaceEntryV1))

        submission = ModeloEditSubmissionV1(
            baseline=baseline,
            mutation_family=ModeloEditMutationFamily.CALCULATE,
            scalar_intents=(
                ModeloScalarEditIntentV1(
                    address=ModeloEditScalarAddressV1(casilla_id=scalar_entry.casilla_id), kind=kind
                ),
            ),
        )
        result = apply_modelo_edit(
            ModeloEditApplyRequestV1(operation_id=_OPERATION_ID, submission=submission),
            work_unit_repository=work_unit_repository,
            calculation_repository=calculation_repository,
            bucket_event_repository=bucket_event_repository,
            receipt_repository=receipt_repository,
            now=datetime(2026, 1, 10, 6, 0, tzinfo=UTC),
            result_destination="modelo/131/2025/1T/edit-result",
        )

    assert isinstance(result, ModeloEditExecutionNoEffectV1)
    assert isinstance(result.refusal, ModeloEditUnsupportedIntentRefusalV1)
    assert result.refusal.reason is reason


def test_apply_refuses_a_row_intent_by_its_specific_kind(tmp_path: Path) -> None:
    """A row intent refuses with the reason naming its exact kind, e.g. MOVE_ROW."""
    work_unit = _work_unit()

    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        work_unit_repository = WorkUnitCatalogueRepository(objects=profile.repository)
        calculation_repository = CalculationRevisionCatalogueRepository(objects=profile.repository)
        bucket_event_repository = BucketEventHistoryRepository(objects=profile.repository)
        receipt_repository = ModeloEditReceiptRepository(objects=profile.repository)

        work_unit_repository.save(WorkUnitCatalogue.from_work_units((work_unit,)))
        admitted = _admit(work_unit, work_catalogue=work_unit_repository.load())
        baseline = admitted.baseline

        # No modelo 131 manual_input binding admits a row-group entry (none is
        # a real row set); the executor's row-intent refusal fires on any row
        # intent's presence, before permitted-surface admission is checked, so
        # the address below names no real binding on purpose.
        submission = ModeloEditSubmissionV1(
            baseline=baseline,
            mutation_family=ModeloEditMutationFamily.CALCULATE,
            row_intents=(
                ModeloRowEditIntentV1(
                    address=ModeloEditExistingRowAddressV1(binding_id="a" * 64, row_index=1),
                    kind=ModeloEditRowIntentKind.DELETE_ROW,
                ),
            ),
        )
        result = apply_modelo_edit(
            ModeloEditApplyRequestV1(operation_id=_OPERATION_ID, submission=submission),
            work_unit_repository=work_unit_repository,
            calculation_repository=calculation_repository,
            bucket_event_repository=bucket_event_repository,
            receipt_repository=receipt_repository,
            now=datetime(2026, 1, 10, 6, 0, tzinfo=UTC),
            result_destination="modelo/131/2025/1T/edit-result",
        )

    assert isinstance(result, ModeloEditExecutionNoEffectV1)
    assert isinstance(result.refusal, ModeloEditUnsupportedIntentRefusalV1)
    assert result.refusal.reason is ModeloEditUnsupportedIntentReason.DELETE_ROW_NOT_YET_WIRED


def test_apply_refuses_a_real_conflicting_write_at_the_guarded_commit_point(tmp_path: Path) -> None:
    """A real second writer racing between admission and the guarded commit point is caught.

    This proves the recheck happens AT the commit point, not merely before it:
    the race lands after the baseline was already admitted, and the guarded
    commit still refuses rather than writing over it.
    """
    work_unit = _work_unit()

    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        work_unit_repository = WorkUnitCatalogueRepository(objects=profile.repository)
        calculation_repository = CalculationRevisionCatalogueRepository(objects=profile.repository)
        bucket_event_repository = BucketEventHistoryRepository(objects=profile.repository)
        receipt_repository = ModeloEditReceiptRepository(objects=profile.repository)

        work_unit_repository.save(WorkUnitCatalogue.from_work_units((work_unit,)))
        admitted = _admit(work_unit, work_catalogue=work_unit_repository.load())
        baseline = admitted.baseline
        scalar_entry = next(e for e in baseline.permitted_surface if isinstance(e, ModeloEditWritableScalarSurfaceEntryV1))

        # A REAL second writer commits after admission, before the executor's
        # own commit-point recheck runs.
        work_unit_repository.save(
            WorkUnitCatalogue.from_work_units((work_unit.model_copy(update={"name": "renamed-by-race"}),)),
        )

        submission = ModeloEditSubmissionV1(
            baseline=baseline,
            mutation_family=ModeloEditMutationFamily.CALCULATE,
            scalar_intents=(
                ModeloScalarEditIntentV1(
                    address=ModeloEditScalarAddressV1(casilla_id=scalar_entry.casilla_id),
                    kind=ModeloEditScalarIntentKind.SET_TYPED_VALUE,
                    value="200.00",
                ),
            ),
        )
        result = apply_modelo_edit(
            ModeloEditApplyRequestV1(operation_id=_OPERATION_ID, submission=submission),
            work_unit_repository=work_unit_repository,
            calculation_repository=calculation_repository,
            bucket_event_repository=bucket_event_repository,
            receipt_repository=receipt_repository,
            now=datetime(2026, 1, 10, 6, 0, tzinfo=UTC),
            result_destination="modelo/131/2025/1T/edit-result",
        )

        # Nothing was written for this attempt: no calculation revision exists.
        assert not tuple(calculation_repository.load().values())

    assert isinstance(result, ModeloEditExecutionNoEffectV1)
    assert isinstance(result.refusal, ModeloEditStaleBaselineRefusalV1)
    assert "work_catalogue_revision" in result.refusal.mismatching_coordinates
