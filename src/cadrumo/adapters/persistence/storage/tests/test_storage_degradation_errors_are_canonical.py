"""Behavioral checks for the canonical storage-degradation error set."""

from __future__ import annotations

import pytest

from ..errors import (
    STORAGE_DEGRADATION_ERRORS,
    ClassificationError,
    DecryptionError,
    EnvelopeVersionError,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


def test_the_canonical_set_is_what_it_claims() -> None:
    assert (
        ClassificationError,
        DecryptionError,
        EnvelopeVersionError,
    ) == STORAGE_DEGRADATION_ERRORS


def test_every_member_is_catchable_as_an_exception() -> None:
    assert STORAGE_DEGRADATION_ERRORS
    for member in STORAGE_DEGRADATION_ERRORS:
        assert isinstance(member, type)
        assert issubclass(member, BaseException)
