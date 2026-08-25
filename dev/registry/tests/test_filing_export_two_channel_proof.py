"""Dynamic refusal coverage for the two-channel filing-export proof port."""

from __future__ import annotations

from inspect import signature
from pathlib import Path
from typing import Any, cast

import pytest

from cadrumo.application.filing import FilingExportProofChannel, FilingExportProofCoordinate
from cadrumo.core import RegistryAuthorityGrade
from cadrumo.core.resources import bundled_path
from cadrumo.domain.calculations.registry import (
    bundled_authority,
)

from ..filing_export_proof import canonical_two_channel_filing_export_proof_authority

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def test_canonical_authority_cannot_accept_a_preconstructed_replay_receipt() -> None:
    """Replay success must execute source and custody ports, not trust a model."""
    parameters = signature(canonical_two_channel_filing_export_proof_authority).parameters

    assert "secure_replay_receipts" not in parameters
    assert {"secure_replay_source", "secure_replay_custody"} <= set(parameters)

    with pytest.raises(TypeError, match="secure_replay_receipts"):
        cast(Any, canonical_two_channel_filing_export_proof_authority)(
            workspace_root=_REPOSITORY_ROOT,
            registry_root=bundled_path("registry", "aeat"),
            source_root=bundled_path(),
            authority=bundled_authority(),
            secure_replay_source=None,
            secure_replay_custody=None,
            secure_replay_receipts=(object(),),
        )


def test_every_selected_filing_revision_refuses_each_unenrolled_proof_channel() -> None:
    """Each filing revision refuses both proof channels until evidence is enrolled."""
    registry = bundled_authority()
    proof = canonical_two_channel_filing_export_proof_authority(
        workspace_root=_REPOSITORY_ROOT,
        registry_root=bundled_path("registry", "aeat"),
        source_root=bundled_path(),
        authority=registry,
        secure_replay_source=None,
        secure_replay_custody=None,
    )
    assessed = 0
    for modelo in registry.modelos:
        for revision in modelo.revisions.values():
            if revision.authority_grade is not RegistryAuthorityGrade.FILING:
                continue
            coordinate = FilingExportProofCoordinate(
                modelo=modelo.id,
                revision=revision.id,
                layout_ids=tuple(layout.id for layout in revision.export_layouts),
            )
            assessment = proof.assess_for(coordinate)
            assert assessment.proof is None
            assert {item.channel for item in assessment.refusals} == {
                FilingExportProofChannel.CONFORMANCE,
                FilingExportProofChannel.SECURE_REPLAY,
            }
            assessed += 1
    assert assessed > 0
