"""Post-roundtrip snapshot-vs-evidence coverage validator.

``assert_revision_snapshot_evidence_coverage`` cross-checks that a loaded
revision's ``ledger_filing_snapshot.rows`` and ``ledger_filing_evidence.rows``
cover the same contributor set. A deliberate mismatch (a contributor present in
the fingerprint snapshot but dropped from the evidence) must raise a typed
:class:`LedgerFilingCoverageError` that names the missing contributor.
"""

from __future__ import annotations

import pytest

from ....core.errors.error_codes import resolve_error_message
from ..calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    assert_revision_snapshot_evidence_coverage,
    derive_calculation_revision_id,
)
from ..errors import LedgerFilingCoverageError
from .snapshot_evidence_coverage_support import (
    CAPTURED_AT,
    EVIDENCE_INPUT_CASILLA,
    REGISTRY_SNAPSHOT_REF,
    TX_A,
    TX_B,
    hex_seed,
    ledger_filing_revision,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_matching_coverage_passes() -> None:
    """A revision whose snapshot and evidence cover the same contributors passes."""
    revision = ledger_filing_revision(snapshot_ids=(TX_A, TX_B), evidence_ids=(TX_A, TX_B))
    assert_revision_snapshot_evidence_coverage(revision)  # does not raise


def test_missing_contributor_in_evidence_raises_naming_it() -> None:
    """A contributor in the fingerprint snapshot but absent from evidence raises."""
    revision = ledger_filing_revision(snapshot_ids=(TX_A, TX_B), evidence_ids=(TX_A,))
    with pytest.raises(LedgerFilingCoverageError) as raised:
        assert_revision_snapshot_evidence_coverage(revision)
    assert TX_B in str(raised.value)
    assert "missing_from_evidence" in str(raised.value)


def test_extra_contributor_in_evidence_raises_naming_it() -> None:
    """A contributor in evidence but absent from the fingerprint snapshot raises."""
    revision = ledger_filing_revision(snapshot_ids=(TX_A,), evidence_ids=(TX_A, TX_B))
    with pytest.raises(LedgerFilingCoverageError) as raised:
        assert_revision_snapshot_evidence_coverage(revision)
    assert TX_B in str(raised.value)
    assert "extra_in_evidence" in str(raised.value)


def test_non_ledger_revision_passes_trivially() -> None:
    """A revision with neither snapshot nor evidence passes the coverage gate."""
    work_unit_id = hex_seed("9")
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit_id,
        input_values_by_casilla_id={EVIDENCE_INPUT_CASILLA: "1"},
        binding_overrides={},
        casilla_values={},
        source_transaction_ids=(),
        filing_instance_evidence=None,
        source_provenance=(),
    )
    revision = CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=work_unit_id,
        registry_snapshot_ref=REGISTRY_SNAPSHOT_REF,
        state=CalculationRevisionState.BORRADOR,
        input_values_by_casilla_id={EVIDENCE_INPUT_CASILLA: "1"},
        created_at=CAPTURED_AT,
        updated_at=CAPTURED_AT,
        filing_instance_evidence=None,
        source_provenance=(),
    )
    assert_revision_snapshot_evidence_coverage(revision)  # does not raise


def test_the_coverage_refusal_is_catalogue_words_naming_the_revision_and_the_counts() -> None:
    revision = ledger_filing_revision(snapshot_ids=(TX_A, TX_B), evidence_ids=(TX_A,))

    with pytest.raises(LedgerFilingCoverageError) as raised:
        assert_revision_snapshot_evidence_coverage(revision)

    key = "errors.integrity.ledger_filing_evidence_diverges_from_snapshot"
    assert raised.value.translated_message == key
    for locale in ("en", "es", "ca", "hu"):
        words = resolve_error_message(raised.value, locale=locale)
        assert words != key
        assert "%{" not in words
        assert revision.calculation_revision_id in words
