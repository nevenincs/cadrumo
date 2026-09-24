"""Real revision fixtures for ledger removal advisory tests."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from cadrumo.domain.modelos.tests.work_unit_catalogue_support import build_work_unit_catalogue

from .....application.calculations.tests.filing_evidence import general_m303_filing_evidence
from .....application.ledger.actions_manual import create_manual_transaction
from .....application.ledger.models import ManualLedgerTransactionCommand
from .....core.casilla_id import CasillaId, validated_casilla_id
from .....core.period import Period
from .....domain.calculations.registry.authority import PinnedAuthorityOperation
from .....domain.calculations.registry.tests.registry_observations import registry_grounded_observations
from .....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionCatalogue,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from .....domain.modelos.codes import ModeloCode
from .....domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from .....domain.transactions.enums import TransactionDirection
from ...storage.sql.secure_objects import SecureObjectRepository
from ..modelos_calculation import CalculationRevisionCatalogueRepository
from ..modelos_work_units import WorkUnitCatalogueRepository
from .ledger_action_create_support import ledger_ports_for_test
from .ledger_action_persistence_support import (
    BUCKET_ID as _BUCKET_ID,
)
from .ledger_action_persistence_support import (
    repositories as _repositories,
)

_REVISION_CASILLA: CasillaId = validated_casilla_id("01")


def seed_revision_citing_transaction(
    objects: SecureObjectRepository,
    *,
    transaction_id: str,
    state: CalculationRevisionState,
    period_code: str,
    bucket_id: str = _BUCKET_ID,
    operation: PinnedAuthorityOperation,
) -> str:
    """Seed one real revision in ``state`` that cites ``transaction_id``."""
    period = Period.from_year_and_code(2026, period_code)
    registry_snapshot_ref = operation.snapshot(
        "303",
        filing_year=period.filing_year,
        period=period.registry_token,
    ).snapshot_ref
    work_unit_id = derive_work_unit_id(
        bucket_id=bucket_id,
        modelo="303",
        filing_year=2026,
        period=period,
        revision_id=registry_snapshot_ref.revision_id,
    )
    filing_instance_evidence = general_m303_filing_evidence(
        period, reference="test:remove-draft-revision", operation=operation
    )
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
        revision_id=registry_snapshot_ref.revision_id,
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
        registry_snapshot_ref=registry_snapshot_ref,
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
    WorkUnitCatalogueRepository(objects=objects).save(build_work_unit_catalogue((work_unit,)))
    catalogue = CalculationRevisionCatalogueRepository(objects=objects).load()
    merged = dict(catalogue.revisions)
    merged[revision_id] = revision
    CalculationRevisionCatalogueRepository(objects=objects).save(
        CalculationRevisionCatalogue(revisions=merged),
    )
    return revision_id


def create_row(
    objects: SecureObjectRepository,
    *,
    idempotency_key: str,
    description: str,
) -> str:
    transaction_repository, event_repository = _repositories(objects)
    with ledger_ports_for_test(
        bucket_id=_BUCKET_ID,
        objects=objects,
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
    ) as ports:
        created = create_manual_transaction(
            ManualLedgerTransactionCommand(
                bucket_id=_BUCKET_ID,
                booked_date=date(2026, 5, 2),
                amount=Decimal("1200.00"),
                direction=TransactionDirection.INCOMING,
                description=description,
                idempotency_key=idempotency_key,
            ),
            ports=ports,
            occurred_at=datetime(2026, 5, 4, 9, 30, tzinfo=UTC),
        )
    return created.ref.transaction_id
