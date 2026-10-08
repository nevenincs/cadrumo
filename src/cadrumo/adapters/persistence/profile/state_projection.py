"""Persistence adapter for the operator state-projection read contract.

Core types:
:class:`~cadrumo.adapters.persistence.profile.transactions.TransactionCatalogueRepository`.

Core types: :class:`~cadrumo.adapters.persistence.storage.sql.secure_objects.SecureObjectRepository`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ....application.diagnostics_ports import DiagnosticsPorts
from ....application.state_projection_ports import (
    StateProjectionProfileRead,
    StateProjectionReadError,
    StateProjectionWorkspaceRead,
)
from ....application.user_profile.access_contracts import AccessDenialCode
from ....application.user_profile.access_errors import ProfileAccessRefusedError
from ....application.user_profile.profile_record_repository import ProfileRecordRepository
from ....application.workflow.profile_bucket_scan import read_profile_bucket_by_id
from ....core.bucket_pointer import require_active_bucket_id
from ....domain.modelos.work_unit import WorkUnitState
from ..storage.runtime import inspect_bucket_storage_runtime
from .filing_drafts import ModeloDraftRepository
from .invoices import InvoiceCatalogueRepository
from .modelos_calculation import CalculationRevisionCatalogueRepository
from .modelos_work_units import WorkUnitCatalogueRepository
from .transactions import TransactionCatalogueRepository

if TYPE_CHECKING:
    from ....domain.calculations.registry.authority import PinnedAuthorityOperation
    from ....domain.calculations.registry.tax_id_format import SubjectTaxId
    from ..storage.sql.secure_objects import SecureObjectRepository


class StateProjectionPersistenceAdapter:
    """Translate profile persistence records into projection-owned DTOs."""

    def __init__(
        self,
        *,
        diagnostics_ports: DiagnosticsPorts,
        operation: PinnedAuthorityOperation | None = None,
        objects: SecureObjectRepository | None = None,
        bucket_id: str | None = None,
        m303_rectificativa_taxpayer_tax_id: SubjectTaxId | None = None,
    ) -> None:
        """Bind the required secure-object diagnostic capability."""
        if (operation is not None or objects is not None or bucket_id is not None) and (
            operation is None or objects is None or bucket_id is None
        ):
            raise ValueError("a bound projection needs its profile, repository and retained authority together")
        self._diagnostics_ports = diagnostics_ports
        self._operation = operation
        self._objects = objects
        self._bucket_id = bucket_id
        self._m303_rectificativa_taxpayer_tax_id = m303_rectificativa_taxpayer_tax_id

    def _require_bucket(self, bucket_id: str) -> None:
        """Check the immutable worker binding before any private projection read."""
        if self._bucket_id is not None and (
            bucket_id != self._bucket_id or require_active_bucket_id() != self._bucket_id
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)

    def read_workspace(self, *, bucket_id: str) -> StateProjectionWorkspaceRead:
        """Read and count every workspace catalogue for ``bucket_id``."""
        self._require_bucket(bucket_id)
        try:
            inspect_bucket_storage_runtime(bucket_id).require_ready()
            transactions = TransactionCatalogueRepository(bucket_id=bucket_id, objects=self._objects).load()
            invoices = InvoiceCatalogueRepository(bucket_id=bucket_id, objects=self._objects).load()
            drafts = tuple(ModeloDraftRepository(bucket_id=bucket_id, objects=self._objects).iter_drafts())
            work_units = WorkUnitCatalogueRepository(bucket_id=bucket_id, objects=self._objects).load()
            revisions = CalculationRevisionCatalogueRepository(
                bucket_id=bucket_id,
                objects=self._objects,
                m303_rectificativa_taxpayer_tax_id=self._m303_rectificativa_taxpayer_tax_id,
            ).load(operation=self._operation)
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
                unreadable_rows=secure_object_unreadable_total(ports=self._diagnostics_ports),
            )
        except ProfileAccessRefusedError:
            raise
        except Exception as exc:
            raise StateProjectionReadError("workspace") from exc

    def read_profile(self, *, profile_id: str) -> StateProjectionProfileRead | None:
        """Read the profile pointer and its authenticated current record."""
        self._require_bucket(profile_id)
        try:
            pointer = read_profile_bucket_by_id(profile_id)
            if pointer is None:
                return None
            self._require_bucket(pointer.bucket_id)
            from ....domain.calculations.registry.authority import bundled_indexed_authority

            if self._operation is not None:
                record = ProfileRecordRepository.for_current_session(
                    pointer.bucket_id,
                    profile_decode_context=self._operation.profile_decode_context(),
                ).load(pointer.bucket_id)
            else:
                with bundled_indexed_authority().operation() as operation:
                    record = ProfileRecordRepository.for_current_session(
                        pointer.bucket_id,
                        profile_decode_context=operation.profile_decode_context(),
                    ).load(pointer.bucket_id)
            return StateProjectionProfileRead(bucket_id=pointer.bucket_id, record=record)
        except ProfileAccessRefusedError:
            raise
        except Exception as exc:
            raise StateProjectionReadError("profile") from exc
