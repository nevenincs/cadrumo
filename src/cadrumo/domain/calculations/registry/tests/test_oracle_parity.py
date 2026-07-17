"""Real-adapter tests for the modelo-agnostic live-parity backend."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from .._aeat_nif_iva_oracle import ORACLE_ID, AeatNifIvaCheckerOracle
from .._errors import RegistryValidationError
from .._groi_oracle import GROI_ORACLE_ID, GroiOracle
from .._live_parity import (
    LiveParityCatalogue,
    OracleEnvironment,
    ParityFieldComparison,
    ParityResult,
    ReplayPayload,
    decode_replay_json_payload,
)
from .._renta_web_open_oracle import RentaWebOpenOracle

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


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
