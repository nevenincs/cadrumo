"""Real-registry end-to-end proof of a detail-row edit through ``apply_modelo_edit``.

Drives a real ADD, UPDATE, and DELETE `Modelo347ContraparteRow` edit against
a live modelo 347 revision, with real profile setup, through the same
guarded compare-and-swap executor every scalar/binding edit already uses.
Proves the reconstructed rows reach the persisted ``CalculationRevision``,
and that an unknown natural key refuses without writing.

MOVE_ROW is not exercised: it was later retired, because the
calculation revision's content address is order-blind, so a pure reorder
would have been silently absorbed by the guarded duplicate-result branch
rather than actually persist.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
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
from ....domain.modelos.row_models import Modelo347ContraparteRow
from ....domain.modelos.work_unit import WorkUnit, WorkUnitCatalogue, derive_work_unit_id
from ....tests.profile_capsule import seed_modelo_ready_profile_record
from ....tests.secure_sql import isolated_runtime_profile
from ...operations.registry import OperationSchemaIdentityV1
from .._edit_execution import apply_modelo_edit
from .._edit_models import (
    ModeloDetailRowEditIntentV1,
    ModeloEditAdmissionRequestV1,
    ModeloEditAdmittedV1,
    ModeloEditApplyRequestV1,
    ModeloEditDetailRowAddressV1,
    ModeloEditDetailRowIntentKind,
    ModeloEditExecutionNoEffectV1,
    ModeloEditExecutionUpdatedV1,
    ModeloEditMutationFamily,
    ModeloEditSubmissionV1,
    ModeloEditWritableDetailRowSurfaceEntryV1,
)
from .._edit_services import admit_modelo_edit, modelo_edit_request_schema_identity, modelo_edit_result_schema_identity
from ..edit_contract import ModeloEditCompatibilityTupleV1
from ..work_addressing import ModeloExactWorkUnitTarget
from ..workspace_models import ModeloWorkspaceExactWorkUnitTargetV1, ModeloWorkspaceTargetV1

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_BUCKET_ID = "0f629c46-1dc8-4cb1-8d02-aa0ee4f45a48"
_MODELO = "347"
_FILING_YEAR = 2025
_PERIOD_CODE = "0A"
_DIGEST = "a" * 64
_OPERATION_ID = "0" * 64
_CLOCK = datetime(2026, 1, 10, tzinfo=UTC)


def _seed_minimal_profile(objects: SecureObjectRepository) -> None:
    """Seed the modelo readiness baseline through the canonical seeder.

    The fact tuple this used to restate lived here in four identical
    copies. It is declared once in `tests.profile_capsule` now, because
    the readiness gate decides what modelo work may run at all and every
    copy was another place for that answer to drift.
    """
    del objects
    seed_modelo_ready_profile_record(str(_BUCKET_ID), clock=_CLOCK)


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
    work_unit: WorkUnit, *, work_catalogue: WorkUnitCatalogue, calculation_catalogue: CalculationRevisionCatalogue
) -> ModeloEditAdmittedV1:
    result = admit_modelo_edit(
        ModeloEditAdmissionRequestV1(target=_target_for(work_unit), mutation_family=ModeloEditMutationFamily.CALCULATE),
        bucket_id=_BUCKET_ID,
        work_catalogue=work_catalogue,
        calculation_catalogue=calculation_catalogue,
        compatibility=_compatibility(),
    )
    assert isinstance(result, ModeloEditAdmittedV1)
    return result


def _address(natural_key: str) -> ModeloEditDetailRowAddressV1:
    return ModeloEditDetailRowAddressV1(detail_row_kind="contraparte", natural_key=natural_key)


def test_admission_surfaces_the_real_m347_contraparte_detail_row_kind() -> None:
    """Modelo 347's real registry revision admits 'contraparte' as a writable detail row."""
    work_unit = _work_unit()
    admitted = _admit(
        work_unit,
        work_catalogue=WorkUnitCatalogue.from_work_units((work_unit,)),
        calculation_catalogue=CalculationRevisionCatalogue(),
    )
    entries = [
        e for e in admitted.baseline.permitted_surface if isinstance(e, ModeloEditWritableDetailRowSurfaceEntryV1)
    ]
    assert {e.detail_row_kind for e in entries} == {"contraparte"}


def test_add_then_update_then_delete_a_detail_row_reaches_the_persisted_revision(tmp_path: Path) -> None:
    """A real ADD, UPDATE, then DELETE each reach a persisted CalculationRevision.detail_rows."""
    work_unit = _work_unit()

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        _seed_minimal_profile(profile.repository)
        work_unit_repository = WorkUnitCatalogueRepository(objects=profile.repository)
        calculation_repository = CalculationRevisionCatalogueRepository(objects=profile.repository)
        bucket_event_repository = BucketEventHistoryRepository(objects=profile.repository)
        receipt_repository = ModeloEditReceiptRepository(objects=profile.repository)

        work_unit_repository.save(WorkUnitCatalogue.from_work_units((work_unit,)))

        def _apply(*, detail_row_intents: tuple[ModeloDetailRowEditIntentV1, ...]) -> ModeloEditExecutionUpdatedV1:
            admitted = _admit(
                work_unit,
                work_catalogue=work_unit_repository.load(),
                calculation_catalogue=calculation_repository.load(),
            )
            submission = ModeloEditSubmissionV1(
                baseline=admitted.baseline,
                mutation_family=ModeloEditMutationFamily.CALCULATE,
                detail_row_intents=detail_row_intents,
            )
            outcome = apply_modelo_edit(
                ModeloEditApplyRequestV1(operation_id=_OPERATION_ID, submission=submission),
                work_unit_repository=work_unit_repository,
                calculation_repository=calculation_repository,
                bucket_event_repository=bucket_event_repository,
                receipt_repository=receipt_repository,
                now=datetime(2026, 1, 10, 6, 0, tzinfo=UTC),
                result_destination="modelo/347/2025/0A/edit-result",
            )
            assert isinstance(outcome, ModeloEditExecutionUpdatedV1)
            return outcome

        # ADD: a real contraparte row reaches the persisted revision.
        added_row = Modelo347ContraparteRow(nif="11111111H", importe_Q1=Decimal("5000"))
        add_result = _apply(
            detail_row_intents=(
                ModeloDetailRowEditIntentV1(
                    address=_address("11111111H"), kind=ModeloEditDetailRowIntentKind.ADD_ROW, row=added_row
                ),
            )
        )
        persisted = calculation_repository.load().get(add_result.receipt.calculation_revision_id)
        assert persisted is not None
        assert persisted.detail_rows == (added_row,)

        # UPDATE: the same natural key, new content, reaches the persisted revision.
        updated_row = Modelo347ContraparteRow(nif="11111111H", importe_Q1=Decimal("9999"))
        update_result = _apply(
            detail_row_intents=(
                ModeloDetailRowEditIntentV1(
                    address=_address("11111111H"), kind=ModeloEditDetailRowIntentKind.UPDATE_ROW, row=updated_row
                ),
            )
        )
        persisted = calculation_repository.load().get(update_result.receipt.calculation_revision_id)
        assert persisted is not None
        assert persisted.detail_rows == (updated_row,)

        # DELETE: the row's absence reaches the persisted revision.
        delete_result = _apply(
            detail_row_intents=(
                ModeloDetailRowEditIntentV1(
                    address=_address("11111111H"), kind=ModeloEditDetailRowIntentKind.DELETE_ROW
                ),
            )
        )
        persisted = calculation_repository.load().get(delete_result.receipt.calculation_revision_id)
        assert persisted is not None
        assert persisted.detail_rows == ()


def test_an_unknown_natural_key_refuses_without_writing(tmp_path: Path) -> None:
    """UPDATE/DELETE against a natural key the current revision never declared refuses, writes nothing."""
    work_unit = _work_unit()

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        _seed_minimal_profile(profile.repository)
        work_unit_repository = WorkUnitCatalogueRepository(objects=profile.repository)
        calculation_repository = CalculationRevisionCatalogueRepository(objects=profile.repository)
        bucket_event_repository = BucketEventHistoryRepository(objects=profile.repository)
        receipt_repository = ModeloEditReceiptRepository(objects=profile.repository)

        work_unit_repository.save(WorkUnitCatalogue.from_work_units((work_unit,)))
        admitted = _admit(
            work_unit,
            work_catalogue=work_unit_repository.load(),
            calculation_catalogue=calculation_repository.load(),
        )

        ghost_row = Modelo347ContraparteRow(nif="99999999Z", importe_Q1=Decimal("1"))
        submission = ModeloEditSubmissionV1(
            baseline=admitted.baseline,
            mutation_family=ModeloEditMutationFamily.CALCULATE,
            detail_row_intents=(
                ModeloDetailRowEditIntentV1(
                    address=_address("99999999Z"), kind=ModeloEditDetailRowIntentKind.UPDATE_ROW, row=ghost_row
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
            result_destination="modelo/347/2025/0A/edit-result",
        )

        assert isinstance(result, ModeloEditExecutionNoEffectV1)
        assert calculation_repository.load().revisions == {}
