from datetime import date

import pytest

from cadrumo.application.aggregation import collect_unhandled_source_diagnostics
from cadrumo.application.modelo.calculation_route import (
    CALCULATION_ROUTE_RESOLVER_OWNERSHIP,
    CALCULATION_ROUTE_SOURCE_DISPOSITIONS,
)
from cadrumo.application.registry import compose_source_connectivity_coverage
from cadrumo.application.registry.source_connectivity import load_source_connectivity_census
from cadrumo.core import BindingSourceKind
from cadrumo.core.resources import bundled_path, resources
from cadrumo.domain.calculations.registry import CasillaFieldKind, load_modelo_directory

from ..check import SourceConnectivityCheckError, check_census_governance
from ..live_proof import CONNECTED_PROOF_FIXTURES, connected_candidate_ids

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_m360_remains_measurably_ingress_blocked_until_its_missing_authority_exists() -> None:
    reopening_predicate = (
        "Reopen only when a secure owner retains the full official M360 request/document carrier: refund country/year/"
        "period, operation type, invoice/import document number/date, base, VAT quota, deductible proportion, "
        "requested amount, currency, nature (including Other description), and supplier VAT identity/name/address; "
        "every document has immutable durable identity/fingerprint; and S98 proves encrypted revision persistence/"
        "replay, diagnostics, review, and supported official repeated-record export."
    )
    entry = next(
        item for item in load_source_connectivity_census().entries if item.candidate_id == "rows.refund-operation"
    )

    assert entry.disposition.value == "ingress_blocked"
    assert entry.owner == "source-connectivity-campaign"
    assert entry.review_condition == reopening_predicate
    assert entry.expires_on == date(2026, 12, 31)
    assert entry.bounded_follow_up is not None
    assert entry.bounded_follow_up.action_id == "source-casilla.rows-refund-ingress"
    assert entry.bounded_follow_up.owner == "source-connectivity-campaign"
    assert entry.follow_up_owner() == "source-connectivity-campaign"
    assert entry.bounded_follow_up.deadline == date(2026, 11, 30)
    assert entry.bounded_follow_up.completion_criterion == (
        "Keep ingress_blocked until the review condition is satisfied: the full carrier, secure owner, immutable "
        "durable identity and fingerprint, and S98 proof must all exist before resolver enrollment or any connected "
        "claim; S99 independently reviews that evidence."
    )


def test_m360_deferred_source_has_no_connected_downstream_lifecycle() -> None:
    """Only the unowned M360 refund source stays blocked before a persistent claim can form.

    The distinct operator-entered ``manual_input`` bindings remain available;
    their presence cannot clear the deferred ``refund_operation`` lifecycle.
    """
    source_kind = BindingSourceKind.REFUND_OPERATION
    candidate_id = "rows.refund-operation"
    modelo = load_modelo_directory(bundled_path("registry", "aeat", "modelos", "360"))
    revision = modelo.revisions["2010-y-siguientes"]

    assert any(binding.source is source_kind for binding in revision.bindings)
    assert any(binding.source is BindingSourceKind.MANUAL_INPUT for binding in revision.bindings)
    assert CALCULATION_ROUTE_SOURCE_DISPOSITIONS[source_kind].value == "deferred"
    assert all(source_kind not in owner.owned_sources for owner in CALCULATION_ROUTE_RESOLVER_OWNERSHIP)

    handled_sources = frozenset(
        kind.value
        for kind, disposition in CALCULATION_ROUTE_SOURCE_DISPOSITIONS.items()
        if disposition.value == "enrolled"
    )
    diagnostics = collect_unhandled_source_diagnostics(revision, handled_sources=handled_sources)
    assert any(
        diagnostic.source_kind == source_kind.value and diagnostic.reason == "unhandled_binding_source"
        for diagnostic in diagnostics
    )

    assert candidate_id not in connected_candidate_ids()
    assert all(fixture.candidate_id != candidate_id for fixture in CONNECTED_PROOF_FIXTURES)

    census = load_source_connectivity_census()
    coverage = compose_source_connectivity_coverage(
        authority=resources().modelos.authority,
        census=census,
        as_of=date(2026, 8, 25),
    )
    limb = next(item for item in coverage.limbs if item.modelo == "360" and item.revision == "2010-y-siguientes")
    assert limb.outcome == "refused"
    assert limb.refusal is not None
    assert limb.refusal.disposition.work_item == "source-casilla.rows-refund-ingress"
    entry = next(item for item in census.entries if item.candidate_id == candidate_id)
    assert limb.refusal.disposition.reconsideration_condition == entry.review_condition

    assert all(
        record.repeat != "projection_rows"
        and all(field.kind is not CasillaFieldKind.PROJECTION for field in record.fields)
        for layout in revision.export_layouts
        for record in layout.records
    )


def test_m360_terminal_deferral_is_rejected_after_its_expiry() -> None:
    """The bounded M360 deferral cannot remain current after 2026-12-31."""
    census = load_source_connectivity_census()
    entry = next(item for item in census.entries if item.candidate_id == "rows.refund-operation")
    expired = entry.model_copy(update={"expires_on": date(2027, 1, 1)})
    expired_census = census.model_copy(
        update={"entries": tuple(expired if item is entry else item for item in census.entries)},
    )

    with pytest.raises(SourceConnectivityCheckError, match="expired without adjudication"):
        check_census_governance(expired_census, as_of=date(2027, 1, 1))
