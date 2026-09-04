"""Tests for the all-extras lane's claim list and argument contract.

`dev.quality.module_test_reach` listed `dev/packaging/all_extra_smoke.py` as
unreached. The lane installs the aggregate optional extras into a stdlib venv
and drives the installed console script; that is what the packaging-smoke
workflow runs on every OS leg, and reproducing it here would prove nothing the
live legs do not.

What had no coverage is the part deciding what the run CLAIMS. The smoke
manifest refuses a declared claim whose assertion never ran, so the claim list
and the lane body are one contract - and this lane's distinguishing claim is the
capability-gated optional imports, which is the whole reason it exists apart
from the core lane. That coupling was reachable only by building a wheel, a venv
and every extra.
"""

from __future__ import annotations

import pathlib

import pytest

from ..all_extra_smoke import build_parser, declared_claims

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_EXPORT_CLAIM = "frozen dependency exports"


def test_the_export_claim_is_dropped_when_the_checks_are_skipped() -> None:
    """Leaving the claim while skipping the work is what the manifest refuses."""
    assert _EXPORT_CLAIM not in declared_claims(skip_export_checks=True)


def test_the_export_claim_is_present_when_the_checks_run() -> None:
    """A proof that ran must be claimed, or the evidence goes unrecorded."""
    assert _EXPORT_CLAIM in declared_claims(skip_export_checks=False)


def test_skipping_drops_exactly_one_claim() -> None:
    """Skipping one check must not quietly drop another's evidence."""
    full = declared_claims(skip_export_checks=False)
    reduced = declared_claims(skip_export_checks=True)

    assert set(full) - set(reduced) == {_EXPORT_CLAIM}


def test_the_lane_claims_the_optional_imports_that_distinguish_it() -> None:
    """This lane exists to install the aggregate extras, not merely a wheel.

    Named rather than counted: a count would survive the claim being replaced
    by another, and the optional-import proof is the only thing separating this
    lane from the core one.
    """
    assert "all capability-gated optional imports" in declared_claims(skip_export_checks=False)


def test_every_claim_is_distinct_and_non_empty() -> None:
    """The manifest matches claims by exact text, so a duplicate masks a gap.

    Two identical claims are satisfied by one recorded proof, letting a lane
    declare work it never did.
    """
    claims = declared_claims(skip_export_checks=False)

    assert all(claim.strip() for claim in claims)
    assert len(set(claims)) == len(claims)


def test_the_cohort_directory_is_required() -> None:
    """The lane proves one immutable cohort; defaulting it would prove another."""
    with pytest.raises(SystemExit):
        build_parser().parse_args([])


def test_the_cohort_directory_is_parsed_as_a_path() -> None:
    """It is resolved and joined downstream, where a string would not behave."""
    parsed = build_parser().parse_args(["--cohort-dir", "cohort"])

    assert isinstance(parsed.cohort_dir, pathlib.Path)


def test_the_export_checks_run_unless_asked_otherwise() -> None:
    """Skipping is opt-in; a lane skipping by default would prove less in silence."""
    assert build_parser().parse_args(["--cohort-dir", "c"]).skip_export_checks is False
    assert build_parser().parse_args(["--cohort-dir", "c", "--skip-export-checks"]).skip_export_checks is True
