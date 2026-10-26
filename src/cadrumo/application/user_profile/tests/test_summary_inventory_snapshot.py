"""One read-only command observes the profile listing once; nothing outlives the command."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pytest

from .. import profile_summary
from ..custody_ports import ProfileCustodyConcurrentChangeError, ProfileCustodyRecordIntegrityError
from ..profile_summary import summary_inventory, summary_inventory_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@dataclass
class _CountingCustody:
    """A custody port stand-in that records each listing observation."""

    failures: list[Exception] = field(default_factory=list)
    observed: list[Path] = field(default_factory=list)

    def list_committed_capsule_summaries(self, *, root: Path) -> tuple[()]:
        self.observed.append(root)
        if self.failures:
            raise self.failures.pop(0)
        return ()


@pytest.fixture
def custody(monkeypatch: pytest.MonkeyPatch) -> _CountingCustody:
    port = _CountingCustody()
    monkeypatch.setattr(profile_summary, "profile_custody_port", lambda: port)
    return port


def test_every_ask_inside_one_scope_shares_one_observation(tmp_path: Path, custody: _CountingCustody) -> None:
    with summary_inventory_snapshot():
        answers = [summary_inventory(root=tmp_path) for _ in range(4)]

    assert custody.observed == [tmp_path]
    assert all(answer is answers[0] for answer in answers)
    assert answers[0].recognized


def test_nothing_is_reused_outside_a_scope_or_across_scopes(tmp_path: Path, custody: _CountingCustody) -> None:
    """STALE KEY: the listing belongs to other processes too, so each command observes it afresh."""
    summary_inventory(root=tmp_path)
    summary_inventory(root=tmp_path)
    with summary_inventory_snapshot():
        summary_inventory(root=tmp_path)
    with summary_inventory_snapshot():
        summary_inventory(root=tmp_path)

    assert len(custody.observed) == 4


def test_a_nested_scope_shares_the_outer_observation(tmp_path: Path, custody: _CountingCustody) -> None:
    with summary_inventory_snapshot():
        summary_inventory(root=tmp_path)
        with summary_inventory_snapshot():
            summary_inventory(root=tmp_path)
        summary_inventory(root=tmp_path)

    assert custody.observed == [tmp_path]


def test_each_root_is_observed_on_its_own(tmp_path: Path, custody: _CountingCustody) -> None:
    other = tmp_path / "other"
    with summary_inventory_snapshot():
        summary_inventory(root=tmp_path)
        summary_inventory(root=other)
        summary_inventory(root=tmp_path)

    assert custody.observed == [tmp_path, other]


@pytest.mark.parametrize(
    "failure",
    [ProfileCustodyConcurrentChangeError("moved"), ProfileCustodyRecordIntegrityError("damaged")],
    ids=["concurrent-change", "degraded"],
)
def test_an_untrustworthy_observation_is_never_reused(
    tmp_path: Path,
    custody: _CountingCustody,
    failure: Exception,
) -> None:
    """A retry inside the command must look at the store again, not repeat the refusal."""
    custody.failures.append(failure)
    with summary_inventory_snapshot():
        first = summary_inventory(root=tmp_path)
        second = summary_inventory(root=tmp_path)

    assert not first.recognized
    assert second.recognized
    assert len(custody.observed) == 2
