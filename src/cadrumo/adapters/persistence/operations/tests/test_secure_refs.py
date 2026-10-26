"""Real encrypted-storage proofs for operation secure references."""

from __future__ import annotations

import asyncio
import threading
from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager, suppress
from contextvars import ContextVar
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import BaseModel, Field, ValidationError, model_validator

from cadrumo.adapters.persistence.storage.tests.namespace_registry_support import lookup_namespace_definition

from .....core.classification.policies import SensitivityClass
from .....core.hashing import sha256_hex
from ...storage.errors import RepositoryError
from ...storage.namespace_registry import STORAGE_NAMESPACE_REGISTRY
from ...storage.namespace_taxonomy import StorageCustodyDisposition, StorageNamespaceScope
from ...storage.secure_object_namespaces import OPERATION_SECURE_REFERENCE_NAMESPACE
from ...storage.sql.secure_objects import SecureObjectRepository
from ...storage.tests.secure_sql import isolated_runtime_profile, read_db_at_rest_bytes
from ..secure_references import OperationSecureReferenceRepository, operation_secure_reference_repository

pytestmark = [pytest.mark.integration, pytest.mark.hex_persistence_adapter]

_WRITTEN_AT = datetime(2026, 8, 14, 14, tzinfo=UTC)


class _Operand(BaseModel):
    subject: str = Field(min_length=1)
    amount: int = Field(ge=0)


class _OtherOperand(BaseModel):
    label: str = Field(min_length=1)


def test_secure_reference_round_trip_is_content_addressed_and_encrypted(tmp_path: Path) -> None:
    """Typed operands deduplicate by exact JSON bytes and never reach disk plaintext."""
    operand = _Operand(subject="taxpayer-private", amount=73)
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        store = operation_secure_reference_repository(objects=profile.repository)
        reference = asyncio.run(store.put(operand, written_at=_WRITTEN_AT))
        repeated = asyncio.run(store.put(operand, written_at=_WRITTEN_AT))

        assert reference == repeated == sha256_hex(operand.model_dump_json().encode("utf-8"))
        assert asyncio.run(store.resolve(reference, _Operand)) == operand
        encrypted_database = read_db_at_rest_bytes(profile.paths.database_file)
        assert operand.subject.encode("utf-8") not in encrypted_database
        assert b'"amount":73' not in encrypted_database


def test_secure_reference_refuses_absent_wrong_type_and_digest_corruption(tmp_path: Path) -> None:
    """An addressed object must exist, match its bytes, and hydrate the requested type."""
    operand = _Operand(subject="integrity-subject", amount=12)
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        objects = profile.repository
        store = operation_secure_reference_repository(objects=objects)
        with pytest.raises(RepositoryError, match="absent"):
            asyncio.run(store.resolve("a" * 64, _Operand))

        reference = asyncio.run(store.put(operand, written_at=_WRITTEN_AT))
        with pytest.raises(RepositoryError, match="requested operand type") as wrong_type:
            asyncio.run(store.resolve(reference, _OtherOperand))
        assert isinstance(wrong_type.value.__cause__, ValidationError)

        objects.save(
            namespace=OPERATION_SECURE_REFERENCE_NAMESPACE.namespace,
            object_key=reference,
            classification=OPERATION_SECURE_REFERENCE_NAMESPACE.sensitivity,
            schema_version=OPERATION_SECURE_REFERENCE_NAMESPACE.schema_version,
            written_at=_WRITTEN_AT,
            payload=_Operand(subject="substituted", amount=99).model_dump_json().encode("utf-8"),
        )
        with pytest.raises(RepositoryError, match="digest mismatch"):
            asyncio.run(store.resolve(reference, _Operand))


def test_secure_reference_constructor_refuses_plaintext_or_non_digest_namespace(tmp_path: Path) -> None:
    """The adapter accepts only a ciphertext-required content-addressed namespace."""
    plaintext_namespace = OPERATION_SECURE_REFERENCE_NAMESPACE.model_copy(
        update={"sensitivity": SensitivityClass.OPERATIONAL}
    )
    wrong_key_namespace = OPERATION_SECURE_REFERENCE_NAMESPACE.model_copy(
        update={"object_key_grammar": "operand:{content_digest}"}
    )
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        with pytest.raises(ValueError, match="unsuitable sensitivity"):
            OperationSecureReferenceRepository(objects=profile.repository, namespace=plaintext_namespace)
        with pytest.raises(ValueError, match="keyed by"):
            OperationSecureReferenceRepository(objects=profile.repository, namespace=wrong_key_namespace)


def test_canonical_namespace_is_registered_once_in_its_defining_module() -> None:
    """The global operation-reference home is unique and definition-owned."""
    namespace = OPERATION_SECURE_REFERENCE_NAMESPACE

    assert lookup_namespace_definition(namespace.key) is namespace
    assert STORAGE_NAMESPACE_REGISTRY.namespace_by_value(namespace.namespace) is namespace
    assert namespace.owner == "cadrumo.adapters.persistence.operations"
    assert namespace.object_key_grammar == "{content_digest}"
    assert namespace.scope is StorageNamespaceScope.BUCKET_LOCAL
    assert namespace.custody_disposition is StorageCustodyDisposition.PROCESS_LOCAL


def test_secure_reference_storage_runs_off_the_awaiting_event_loop(tmp_path: Path) -> None:
    """Encrypted operand reads and writes happen on a worker, never on the caller's loop."""
    operand = _Operand(subject="off-loop-subject", amount=5)
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        storage_threads: list[int] = []

        def objects() -> SecureObjectRepository:
            # The store resolves its repository exactly where it is about to use it.
            storage_threads.append(threading.get_ident())
            return profile.repository

        store = OperationSecureReferenceRepository(
            objects_factory=objects,
            namespace=OPERATION_SECURE_REFERENCE_NAMESPACE,
        )

        async def round_trip() -> tuple[int, _Operand]:
            reference = await store.put(operand, written_at=_WRITTEN_AT)
            return threading.get_ident(), await store.resolve(reference, _Operand)

        loop_thread, resolved = asyncio.run(round_trip())

    assert resolved == operand
    assert len(storage_threads) == 2
    assert loop_thread not in storage_threads


_HYDRATION_HOOK: ContextVar[Callable[[object], object] | None] = ContextVar("secure_reference_hydration", default=None)
_HYDRATION_IDENTITY: ContextVar[str] = ContextVar("secure_reference_identity", default="")


class _HeldOperand(_Operand):
    """Exercise the real strict parser while its model validator owns a blocking read body."""

    @model_validator(mode="before")
    @classmethod
    def _hold_hydration(cls, value: object) -> object:
        hook = _HYDRATION_HOOK.get()
        return value if hook is None else hook(value)


async def _await_hydration_entry[T](pending: asyncio.Task[T], entered: asyncio.Event) -> None:
    """Detect a synchronous-parser regression without blocking the event loop or imposing a timer."""
    waiting = asyncio.create_task(entered.wait())
    try:
        await asyncio.wait((pending, waiting), return_when=asyncio.FIRST_COMPLETED)
        if not entered.is_set():
            pending.result()
            pytest.fail("the strict parser did not enter its held validation body")
    finally:
        waiting.cancel()
        with suppress(asyncio.CancelledError):
            await waiting


def test_strict_hydration_yields_to_control_and_copies_context(tmp_path: Path) -> None:
    """A live encrypted read retains its context while an independent loop task progresses."""
    operand = _HeldOperand(subject="held-hydration", amount=4)
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        store = operation_secure_reference_repository(objects=profile.repository)
        reference = asyncio.run(store.put(operand, written_at=_WRITTEN_AT))

        async def read() -> None:
            loop = asyncio.get_running_loop()
            loop_thread = threading.get_ident()
            entered, progressed = asyncio.Event(), asyncio.Event()
            resume = threading.Event()

            def hold(value: object) -> object:
                assert threading.get_ident() != loop_thread
                assert _HYDRATION_IDENTITY.get() == "original-read-context"
                loop.call_soon_threadsafe(entered.set)
                resume.wait()
                return value

            async def control() -> None:
                assert entered.is_set() and not resume.is_set()
                progressed.set()

            identity = _HYDRATION_IDENTITY.set("original-read-context")
            hook = _HYDRATION_HOOK.set(hold)
            pending = asyncio.create_task(store.resolve(reference, _HeldOperand))
            try:
                await _await_hydration_entry(pending, entered)
                await asyncio.create_task(control())
                assert progressed.is_set() and not pending.done()
                resume.set()
                assert await pending == operand
            finally:
                resume.set()
                _HYDRATION_HOOK.reset(hook)
                _HYDRATION_IDENTITY.reset(identity)
                if not pending.done():
                    await pending

        asyncio.run(read())


@pytest.mark.parametrize("refuse", [False, True])
def test_cancelled_hydration_settles_before_the_callers_guard_releases(tmp_path: Path, refuse: bool) -> None:
    """Repeated cancellation cannot release a caller's authority while strict hydration still runs."""
    operand = _HeldOperand(subject="cancelled-hydration", amount=6)
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        store = operation_secure_reference_repository(objects=profile.repository)
        reference = asyncio.run(store.put(operand, written_at=_WRITTEN_AT))

        async def read() -> None:
            loop = asyncio.get_running_loop()
            loop_thread = threading.get_ident()
            entered = asyncio.Event()
            resume = threading.Event()
            events: list[str] = []

            def hold(value: object) -> object:
                assert threading.get_ident() != loop_thread
                loop.call_soon_threadsafe(entered.set)
                resume.wait()
                events.append("hydration-settled")
                if refuse:
                    raise ValueError("synthetic strict hydration refusal")
                return value

            @asynccontextmanager
            async def caller_guard() -> AsyncGenerator[None]:
                events.append("authority-held")
                try:
                    yield
                finally:
                    events.append("authority-released")

            async def guarded_read() -> _HeldOperand:
                async with caller_guard():
                    return await store.resolve(reference, _HeldOperand)

            hook = _HYDRATION_HOOK.set(hold)
            pending = asyncio.create_task(guarded_read())
            try:
                await _await_hydration_entry(pending, entered)
                pending.cancel()
                await asyncio.sleep(0)
                pending.cancel()
                await asyncio.sleep(0)
                assert not pending.done()
                assert events == ["authority-held"]
                resume.set()
                with pytest.raises(asyncio.CancelledError) as cancelled:
                    await pending
                assert events == ["authority-held", "hydration-settled", "authority-released"]
                error = cancelled.value.__dict__.get("cleanup_error")
                if refuse:
                    assert isinstance(error, RepositoryError)
                    assert isinstance(error.__cause__, ValidationError)
                    assert "requested operand type" in str(error)
                else:
                    assert error is None
            finally:
                resume.set()
                _HYDRATION_HOOK.reset(hook)
                if not pending.done():
                    with suppress(asyncio.CancelledError):
                        await pending

        asyncio.run(read())


def test_every_hydration_reads_and_verifies_current_encrypted_bytes(tmp_path: Path) -> None:
    """Success never caches a plaintext operand or masks later addressed-byte corruption."""
    operand = _Operand(subject="fresh-hydration", amount=8)
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        reads: list[int] = []

        def objects() -> SecureObjectRepository:
            reads.append(threading.get_ident())
            return profile.repository

        store = OperationSecureReferenceRepository(
            objects_factory=objects, namespace=OPERATION_SECURE_REFERENCE_NAMESPACE
        )
        reference = asyncio.run(store.put(operand, written_at=_WRITTEN_AT))
        for _ in range(2):
            assert asyncio.run(store.resolve(reference, _Operand)) == operand
        profile.repository.save(
            namespace=OPERATION_SECURE_REFERENCE_NAMESPACE.namespace,
            object_key=reference,
            classification=OPERATION_SECURE_REFERENCE_NAMESPACE.sensitivity,
            schema_version=OPERATION_SECURE_REFERENCE_NAMESPACE.schema_version,
            written_at=_WRITTEN_AT,
            payload=b'{"subject":"substituted","amount":9}',
        )
        with pytest.raises(RepositoryError, match="digest mismatch"):
            asyncio.run(store.resolve(reference, _Operand))
        assert len(reads) == 4
