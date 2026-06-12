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
participation index (ledger-participation-index-is-derived-rebuildable): the
revisions are seeded into a real :class:`CalculationRevisionCatalogueRepository`
backed by a real :class:`SecureObjectRepository`, with no mocks, stubs, or skips.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from ....core import Period
from ....domain.modelos._calculation_repository import CalculationRevisionCatalogueRepository
from ....domain.modelos._calculation_revision import (
    CalculationRevision,
    CalculationRevisionCatalogue,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from ....domain.modelos._codes import ModeloCode
from ....domain.modelos._repository import WorkUnitCatalogueRepository
from ....domain.modelos._work_unit import (
    WorkUnit,
    WorkUnitCatalogue,
    derive_work_unit_id,
)
from ._action_test_support import (
    UTC,
    Decimal,
    ManualLedgerTransactionCommand,
    SecureObjectRepository,
    TransactionDirection,
    TransactionValidationError,
    _repositories,
    create_manual_transaction,
    date,
    remove_manual_transaction,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _seed_revision_citing_transaction(
    objects: SecureObjectRepository,
    *,
    transaction_id: str,
    state: CalculationRevisionState,
    period_code: str,
    bucket_id: str = "bucket-a",
) -> str:
    """Seed one real revision (in ``state``) citing ``transaction_id``.

    Returns the derived calculation_revision_id so the caller can assert the
    advisory is keyed to the actual seeded id (anti-tautology). The ``period_code``
    keeps each seeded work unit / revision distinct so multiple states can
    coexist in one catalogue.
    """
    period = Period.from_year_and_code(2026, period_code)
    work_unit_id = derive_work_unit_id(
        bucket_id=bucket_id,
        modelo="303",
        filing_year=2026,
        period=period,
        revision_id="2009-y-siguientes",
    )
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit_id,
        inputs_snapshot={"01": "1"},
        binding_overrides={},
        casilla_values={"01": Decimal("1")},
        source_transaction_ids=(transaction_id,),
    )
    work_unit = WorkUnit(
        work_unit_id=work_unit_id,
        bucket_id=bucket_id,
        modelo=ModeloCode("303"),
        filing_year=2026,
        period=period,
        revision_id="2009-y-siguientes",
        name=f"303-2026-{period_code}",
        created_at=datetime(2026, 5, 1, 8, 0, tzinfo=UTC),
        updated_at=datetime(2026, 5, 2, 8, 0, tzinfo=UTC),
        current_calculation_revision_id=revision_id,
    )
    audit_fields: dict[str, object] = {}
    if state is CalculationRevisionState.VERIFICADO_COMPLETO:
        audit_fields = {
            "verified_at": datetime(2026, 5, 2, 9, 0, tzinfo=UTC),
            "verified_by": "operator-A",
        }
    elif state is CalculationRevisionState.DESCARTADO:
        audit_fields = {
            "discarded_at": datetime(2026, 5, 2, 9, 0, tzinfo=UTC),
            "discarded_by": "operator-A",
        }
    revision = CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=work_unit_id,
        state=state,
        inputs_snapshot={"01": "1"},
        binding_overrides={},
        source_transaction_ids=(transaction_id,),
        casilla_values={"01": Decimal("1")},
        created_at=datetime(2026, 5, 2, 8, 0, tzinfo=UTC),
        updated_at=datetime(2026, 5, 2, 9, 0, tzinfo=UTC),
        **audit_fields,
    )
    WorkUnitCatalogueRepository(objects=objects).save(WorkUnitCatalogue.from_work_units((work_unit,)))
    catalogue = CalculationRevisionCatalogueRepository(objects=objects).load()
    merged = dict(catalogue.revisions)
    merged[revision_id] = revision
    CalculationRevisionCatalogueRepository(objects=objects).save(
        CalculationRevisionCatalogue(revisions=merged),
    )
    return revision_id


def _create_row(
    objects: SecureObjectRepository,
    *,
    idempotency_key: str,
    description: str,
) -> str:
    transaction_repository, event_repository = _repositories(objects)
    created = create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id="bucket-a",
            booked_date=date(2026, 5, 2),
            amount=Decimal("1200.00"),
            direction=TransactionDirection.INCOMING,
            description=description,
            idempotency_key=idempotency_key,
        ),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 4, 9, 30, tzinfo=UTC),
    )
    return created.ref.transaction_id


def test_remove_advises_on_draft_revision_and_still_removes(
    secure_objects: SecureObjectRepository,
) -> None:
    transaction_repository, event_repository = _repositories(secure_objects)
    transaction_id = _create_row(
        secure_objects, idempotency_key="remove-draft-cited", description="draft-cited income",
    )
    draft_revision_id = _seed_revision_citing_transaction(
        secure_objects,
        transaction_id=transaction_id,
        state=CalculationRevisionState.BORRADOR,
        period_code="1T",
    )

    report = remove_manual_transaction(
        bucket_id="bucket-a",
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
        secure_objects, idempotency_key="remove-draft-dry", description="draft-cited income",
    )
    draft_revision_id = _seed_revision_citing_transaction(
        secure_objects,
        transaction_id=transaction_id,
        state=CalculationRevisionState.BORRADOR,
        period_code="1T",
    )

    report = remove_manual_transaction(
        bucket_id="bucket-a",
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
        secure_objects, idempotency_key="remove-draft-other", description="cited income",
    )
    uncited_id = _create_row(
        secure_objects, idempotency_key="remove-draft-free", description="uncited income",
    )
    _seed_revision_citing_transaction(
        secure_objects,
        transaction_id=cited_id,
        state=CalculationRevisionState.BORRADOR,
        period_code="1T",
    )

    report = remove_manual_transaction(
        bucket_id="bucket-a",
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
        secure_objects, idempotency_key="remove-discarded", description="discarded-draft income",
    )
    _seed_revision_citing_transaction(
        secure_objects,
        transaction_id=transaction_id,
        state=CalculationRevisionState.DESCARTADO,
        period_code="1T",
    )

    report = remove_manual_transaction(
        bucket_id="bucket-a",
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


def test_remove_finalized_revision_still_blocks_and_not_advised(
    secure_objects: SecureObjectRepository,
) -> None:
    # Re-pin the finalized BLOCK path: a VERIFICADO_COMPLETO revision citing the
    # row still refuses removal, and the draft-advisory channel stays empty (the
    # blocker is not laundered into the non-blocking advisory).
    transaction_repository, event_repository = _repositories(secure_objects)
    transaction_id = _create_row(
        secure_objects, idempotency_key="remove-finalized", description="finalized-cited income",
    )
    finalized_revision_id = _seed_revision_citing_transaction(
        secure_objects,
        transaction_id=transaction_id,
        state=CalculationRevisionState.VERIFICADO_COMPLETO,
        period_code="1T",
    )

    dry_run = remove_manual_transaction(
        bucket_id="bucket-a",
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
            bucket_id="bucket-a",
            transaction_id=transaction_id,
            actor="operator-A",
            transaction_repository=transaction_repository,
            bucket_event_repository=event_repository,
            work_unit_repository=WorkUnitCatalogueRepository(objects=secure_objects),
            calculation_repository=CalculationRevisionCatalogueRepository(objects=secure_objects),
        )
    assert transaction_repository.load().get(transaction_id) is not None
