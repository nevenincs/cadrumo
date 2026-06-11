"""Renta WEB Open replay parity for chain-behaviour scenarios.

Each replay payload at ``corpus/parity_replays/renta_web_open/`` is
loaded through :class:`RentaWebOpenReplayDriver`, fed to
:class:`RentaWebOpenOracle`, and asserted to match the registry's
computed casilla values for the corresponding synthetic scenario.

The test parametrizes over discovered payload files. When the
directory is empty the test collection is empty too; the
companion hygiene gate
``test_every_renta_chain_scenario_has_renta_web_open_replay_payload``
in :mod:`test_schema_hygiene` warns when scenarios lack payloads
that should exist.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from decimal import Decimal
from pathlib import Path

import pytest

from .....core.resources import bundled_path
from .....tests.aeat_literal_fixtures import aeat_host
from .._remote_state_guard import RemoteStateGuardPolicy, remote_state_policy_from_cross_reference
from .._renta_web_open_oracle import (
    RentaWebOpenOracle,
    RentaWebOpenReplayDriver,
)
from .._schema import LiveCrossReferenceDecision

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_REPLAY_DIR = bundled_path("corpus", "parity_replays", "renta_web_open")
_SEDE_HOST = aeat_host("sede")
_WWW2_HOST = aeat_host("www2")


def _discovered_payloads() -> list[Path]:
    if not _REPLAY_DIR.exists():
        return []
    return sorted(p for p in _REPLAY_DIR.glob("*.json"))


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


def _load_expected(payload_path: Path) -> Mapping[str, Decimal]:
    document = json.loads(payload_path.read_text(encoding="utf-8"))
    if "expected" not in document or not isinstance(document["expected"], dict):
        raise AssertionError(
            f"replay payload {payload_path.name!r} must declare an 'expected' object "
            f"that names the casilla values the registry must produce",
        )
    expected: dict[str, Decimal] = {}
    for casilla_id, value in document["expected"].items():
        if not isinstance(casilla_id, str) or not isinstance(value, str):
            raise AssertionError(f"replay payload {payload_path.name!r} expected entries must be string keyed strings")
        expected[casilla_id] = Decimal(value)
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
