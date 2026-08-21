"""The durable local-record contract an interrupted login recovers through.

The login handover journal is one bounded local custody record. Every failure
against it is funnelled into a fail-closed refusal, so what these primitives
accept and refuse IS the recovery contract: a retry that converges, a crash that
leaves a resumable witness, and a foreign leaf that is preserved rather than
overwritten.

The behaviour under test is the part a caller cannot verify for itself. It has
to publish once and know a second publication cannot silently win; it has to
re-submit the same receipt after a crash and have that be a no-op rather than an
error; and when it loses a compare-and-swap it needs the leaf it did not write
left exactly as it found it, because that leaf is another party's witness.

Driven against real files through the package facade, with no patching: these
are filesystem primitives, and a stand-in for the filesystem would assert only
the shape of the call.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from .. import (
    ProfileCustodyRecordError,
    clear_profile_custody_local_record,
    compare_and_replace_profile_custody_local_record,
    compare_and_replace_same_or_predecessor_profile_custody_local_record,
    read_optional_profile_custody_local_record,
    write_profile_custody_local_record,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_LIMIT = 4096
_FIRST = b'{"phase":"prepared"}'
_SECOND = b'{"phase":"published"}'
_FOREIGN = b'{"phase":"someone-elses"}'


def _record(tmp_path: Path) -> Path:
    return tmp_path / "handover-journal"


def _on_disk(path: Path) -> bytes | None:
    return read_optional_profile_custody_local_record(path, maximum_bytes=_LIMIT)


def test_a_write_once_publication_refuses_a_second_publisher(tmp_path: Path) -> None:
    """DISCRIMINATING: two processes must not both believe they published.

    The witness is created write-once precisely so a second party discovers the
    first rather than overwriting it.
    """
    path = _record(tmp_path)
    write_profile_custody_local_record(path, _FIRST, publish_once=True)

    with pytest.raises(ProfileCustodyRecordError, match="already exists"):
        write_profile_custody_local_record(path, _SECOND, publish_once=True)

    assert _on_disk(path) == _FIRST


def test_the_expected_witness_is_replaced(tmp_path: Path) -> None:
    """The ordinary advance: the caller's captured bytes are still on disk."""
    path = _record(tmp_path)
    write_profile_custody_local_record(path, _FIRST, publish_once=True)

    compare_and_replace_profile_custody_local_record(
        path, expected=_FIRST, replacement=_SECOND, maximum_bytes=_LIMIT
    )

    assert _on_disk(path) == _SECOND


def test_a_lost_compare_and_swap_preserves_the_other_partys_bytes(tmp_path: Path) -> None:
    """DISCRIMINATING: refusing is not enough; the leaf must survive intact.

    The caller lost the race, so the record on disk belongs to whoever won it.
    A refusal that had already destroyed or truncated those bytes would leave
    the winner's witness unrecoverable.
    """
    path = _record(tmp_path)
    write_profile_custody_local_record(path, _FOREIGN, publish_once=True)

    with pytest.raises(ProfileCustodyRecordError):
        compare_and_replace_profile_custody_local_record(
            path, expected=_FIRST, replacement=_SECOND, maximum_bytes=_LIMIT
        )

    assert _on_disk(path) == _FOREIGN


def test_republishing_the_current_witness_is_a_successful_no_op(tmp_path: Path) -> None:
    """DISCRIMINATING: the crash-retry case the idempotent CAS exists for.

    A process that crashed after publishing re-submits the same receipt on the
    next run. If that raised, recovery could never converge; if it wrote again,
    it would emit a second mutation for one logical transition.
    """
    path = _record(tmp_path)
    write_profile_custody_local_record(path, _SECOND, publish_once=True)

    compare_and_replace_same_or_predecessor_profile_custody_local_record(
        path, current=_SECOND, predecessor=_FIRST, maximum_bytes=_LIMIT
    )

    assert _on_disk(path) == _SECOND


def test_the_exact_predecessor_converges_to_the_current_witness(tmp_path: Path) -> None:
    """The other half: a crash BEFORE the transition still completes it."""
    path = _record(tmp_path)
    write_profile_custody_local_record(path, _FIRST, publish_once=True)

    compare_and_replace_same_or_predecessor_profile_custody_local_record(
        path, current=_SECOND, predecessor=_FIRST, maximum_bytes=_LIMIT
    )

    assert _on_disk(path) == _SECOND


def test_a_leaf_that_is_neither_current_nor_predecessor_is_refused(tmp_path: Path) -> None:
    """DISCRIMINATING: the idempotent CAS must not degrade into a blind write.

    Accepting anything other than the two known states would let a retry
    overwrite an unrelated witness while reporting convergence.
    """
    path = _record(tmp_path)
    write_profile_custody_local_record(path, _FOREIGN, publish_once=True)

    with pytest.raises(ProfileCustodyRecordError):
        compare_and_replace_same_or_predecessor_profile_custody_local_record(
            path, current=_SECOND, predecessor=_FIRST, maximum_bytes=_LIMIT
        )

    assert _on_disk(path) == _FOREIGN


def test_an_oversized_payload_is_refused_before_it_reaches_disk(tmp_path: Path) -> None:
    """The bound is the reason the witness stays cheap to read on every login."""
    path = _record(tmp_path)
    write_profile_custody_local_record(path, _FIRST, publish_once=True)

    with pytest.raises(ProfileCustodyRecordError, match="byte limit"):
        compare_and_replace_profile_custody_local_record(
            path, expected=_FIRST, replacement=b"x" * 64, maximum_bytes=16
        )

    assert _on_disk(path) == _FIRST


def test_clearing_an_absent_record_is_idempotent(tmp_path: Path) -> None:
    """A rolled-back handover clears a witness that may already be gone."""
    clear_profile_custody_local_record(_record(tmp_path))


def test_clearing_removes_the_published_witness(tmp_path: Path) -> None:
    """ANTI-TAUTOLOGY: the idempotent clear must still actually clear."""
    path = _record(tmp_path)
    write_profile_custody_local_record(path, _FIRST, publish_once=True)

    clear_profile_custody_local_record(path)

    assert _on_disk(path) is None
