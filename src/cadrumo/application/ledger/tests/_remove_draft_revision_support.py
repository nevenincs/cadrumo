"""Real revision fixtures for ledger removal advisory tests."""

from __future__ import annotations

from datetime import datetime

from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....core import CasillaId, Period, validated_casilla_id
from ....domain.modelos import (
    CalculationRevision,
    CalculationRevisionCatalogue,
    CalculationRevisionState,
    ModeloCode,
    WorkUnit,
    WorkUnitCatalogue,
    derive_calculation_revision_id,
    derive_work_unit_id,
)
from ....tests import general_m303_filing_evidence
from ....tests.registry_observations import registry_grounded_observations
from ._action_test_support import (
    _BUCKET_ID,
    UTC,
    Decimal,
    ManualLedgerTransactionCommand,
    SecureObjectRepository,
    TransactionDirection,
    _repositories,
    create_manual_transaction,
    date,
)

_REVISION_CASILLA: CasillaId = validated_casilla_id("01")


def _seed_revision_citing_transaction(
    objects: SecureObjectRepository,
    *,
    transaction_id: str,
    state: CalculationRevisionState,
    period_code: str,
    bucket_id: str = _BUCKET_ID,
) -> str:
    """Seed one real revision in ``state`` that cites ``transaction_id``."""
    period = Period.from_year_and_code(2026, period_code)
    work_unit_id = derive_work_unit_id(
        bucket_id=bucket_id,
        modelo="303",
        filing_year=2026,
        period=period,
        revision_id="2022",
    )
    filing_instance_evidence = general_m303_filing_evidence(period, reference="test:remove-draft-revision")
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit_id,
        input_values_by_casilla_id={_REVISION_CASILLA: "1"},
        binding_overrides={},
        casilla_values={_REVISION_CASILLA: Decimal("1")},
        source_transaction_ids=(transaction_id,),
        filing_instance_evidence=filing_instance_evidence,
        source_provenance=(),
    )
    work_unit = WorkUnit(
        work_unit_id=work_unit_id,
        bucket_id=bucket_id,
        modelo=ModeloCode("303"),
        filing_year=2026,
        period=period,
        revision_id="2022",
        name=f"303-2026-{period_code}",
        created_at=datetime(2026, 5, 1, 8, 0, tzinfo=UTC),
        updated_at=datetime(2026, 5, 2, 8, 0, tzinfo=UTC),
        current_calculation_revision_id=revision_id,
    )
    verified_at: datetime | None = None
    verified_by: str | None = None
    discarded_at: datetime | None = None
    discarded_by: str | None = None
    if state is CalculationRevisionState.VERIFICADO_COMPLETO:
        verified_at = datetime(2026, 5, 2, 9, 0, tzinfo=UTC)
        verified_by = "operator-A"
    elif state is CalculationRevisionState.DESCARTADO:
        discarded_at = datetime(2026, 5, 2, 9, 0, tzinfo=UTC)
        discarded_by = "operator-A"
    revision = CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=work_unit_id,
        state=state,
        input_values_by_casilla_id={_REVISION_CASILLA: "1"},
        binding_overrides={},
        source_transaction_ids=(transaction_id,),
        casilla_values={_REVISION_CASILLA: Decimal("1")},
        observations=registry_grounded_observations(
            modelo="303",
            filing_year=2026,
            period=period.registry_token,
            casilla_values={_REVISION_CASILLA: Decimal("1")},
        ),
        created_at=datetime(2026, 5, 2, 8, 0, tzinfo=UTC),
        updated_at=datetime(2026, 5, 2, 9, 0, tzinfo=UTC),
        verified_at=verified_at,
        verified_by=verified_by,
        discarded_at=discarded_at,
        discarded_by=discarded_by,
        filing_instance_evidence=filing_instance_evidence,
        source_provenance=(),
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
            bucket_id=_BUCKET_ID,
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
