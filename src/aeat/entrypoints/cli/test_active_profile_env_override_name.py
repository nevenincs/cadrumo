"""Real-operator test: ``AEAT_ACTIVE_PROFILE`` accepts the display label.

An operator addresses their profile by the display label they chose at
``profile create`` — the immutable UUIDv4 bucket id is never surfaced to them.
The active-profile env override ``AEAT_ACTIVE_PROFILE`` is the highest-precedence
rung of the active-profile precedence chain, and the canonical ``core.config``
storage-route resolver keys directly on ``buckets/<value>``. Before the
entrypoint name→UUID normalization, a label-valued ``AEAT_ACTIVE_PROFILE`` made
every profile-bound command hard-miss with a "no registered bucket manifest"
refusal. This module pins the fixed behaviour by driving the REAL CLI root
callback (the normalization site) against a REAL profile created through the real
``config profile create`` flow — exactly the operator path the persona swarm
missed, not the in-process diagnostics path.

See the ``2026-06-03-cli-ledger-testimonials`` ADR + the ``2026-05-19``
profile-lifecycle disaster ADR (the single canonical route resolver this fix
feeds a UUID).
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ...adapters.persistence.storage.sql.engine import dispose_engine
from ...core.config import override_settings
from ...tests.secure_sql import isolated_profile_storage_root
from . import app

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]

_RUNNER = CliRunner()

#: The display label the operator chooses at create — the only id they know.
_LABEL = "operator"


@pytest.fixture(autouse=True)
def _isolated_root(tmp_path: Path) -> Iterator[None]:
    """Isolated storage root; no pre-opened span (each invoke is its own process surface)."""
    dispose_engine()
    with isolated_profile_storage_root(tmp_path=tmp_path):
        try:
            yield
        finally:
            dispose_engine()


def _create_profile_and_resolve_uuid() -> str:
    """Create a real profile via the CLI and return its minted UUID bucket id.

    Mirrors a real operator's ``aeat config profile create <label>`` — it mints
    the UUIDv4 bucket directory + manifest and writes the active-profile pointer
    to that UUID (never the label).
    """
    created = _RUNNER.invoke(
        app,
        [
            "config",
            "profile",
            "create",
            _LABEL,
            "--quiet",
            "--accept-defaults",
            "--tax-id",
            "12345678Z",
            "--name",
            "Operator",
            "--activity",
            "design",
        ],
    )
    assert created.exit_code == 0, created.output
    from ...application.workflow import read_profile_bucket

    pointer = read_profile_bucket(_LABEL)
    assert pointer is not None, "the created profile must resolve by its label"
    return pointer.bucket_id


def test_env_override_by_display_label_resolves_the_profile_bucket() -> None:
    """``AEAT_ACTIVE_PROFILE=<label>`` resolves the operator's bucket (the fixed bug).

    The real operator path: a fresh resolution whose active profile comes from
    the ``AEAT_ACTIVE_PROFILE`` env override set to the LABEL the operator chose.
    Before the entrypoint normalization this refused with "no registered bucket
    manifest at buckets/<label>"; the root callback now normalizes the label to
    its UUID via the single profile resolver, so a profile-bound command resolves.
    """
    uuid = _create_profile_and_resolve_uuid()
    assert uuid != _LABEL, "the bucket id must be a minted UUID, not the label"

    with override_settings(aeat_active_profile=_LABEL):
        listed = _RUNNER.invoke(app, ["--format", "json", "app", "ledger", "list"])

    assert listed.exit_code == 0, listed.output
    # The command resolved the operator's bucket and rendered the (empty) ledger
    # read model rather than refusing on a missing manifest.
    assert "REFUSED_PROFILE_NOT_FOUND" not in listed.output
    payload = json.loads(listed.output)
    assert "rows" in payload.get("result", payload)


def test_env_override_by_uuid_is_unchanged() -> None:
    """``AEAT_ACTIVE_PROFILE=<uuid>`` resolves byte-identically (backward-compatible).

    The UUID fast path must be untouched: the normalization only fires when the
    direct UUID-bucket lookup misses, so a UUID-valued override never reaches the
    label fallback.
    """
    uuid = _create_profile_and_resolve_uuid()

    with override_settings(aeat_active_profile=uuid):
        listed = _RUNNER.invoke(app, ["--format", "json", "app", "ledger", "list"])

    assert listed.exit_code == 0, listed.output
    assert "REFUSED_PROFILE_NOT_FOUND" not in listed.output


def test_env_override_unknown_label_does_not_resolve() -> None:
    """An ``AEAT_ACTIVE_PROFILE`` label matching no live profile does not resolve.

    The normalization no-ops on an unknown label (neither a UUID bucket nor a live
    label); the per-command active-profile guard then refuses rather than silently
    inventing a bucket — never a false resolution.
    """
    _create_profile_and_resolve_uuid()

    with override_settings(aeat_active_profile="no-such-profile"):
        listed = _RUNNER.invoke(app, ["--format", "json", "app", "ledger", "list"])

    assert listed.exit_code != 0, listed.output
