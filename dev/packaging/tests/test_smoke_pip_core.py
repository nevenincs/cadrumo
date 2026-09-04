"""Tests for the pip-core lane's claim list and argument contract.

`dev.quality.module_test_reach` listed `dev/packaging/smoke_pip_core.py` as
unreached. The lane itself builds a stdlib venv and installs a digest-pinned
cohort into it, which is what the packaging-smoke workflow runs; reproducing
that here would prove nothing the live lane does not.

What had no coverage is the part that decides what the run CLAIMS. The smoke
manifest refuses a declared claim whose assertion never ran, so the claim list
and the lane body are one contract: skipping the export checks must drop their
claim, or the run dies with a ProofContractError naming it. That coupling was
buried inside ``main`` and could only be exercised by building a wheel.
"""

from __future__ import annotations

import pathlib

import pytest

from ..smoke_pip_core import build_parser, declared_claims

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_EXPORT_CLAIM = "frozen dependency exports"


def test_the_export_claim_is_dropped_when_the_checks_are_skipped() -> None:
    """The coupling the manifest enforces, asserted directly.

    Leaving the claim in while skipping the work is exactly what
    ``ProofContractError`` exists to catch - a claim with no assertion behind
    it - so this is the contract, not a formatting detail.
    """
    assert _EXPORT_CLAIM not in declared_claims(skip_export_checks=True)


def test_the_export_claim_is_present_when_the_checks_run() -> None:
    """The other direction: a proof that ran must be claimed, or it is unrecorded."""
    assert _EXPORT_CLAIM in declared_claims(skip_export_checks=False)


def test_skipping_drops_exactly_one_claim() -> None:
    """Skipping one check must not quietly drop another lane's evidence."""
    full = declared_claims(skip_export_checks=False)
    reduced = declared_claims(skip_export_checks=True)

    assert set(full) - set(reduced) == {_EXPORT_CLAIM}
    assert len(full) - len(reduced) == 1


def test_every_claim_is_a_distinct_non_empty_sentence() -> None:
    """The manifest matches claims by exact text, so a duplicate masks a gap.

    Two identical claims are satisfied by one recorded proof, which would let a
    lane declare work it never did.
    """
    claims = declared_claims(skip_export_checks=False)

    assert all(claim.strip() for claim in claims)
    assert len(set(claims)) == len(claims)


def test_the_cohort_directory_is_required() -> None:
    """The lane proves a specific immutable cohort; defaulting it would prove another."""
    with pytest.raises(SystemExit):
        build_parser().parse_args([])


def test_the_cohort_directory_is_parsed_as_a_path() -> None:
    """It is joined and resolved downstream, where a string would not behave."""
    parsed = build_parser().parse_args(["--cohort-dir", "cohort"])

    assert isinstance(parsed.cohort_dir, pathlib.Path)


def test_the_export_checks_run_unless_asked_otherwise() -> None:
    """Skipping is opt-in: a lane that skipped by default would prove less silently."""
    assert build_parser().parse_args(["--cohort-dir", "cohort"]).skip_export_checks is False
    assert build_parser().parse_args(["--cohort-dir", "cohort", "--skip-export-checks"]).skip_export_checks is True


def test_the_interpreter_default_matches_the_running_one() -> None:
    """The venv is created for this major.minor, so a stale literal would drift.

    Asserted against the live interpreter rather than a pinned string, which is
    what keeps it true when the project moves version.
    """
    import sys

    parsed = build_parser().parse_args(["--cohort-dir", "cohort"])

    assert parsed.python == f"{sys.version_info.major}.{sys.version_info.minor}"
