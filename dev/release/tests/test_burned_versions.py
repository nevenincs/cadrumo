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
    read_ledger,
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


def test_the_shipped_accessor_reads_the_shipped_ledger_through_the_same_reader() -> None:
    """``burned_versions`` is ``read_ledger`` over :data:`LEDGER_PATH`, nothing else.

    The refusal cases below exercise :func:`read_ledger` against real files. That
    only guards the shipped path if the shipped accessor is that same reader over
    the shipped ledger, so the identity is asserted rather than assumed.
    """
    assert burned_versions() == read_ledger(LEDGER_PATH)


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
) -> None:
    """Each malformed shape refuses by name rather than parsing to an empty set.

    Parsing any of these to "no burns" is the silent failure this guards: the
    downstream identity check would then permit a version somebody burned.
    """
    ledger = tmp_path / "burned_versions.json"
    ledger.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(BurnedVersionLedgerError, match=fragment):
        read_ledger(ledger)


def test_a_duplicated_version_refuses(tmp_path: Path) -> None:
    """Two burns claiming one version have conflicting evidence; refuse both."""
    entry = {"version": "2.0.0", "burned_on": "2026-07-27", "reason": "y" * 50}
    ledger = tmp_path / "burned_versions.json"
    ledger.write_text(json.dumps({"burned": [entry, {**entry, "reason": "z" * 50}]}), encoding="utf-8")
    with pytest.raises(BurnedVersionLedgerError, match="more than once"):
        read_ledger(ledger)


def test_an_absent_ledger_refuses_rather_than_reading_empty(tmp_path: Path) -> None:
    """A deleted ledger must not read as "nothing is burned"."""
    with pytest.raises(BurnedVersionLedgerError, match="absent"):
        read_ledger(tmp_path / "absent.json")


def test_a_well_formed_ledger_parses_every_entry(tmp_path: Path) -> None:
    """The refusals above only mean something if the accepted shape is accepted.

    Without this control every refusal test would pass against a reader that
    rejected outright, and the parametrised cases could not distinguish a
    precise refusal from a blanket one.
    """
    ledger = tmp_path / "burned_versions.json"
    ledger.write_text(
        json.dumps(
            {
                "burned": [
                    {"version": "3.0.0", "burned_on": "2026-07-27", "reason": "q" * 50},
                    {"version": "3.1.0", "burned_on": "2026-07-28", "reason": "r" * 50},
                ]
            }
        ),
        encoding="utf-8",
    )

    entries = read_ledger(ledger)

    assert [entry.version for entry in entries] == ["3.0.0", "3.1.0"]
    assert entries[1].burned_on == date(2026, 7, 28)
