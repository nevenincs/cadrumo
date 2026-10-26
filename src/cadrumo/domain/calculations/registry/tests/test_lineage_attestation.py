"""Lineage evidence carriers resolve one exact member on one authored edge."""

import pytest

from ..errors import RegistryValidationError
from ..lineage_attestation import LineageAttestation, validate_lineage_attestations

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _claim() -> LineageAttestation:
    return LineageAttestation.model_validate(
        {
            "family": "casillas",
            "continuidad_id": "test-chain",
            "from_revision": "2024",
            "to_revision": "2025",
            "origin": "grounded",
            "evidence": "Official fixture, page 1",
            "legal_refs": ("ley-58-2003:art-29",),
            "source_refs": ("aeat-manual",),
        }
    )


@pytest.mark.parametrize("ambiguous_revision", ["2024", "2025"])
def test_ambiguous_attestation_target_is_refused(ambiguous_revision: str) -> None:
    members: dict[str, dict[str, tuple[str, ...]]] = {
        "2024": {"casillas": ("test-chain",)},
        "2025": {"casillas": ("test-chain",)},
    }
    members[ambiguous_revision]["casillas"] = ("test-chain", "test-chain")

    with pytest.raises(RegistryValidationError, match=rf"2 targets in .* revision {ambiguous_revision!r}"):
        validate_lineage_attestations(
            (_claim(),),
            predecessors={"2025": "2024"},
            members_by_revision=members,
        )


def test_dangling_attestation_target_is_refused() -> None:
    with pytest.raises(RegistryValidationError, match="0 targets in target revision '2025'"):
        validate_lineage_attestations(
            (_claim(),),
            predecessors={"2025": "2024"},
            members_by_revision={
                "2024": {"casillas": ("test-chain",)},
                "2025": {"casillas": ()},
            },
        )
