"""Ownership and addressing for stale-filing findings.

The bucket filter is the assertion that matters. The calculation-revision
catalogue is not bucket-scoped, so ownership is established only by joining to
the work unit — and a join that forgets to compare buckets shows one profile
another profile's filings. That is a disclosure, not a display bug, and it was
decided inside a CLI verb where nothing tested it.

The detector itself (`stale_filed_revisions`) is pure and covered by its own
suite; these tests cover the scoping and addressing this module adds.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

import pytest

from ....domain.transactions.models import TransactionCatalogue
from ..stale_filing_query import LedgerStaleFilingV1, read_stale_ledger_filings

if TYPE_CHECKING:
    from collections.abc import Mapping

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET = "44444444-4444-4444-8444-444444444444"
_OTHER_BUCKET = "55555555-5555-4555-8555-555555555555"


class _Period:
    def __init__(self, token: str) -> None:
        self.registry_token = token


class _WorkUnit:
    def __init__(self, *, bucket_id: str) -> None:
        self.bucket_id = bucket_id
        self.modelo = "303"
        self.filing_year = 2024
        self.period = _Period("1T")


class _WorkUnits:
    """Only the lookup the query uses; the real catalogue is far larger."""

    def __init__(self, units: Mapping[str, _WorkUnit]) -> None:
        self._units = units

    def get(self, work_unit_id: str) -> _WorkUnit | None:
        return self._units.get(work_unit_id)


class _Verdict:
    def __init__(self, *, changed: tuple[str, ...], removed: tuple[str, ...]) -> None:
        self.changed = changed
        self.removed = removed


class _Revision:
    def __init__(self, *, revision_id: str, work_unit_id: str) -> None:
        self.calculation_revision_id = revision_id
        self.work_unit_id = work_unit_id


def _detector(findings: tuple[tuple[_Revision, _Verdict], ...]) -> Callable[..., tuple[tuple[Any, Any], ...]]:
    """Supply a fixed staleness verdict through the injectable boundary.

    The staleness decision has its own suite; reproducing a drifted snapshot
    here would test that instead of the ownership join this module owns. It is
    injected rather than patched because a patch mutates a production module.
    """

    def _fixed(*, revisions: object, catalogue: object) -> tuple[tuple[Any, Any], ...]:
        del revisions, catalogue
        return findings

    return _fixed


def test_a_drifted_filing_owned_by_this_bucket_is_reported() -> None:
    """The baseline: an owned, drifted revision surfaces with its address."""
    revision = _Revision(revision_id="rev-1", work_unit_id="wu-1")

    findings = read_stale_ledger_filings(
        bucket_id=_BUCKET,
        revisions={},
        work_units=_WorkUnits({"wu-1": _WorkUnit(bucket_id=_BUCKET)}),
        transactions=TransactionCatalogue(),
        detector=_detector(((revision, _Verdict(changed=("a",), removed=())),)),
    )

    assert findings == (
        LedgerStaleFilingV1(
            modelo="303",
            filing_year=2024,
            period="1T",
            calculation_revision_id="rev-1",
            work_unit_id="wu-1",
            changed_count=1,
            removed_count=0,
        ),
    )


def test_a_filing_owned_by_another_bucket_is_excluded() -> None:
    """The disclosure case: another profile's filing must never be reported."""
    revision = _Revision(revision_id="rev-1", work_unit_id="wu-1")

    findings = read_stale_ledger_filings(
        bucket_id=_BUCKET,
        revisions={},
        work_units=_WorkUnits({"wu-1": _WorkUnit(bucket_id=_OTHER_BUCKET)}),
        transactions=TransactionCatalogue(),
        detector=_detector(((revision, _Verdict(changed=("a",), removed=())),)),
    )

    assert findings == ()


def test_a_revision_whose_work_unit_is_missing_is_excluded() -> None:
    """Ownership cannot be established without the join, so it is not assumed."""
    revision = _Revision(revision_id="rev-1", work_unit_id="wu-missing")

    findings = read_stale_ledger_filings(
        bucket_id=_BUCKET,
        revisions={},
        work_units=_WorkUnits({}),
        transactions=TransactionCatalogue(),
        detector=_detector(((revision, _Verdict(changed=("a",), removed=())),)),
    )

    assert findings == ()


def test_changed_and_removed_counts_are_carried_separately() -> None:
    """A row that changed and one that vanished are different operator problems."""
    revision = _Revision(revision_id="rev-1", work_unit_id="wu-1")

    findings = read_stale_ledger_filings(
        bucket_id=_BUCKET,
        revisions={},
        work_units=_WorkUnits({"wu-1": _WorkUnit(bucket_id=_BUCKET)}),
        transactions=TransactionCatalogue(),
        detector=_detector(((revision, _Verdict(changed=("a", "b"), removed=("c",))),)),
    )

    assert findings[0].changed_count == 2
    assert findings[0].removed_count == 1


def test_no_drift_reports_nothing() -> None:
    """An empty result is the ordinary state, not an absent read."""

    findings = read_stale_ledger_filings(
        bucket_id=_BUCKET,
        revisions={},
        work_units=_WorkUnits({}),
        transactions=TransactionCatalogue(),
        detector=_detector(()),
    )

    assert findings == ()
