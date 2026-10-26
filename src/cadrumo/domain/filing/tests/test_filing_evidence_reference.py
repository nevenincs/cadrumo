"""Canonical ownership and nominality of filing evidence references."""

from __future__ import annotations

from importlib.util import find_spec

import pytest
from pydantic import ValidationError

from ... import filing
from ...filing_evidence import FilingEvidenceReference
from ...modelos.calculation_revision_m303_evidence import M303Exonerado390FilingEvidence

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_filing_evidence_reference_has_one_canonical_owner_and_no_root_forwarder() -> None:
    assert FilingEvidenceReference.__module__ == "cadrumo.domain.filing_evidence"
    assert find_spec("cadrumo.domain._filing_evidence_reference") is None
    assert not hasattr(filing, "FilingEvidenceReference")


def test_filing_evidence_reference_is_nominal_at_filing_fact_boundary() -> None:
    with pytest.raises(ValidationError, match="applicability_reference"):
        M303Exonerado390FilingEvidence.model_validate(
            {
                "applicable": False,
                "applicability_reference": "raw-string-is-not-a-reference",
            },
        )
