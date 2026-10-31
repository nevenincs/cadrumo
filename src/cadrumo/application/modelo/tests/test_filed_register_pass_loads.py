"""A pass over a profile's sealed revisions reads the asset register and the transactions once, not once per revision.

The register comparison, the membership query and the resolvers are the real
ones. The stores behind them count their loads, and the profile record, whose
read is not the subject, is supplied directly.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, date, datetime
from typing import override

import pytest

from cadrumo.application.aggregation.tests.usage_ratio_support import no_stored_usage_ratios
from cadrumo.domain.calculations.registry.tests.published_authority import (
    leased_profile_create_context as _profile_creation_context_for_test,
)
from cadrumo.domain.user_profile.values import create_user_profile_record as _create_profile_record_for_test

from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.tests.published_authority import published_snapshot
from ....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from ....domain.modelos.codes import ModeloCode
from ....domain.modelos.ledger_filing_snapshot import FiledRegisterState
from ....domain.modelos.work_unit import WorkUnit, WorkUnitCatalogue, derive_work_unit_id
from ....domain.transactions.date_partition import LedgerDatePartition
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact
from ...actividad_asset.history import ActivityAssetHistory
from ...aggregation.ledger_filing_snapshot import stale_filed_revisions
from ...aggregation.ledger_membership import LedgerMembershipPorts
from ...aggregation.tests.ledger_source_mesh_support import (
    BUCKET_ID,
    EmptyInventoryRepository,
    EmptyInvestmentRegisterRepository,
    InMemoryTransactionCatalogueRepository,
    StaticActivityAssetHistoryRepository,
    catalogue_read_ports,
    empty_invoice_repository,
    empty_prorrata_repository,
    machine_acquisition_transaction,
    machine_asset,
    machine_claim,
    resolve_m100,
)
from .. import filed_register_reader as reader_module
from ..calculation_bucket_actions import _source_provenance_refs
from ..filed_register_reader import filed_register_reader
from ..work_profile import ModeloWorkProfile

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_AT = datetime(2026, 4, 20, 12, 0, tzinfo=UTC)
_YEARS = (2025, 2024, 2023)
"""One sealed revision per year; each year asks the stores a different window."""


class _CountingHistory(StaticActivityAssetHistoryRepository):
    """The register store, counting how often a pass reads it."""

    def __init__(self, history: ActivityAssetHistory) -> None:
        super().__init__(history)
        self.loads = 0
        self.replace_with: ActivityAssetHistory | None = None

    @override
    def load(self) -> ActivityAssetHistory:
        self.loads += 1
        if self.replace_with is not None:
            self._history, self.replace_with = self.replace_with, None
        return super().load()


class _CountingTransactions(InMemoryTransactionCatalogueRepository):
    """The ledger store, counting each distinct read a pass makes of it."""

    def __init__(self, catalogue: TransactionCatalogue) -> None:
        super().__init__(bucket_id=BUCKET_ID)
        self.save(catalogue)
        self.reads: list[tuple[object, ...]] = []

    @override
    def load(self) -> TransactionCatalogue:
        self.reads.append(("load",))
        return super().load()

    @override
    def load_by_ids(self, transaction_ids: Iterable[str]) -> TransactionCatalogue:
        ids = tuple(sorted(set(transaction_ids)))
        self.reads.append(("load_by_ids", ids))
        return super().load_by_ids(ids)

    @override
    def partition_by_date_range(self, start: date, end: date) -> LedgerDatePartition:
        self.reads.append(("partition", start, end))
        return super().partition_by_date_range(start, end)


def _seal(operation: PinnedAuthorityOperation, history: ActivityAssetHistory, rows: tuple[Transaction, ...]):
    """Calculate each year's revision through the real resolver and seal what its provenance says."""
    snapshot = published_snapshot("100", filing_year=2025, period="0A")
    units: dict[str, WorkUnit] = {}
    sealed: dict[str, CalculationRevision] = {}
    for year in _YEARS:
        period = Period.from_year_and_code(year, "0A")
        unit = WorkUnit(
            work_unit_id=derive_work_unit_id(
                bucket_id=BUCKET_ID, modelo="100", filing_year=year, period=period, revision_id=snapshot.revision.id
            ),
            bucket_id=BUCKET_ID,
            modelo=ModeloCode("100"),
            filing_year=year,
            period=period,
            revision_id=snapshot.revision.id,
            name=f"100-{year}-0A",
            created_at=_AT,
            updated_at=_AT,
        )
        provenance = _source_provenance_refs(resolve_m100(history, rows=rows, year=year))
        draft = CalculationRevision(
            calculation_revision_id=derive_calculation_revision_id(
                work_unit_id=unit.work_unit_id,
                input_values_by_casilla_id={},
                binding_overrides={},
                casilla_values={},
                filing_instance_evidence=None,
                source_provenance=provenance,
            ),
            work_unit_id=unit.work_unit_id,
            registry_snapshot_ref=snapshot.snapshot_ref,
            state=CalculationRevisionState.BORRADOR,
            input_values_by_casilla_id={},
            binding_overrides={},
            casilla_values={},
            observations=(),
            created_at=_AT,
            updated_at=_AT,
            filing_instance_evidence=None,
            source_provenance=provenance,
        )
        units[unit.work_unit_id] = unit
        filed = draft.model_copy(update={"state": CalculationRevisionState.PRESENTADO})
        sealed[filed.calculation_revision_id] = filed
    return WorkUnitCatalogue(work_units=units), sealed


def _pass_ports(history: _CountingHistory, transactions: _CountingTransactions) -> LedgerMembershipPorts:
    return LedgerMembershipPorts(
        transaction_repository=transactions,
        invoice_catalogue_read_ports=catalogue_read_ports(
            invoice_repository=empty_invoice_repository(), transaction_repository=transactions
        ),
        prorrata_register_repository=empty_prorrata_repository(),
        bienes_inversion_repository=EmptyInvestmentRegisterRepository(),
        activity_asset_history_repository=history,
        usage_ratio_profile_loader=no_stored_usage_ratios,
        inventory_repository=EmptyInventoryRepository(),
    )


@pytest.fixture
def world(operation: PinnedAuthorityOperation, monkeypatch: pytest.MonkeyPatch):
    """Three sealed revisions over a three-asset register and its three purchases."""
    purchases = tuple(
        machine_acquisition_transaction("hardware_amortizable", provider_id=f"purchase-{index}") for index in range(3)
    )
    assets = tuple(
        machine_asset(purchase.transaction_id).model_copy(update={"asset_id": f"machine-{index}"})
        for index, purchase in enumerate(purchases)
    )
    claims = tuple(
        machine_claim(asset).model_copy(update={"schedule_fingerprint": f"{index:064x}"})
        for index, asset in enumerate(assets)
    )
    register = ActivityAssetHistory(revisions=assets, claims=claims)
    profile = ModeloWorkProfile(
        record=_create_profile_record_for_test(
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=BUCKET_ID,
            facts=(UserProfileFact(path="identity.tax_id", value="X1234567L"),),
            context=_profile_creation_context_for_test(),
        ),
        profile_decode_context=operation.profile_decode_context(),
    )
    monkeypatch.setattr(reader_module, "load_modelo_work_profile", lambda **_: profile)
    units, sealed = _seal(operation, register, purchases)
    history = _CountingHistory(register)
    transactions = _CountingTransactions(TransactionCatalogue.from_transactions(purchases))
    return units, sealed, history, transactions, operation


def test_a_pass_reads_the_register_once_however_many_revisions_it_compares(world) -> None:
    units, sealed, history, transactions, operation = world
    read = filed_register_reader(
        bucket_id=BUCKET_ID, work_units=units, ports=_pass_ports(history, transactions), operation=operation
    )

    findings = stale_filed_revisions(revisions=sealed, catalogue=TransactionCatalogue(), register_reader=read)

    assert len(sealed) == len(_YEARS)
    assert findings == ()
    assert history.loads == 1
    assert len(transactions.reads) == len(set(transactions.reads)), "a pass asked its ledger the same question twice"


def test_a_later_pass_reads_the_register_again_and_sees_what_changed_in_between(world) -> None:
    units, sealed, history, transactions, operation = world
    ports = _pass_ports(history, transactions)

    def run_pass():
        read = filed_register_reader(bucket_id=BUCKET_ID, work_units=units, ports=ports, operation=operation)
        return stale_filed_revisions(revisions=sealed, catalogue=TransactionCatalogue(), register_reader=read)

    assert run_pass() == ()
    first_pass_loads = history.loads
    shrunk = ActivityAssetHistory(revisions=history.load().revisions[:2], claims=history.load().claims[:2])
    history.replace_with = shrunk
    findings = run_pass()

    assert history.loads > first_pass_loads
    # Only the 2025 revision consumed claims; the earlier years' filings rested on none.
    ((revision, verdict),) = findings
    assert revision.work_unit_id in units.work_units
    assert units.work_units[revision.work_unit_id].filing_year == 2025
    assert verdict.register_state is FiledRegisterState.CHANGED
    assert verdict.register_change_count == 1
