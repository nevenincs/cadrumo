"""Cold-start contract: every profile-scoped verb refuses cleanly with no profile.

A first-contact operator runs a profile-scoped command before any
profile exists. The command must refuse with the same translated
``profile create`` guidance regardless of which surface it lands on —
``modelo work`` and ``ledger`` must not disagree, and no path may leak
the raw internal ``aeat_database_url is empty`` config error or a
low-level ``NoActiveBucketSession`` decryption failure.

These tests invoke each cold-start verb against a fresh
``AEAT_LOCAL_STORAGE_ROOT`` with no profile pointer and assert a clean,
consistent refusal. The CLI is invoked in-process through the cached
Click command, the same harness every other CLI test uses.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from ....core.config import override_settings
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_sessionless_storage_root

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

# Profile-scoped verbs an operator may reach on first contact. Each
# opens the active-profile bucket database; with no profile every one
# must produce the same clean translated refusal.
_COLD_START_VERBS: tuple[tuple[str, ...], ...] = (
    ("app", "modelo", "work", "list"),
    ("app", "modelo", "work", "revisions"),
    ("app", "ledger", "list"),
    ("app", "overview", "status", "--period", "2026Q1"),
)

# Internal plumbing strings that must never reach the operator.
_LEAK_MARKERS: tuple[str, ...] = (
    "aeat_database_url is empty",
    "AEAT_DATABASE_URL",
    "NoActiveBucketSession",
    "Traceback",
    "StorageError",
)


@pytest.fixture
def _fresh_storage_root(tmp_path: Path) -> Iterator[Path]:
    """A pristine storage root: no pointer, no database, no buckets.

    Output-language is pinned to English via ``override_settings`` so
    locale-resolved CLI output stays deterministic for assertions.
    """

    with override_settings(aeat_output_language="en"):
        with isolated_sessionless_storage_root(tmp_path=tmp_path) as storage_root:
            yield storage_root


@pytest.mark.parametrize("verb", _COLD_START_VERBS, ids=lambda v: " ".join(v))
def test_cold_start_verb_refuses_without_leaking_internals(verb: tuple[str, ...], _fresh_storage_root: Path) -> None:
    """Each cold-start verb refuses without surfacing a raw config error."""

    result = invoke_cached_cli(list(verb))

    assert result.exit_code != 0, f"{' '.join(verb)} should refuse: {result.output}"
    for marker in _LEAK_MARKERS:
        assert marker not in result.output, f"{' '.join(verb)} leaked internal plumbing {marker!r}: {result.output}"


@pytest.mark.parametrize("verb", _COLD_START_VERBS, ids=lambda v: " ".join(v))
def test_cold_start_verb_surfaces_profile_create_guidance(verb: tuple[str, ...], _fresh_storage_root: Path) -> None:
    """Each cold-start verb names ``profile create`` so the operator can recover."""

    result = invoke_cached_cli(list(verb))

    flat = result.output.replace("\n", " ")
    assert "profile create" in flat, f"{' '.join(verb)} did not point at `profile create`: {result.output}"


def test_cold_start_refusal_is_consistent_across_surfaces(_fresh_storage_root: Path) -> None:
    """``modelo work list`` and ``ledger list`` give the identical refusal text.

    The disaster-recovery testimony flagged the two surfaces disagreeing:
    ``ledger list`` gave a clean refusal while ``modelo work list`` leaked
    the raw ``aeat_database_url is empty`` error. The cold-start contract
    is that every profile-scoped surface produces the same refusal.
    """

    modelo = invoke_cached_cli(["app", "modelo", "work", "list"])
    ledger = invoke_cached_cli(["app", "ledger", "list"])

    assert modelo.exit_code != 0, modelo.output
    assert ledger.exit_code != 0, ledger.output
    assert modelo.output.strip() == ledger.output.strip(), (
        "cold-start refusal diverged between modelo work and ledger surfaces:\n"
        f"  modelo work list: {modelo.output!r}\n"
        f"  ledger list:      {ledger.output!r}"
    )


def test_overview_period_status_uses_refusal_boundary(_fresh_storage_root: Path) -> None:
    """`overview status --period` must not wrap no-profile as a bad parameter."""

    result = invoke_cached_cli(["app", "overview", "status", "--period", "2026Q1"])

    assert result.exit_code != 0, result.output
    assert "Invalid value" not in result.output
    assert "profile create" in result.output.replace("\n", " ")
