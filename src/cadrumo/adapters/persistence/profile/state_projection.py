"""Persistence adapter for the operator state-projection read contract."""

from __future__ import annotations

from ....application.state_projection_ports import (
    StateProjectionProfileRead,
    StateProjectionReadError,
    StateProjectionWorkspaceRead,
)
from ....application.user_profile.profile_record_repository import ProfileRecordRepository
from ....application.workflow.profile_bucket_scan import read_profile_bucket_by_id
from ....domain.modelos.work_unit import WorkUnitState
from ..storage.runtime import inspect_bucket_storage_runtime
from .filing_drafts import ModeloDraftRepository
from .invoices import InvoiceCatalogueRepository
from .modelos_calculation import CalculationRevisionCatalogueRepository
from .modelos_work_units import WorkUnitCatalogueRepository
from .transactions import TransactionCatalogueRepository


class StateProjectionPersistenceAdapter:
    """Translate profile persistence records into projection-owned DTOs."""

    def read_workspace(self, *, bucket_id: str) -> StateProjectionWorkspaceRead:
        """Read and count every workspace catalogue for ``bucket_id``."""
        try:
            inspect_bucket_storage_runtime(bucket_id).require_ready()
            transactions = TransactionCatalogueRepository(bucket_id=bucket_id).load()
            invoices = InvoiceCatalogueRepository(bucket_id=bucket_id).load()
            drafts = tuple(ModeloDraftRepository(bucket_id=bucket_id).iter_drafts())
            work_units = WorkUnitCatalogueRepository(bucket_id=bucket_id).load()
            revisions = CalculationRevisionCatalogueRepository(bucket_id=bucket_id).load()
            from ....application.diagnostics import secure_object_unreadable_total

            active_work_units = sum(1 for unit in work_units.values() if unit.state is WorkUnitState.BORRADOR)
            discarded_work_units = sum(1 for unit in work_units.values() if unit.state is WorkUnitState.DESCARTADO)
            return StateProjectionWorkspaceRead(
                transactions=len(transactions.transactions),
                invoices=len(invoices),
                drafts=len(drafts),
                work_units=active_work_units,
                discarded_work_units=discarded_work_units,
                calculation_revisions=len(revisions),
                unreadable_rows=secure_object_unreadable_total(),
            )
        except Exception as exc:
            raise StateProjectionReadError("workspace") from exc

    def read_profile(self, *, profile_id: str) -> StateProjectionProfileRead | None:
        """Read the profile pointer and its authenticated current record."""
        try:
            pointer = read_profile_bucket_by_id(profile_id)
            if pointer is None:
                return None
            record = ProfileRecordRepository.for_current_session(pointer.bucket_id).load(pointer.bucket_id)
            return StateProjectionProfileRead(bucket_id=pointer.bucket_id, record=record)
        except Exception as exc:
            raise StateProjectionReadError("profile") from exc
