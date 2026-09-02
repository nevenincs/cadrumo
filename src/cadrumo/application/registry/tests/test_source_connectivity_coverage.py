"""Focused closure projection tests for the reviewed source-connectivity census."""

from __future__ import annotations

from datetime import date

import pytest

from ....core.source_connectivity import SourceConnectivityDisposition
from ..source_connectivity import load_source_connectivity_census
from ..source_connectivity_coverage import compose_source_connectivity_coverage

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
        (modelo.id, revision.id) for modelo in registry_authority.modelos for revision in modelo.revisions.values()
    }
    assert all(limb.name == "source_connectivity" for limb in report.limbs)
    inventory = next(limb for limb in report.limbs if (limb.modelo, limb.revision) == ("100", "2025"))
    assert inventory.refusal is not None
    assert (inventory.outcome, inventory.refusal.reason) == ("refused", "unreviewed_evidence")
    assert inventory.refusal.disposition.state == "deferred"
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

    assert limb.refusal is not None
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

    limb = next(limb for limb in report.limbs if (limb.modelo, limb.revision) == ("182", "2025"))

    assert limb.refusal is not None
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
        census=census.model_copy(
            update={
                "entries": tuple(
                    terminal_inventory if entry.candidate_id == inventory.candidate_id else entry
                    for entry in census.entries
                ),
            },
        ),
        as_of=_AS_OF,
    )

    limb = next(limb for limb in report.limbs if (limb.modelo, limb.revision) == ("100", "2025"))

    assert limb.outcome == "satisfied"
    assert limb.refusal is None
    assert limb.evidence


def test_modelo_100_destination_cannot_cross_satisfy_other_revisions(
    registry_authority,
) -> None:
    """A 2025 inventory decision cannot certify earlier Renta revisions sharing its roles."""
    census = load_source_connectivity_census()
    inventory = next(entry for entry in census.entries if entry.candidate_id == "inventory.stock-valuation")
    terminal_inventory = inventory.model_copy(update={"disposition": SourceConnectivityDisposition.NOT_APPLICABLE})
    report = compose_source_connectivity_coverage(
        authority=registry_authority,
        census=census.model_copy(
            update={
                "entries": tuple(
                    terminal_inventory if entry.candidate_id == inventory.candidate_id else entry
                    for entry in census.entries
                ),
            },
        ),
        as_of=_AS_OF,
    )

    outcomes = {str(limb.revision): limb.outcome for limb in report.limbs if str(limb.modelo) == "100"}
    assert outcomes["2025"] == "satisfied"
    assert all(outcomes[revision] == "unmeasured" for revision in ("2020", "2021", "2022", "2023", "2024"))


def test_modelo_193_destination_certifies_each_explicitly_scoped_revision(
    registry_authority,
) -> None:
    """One row can satisfy only the two Modelo 193 revisions it explicitly scopes."""
    census = load_source_connectivity_census()
    gasto = next(entry for entry in census.entries if entry.candidate_id == "rows.gasto193-contributor")
    terminal_gasto = gasto.model_copy(update={"disposition": SourceConnectivityDisposition.NOT_APPLICABLE})
    entries = tuple(terminal_gasto if entry.candidate_id == gasto.candidate_id else entry for entry in census.entries)
    report = compose_source_connectivity_coverage(
        authority=registry_authority,
        census=census.model_copy(update={"entries": entries}),
        as_of=_AS_OF,
    )

    outcomes = {str(limb.revision): limb.outcome for limb in report.limbs if str(limb.modelo) == "193"}
    assert outcomes == {"2024": "satisfied", "2025-y-siguientes": "satisfied"}


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
        census=census.model_copy(
            update={
                "entries": tuple(
                    expired_terminal if entry.candidate_id == inventory.candidate_id else entry
                    for entry in census.entries
                ),
            },
        ),
        as_of=_AS_OF,
    )

    limb = next(limb for limb in report.limbs if (limb.modelo, limb.revision) == ("100", "2025"))

    assert limb.refusal is not None
    assert (limb.outcome, limb.refusal.reason) == ("refused", "stale_evidence")
    assert limb.refusal.disposition.model_dump() == {
        "limb": "source_connectivity",
        "state": "owned",
        "owner": "source-connectivity-campaign",
        "work_item": "inventory.stock-valuation:revalidate-expired-evidence",
        "reconsideration_condition": "Current source-connectivity evidence revalidates the terminal disposition.",
    }
