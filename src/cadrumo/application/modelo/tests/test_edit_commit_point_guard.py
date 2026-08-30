"""Proves the guarded-commit-point race window is closed end to end.

D6 requires the executor to reconfirm every baseline coordinate immediately
before effect and never promote a stale reconfirmation into authority. A
reconfirm performed and then handed to a separate later write has a window
between the two; this module drives a REAL conflicting write landing inside
that exact window and proves the guarded commit still refuses rather than
silently committing over it.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....adapters.persistence.storage import SecureObjectRevisionConflictError
from ....core.period import Period
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.modelos.calculation_revision import CalculationRevisionCatalogue
from ....domain.modelos.codes import ModeloCode
from ....domain.modelos.work_unit import WorkUnit, WorkUnitCatalogue, derive_work_unit_id
from ....tests.secure_sql import isolated_runtime_profile
from ...operations.registry import OperationSchemaIdentityV1
from .._edit_models import (
    ModeloEditAdmissionRequestV1,
    ModeloEditAdmittedV1,
    ModeloEditMutationFamily,
    ModeloEditWritableScalarSurfaceEntryV1,
)
from .._edit_services import (
    admit_modelo_edit,
    modelo_edit_request_schema_identity,
    modelo_edit_result_schema_identity,
    reconfirm_modelo_edit_baseline,
)
from .._revision_persistence import persist_calculation_revision
from ..edit_contract import ModeloEditCompatibilityTupleV1
from ..work_addressing import ModeloExactWorkUnitTarget
from ..workspace_models import ModeloWorkspaceExactWorkUnitTargetV1, ModeloWorkspaceTargetV1

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_BUCKET_ID = "commit-point-guard-bucket"
_MODELO = "131"
_FILING_YEAR = 2025
_PERIOD_CODE = "1T"
_DIGEST = "a" * 64
_ACTOR = "test-operator"


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


def test_a_real_conflicting_write_inside_the_reconfirm_to_commit_window_is_refused(tmp_path: Path) -> None:
    """Racing a second writer strictly between reconfirm and the guarded write must be caught.

    Reconfirm and the guarded persistence call both compare against the SAME
    catalogue snapshot read once up front -- never re-read in between -- which
    is precisely what closes the window: any write landing after that one
    read, including one a passed reconfirm never observed, is still rejected
    by the persistence primitive's own compare-and-swap.
    """
    work_unit = _work_unit()

    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        work_unit_repository = WorkUnitCatalogueRepository(objects=profile.repository)
        calculation_repository = CalculationRevisionCatalogueRepository(objects=profile.repository)
        bucket_event_repository = BucketEventHistoryRepository(objects=profile.repository)

        work_unit_repository.save(WorkUnitCatalogue.from_work_units((work_unit,)))

        admitted = admit_modelo_edit(
            ModeloEditAdmissionRequestV1(
                target=_target_for(work_unit), mutation_family=ModeloEditMutationFamily.CALCULATE
            ),
            bucket_id=_BUCKET_ID,
            work_catalogue=work_unit_repository.load(),
            calculation_catalogue=CalculationRevisionCatalogue(),
            compatibility=_compatibility(),
        )
        assert isinstance(admitted, ModeloEditAdmittedV1)
        baseline = admitted.baseline

        # ONE shared read: both the commit-point reconfirm and the guarded
        # write below compare against this exact snapshot.
        work_units, work_units_revision_id = work_unit_repository.load_revisioned()
        calculation_catalogue, _ = calculation_repository.load_revisioned()

        stale = reconfirm_modelo_edit_baseline(
            baseline, work_catalogue=work_units, calculation_catalogue=calculation_catalogue
        )
        assert stale is None, "the baseline must reconfirm cleanly before the race lands"

        # A REAL second writer commits inside the window between reconfirm and
        # the guarded persistence call below.
        racing_unit = work_units.get(work_unit.work_unit_id)
        assert racing_unit is not None
        work_unit_repository.save(
            WorkUnitCatalogue.from_work_units((racing_unit.model_copy(update={"name": "renamed-by-race"}),)),
        )

        scalar_entry = next(
            entry for entry in baseline.permitted_surface if isinstance(entry, ModeloEditWritableScalarSurfaceEntryV1)
        )
        with pytest.raises(SecureObjectRevisionConflictError):
            persist_calculation_revision(
                work_unit_id=work_unit.work_unit_id,
                work_unit=racing_unit,
                work_units=work_units,
                work_units_revision_id=work_units_revision_id,
                input_values_by_casilla_id={scalar_entry.casilla_id: "150.00"},
                binding_overrides={},
                row_binding_values={},
                row_source_identities={},
                row_casilla_values={},
                row_casilla_provenance={},
                relation_overrides={},
                casilla_values={},
                source_transaction_ids=(),
                borrador_snapshot_id=None,
                bindings_sourced_from_borrador=(),
                observations=(),
                source_provenance=(),
                detail_rows=(),
                formula_count=0,
                actor=_ACTOR,
                now=datetime(2026, 1, 10, 5, 0, tzinfo=UTC),
                calculation_repository=calculation_repository,
                work_unit_repository=work_unit_repository,
                bucket_event_repository=bucket_event_repository,
            )
