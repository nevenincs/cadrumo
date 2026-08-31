"""Renta WEB Open replay parity for chain-behaviour scenarios.

Each replay payload at ``corpus/parity_replays/renta_web_open/`` is
loaded through :class:`RentaWebOpenReplayDriver`, fed to
:class:`RentaWebOpenOracle`, and asserted to match the registry's
computed casilla values for the corresponding synthetic scenario.

The test parametrizes over discovered payload files. When the
directory is empty the test collection is empty too; the formula-target
coverage gate in :mod:`test_schema_hygiene` validates canonical
``expected_by_casilla_id`` / ``observed_by_casilla_id`` replay keys.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from decimal import Decimal
from pathlib import Path

import pytest

from .....core.casilla_id import CasillaId, validated_casilla_id
from .....core.directory_scan import scan_directory
from .....core.resources._boundary import bundled_path
from .....tests.aeat_literal_fixtures import aeat_host
from ..remote_state_guard import RemoteStateGuardPolicy, remote_state_policy_from_cross_reference
from ..renta_web_open_oracle import (
    RentaWebOpenOracle,
    RentaWebOpenReplayDriver,
)
from ..schema_verification import LiveCrossReferenceDecision

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_REPLAY_DIR = bundled_path("corpus", "parity_replays", "renta_web_open")
_SEDE_HOST = aeat_host("sede")
_WWW2_HOST = aeat_host("www2")


def _discovered_payloads() -> tuple[Path, ...]:
    return scan_directory(_REPLAY_DIR, pattern="*.json")


def _open_simulator_policy() -> RemoteStateGuardPolicy:
    decision = LiveCrossReferenceDecision(
        id="modelo-100-renta-web-open",
        evidence_tier="executable_parity_evidence",
        surface="open_simulator",
        guard_policy_id="modelo-100-renta-web-open-read-only",
        allowed_hosts=(_SEDE_HOST, _WWW2_HOST),
        allowed_methods=("GET", "POST"),
        forbidden_actions=(
            "authenticated-renta-web",
            "fiscal-data-read",
            "borrador-read",
            "filed-declaration-read",
            "server-side-save",
            "signing",
            "presentation",
            "payment",
            "amendment",
            "cancellation",
            "document-submission",
            "declaration-submission",
        ),
        synthetic_data_allowed=False,
        requires_authentication=False,
        requires_aeat_authorization=False,
        legal_refs=("ley-35-2006:art-99",),
        source_refs=("aeat-renta-2025-manual-parte1",),
    )
    return remote_state_policy_from_cross_reference(decision)


def _casilla_id_from_replay_key(value: object, *, payload_path: Path) -> CasillaId:
    try:
        return validated_casilla_id(value, surface="test casilla id")
    except ValueError as exc:
        raise AssertionError(
            f"replay payload {payload_path.name!r} expected_by_casilla_id key {value!r} is not a canonical casilla.id",
        ) from exc


def _load_expected(payload_path: Path) -> Mapping[CasillaId, Decimal]:
    document = json.loads(payload_path.read_text(encoding="utf-8"))
    if "expected_by_casilla_id" not in document or not isinstance(document["expected_by_casilla_id"], dict):
        raise AssertionError(
            f"replay payload {payload_path.name!r} must declare an 'expected_by_casilla_id' object "
            f"keyed by canonical casilla.id values",
        )
    expected: dict[CasillaId, Decimal] = {}
    for casilla_id, value in document["expected_by_casilla_id"].items():
        if not isinstance(value, str):
            raise AssertionError(
                f"replay payload {payload_path.name!r} expected_by_casilla_id entries must be string values",
            )
        expected[_casilla_id_from_replay_key(casilla_id, payload_path=payload_path)] = Decimal(value)
    return expected


@pytest.mark.parametrize(
    "payload_path",
    _discovered_payloads(),
    ids=lambda path: path.stem if isinstance(path, Path) else "no-payloads",
)
def test_renta_web_open_replay_payload_matches_registry_via_oracle(payload_path: Path) -> None:
    """Each replay payload must verify-match through ``RentaWebOpenOracle``.

    The payload's ``expected`` mapping declares which casilla values the
    registry is asserting. The payload's ``observed`` mapping carries the
    AEAT-captured values. The oracle compares them and the test asserts the
    overall verdict is ``match``.
    """

    expected = _load_expected(payload_path)
    payload_bytes = payload_path.read_bytes()
    oracle = RentaWebOpenOracle(driver=RentaWebOpenReplayDriver())
    policy = _open_simulator_policy()
    result = oracle.verify_payload(policy, payload_bytes, expected=dict(expected))

    assert result.verdict == "match", (
        f"replay payload {payload_path.name!r} did not match the registry; "
        f"narrative: {result.narrative}; fields: {result.fields}"
    )
