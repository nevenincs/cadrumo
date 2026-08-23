"""Mutation-shaped proofs for every source-connectivity ratchet failure."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from cadrumo.application.registry.source_connectivity import (
    SourceConnectivityCensusEntry,
    load_source_connectivity_census,
)
from cadrumo.core import SourceConnectivityDisposition

from ..check import SourceConnectivityCheckError, check_capability_locators, check_census_governance
from ..discovery import (
    assign_capabilities_to_census,
    discovered_source_capability_evidence,
    discovered_source_capability_ids,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def live_capability_ids() -> tuple[str, ...]:
    return discovered_source_capability_ids(REPO_ROOT)


@pytest.fixture(scope="module")
def live_capability_evidence() -> dict[str, str]:
    return discovered_source_capability_evidence(REPO_ROOT)


def test_external_new_capability_is_rejected(live_capability_ids: tuple[str, ...]) -> None:
    manifest = load_source_connectivity_census()
    mutation = "calculation_helper:src/cadrumo/domain/external_probe.py:calculate_probe"

    with pytest.raises(ValueError, match="capability coverage drift"):
        assign_capabilities_to_census((*live_capability_ids, mutation), manifest)


def test_external_capability_disappearance_is_rejected(live_capability_ids: tuple[str, ...]) -> None:
    manifest = load_source_connectivity_census()
    removed = manifest.entries[0].capability_ids[0]

    with pytest.raises(ValueError, match="claims undiscovered capabilities"):
        assign_capabilities_to_census(
            tuple(capability_id for capability_id in live_capability_ids if capability_id != removed),
            manifest,
        )


def test_expired_blocked_row_is_rejected() -> None:
    manifest = load_source_connectivity_census()
    blocked = next(
        row for row in manifest.entries if row.disposition is SourceConnectivityDisposition.GROUNDING_BLOCKED
    )
    expired = blocked.model_copy(update={"expires_on": date(2026, 8, 23)})
    mutation = manifest.model_copy(
        update={"entries": tuple(expired if row is blocked else row for row in manifest.entries)}
    )

    with pytest.raises(SourceConnectivityCheckError, match="expired without adjudication"):
        check_census_governance(mutation, as_of=date(2026, 8, 23))


def test_unresolved_row_without_bounded_follow_up_is_rejected() -> None:
    manifest = load_source_connectivity_census()
    candidate = next(
        row for row in manifest.entries if row.disposition is SourceConnectivityDisposition.CONNECT_CANDIDATE
    )
    unactioned = candidate.model_copy(update={"bounded_follow_up": None})
    mutation = manifest.model_copy(
        update={"entries": tuple(unactioned if row is candidate else row for row in manifest.entries)}
    )

    with pytest.raises(SourceConnectivityCheckError, match="lacks owned bounded follow-up"):
        check_census_governance(mutation, as_of=date(2026, 8, 23))


def test_unsupported_connected_claim_is_rejected_without_live_proof() -> None:
    candidate = load_source_connectivity_census().entries[0]
    mutation = candidate.model_dump()
    mutation.update(
        disposition=SourceConnectivityDisposition.CONNECTED,
        review_condition=None,
        bounded_follow_up=None,
        connected_proof=None,
    )

    with pytest.raises(ValidationError, match="requires complete connected_proof"):
        SourceConnectivityCensusEntry.model_validate(mutation)


def test_missing_capability_locator_line_is_rejected(
    live_capability_evidence: dict[str, str],
) -> None:
    manifest = load_source_connectivity_census()
    first = manifest.entries[0]
    stale = first.model_copy(
        update={"capability_locators": ("src/cadrumo/adapters/persistence/profile/inventory.py:999999",)}
    )
    mutation = manifest.model_copy(update={"entries": (stale, *manifest.entries[1:])})

    with pytest.raises(SourceConnectivityCheckError, match="locator line is absent"):
        check_capability_locators(
            REPO_ROOT,
            mutation,
            capability_evidence=live_capability_evidence,
        )


def test_capability_locator_correspondence_drift_is_rejected(
    live_capability_evidence: dict[str, str],
) -> None:
    manifest = load_source_connectivity_census()
    first = manifest.entries[0]
    stale = first.model_copy(update={"capability_locators": first.capability_locators[1:]})
    mutation = manifest.model_copy(update={"entries": (stale, *manifest.entries[1:])})

    with pytest.raises(SourceConnectivityCheckError, match="capability locator drift"):
        check_capability_locators(
            REPO_ROOT,
            mutation,
            capability_evidence=live_capability_evidence,
        )
