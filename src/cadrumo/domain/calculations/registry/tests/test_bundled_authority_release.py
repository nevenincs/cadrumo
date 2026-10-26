"""Releasing the process-shared authority owner closes its database and lets the next use reopen it.

Each case reads a private copy of the published pair, so the owner it opens and
releases holds a database nothing else in the session reads.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from pathlib import Path

import pytest

from ..authority import bundled_indexed_authority, release_bundled_indexed_authority
from ..authority_store import AuthorityStoreError
from .shared_authority_isolation import isolated_shared_authority

pytestmark = [pytest.mark.integration, pytest.mark.hex_domain]


@pytest.fixture
def private_database(tmp_path: Path) -> Iterator[Path]:
    """Serve the shared owner from a private copy and yield the copied database."""
    with isolated_shared_authority(tmp_path) as database:
        yield database


def test_release_closes_the_shared_owner_and_the_next_use_admits_a_fresh_one(private_database: Path) -> None:
    released = bundled_indexed_authority()
    with released.operation() as operation:
        generation = operation.pin().logical_generation

    assert release_bundled_indexed_authority() is True

    with pytest.raises(AuthorityStoreError, match="closed"), released.operation():
        pass
    reopened = bundled_indexed_authority()
    assert reopened is not released
    with reopened.operation() as operation:
        assert operation.pin().logical_generation == generation
    assert release_bundled_indexed_authority() is True
    assert release_bundled_indexed_authority() is True


def test_a_released_database_is_no_longer_held_open(private_database: Path) -> None:
    """Windows refuses to delete a file any connection still holds, so the deletion is the proof there."""
    with bundled_indexed_authority().operation():
        pass

    assert release_bundled_indexed_authority() is True
    private_database.unlink()

    assert not private_database.exists()


def test_release_is_refused_and_logged_while_an_operation_holds_a_lease(
    private_database: Path, caplog: pytest.LogCaptureFixture
) -> None:
    owner = bundled_indexed_authority()
    with owner.operation(), caplog.at_level(logging.WARNING):
        assert release_bundled_indexed_authority() is False

    assert "the shared registry authority stayed open" in caplog.text
    assert "hold leases" in caplog.text
    # The refusal closed nothing: the same owner is still shared and still reads.
    assert bundled_indexed_authority() is owner
    with owner.operation() as operation:
        assert operation.pin().logical_generation
    assert release_bundled_indexed_authority() is True
