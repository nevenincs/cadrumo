"""Roundtrip: every ``repair`` verb runs sessionless on a fresh root.

The repair bootstrap contract makes the ``aeat config repair`` family
state-free: every repair verb must run cleanly
without an active :class:`BucketSession` on a pristine storage root.
The original disaster welded the escape hatch shut — every documented
recovery verb crashed with ``NoActiveBucketSessionError`` from the
same cold-start gap it was meant to recover from.

These tests invoke each repair verb against a fresh
``CADRUMO_LOCAL_STORAGE_ROOT`` with no profile pointer, no encrypted
database, and no buckets directory, and assert a clean exit. A verb
that re-introduces a session requirement, or that crashes on the
absent per-bucket database URL, fails loudly here.

The CLI is invoked in-process through the cached Click command, the
same harness every other CLI test uses.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest

from ....adapters.persistence.storage.master_key.active_session import has_active_bucket_session
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_sessionless_storage_root

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

# Every fast repair verb (and sub-verb) that must run sessionless on a
# clean root. `repair` (bare) and `integrity registry` are exercised in
# dedicated tests because they run the slower registry probe.
_FAST_REPAIR_VERBS: tuple[tuple[str, ...], ...] = (
    ("config", "repair", "logs"),
    ("config", "repair", "reset-progress", "--yes"),
    ("config", "repair", "reset-progress", "--dry-run"),
    ("config", "repair", "quarantine", "--yes"),
    ("config", "repair", "profile"),
    ("config", "repair", "connectivity"),
    ("config", "repair", "integrity", "objects"),
)


@pytest.fixture
def _fresh_storage_root(tmp_path: Path) -> Iterator[Path]:
    """A pristine storage root: no pointer, no database, no buckets.

    Output-language is pinned to English via ``override_settings`` so
    locale-resolved CLI output stays deterministic for assertions.
    """

    from ....core.config import override_settings

    with (
        override_settings(cadrumo_output_language="en"),
        isolated_sessionless_storage_root(tmp_path=tmp_path) as storage_root,
    ):
        yield storage_root


@pytest.mark.parametrize("verb", _FAST_REPAIR_VERBS, ids=lambda v: " ".join(v))
def test_repair_verb_runs_clean_without_session_on_fresh_root(verb: tuple[str, ...], _fresh_storage_root: Path) -> None:
    """Each fast repair verb exits 0 on a fresh root with no active session."""

    assert not has_active_bucket_session(), "fixture must leave no session active"

    result = invoke_cached_cli(list(verb))

    assert result.exit_code == 0, f"{' '.join(verb)} failed: {result.output}"
    # `repair logs` echoes the on-disk log file verbatim, which may
    # carry tracebacks from earlier runs; the crash-surface assertion
    # below would mis-fire on its dumped content. Every other repair
    # verb renders its own structured payload, so the no-crash check
    # applies. The exit-0 assertion above is the universal contract.
    if verb[:3] != ("config", "repair", "logs"):
        assert "NoActiveBucketSession" not in result.output
        assert "Traceback" not in result.output


def test_bare_repair_runs_clean_without_session_on_fresh_root(_fresh_storage_root: Path) -> None:
    """``aeat config repair`` (the bare diagnostic) runs sessionless on a fresh root.

    The bare verb walks the full local-environment diagnostic. It must
    complete without an active session — a degraded ``overall`` status
    is an expected diagnostic verdict, not a crash.
    """

    result = invoke_cached_cli(["config", "repair"])
    json_result = invoke_cached_cli(["--format", "json", "config", "repair"])

    assert result.exit_code == 0, result.output
    assert json_result.exit_code == 0, json_result.output
    assert "NoActiveBucketSession" not in result.output
    assert "Traceback" not in result.output

    payload = json.loads(json_result.output)
    profile_check = next(check for check in payload["result"]["checks"] if check["name"] == "profile.readiness")
    # `next_action` is a retired prose channel, not a field that happens to be
    # unset: the payload model forbids it outright, so reading it here asserted
    # nothing and could only ever raise. The typed projection below is what
    # replaced it.
    assert "next_action" not in profile_check
    assert profile_check["precondition_action"]["failed_condition_id"] == "profile.active.available"
    assert profile_check["precondition_action"]["action"]["action"]["action_id"] == "operator.profile.create"
    assert profile_check["precondition_action"]["missing_argument_names"] == ["profile_name"]
    assert "aeat " not in json.dumps(profile_check).lower()


def test_integrity_registry_runs_clean_without_session_on_fresh_root(_fresh_storage_root: Path) -> None:
    """``aeat config repair integrity registry`` runs sessionless on a fresh root.

    The opt-in registry-validation verb probes the bundled registry,
    not encrypted state, so it must run without a session regardless
    of the storage root's contents.
    """

    result = invoke_cached_cli(["config", "repair", "integrity", "registry"])

    assert result.exit_code == 0, result.output
    assert "NoActiveBucketSession" not in result.output
    assert "Traceback" not in result.output


def test_quarantine_on_fresh_root_reports_nothing_to_quarantine(_fresh_storage_root: Path) -> None:
    """The cold-root quarantine guard reports a clean no-op, not a crash.

    Before the disaster recovery, ``repair quarantine`` crashed on the
    absent per-bucket database URL. The cold-root guard now reports a
    zero-row no-op so the operator sees the verb completed.
    """

    result = invoke_cached_cli(["config", "repair", "quarantine", "--yes"])

    assert result.exit_code == 0, result.output
    assert "quarantined\t0" in result.output
    assert "cadrumo_database_url is empty" not in result.output


def test_reset_progress_on_fresh_root_reports_nothing_to_reset(_fresh_storage_root: Path) -> None:
    """The cold-root reset-progress guard reports a clean no-op, not a crash."""

    result = invoke_cached_cli(["config", "repair", "reset-progress", "--yes"])

    assert result.exit_code == 0, result.output
    assert "reset\tfalse" in result.output
    assert "nothing to reset" in result.output


def test_repair_profile_refuses_removed_manifest_status_flag(_fresh_storage_root: Path) -> None:
    """The removed manifest backfill flag is not accepted as a hidden repair path."""

    result = invoke_cached_cli(["config", "repair", "profile", "--repair-manifest-status", "--yes"])

    assert result.exit_code != 0, result.output
    assert "Traceback" not in result.output
    assert "repair-manifest-status" in result.output


def test_repair_profile_clear_active_requires_confirmation(_fresh_storage_root: Path) -> None:
    """``--clear-active`` without ``--yes`` is refused by the requires-yes guard."""

    result = invoke_cached_cli(["config", "repair", "profile", "--clear-active"])

    assert result.exit_code != 0, result.output
    assert "Traceback" not in result.output
