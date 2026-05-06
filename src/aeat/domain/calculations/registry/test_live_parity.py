"""Modelo-agnostic tests for the live parity oracle backend.

These tests use a synthetic FakeOracle to prove the contract enforced by
:mod:`_live_parity` without touching any real AEAT surface:

- Pre-flight rejects oracles whose planned operations violate the
  remote-state guard before any verification code runs.
- The catalogue rejects duplicate registrations and resolves oracle ids.
- Per-policy classification short-circuits correctly (static-only policies
  block remote operations even when the oracle plans benign GETs).
"""

from __future__ import annotations

from collections.abc import Mapping

import pytest
from pydantic import AnyUrl

from ._errors import RegistryValidationError
from ._live_parity import (
    LiveParityCatalogue,
    OracleSurfaceKind,
    ParityFieldComparison,
    ParityResult,
    assert_oracle_operations_allowed,
    build_planned_operations,
    evaluate_planned_operations,
    pre_flight_oracle_operations,
)
from ._remote_state_guard import RemoteOperation, RemoteStateGuardPolicy

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


class _FakeOracle:
    """Test-double oracle that returns canned operations + verdicts."""

    def __init__(
        self,
        *,
        oracle_id: str,
        surface_kind: OracleSurfaceKind,
        operations: tuple[RemoteOperation, ...],
        verdict: ParityResult,
    ) -> None:
        self._oracle_id = oracle_id
        self._surface_kind = surface_kind
        self._operations = operations
        self._verdict = verdict

    @property
    def oracle_id(self) -> str:
        return self._oracle_id

    @property
    def surface_kind(self) -> OracleSurfaceKind:
        return self._surface_kind

    def planned_operations(
        self,
        payload: bytes,
        *,
        expected: Mapping[str, object],
    ) -> tuple[RemoteOperation, ...]:
        return self._operations

    def verify_payload(
        self,
        policy: RemoteStateGuardPolicy,
        payload: bytes,
        *,
        expected: Mapping[str, object],
    ) -> ParityResult:
        assert_oracle_operations_allowed(self, policy, self._operations)
        return self._verdict


def _read_only_policy() -> RemoteStateGuardPolicy:
    return RemoteStateGuardPolicy(
        id="test-policy",
        evidence_tier="executable_parity_evidence",
        classification="open_simulator",
        allowed_hosts=("www6.agenciatributaria.gob.es",),
        synthetic_data_allowed=True,
        requires_authentication=False,
        requires_aeat_authorization=False,
        forbidden_actions=("presentation", "signing"),
    )


def _static_only_policy() -> RemoteStateGuardPolicy:
    return RemoteStateGuardPolicy(
        id="static-only-policy",
        evidence_tier="official_source_guidance",
        classification="static_official_only",
        allowed_hosts=(),
        synthetic_data_allowed=False,
        requires_authentication=False,
        requires_aeat_authorization=False,
        forbidden_actions=("presentation",),
    )


def _read_only_get(url: str) -> RemoteOperation:
    return RemoteOperation(kind="http", method="GET", url=AnyUrl(url))


def _post(url: str) -> RemoteOperation:
    return RemoteOperation(kind="http", method="POST", url=AnyUrl(url))


def test_parity_field_comparison_rejects_duplicate_field_names() -> None:
    with pytest.raises(ValueError, match="duplicate parity field"):
        ParityResult(
            oracle_id="o",
            cross_reference_id="c",
            verdict="match",
            narrative="dup",
            fields=(
                ParityFieldComparison(name="x", expected="1", observed="1", verdict="match"),
                ParityFieldComparison(name="x", expected="2", observed="2", verdict="match"),
            ),
        )


def test_catalogue_register_and_lookup_round_trip() -> None:
    catalogue = LiveParityCatalogue()
    oracle = _FakeOracle(
        oracle_id="aeat-tgvi-online",
        surface_kind="file_validator",
        operations=(_read_only_get("https://www6.agenciatributaria.gob.es/wlpl/PRET/check"),),
        verdict=ParityResult(
            oracle_id="aeat-tgvi-online",
            cross_reference_id="test-policy",
            verdict="match",
            narrative="canned",
        ),
    )

    catalogue.register(oracle)

    assert catalogue.is_registered("aeat-tgvi-online")
    assert catalogue.ids() == ("aeat-tgvi-online",)
    assert catalogue.lookup("aeat-tgvi-online") is oracle


def test_catalogue_rejects_duplicate_oracle_id() -> None:
    catalogue = LiveParityCatalogue()
    oracle = _FakeOracle(
        oracle_id="dup",
        surface_kind="file_validator",
        operations=(),
        verdict=ParityResult(oracle_id="dup", cross_reference_id="c", verdict="match", narrative="x"),
    )
    catalogue.register(oracle)

    with pytest.raises(RegistryValidationError, match="already registered"):
        catalogue.register(oracle)


def test_catalogue_lookup_unknown_id_raises() -> None:
    catalogue = LiveParityCatalogue()

    with pytest.raises(RegistryValidationError, match="unknown oracle_id"):
        catalogue.lookup("missing")


def test_pre_flight_passes_when_planned_operations_are_read_only() -> None:
    oracle = _FakeOracle(
        oracle_id="vies",
        surface_kind="vat_id_check",
        operations=(_read_only_get("https://www6.agenciatributaria.gob.es/wlpl/check?nif=DE111"),),
        verdict=ParityResult(oracle_id="vies", cross_reference_id="test-policy", verdict="match", narrative="ok"),
    )
    policy = _read_only_policy()

    operations = pre_flight_oracle_operations(oracle, policy, payload=b"", expected={})

    assert operations == oracle.planned_operations(b"", expected={})


def test_pre_flight_blocks_oracle_with_post_operation() -> None:
    oracle = _FakeOracle(
        oracle_id="bad",
        surface_kind="pre_filing_validator",
        operations=(
            _read_only_get("https://www6.agenciatributaria.gob.es/wlpl/check"),
            _post("https://www6.agenciatributaria.gob.es/wlpl/submit"),
        ),
        verdict=ParityResult(oracle_id="bad", cross_reference_id="test-policy", verdict="match", narrative="x"),
    )
    policy = _read_only_policy()

    with pytest.raises(RegistryValidationError, match="blocked by policy"):
        pre_flight_oracle_operations(oracle, policy, payload=b"", expected={})


def test_pre_flight_blocks_oracle_targeting_non_aeat_host() -> None:
    oracle = _FakeOracle(
        oracle_id="phisher",
        surface_kind="vat_id_check",
        operations=(_read_only_get("https://example.com/check"),),
        verdict=ParityResult(oracle_id="phisher", cross_reference_id="test-policy", verdict="match", narrative="x"),
    )
    policy = _read_only_policy()

    with pytest.raises(RegistryValidationError, match="not in allowed read-only hosts"):
        pre_flight_oracle_operations(oracle, policy, payload=b"", expected={})


def test_evaluate_returns_blocked_result_for_static_only_policy_when_oracle_plans_remote_operations() -> None:
    oracle = _FakeOracle(
        oracle_id="oracle",
        surface_kind="open_simulator",
        operations=(_read_only_get("https://www6.agenciatributaria.gob.es/wlpl/sim"),),
        verdict=ParityResult(
            oracle_id="oracle",
            cross_reference_id="static-only-policy",
            verdict="match",
            narrative="canned",
        ),
    )
    policy = _static_only_policy()

    result = evaluate_planned_operations(oracle, policy, payload=b"", expected={})

    assert isinstance(result, ParityResult)
    assert result.verdict == "blocked"
    assert "static_official_only" in result.narrative


def test_oracle_verify_payload_calls_guard_before_returning_match() -> None:
    oracle = _FakeOracle(
        oracle_id="guarded",
        surface_kind="open_simulator",
        operations=(_read_only_get("https://www6.agenciatributaria.gob.es/wlpl/sim"),),
        verdict=ParityResult(
            oracle_id="guarded",
            cross_reference_id="test-policy",
            verdict="match",
            narrative="all fields conform",
            fields=(ParityFieldComparison(name="op-count", expected="2", observed="2", verdict="match"),),
        ),
    )
    policy = _read_only_policy()

    result = oracle.verify_payload(policy, b"<payload>", expected={"op-count": 2})

    assert result.verdict == "match"
    assert result.fields[0].name == "op-count"


def test_oracle_verify_payload_raises_when_planned_operation_blocked() -> None:
    oracle = _FakeOracle(
        oracle_id="bad-verify",
        surface_kind="pre_filing_validator",
        operations=(_post("https://www6.agenciatributaria.gob.es/wlpl/submit"),),
        verdict=ParityResult(oracle_id="bad-verify", cross_reference_id="test-policy", verdict="match", narrative="x"),
    )
    policy = _read_only_policy()

    with pytest.raises(RegistryValidationError):
        oracle.verify_payload(policy, b"", expected={})


def test_build_planned_operations_returns_immutable_tuple() -> None:
    oracle = _FakeOracle(
        oracle_id="immut",
        surface_kind="vat_id_check",
        operations=(_read_only_get("https://www6.agenciatributaria.gob.es/wlpl/check"),),
        verdict=ParityResult(oracle_id="immut", cross_reference_id="test-policy", verdict="match", narrative="x"),
    )

    planned = build_planned_operations(oracle, b"", expected={})

    assert isinstance(planned, tuple)
    assert len(planned) == 1
