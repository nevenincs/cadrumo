"""RET-R9 public correction/readback acceptance audit."""

from __future__ import annotations

import pytest

from ..public_correction_history import (
    LIMITATION_CODE,
    SCENARIO_VERSION,
    inspect_resident_professional_correction_capability,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_public_cli_correction_exposes_an_actionable_baseline_and_immediate_lineage() -> None:
    """Prove the new readback contract without overstating its coverage.

    The live public command graph proves that a resident-professional append
    route and its evidence request declare replace fields.  The aggregate
    result now supplies the baseline and immediate generation lineage needed
    for the next replacement; this test does not create a filing or annual
    projection, nor does it prove a fresh-process history walk.
    """
    evidence = inspect_resident_professional_correction_capability()

    assert evidence.scenario == SCENARIO_VERSION
    assert evidence.slice_id == "professional-111-q2-partial-payments"
    assert evidence.modelo == "111"
    assert evidence.evidence_level == "public_cli_contract"
    assert evidence.outcome == "partial"
    assert evidence.append_transport_available is True
    assert evidence.replace_transport_declared is True
    assert evidence.public_baseline_read_available is True
    assert evidence.immediate_generation_lineage_available is True
    assert evidence.full_generation_history_available is False
    assert evidence.fresh_process_readback_proven is False
    assert evidence.effective_annual_projection_read_available is False
    assert evidence.local_filing_or_export == "not_exercised"
    assert evidence.aeat_confirmation == "not_claimed"
    assert evidence.limitation_code == LIMITATION_CODE
