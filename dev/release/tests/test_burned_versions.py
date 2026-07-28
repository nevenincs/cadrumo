"""Proof that the burned-version ledger refuses what it promises to refuse.

The ledger's whole value is that it survives the thing that erases every other
record of exposure: deleting the published release. So these tests assert the
two seeded burns are present and readable, and -- more importantly -- that the
reader rejects the shapes that would silently empty it. A ledger that parses an
under-specified entry is worse than no ledger, because the guard downstream
would report "not burned" for a version somebody meant to burn.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from dev.release.burned_versions import (
    LEDGER_PATH,
    BurnedVersion,
    BurnedVersionLedgerError,
    burn_reason,
    burned_versions,
    is_burned,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

#: The two partial releases this project deleted rather than delivered. Pinned
#: here so removing one from the ledger fails loudly rather than quietly
#: widening the set of versions a release may mint.
_SEEDED: tuple[str, ...] = ("0.2.0", "0.2.1")


def test_both_seeded_versions_are_burned() -> None:
    """The deleted partial releases are in the ledger and stay there."""
    versions = tuple(entry.version for entry in burned_versions())
    assert versions == _SEEDED
    for version in _SEEDED:
        assert is_burned(version), f"{version} was publicly downloadable and must never be minted again"


def test_every_entry_carries_auditable_evidence() -> None:
    """A burn with no date or no reason cannot be audited, so it is not allowed."""
    for entry in burned_versions():
        assert isinstance(entry, BurnedVersion)
        assert isinstance(entry.burned_on, date)
        # The reason must explain the exposure, not merely restate the version.
        assert len(entry.reason) > 40, f"{entry.version} has no auditable reason"
        assert entry.version not in entry.reason[:20]


def test_a_version_never_published_is_not_burned() -> None:
    """The ledger is a deny-list, not a catch-all: unknown versions pass."""
    assert not is_burned("0.1.0")
    assert burn_reason("0.1.0") is None


def test_burn_reason_returns_the_recorded_evidence() -> None:
    """The identity guard names this in its refusal, so it must be real text."""
    reason = burn_reason("0.2.1")
    assert reason is not None
    assert "deleted" in reason


def test_the_shipped_ledger_file_is_where_the_reader_looks() -> None:
    """Data and reader ship together; neither is deployable without the other."""
    assert LEDGER_PATH.exists()
    assert LEDGER_PATH.parent == Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    ("payload", "fragment"),
    [
        pytest.param({"burned": [{"burned_on": "2026-07-27", "reason": "x" * 50}]}, "missing", id="no-version"),
        pytest.param({"burned": [{"version": "1.0.0", "reason": "x" * 50}]}, "missing", id="no-date"),
        pytest.param({"burned": [{"version": "1.0.0", "burned_on": "2026-07-27"}]}, "missing", id="no-reason"),
        pytest.param(
            {"burned": [{"version": " ", "burned_on": "2026-07-27", "reason": "x" * 50}]},
            "empty version",
            id="blank-version",
        ),
        pytest.param(
            {"burned": [{"version": "1.0.0", "burned_on": "not-a-date", "reason": "x" * 50}]},
            "burned_on",
            id="unparseable-date",
        ),
        pytest.param({"burned": ["1.0.0"]}, "not an object", id="bare-string-entry"),
        pytest.param({"versions": []}, "'burned' list", id="wrong-top-level-key"),
    ],
)
def test_reader_refuses_every_under_specified_shape(
    payload: dict[str, object],
    fragment: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Each malformed shape refuses by name rather than parsing to an empty set.

    Parsing any of these to "no burns" is the silent failure this guards: the
    downstream identity check would then permit a version somebody burned.
    """
    ledger = tmp_path / "burned_versions.json"
    ledger.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr("dev.release.burned_versions.LEDGER_PATH", ledger)
    burned_versions.cache_clear()
    with pytest.raises(BurnedVersionLedgerError, match=fragment):
        burned_versions()
    burned_versions.cache_clear()


def test_a_duplicated_version_refuses(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Two burns claiming one version have conflicting evidence; refuse both."""
    entry = {"version": "2.0.0", "burned_on": "2026-07-27", "reason": "y" * 50}
    ledger = tmp_path / "burned_versions.json"
    ledger.write_text(json.dumps({"burned": [entry, {**entry, "reason": "z" * 50}]}), encoding="utf-8")
    monkeypatch.setattr("dev.release.burned_versions.LEDGER_PATH", ledger)
    burned_versions.cache_clear()
    with pytest.raises(BurnedVersionLedgerError, match="more than once"):
        burned_versions()
    burned_versions.cache_clear()


def test_an_absent_ledger_refuses_rather_than_reading_empty(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A deleted ledger must not read as "nothing is burned"."""
    monkeypatch.setattr("dev.release.burned_versions.LEDGER_PATH", tmp_path / "absent.json")
    burned_versions.cache_clear()
    with pytest.raises(BurnedVersionLedgerError, match="absent"):
        burned_versions()
    burned_versions.cache_clear()
