"""Contract tests for fail-closed per-revision registry closure records."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ....tests.aeat_literal_fixtures import aeat_url
from .. import (
    RegistryClosureEvidence,
    RegistryClosureLimb,
    RegistryClosureLimbName,
    RegistryClosureLimbOutcome,
    RegistryClosureOwnerDisposition,
    RegistryClosureRefusal,
    RegistryClosureRefusalReason,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _evidence() -> RegistryClosureEvidence:
    return RegistryClosureEvidence(
        authority="AEAT approved record design",
        locator=aeat_url("aeat_gob", "/record-design"),
    )


def _refusal(
    *,
    limb: RegistryClosureLimbName = "filing_export",
    reason: RegistryClosureRefusalReason = "missing_evidence",
) -> RegistryClosureRefusal:
    return RegistryClosureRefusal(
        reason=reason,
        detail="The selected revision lacks evidence required for this capability.",
        disposition=RegistryClosureOwnerDisposition(
            limb=limb,
            state="blocked",
            owner="registry release owner",
            work_item="export-authority-adjudication",
            reconsideration_condition="Acquire exact official authority for the revision.",
        ),
    )


def test_satisfied_limb_carries_validated_revision_identity_and_evidence() -> None:
    limb = RegistryClosureLimb(
        modelo="303",
        revision="2025",
        name="temporal_coverage",
        outcome="satisfied",
        evidence=(_evidence(),),
    )

    assert (limb.modelo, limb.revision, limb.name, limb.outcome) == (
        "303",
        "2025",
        "temporal_coverage",
        "satisfied",
    )
    assert limb.refusal is None


def test_satisfied_limb_refuses_missing_evidence_or_a_refusal() -> None:
    with pytest.raises(ValidationError, match="requires evidence"):
        RegistryClosureLimb(
            modelo="303",
            revision="2025",
            name="temporal_coverage",
            outcome="satisfied",
        )

    with pytest.raises(ValidationError, match="cannot carry a refusal"):
        RegistryClosureLimb(
            modelo="303",
            revision="2025",
            name="temporal_coverage",
            outcome="satisfied",
            evidence=(_evidence(),),
            refusal=_refusal(limb="temporal_coverage"),
        )


def test_refused_limb_requires_accountable_disposition_for_the_same_limb() -> None:
    with pytest.raises(ValidationError, match="requires an actionable refusal"):
        RegistryClosureLimb(
            modelo="303",
            revision="2025",
            name="filing_export",
            outcome="refused",
        )

    with pytest.raises(ValidationError, match="must name the owning limb"):
        RegistryClosureLimb(
            modelo="303",
            revision="2025",
            name="filing_export",
            outcome="refused",
            refusal=_refusal(limb="temporal_coverage"),
        )


def test_unmeasured_limb_cannot_disguise_a_refusal_as_a_measurement_gap() -> None:
    with pytest.raises(ValidationError, match="requires the unmeasured refusal reason"):
        RegistryClosureLimb(
            modelo="303",
            revision="2025",
            name="source_connectivity",
            outcome="unmeasured",
            refusal=_refusal(limb="source_connectivity", reason="missing_evidence"),
        )

    with pytest.raises(ValidationError, match="cannot use the unmeasured refusal reason"):
        RegistryClosureLimb(
            modelo="303",
            revision="2025",
            name="source_connectivity",
            outcome="refused",
            refusal=_refusal(limb="source_connectivity", reason="unmeasured"),
        )


def test_not_applicable_is_a_filing_only_non_capability_state() -> None:
    """The conditional filing limb cannot become evidence or leak to another authority."""
    limb = RegistryClosureLimb(
        modelo="036",
        revision="2025-02-03-y-siguientes",
        name="filing_export",
        outcome="not_applicable",
    )

    assert (limb.evidence, limb.refusal) == ((), None)
    with pytest.raises(ValidationError, match="only the filing-export limb"):
        RegistryClosureLimb(
            modelo=limb.modelo,
            revision=limb.revision,
            name="source_connectivity",
            outcome="not_applicable",
        )
    with pytest.raises(ValidationError, match="cannot carry capability evidence"):
        RegistryClosureLimb(
            modelo=limb.modelo,
            revision=limb.revision,
            name="filing_export",
            outcome="not_applicable",
            evidence=(_evidence(),),
        )
    with pytest.raises(ValidationError, match="cannot carry a refusal"):
        RegistryClosureLimb(
            modelo=limb.modelo,
            revision=limb.revision,
            name="filing_export",
            outcome="not_applicable",
            refusal=_refusal(),
        )


@pytest.mark.parametrize(
    ("outcome", "reason"),
    (("refused", "missing_evidence"), ("unmeasured", "unmeasured")),
)
def test_active_closure_refusal_cannot_claim_a_resolved_owner_disposition(
    outcome: RegistryClosureLimbOutcome,
    reason: RegistryClosureRefusalReason,
) -> None:
    refusal = _refusal(limb="source_connectivity", reason=reason).model_copy(
        update={
            "disposition": RegistryClosureOwnerDisposition(
                limb="source_connectivity",
                state="resolved",
                owner="registry release owner",
                work_item="source-connectivity-adjudication",
                reconsideration_condition="Measure the selected revision against current evidence.",
            ),
        },
    )

    with pytest.raises(ValidationError, match="cannot carry a resolved owner disposition"):
        RegistryClosureLimb(
            modelo="303",
            revision="2025",
            name="source_connectivity",
            outcome=outcome,
            refusal=refusal,
        )


def test_evidence_and_models_are_strict_and_immutable() -> None:
    evidence = _evidence()
    with pytest.raises(ValidationError, match="frozen"):
        evidence.authority = "different authority"
    with pytest.raises(ValidationError, match="Extra inputs"):
        RegistryClosureEvidence(
            authority="AEAT approved record design",
            locator=aeat_url("aeat_gob", "/record-design"),
            guessed_layout=True,
        )
    with pytest.raises(ValidationError, match="unique"):
        RegistryClosureLimb(
            modelo="303",
            revision="2025",
            name="filing_export",
            outcome="satisfied",
            evidence=(evidence, evidence),
        )
