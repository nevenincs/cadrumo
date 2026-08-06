"""Wrapped-bucket-DEK version gate: a single-point readable range.

Companion to the secure-object, bundle and archive lineage gates. The
wrapped DEK is the key that unlocks every encrypted byte in a bucket, so it is
the paradigm durable format — yet it was declared ``DURABLE`` in the persisted
inventory while carrying no floor constant and no tier gate, which is half of
what made the checkpoint enrollment deadlock unresolvable.

This tier is deliberately the simplest shape in the set. Its version field is a
``Literal``, so the read path already refuses every direction of drift by
construction: there is no ceiling-plus-floor range to evaluate and no upgrade
dispatch to keep complete. What was missing was not enforcement but ENROLLMENT
— named constants the flip can freeze a floor against, and a gate binding those
constants to the constraint that actually does the refusing.

Nothing here touches key derivation, the wrapping scheme, the schedule enum, or
the document shape. Any change to those is owner-gated and does not belong in a
lineage gate; a bump of the ``Literal`` means a DEK document or schedule change,
and this gate exists to make such a bump loud rather than to perform it.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Final, get_args

import pytest

from ......core import COMPATIBILITY_REGIME, RELEASED_FORMAT_FLOORS, expected_floor
from ......core.external_constants import UTF_8_ENCODING
from ...crypto import GCM_TAG_SIZE, KEY_SIZE, NONCE_SIZE
from ...errors import MasterKeyUnavailableError
from .._master_key_bucket_dek import read_wrapped_bucket_dek
from .._master_key_records import (
    BUCKET_DEK_DURABILITY_FLOOR,
    BUCKET_DEK_SCHEMA_VERSION,
    _WrappedBucketDekDocument,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_FORMAT_KEY: Final[str] = "bucket_dek"


def _document_payload(*, schema_version: int) -> str:
    """Return a structurally complete wrapped-DEK document at a chosen version.

    Field lengths are taken from the real crypto constants rather than
    hand-sized, so a refusal below can only be the version gate. Hand-sized
    placeholders made the accept cases fail on field length, which would have
    left both refusal cases passing for a reason unrelated to the version.
    """
    return json.dumps(
        {
            "schema_version": schema_version,
            "nonce_b64": base64.b64encode(bytes(NONCE_SIZE)).decode("ascii"),
            "ciphertext_b64": base64.b64encode(bytes(KEY_SIZE)).decode("ascii"),
            "tag_b64": base64.b64encode(bytes(GCM_TAG_SIZE)).decode("ascii"),
        }
    )


def test_floor_does_not_exceed_current_version() -> None:
    assert BUCKET_DEK_DURABILITY_FLOOR <= BUCKET_DEK_SCHEMA_VERSION


def test_floor_matches_the_regime_expected_floor() -> None:
    """The DEK floor tracks the regime-switched compatibility policy.

    While ``PRE_RELEASE`` the expected floor IS the current version. Post-flip
    it becomes the frozen released value and this same assertion demands the
    floor stay pinned there — which is the whole point of enrolling this format:
    the flip can now freeze a floor for it, and this gate holds that floor
    honest afterwards.
    """
    assert (
        expected_floor(
            COMPATIBILITY_REGIME,
            _FORMAT_KEY,
            BUCKET_DEK_SCHEMA_VERSION,
            RELEASED_FORMAT_FLOORS,
        )
        == BUCKET_DEK_DURABILITY_FLOOR
    ), (
        "wrapped-DEK durability floor diverges from the regime-expected floor. This format has no "
        "upgrade dispatch and its version field is a Literal accepting one value, so a floor below "
        "current has no mechanism behind it; raise the floor with the version, or land a "
        "version-aware reader and an old-document restorability test in the same change"
    )


def test_the_declared_version_is_the_version_the_model_enforces() -> None:
    """The named constant and the constraint that refuses must agree.

    They are declared independently — one as a module constant, one as a
    ``Literal`` annotation — so this is a real relation rather than a value
    compared against its own definition. Without it the constant could drift
    into describing a version the model does not actually accept, and the floor
    frozen at the checkpoint would name a shape nothing can read.
    """
    enforced = get_args(_WrappedBucketDekDocument.model_fields["schema_version"].annotation)
    assert enforced == (BUCKET_DEK_SCHEMA_VERSION,), (
        f"the wrapped-DEK document enforces schema_version in {enforced} while the declared "
        f"current version is {BUCKET_DEK_SCHEMA_VERSION}; the constant and the Literal must move together"
    )


def test_every_version_from_floor_to_current_is_readable(tmp_path: Path) -> None:
    """The declared readable range is genuinely readable through the real path."""
    for version in range(BUCKET_DEK_DURABILITY_FLOOR, BUCKET_DEK_SCHEMA_VERSION + 1):
        path = tmp_path / f"dek-v{version}.json"
        path.write_text(_document_payload(schema_version=version), encoding=UTF_8_ENCODING)
        assert read_wrapped_bucket_dek(path) is not None


def test_a_future_dek_version_is_refused_by_the_real_read_path(tmp_path: Path) -> None:
    """A document written by a newer application is refused, not silently read.

    Driven through ``read_wrapped_bucket_dek`` rather than the model directly,
    so this proves the refusal survives the production read path's own
    exception translation instead of only the annotation.
    """
    path = tmp_path / "dek-future.json"
    path.write_text(_document_payload(schema_version=BUCKET_DEK_SCHEMA_VERSION + 1), encoding=UTF_8_ENCODING)
    with pytest.raises(MasterKeyUnavailableError):
        read_wrapped_bucket_dek(path)


def test_a_below_floor_dek_version_is_refused_by_the_real_read_path(tmp_path: Path) -> None:
    """The other direction is refused too, so the range is closed at both ends.

    Asserted separately from the future case rather than assumed symmetric: the
    ``Literal`` happens to close both ends today, but a later widening to a
    ceiling-only gate would silently re-open this side, and the wrapped DEK is
    the last format where a silently-accepted foreign shape should be tolerated.
    """
    path = tmp_path / "dek-ancient.json"
    path.write_text(_document_payload(schema_version=BUCKET_DEK_DURABILITY_FLOOR - 1), encoding=UTF_8_ENCODING)
    with pytest.raises(MasterKeyUnavailableError):
        read_wrapped_bucket_dek(path)


def test_a_current_version_document_is_accepted(tmp_path: Path) -> None:
    """Anti-tautology: the refusals above discriminate rather than always-refuse.

    Without this, a read path broken in some unrelated way would make both
    refusal tests pass while proving nothing about the version gate.
    """
    path = tmp_path / "dek-current.json"
    path.write_text(_document_payload(schema_version=BUCKET_DEK_SCHEMA_VERSION), encoding=UTF_8_ENCODING)
    assert read_wrapped_bucket_dek(path) is not None
