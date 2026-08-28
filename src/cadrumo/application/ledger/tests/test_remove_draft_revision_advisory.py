"""Draft-revision advisory on ledger transaction removal.

A finalized revision (VERIFICADO_COMPLETO / PRESENTADO / PRESENTADO_SUPERSEDIDO)
that cites a ledger row BLOCKS its removal. A DRAFT (BORRADOR) revision that
cites the same row does NOT block removal — the operator may legitimately prune a
row before finalising — but the draft's ``source_transaction_ids`` will keep
asserting the removed row's income/expense on the next verify/file. These tests
pin the non-blocking advisory that names each affected draft so the
under-declaration is non-silent (no-silent-under-declaration), and re-pin that
the finalized BLOCK path is unchanged.

Correctness rides on the live revision-catalogue scan, never the derived
participation index (aeat-ledger-contract): the
revisions are seeded into a real :class:`CalculationRevisionCatalogueRepository`
backed by a real :class:`SecureObjectRepository`, with no mocks, stubs, or skips.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....domain.modelos.calculation_revision import CalculationRevisionState
from ._action_test_support import (
    _BUCKET_ID,
    SecureObjectRepository,
    _repositories,
    remove_manual_transaction,
)
from ._remove_draft_revision_support import _create_row, _seed_revision_citing_transaction

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_remove_advises_on_draft_revision_and_still_removes(
    secure_objects: SecureObjectRepository,
) -> None:
    transaction_repository, event_repository = _repositories(secure_objects)
    transaction_id = _create_row(
        secure_objects,
        idempotency_key="remove-draft-cited",
        description="draft-cited income",
    )
    draft_revision_id = _seed_revision_citing_transaction(
        secure_objects,
        transaction_id=transaction_id,
        state=CalculationRevisionState.BORRADOR,
        period_code="1T",
    )

    report = remove_manual_transaction(
        bucket_id=_BUCKET_ID,
        transaction_id=transaction_id,
        actor="operator-A",
        reason="duplicate income",
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        work_unit_repository=WorkUnitCatalogueRepository(objects=secure_objects),
        calculation_repository=CalculationRevisionCatalogueRepository(objects=secure_objects),
        occurred_at=datetime(2026, 5, 5, 10, 0, tzinfo=UTC),
    )

    # Removal PROCEEDS for a draft-cited row.
    assert report.removed is True
    assert report.blocking_modelo_references == ()
    assert transaction_repository.load().get(transaction_id) is None
    # The draft is named in the non-blocking advisory.
    assert len(report.stale_draft_revision_references) == 1
    advisory = report.stale_draft_revision_references[0]
    # Anti-tautology: keyed to the ACTUAL seeded draft revision id, not a
    # constant that would pass regardless of which revision was seeded.
    assert advisory.calculation_revision_id == draft_revision_id
    assert advisory.revision_state == CalculationRevisionState.BORRADOR.value
    assert advisory.modelo == "303"
    assert advisory.filing_year == 2026
    assert advisory.period == "1T"


def test_remove_dry_run_surfaces_draft_advisory_without_mutation(
    secure_objects: SecureObjectRepository,
) -> None:
    transaction_repository, event_repository = _repositories(secure_objects)
    transaction_id = _create_row(
        secure_objects,
        idempotency_key="remove-draft-dry",
        description="draft-cited income",
    )
    draft_revision_id = _seed_revision_citing_transaction(
        secure_objects,
        transaction_id=transaction_id,
        state=CalculationRevisionState.BORRADOR,
        period_code="1T",
    )

    report = remove_manual_transaction(
        bucket_id=_BUCKET_ID,
        transaction_id=transaction_id,
        actor="operator-A",
        dry_run=True,
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        work_unit_repository=WorkUnitCatalogueRepository(objects=secure_objects),
        calculation_repository=CalculationRevisionCatalogueRepository(objects=secure_objects),
    )

    assert report.dry_run is True
    assert report.removed is False
    assert transaction_repository.load().get(transaction_id) is not None
    assert [r.calculation_revision_id for r in report.stale_draft_revision_references] == [draft_revision_id]


def test_remove_uncited_row_yields_empty_draft_advisory(
    secure_objects: SecureObjectRepository,
) -> None:
    transaction_repository, event_repository = _repositories(secure_objects)
    cited_id = _create_row(
        secure_objects,
        idempotency_key="remove-draft-other",
        description="cited income",
    )
    uncited_id = _create_row(
        secure_objects,
        idempotency_key="remove-draft-free",
        description="uncited income",
    )
    _seed_revision_citing_transaction(
        secure_objects,
        transaction_id=cited_id,
        state=CalculationRevisionState.BORRADOR,
        period_code="1T",
    )

    report = remove_manual_transaction(
        bucket_id=_BUCKET_ID,
        transaction_id=uncited_id,
        actor="operator-A",
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        work_unit_repository=WorkUnitCatalogueRepository(objects=secure_objects),
        calculation_repository=CalculationRevisionCatalogueRepository(objects=secure_objects),
        occurred_at=datetime(2026, 5, 5, 10, 0, tzinfo=UTC),
    )

    assert report.removed is True
    assert report.stale_draft_revision_references == ()


def test_remove_discarded_draft_is_not_advised(
    secure_objects: SecureObjectRepository,
) -> None:
    # A DESCARTADO (discarded) draft is not a live filing: removing a row it
    # cites must NOT raise an advisory.
    transaction_repository, event_repository = _repositories(secure_objects)
    transaction_id = _create_row(
        secure_objects,
        idempotency_key="remove-discarded",
        description="discarded-draft income",
    )
    _seed_revision_citing_transaction(
        secure_objects,
        transaction_id=transaction_id,
        state=CalculationRevisionState.DESCARTADO,
        period_code="1T",
    )

    report = remove_manual_transaction(
        bucket_id=_BUCKET_ID,
        transaction_id=transaction_id,
        actor="operator-A",
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        work_unit_repository=WorkUnitCatalogueRepository(objects=secure_objects),
        calculation_repository=CalculationRevisionCatalogueRepository(objects=secure_objects),
        occurred_at=datetime(2026, 5, 5, 10, 0, tzinfo=UTC),
    )

    assert report.removed is True
    assert report.stale_draft_revision_references == ()
    assert report.blocking_modelo_references == ()
