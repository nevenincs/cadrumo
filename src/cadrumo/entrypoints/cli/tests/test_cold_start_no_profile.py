"""Cold-start contract: every profile-scoped verb refuses cleanly with no profile.

A first-contact operator runs a profile-scoped command before any
profile exists. The command must refuse with the same translated
``profile create`` guidance regardless of which surface it lands on —
``modelo work`` and ``ledger`` must not disagree, and no path may leak
the raw internal ``cadrumo_database_url is empty`` config error or a
low-level ``NoActiveBucketSession`` decryption failure.

These tests invoke each cold-start verb against a fresh
``CADRUMO_LOCAL_STORAGE_ROOT`` with no profile pointer and assert a clean,
consistent refusal. The CLI is invoked in-process through the cached
Click command, the same harness every other CLI test uses.
"""

from __future__ import annotations

import json
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
    (
        "app",
        "modelo",
        "readiness",
        "--modelo",
        "303",
        "--revision-id",
        "2023-y-siguientes",
        "--year",
        "2026",
        "--period",
        "1T",
    ),
    (
        "app",
        "modelo",
        "work",
        "create",
        "--modelo",
        "303",
        "--year",
        "2026",
        "--period",
        "1T",
        "--revision",
        "2023-y-siguientes",
    ),
    ("app", "modelo", "work", "list"),
    ("app", "modelo", "work", "revisions"),
    ("app", "ledger", "list"),
    ("app", "overview", "status", "--period", "2026Q1"),
)

# Internal plumbing strings that must never reach the operator.
_LEAK_MARKERS: tuple[str, ...] = (
    "cadrumo_database_url is empty",
    "CADRUMO_DATABASE_URL",
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

    with override_settings(cadrumo_output_language="en"):
        with isolated_sessionless_storage_root(tmp_path=tmp_path) as storage_root:
            yield storage_root


def _verb_label(verb: tuple[str, ...]) -> str:
    return " ".join(verb)


def test_cold_start_verbs_refuse_without_leaks_and_surface_profile_guidance(tmp_path: Path) -> None:
    """Each cold-start verb refuses cleanly and names ``profile create`` recovery guidance."""

    for index, verb in enumerate(_COLD_START_VERBS):
        label = _verb_label(verb)
        with override_settings(cadrumo_output_language="en"):
            with isolated_sessionless_storage_root(tmp_path=tmp_path / f"cold-start-{index}"):
                result = invoke_cached_cli(list(verb))

        assert result.exit_code != 0, f"{label} should refuse: {result.output}"
        for marker in _LEAK_MARKERS:
            assert marker not in result.output, f"{label} leaked internal plumbing {marker!r}: {result.output}"
        flat = result.output.replace("\n", " ")
        assert "profile create" in flat, f"{label} did not point at `profile create`: {result.output}"


def test_cold_start_refusal_is_consistent_across_surfaces(_fresh_storage_root: Path) -> None:
    """``modelo work list`` and ``ledger list`` give the identical refusal text.

    The disaster-recovery testimony flagged the two surfaces disagreeing:
    ``ledger list`` gave a clean refusal while ``modelo work list`` leaked
    the raw ``cadrumo_database_url is empty`` error. The cold-start contract
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


def test_bindings_list_missing_conservatively_lists_profile_bindings_without_active_profile(
    _fresh_storage_root: Path,
) -> None:
    result = invoke_cached_cli(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "bindings",
            "list",
            "--modelo",
            "303",
            "--year",
            "2026",
            "--period",
            "1T",
            "--missing",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    bindings = payload["result"]["bindings"]
    assert bindings, result.output
    assert all(binding["source"] != "constant_value" for binding in bindings)
    assert any(
        binding["binding_id"] == "modelo-303-autoconsumo-promotor-base" and binding["source"] == "profile"
        for binding in bindings
    ), result.output
