"""Lineage evidence carriers resolve one exact member on one authored edge."""

import pytest

from ..errors import RegistryValidationError
from ..lineage_attestation import LineageAttestation, validate_lineage_attestations
from .authored_editions import authored_revisions

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_FROM, _TO = (str(revision.id) for revision in authored_revisions("100")[-2:])


def _claim() -> LineageAttestation:
    return LineageAttestation.model_validate(
        {
            "family": "casillas",
            "continuidad_id": "test-chain",
            "from_revision": _FROM,
            "to_revision": _TO,
            "origin": "grounded",
            "evidence": "Official fixture, page 1",
            "legal_refs": ("ley-58-2003:art-29",),
            "source_refs": ("aeat-manual",),
        }
    )


@pytest.mark.parametrize("ambiguous_revision", [_FROM, _TO])
def test_ambiguous_attestation_target_is_refused(ambiguous_revision: str) -> None:
    members: dict[str, dict[str, tuple[str, ...]]] = {
        _FROM: {"casillas": ("test-chain",)},
        _TO: {"casillas": ("test-chain",)},
    }
    members[ambiguous_revision]["casillas"] = ("test-chain", "test-chain")

    with pytest.raises(RegistryValidationError, match=rf"2 targets in .* revision {ambiguous_revision!r}"):
        validate_lineage_attestations(
            (_claim(),),
            predecessors={_TO: _FROM},
            members_by_revision=members,
        )


def test_dangling_attestation_target_is_refused() -> None:
    with pytest.raises(RegistryValidationError, match=f"0 targets in target revision {_TO!r}"):
        validate_lineage_attestations(
            (_claim(),),
            predecessors={_TO: _FROM},
            members_by_revision={
                _FROM: {"casillas": ("test-chain",)},
                _TO: {"casillas": ()},
            },
        )
