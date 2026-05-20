"""Live grounded test of the GROI dependency chain against AEAT.

This is the dependency-chain exercise mandated by the calculation-truth
registry: the registry's catalogue → ``resolve_cross_reference_oracle``
→ oracle → live driver → AEAT chain end-to-end on a real modelo 349
counterparty-verification scenario. The test is non-tautological by
construction:

- Expected verdicts come from EXTERNAL ground truth (publicly-known
  Spanish corporate NIFs documented in their own filings as registered
  intra-community operators), not from analyst arithmetic.
- The verification authority is AEAT'S OWN ROI registry consulted via
  the GROI servlet. AEAT reports the answer; the test asserts the
  response shape matches what we know.
- If Telefónica (or any other reference NIF) is silently DEREGISTERED
  by AEAT, this test fires loudly — that is exactly the signal we
  want. The test depends on AEAT's stable answer, not on a duplicated
  computation we control.

Modelo 349 is the recapitulative declaration of intra-community
operations. Spanish counterparties on it MUST be ROI-registered. The
GROI oracle is the surface that confirms it. The dependency chain
exercised here is:

    LiveCrossReferenceDecision (synthetic, public_read_surface)
    └─> remote_state_policy_from_cross_reference
        └─> resolve_cross_reference_oracle (catalogue lookup)
            └─> GroiOracle.verify_payload (per-NIF Protocol contract)
                └─> GroiSedeDriver.collect_observation (Playwright)
                    └─> AEAT GROI servlet
                        └─> live ROI verdict

Read-only mandate: every operation passes through the
RemoteStateGuard with the canonical AEAT_WRITE_FORBIDDEN_ACTIONS
forbidden_actions set. Driver-level form-action attribute guard
catches AEAT silently retargeting the form to a write endpoint
before any submit click.

Live runs require ``AEAT_LIVE_TESTS_ENABLED=1`` plus a fresh
cl@ve-movil session.
"""

from __future__ import annotations

import pytest

from aeat.adapters.outbound.aeat.sede._groi_check import GroiSedeDriver
from aeat.core.resources import resources
from aeat.domain.calculations.registry import (
    AEAT_WRITE_FORBIDDEN_ACTIONS,
    GROI_ORACLE_ID,
    GroiOracle,
    LiveParityCatalogue,
    RemoteStateGuardPolicy,
    evaluate_cross_reference_applicability,
    resolve_cross_reference_oracle,
)
from aeat.tests.live_gate import requires_live_enabled

pytestmark = [pytest.mark.live_read, pytest.mark.domain_outbound]

# External ground truth for the dependency-chain exercise.
#
# Telefónica SA (NIF A28015865) is a publicly-listed Spanish corporate
# entity registered in the AEAT ROI registry; ROI registration is a
# prerequisite for declaring intra-community operations on modelo 349,
# and Telefónica conducts those operations as a matter of public
# record. AEAT IS the authority on whether a NIF is in the registry;
# this test queries AEAT and asserts the answer matches the public
# fact. If AEAT silently deregisters Telefónica, this test fires.
_REGISTERED_PUBLIC_NIF: str = "A28015865"

# A syntactically invalid Spanish NIF that AEAT's GROI form rejects
# at the input-validation layer with the rendered text "El campo Nif
# no es un NIF válido". The verdict for this NIF is stable as long as
# AEAT's NIF format validator behaves per the modelo 036/037 rules.
_INVALID_FORMAT_NIF: str = "B00000001"


def _modelo_349_groi_policy() -> RemoteStateGuardPolicy:
    """Runtime guard policy modelling how modelo 349 would gate GROI traffic.

    Built directly as a :class:`RemoteStateGuardPolicy` (not as a
    :class:`LiveCrossReferenceDecision`) because the cross-reference
    schema's surface-kind taxonomy does not yet model "authenticated
    surface that accepts synthetic VAT-IDs" — the empirical GROI
    semantics. That taxonomy gap is documented as a separate
    follow-up; the guard policy here exercises the runtime read-only
    invariants the calculation engine actually enforces at execution
    time.
    """

    return RemoteStateGuardPolicy(
        id="modelo-349-groi-spanish-counterparty-check",
        evidence_tier="executable_parity_evidence",
        classification="open_simulator",
        allowed_hosts=("www2.agenciatributaria.gob.es",),
        forbidden_actions=AEAT_WRITE_FORBIDDEN_ACTIONS,
        synthetic_data_allowed=True,
        requires_authentication=False,
        requires_aeat_authorization=False,
    )


def _catalogue_with_groi_oracle() -> LiveParityCatalogue:
    catalogue = LiveParityCatalogue()
    catalogue.register(GroiOracle(driver=GroiSedeDriver()), environment="production")
    return catalogue


def test_dependency_chain_resolves_groi_oracle_through_catalogue_lookup() -> None:
    """The catalogue resolves the GROI oracle id to a callable Protocol implementation."""

    requires_live_enabled()
    catalogue = _catalogue_with_groi_oracle()

    oracle = resolve_cross_reference_oracle(
        cross_reference_id="modelo-349-groi-spanish-counterparty-check",
        oracle_id=GROI_ORACLE_ID,
        catalogue=catalogue,
        environment="production",
    )

    assert oracle.oracle_id == GROI_ORACLE_ID
    assert oracle.surface_kind == "vat_id_check"


def test_dependency_chain_confirms_telefonica_is_roi_registered_against_aeat() -> None:
    """AEAT's authoritative response confirms Telefónica's ROI registration.

    Non-tautological: the expected verdict is "valid" because Telefónica
    is publicly-known to be a registered intra-community operator in
    Spain (visible on every public-facing tax-ID lookup, declared on
    their own filings, and a matter of business-registry public
    record). This test asks AEAT and asserts the response shape
    matches that public fact. AEAT is the authority; the test is the
    consumer.
    """

    requires_live_enabled()
    catalogue = _catalogue_with_groi_oracle()
    policy = _modelo_349_groi_policy()

    oracle = resolve_cross_reference_oracle(
        cross_reference_id=policy.id,
        oracle_id=GROI_ORACLE_ID,
        catalogue=catalogue,
        environment="production",
    )
    result = oracle.verify_payload(
        policy,
        b"",
        expected={_REGISTERED_PUBLIC_NIF: "valid"},
    )

    assert result.verdict == "match", result
    assert result.cross_reference_id == policy.id
    assert result.oracle_id == GROI_ORACLE_ID
    assert len(result.fields) == 1
    field = result.fields[0]
    assert field.name == _REGISTERED_PUBLIC_NIF
    assert field.expected == "valid"
    assert field.observed == "valid"
    assert "agenciatributaria.gob.es" in (result.raw_evidence_locator or "")


def test_dependency_chain_aggregates_multiple_counterparty_verdicts() -> None:
    """A modelo 349 declaration with mixed counterparty NIFs surfaces per-NIF verdicts.

    Two NIFs are queried in one call: a public ROI-registered corporate
    NIF (Telefónica) and a syntactically-invalid NIF. AEAT confirms
    the registered NIF, rejects the invalid one. The oracle aggregates
    both as ParityFieldComparisons; the overall verdict is mismatch
    (because we declared expected="valid" for a NIF AEAT considers
    invalid).
    """

    requires_live_enabled()
    catalogue = _catalogue_with_groi_oracle()
    policy = _modelo_349_groi_policy()

    oracle = resolve_cross_reference_oracle(
        cross_reference_id=policy.id,
        oracle_id=GROI_ORACLE_ID,
        catalogue=catalogue,
        environment="production",
    )
    result = oracle.verify_payload(
        policy,
        b"",
        expected={
            _REGISTERED_PUBLIC_NIF: "valid",
            _INVALID_FORMAT_NIF: "valid",  # We claim valid; AEAT will say invalid.
        },
    )

    assert result.verdict == "mismatch", result
    by_nif = {field.name: field for field in result.fields}
    assert by_nif[_REGISTERED_PUBLIC_NIF].verdict == "match"
    assert by_nif[_REGISTERED_PUBLIC_NIF].observed == "valid"
    assert by_nif[_INVALID_FORMAT_NIF].verdict == "mismatch"
    assert by_nif[_INVALID_FORMAT_NIF].observed == "invalid"


def test_dependency_chain_blocks_when_policy_pins_disallowed_host() -> None:
    """The full chain still respects the read-only mandate even when wired through the resolver."""

    requires_live_enabled()
    # Synthesise a policy that pins the wrong host; the guard
    # rejects the GET to www2 before any submit click runs.
    wrong_host_policy = RemoteStateGuardPolicy(
        id="modelo-349-groi-wrong-host",
        evidence_tier="executable_parity_evidence",
        classification="open_simulator",
        allowed_hosts=("sede.agenciatributaria.gob.es",),  # GROI is on www2, not sede.
        forbidden_actions=AEAT_WRITE_FORBIDDEN_ACTIONS,
        synthetic_data_allowed=True,
        requires_authentication=False,
        requires_aeat_authorization=False,
    )
    catalogue = _catalogue_with_groi_oracle()

    oracle = resolve_cross_reference_oracle(
        cross_reference_id=wrong_host_policy.id,
        oracle_id=GROI_ORACLE_ID,
        catalogue=catalogue,
        environment="production",
    )
    result = oracle.verify_payload(wrong_host_policy, b"", expected={_REGISTERED_PUBLIC_NIF: "valid"})

    assert result.verdict == "blocked", result
    assert "blocked by remote-state guard" in result.narrative
    # Critically, no Playwright code ran. The guard rejected before
    # any browser action could leave the process toward AEAT.
    assert result.fields == ()


def test_dependency_chain_skips_groi_when_profile_says_not_intracomunitario() -> None:
    """When the profile is not intracomunitario the chain skips before any HTTP.

    The applicability gate is the structural guarantee that the GROI
    surface is never reached for taxpayers who don't conduct
    intracommunity operations. The test loads the committed binding,
    feeds a profile with does_intracomunitario=False, and asserts the
    typed CrossReferenceApplicability surfaces applicable=False with
    the unmet predicate field. No oracle resolution and no network
    operation runs in the not-applicable branch.

    Marked live_read for collocation with the rest of the GROI
    dependency-chain suite, but the assertion path performs no
    network operation regardless of AEAT_LIVE_TESTS_ENABLED state.
    """

    requires_live_enabled()
    modelo = resources().modelos.get("349")
    binding = next(
        decision
        for decision in modelo.revisions["2020-y-siguientes"].live_cross_references
        if decision.id == "modelo-349-groi-spanish-counterparty-check"
    )

    not_applicable = evaluate_cross_reference_applicability(
        binding,
        profile_facts={"does_intracomunitario": False},
    )
    # The gate is the only contract the dependency chain needs at
    # this layer; downstream invocation is unreachable when the
    # decision says not applicable.
    assert not_applicable.applicable is False
    assert "does_intracomunitario" in not_applicable.unmet_predicate_fields
