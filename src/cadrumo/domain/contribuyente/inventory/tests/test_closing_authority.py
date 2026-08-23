"""Physical closing observation, authority, and continuity domain tests."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from cadrumo.domain.contribuyente.inventory import (
    InventoryClosingAuthority,
    InventoryClosingAuthorityDecision,
    InventoryClosingConflictDiagnostic,
    InventoryClosingDecisionEvidence,
    InventoryClosingDecisionEvidenceRole,
    InventoryClosingResolution,
    InventoryClosingValuationBasis,
    InventoryLedger,
    InventoryValidationError,
    PhysicalClosingEvidence,
    PhysicalClosingEvidenceRole,
    PhysicalClosingObservation,
    PriorAuthoritativeClosingLink,
    PriorClosingContinuityEvidence,
    ValuationMethod,
    fingerprint_prior_authoritative_closing,
    resolve_inventory_authoritative_closing,
)
from cadrumo.domain.filing_evidence import FilingEvidenceReference

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _ref(value: str) -> FilingEvidenceReference:
    return FilingEvidenceReference(reference=value)


def _evidence() -> tuple[PhysicalClosingEvidence, ...]:
    return (
        PhysicalClosingEvidence(
            reference=_ref("physical-count"),
            role=PhysicalClosingEvidenceRole.PHYSICAL_COUNT,
            content_digest="a" * 64,
        ),
        PhysicalClosingEvidence(
            reference=_ref("valuation-workpaper"),
            role=PhysicalClosingEvidenceRole.ACQUISITION_PRICE_VALUATION,
            content_digest="b" * 64,
        ),
    )


def _observation(**overrides: object) -> PhysicalClosingObservation:
    fields: dict[str, object] = {
        "observation_id": "physical-2025",
        "observed_on": date(2026, 1, 2),
        "as_of_date": date(2025, 12, 31),
        "actividad_id": "retail",
        "filing_year": 2025,
        "closing_value": Decimal("130.00"),
        "valuation_basis": InventoryClosingValuationBasis.FIFO_ACQUISITION_PRICE,
        "evidence": _evidence(),
    }
    fields.update(overrides)
    return PhysicalClosingObservation.model_validate(fields)


def _decision(
    *,
    authority: InventoryClosingAuthority,
    observation: PhysicalClosingObservation | None = None,
    **overrides: object,
) -> InventoryClosingAuthorityDecision:
    fields: dict[str, object] = {
        "decision_id": "decision-2025",
        "actividad_id": "retail",
        "filing_year": 2025,
        "authority": authority,
        "physical_observation_id": observation.observation_id if observation else None,
        "physical_observation_fingerprint": observation.fingerprint if observation else None,
        "reason": "Year-end physical count adjudicated against movement-derived valuation.",
        "actor": "inventory-reviewer",
        "source_command": "inventory.closing.authority.decide",
        "decided_at": datetime(2026, 1, 3, tzinfo=UTC),
        "evidence": (
            InventoryClosingDecisionEvidence(
                reference=_ref("decision-evidence"),
                role=InventoryClosingDecisionEvidenceRole.AUTHORITY_RECONCILIATION,
                content_digest="e" * 64,
            ),
        ),
    }
    fields.update(overrides)
    return InventoryClosingAuthorityDecision.model_validate(fields)


def _continuity(**overrides: object) -> PriorAuthoritativeClosingLink:
    evidence = (
        PriorClosingContinuityEvidence(
            reference=_ref("prior-closing-evidence"),
            content_digest="f" * 64,
        ),
    )
    fields: dict[str, object] = {
        "actividad_id": "retail",
        "current_filing_year": 2025,
        "prior_filing_year": 2024,
        "prior_authoritative_closing_value": Decimal("100.00"),
        "current_opening_value": Decimal("100.00"),
        "prior_authoritative_source_fingerprint": "c" * 64,
        "evidence": evidence,
    }
    fields.update(overrides)
    fields.setdefault(
        "prior_authoritative_closing_fingerprint",
        fingerprint_prior_authoritative_closing(
            actividad_id=str(fields["actividad_id"]),
            filing_year=int(fields["prior_filing_year"]),
            authoritative_closing_value=Decimal(fields["prior_authoritative_closing_value"]),
            authoritative_source_fingerprint=str(fields["prior_authoritative_source_fingerprint"]),
            evidence=fields["evidence"],
        ),
    )
    return PriorAuthoritativeClosingLink.model_validate(fields)


def _ledger(method: ValuationMethod = ValuationMethod.FIFO) -> InventoryLedger:
    return InventoryLedger(
        actividad_id="retail",
        year=2025,
        valuation_method=method,
        opening_stock=Decimal("100.00"),
    )


def test_physical_observation_fingerprint_is_order_stable_and_mutation_sensitive() -> None:
    observation = _observation()
    reordered = _observation(evidence=tuple(reversed(_evidence())))
    assert reordered.fingerprint == observation.fingerprint

    changed_value = _observation(closing_value=Decimal("130.01"))
    changed_digest_evidence = list(_evidence())
    changed_digest_evidence[0] = changed_digest_evidence[0].model_copy(update={"content_digest": "d" * 64})
    changed_digest = _observation(evidence=tuple(changed_digest_evidence))
    assert changed_value.fingerprint != observation.fingerprint
    assert changed_digest.fingerprint != observation.fingerprint


@pytest.mark.parametrize(
    "mutation",
    [
        {"as_of_date": date(2025, 12, 30)},
        {"observed_on": date(2025, 12, 30)},
        {"closing_value": Decimal("100.001")},
        {"evidence": (_evidence()[0],)},
        {"evidence": (_evidence()[0], _evidence()[0])},
        {
            "evidence": (
                _evidence()[0],
                _evidence()[0].model_copy(update={"reference": _ref("second-count")}),
                _evidence()[1],
            ),
        },
    ],
)
def test_physical_observation_refuses_bad_dates_cents_and_evidence(mutation: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        _observation(**mutation)


def test_authority_decision_requires_closed_observation_identity_and_evidence() -> None:
    observation = _observation()
    with pytest.raises(ValidationError, match="requires observation identity and fingerprint"):
        _decision(authority=InventoryClosingAuthority.PHYSICAL_OBSERVATION)
    with pytest.raises(ValidationError, match="must travel together"):
        _decision(
            authority=InventoryClosingAuthority.MOVEMENT_DERIVED,
            physical_observation_id=observation.observation_id,
        )
    with pytest.raises(ValidationError, match="timezone-aware"):
        _decision(authority=InventoryClosingAuthority.MOVEMENT_DERIVED, decided_at=datetime(2026, 1, 3))


def test_authority_decision_fingerprint_is_mutation_sensitive() -> None:
    decision = _decision(authority=InventoryClosingAuthority.MOVEMENT_DERIVED)
    assert _decision(authority=decision.authority, reason=f"{decision.reason} amended").fingerprint != decision.fingerprint
    assert _decision(authority=decision.authority, actor="other-reviewer").fingerprint != decision.fingerprint
    assert (
        _decision(authority=decision.authority, decided_at=datetime(2026, 1, 4, tzinfo=UTC)).fingerprint
        != decision.fingerprint
    )
    changed_evidence = decision.evidence[0].model_copy(update={"content_digest": "d" * 64})
    assert _decision(authority=decision.authority, evidence=(changed_evidence,)).fingerprint != decision.fingerprint


@pytest.mark.parametrize(
    "mutation",
    [
        {"prior_filing_year": 2023},
        {"prior_authoritative_closing_value": Decimal("99.99")},
        {"current_opening_value": Decimal("100.001")},
        {"prior_authoritative_source_fingerprint": "not-a-digest"},
    ],
)
def test_prior_link_refuses_gap_value_drift_subcents_and_bad_source_fingerprint(
    mutation: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        _continuity(**mutation)


def test_prior_link_refuses_valid_source_or_value_substitution_with_stale_binding() -> None:
    link = _continuity()
    with pytest.raises(ValidationError, match="does not bind"):
        _continuity(
            prior_authoritative_source_fingerprint="d" * 64,
            prior_authoritative_closing_fingerprint=link.prior_authoritative_closing_fingerprint,
        )
    with pytest.raises(ValidationError, match="does not bind"):
        _continuity(
            prior_authoritative_closing_value=Decimal("99.00"),
            current_opening_value=Decimal("99.00"),
            prior_authoritative_closing_fingerprint=link.prior_authoritative_closing_fingerprint,
        )


def test_physical_conflict_requires_decision_continuity_and_is_retained() -> None:
    observation = _observation()
    decision = _decision(authority=InventoryClosingAuthority.PHYSICAL_OBSERVATION, observation=observation)
    resolution = resolve_inventory_authoritative_closing(
        _ledger(),
        decision=decision,
        physical_observation=observation,
        prior_closing_link=_continuity(),
    )

    assert resolution.authoritative_value == Decimal("130.00")
    assert resolution.movement_derived_value == Decimal("100.00")
    assert resolution.conflict is not None
    assert resolution.conflict.physical_observation_fingerprint == observation.fingerprint
    assert resolution.decision_id == decision.decision_id
    assert resolution.decision_fingerprint == decision.fingerprint
    assert resolution.physical_observation_id == observation.observation_id
    assert resolution.prior_closing_link_fingerprint == _continuity().fingerprint

    with pytest.raises(InventoryValidationError, match="requires complete prior-closing continuity"):
        resolve_inventory_authoritative_closing(
            _ledger(),
            decision=decision,
            physical_observation=observation,
            prior_closing_link=None,
        )


def test_physical_resolution_refuses_same_id_substitution_coordinate_basis_and_opening_drift() -> None:
    observation = _observation()
    decision = _decision(authority=InventoryClosingAuthority.PHYSICAL_OBSERVATION, observation=observation)
    substituted = _observation(closing_value=Decimal("131.00"))
    with pytest.raises(InventoryValidationError, match="fingerprint does not match"):
        resolve_inventory_authoritative_closing(
            _ledger(),
            decision=decision,
            physical_observation=substituted,
            prior_closing_link=_continuity(),
        )
    with pytest.raises(InventoryValidationError, match="valuation basis"):
        resolve_inventory_authoritative_closing(
            _ledger(ValuationMethod.PMP),
            decision=decision,
            physical_observation=observation,
            prior_closing_link=_continuity(),
        )
    with pytest.raises(InventoryValidationError, match="coordinate and opening"):
        resolve_inventory_authoritative_closing(
            _ledger(),
            decision=decision,
            physical_observation=observation,
            prior_closing_link=_continuity(
                prior_authoritative_closing_value=Decimal("90.00"),
                current_opening_value=Decimal("90.00"),
            ),
        )


@pytest.mark.parametrize(
    "authority",
    [InventoryClosingAuthority.PHYSICAL_OBSERVATION, InventoryClosingAuthority.MOVEMENT_DERIVED],
)
def test_resolution_refuses_decision_that_predates_named_physical_observation(
    authority: InventoryClosingAuthority,
) -> None:
    observation = _observation()
    decision = _decision(
        authority=authority,
        observation=observation,
        decided_at=datetime(2026, 1, 1, 23, 59, tzinfo=UTC),
    )

    with pytest.raises(InventoryValidationError, match="cannot predate"):
        resolve_inventory_authoritative_closing(
            _ledger(),
            decision=decision,
            physical_observation=observation,
            prior_closing_link=_continuity(),
        )


def test_movement_authority_retains_competing_physical_conflict_and_continuity() -> None:
    observation = _observation()
    resolution = resolve_inventory_authoritative_closing(
        _ledger(),
        decision=_decision(authority=InventoryClosingAuthority.MOVEMENT_DERIVED, observation=observation),
        physical_observation=observation,
        prior_closing_link=_continuity(),
    )

    assert resolution.authoritative_value == Decimal("100.00")
    assert resolution.physical_observed_value == Decimal("130.00")
    assert resolution.conflict is not None

    with pytest.raises(InventoryValidationError, match="requires complete prior-closing continuity"):
        resolve_inventory_authoritative_closing(
            _ledger(),
            decision=_decision(authority=InventoryClosingAuthority.MOVEMENT_DERIVED),
            physical_observation=None,
            prior_closing_link=None,
        )


@pytest.mark.parametrize(
    ("method", "basis"),
    [
        (ValuationMethod.PMP, InventoryClosingValuationBasis.PMP_ACQUISITION_PRICE),
        (ValuationMethod.COSTE_MEDIO, InventoryClosingValuationBasis.COSTE_MEDIO_ACQUISITION_PRICE),
    ],
)
def test_supported_average_methods_keep_distinct_grounded_bases(
    method: ValuationMethod,
    basis: InventoryClosingValuationBasis,
) -> None:
    observation = _observation(valuation_basis=basis)
    resolution = resolve_inventory_authoritative_closing(
        _ledger(method),
        decision=_decision(authority=InventoryClosingAuthority.PHYSICAL_OBSERVATION, observation=observation),
        physical_observation=observation,
        prior_closing_link=_continuity(),
    )
    assert resolution.authority is InventoryClosingAuthority.PHYSICAL_OBSERVATION


def test_resolution_refuses_forged_missing_conflict_and_legacy_bare_closing_stock() -> None:
    provenance = {
        "decision_id": "decision-2025",
        "decision_fingerprint": "d" * 64,
        "prior_closing_link_fingerprint": "e" * 64,
    }
    with pytest.raises(ValidationError, match="conflict diagnostic"):
        InventoryClosingResolution(
            actividad_id="retail",
            filing_year=2025,
            authority=InventoryClosingAuthority.PHYSICAL_OBSERVATION,
            authoritative_value=Decimal("130.00"),
            movement_derived_value=Decimal("100.00"),
            physical_observed_value=Decimal("130.00"),
            physical_observation_fingerprint="a" * 64,
            physical_observation_id="physical-2025",
            conflict=None,
            **provenance,
        )
    with pytest.raises(ValidationError, match="movement-derived authority value"):
        InventoryClosingResolution(
            actividad_id="retail",
            filing_year=2025,
            authority=InventoryClosingAuthority.MOVEMENT_DERIVED,
            authoritative_value=Decimal("101.00"),
            movement_derived_value=Decimal("100.00"),
            **provenance,
        )
    with pytest.raises(ValidationError, match="conflict diagnostic does not match"):
        InventoryClosingResolution(
            actividad_id="retail",
            filing_year=2025,
            authority=InventoryClosingAuthority.PHYSICAL_OBSERVATION,
            authoritative_value=Decimal("130.00"),
            movement_derived_value=Decimal("100.00"),
            physical_observed_value=Decimal("130.00"),
            physical_observation_fingerprint="a" * 64,
            physical_observation_id="physical-2025",
            conflict=InventoryClosingConflictDiagnostic(
                actividad_id="retail",
                filing_year=2025,
                movement_derived_value=Decimal("100.00"),
                physical_observed_value=Decimal("131.00"),
                physical_observation_fingerprint="a" * 64,
            ),
            **provenance,
        )
    with pytest.raises(ValidationError, match="quantised to cents"):
        InventoryClosingResolution(
            actividad_id="retail",
            filing_year=2025,
            authority=InventoryClosingAuthority.MOVEMENT_DERIVED,
            authoritative_value=Decimal("100.001"),
            movement_derived_value=Decimal("100.001"),
            **provenance,
        )
    with pytest.raises(ValidationError, match="closing_stock"):
        InventoryLedger.model_validate(
            {
                "actividad_id": "retail",
                "year": 2025,
                "valuation_method": "fifo",
                "opening_stock": "100.00",
                "closing_stock": "130.00",
            },
        )
