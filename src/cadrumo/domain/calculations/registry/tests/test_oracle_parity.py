"""Real-adapter tests for the modelo-agnostic live-parity backend."""

from __future__ import annotations

from collections.abc import Mapping

import pytest
from pydantic import AnyUrl, ValidationError

from .....tests.aeat_literal_fixtures import (
    LIVE_PARITY_GENERIC_CHECK_PATH_FIXTURE,
    LIVE_PARITY_PRET_CHECK_PATH_FIXTURE,
    LIVE_PARITY_STATIC_REMOTE_PATH_FIXTURE,
    aeat_host,
    aeat_url,
)
from .._aeat_nif_iva_oracle import ORACLE_ID, AeatNifIvaCheckerOracle
from ..errors import RegistryValidationError
from .._groi_oracle import GROI_ORACLE_ID, GroiOracle
from .._live_parity import (
    LiveParityCatalogue,
    OracleEnvironment,
    OracleSurfaceKind,
    ParityFieldComparison,
    ParityResult,
    ReplayPayload,
    decode_replay_json_payload,
    evaluate_planned_operations,
    pre_flight_oracle_operations,
)
from .._remote_state_guard import RemoteOperation, RemoteStateGuardPolicy
from .._renta_web_open_oracle import RentaWebOpenOracle

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_WWW6_HOST = aeat_host("www6")


class _ScriptedOracle:
    """Real :class:`LiveParityOracle` implementation backed by canned operations.

    Feeds operator-supplied ``planned_operations`` into the real
    ``pre_flight_oracle_operations`` / ``evaluate_planned_operations``
    production functions under test -- those functions run unchanged on the
    canned plan, so a guard regression here is real, not a mock artefact.
    """

    def __init__(
        self,
        *,
        oracle_id: str,
        surface_kind: OracleSurfaceKind,
        operations: tuple[RemoteOperation, ...],
    ) -> None:
        self._oracle_id = oracle_id
        self._surface_kind: OracleSurfaceKind = surface_kind
        self._operations = operations

    @property
    def oracle_id(self) -> str:
        return self._oracle_id

    @property
    def surface_kind(self) -> OracleSurfaceKind:
        return self._surface_kind

    def planned_operations(self, payload: bytes, *, expected: Mapping[str, object]) -> tuple[RemoteOperation, ...]:
        return self._operations

    def verify_payload(
        self,
        policy: RemoteStateGuardPolicy,
        payload: bytes,
        *,
        expected: Mapping[str, object],
    ) -> ParityResult:
        raise NotImplementedError("not exercised by the pre-flight/evaluate tests below")


def _read_only_policy() -> RemoteStateGuardPolicy:
    return RemoteStateGuardPolicy(
        id="pre-flight-test-policy",
        evidence_tier="executable_parity_evidence",
        classification="open_simulator",
        allowed_hosts=(_WWW6_HOST,),
        synthetic_data_allowed=False,
        requires_authentication=False,
        requires_aeat_authorization=False,
    )


def _static_only_policy() -> RemoteStateGuardPolicy:
    return RemoteStateGuardPolicy(
        id="pre-flight-static-only-policy",
        evidence_tier="official_source_guidance",
        classification="static_official_only",
        allowed_hosts=(),
        synthetic_data_allowed=False,
        requires_authentication=False,
        requires_aeat_authorization=False,
    )


def _read_only_get(path: str) -> RemoteOperation:
    return RemoteOperation(kind="http", method="GET", url=AnyUrl(aeat_url("www6", path)))


def _post(path: str) -> RemoteOperation:
    return RemoteOperation(kind="http", method="POST", url=AnyUrl(aeat_url("www6", path)))


def test_pre_flight_passes_when_planned_operations_are_read_only() -> None:
    """``pre_flight_oracle_operations`` returns the plan when every step is read-only.

    Restores the coverage ``LIVE_PARITY_GENERIC_CHECK_PATH_FIXTURE`` lost when
    the 561-line ``test_live_parity.py`` (which exercised this exact function
    with a canned oracle) was deleted in favour of this file's much narrower
    predecessor -- ``pre_flight_oracle_operations`` stayed exported in
    ``_live_parity.__all__`` with zero test coverage in the interim.
    """
    oracle = _ScriptedOracle(
        oracle_id="pre-flight-read-only",
        surface_kind="iva_id_check",
        operations=(_read_only_get(LIVE_PARITY_GENERIC_CHECK_PATH_FIXTURE),),
    )
    operations = pre_flight_oracle_operations(oracle, _read_only_policy(), payload=b"", expected={})
    assert operations == (_read_only_get(LIVE_PARITY_GENERIC_CHECK_PATH_FIXTURE),)


def test_pre_flight_blocks_oracle_with_post_operation() -> None:
    """A planned POST is refused before any network call, naming the offending step."""
    oracle = _ScriptedOracle(
        oracle_id="pre-flight-post",
        surface_kind="pre_filing_validator",
        operations=(
            _read_only_get(LIVE_PARITY_GENERIC_CHECK_PATH_FIXTURE),
            _post(LIVE_PARITY_PRET_CHECK_PATH_FIXTURE),
        ),
    )
    with pytest.raises(RegistryValidationError, match="forbidden"):
        pre_flight_oracle_operations(oracle, _read_only_policy(), payload=b"", expected={})


def test_evaluate_planned_operations_returns_blocked_result_for_static_only_policy() -> None:
    """A static-only policy blocks every remote operation, even a benign GET.

    ``evaluate_planned_operations`` is the exception-free sibling of
    ``pre_flight_oracle_operations``; it returns a ``blocked`` verdict rather
    than raising, which this test proves by inspecting the returned value
    instead of catching an exception.
    """
    oracle = _ScriptedOracle(
        oracle_id="static-only-oracle",
        surface_kind="file_validator",
        operations=(_read_only_get(LIVE_PARITY_STATIC_REMOTE_PATH_FIXTURE),),
    )
    result = evaluate_planned_operations(oracle, _static_only_policy(), payload=b"", expected={})
    assert isinstance(result, ParityResult)
    assert result.verdict == "blocked"


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


def test_catalogue_register_and_lookup_round_trip_with_production_oracle() -> None:
    catalogue = LiveParityCatalogue()
    oracle = AeatNifIvaCheckerOracle()

    catalogue.register(oracle, environment=OracleEnvironment.PRODUCTION)

    assert catalogue.is_registered(ORACLE_ID)
    assert catalogue.ids() == (ORACLE_ID,)
    assert catalogue.lookup(ORACLE_ID) is oracle
    assert catalogue.environment_of(ORACLE_ID) == OracleEnvironment.PRODUCTION


def test_catalogue_rejects_duplicate_production_oracle() -> None:
    catalogue = LiveParityCatalogue()
    oracle = AeatNifIvaCheckerOracle()
    catalogue.register(oracle, environment=OracleEnvironment.PRODUCTION)

    with pytest.raises(RegistryValidationError, match="already registered"):
        catalogue.register(oracle, environment=OracleEnvironment.PRODUCTION)


def test_catalogue_lookup_unknown_id_raises() -> None:
    with pytest.raises(RegistryValidationError, match="unknown oracle_id"):
        LiveParityCatalogue().lookup("missing")


def test_catalogue_filters_concrete_oracles_by_environment() -> None:
    catalogue = LiveParityCatalogue()
    nif_iva = AeatNifIvaCheckerOracle()
    groi = GroiOracle()
    renta_web = RentaWebOpenOracle()
    catalogue.register(nif_iva, environment=OracleEnvironment.PRODUCTION)
    catalogue.register(groi, environment=OracleEnvironment.TEST_ENVIRONMENT)
    catalogue.register(renta_web, environment=OracleEnvironment.BOTH)

    renta_web_id = renta_web.oracle_id
    assert catalogue.ids() == tuple(sorted((ORACLE_ID, GROI_ORACLE_ID, renta_web_id)))
    assert catalogue.ids(environment=OracleEnvironment.PRODUCTION) == tuple(sorted((ORACLE_ID, renta_web_id)))
    assert catalogue.ids(environment=OracleEnvironment.TEST_ENVIRONMENT) == tuple(
        sorted((GROI_ORACLE_ID, renta_web_id))
    )
    assert catalogue.lookup(renta_web_id, environment=OracleEnvironment.PRODUCTION) is renta_web
    assert catalogue.lookup(renta_web_id, environment=OracleEnvironment.TEST_ENVIRONMENT) is renta_web

    with pytest.raises(RegistryValidationError, match="not available under requested environment"):
        catalogue.lookup(GROI_ORACLE_ID, environment=OracleEnvironment.PRODUCTION)
    with pytest.raises(RegistryValidationError, match="not available under requested environment"):
        catalogue.lookup(ORACLE_ID, environment=OracleEnvironment.TEST_ENVIRONMENT)


def test_oracle_environment_values_are_canonical_strings() -> None:
    assert tuple((member, str(member)) for member in OracleEnvironment) == (
        ("production", "production"),
        ("test_environment", "test_environment"),
        ("both", "both"),
    )


def test_replay_payload_accepts_well_formed_payload() -> None:
    raw = b'{"observed": {"B01": "conforme", "B02": "no_conforme"}, "raw_evidence_locator": "https://example.com/r/1"}'
    result = decode_replay_json_payload(raw, surface_label="test surface")
    assert isinstance(result, ReplayPayload)
    assert result.observed == {"B01": "conforme", "B02": "no_conforme"}
    assert result.raw_evidence_locator == "https://example.com/r/1"


def test_replay_payload_accepts_payload_without_locator() -> None:
    result = decode_replay_json_payload(b'{"observed": {"X99": "ok"}}', surface_label="test surface")
    assert result.raw_evidence_locator is None
    assert dict(result.observed) == {"X99": "ok"}


@pytest.mark.parametrize(
    "payload",
    (
        {"raw_evidence_locator": None},
        {"observed": {"B01": 42}},
        {"observed": {1: "value"}},
        {"observed": {}, "unexpected_key": "x"},
        {"observed": ["a", "b"]},
    ),
)
def test_replay_payload_rejects_invalid_shapes(payload: object) -> None:
    with pytest.raises(ValidationError):
        ReplayPayload.model_validate(payload)


@pytest.mark.parametrize(
    ("raw", "message"),
    (
        (b"\xff\xfe invalid utf-8", "UTF-8 JSON"),
        (b'["observed", {}]', "JSON object"),
        (b"{not valid json", "UTF-8 JSON"),
    ),
)
def test_decode_replay_json_payload_rejects_invalid_bytes(raw: bytes, message: str) -> None:
    with pytest.raises(RegistryValidationError, match=message):
        decode_replay_json_payload(raw, surface_label="test surface")
