"""Cross-process proof for the profile-record object-key boundary.

The sibling roundtrip suite saves and loads inside one interpreter, which is
the one configuration where a process-scoped key derivation cannot fail: the
same live session both writes the row and computes the key it is compared
against. Every observation that made the record look invisible across a
process boundary came from a reader that had NOT written it, so the boundary
is the subject and only a second process can carry it.

The child interpreter publishes the capsule through the production lifecycle
-- which stages the encrypted database under the short-lived staging session
the capsule repository opens BEFORE publication -- and exits. This process
then opens the published capsule cold and reads the row back. Nothing is
shared but the storage root on disk: no session, no cache, no import state.

The stored ``object_key`` is a keyed digest of the natural key under a
sub-key derived from the profile's data key, so the assertion that it is
byte-identical to the digest THIS process derives is the direct measurement
of key stability across the staging/published boundary, not an inference
from a successful read.

Every adapter is real: a real published capsule on disk, a real SQLite
substrate, a real ``ProfileRecordSession`` over a real envelope, and the
production ``ProfileRecordStore``. The anti-tautology proofs corrupt the
persisted bytes -- one for each half of the two-part admission test -- and
require the cold load to refuse. If either ever passes with the boundary
broken, the roundtrip assertion above it is worthless.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from pathlib import Path
from textwrap import dedent

import pytest

from ....adapters.persistence.storage import DecryptionError
from ....domain.user_profile import UserProfileRecord
from ....tests.subprocess_cli import run_subprocess_cli_harness
from .. import (
    profile_custody_secure_object_key_digest,
    profile_custody_secure_object_repository,
)
from .._capsule_record import (
    ProfileRecordIntegrityError,
    ProfileRecordSession,
    ProfileRecordStore,
    profile_record_object_key,
)
from ._profile_record_boundary_support import (
    PROFILE_ID,
    RECORD_NAMESPACE,
    defaultable_fields_at_default,
    initial_record,
    open_record_session,
    replacement_record,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PUBLISHER_SOURCE = dedent(
    """
    from __future__ import annotations

    import sys
    from pathlib import Path

    from cadrumo.application.user_profile.tests._profile_record_boundary_support import (
        advance_to_revision_two,
        open_record_session,
        publish_capsule,
    )

    root = Path(sys.argv[1])
    written = publish_capsule(root)
    session = open_record_session()
    try:
        advance_to_revision_two(
            session,
            root,
            written,
            event_payload={"reason": "cross-process-boundary-proof"},
        )
    finally:
        session.close()
    """,
)
"""Child program: publish the capsule AND drive its replacement, then exit.

Both revisions are written by the child on purpose. Revision one cannot
populate ``record_revision`` or ``previous_record_digest`` with a non-default
value, so a capsule left at revision one would cross the boundary with two
fields at their defaults and a save-drops regression in either would be
invisible to the equality assertion. Advancing HERE rather than in the
reading process keeps every persisted field the work of a process that has
since exited.
"""


def _publish_in_a_separate_process(root: Path) -> None:
    """Publish the capsule in a genuinely fresh interpreter, then let it exit.

    ``CADRUMO_`` is stripped from the child's environment alongside the
    scaffolding prefixes: the capsule root is passed as an explicit argument,
    so a developer's exported storage root must not be able to redirect where
    this test writes.
    """
    completed = run_subprocess_cli_harness(
        _PUBLISHER_SOURCE,
        [str(root)],
        env_strip_prefixes=("AEAT_", "PYTEST_", "CADRUMO_"),
    )
    assert completed.returncode == 0, f"publisher process failed:\n{completed.stdout}\n{completed.stderr}"


def _capsule_database(root: Path) -> Path:
    databases = sorted(root.rglob("cadrumo.db"))
    assert len(databases) == 1, f"expected exactly one published capsule database, found {databases}"
    return databases[0]


def _stored_object_key(root: Path) -> bytes:
    """Read the persisted key digest straight from disk, decrypting nothing.

    The ``object_key`` column is already an opaque keyed digest, so reading it
    needs no session at all -- which is what makes it usable as the
    measurement: it is the value the WRITER produced, observed without going
    back through any read path that could reproduce the writer's mistake.
    """
    connection = sqlite3.connect(_capsule_database(root))
    try:
        rows = connection.execute(
            "SELECT object_key FROM secure_objects WHERE namespace = ?",
            (RECORD_NAMESPACE,),
        ).fetchall()
    finally:
        connection.close()
    assert len(rows) == 1, f"expected exactly one persisted record row, found {len(rows)}"
    return bytes(rows[0][0])


def _mutate_persisted_row(root: Path, column: str, value: bytes) -> None:
    connection = sqlite3.connect(_capsule_database(root))
    try:
        connection.execute(
            f"UPDATE secure_objects SET {column} = ? WHERE namespace = ?",  # noqa: S608
            (value, RECORD_NAMESPACE),
        )
        connection.commit()
        connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        connection.close()


@pytest.fixture
def published_capsule(tmp_path: Path) -> Iterator[tuple[ProfileRecordSession, Path]]:
    """Publish the capsule elsewhere, then hand this process a cold session."""
    root = tmp_path / "published"
    root.mkdir()
    _publish_in_a_separate_process(root)
    session = open_record_session()
    try:
        yield session, root
    finally:
        session.close()


def test_record_published_by_another_process_roundtrips_strictly(
    published_capsule: tuple[ProfileRecordSession, Path],
) -> None:
    """Strict equality against a capsule this interpreter never wrote.

    The expected record is rebuilt here from the shared fixture rather than
    handed over by the child, so the comparison is against an independently
    constructed value and not against whatever the writer happened to emit.
    """
    session, root = published_capsule

    loaded = ProfileRecordStore(session=session, root=root).load().record

    assert loaded == replacement_record(initial_record())
    assert isinstance(loaded, UserProfileRecord)


def test_every_defaultable_field_survives_the_process_boundary_non_default(
    published_capsule: tuple[ProfileRecordSession, Path],
) -> None:
    """Keep the cross-process fixture honest, exactly as the in-process one is.

    Strict equality is only a strong claim while the record being compared
    populates its defaultable fields. If the fixture degraded to defaults,
    a boundary that dropped one of them and re-defaulted it on load would
    still satisfy the equality assertion above.
    """
    session, root = published_capsule
    loaded = ProfileRecordStore(session=session, root=root).load().record

    at_default = defaultable_fields_at_default(loaded)

    assert not at_default, (
        "these defaultable fields sit at their model default after crossing the process "
        f"boundary, so a save-drops-field / load-re-defaults-field regression in them "
        f"would be invisible: {sorted(at_default)}"
    )


def test_object_key_written_by_another_process_is_byte_identical(
    published_capsule: tuple[ProfileRecordSession, Path],
) -> None:
    """The measurement: the writer's key and this process's key are the same bytes.

    This is the assertion the hypothesis about a staging-session-scoped key
    would have failed. The publishing process wrote the row under the
    short-lived staging session that precedes capsule publication; this one
    derives the key from the published envelope's data key. A derivation that
    folded in anything session-scoped -- a session identity, an open instant,
    a per-session salt -- would produce two different digests here while every
    other observation stayed unchanged.
    """
    session, root = published_capsule
    stored = _stored_object_key(root)

    # The digest needs the profile's data key bound, which is exactly what the
    # production repository context establishes; nothing here reaches past it.
    with profile_custody_secure_object_repository(
        profile_id=session.profile_id,
        dek=session.encryption_key(),
        root=root,
    ):
        derived = profile_custody_secure_object_key_digest(profile_record_object_key(PROFILE_ID))

    assert derived == stored


def test_cold_load_refuses_a_row_whose_object_key_was_corrupted_on_disk(
    published_capsule: tuple[ProfileRecordSession, Path],
) -> None:
    """Anti-tautology for the KEY half, and for the refusal that reports it.

    Corrupting the stored key leaves the row count at exactly one, so the
    count clause of the admission test passes and only the key clause can
    fail. A refusal naming the row count here would be describing the half
    that did not fail -- the precise diagnostic defect this proof exists to
    keep fixed -- so the assertion binds to what genuinely failed and
    explicitly rejects the count wording.
    """
    session, root = published_capsule
    corrupted = bytes(byte ^ 0xFF for byte in _stored_object_key(root))
    _mutate_persisted_row(root, "object_key", corrupted)

    with pytest.raises(ProfileRecordIntegrityError) as refusal:
        ProfileRecordStore(session=session, root=root).load()

    message = str(refusal.value)
    assert "addressed to a different object key" in message
    assert "exactly one current record row" not in message


def test_cold_load_refuses_a_row_whose_payload_was_corrupted_on_disk(
    published_capsule: tuple[ProfileRecordSession, Path],
) -> None:
    """Anti-tautology for the payload: corrupted ciphertext must not load.

    The payload is AEAD-sealed against the row's own identity, so flipping
    its bytes must fail authentication rather than decode into some other
    record. If this ever loads cleanly, the encrypted boundary is not
    authenticating anything and every roundtrip assertion here is vacuous.
    """
    session, root = published_capsule
    _mutate_persisted_row(root, "payload", b"\x00" * 96)

    with pytest.raises((ProfileRecordIntegrityError, DecryptionError)):
        ProfileRecordStore(session=session, root=root).load()
