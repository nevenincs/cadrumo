"""Modelo-agnostic tests for the live parity oracle backend.

These tests use a canned-response oracle to prove the contract enforced
by :mod:`_live_parity` without touching any real AEAT surface:

- Pre-flight rejects oracles whose planned operations violate the
  remote-state guard before any verification code runs.
- The catalogue rejects duplicate registrations and resolves oracle ids.
- Per-policy classification short-circuits correctly (static-only policies
  block remote operations even when the oracle plans benign GETs).
"""

from __future__ import annotations

from collections.abc import Mapping

import pytest
from pydantic import AnyUrl, ValidationError

from .....tests.aeat_literal_fixtures import (
    LIVE_PARITY_GENERIC_CHECK_PATH_FIXTURE,
    LIVE_PARITY_PRET_CHECK_PATH_FIXTURE,
    LIVE_PARITY_STATE_CREATING_PATH_CANARIES,
    LIVE_PARITY_STATIC_REMOTE_PATH_FIXTURE,
    LIVE_PARITY_SUBMIT_PATH_CANARY,
    aeat_host,
    aeat_url,
)
from .._errors import RegistryValidationError
from .._live_parity import (
    LiveParityCatalogue,
    OracleEnvironment,
    OracleSurfaceKind,
    ParityFieldComparison,
    ParityResult,
    ReplayPayload,
    assert_oracle_operations_allowed,
    decode_replay_json_payload,
    evaluate_planned_operations,
    pre_flight_oracle_operations,
)
from .._remote_state_guard import RemoteOperation, RemoteStateGuardPolicy

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_WWW6_HOST = aeat_host("www6")


class _CannedOracle:
    """Real :class:`Oracle` protocol implementation backed by canned values.

    Returns operator-supplied ``planned_operations`` and
    ``ParityResult`` verdicts. Used as input to the real
    ``pre_flight_oracle_operations`` /
    ``evaluate_planned_operations`` / ``LiveParityCatalogue`` code
    under test — those production functions run unchanged on the
    canned inputs.
    """

    def __init__(
        self,
        *,
        oracle_id: str,
        surface_kind: OracleSurfaceKind,
        operations: tuple[RemoteOperation, ...],
        verdict: ParityResult,
    ) -> None:
        self._oracle_id = oracle_id
        self._surface_kind: OracleSurfaceKind = surface_kind
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
        allowed_hosts=(_WWW6_HOST,),
        synthetic_data_allowed=False,
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


@pytest.mark.parametrize(
    "url",
    [aeat_url("www6", path) for path in LIVE_PARITY_STATE_CREATING_PATH_CANARIES],
)
def test_pre_flight_blocks_oracle_targeting_state_creating_aeat_surface(url: str) -> None:
    oracle = _CannedOracle(
        oracle_id="state-creator",
        surface_kind="file_validator",
        operations=(_read_only_get(url),),
        verdict=ParityResult(
            oracle_id="state-creator",
            cross_reference_id="test-policy",
            verdict="match",
            narrative="x",
        ),
    )
    policy = _read_only_policy()

    with pytest.raises(RegistryValidationError, match="forbidden"):
        pre_flight_oracle_operations(oracle, policy, payload=b"", expected={})


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
    oracle = _CannedOracle(
        oracle_id="aeat-public-vies",
        surface_kind="iva_id_check",
        operations=(_read_only_get(aeat_url("www6", LIVE_PARITY_PRET_CHECK_PATH_FIXTURE)),),
        verdict=ParityResult(
            oracle_id="aeat-public-vies",
            cross_reference_id="test-policy",
            verdict="match",
            narrative="canned",
        ),
    )

    catalogue.register(oracle, environment=OracleEnvironment.PRODUCTION)

    assert catalogue.is_registered("aeat-public-vies")
    assert catalogue.ids() == ("aeat-public-vies",)
    assert catalogue.lookup("aeat-public-vies") is oracle
    assert catalogue.environment_of("aeat-public-vies") == OracleEnvironment.PRODUCTION


def test_catalogue_rejects_duplicate_oracle_id() -> None:
    catalogue = LiveParityCatalogue()
    oracle = _CannedOracle(
        oracle_id="dup",
        surface_kind="file_validator",
        operations=(),
        verdict=ParityResult(oracle_id="dup", cross_reference_id="c", verdict="match", narrative="x"),
    )
    catalogue.register(oracle, environment=OracleEnvironment.PRODUCTION)

    with pytest.raises(RegistryValidationError, match="already registered"):
        catalogue.register(oracle, environment=OracleEnvironment.PRODUCTION)


def test_catalogue_lookup_unknown_id_raises() -> None:
    catalogue = LiveParityCatalogue()

    with pytest.raises(RegistryValidationError, match="unknown oracle_id"):
        catalogue.lookup("missing")


def test_catalogue_test_environment_oracle_not_visible_to_production_lookup() -> None:
    catalogue = LiveParityCatalogue()
    oracle = _CannedOracle(
        oracle_id="aeat-tgvi-preproduccion",
        surface_kind="file_validator",
        operations=(),
        verdict=ParityResult(
            oracle_id="aeat-tgvi-preproduccion",
            cross_reference_id="test-policy",
            verdict="match",
            narrative="canned",
        ),
    )
    catalogue.register(oracle, environment=OracleEnvironment.TEST_ENVIRONMENT)

    with pytest.raises(RegistryValidationError, match="not available under requested environment"):
        catalogue.lookup("aeat-tgvi-preproduccion", environment=OracleEnvironment.PRODUCTION)

    # Test-environment lookup succeeds.
    assert catalogue.lookup("aeat-tgvi-preproduccion", environment=OracleEnvironment.TEST_ENVIRONMENT) is oracle


def test_catalogue_production_oracle_not_visible_to_test_environment_lookup() -> None:
    catalogue = LiveParityCatalogue()
    oracle = _CannedOracle(
        oracle_id="aeat-vies-public",
        surface_kind="iva_id_check",
        operations=(),
        verdict=ParityResult(
            oracle_id="aeat-vies-public",
            cross_reference_id="test-policy",
            verdict="match",
            narrative="canned",
        ),
    )
    catalogue.register(oracle, environment=OracleEnvironment.PRODUCTION)

    with pytest.raises(RegistryValidationError, match="not available under requested environment"):
        catalogue.lookup("aeat-vies-public", environment=OracleEnvironment.TEST_ENVIRONMENT)


def test_catalogue_both_environment_oracle_visible_to_either_lookup() -> None:
    catalogue = LiveParityCatalogue()
    oracle = _CannedOracle(
        oracle_id="aeat-static-doc",
        surface_kind="iva_id_check",
        operations=(),
        verdict=ParityResult(
            oracle_id="aeat-static-doc",
            cross_reference_id="test-policy",
            verdict="match",
            narrative="canned",
        ),
    )
    catalogue.register(oracle, environment=OracleEnvironment.BOTH)

    assert catalogue.lookup("aeat-static-doc", environment=OracleEnvironment.PRODUCTION) is oracle
    assert catalogue.lookup("aeat-static-doc", environment=OracleEnvironment.TEST_ENVIRONMENT) is oracle


def test_catalogue_ids_filter_by_environment() -> None:
    catalogue = LiveParityCatalogue()
    prod_oracle = _CannedOracle(
        oracle_id="prod",
        surface_kind="iva_id_check",
        operations=(),
        verdict=ParityResult(oracle_id="prod", cross_reference_id="c", verdict="match", narrative="x"),
    )
    test_oracle = _CannedOracle(
        oracle_id="test",
        surface_kind="file_validator",
        operations=(),
        verdict=ParityResult(oracle_id="test", cross_reference_id="c", verdict="match", narrative="x"),
    )
    both_oracle = _CannedOracle(
        oracle_id="both",
        surface_kind="iva_id_check",
        operations=(),
        verdict=ParityResult(oracle_id="both", cross_reference_id="c", verdict="match", narrative="x"),
    )
    catalogue.register(prod_oracle, environment=OracleEnvironment.PRODUCTION)
    catalogue.register(test_oracle, environment=OracleEnvironment.TEST_ENVIRONMENT)
    catalogue.register(both_oracle, environment=OracleEnvironment.BOTH)

    assert catalogue.ids() == ("both", "prod", "test")
    assert catalogue.ids(environment=OracleEnvironment.PRODUCTION) == ("both", "prod")
    assert catalogue.ids(environment=OracleEnvironment.TEST_ENVIRONMENT) == ("both", "test")


# ── contract: OracleEnvironment StrEnum round-trip ───────────────────────────────


def test_oracle_environment_members_are_str_subclass() -> None:
    """Every OracleEnvironment member must be a str subclass (StrEnum contract)."""
    for member in OracleEnvironment:
        assert isinstance(member, str), f"{member!r} is not a str instance"


@pytest.mark.parametrize(
    ("member", "expected_value"),
    [
        (OracleEnvironment.PRODUCTION, "production"),
        (OracleEnvironment.TEST_ENVIRONMENT, "test_environment"),
        (OracleEnvironment.BOTH, "both"),
    ],
)
def test_oracle_environment_member_values(member: OracleEnvironment, expected_value: str) -> None:
    """Each member's string value must match the canonical AEAT environment name."""
    assert member == expected_value
    assert str(member) == expected_value


def test_oracle_environment_default_round_trips_through_catalogue_register() -> None:
    """OracleEnvironment.PRODUCTION default must survive a full register→lookup cycle."""
    catalogue = LiveParityCatalogue()
    oracle = _CannedOracle(
        oracle_id="env-roundtrip",
        surface_kind="iva_id_check",
        operations=(),
        verdict=ParityResult(oracle_id="env-roundtrip", cross_reference_id="c", verdict="match", narrative="x"),
    )
    # Use the enum member as the explicit environment value.
    catalogue.register(oracle, environment=OracleEnvironment.PRODUCTION)

    # Default lookup (OracleEnvironment.PRODUCTION) must resolve the oracle.
    resolved = catalogue.lookup("env-roundtrip")
    assert resolved is oracle
    assert catalogue.environment_of("env-roundtrip") == OracleEnvironment.PRODUCTION
    assert catalogue.environment_of("env-roundtrip") == "production"


def test_oracle_environment_test_environment_round_trips_through_catalogue() -> None:
    catalogue = LiveParityCatalogue()
    oracle = _CannedOracle(
        oracle_id="env-test-rt",
        surface_kind="file_validator",
        operations=(),
        verdict=ParityResult(oracle_id="env-test-rt", cross_reference_id="c", verdict="match", narrative="x"),
    )
    catalogue.register(oracle, environment=OracleEnvironment.TEST_ENVIRONMENT)

    resolved = catalogue.lookup("env-test-rt", environment=OracleEnvironment.TEST_ENVIRONMENT)
    assert resolved is oracle
    assert catalogue.environment_of("env-test-rt") == OracleEnvironment.TEST_ENVIRONMENT
    assert catalogue.environment_of("env-test-rt") == "test_environment"


def test_oracle_environment_both_round_trips_through_catalogue() -> None:
    catalogue = LiveParityCatalogue()
    oracle = _CannedOracle(
        oracle_id="env-both-rt",
        surface_kind="iva_id_check",
        operations=(),
        verdict=ParityResult(oracle_id="env-both-rt", cross_reference_id="c", verdict="match", narrative="x"),
    )
    catalogue.register(oracle, environment=OracleEnvironment.BOTH)

    assert catalogue.lookup("env-both-rt", environment=OracleEnvironment.PRODUCTION) is oracle
    assert catalogue.lookup("env-both-rt", environment=OracleEnvironment.TEST_ENVIRONMENT) is oracle
    assert catalogue.environment_of("env-both-rt") == OracleEnvironment.BOTH
    assert catalogue.environment_of("env-both-rt") == "both"


def test_pre_flight_passes_when_planned_operations_are_read_only() -> None:
    oracle = _CannedOracle(
        oracle_id="vies",
        surface_kind="iva_id_check",
        operations=(_read_only_get(f"{aeat_url('www6', LIVE_PARITY_GENERIC_CHECK_PATH_FIXTURE)}?nif=DE111"),),
        verdict=ParityResult(oracle_id="vies", cross_reference_id="test-policy", verdict="match", narrative="ok"),
    )
    policy = _read_only_policy()

    operations = pre_flight_oracle_operations(oracle, policy, payload=b"", expected={})

    assert operations == oracle.planned_operations(b"", expected={})


def test_pre_flight_blocks_oracle_with_post_operation() -> None:
    oracle = _CannedOracle(
        oracle_id="bad",
        surface_kind="pre_filing_validator",
        operations=(
            _read_only_get(aeat_url("www6", LIVE_PARITY_GENERIC_CHECK_PATH_FIXTURE)),
            _post(aeat_url("www6", LIVE_PARITY_SUBMIT_PATH_CANARY)),
        ),
        verdict=ParityResult(oracle_id="bad", cross_reference_id="test-policy", verdict="match", narrative="x"),
    )
    policy = _read_only_policy()

    with pytest.raises(RegistryValidationError, match="blocked by policy"):
        pre_flight_oracle_operations(oracle, policy, payload=b"", expected={})


def test_pre_flight_blocks_oracle_targeting_non_aeat_host() -> None:
    oracle = _CannedOracle(
        oracle_id="phisher",
        surface_kind="iva_id_check",
        operations=(_read_only_get("https://example.com/check"),),
        verdict=ParityResult(oracle_id="phisher", cross_reference_id="test-policy", verdict="match", narrative="x"),
    )
    policy = _read_only_policy()

    with pytest.raises(RegistryValidationError, match="not in allowed read-only hosts"):
        pre_flight_oracle_operations(oracle, policy, payload=b"", expected={})


def test_evaluate_returns_blocked_result_for_static_only_policy_when_oracle_plans_remote_operations() -> None:
    oracle = _CannedOracle(
        oracle_id="oracle",
        surface_kind="open_simulator",
        operations=(_read_only_get(aeat_url("www6", LIVE_PARITY_STATIC_REMOTE_PATH_FIXTURE)),),
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


def test_oracle_verify_payload_raises_when_planned_operation_blocked() -> None:
    oracle = _CannedOracle(
        oracle_id="bad-verify",
        surface_kind="pre_filing_validator",
        operations=(_post(aeat_url("www6", LIVE_PARITY_SUBMIT_PATH_CANARY)),),
        verdict=ParityResult(oracle_id="bad-verify", cross_reference_id="test-policy", verdict="match", narrative="x"),
    )
    policy = _read_only_policy()

    with pytest.raises(RegistryValidationError, match=r"policy|method|forbidden|operation"):
        oracle.verify_payload(policy, b"", expected={})


# ---------------------------------------------------------------------------
# ReplayPayload roundtrip tests (contract)
# ---------------------------------------------------------------------------


def test_replay_payload_accepts_well_formed_payload() -> None:
    """decode_replay_json_payload returns a typed ReplayPayload for valid input."""
    raw = b'{"observed": {"B01": "conforme", "B02": "no_conforme"}, "raw_evidence_locator": "https://example.com/r/1"}'
    result = decode_replay_json_payload(raw, surface_label="test surface")
    assert isinstance(result, ReplayPayload)
    assert result.observed == {"B01": "conforme", "B02": "no_conforme"}
    assert result.raw_evidence_locator == "https://example.com/r/1"


def test_replay_payload_accepts_payload_without_locator() -> None:
    """raw_evidence_locator is optional; absent key decodes cleanly."""
    raw = b'{"observed": {"X99": "ok"}}'
    result = decode_replay_json_payload(raw, surface_label="test surface")
    assert result.raw_evidence_locator is None
    assert dict(result.observed) == {"X99": "ok"}


def test_replay_payload_rejects_missing_observed_field() -> None:
    """model_validate raises ValidationError when 'observed' is absent."""
    with pytest.raises(ValidationError):
        ReplayPayload.model_validate({"raw_evidence_locator": None})


def test_replay_payload_rejects_observed_with_non_string_values() -> None:
    """strict=True rejects integer values in observed — no coercion."""
    with pytest.raises(ValidationError):
        ReplayPayload.model_validate({"observed": {"B01": 42}})


def test_replay_payload_rejects_observed_with_non_string_keys() -> None:
    """strict=True rejects non-string keys in observed mapping."""
    # JSON always produces str keys; the path that matters is Python-level
    # model_validate with a dict that has non-str keys.
    with pytest.raises(ValidationError):
        ReplayPayload.model_validate({"observed": {1: "value"}})


def test_replay_payload_rejects_extra_fields() -> None:
    """extra='forbid' rejects unknown top-level keys."""
    with pytest.raises(ValidationError):
        ReplayPayload.model_validate({"observed": {}, "unexpected_key": "x"})


def test_replay_payload_rejects_non_object_observed() -> None:
    """observed must be a mapping, not a list or scalar."""
    with pytest.raises(ValidationError):
        ReplayPayload.model_validate({"observed": ["a", "b"]})


def test_decode_replay_json_payload_rejects_non_utf8_bytes() -> None:
    """Non-UTF-8 bytes raise RegistryValidationError, not a bare codec error."""
    raw = b"\xff\xfe invalid utf-8"
    with pytest.raises(RegistryValidationError, match="UTF-8 JSON"):
        decode_replay_json_payload(raw, surface_label="test surface")


def test_decode_replay_json_payload_rejects_json_array() -> None:
    """A JSON array at the top level is rejected as not a JSON object."""
    raw = b'["observed", {}]'
    with pytest.raises(RegistryValidationError, match="JSON object"):
        decode_replay_json_payload(raw, surface_label="test surface")


def test_decode_replay_json_payload_rejects_invalid_json() -> None:
    """Malformed JSON raises RegistryValidationError."""
    raw = b"{not valid json"
    with pytest.raises(RegistryValidationError, match="UTF-8 JSON"):
        decode_replay_json_payload(raw, surface_label="test surface")


def test_replay_payload_anti_tautology() -> None:
    """Mutating the decoded payload's required field surfaces a real failure.

    Encodes the boundary contract: loading a payload with 'observed' deleted
    must NOT succeed. This proves the roundtrip test cannot silently pass
    when the schema is broken.
    """

    good = {"observed": {"B01": "ok"}}
    broken = {k: v for k, v in good.items() if k != "observed"}
    with pytest.raises(ValidationError):
        ReplayPayload.model_validate(broken)
    # Confirm the good payload does validate (proving the test isn't vacuous).
    result = ReplayPayload.model_validate(good)
    assert result.observed == {"B01": "ok"}
