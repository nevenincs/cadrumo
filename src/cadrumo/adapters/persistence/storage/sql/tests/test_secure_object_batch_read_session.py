"""The secure-object batch read checks its session per call, and still stops a mid-call lapse.

``load_many_current`` resolves the active session's keys once for the call,
decodes every row under them, and proves the session again before it releases
the first record. These tests pin the refusal half of that contract on real
SQLite, a real ``BucketSession`` and real AEAD:

- a session that expires, is sealed, or is replaced AFTER the read began --
  after its rows were selected, before they were decoded -- refuses the whole
  call with the session refusal, and no record is yielded;
- every integrity and binding refusal still fires through the batch path;
- over varied seeds the batch read returns exactly what the single-row read
  returns for every requested key.

The mid-call lapse is driven from SQLAlchemy's ``after_cursor_execute`` event
on the batch SELECT, so it lands at a real point inside the call. Time moves
through the canonical clock seam; nothing on the read path is replaced.
"""

from __future__ import annotations

import hashlib
import sqlite3
from collections.abc import Callable, Generator, Iterator
from contextlib import ExitStack, contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import Engine, event

from ......core.classification.policies import SensitivityClass
from ......core.time.clock import frozen_clock
from ...crypto.encrypted_columns import SecureObjectCallKeys, secure_object_key_digest
from ...errors import SecureObjectUnreadableError, SessionExpiredError, StorageValidationError
from ...master_key.active_session import activate_session
from ...master_key.bucket_session import BucketSession
from ...runtime_readiness import StorageRuntimeReadinessCode
from ...tests.engine_bootstrap import bootstrap_sqlite_engine
from ...tests.ephemeral_bucket_session import EphemeralBucketSession
from ..secure_object_records import SecureObjectRecord
from ..secure_objects import SecureObjectRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_NAMESPACE = "cadrumo.batch.session"
_OTHER_NAMESPACE = "cadrumo.batch.session.other"
_T0 = datetime(2026, 10, 1, 9, 0, 0, tzinfo=UTC)
#: Past the ephemeral session's 60-minute idle and absolute deadlines.
_AFTER_DEADLINE = _T0 + timedelta(minutes=61)
_KEYS = ("row-alpha", "row-beta", "row-gamma", "row-delta")


class _LegacyRefusedError(Exception):
    """Raised by the test's legacy refusal so its invocation is observable."""


def _refuse_legacy(keys: tuple[str, ...]) -> None:
    raise _LegacyRefusedError(keys)


def _seed(repo: SecureObjectRepository, keys: tuple[str, ...] = _KEYS, namespace: str = _NAMESPACE) -> None:
    for index, key in enumerate(keys):
        repo.save(
            namespace=namespace,
            object_key=key,
            classification=SensitivityClass.FINANCIAL,
            schema_version=1,
            written_at=_T0 - timedelta(days=index + 1),
            payload=f"payload-{key}".encode(),
        )


def _batch(repo: SecureObjectRepository, keys: tuple[str, ...] = _KEYS) -> Iterator[SecureObjectRecord]:
    return repo.load_many_current(
        _NAMESPACE,
        keys,
        expected_class=SensitivityClass.FINANCIAL,
        current_version=1,
        refuse_legacy=_refuse_legacy,
    )


@contextmanager
def _after_batch_select(engine: Engine, action: Callable[[], object]) -> Generator[list[str]]:
    """Run ``action`` once, right after the batch SELECT executes and before any row is decoded.

    Yields the list of statements the action ran after, so a test can prove
    the hook actually fired inside the call it targets.
    """
    fired: list[str] = []

    def after_cursor_execute(*args: object) -> None:
        statement = str(args[2])
        if "object_key IN" in statement and "FROM secure_objects" in statement and not fired:
            fired.append(statement)
            action()

    event.listen(engine, "after_cursor_execute", after_cursor_execute)
    try:
        yield fired
    finally:
        event.remove(engine, "after_cursor_execute", after_cursor_execute)


@contextmanager
def _seeded_session_repo(
    tmp_path: Path,
    *,
    runtime_bound: bool = False,
) -> Generator[tuple[Engine, SecureObjectRepository, BucketSession, ExitStack]]:
    """Yield a seeded repository under a fresh session opened at the frozen ``_T0``.

    The returned :class:`ExitStack` lets a mid-call action enter a scope (a
    later clock, a replacement session) that unwinds before the session does.
    ``runtime_bound`` builds the repository the runtime builds: bound to the
    session's bucket and refusing to run without a session.
    """
    db_path = tmp_path / "batch-session.db"
    with frozen_clock(_T0), EphemeralBucketSession() as session, ExitStack() as stack:
        engine = bootstrap_sqlite_engine(db_path)
        try:
            repo = SecureObjectRepository(
                engine=engine,
                active_session_bucket_id=session.bucket_id if runtime_bound else None,
                require_secure_active_session=runtime_bound,
            )
            _seed(repo)
            yield engine, repo, session, stack
        finally:
            engine.dispose()


def _fresh_session(*, bucket_id: str, dek: bytes) -> BucketSession:
    return BucketSession.open_resumed(
        bucket_id=bucket_id,
        dek=dek,
        idle_minutes=60,
        opened_at=_T0,
        idle_deadline=_T0 + timedelta(minutes=60),
        absolute_deadline=_T0 + timedelta(minutes=240),
    )


def _readiness_code(error: StorageValidationError) -> object:
    context = error.context
    assert context is not None
    return context["readiness_code"]


def test_a_quiet_hook_leaves_the_batch_read_whole(tmp_path: Path) -> None:
    """Control: the mid-call hook fires inside the call and, doing nothing, changes nothing."""
    with (
        _seeded_session_repo(tmp_path) as (engine, repo, _, _stack),
        _after_batch_select(engine, lambda: None) as fired,
    ):
        records = tuple(_batch(repo))

    assert len(fired) == 1
    assert sorted(record.payload for record in records) == sorted(f"payload-{key}".encode() for key in _KEYS)


@pytest.mark.parametrize("runtime_bound", [False, True])
def test_a_session_that_expires_mid_call_refuses_the_whole_read(tmp_path: Path, runtime_bound: bool) -> None:
    """The deadline passes after the rows were selected: nothing is released.

    DISCRIMINATING against a read that checks the session only when it starts.
    The refusal is the session refusal a call opening after the deadline
    meets, not a row-level unreadable error.
    """
    with _seeded_session_repo(tmp_path, runtime_bound=runtime_bound) as (engine, repo, session, stack):
        with _after_batch_select(engine, lambda: stack.enter_context(frozen_clock(_AFTER_DEADLINE))) as fired:
            batch = _batch(repo)
            with pytest.raises(SessionExpiredError):
                next(batch)
        assert len(fired) == 1
        assert session.is_expired(_AFTER_DEADLINE)


def test_a_session_sealed_mid_call_refuses_the_whole_read(tmp_path: Path) -> None:
    """Logout or lock closes the session while the rows are decoded: nothing is released."""
    with (
        _seeded_session_repo(tmp_path) as (engine, repo, session, _stack),
        _after_batch_select(engine, session.close) as fired,
    ):
        batch = _batch(repo)
        with pytest.raises(SessionExpiredError):
            next(batch)

    assert len(fired) == 1
    assert session.sealed is True


@pytest.mark.parametrize("runtime_bound", [False, True])
def test_a_session_replaced_by_another_profile_mid_call_refuses_the_whole_read(
    tmp_path: Path,
    runtime_bound: bool,
) -> None:
    """A handover to another profile mid-call refuses with the session-changed refusal."""
    other = _fresh_session(bucket_id="other-profile", dek=bytes(range(32)))
    with _seeded_session_repo(tmp_path, runtime_bound=runtime_bound) as (engine, repo, _, stack):
        with _after_batch_select(engine, lambda: stack.enter_context(activate_session(other))) as fired:
            batch = _batch(repo)
            with pytest.raises(StorageValidationError) as raised:
                next(batch)
        assert len(fired) == 1
    other.close()

    assert _readiness_code(raised.value) == StorageRuntimeReadinessCode.SESSION_CHANGED.value


def test_a_new_session_for_the_same_profile_mid_call_still_refuses(tmp_path: Path) -> None:
    """Identity, not key equality, decides: a re-login with the same DEK did not authorize this read.

    A read that re-resolved its key per row would decrypt the remaining rows
    under the new session's equal DEK and release them. The batch read refuses
    instead, because the session that admitted the call is no longer in force.
    """
    with _seeded_session_repo(tmp_path) as (engine, repo, session, stack):
        replacement = _fresh_session(bucket_id=session.bucket_id, dek=session.dek)
        with _after_batch_select(engine, lambda: stack.enter_context(activate_session(replacement))) as fired:
            batch = _batch(repo)
            with pytest.raises(StorageValidationError) as raised:
                next(batch)
        assert len(fired) == 1
    replacement.close()

    assert _readiness_code(raised.value) == StorageRuntimeReadinessCode.SESSION_CHANGED.value


def test_a_session_expired_before_the_call_refuses_before_any_select(tmp_path: Path) -> None:
    """The opening check still refuses a lapsed session before the database is read."""
    with _seeded_session_repo(tmp_path) as (engine, repo, _, stack):
        stack.enter_context(frozen_clock(_AFTER_DEADLINE))
        with _after_batch_select(engine, lambda: None) as fired, pytest.raises(SessionExpiredError):
            next(_batch(repo))
        assert fired == []


def test_the_call_keys_never_render_their_key_material() -> None:
    """The resolved keys are reachable only through their properties, never through ``repr``."""
    with EphemeralBucketSession() as session:
        keys = SecureObjectCallKeys()
        rendered = repr(keys)
        assert keys.still_active() is True
        dek = session.dek
        lookup = keys.lookup_key

    assert keys.payload_key == dek
    for secret in (dek, lookup):
        assert secret.hex() not in rendered
        assert repr(secret) not in rendered
    assert "ephemeral" in rendered


# --- integrity and binding refusals through the batch path -------------------------------------


def _tamper(db_path: Path, sql: str, parameters: tuple[object, ...]) -> None:
    with sqlite3.connect(db_path) as con:
        con.execute(sql, parameters)


def _row(db_path: Path, namespace: str, natural_key: str) -> tuple[int, bytes]:
    digest = secure_object_key_digest(natural_key)
    with sqlite3.connect(db_path) as con:
        row_id, payload = con.execute(
            "SELECT id, payload FROM secure_objects WHERE namespace = ? AND object_key = ?",
            (namespace, digest),
        ).fetchone()
    return int(row_id), bytes(payload)


@contextmanager
def _seeded_plain_repo(tmp_path: Path) -> Generator[tuple[Path, SecureObjectRepository]]:
    db_path = tmp_path / "batch-refusals.db"
    with EphemeralBucketSession():
        engine = bootstrap_sqlite_engine(db_path)
        try:
            repo = SecureObjectRepository(engine=engine)
            _seed(repo)
            yield db_path, repo
        finally:
            engine.dispose()


def _flip_last_byte(db_path: Path) -> None:
    row_id, payload = _row(db_path, _NAMESPACE, "row-beta")
    _tamper(
        db_path, "UPDATE secure_objects SET payload = ? WHERE id = ?", (payload[:-1] + bytes([payload[-1] ^ 1]), row_id)
    )


def _substitute_sibling_ciphertext(db_path: Path) -> None:
    _, alpha_payload = _row(db_path, _NAMESPACE, "row-alpha")
    beta_id, _ = _row(db_path, _NAMESPACE, "row-beta")
    _tamper(db_path, "UPDATE secure_objects SET payload = ? WHERE id = ?", (alpha_payload, beta_id))


def _break_lineage(db_path: Path) -> None:
    row_id, _ = _row(db_path, _NAMESPACE, "row-gamma")
    _tamper(db_path, "UPDATE secure_objects SET revision_id = ? WHERE id = ?", ("f" * 64, row_id))


def _wrong_classification(db_path: Path) -> None:
    row_id, _ = _row(db_path, _NAMESPACE, "row-delta")
    _tamper(
        db_path,
        "UPDATE secure_objects SET classification = ? WHERE id = ?",
        (SensitivityClass.AUDIT.value, row_id),
    )


@pytest.mark.parametrize(
    "tamper",
    [_flip_last_byte, _substitute_sibling_ciphertext, _break_lineage, _wrong_classification],
    ids=["ciphertext-byte", "row-substitution", "revision-lineage", "classification"],
)
def test_every_row_refusal_still_fires_through_the_batch_read(
    tmp_path: Path,
    tamper: Callable[[Path], None],
) -> None:
    """Tag, row-identity AAD, lineage and classification refusals survive the per-call keys."""
    with _seeded_plain_repo(tmp_path) as (db_path, repo):
        tamper(db_path)
        with pytest.raises(SecureObjectUnreadableError):
            tuple(_batch(repo))


def test_a_ciphertext_moved_to_another_namespace_is_refused(tmp_path: Path) -> None:
    """The namespace is bound into the AAD: the same natural key in another namespace cannot open it."""
    with _seeded_plain_repo(tmp_path) as (db_path, repo):
        _seed(repo, keys=("row-alpha",), namespace=_OTHER_NAMESPACE)
        foreign_id, _ = _row(db_path, _OTHER_NAMESPACE, "row-alpha")
        _, payload = _row(db_path, _NAMESPACE, "row-alpha")
        _tamper(db_path, "UPDATE secure_objects SET payload = ? WHERE id = ?", (payload, foreign_id))
        with pytest.raises(SecureObjectUnreadableError):
            tuple(
                repo.load_many_current(
                    _OTHER_NAMESPACE,
                    ("row-alpha",),
                    expected_class=SensitivityClass.FINANCIAL,
                    current_version=1,
                    refuse_legacy=_refuse_legacy,
                )
            )


def test_a_tampered_schema_version_reaches_the_legacy_refusal(tmp_path: Path) -> None:
    """A row whose stored version moved is refused before any payload is decrypted."""
    with _seeded_plain_repo(tmp_path) as (db_path, repo):
        row_id, _ = _row(db_path, _NAMESPACE, "row-alpha")
        _tamper(db_path, "UPDATE secure_objects SET schema_version = ? WHERE id = ?", (2, row_id))
        with pytest.raises(_LegacyRefusedError) as raised:
            tuple(_batch(repo))

    assert raised.value.args == (("row-alpha",),)


# --- identity over varied seeds ------------------------------------------------------------------


class _SeededStream:
    """Deterministic test values drawn from a SHA-256 counter stream over ``seed``."""

    def __init__(self, seed: int) -> None:
        self._seed = seed.to_bytes(8, "big")
        self._counter = 0

    def _block(self) -> bytes:
        self._counter += 1
        return hashlib.sha256(self._seed + self._counter.to_bytes(8, "big")).digest()

    def integer(self, low: int, high: int) -> int:
        return low + int.from_bytes(self._block(), "big") % (high - low + 1)

    def payload(self, size: int) -> bytes:
        blocks = b"".join(self._block() for _ in range(size // 32 + 1))
        return blocks[:size]

    def key(self, index: int) -> str:
        alphabet = "abcdefghijklmnopqrstuvwxyz0123456789-_.:/ñçőé€"
        body = "".join(alphabet[self.integer(0, len(alphabet) - 1)] for _ in range(self.integer(1, 40)))
        return f"{index}:{body}"

    def order(self, values: list[str]) -> list[str]:
        return sorted(values, key=lambda value: hashlib.sha256(self._seed + value.encode()).digest())


@pytest.mark.parametrize("seed", [0, 1, 7, 2026, 31337])
def test_the_batch_read_returns_what_the_single_row_read_returns(tmp_path: Path, seed: int) -> None:
    """Every requested key: same record, same fields, in stored-digest order; absent keys omitted.

    The expected side is the single-row ``load``, which addresses each row
    through the ORM's own digest bind and resolves the session per call, so
    it shares neither the per-call keys nor the batch SELECT.
    """
    rng = _SeededStream(seed)
    db_path = tmp_path / f"identity-{seed}.db"
    with EphemeralBucketSession():
        engine = bootstrap_sqlite_engine(db_path)
        try:
            repo = SecureObjectRepository(engine=engine)
            stored = [rng.key(index) for index in range(rng.integer(40, 120))]
            for key in stored:
                repo.save(
                    namespace=_NAMESPACE,
                    object_key=key,
                    classification=SensitivityClass.FINANCIAL,
                    schema_version=1,
                    written_at=_T0 - timedelta(seconds=rng.integer(0, 10**8)),
                    payload=rng.payload(rng.integer(1, 4096)),
                )
            absent = [f"absent-{index}" for index in range(rng.integer(1, 10))]
            present = [stored[0], *(key for key in stored[1:] if rng.integer(0, 2))]
            requested = rng.order([*present, *absent])
            requested += requested[:5]

            batch = tuple(
                repo.load_many_current(
                    _NAMESPACE,
                    requested,
                    expected_class=SensitivityClass.FINANCIAL,
                    current_version=1,
                    refuse_legacy=_refuse_legacy,
                )
            )
            expected_by_key = {
                key: record
                for key in dict.fromkeys(requested)
                if (
                    record := repo.load(
                        _NAMESPACE,
                        key,
                        expected_class=SensitivityClass.FINANCIAL,
                        max_supported_version=1,
                    )
                )
                is not None
            }
            expected = sorted(expected_by_key.values(), key=lambda record: record.object_key)
        finally:
            engine.dispose()

    assert len(expected_by_key) == len(present)
    assert list(batch) == expected
    assert [record.model_dump() for record in batch] == [record.model_dump() for record in expected]
