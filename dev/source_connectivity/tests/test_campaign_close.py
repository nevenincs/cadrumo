"""Final non-vacuous closure gate for the reviewed connectivity census."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from cadrumo.core.source_connectivity import (
    SourceConnectivityDisposition,
    SourceConnectivityExpiryPosture,
)

from ..check import check_capability_census
from ..discovery import discovered_source_capability_ids
from ..live_proof import (
    CONNECTED_PROOF_FIXTURES,
    canonical_live_connected_proof_authority,
    connected_candidate_ids,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_final_census_has_no_expired_disappearance_or_unsupported_connection() -> None:
    """Compose every closure authority over the exact reviewed campaign snapshot."""
    as_of = date.today()
    connected_ids = connected_candidate_ids()
    fixture_ids = tuple(sorted(fixture.candidate_id for fixture in CONNECTED_PROOF_FIXTURES))

    # The fixture catalogue is independent of census.toml. Exact equality prevents
    # a zero-connected census from turning this live-proof gate into a silent no-op.
    assert connected_ids == fixture_ids

    with canonical_live_connected_proof_authority(REPO_ROOT) as proof_authority:
        assert (proof_authority is not None) is bool(connected_ids)
        result = check_capability_census(
            REPO_ROOT,
            as_of=as_of,
            proof_authority=proof_authority,
        )

    discovered = discovered_source_capability_ids(REPO_ROOT)
    assigned = tuple(capability_id for _, capability_ids in result.assignments for capability_id in capability_ids)

    assert result.assignment_count == result.capability_count
    assert len(assigned) == len(set(assigned))
    assert set(assigned) == set(discovered)
    assert all(
        row.expiry_posture(as_of=as_of) is not SourceConnectivityExpiryPosture.EXPIRED
        for row in result.manifest.entries
    )
    assert (
        tuple(
            sorted(
                row.candidate_id
                for row in result.manifest.entries
                if row.disposition is SourceConnectivityDisposition.CONNECTED
            )
        )
        == connected_ids
    )
