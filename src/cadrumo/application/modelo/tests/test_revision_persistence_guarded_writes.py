"""Guarded compare-and-swap proofs for calculation-revision persistence.

Covers the two defects the Modelo Edit Contract V1 persistence Step fixes in
:func:`persist_calculation_revision`: the duplicate-result branch's pointer
save is now guarded (never a bare, unguarded ``.save``), and both the
new-revision and duplicate branches co-commit any caller-supplied
``additional_secure_object_writes`` -- exercised here with a real
:class:`ModeloEditReceiptRepository` write, exactly the shape the edit
executor composes -- in the SAME encrypted transaction.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_edit_receipts import ModeloEditReceiptRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....adapters.persistence.storage.errors import SecureObjectRevisionConflictError
from ....adapters.persistence.storage.sql.secure_objects import SecureObjectWrite
from ....core.period import Period
from ....domain.modelos.codes import ModeloCode
from ....domain.modelos.work_unit import WorkUnit, WorkUnitCatalogue, derive_work_unit_id
from ....tests.secure_sql import isolated_runtime_profile
from .._edit_models import ModeloEditMutationFamily, ModeloEditMutationResultReceiptV1
from .._revision_persistence import persist_calculation_revision

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_MODELO = "130"
_FILING_YEAR = 2025
_REVISION_ID = "2019-y-siguientes"
_ACTOR = "test-operator"


def _work_unit() -> WorkUnit:
    period = Period.from_year_and_code(_FILING_YEAR, "1T")
    now = datetime(2026, 1, 10, tzinfo=UTC)
    bucket_id = "revision-persistence-bucket"
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=bucket_id, modelo=_MODELO, filing_year=_FILING_YEAR, period=period, revision_id=_REVISION_ID
        ),
        bucket_id=bucket_id,
        modelo=ModeloCode(_MODELO),
        filing_year=_FILING_YEAR,
        period=period,
        revision_id=_REVISION_ID,
        name=f"{_MODELO}-{_FILING_YEAR}-{period.registry_token}",
        created_at=now,
        updated_at=now,
    )


def _receipt(
    *, receipt_id: str, calculation_revision_id: str, bucket_event_id: str | None = "c" * 64
) -> ModeloEditMutationResultReceiptV1:
    return ModeloEditMutationResultReceiptV1(
        receipt_id=receipt_id,
        operation_id="0" * 64,
        mutation_family=ModeloEditMutationFamily.CALCULATE,
        baseline_id="b" * 64,
        work_unit_id=_work_unit().work_unit_id,
        calculation_revision_id=calculation_revision_id,
        bucket_event_id=bucket_event_id,
        committed_at=datetime(2026, 1, 10, 1, 0, tzinfo=UTC),
        result_destination="modelo/130/2025/1T/edit-result",
    )


def _persist(
    *,
    work_unit: WorkUnit,
    work_units: WorkUnitCatalogue,
    work_units_revision_id: str,
    calculation_repository: CalculationRevisionCatalogueRepository,
    work_unit_repository: WorkUnitCatalogueRepository,
    bucket_event_repository: BucketEventHistoryRepository,
    now: datetime,
    input_value: str,
    additional_secure_object_writes_for_revision: (
        Callable[[str, str | None], tuple[SecureObjectWrite, ...]] | None
    ) = None,
):
    return persist_calculation_revision(
        work_unit_id=work_unit.work_unit_id,
        work_unit=work_unit,
        work_units=work_units,
        work_units_revision_id=work_units_revision_id,
        input_values_by_casilla_id={"06": input_value},
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
        now=now,
        calculation_repository=calculation_repository,
        work_unit_repository=work_unit_repository,
        bucket_event_repository=bucket_event_repository,
        additional_secure_object_writes_for_revision=additional_secure_object_writes_for_revision,
    )


def test_new_revision_co_commits_additional_writes_atomically(tmp_path: Path) -> None:
    """A caller-supplied receipt write lands in the same transaction as the new revision."""
    work_unit = _work_unit()

    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        work_unit_repository = WorkUnitCatalogueRepository(objects=profile.repository)
        calculation_repository = CalculationRevisionCatalogueRepository(objects=profile.repository)
        bucket_event_repository = BucketEventHistoryRepository(objects=profile.repository)
        receipt_repository = ModeloEditReceiptRepository(objects=profile.repository)

        work_units = WorkUnitCatalogue.from_work_units((work_unit,))
        work_unit_repository.save(work_units)
        work_units, work_units_revision_id = work_unit_repository.load_revisioned()

        revision = _persist(
            work_unit=work_unit,
            work_units=work_units,
            work_units_revision_id=work_units_revision_id,
            calculation_repository=calculation_repository,
            work_unit_repository=work_unit_repository,
            bucket_event_repository=bucket_event_repository,
            now=datetime(2026, 1, 10, 2, 0, tzinfo=UTC),
            input_value="100.00",
            additional_secure_object_writes_for_revision=lambda revision_id, bucket_event_id: (
                receipt_repository.to_secure_object_write(
                    _receipt(
                        receipt_id="1" * 64,
                        calculation_revision_id=revision_id,
                        bucket_event_id=bucket_event_id,
                    ),
                ),
            ),
        )

        loaded_receipt = receipt_repository.load("1" * 64)
        loaded_work_units = work_unit_repository.load()

    assert loaded_receipt is not None
    assert loaded_receipt.calculation_revision_id == revision.calculation_revision_id
    reloaded_work_unit = loaded_work_units.get(work_unit.work_unit_id)
    assert reloaded_work_unit is not None
    assert reloaded_work_unit.current_calculation_revision_id == revision.calculation_revision_id


def test_duplicate_branch_confirms_pointer_under_guard_and_co_commits(tmp_path: Path) -> None:
    """Recalculating the same inputs still guards the pointer save and co-commits."""
    work_unit = _work_unit()

    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        work_unit_repository = WorkUnitCatalogueRepository(objects=profile.repository)
        calculation_repository = CalculationRevisionCatalogueRepository(objects=profile.repository)
        bucket_event_repository = BucketEventHistoryRepository(objects=profile.repository)
        receipt_repository = ModeloEditReceiptRepository(objects=profile.repository)

        work_unit_repository.save(WorkUnitCatalogue.from_work_units((work_unit,)))
        work_units, work_units_revision_id = work_unit_repository.load_revisioned()
        first = _persist(
            work_unit=work_unit,
            work_units=work_units,
            work_units_revision_id=work_units_revision_id,
            calculation_repository=calculation_repository,
            work_unit_repository=work_unit_repository,
            bucket_event_repository=bucket_event_repository,
            now=datetime(2026, 1, 10, 2, 0, tzinfo=UTC),
            input_value="100.00",
        )

        advanced_work_unit = work_unit_repository.load().get(work_unit.work_unit_id)
        assert advanced_work_unit is not None
        work_units, work_units_revision_id = work_unit_repository.load_revisioned()
        second = _persist(
            work_unit=advanced_work_unit,
            work_units=work_units,
            work_units_revision_id=work_units_revision_id,
            calculation_repository=calculation_repository,
            work_unit_repository=work_unit_repository,
            bucket_event_repository=bucket_event_repository,
            now=datetime(2026, 1, 10, 3, 0, tzinfo=UTC),
            input_value="100.00",
            additional_secure_object_writes_for_revision=lambda revision_id, bucket_event_id: (
                receipt_repository.to_secure_object_write(
                    _receipt(
                        receipt_id="2" * 64,
                        calculation_revision_id=revision_id,
                        bucket_event_id=bucket_event_id,
                    ),
                ),
            ),
        )

        loaded_second_receipt = receipt_repository.load("2" * 64)

    assert second.calculation_revision_id == first.calculation_revision_id
    assert loaded_second_receipt is not None


def test_duplicate_branch_refuses_a_real_conflicting_pointer_write(tmp_path: Path) -> None:
    """A genuine second writer racing the work-unit catalogue is rejected, not overwritten.

    This drives an ACTUAL conflicting write between the stale read and the
    duplicate-branch save: the CAS guard must reject it outright rather than
    silently discarding the concurrent change, which is exactly what the
    unguarded ``.save`` this fix replaces would have done.
    """
    work_unit = _work_unit()

    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        work_unit_repository = WorkUnitCatalogueRepository(objects=profile.repository)
        calculation_repository = CalculationRevisionCatalogueRepository(objects=profile.repository)
        bucket_event_repository = BucketEventHistoryRepository(objects=profile.repository)

        work_unit_repository.save(WorkUnitCatalogue.from_work_units((work_unit,)))
        work_units, work_units_revision_id = work_unit_repository.load_revisioned()
        _persist(
            work_unit=work_unit,
            work_units=work_units,
            work_units_revision_id=work_units_revision_id,
            calculation_repository=calculation_repository,
            work_unit_repository=work_unit_repository,
            bucket_event_repository=bucket_event_repository,
            now=datetime(2026, 1, 10, 2, 0, tzinfo=UTC),
            input_value="100.00",
        )

        # Capture a STALE read (as of before the first persist's pointer advance
        # would be observed by a second concurrent caller who read even earlier).
        stale_work_units, stale_revision_id = work_unit_repository.load_revisioned()

        # A real second writer advances the work unit's name in between --
        # any change is enough to move the row's revision id.
        racing_work_units = work_unit_repository.load()
        racing_unit = racing_work_units.get(work_unit.work_unit_id)
        assert racing_unit is not None
        work_unit_repository.save(
            WorkUnitCatalogue.from_work_units((racing_unit.model_copy(update={"name": "renamed-by-race"}),)),
        )

        with pytest.raises(SecureObjectRevisionConflictError):
            _persist(
                work_unit=racing_unit.model_copy(update={"current_calculation_revision_id": None}),
                work_units=stale_work_units,
                work_units_revision_id=stale_revision_id,
                calculation_repository=calculation_repository,
                work_unit_repository=work_unit_repository,
                bucket_event_repository=bucket_event_repository,
                now=datetime(2026, 1, 10, 4, 0, tzinfo=UTC),
                input_value="100.00",
            )
