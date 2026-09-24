"""Finalized modelo revisions block ledger transaction removal."""

from __future__ import annotations

import pytest

from cadrumo.adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.application.ledger.actions_lifecycle import remove_manual_transaction
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.modelos.calculation_revision import CalculationRevisionState
from cadrumo.domain.transactions.errors import TransactionValidationError

from .ledger_action_persistence_support import (
    BUCKET_ID as _BUCKET_ID,
    repositories as _repositories,
)
from .remove_draft_revision_support import create_row, seed_revision_citing_transaction

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_remove_finalized_revision_still_blocks_and_not_advised(
    secure_objects: SecureObjectRepository, *, operation: PinnedAuthorityOperation
) -> None:
    # Re-pin the finalized BLOCK path: a VERIFICADO_COMPLETO revision citing the
    # row still refuses removal, and the draft-advisory channel stays empty.
    transaction_repository, event_repository = _repositories(secure_objects)
    transaction_id = create_row(
        secure_objects,
        idempotency_key="remove-finalized",
        description="finalized-cited income",
    )
    finalized_revision_id = seed_revision_citing_transaction(
        secure_objects,
        transaction_id=transaction_id,
        state=CalculationRevisionState.VERIFICADO_COMPLETO,
        period_code="1T",
        operation=operation,
    )

    dry_run = remove_manual_transaction(
        bucket_id=_BUCKET_ID,
        transaction_id=transaction_id,
        actor="operator-A",
        dry_run=True,
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        work_unit_repository=WorkUnitCatalogueRepository(objects=secure_objects),
        calculation_repository=CalculationRevisionCatalogueRepository(objects=secure_objects),
    )
    assert dry_run.blocking_modelo_references[0].calculation_revision_id == finalized_revision_id
    assert dry_run.stale_draft_revision_references == ()

    with pytest.raises(TransactionValidationError, match="finalized modelo"):
        remove_manual_transaction(
            bucket_id=_BUCKET_ID,
            transaction_id=transaction_id,
            actor="operator-A",
            transaction_repository=transaction_repository,
            bucket_event_repository=event_repository,
            work_unit_repository=WorkUnitCatalogueRepository(objects=secure_objects),
            calculation_repository=CalculationRevisionCatalogueRepository(objects=secure_objects),
        )
    assert transaction_repository.load().get(transaction_id) is not None
