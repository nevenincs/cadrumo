"""Focused exact-profile and bounded-staging tests for ledger import."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import pytest
from pydantic import ValidationError

from ....core.operations import OperationEffect, profile_operation_subject
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.currency.service import CurrencyNormalizationService
from ....domain.transactions.models import TransactionCatalogue
from ....domain.transactions.own_accounts import OwnAccountRegister
from ...operations.models import OperationRequest
from ..actions_import import LedgerProviderID
from ..import_operation import (
    LEDGER_IMPORT_OPERATION_DEFINITION_ID,
    MAX_LEDGER_IMPORT_FILES,
    MAX_LEDGER_IMPORT_ROWS,
    LedgerImportExecutionResult,
    LedgerImportExecutor,
    LedgerImportOperationPorts,
    LedgerImportRequest,
)
from ..import_ports import LedgerImportPorts
from ..models import (
    LedgerSourceImportResult,
    LedgerSourceValidationReport,
    LedgerSourceVerificationReport,
)
from .unused_repository_ports import ProfileOnlyCatalogueRepository, UnusedBucketEventRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")


class _Events:
    def __init__(self) -> None:
        self.phases: list[str] = []
        self.effects: list[OperationEffect] = []

    async def phase(self, phase: str) -> None:
        self.phases.append(phase)

    async def effect(self, effect: OperationEffect) -> None:
        self.effects.append(effect)


class _Cancellation:
    def __init__(self) -> None:
        self.active = False
        self.entries = 0

    @asynccontextmanager
    async def irreversible_section(self) -> AsyncIterator[None]:
        self.entries += 1
        self.active = True
        try:
            yield
        finally:
            self.active = False


class _Resolver:
    def resolve(self, *, provider_id: str, path: Path) -> None:
        raise AssertionError(f"prepare was replaced for {provider_id}:{path}")


class _Location:
    def path_for(self, *, bucket_id: str) -> str:
        return f"fake://{bucket_id}"


class _NoOwnAccounts:
    """A profile that has registered no own bank account."""

    def load(self) -> OwnAccountRegister:
        return OwnAccountRegister()

    def mutate(self, change: Callable[[OwnAccountRegister], OwnAccountRegister]) -> OwnAccountRegister:
        raise AssertionError("ledger import never writes the own-account register")


class _PortsFactory:
    def __init__(
        self,
        operation: PinnedAuthorityOperation,
        transaction_repository: ProfileOnlyCatalogueRepository[TransactionCatalogue],
    ) -> None:
        self.operation = operation
        self.transaction_repository = transaction_repository

    def __call__(self, *, bucket_id: str, operation: PinnedAuthorityOperation) -> LedgerImportOperationPorts:
        assert bucket_id == str(_PROFILE)
        assert operation is self.operation
        return LedgerImportOperationPorts(
            import_ports=LedgerImportPorts(provider_resolver=_Resolver(), catalogue_location=_Location()),
            transaction_repository=self.transaction_repository,
            bucket_event_repository=UnusedBucketEventRepository(),
            currency_normalizer=CurrencyNormalizationService(),
            operation=operation,
            own_accounts=_NoOwnAccounts(),
        )


def _source_result(*, bucket_id: str, rows: int) -> LedgerSourceImportResult:
    return LedgerSourceImportResult(
        rows=rows,
        imported=rows,
        skipped=0,
        likely_duplicates=0,
        dry_run=False,
        verify=False,
        bucket_id=bucket_id,
        validations=(LedgerSourceValidationReport(valid=True),),
        sources=(LedgerSourceVerificationReport(requested=False),),
    )


def test_import_request_rejects_more_than_the_registered_file_limit() -> None:
    with pytest.raises(ValidationError):
        LedgerImportRequest(
            profile_id=_PROFILE,
            files=tuple(Path(f"{index}.csv") for index in range(MAX_LEDGER_IMPORT_FILES + 1)),
            provider=LedgerProviderID.CSV,
        )


def test_over_budget_file_is_refused_before_persist_and_later_small_file_fits(
    monkeypatch: pytest.MonkeyPatch, operation: PinnedAuthorityOperation
) -> None:
    """Row limits are applied during staging, before any source reaches persistence."""
    from .. import import_operation as operation_module

    counts = {"first.csv": MAX_LEDGER_IMPORT_ROWS - 1, "over.csv": 2, "later.csv": 1}
    prepared_paths: list[str] = []
    persisted_paths: list[str] = []
    cancellation = _Cancellation()
    events = _Events()
    stored: list[LedgerImportExecutionResult] = []
    repository = ProfileOnlyCatalogueRepository[TransactionCatalogue](str(_PROFILE))

    def prepare(command, *, ports, own_accounts):
        del ports, own_accounts
        assert not cancellation.active
        name = command.path.name
        prepared_paths.append(name)
        return SimpleNamespace(command=command, source=SimpleNamespace(parsed_rows=(None,) * counts[name]))

    def persist(staged, *, transaction_repository, bucket_event_repository, currency_normalizer):
        del bucket_event_repository, currency_normalizer
        assert cancellation.active
        assert transaction_repository is repository
        name = staged.command.path.name
        persisted_paths.append(name)
        return _source_result(bucket_id=str(_PROFILE), rows=counts[name])

    class _Operands:
        async def put(self, result: LedgerImportExecutionResult, *, written_at):
            del written_at
            stored.append(result)
            return "secure-result-reference"

    monkeypatch.setattr("cadrumo.application.operations.profile_guard.require_active_bucket_id", lambda: str(_PROFILE))
    monkeypatch.setattr(operation_module, "prepare_ledger_source_import", prepare)
    monkeypatch.setattr(operation_module, "persist_prepared_ledger_source_import", persist)
    context = SimpleNamespace(
        identity=SimpleNamespace(
            definition_id=LEDGER_IMPORT_OPERATION_DEFINITION_ID,
            subject_ref=profile_operation_subject(str(_PROFILE)),
        ),
        authority_operation=operation,
        events=events,
        operands=_Operands(),
        cancellation=cancellation,
    )
    request = OperationRequest(
        definition_id=LEDGER_IMPORT_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(_PROFILE)),
        payload=LedgerImportRequest(
            profile_id=_PROFILE,
            files=tuple(Path(name) for name in counts),
            provider=LedgerProviderID.CSV,
        ),
    )

    reference = asyncio.run(LedgerImportExecutor(_PortsFactory(operation, repository)).execute(request, context))

    assert reference == "secure-result-reference"
    assert prepared_paths == ["first.csv", "over.csv", "later.csv"]
    assert persisted_paths == ["first.csv", "later.csv"]
    assert cancellation.entries == 1
    assert not cancellation.active
    assert events.phases == [LEDGER_IMPORT_OPERATION_DEFINITION_ID]
    assert events.effects == [OperationEffect.UNKNOWN, OperationEffect.UPDATED]
    execution = stored[0]
    assert [item.file_name for item in execution.files] == ["first.csv", "later.csv"]
    assert [(item.file_name, item.reason_code) for item in execution.refused_files] == [
        ("over.csv", "result_limit"),
    ]
