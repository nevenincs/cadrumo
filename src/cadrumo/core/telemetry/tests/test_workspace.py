"""Tests for the stable pseudonymous workspace-hash derivation.

Proves the hash is deterministic per storage-root path, differs across
distinct paths, and never carries the raw path or any identity value.

See Also:
    :func:`~core.telemetry.workspace_hash`:
        Pseudonymous deployment-id helper under test.
    :class:`~core.telemetry.TelemetryEventPayload`:
        Payload contract that carries the derived ``workspace_hash``.
    :class:`~core.config.Settings`:
        Source of the local storage root used as hash input.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from .._workspace import workspace_hash

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_workspace_hash_is_a_64_char_lowercase_hex_digest(tmp_path: Path) -> None:
    digest = workspace_hash(tmp_path)
    assert len(digest) == 64
    assert digest == digest.lower()
    assert all(c in "0123456789abcdef" for c in digest)


def test_workspace_hash_is_deterministic_for_the_same_path(tmp_path: Path) -> None:
    first = workspace_hash(tmp_path)
    second = workspace_hash(tmp_path)
    assert first == second


def test_workspace_hash_differs_across_distinct_paths(tmp_path: Path) -> None:
    other = tmp_path / "other-deployment"
    other.mkdir()
    assert workspace_hash(tmp_path) != workspace_hash(other)


def test_workspace_hash_never_embeds_the_raw_path_text(tmp_path: Path) -> None:
    digest = workspace_hash(tmp_path)
    assert str(tmp_path) not in digest
    assert tmp_path.name not in digest
