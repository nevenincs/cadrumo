"""The authority cache key hashes on a digest, not on the fingerprint corpus.

The key carries the complete fingerprint of every file the authority read,
because that is what makes a tree edit visible. Hashing those tuples on every
lookup costs one pass over the whole corpus, and the corpus grows. Keying on a
digest makes the hash constant while leaving the tuples available to the body
and leaving invalidation exactly as strict: a different corpus digests
differently, so it misses the cache.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from .....core.hashing import content_hash_hex
from ..authority import (
    _authority_comparison_domain,
    _authority_comparison_domain_payload,
    _canonical_authority_root_pair,
    _fingerprint_key,
    _fingerprint_key_payload,
    _FingerprintKey,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _fingerprints(count: int) -> tuple[tuple[str, int, int, str], ...]:
    return tuple((f"modelos/{index}/revision.toml", index, 1700000000 + index, f"d{index}") for index in range(count))


def test_the_key_carries_the_fingerprints_the_body_reads() -> None:
    """The digest must not cost the body access to the tuples it validates against."""
    fingerprints = _fingerprints(4)
    assert _fingerprint_key(fingerprints).fingerprints == fingerprints


def test_the_key_digest_uses_the_canonical_framed_content_hash() -> None:
    """The source-key frame stays explicit while hashing stays core-owned."""
    fingerprints = (("modelos/303/revision.toml", 1, 2, "digest"),)

    assert _fingerprint_key(fingerprints).digest == content_hash_hex(_fingerprint_key_payload(fingerprints))
    assert len(_fingerprint_key(fingerprints).digest) == 64


def test_the_comparison_domain_preserves_its_frame_under_the_canonical_hash(tmp_path: Path) -> None:
    """The opaque domain is byte-for-byte the core hash of its explicit frame."""
    root = tmp_path / "registry-root"
    source_root = tmp_path / "source-root"
    root.mkdir()
    source_root.mkdir()
    identity = _canonical_authority_root_pair(root, source_root)

    payload = _authority_comparison_domain_payload(identity)
    domain = _authority_comparison_domain(identity)

    assert domain == content_hash_hex(payload)
    assert isinstance(domain, str)
    assert len(domain) == 64


def test_the_hash_is_the_digest_hash_and_not_the_corpus_hash() -> None:
    """A large corpus and a small one both hash one fixed-width digest."""
    small = _fingerprint_key(_fingerprints(1))
    large = _fingerprint_key(_fingerprints(5000))
    assert hash(small) == hash(small.digest)
    assert hash(large) == hash(large.digest)
    assert len(small.digest) == len(large.digest)


def test_equal_corpora_produce_one_cache_entry() -> None:
    """Two independently collected but identical corpora must hit the same entry."""
    first = _fingerprint_key(_fingerprints(64))
    second = _fingerprint_key(_fingerprints(64))
    assert first is not second
    assert first == second
    assert hash(first) == hash(second)
    assert len({first, second}) == 1


@pytest.mark.parametrize(
    ("mutate", "reason"),
    [
        (lambda rows: rows[:-1], "a dropped file"),
        (lambda rows: (*rows, ("modelos/new/revision.toml", 99, 1700000099, "dnew")), "an added file"),
        (lambda rows: ((rows[0][0], rows[0][1], rows[0][2], "CHANGED"), *rows[1:]), "a changed digest"),
        (lambda rows: ((rows[0][0], rows[0][1], 1799999999, rows[0][3]), *rows[1:]), "a changed mtime"),
        (lambda rows: (rows[1], rows[0], *rows[2:]), "a reordered corpus"),
    ],
)
def test_any_corpus_change_changes_the_key(
    mutate: Callable[
        [tuple[tuple[str, int, int, str], ...]],
        tuple[tuple[str, int, int, str], ...],
    ],
    reason: str,
) -> None:
    """Invalidation must not be weakened: every corpus edit must miss the cache."""
    rows = _fingerprints(8)
    original = _fingerprint_key(rows)
    changed = _fingerprint_key(mutate(rows))
    assert changed != original, f"{reason} still hit the cached authority"
    assert changed.digest != original.digest, f"{reason} produced a colliding digest"


def test_field_boundaries_cannot_be_forged_by_concatenation() -> None:
    """Delimiting each field stops two different corpora digesting the same."""
    left = _fingerprint_key((("ab", 1, 2, "c"),))
    right = _fingerprint_key((("a", 1, 2, "bc"),))
    assert left != right


def test_a_foreign_key_type_is_never_equal() -> None:
    """Equality is defined against this key type only."""
    assert _fingerprint_key(_fingerprints(2)) != "not-a-key"


def test_the_key_is_hashable_while_frozen() -> None:
    """The key must stay immutable, since a cache key that can be edited is a bug."""
    key = _fingerprint_key(_fingerprints(2))
    with pytest.raises(AttributeError):
        field_name = "digest"
        setattr(key, field_name, "tampered")
    assert isinstance(key, _FingerprintKey)
