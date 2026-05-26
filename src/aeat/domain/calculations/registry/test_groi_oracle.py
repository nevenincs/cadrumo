"""Offline contract tests for the GROI Spanish-ROI registry oracle.

Mirrors :mod:`test_aeat_nif_iva_oracle`: exercises the LiveParityOracle
Protocol conformance, planned-operations enumeration, replay-driver
JSON round-trip, oracle-with-replay verify_payload returning the
expected ParityResult shape, oracle-without-driver returning
``unverifiable``, and policy-blocked returning ``blocked``.

The replay payloads use the same JSON shape the IXVI replay adapter
uses so a calculation engine can drive both oracles uniformly.
"""

from __future__ import annotations

import pytest
from pydantic import AnyUrl

from aeat.core.config import Settings

from ._errors import RegistryValidationError
from ._groi_oracle import (
    AEAT_GROI_URL,
    GROI_ORACLE_ID,
    GroiObservation,
    GroiOracle,
    GroiReplayDriver,
    register_default,
)
from ._live_parity import LiveParityCatalogue, LiveParityOracle
from ._remote_state_guard import (
    AEAT_WRITE_FORBIDDEN_ACTIONS,
    RemoteOperation,
    RemoteStateGuardPolicy,
    assert_remote_operation_allowed,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def _aeat_policy() -> RemoteStateGuardPolicy:
    # AEAT-hosted policies must not advertise synthetic input per the
    # no-synthetic-sede-live-surfaces ADR.
    return RemoteStateGuardPolicy(
        id="modelo-349-groi-spanish-roi-check",
        evidence_tier="executable_parity_evidence",
        classification="open_simulator",
        allowed_hosts=("www2.agenciatributaria.gob.es",),
        allowed_browser_action_patterns=(
            Settings.external_constants().aeat.live_safety.consult_oracle_browser_action_patterns
        ),
        forbidden_actions=AEAT_WRITE_FORBIDDEN_ACTIONS,
        synthetic_data_allowed=False,
        requires_authentication=False,
        requires_aeat_authorization=False,
    )


def _wrong_host_policy() -> RemoteStateGuardPolicy:
    return RemoteStateGuardPolicy(
        id="wrong-host",
        evidence_tier="executable_parity_evidence",
        classification="open_simulator",
        allowed_hosts=("sede.agenciatributaria.gob.es",),
        forbidden_actions=AEAT_WRITE_FORBIDDEN_ACTIONS,
        synthetic_data_allowed=False,
        requires_authentication=False,
        requires_aeat_authorization=False,
    )


def test_oracle_satisfies_live_parity_oracle_protocol() -> None:
    oracle = GroiOracle()
    assert isinstance(oracle, LiveParityOracle)
    assert oracle.oracle_id == GROI_ORACLE_ID
    assert oracle.surface_kind == "vat_id_check"


def test_oracle_url_stays_inside_aeat_host_pinning_suffix() -> None:
    """The form URL is on www2.agenciatributaria.gob.es; suffix-pinning still covers it."""

    assert str(AEAT_GROI_URL).startswith("https://www2.agenciatributaria.gob.es/")
    assert str(AEAT_GROI_URL).endswith("/wlpl/GROI-JDIT/ConsultaOperadorSedeGroiServlet")


def test_planned_operations_returns_form_open_per_nif_then_discard() -> None:
    oracle = GroiOracle()
    operations = oracle.planned_operations(
        b"",
        expected={"A28015865": "valid", "B12345678": "invalid"},
    )

    # Five steps: form GET, open-form, two per-NIF checks (sorted), discard.
    assert len(operations) == 5
    assert operations[0].kind == "http"
    assert operations[0].method == "GET"
    assert operations[0].url == AEAT_GROI_URL
    assert operations[1].kind == "browser_action"
    assert operations[1].action == "open-groi-form"
    assert operations[2].action == "check-nif-A28015865"
    assert operations[3].action == "check-nif-B12345678"
    assert operations[4].action == "discard-session"


def test_planned_operations_rejects_empty_expected() -> None:
    oracle = GroiOracle()
    with pytest.raises(RegistryValidationError, match="at least one expected NIF"):
        oracle.planned_operations(b"", expected={})


def test_verify_payload_without_driver_returns_unverifiable_after_guard_preflight() -> None:
    oracle = GroiOracle()
    policy = _aeat_policy()

    result = oracle.verify_payload(policy, b"", expected={"A28015865": "valid"})

    assert result.verdict == "unverifiable"
    assert result.oracle_id == GROI_ORACLE_ID
    assert result.cross_reference_id == policy.id
    assert "no executable driver configured" in result.narrative


def test_groi_policy_rejects_unclassified_browser_action() -> None:
    with pytest.raises(RegistryValidationError, match="explicit read-only allow-list"):
        assert_remote_operation_allowed(
            _aeat_policy(),
            RemoteOperation(kind="browser_action", action="new-unreviewed-groi-click"),
        )


def test_verify_payload_reports_guard_block_when_aeat_host_not_in_policy() -> None:
    oracle = GroiOracle()
    policy = _wrong_host_policy()

    result = oracle.verify_payload(policy, b"", expected={"A28015865": "valid"})

    assert result.verdict == "blocked"
    assert result.cross_reference_id == policy.id
    assert "blocked by remote-state guard" in result.narrative


def test_verify_payload_compares_replay_observations_to_expected_verdicts() -> None:
    """Replay driver round-trips JSON; oracle compares per-NIF and emits match/mismatch."""

    oracle = GroiOracle(driver=GroiReplayDriver())
    policy = _aeat_policy()
    payload = (
        b'{"observed": {"A28015865": "valid", "B12345678": "invalid"}, '
        b'"raw_evidence_locator": "corpus/aeat_official/groi_response_samples/valid_telefonica_a28015865.txt"}'
    )

    result = oracle.verify_payload(
        policy,
        payload,
        expected={"A28015865": "valid", "B12345678": "valid"},
    )

    assert result.verdict == "mismatch"
    assert result.raw_evidence_locator == ("corpus/aeat_official/groi_response_samples/valid_telefonica_a28015865.txt")
    assert [(field.name, field.verdict) for field in result.fields] == [
        ("A28015865", "match"),
        ("B12345678", "mismatch"),
    ]


def test_verify_payload_match_when_all_observations_agree() -> None:
    oracle = GroiOracle(driver=GroiReplayDriver())
    policy = _aeat_policy()
    payload = b'{"observed": {"A28015865": "valid"}}'

    result = oracle.verify_payload(policy, payload, expected={"A28015865": "valid"})

    assert result.verdict == "match"
    assert len(result.fields) == 1
    assert result.fields[0].verdict == "match"


def test_verify_payload_unverifiable_when_replay_payload_is_malformed() -> None:
    oracle = GroiOracle(driver=GroiReplayDriver())
    policy = _aeat_policy()

    result = oracle.verify_payload(policy, b"not-json", expected={"A28015865": "valid"})

    assert result.verdict == "unverifiable"
    assert "could not produce comparable observations" in result.narrative


def test_replay_driver_rejects_payload_without_observed_object() -> None:
    driver = GroiReplayDriver()
    with pytest.raises(RegistryValidationError, match="observed object"):
        driver.collect_observation(b'{"raw_evidence_locator": "x"}', expected={})


def test_replay_driver_rejects_non_string_observed_values() -> None:
    driver = GroiReplayDriver()
    with pytest.raises(RegistryValidationError, match="string-keyed strings"):
        driver.collect_observation(b'{"observed": {"A28015865": 1}}', expected={})


def test_observation_model_normalises_nif_uppercase_and_verdict_lowercase() -> None:
    observation = GroiObservation(values={"a28015865": "VALID"})
    assert observation.values == {"A28015865": "valid"}


def test_observation_model_rejects_blank_keys_or_values() -> None:
    with pytest.raises(ValueError, match="blank"):
        GroiObservation(values={"": "valid"})


def test_register_default_under_production_environment() -> None:
    catalogue = LiveParityCatalogue()
    register_default(catalogue)

    assert catalogue.is_registered(GROI_ORACLE_ID)
    assert catalogue.environment_of(GROI_ORACLE_ID) == "production"
    assert catalogue.lookup(GROI_ORACLE_ID, environment="production").oracle_id == GROI_ORACLE_ID


def test_register_default_test_environment_classification_supported() -> None:
    catalogue = LiveParityCatalogue()
    register_default(catalogue, environment="test_environment")

    assert catalogue.environment_of(GROI_ORACLE_ID) == "test_environment"
    with pytest.raises(RegistryValidationError, match=r"environment|production|test_environment|oracle"):
        catalogue.lookup(GROI_ORACLE_ID, environment="production")


# ---------------------------------------------------------------------------
# HARD MANDATE: AEAT writes are PERMANENTLY FORBIDDEN. Every GROI guard
# policy must reject every fabricated write-class operation. The tests below
# prove the read-only invariant by construction — they exercise the guard
# directly with deliberately malformed write operations and confirm
# RegistryValidationError fires before any browser interaction could occur.
# ---------------------------------------------------------------------------


def test_groi_planned_operations_emit_zero_write_class_action_labels() -> None:
    """The oracle's enumerated operations must contain no AEAT write-class action label."""

    oracle = GroiOracle()
    operations = oracle.planned_operations(
        b"",
        expected={"A28015865": "valid", "B12345678": "valid"},
    )
    for operation in operations:
        action = (operation.action or "").lower()
        for forbidden in AEAT_WRITE_FORBIDDEN_ACTIONS:
            assert forbidden.lower() not in action, (operation, forbidden)


def test_groi_planned_operations_emit_only_read_only_http_methods() -> None:
    """Every kind='http' operation must use GET / HEAD / OPTIONS — never a write method."""

    oracle = GroiOracle()
    operations = oracle.planned_operations(b"", expected={"A28015865": "valid"})
    for operation in operations:
        if operation.kind == "http":
            assert operation.method in {"GET", "HEAD", "OPTIONS"}, operation


@pytest.mark.parametrize("forbidden_label", AEAT_WRITE_FORBIDDEN_ACTIONS)
def test_guard_blocks_fabricated_write_class_browser_action_under_groi_policy(forbidden_label: str) -> None:
    """The guard rejects every write-class action label the GROI policy declares forbidden."""

    fabricated = RemoteOperation(kind="browser_action", action=f"trigger-{forbidden_label}-on-aeat")
    with pytest.raises(RegistryValidationError, match="forbidden action"):
        assert_remote_operation_allowed(_aeat_policy(), fabricated)


@pytest.mark.parametrize(
    "forbidden_token",
    ("submit", "send", "post", "save", "sign", "payment", "presentar", "enviar", "firmar"),
)
def test_guard_blocks_fabricated_browser_action_carrying_forbidden_token(forbidden_token: str) -> None:
    """The guard's global forbidden-token set blocks any action label containing a write verb."""

    fabricated = RemoteOperation(kind="browser_action", action=f"groi-{forbidden_token}-form-data")
    with pytest.raises(RegistryValidationError, match="forbidden"):
        assert_remote_operation_allowed(_aeat_policy(), fabricated)


def test_guard_blocks_fabricated_http_post_to_aeat_under_groi_policy() -> None:
    """An HTTP POST to AEAT (write method) is rejected before any network call."""

    fabricated = RemoteOperation(
        kind="http",
        method="POST",
        url=AEAT_GROI_URL,
    )
    with pytest.raises(RegistryValidationError, match="write method"):
        assert_remote_operation_allowed(_aeat_policy(), fabricated)


def test_guard_blocks_fabricated_http_put_to_aeat_under_groi_policy() -> None:
    """PUT, DELETE, PATCH — every write method is blocked, not just POST."""

    for method in ("PUT", "DELETE", "PATCH"):
        fabricated = RemoteOperation(kind="http", method=method, url=AEAT_GROI_URL)
        with pytest.raises(RegistryValidationError, match="write method"):
            assert_remote_operation_allowed(_aeat_policy(), fabricated)


def test_guard_blocks_http_get_to_aeat_host_outside_policy_allowed_hosts() -> None:
    """Even a GET to a non-allow-listed AEAT host is rejected."""

    fabricated = RemoteOperation(
        kind="http",
        method="GET",
        url=AnyUrl("https://www99.agenciatributaria.gob.es/some/forbidden/path"),
    )
    with pytest.raises(RegistryValidationError, match="not in allowed read-only hosts"):
        assert_remote_operation_allowed(_aeat_policy(), fabricated)


def test_groi_oracle_verify_payload_returns_blocked_on_fabricated_write_intent() -> None:
    """Top-level oracle Protocol returns verdict=blocked rather than letting a write reach AEAT.

    The guard fence is the contract. Even if a future driver mislabels an
    operation, the oracle's verify_payload runs the guard preflight first
    and returns a ParityResult(verdict='blocked') — no Playwright code runs,
    no network call leaves the process.
    """

    # Hand-craft a policy whose forbidden_actions catches the GROI driver's
    # check-nif label, simulating a "future-mislabeled" scenario.
    paranoid_policy = RemoteStateGuardPolicy(
        id="paranoid-policy",
        evidence_tier="executable_parity_evidence",
        classification="open_simulator",
        allowed_hosts=("www2.agenciatributaria.gob.es",),
        forbidden_actions=(*AEAT_WRITE_FORBIDDEN_ACTIONS, "check-nif"),
        synthetic_data_allowed=False,
        requires_authentication=False,
        requires_aeat_authorization=False,
    )
    oracle = GroiOracle()
    result = oracle.verify_payload(paranoid_policy, b"", expected={"A28015865": "valid"})

    assert result.verdict == "blocked"
    assert "blocked by remote-state guard" in result.narrative
    assert result.fields == ()
