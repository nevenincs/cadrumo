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

from aeat.adapters.persistence.storage.sql.engine import dispose_engine
from aeat.tests.cli_runner import invoke_cached_cli

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]

# Profile-scoped verbs an operator may reach on first contact. Each
# opens the active-profile bucket database; with no profile every one
# must produce the same clean translated refusal.
_COLD_START_VERBS: tuple[tuple[str, ...], ...] = (
    ("app", "modelo", "work", "list"),
    ("app", "modelo", "work", "revisions"),
    ("app", "ledger", "list"),
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
def _fresh_storage_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """A pristine storage root: no pointer, no database, no buckets."""

    monkeypatch.delenv("AEAT_DATABASE_URL", raising=False)
    monkeypatch.setenv("AEAT_LOCAL_STORAGE_ROOT", str(tmp_path))
    monkeypatch.setenv("AEAT_SECRET_STORE_BACKEND", "unsecured")
    monkeypatch.setenv("AEAT_ALLOW_UNENCRYPTED", "1")
    monkeypatch.setenv("AEAT_OUTPUT_LANGUAGE", "en")
    dispose_engine()
    try:
        yield tmp_path
    finally:
        dispose_engine()


@pytest.mark.parametrize("verb", _COLD_START_VERBS, ids=lambda v: " ".join(v))
def test_cold_start_verb_refuses_without_leaking_internals(
    verb: tuple[str, ...], _fresh_storage_root: Path
) -> None:
    """Each cold-start verb refuses without surfacing a raw config error."""

    dispose_engine()
    result = invoke_cached_cli(list(verb))

    assert result.exit_code != 0, f"{' '.join(verb)} should refuse: {result.output}"
    for marker in _LEAK_MARKERS:
        assert marker not in result.output, (
            f"{' '.join(verb)} leaked internal plumbing {marker!r}: {result.output}"
        )


@pytest.mark.parametrize("verb", _COLD_START_VERBS, ids=lambda v: " ".join(v))
def test_cold_start_verb_surfaces_profile_create_guidance(
    verb: tuple[str, ...], _fresh_storage_root: Path
) -> None:
    """Each cold-start verb names ``profile create`` so the operator can recover."""

    dispose_engine()
    result = invoke_cached_cli(list(verb))

    flat = result.output.replace("\n", " ")
    assert "profile create" in flat, (
        f"{' '.join(verb)} did not point at `profile create`: {result.output}"
    )


def test_cold_start_refusal_is_consistent_across_surfaces(_fresh_storage_root: Path) -> None:
    """``modelo work list`` and ``ledger list`` give the identical refusal text.

    The disaster-recovery testimony flagged the two surfaces disagreeing:
    ``ledger list`` gave a clean refusal while ``modelo work list`` leaked
    the raw ``aeat_database_url is empty`` error. The cold-start contract
    is that every profile-scoped surface produces the same refusal.
    """

    dispose_engine()
    modelo = invoke_cached_cli(["app", "modelo", "work", "list"])
    dispose_engine()
    ledger = invoke_cached_cli(["app", "ledger", "list"])

    assert modelo.exit_code != 0, modelo.output
    assert ledger.exit_code != 0, ledger.output
    assert modelo.output.strip() == ledger.output.strip(), (
        "cold-start refusal diverged between modelo work and ledger surfaces:\n"
        f"  modelo work list: {modelo.output!r}\n"
        f"  ledger list:      {ledger.output!r}"
    )
