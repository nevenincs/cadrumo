"""Ledger read operations answer as a whole-catalogue read would, over real encrypted storage.

Each read below narrows what it decrypts: ``ledger.preflight`` reads the
period's date partition, the id-addressed reads (view, track, history,
participation) read one row when handed a full live id, and status and check
read the whole catalogue once and hand that snapshot to every helper. None of
that may change an answer. Every read runs through its registered executor and
the production port composition against a real bucket, and is compared with
the same executor reading through a repository whose targeted reads are
widened back to the whole catalogue -- the result a full scan gives. A
counting view of the same repository pins how much each read decrypts, and
independently stated expectations pin the boundary rows, the split lineage and
the refusals.
"""

from __future__ import annotations

import asyncio
from collections import Counter
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Protocol, cast, override
from uuid import UUID

import pytest
from pydantic import BaseModel
from sqlalchemy import delete

from ...adapters.persistence.profile.participation_index import TransactionParticipationIndexRepository
from ...adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ...adapters.persistence.storage.sql import orm
from ...adapters.persistence.storage.sql.session import session_scope
from ...adapters.persistence.storage.tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile
from ...application.ledger.action_ports import LedgerActionPorts, LedgerActionPortsFactory
from ...application.ledger.actions_manual import (
    LedgerSummaryPeriodWithoutSpanError,
    summarize_manual_transactions,
    update_manual_transaction_fields,
)
from ...application.ledger.actions_split_merge import split_transaction
from ...application.ledger.check_operation import (
    LEDGER_CHECK_OPERATION_DEFINITION_ID,
    LedgerCheckExecutor,
    LedgerCheckProjection,
    LedgerCheckRequest,
)
from ...application.ledger.history_operation import (
    LEDGER_HISTORY_OPERATION_DEFINITION_ID,
    LedgerHistoryExecutor,
    LedgerHistoryProjection,
    LedgerHistoryRequest,
)
from ...application.ledger.models import ManualLedgerTransactionCommand, ManualLedgerTransactionPatch, SplitChildCommand
from ...application.ledger.participation_operation import (
    LEDGER_PARTICIPATION_OPERATION_DEFINITION_ID,
    LedgerParticipationExecutor,
    LedgerParticipationRequest,
)
from ...application.ledger.preflight_operation import (
    LEDGER_PREFLIGHT_OPERATION_DEFINITION_ID,
    LedgerPreflightExecutor,
    LedgerPreflightProjection,
    LedgerPreflightRequest,
)
from ...application.ledger.protocols import TransactionCatalogueCoCommitWriterProtocol
from ...application.ledger.read_ports import LedgerReadPorts, LedgerReadPortsFactory
from ...application.ledger.readiness_query import read_ledger_readiness
from ...application.ledger.stale_filing_query import read_stale_ledger_filings
from ...application.ledger.status_operation import (
    LEDGER_STATUS_OPERATION_DEFINITION_ID,
    LedgerStatusExecutor,
    LedgerStatusProjection,
    LedgerStatusRequest,
)
from ...application.ledger.tests.manual_transaction_support import create_manual_transaction
from ...application.ledger.track_operation import (
    LEDGER_TRACK_OPERATION_DEFINITION_ID,
    LedgerTrackExecutor,
    LedgerTrackRequest,
)
from ...application.ledger.view_operation import (
    LEDGER_VIEW_OPERATION_DEFINITION_ID,
    LedgerViewExecutor,
    LedgerViewProjection,
    LedgerViewRequest,
)
from ...application.operations.models import OperationIdentity, OperationRequest
from ...application.operations.owner import OperationExecutorContext
from ...application.operations.public_period import PublicPeriod
from ...core.errors.error_codes import ErrorCategory, get_registered_error_code, resolve_error_message
from ...core.operations import OperationEffect, profile_operation_subject
from ...core.period import Period
from ...core.secure_object_write import SecureObjectWrite
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.iva.schema import IvaCashAccountingPaymentEvidence, IvaCashAccountingTreatment, IvaCategory
from ...domain.transactions.enums import BusinessClassification, TransactionDirection
from ...domain.transactions.errors import TransactionIdPrefixError
from ...domain.transactions.models import LedgerDatePartition, Transaction, TransactionCatalogue
from ...domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ..adapter_composition import build_verification_repository_bundle
from ..ledger_action_composition import compose_ledger_action_ports, compose_ledger_read_ports

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_BUCKET = "66666666-6666-4666-8666-666666666666"
_PROFILE_UUID = UUID(_BUCKET)
_ACTOR = "ledger-read-parity"


@dataclass(frozen=True)
class _Row:
    """One synthetic ledger row stored directly, with the facts the reads key on."""

    provider_id: str
    booked: date
    value: date | None = None
    amount: Decimal = Decimal("10.00")
    classification: BusinessClassification = BusinessClassification.BUSINESS
    accrued: date | None = None
    invoice_id: str | None = None


#: Boundary rows around the fourth quarter of 2030. Reads key on the value date
#: when present, else the booked date; the accrued rows are criterio-de-caja
#: rows whose devengo date sits apart from that filing date, so the partition
#: offers them as candidates outside their filing quarter.
_ROWS: tuple[_Row, ...] = (
    _Row("q3-last-day", booked=date(2030, 9, 30)),
    _Row("q4-first-day", booked=date(2030, 10, 1), amount=Decimal("40.00")),
    _Row("booked-q3-valued-q4", booked=date(2030, 9, 30), value=date(2030, 10, 1), amount=Decimal("5.00")),
    _Row(
        "q4-mid-pending",
        booked=date(2030, 11, 15),
        amount=Decimal("30.00"),
        classification=BusinessClassification.NOT_YET_PROCESSED,
    ),
    _Row("q4-mid-office", booked=date(2030, 11, 15), amount=Decimal("20.00")),
    _Row("q4-personal", booked=date(2030, 11, 1), classification=BusinessClassification.PERSONAL),
    _Row("q4-last-day", booked=date(2030, 12, 31), amount=Decimal("15.00")),
    _Row("booked-q4-valued-next-year", booked=date(2030, 12, 31), value=date(2031, 1, 1)),
    _Row("next-year-first-day", booked=date(2031, 1, 1)),
    _Row("same-quarter-prior-year", booked=date(2029, 11, 15)),
    _Row("filed-next-year-accrued-q4", booked=date(2031, 1, 15), amount=Decimal("1210.00"), accrued=date(2030, 11, 2)),
    _Row("filed-q4-accrued-q3", booked=date(2030, 12, 1), amount=Decimal("1210.00"), accrued=date(2030, 8, 3)),
    #: Outside every measured period, and citing an invoice the catalogue does
    #: not hold: a one-sided link the check must report whatever period it is
    #: given, because links are global.
    _Row("prior-year-one-sided-link", booked=date(2029, 6, 1), invoice_id="INV-NOT-STORED-0001"),
)

#: Independently stated: the stored rows whose filing date falls in 2030-Q4.
_Q4_2030_DIRECT: frozenset[str] = frozenset(
    {
        "q4-first-day",
        "booked-q3-valued-q4",
        "q4-mid-pending",
        "q4-mid-office",
        "q4-personal",
        "q4-last-day",
        "filed-q4-accrued-q3",
    }
)

_Q4_2030 = Period.from_year_and_code(2030, "4T")

#: The periods whose answers must not depend on which read served them,
#: including an empty one and one with no calendar span.
_PERIODS: tuple[Period, ...] = (
    _Q4_2030,
    Period.from_year_and_code(2030, "12"),
    Period.from_year_and_code(2031, "1T"),
    Period.from_year_and_code(2030, "2T"),
    Period.from_year_and_code(2030, "0A"),
    Period.from_year_and_code(2030, "1P"),
)


@dataclass(frozen=True)
class _Seeded:
    """The real bucket and the identities the id-addressed reads open."""

    profile: TestRuntimeProfile
    direct: dict[str, Transaction]
    split_parent_id: str
    split_child_ids: tuple[str, ...]
    edited_id: str
    superseded_id: str


def _transaction(row: _Row) -> Transaction:
    raw = RawTransaction(
        provider_transaction_id=row.provider_id,
        booked_date=row.booked,
        value_date=row.value,
        amount=row.amount,
        currency="EUR",
        counterparty="Proveedor Sintetico SL",
        description=f"row {row.provider_id}",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="e" * 64,
            source_row_index=1,
            source_format=SourceFormat.CSV,
            ingested_at=datetime(2031, 2, 1, 9, 0, tzinfo=UTC),
            provider_name="synthetic provider",
        ),
        raw_fields={"Concepto": row.provider_id},
    )
    fields: dict[str, object] = {
        "raw": raw,
        "direction": TransactionDirection.OUTGOING,
        "business_classification": row.classification,
        "source_jurisdiction": "ES",
        "group_label": None,
        "invoice_id": row.invoice_id,
        "created_at": datetime(2031, 2, 1, 9, 0, tzinfo=UTC),
        "modified_at": datetime(2031, 2, 1, 9, 0, tzinfo=UTC),
    }
    if row.accrued is not None:
        fields |= {
            "taxable_base": Decimal("1000.00"),
            "iva_rate": Decimal("0.21"),
            "iva_amount": Decimal("210.00"),
            "iva_category": IvaCategory("domestic_general"),
            "cash_accounting_treatment": IvaCashAccountingTreatment("supplier_regime"),
            "operation_date": row.accrued,
            "cash_accounting_payment_evidence": (
                IvaCashAccountingPaymentEvidence(
                    payment_date=row.value or row.booked,
                    taxable_base=Decimal("1000.00"),
                    iva_amount=Decimal("210.00"),
                    recargo_amount=Decimal("0.00"),
                ),
            ),
            "classified_at": datetime(2031, 2, 1, 10, 0, tzinfo=UTC),
            "classified_by": "manual",
        }
    return Transaction.model_validate(fields)


def _manual(booked: date, amount: str, description: str) -> ManualLedgerTransactionCommand:
    return ManualLedgerTransactionCommand(
        bucket_id=_BUCKET,
        booked_date=booked,
        amount=Decimal(amount),
        direction=TransactionDirection.OUTGOING,
        counterparty="Proveedor Manual SL",
        description=description,
        actor=_ACTOR,
    )


@pytest.fixture
def seeded(tmp_path: Path, authority_operation: PinnedAuthorityOperation) -> Iterator[_Seeded]:
    """Seed one real bucket: stored boundary rows, a split, and an edited row with its old id."""
    direct = {row.provider_id: _transaction(row) for row in _ROWS}
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET) as profile:
        TransactionCatalogueRepository(bucket_id=_BUCKET).save(TransactionCatalogue.from_transactions(direct.values()))
        ports = compose_ledger_action_ports(bucket_id=_BUCKET, operation=authority_operation)
        parent = create_manual_transaction(
            _manual(date(2030, 11, 20), "100.00", "split parent"),
            ports=ports,
            occurred_at=datetime(2031, 2, 2, 9, 0, tzinfo=UTC),
        )
        split = split_transaction(
            bucket_id=_BUCKET,
            transaction_id=parent.ref.transaction_id,
            children=(
                SplitChildCommand(amount=Decimal("60.00"), description="split slice a"),
                SplitChildCommand(amount=Decimal("40.00"), description="split slice b"),
            ),
            actor=_ACTOR,
            ports=compose_ledger_action_ports(bucket_id=_BUCKET, operation=authority_operation),
            occurred_at=datetime(2031, 2, 2, 10, 0, tzinfo=UTC),
        )
        original = create_manual_transaction(
            _manual(date(2030, 12, 15), "50.00", "before the edit"),
            ports=compose_ledger_action_ports(bucket_id=_BUCKET, operation=authority_operation),
            occurred_at=datetime(2031, 2, 3, 9, 0, tzinfo=UTC),
        )
        edited = update_manual_transaction_fields(
            bucket_id=_BUCKET,
            transaction_id=original.ref.transaction_id,
            patch=ManualLedgerTransactionPatch(description="after the edit"),
            actor=_ACTOR,
            source_command="aeat app ledger edit",
            ports=compose_ledger_action_ports(bucket_id=_BUCKET, operation=authority_operation),
            occurred_at=datetime(2031, 2, 3, 10, 0, tzinfo=UTC),
        )
        assert edited.ref.transaction_id != original.ref.transaction_id, (
            "the edit must re-derive the id for the superseded handle to mean anything"
        )
        yield _Seeded(
            profile=profile,
            direct=direct,
            split_parent_id=parent.ref.transaction_id,
            split_child_ids=tuple(split.child_transaction_ids),
            edited_id=edited.ref.transaction_id,
            superseded_id=original.ref.transaction_id,
        )


# ---------------------------------------------------------------------------
# Observed and whole-catalogue repositories
# ---------------------------------------------------------------------------


class _ObservedReads(TransactionCatalogueCoCommitWriterProtocol):
    """Count every catalogue read; when ``widen`` is set, answer targeted reads with the whole catalogue.

    The widened view is the full-scan reference: an executor reading through it
    sees every row wherever it asked for one row or one period, which is what a
    whole-catalogue read gave before the reads were narrowed.
    """

    def __init__(self, repository: TransactionCatalogueCoCommitWriterProtocol, *, widen: bool) -> None:
        self._repository = repository
        self._widen = widen
        self.calls: Counter[str] = Counter()

    @property
    @override
    def bucket_id(self) -> str:
        return self._repository.bucket_id

    @override
    def exists(self) -> bool:
        self.calls["exists"] += 1
        return self._repository.exists()

    @override
    def load(self) -> TransactionCatalogue:
        self.calls["load"] += 1
        return self._repository.load()

    @override
    def load_for_date_range(self, start: date, end: date) -> TransactionCatalogue:
        self.calls["load_for_date_range"] += 1
        return self._repository.load_for_date_range(start, end)

    @override
    def load_by_ids(self, transaction_ids: Iterable[str]) -> TransactionCatalogue:
        self.calls["load_by_ids"] += 1
        if self._widen:
            return self._repository.load()
        return self._repository.load_by_ids(transaction_ids)

    @override
    def partition_by_date_range(self, start: date, end: date) -> LedgerDatePartition:
        self.calls["partition_by_date_range"] += 1
        if self._widen:
            return LedgerDatePartition(in_window=self._repository.load(), index_complete=False)
        return self._repository.partition_by_date_range(start, end)

    @override
    def save(self, catalogue: TransactionCatalogue) -> None:
        raise AssertionError("a ledger read must not write the catalogue")

    @override
    def save_with_secure_object_writes(
        self,
        catalogue: TransactionCatalogue,
        extra_writes: tuple[SecureObjectWrite, ...],
    ) -> None:
        raise AssertionError("a ledger read must not write the catalogue")

    @override
    def replace_if_current_with_secure_object_writes(
        self,
        current: Transaction,
        replacement: Transaction,
        extra_writes: tuple[SecureObjectWrite, ...],
    ) -> None:
        raise AssertionError("a ledger read must not write the catalogue")


@dataclass
class _Observer:
    """Collect the repositories handed to one executor run."""

    widen: bool
    repositories: list[_ObservedReads]

    def observe(self, repository: TransactionCatalogueCoCommitWriterProtocol) -> _ObservedReads:
        observed = _ObservedReads(repository, widen=self.widen)
        self.repositories.append(observed)
        return observed

    def calls(self) -> Counter[str]:
        total: Counter[str] = Counter()
        for repository in self.repositories:
            total.update(repository.calls)
        return total


def _action_ports(observer: _Observer) -> LedgerActionPortsFactory:
    def build(*, bucket_id: str, operation: PinnedAuthorityOperation) -> LedgerActionPorts:
        ports = compose_ledger_action_ports(bucket_id=bucket_id, operation=operation)
        return replace(ports, transaction_repository=observer.observe(ports.transaction_repository))

    return build


def _read_ports(observer: _Observer) -> LedgerReadPortsFactory:
    def build(*, bucket_id: str, operation: PinnedAuthorityOperation) -> LedgerReadPorts:
        ports = compose_ledger_read_ports(bucket_id=bucket_id, operation=operation)
        return replace(ports, transaction_repository=observer.observe(ports.transaction_repository))

    return build


# ---------------------------------------------------------------------------
# Running a registered executor
# ---------------------------------------------------------------------------


class _Executor[PayloadT: BaseModel](Protocol):
    async def execute(self, request: OperationRequest[PayloadT], context: OperationExecutorContext) -> str: ...


class _Events:
    async def phase(self, code: str) -> None:
        del code

    async def effect(self, effect: OperationEffect) -> None:
        assert effect is OperationEffect.NONE


@dataclass
class _Operands:
    stored: list[BaseModel]

    async def put(self, value: BaseModel, *, written_at: datetime) -> str:
        del written_at
        self.stored.append(value)
        return "result"


#: A refusal compared by its type, translation key, context and rendered text.
type _Refusal = tuple[str, str | None, dict[str, object] | None, str]
type _Outcome = BaseModel | _Refusal


def _execute[PayloadT: BaseModel](
    executor: _Executor[PayloadT],
    definition_id: str,
    payload: PayloadT,
    operation: PinnedAuthorityOperation,
) -> _Outcome:
    """Run one executor to its captured result, or to the refusal its read raised."""
    subject_ref = profile_operation_subject(_BUCKET)
    request = OperationRequest(definition_id=definition_id, subject_ref=subject_ref, payload=payload)
    operands = _Operands(stored=[])
    context = cast(
        OperationExecutorContext,
        SimpleNamespace(
            identity=OperationIdentity(operation_id="b" * 64, definition_id=definition_id, subject_ref=subject_ref),
            events=_Events(),
            operands=operands,
            authority_operation=operation,
        ),
    )
    try:
        asyncio.run(executor.execute(request, context))
    except TransactionIdPrefixError as refused:
        return (type(refused).__name__, refused.translated_message, refused.context, str(refused))
    assert len(operands.stored) == 1
    return operands.stored[0]


type _Run = Callable[[_Observer], _Outcome]


def _paired(run: _Run) -> tuple[_Outcome, Counter[str], _Outcome]:
    """Run once through the real repository and once through the whole-catalogue reference."""
    observed = _Observer(widen=False, repositories=[])
    outcome = run(observed)
    reference = run(_Observer(widen=True, repositories=[]))
    return outcome, observed.calls(), reference


# ---------------------------------------------------------------------------
# Index staleness
# ---------------------------------------------------------------------------


def _drop_index_rows(profile: TestRuntimeProfile, transaction_ids: frozenset[str] | None) -> None:
    """Remove date-index rows as a crash between the encrypted commit and the index sync would."""
    statement = delete(orm.TransactionDateIndexRow).where(orm.TransactionDateIndexRow.bucket_id == _BUCKET)
    if transaction_ids is not None:
        statement = statement.where(orm.TransactionDateIndexRow.transaction_id.in_(sorted(transaction_ids)))
    with session_scope(profile.repository.engine) as session:
        session.execute(statement)


def _index_is_complete(period: Period) -> bool:
    return (
        TransactionCatalogueRepository(bucket_id=_BUCKET)
        .partition_by_date_range(period.start_date, period.end_date)
        .index_complete
    )


# ---------------------------------------------------------------------------
# ledger.preflight: the period partition
# ---------------------------------------------------------------------------


def _preflight(period: Period, operation: PinnedAuthorityOperation) -> _Run:
    def run(observer: _Observer) -> _Outcome:
        return _execute(
            LedgerPreflightExecutor(_action_ports(observer)),
            LEDGER_PREFLIGHT_OPERATION_DEFINITION_ID,
            LedgerPreflightRequest(profile_id=_PROFILE_UUID, period=PublicPeriod.from_period(period)),
            operation,
        )

    return run


def test_preflight_reads_the_period_partition_and_reports_what_a_full_scan_reports(
    seeded: _Seeded,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """Every period, boundary dates and devengo-only candidates included, matches the full-scan report."""
    assert _index_is_complete(_Q4_2030)

    for period in _PERIODS:
        outcome, calls, reference = _paired(_preflight(period, authority_operation))
        assert outcome == reference, f"partitioned preflight differs from the full scan for {period}"
        if period.has_date_span():
            assert calls == Counter(partition_by_date_range=1), f"{period} must read only its partition"
        else:
            assert calls == Counter(load=1), f"{period} has no span and keeps the whole-catalogue read"

    q4 = _preflight(_Q4_2030, authority_operation)(_Observer(widen=False, repositories=[]))
    assert isinstance(q4, LedgerPreflightProjection)
    # Independently stated: the stored Q4 rows that are ACTIVE, the two split
    # children (the SPLIT parent is not), and the edited row. A row devengado
    # in Q4 but filed in 2031 is a partition candidate and must not be counted.
    assert q4.checked_transaction_count == len(_Q4_2030_DIRECT) + len(seeded.split_child_ids) + 1
    issue_ids = {issue.transaction_id for issue in q4.issues}
    assert seeded.direct["q4-mid-office"].transaction_id in issue_ids
    assert seeded.direct["filed-next-year-accrued-q4"].transaction_id not in issue_ids
    assert seeded.direct["q3-last-day"].transaction_id not in issue_ids
    assert seeded.split_parent_id not in issue_ids


@pytest.mark.parametrize(
    "dropped",
    [
        pytest.param(("q4-mid-office",), id="an-in-window-row-lost-its-index-entry"),
        pytest.param(("next-year-first-day", "same-quarter-prior-year"), id="out-of-window-rows-lost-their-entries"),
        pytest.param(None, id="the-whole-index-is-missing"),
    ],
)
def test_preflight_over_a_stale_date_index_falls_back_to_the_full_scan_report(
    seeded: _Seeded,
    authority_operation: PinnedAuthorityOperation,
    dropped: tuple[str, ...] | None,
) -> None:
    """A stale index costs a full scan, never a row: every report matches the complete-index report.

    Losing an in-window row's entry is the dangerous case: a read trusting the
    index would never decrypt that row and the preflight would silently check
    one row fewer.
    """
    complete = [_preflight(period, authority_operation)(_Observer(widen=False, repositories=[])) for period in _PERIODS]

    _drop_index_rows(
        seeded.profile,
        None if dropped is None else frozenset(seeded.direct[name].transaction_id for name in dropped),
    )
    assert not _index_is_complete(_Q4_2030)

    for period, expected in zip(_PERIODS, complete, strict=True):
        outcome, _calls, reference = _paired(_preflight(period, authority_operation))
        assert outcome == expected, f"stale-index preflight differs from the complete-index report for {period}"
        assert outcome == reference


# ---------------------------------------------------------------------------
# ledger.status and ledger.check: one whole-catalogue read
# ---------------------------------------------------------------------------


def _status(period: Period | None, operation: PinnedAuthorityOperation) -> _Run:
    def run(observer: _Observer) -> _Outcome:
        return _execute(
            LedgerStatusExecutor(_action_ports(observer), build_verification_repository_bundle),
            LEDGER_STATUS_OPERATION_DEFINITION_ID,
            LedgerStatusRequest(
                profile_id=_PROFILE_UUID,
                period=PublicPeriod.from_period(period) if period is not None else None,
            ),
            operation,
        )

    return run


def _full_scan_status(period: Period | None, operation: PinnedAuthorityOperation) -> LedgerStatusProjection:
    """The status each helper gave when every one of them read the whole catalogue itself."""
    ports = compose_ledger_action_ports(bucket_id=_BUCKET, operation=operation)
    repositories = build_verification_repository_bundle(_BUCKET, operation=operation)
    report = summarize_manual_transactions(
        bucket_id=_BUCKET, period=period, ports=ports, catalogue=ports.transaction_repository.load()
    )
    readiness = (
        read_ledger_readiness(
            bucket_id=_BUCKET,
            period=period,
            transaction_repository=ports.transaction_repository,
            usage_ratio_profile_loader=ports.usage_ratio_profile_loader,
            operation=operation,
            catalogue=ports.transaction_repository.load(),
        )
        if period is not None
        else ()
    )
    stale = read_stale_ledger_filings(
        bucket_id=_BUCKET,
        revisions=repositories.calculation.load(operation=operation).revisions,
        work_units=repositories.work_unit.load(),
        transactions=ports.transaction_repository.load(),
    )
    return LedgerStatusProjection.from_report(report, readiness_issues=readiness, stale_filings=stale)


def test_status_reads_the_catalogue_once_and_reports_what_separate_full_reads_reported(
    seeded: _Seeded,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """Counts stay global, the period's money and readiness stay scoped, from one snapshot."""
    for period in (*(period for period in _PERIODS if period.has_date_span()), None):
        outcome, calls, reference = _paired(_status(period, authority_operation))
        assert outcome == reference
        assert outcome == _full_scan_status(period, authority_operation), f"status differs for {period}"
        assert calls == Counter(load=1), f"status for {period} must read the whole catalogue exactly once"

    q4 = _status(_Q4_2030, authority_operation)(_Observer(widen=False, repositories=[]))
    assert isinstance(q4, LedgerStatusProjection)
    assert q4.total_count == len(_ROWS) + 1 + len(seeded.split_child_ids) + 1
    assert q4.split_count == 1
    assert q4.checked_transaction_count == len(_Q4_2030_DIRECT) + len(seeded.split_child_ids) + 1
    assert q4.readiness_issue_count == len(q4.readiness_issues)
    assert all(issue.transaction_present for issue in q4.readiness_issues)


def test_status_refuses_a_period_without_a_date_span_before_reading_the_catalogue(
    seeded: _Seeded,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """An instalment clave selects no filing dates, so its money totals are refused, never zero."""
    no_span = Period.from_year_and_code(2030, "1P")
    assert not no_span.has_date_span()
    # Active business rows are what reach the money totals' date check.
    assert any(row.classification is BusinessClassification.BUSINESS for row in _ROWS)

    observer = _Observer(widen=False, repositories=[])
    with pytest.raises(LedgerSummaryPeriodWithoutSpanError) as refused:
        _status(no_span, authority_operation)(observer)
    assert observer.calls() == Counter(), "a refused period must not decrypt the catalogue"
    assert refused.value.context == {"period": "2030 1P"}

    code = get_registered_error_code(refused.value)
    assert code.code == "REFUSED_LEDGER_SUMMARY_PERIOD_WITHOUT_SPAN"
    assert code.category is ErrorCategory.REFUSED
    message = resolve_error_message(refused.value, locale="en")
    assert "no calendar date span" in message
    assert "1P" in message

    # The summary itself refuses the same period, whoever calls it.
    with pytest.raises(LedgerSummaryPeriodWithoutSpanError):
        _full_scan_status(no_span, authority_operation)

    # A dated period in the same year still reports its status and money totals.
    q4 = _status(_Q4_2030, authority_operation)(_Observer(widen=False, repositories=[]))
    assert isinstance(q4, LedgerStatusProjection)
    assert q4.period == PublicPeriod.from_period(_Q4_2030)
    assert q4 == _full_scan_status(_Q4_2030, authority_operation)
    assert Decimal(q4.business_income_total) + Decimal(q4.business_expense_total) > 0
    assert q4.total_count == len(_ROWS) + 1 + len(seeded.split_child_ids) + 1


def _check(period: Period | None, operation: PinnedAuthorityOperation) -> _Run:
    def run(observer: _Observer) -> _Outcome:
        return _execute(
            LedgerCheckExecutor(_action_ports(observer)),
            LEDGER_CHECK_OPERATION_DEFINITION_ID,
            LedgerCheckRequest(
                profile_id=_PROFILE_UUID,
                period=PublicPeriod.from_period(period) if period is not None else None,
            ),
            operation,
        )

    return run


def test_check_reads_the_catalogue_once_and_keeps_links_global_under_a_period(
    seeded: _Seeded,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """The link check sees a one-sided link on a row outside the period; the preflight stays scoped."""
    for period in (_Q4_2030, Period.from_year_and_code(2030, "2T"), None):
        outcome, calls, reference = _paired(_check(period, authority_operation))
        assert outcome == reference
        assert calls == Counter(load=1), f"check for {period} must read the whole catalogue exactly once"
        assert isinstance(outcome, LedgerCheckProjection)
        assert [(link.transaction_id, link.invoice_id) for link in outcome.link_inconsistencies] == [
            (seeded.direct["prior-year-one-sided-link"].transaction_id, "INV-NOT-STORED-0001")
        ]
        assert outcome.ready is False

    q4 = _check(_Q4_2030, authority_operation)(_Observer(widen=False, repositories=[]))
    preflight = _preflight(_Q4_2030, authority_operation)(_Observer(widen=False, repositories=[]))
    assert isinstance(q4, LedgerCheckProjection)
    assert isinstance(preflight, LedgerPreflightProjection)
    assert q4.checked_transaction_count == preflight.checked_transaction_count
    assert [issue.to_issue() for issue in q4.issues] == [issue.to_issue() for issue in preflight.issues]


# ---------------------------------------------------------------------------
# view, track, history, participation: one row by full id
# ---------------------------------------------------------------------------


def _handles(seeded: _Seeded) -> dict[str, tuple[str, str | None]]:
    """Every handle shape an operator can type, with the live id each must resolve to (``None``: refused)."""
    live_ids = sorted(
        {
            *(row.transaction_id for row in seeded.direct.values()),
            seeded.split_parent_id,
            *seeded.split_child_ids,
            seeded.edited_id,
        }
    )
    known = [*live_ids, seeded.superseded_id]
    first_characters = Counter(transaction_id[0] for transaction_id in live_ids)
    ambiguous = next(character for character, count in first_characters.items() if count > 1)
    unknown_prefix = next(
        candidate
        for candidate in (f"{value:06x}" for value in range(0x1000000))
        if not any(transaction_id.startswith(candidate) for transaction_id in known)
    )
    unknown_full = next(candidate for candidate in (f"{value:064x}" for value in range(16)) if candidate not in known)
    office = seeded.direct["q4-mid-office"].transaction_id
    assert sum(transaction_id.startswith(office[:12]) for transaction_id in known) == 1
    assert sum(transaction_id.startswith(seeded.superseded_id[:12]) for transaction_id in known) == 1
    return {
        "full-live-id": (office, office),
        "full-split-child-id": (seeded.split_child_ids[0], seeded.split_child_ids[0]),
        "full-split-parent-id": (seeded.split_parent_id, seeded.split_parent_id),
        "full-edited-id": (seeded.edited_id, seeded.edited_id),
        "short-live-prefix": (office[:12], office),
        "full-superseded-id": (seeded.superseded_id, seeded.edited_id),
        "short-superseded-prefix": (seeded.superseded_id[:12], seeded.edited_id),
        "unknown-full-id": (unknown_full, None),
        "unknown-short-prefix": (unknown_prefix, None),
        "ambiguous-prefix": (ambiguous, None),
    }


def _view(handle: str, operation: PinnedAuthorityOperation) -> _Run:
    def run(observer: _Observer) -> _Outcome:
        return _execute(
            LedgerViewExecutor(_action_ports(observer)),
            LEDGER_VIEW_OPERATION_DEFINITION_ID,
            LedgerViewRequest(profile_id=_PROFILE_UUID, transaction_prefix=handle),
            operation,
        )

    return run


def _track(handle: str, operation: PinnedAuthorityOperation) -> _Run:
    def run(observer: _Observer) -> _Outcome:
        return _execute(
            LedgerTrackExecutor(_action_ports(observer), TransactionParticipationIndexRepository),
            LEDGER_TRACK_OPERATION_DEFINITION_ID,
            LedgerTrackRequest(profile_id=_PROFILE_UUID, transaction_prefix=handle),
            operation,
        )

    return run


def _participation(handle: str, operation: PinnedAuthorityOperation) -> _Run:
    def run(observer: _Observer) -> _Outcome:
        return _execute(
            LedgerParticipationExecutor(_action_ports(observer), TransactionParticipationIndexRepository),
            LEDGER_PARTICIPATION_OPERATION_DEFINITION_ID,
            LedgerParticipationRequest(profile_id=_PROFILE_UUID, transaction_prefix=handle),
            operation,
        )

    return run


def _history(handle: str, operation: PinnedAuthorityOperation, *, include_split_siblings: bool) -> _Run:
    def run(observer: _Observer) -> _Outcome:
        return _execute(
            LedgerHistoryExecutor(_read_ports(observer)),
            LEDGER_HISTORY_OPERATION_DEFINITION_ID,
            LedgerHistoryRequest(
                profile_id=_PROFILE_UUID,
                transaction_prefix=handle,
                include_split_siblings=include_split_siblings,
            ),
            operation,
        )

    return run


def _resolved_id(outcome: _Outcome) -> str | None:
    if isinstance(outcome, tuple):
        return None
    if isinstance(outcome, LedgerViewProjection):
        return outcome.transaction.transaction_id
    if isinstance(outcome, LedgerHistoryProjection):
        return outcome.transaction_id
    value = getattr(outcome, "transaction_id", None)
    if value is None:
        transaction = getattr(outcome, "transaction", None)
        value = getattr(transaction, "transaction_id", None)
    assert isinstance(value, str)
    return value


def test_id_addressed_reads_resolve_every_handle_as_a_full_scan_does(
    seeded: _Seeded,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """Full ids read one row; prefixes, superseded ids and unknown handles keep the whole-catalogue resolution."""
    for name, (handle, expected) in _handles(seeded).items():
        reads: dict[str, _Run] = {
            "view": _view(handle, authority_operation),
            "track": _track(handle, authority_operation),
            "participation": _participation(handle, authority_operation),
            "history": _history(handle, authority_operation, include_split_siblings=False),
            "history-with-siblings": _history(handle, authority_operation, include_split_siblings=True),
        }
        for read, run in reads.items():
            outcome, calls, reference = _paired(run)
            assert outcome == reference, f"{read} differs from the full scan for the {name} handle"
            assert _resolved_id(outcome) == expected, f"{read} resolved the {name} handle wrongly"
            if expected is not None and len(handle) == len(expected) and handle == expected:
                assert calls == Counter(load_by_ids=1), f"{read} must read only the addressed row for {name}"
            elif len(handle) == len(seeded.edited_id):
                assert calls == Counter(load_by_ids=1, load=1), f"{read} must fall back to the catalogue for {name}"
            else:
                assert calls == Counter(load=1), f"{read} must resolve a prefix against the catalogue for {name}"


def test_id_addressed_refusals_are_unchanged(seeded: _Seeded, authority_operation: PinnedAuthorityOperation) -> None:
    """An unknown full id, an unknown prefix and an ambiguous prefix keep their exact refusal keys."""
    handles = _handles(seeded)
    expected_keys = {
        "unknown-full-id": "application.ledger.errors.transaction_id_prefix_no_match",
        "unknown-short-prefix": "application.ledger.errors.transaction_id_prefix_no_match",
        "ambiguous-prefix": "application.ledger.errors.transaction_id_prefix_ambiguous",
    }
    for name, key in expected_keys.items():
        handle, _expected = handles[name]
        outcome = _view(handle, authority_operation)(_Observer(widen=False, repositories=[]))
        assert isinstance(outcome, tuple)
        assert outcome[0] == TransactionIdPrefixError.__name__
        assert outcome[1] == key, f"{name} refused with {outcome[1]}"


def test_history_of_a_split_child_read_by_full_id_still_reaches_its_siblings(
    seeded: _Seeded,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """The sibling ids live on the child row itself, so reading that row alone keeps the split story."""
    child = seeded.split_child_ids[0]
    with_siblings = _history(child, authority_operation, include_split_siblings=True)(
        _Observer(widen=False, repositories=[])
    )
    without = _history(child, authority_operation, include_split_siblings=False)(
        _Observer(widen=False, repositories=[])
    )
    assert isinstance(with_siblings, LedgerHistoryProjection)
    assert isinstance(without, LedgerHistoryProjection)
    assert set(with_siblings.object_ids) == {seeded.split_parent_id, *seeded.split_child_ids}
    assert without.object_ids == (child,)
    assert len(with_siblings.events) > len(without.events)

    edited = _history(seeded.edited_id, authority_operation, include_split_siblings=False)(
        _Observer(widen=False, repositories=[])
    )
    assert isinstance(edited, LedgerHistoryProjection)
    assert edited.object_ids == (seeded.edited_id, seeded.superseded_id)
