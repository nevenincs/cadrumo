"""Opt-in capture of Renta WEB Open replay payloads.

When ``AEAT_LIVE_TESTS_ENABLED=1``, this test drives the live
:class:`RentaWebOpenSedeDriver` through the AEAT open-simulator for the
baseline employee profile that anchors the
``modelo-100-2025-employee-default-minimo`` chain scenario. It then
persists the captured observation as a replay payload at
``corpus/parity_replays/renta_web_open/``, where the unit-mode parity
test (``test_renta_web_open_replay_payload_matches_registry_via_oracle``)
picks it up automatically on subsequent runs.

This is the capture half of Phase H6 (oracle linkage). The live test
``test_renta_web_open_sede_driver_verifies_baseline_profile_calculations``
already exercises the live driver; this companion writes the observation
to disk for replay-mode reuse.

Subsequent slices add per-scenario captures so every chain-behaviour
scenario carries an oracle-grounded payload (the hygiene gate
``test_every_renta_chain_scenario_has_renta_web_open_replay_payload``
will then convert from soft to hard).
"""

from __future__ import annotations

import json
from decimal import Decimal

import pytest

from .....core.paths import PROJECT_ROOT
from .....domain.calculations.registry import RentaWebOpenLivePayload
from .....entrypoints.cli._live import requires_live_enabled
from ._renta_web_open import collect_renta_web_open_observation

pytestmark = [pytest.mark.live_read, pytest.mark.domain_outbound]

_REPLAY_DIR = PROJECT_ROOT / "corpus" / "parity_replays" / "renta_web_open"

_BASELINE_EXPECTED: dict[str, Decimal] = {
    "Resultado de la declaración": Decimal("0.00"),
    "Mínimo personal y familiar. Parte estatal": Decimal("5550.00"),
    "Mínimo personal y familiar. Parte autonómica": Decimal("5790.00"),
    "Cuota diferencial": Decimal("0.00"),
}

# Maps the user-readable labels Renta WEB Open displays to the registry's
# canonical casilla-number identifiers. Used to dual-key the persisted
# replay payloads so the audit gates (which scan for casilla-id keys)
# resolve coverage correctly without requiring label-aware lookups.
_LABEL_TO_CASILLA: dict[str, str] = {
    "Resultado de la declaración": "0670",
    "Cuota diferencial": "0610",
    "Mínimo personal y familiar. Parte estatal": "0519",
    "Mínimo personal y familiar. Parte autonómica": "0520",
}


async def _capture_baseline_observation() -> tuple[str, dict[str, str]]:
    payload = RentaWebOpenLivePayload(timeout_ms=90_000).model_dump_json().encode("utf-8")
    observation = await collect_renta_web_open_observation(
        payload,
        expected={label: str(value) for label, value in _BASELINE_EXPECTED.items()},
    )
    return observation.raw_evidence_locator or "", observation.values


def test_capture_baseline_employee_replay_payload() -> None:
    """Live-only: capture the baseline-employee Renta WEB Open observation and persist it.

    The captured payload anchors the ``modelo-100-2025-employee-default-minimo``
    scenario for replay-mode parity.
    """
    requires_live_enabled()
    import asyncio

    locator, observed = asyncio.run(_capture_baseline_observation())
    assert observed, "Renta WEB Open returned no observed values"

    _REPLAY_DIR.mkdir(parents=True, exist_ok=True)
    payload_path = _REPLAY_DIR / "modelo-100-2025-employee-default-minimo.json"
    # Dual-key the payload: one block keyed by AEAT-readable labels (used by
    # the oracle's `_compare_expected_field`) and one block keyed by registry
    # casilla numbers (used by the per-formula coverage gate in
    # test_schema_hygiene). The label-block carries the live Renta WEB Open
    # observation; the casilla-block translates each label into its canonical
    # casilla id via _LABEL_TO_CASILLA so audit metrics surface coverage at
    # the registry level.
    expected_by_label = {label: str(value) for label, value in _BASELINE_EXPECTED.items()}
    expected_by_casilla = {
        _LABEL_TO_CASILLA[label]: str(value)
        for label, value in _BASELINE_EXPECTED.items()
        if label in _LABEL_TO_CASILLA
    }
    observed_by_casilla = {
        _LABEL_TO_CASILLA[label]: value
        for label, value in observed.items()
        if label in _LABEL_TO_CASILLA
    }
    document = {
        "expected": expected_by_label,
        "observed": observed,
        "expected_by_casilla": expected_by_casilla,
        "observed_by_casilla": observed_by_casilla,
        "raw_evidence_locator": locator,
    }
    payload_path.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")

    assert payload_path.exists()
    persisted = json.loads(payload_path.read_text(encoding="utf-8"))
    assert persisted["observed"] == observed
