"""Focused closure projection tests for the reviewed source-connectivity census."""

from __future__ import annotations

from datetime import date

import pytest

from ....core import SourceConnectivityDisposition
from .. import compose_source_connectivity_coverage, load_source_connectivity_census

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_AS_OF = date(2026, 8, 24)


def test_source_connectivity_coverage_retains_every_revision_and_live_census_refusal(
    registry_authority,
) -> None:
    """Keep the complete registry denominator while retaining current census gaps."""
    report = compose_source_connectivity_coverage(
        authority=registry_authority,
        census=load_source_connectivity_census(),
        as_of=_AS_OF,
    )

    assert {(limb.modelo, limb.revision) for limb in report.limbs} == {
        (modelo.id, revision.id)
        for modelo in registry_authority.modelos
        for revision in modelo.revisions.values()
    }
    assert all(limb.name == "source_connectivity" for limb in report.limbs)
    inventory = next(limb for limb in report.limbs if (limb.modelo, limb.revision) == ("100", "2025"))
    assert (inventory.outcome, inventory.refusal.reason) == ("refused", "unreviewed_evidence")
    assert inventory.refusal.disposition.work_item == "source-casilla.inventory-grounding"


def test_source_connectivity_coverage_refuses_a_revision_without_scoped_census_evidence(
    registry_authority,
) -> None:
    """Do not turn census absence into an unsupported clean-source claim."""
    report = compose_source_connectivity_coverage(
        authority=registry_authority,
        census=load_source_connectivity_census(),
        as_of=_AS_OF,
    )

    limb = next(limb for limb in report.limbs if (limb.modelo, limb.revision) == ("303", "2025"))

    assert (limb.outcome, limb.refusal.reason) == ("unmeasured", "unmeasured")
    assert limb.refusal.disposition.work_item == "source-domain-to-casilla-connectivity:scope"


def test_source_connectivity_coverage_refuses_an_expired_blocking_row(
    registry_authority,
) -> None:
    """An expired bounded disposition cannot remain current closure evidence."""
    report = compose_source_connectivity_coverage(
        authority=registry_authority,
        census=load_source_connectivity_census(),
        as_of=date(2027, 1, 1),
    )

    limb = next(limb for limb in report.limbs if (limb.modelo, limb.revision) == ("182", "2007-y-siguientes"))

    assert (limb.outcome, limb.refusal.reason) == ("refused", "stale_evidence")
    assert limb.refusal.disposition.work_item == "source-casilla.rows-donativo-ingress"


def test_source_connectivity_coverage_accepts_current_terminal_census_evidence(
    registry_authority,
) -> None:
    """A reviewed terminal disposition supplies source-limb evidence without a second authority."""
    census = load_source_connectivity_census()
    inventory = next(entry for entry in census.entries if entry.candidate_id == "inventory.stock-valuation")
    terminal_inventory = inventory.model_copy(update={"disposition": SourceConnectivityDisposition.NOT_APPLICABLE})
    report = compose_source_connectivity_coverage(
        authority=registry_authority,
        census=census.model_copy(update={"entries": (terminal_inventory, *census.entries[1:])}),
        as_of=_AS_OF,
    )

    limb = next(limb for limb in report.limbs if (limb.modelo, limb.revision) == ("100", "2025"))

    assert limb.outcome == "satisfied"
    assert limb.refusal is None
    assert limb.evidence


def test_source_connectivity_coverage_refuses_expired_terminal_evidence_without_follow_up(
    registry_authority,
) -> None:
    """Expiry invalidates a terminal claim even when it had no open action."""
    census = load_source_connectivity_census()
    inventory = next(entry for entry in census.entries if entry.candidate_id == "inventory.stock-valuation")
    expired_terminal = inventory.model_copy(
        update={
            "disposition": SourceConnectivityDisposition.NOT_APPLICABLE,
            "expires_on": _AS_OF,
            "review_condition": None,
            "bounded_follow_up": None,
        },
    )
    report = compose_source_connectivity_coverage(
        authority=registry_authority,
        census=census.model_copy(update={"entries": (expired_terminal, *census.entries[1:])}),
        as_of=_AS_OF,
    )

    limb = next(limb for limb in report.limbs if (limb.modelo, limb.revision) == ("100", "2025"))

    assert (limb.outcome, limb.refusal.reason) == ("refused", "stale_evidence")
    assert limb.refusal.disposition.model_dump() == {
        "limb": "source_connectivity",
        "state": "owned",
        "owner": "source-connectivity-campaign",
        "work_item": "inventory.stock-valuation:revalidate-expired-evidence",
        "reconsideration_condition": "Current source-connectivity evidence revalidates the terminal disposition.",
    }
