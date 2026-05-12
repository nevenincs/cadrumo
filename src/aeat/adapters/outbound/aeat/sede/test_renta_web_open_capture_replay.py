"""Opt-in capture of Renta WEB Open replay payloads.

When ``AEAT_LIVE_TESTS_ENABLED=1``, these tests drive the live
:class:`RentaWebOpenSedeDriver` through the AEAT open-simulator for
each chain-behaviour scenario and persist the captured observation as
a replay payload at ``corpus/parity_replays/renta_web_open/``, where
the unit-mode parity test
(``test_renta_web_open_replay_payload_matches_registry_via_oracle``)
picks it up automatically on subsequent runs.

This is the capture half of Phase H6 (oracle linkage). Each scenario
declares the ``casilla_overrides`` it needs (e.g. ``{"0511": "2775.00"}``
for the mínimo-aggregation case) and the ``scrape_casillas`` list of
output casilla numbers the driver should record by navigating to each
casilla's form page via the "Buscar casilla" dialog.

Once every chain-behaviour scenario carries a replay payload, the
hygiene gate
``test_every_renta_chain_scenario_has_renta_web_open_replay_payload``
converts from soft to hard.
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
        _LABEL_TO_CASILLA[label]: value for label, value in observed.items() if label in _LABEL_TO_CASILLA
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


# Per-scenario casilla overrides + scrape lists. Each entry mirrors the
# matching ``_scenario_2025`` instance in
# ``src/aeat/domain/calculations/registry/test_renta_chain_behaviour.py``.
# The driver navigates into the editable form for each casilla in
# ``overrides``, fills the value, then reads each casilla in ``scrape``
# back off the form page after recomputation.
_SCENARIO_CAPTURES: tuple[tuple[str, dict[str, str], list[str]], ...] = (
    (
        "minimo-aggregation-estatal",
        {"0511": "2775.00", "0513": "1000.00", "0515": "500.00", "0517": "250.00"},
        ["0519"],
    ),
    (
        "minimo-clip-to-base-liquidable",
        {"0505": "1000.00", "0511": "2775.00", "0512": "2775.00"},
        ["0519", "0521", "0522"],
    ),
    (
        "base-imponible-with-negative-capital-gains",
        {"0003": "30000.00", "1585": "5000.00"},
        ["0432", "0435"],
    ),
    (
        "base-liquidable-with-reductions",
        {"0003": "40000.00", "0461": "3400.00", "0501": "1000.00"},
        ["0435", "0500"],
    ),
)


async def _capture_scenario_observation(
    overrides: dict[str, str],
    scrape: list[str],
) -> tuple[str, dict[str, str]]:
    """Drive the live simulator with per-scenario overrides + scrape list."""

    payload = (
        RentaWebOpenLivePayload(
            timeout_ms=90_000,
            casilla_overrides=overrides,
            scrape_casillas=scrape,
        )
        .model_dump_json()
        .encode("utf-8")
    )
    expected = {label: "0.00" for label in _BASELINE_EXPECTED}
    expected.update({casilla: "" for casilla in scrape})
    observation = await collect_renta_web_open_observation(payload, expected=expected)
    return observation.raw_evidence_locator or "", observation.values


@pytest.mark.parametrize(
    ("scenario_id", "overrides", "scrape"),
    _SCENARIO_CAPTURES,
    ids=[entry[0] for entry in _SCENARIO_CAPTURES],
)
def test_capture_chain_behaviour_scenario_replay_payload(
    scenario_id: str,
    overrides: dict[str, str],
    scrape: list[str],
) -> None:
    """Live-only: capture each chain-behaviour scenario's Renta WEB Open observation.

    Each captured payload anchors one ``_scenario_2025`` chain-behaviour
    case (declared in ``test_renta_chain_behaviour.py``) for replay-mode
    parity, closing the Phase H6 oracle-linkage gate.
    """

    requires_live_enabled()
    import asyncio

    locator, observed = asyncio.run(_capture_scenario_observation(overrides, scrape))
    assert observed, f"Renta WEB Open returned no observed values for {scenario_id}"

    _REPLAY_DIR.mkdir(parents=True, exist_ok=True)
    payload_path = _REPLAY_DIR / f"{scenario_id}.json"
    expected_by_casilla = {casilla: overrides.get(casilla, "") for casilla in scrape}
    observed_by_casilla = {casilla: observed[casilla] for casilla in scrape if casilla in observed}
    document = {
        "scenario_id": scenario_id,
        "casilla_overrides": overrides,
        "scrape_casillas": scrape,
        "expected_by_casilla": expected_by_casilla,
        "observed": observed,
        "observed_by_casilla": observed_by_casilla,
        "raw_evidence_locator": locator,
    }
    payload_path.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")

    assert payload_path.exists()
    persisted = json.loads(payload_path.read_text(encoding="utf-8"))
    assert persisted["observed"] == observed
