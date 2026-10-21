"""Focused exact-profile and bounded-staging tests for ledger import."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Callable
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
from ...operations.execution_actor import OperationExecutionCaller
from ...operations.models import OperationIdentity, OperationRequest
from ...operations.registry import OperationFrontendProjection
from ...user_profile.access_contracts import SessionKind
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
# The ports are doubles keyed on file name; the request still names each file as the runtime requires.
_SOURCES = Path(__file__).resolve().parent / "statements"


@pytest.mark.parametrize(
    ("statement", "verify_source"),
    [(Path("one.csv"), None), (_SOURCES / "one.csv", Path("ledger.csv"))],
)
def test_import_request_refuses_a_path_the_runtime_would_place_itself(
    statement: Path, verify_source: Path | None
) -> None:
    with pytest.raises(ValueError, match="ledger import paths must be absolute"):
        LedgerImportRequest(
            profile_id=_PROFILE, files=(statement,), provider=LedgerProviderID.CSV, verify_source=verify_source
        )


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
    async def irreversible_section(self) -> AsyncGenerator[None]:
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


def _parsed_rows(count: int, digest: str) -> tuple[SimpleNamespace, ...]:
    """Parsed rows carrying the digest of the bytes they were read from, as provider rows do."""
    return (SimpleNamespace(raw=SimpleNamespace(provenance=SimpleNamespace(source_sha256=digest))),) * count


def test_import_request_rejects_more_than_the_registered_file_limit() -> None:
    with pytest.raises(ValidationError):
        LedgerImportRequest(
            profile_id=_PROFILE,
            files=tuple(_SOURCES / f"{index}.csv" for index in range(MAX_LEDGER_IMPORT_FILES + 1)),
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
        return SimpleNamespace(
            command=command, source=SimpleNamespace(parsed_rows=_parsed_rows(counts[name], "a" * 64))
        )

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
            files=tuple(_SOURCES / name for name in counts),
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


def test_a_file_whose_parsed_bytes_differ_from_the_preview_digest_is_refused_before_persist(
    monkeypatch: pytest.MonkeyPatch, operation: PinnedAuthorityOperation
) -> None:
    """Apply imports only the bytes a preview reported; a changed file is refused, never written."""
    from .. import import_operation as operation_module

    digests = {"kept.csv": "b" * 64, "changed.csv": "c" * 64}
    persisted_paths: list[str] = []
    stored: list[LedgerImportExecutionResult] = []
    repository = ProfileOnlyCatalogueRepository[TransactionCatalogue](str(_PROFILE))

    def prepare(command, *, ports, own_accounts):
        del ports, own_accounts
        return SimpleNamespace(
            command=command,
            source=SimpleNamespace(parsed_rows=_parsed_rows(2, digests[command.path.name])),
        )

    def persist(staged, *, transaction_repository, bucket_event_repository, currency_normalizer):
        del transaction_repository, bucket_event_repository, currency_normalizer
        persisted_paths.append(staged.command.path.name)
        return _source_result(bucket_id=str(_PROFILE), rows=2)

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
        events=_Events(),
        operands=_Operands(),
        cancellation=_Cancellation(),
    )
    request = OperationRequest(
        definition_id=LEDGER_IMPORT_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(_PROFILE)),
        payload=LedgerImportRequest(
            profile_id=_PROFILE,
            files=(_SOURCES / "kept.csv", _SOURCES / "changed.csv"),
            provider=LedgerProviderID.CSV,
            # The preview saw "changed.csv" with other bytes than it holds now.
            expected_source_sha256=("b" * 64, "d" * 64),
        ),
    )

    asyncio.run(LedgerImportExecutor(_PortsFactory(operation, repository)).execute(request, context))

    assert persisted_paths == ["kept.csv"]
    execution = stored[0]
    assert [(item.file_name, item.file_index, item.source_sha256) for item in execution.files] == [
        ("kept.csv", 0, "b" * 64),
    ]
    assert [(item.file_name, item.reason_code) for item in execution.refused_files] == [
        ("changed.csv", "source_changed"),
    ]


def test_import_request_requires_one_expected_digest_per_file() -> None:
    with pytest.raises(ValidationError):
        LedgerImportRequest(
            profile_id=_PROFILE,
            files=(_SOURCES / "one.csv", _SOURCES / "two.csv"),
            provider=LedgerProviderID.CSV,
            expected_source_sha256=("a" * 64,),
        )


_SESSION_CLIENT = UUID("5aa00000-0000-4000-8000-0000000000dd")


@pytest.mark.parametrize(
    ("frontend", "recorded"),
    [
        (OperationFrontendProjection.EXTERNAL_CLIENT, f"automation:external-client.attended.{_SESSION_CLIENT}"),
        (OperationFrontendProjection.CLI, str(_PROFILE)),
        (OperationFrontendProjection.TUI, str(_PROFILE)),
        (None, str(_PROFILE)),
    ],
    ids=["external_client", "cli", "tui", "no-session-host"],
)
def test_each_source_is_staged_under_the_session_label_for_automation_and_the_profile_otherwise(
    monkeypatch: pytest.MonkeyPatch,
    operation: PinnedAuthorityOperation,
    frontend: OperationFrontendProjection | None,
    recorded: str,
) -> None:
    """The import request carries no label, so the staged command names the session or the profile."""
    from .. import import_operation as operation_module

    actors: list[str] = []
    repository = ProfileOnlyCatalogueRepository[TransactionCatalogue](str(_PROFILE))

    def prepare(command, *, ports, own_accounts):
        del ports, own_accounts
        actors.append(command.actor)
        return SimpleNamespace(command=command, source=SimpleNamespace(parsed_rows=_parsed_rows(1, "a" * 64)))

    def persist(staged, *, transaction_repository, bucket_event_repository, currency_normalizer):
        del staged, transaction_repository, bucket_event_repository, currency_normalizer
        return _source_result(bucket_id=str(_PROFILE), rows=1)

    def session_host(identity: OperationIdentity) -> OperationExecutionCaller:
        assert frontend is not None and identity.definition_id == LEDGER_IMPORT_OPERATION_DEFINITION_ID
        return OperationExecutionCaller(frontend=frontend, session_kind=SessionKind.ATTENDED, client_id=_SESSION_CLIENT)

    class _Operands:
        async def put(self, result: LedgerImportExecutionResult, *, written_at):
            del result, written_at
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
        events=_Events(),
        operands=_Operands(),
        cancellation=_Cancellation(),
    )
    request = OperationRequest(
        definition_id=LEDGER_IMPORT_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(_PROFILE)),
        payload=LedgerImportRequest(
            profile_id=_PROFILE, files=(_SOURCES / "first.csv", _SOURCES / "second.csv"), provider=LedgerProviderID.CSV
        ),
    )
    executor = LedgerImportExecutor(
        _PortsFactory(operation, repository), execution_caller_reader=None if frontend is None else session_host
    )

    assert asyncio.run(executor.execute(request, context)) == "secure-result-reference"

    assert actors == [recorded, recorded]
