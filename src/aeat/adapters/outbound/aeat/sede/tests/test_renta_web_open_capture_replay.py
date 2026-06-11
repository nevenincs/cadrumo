"""Opt-in capture of Renta WEB Open replay payloads.

When ``AEAT_LIVE_TESTS_ENABLED=1``, these tests drive the live
:class:`RentaWebOpenSedeDriver` through the AEAT open-simulator for
each chain-behaviour scenario and persist the captured observation as
a replay payload at ``corpus/parity_replays/renta_web_open/``, where
the unit-mode parity test
(``test_renta_web_open_replay_payload_matches_registry_via_oracle``)
picks it up automatically on subsequent runs.

This is the capture half of the oracle-linkage gate. Each scenario
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

from ......core.resources import bundled_path
from ......domain.calculations.registry import RentaWebOpenLivePayload, RentaWebOpenSyntheticProfile
from ......tests.live_gate import requires_live_enabled
from .._renta_web_open import collect_renta_web_open_observation

pytestmark = [pytest.mark.aeat_live, pytest.mark.hex_outbound_adapter]

_REPLAY_DIR = bundled_path("corpus", "parity_replays", "renta_web_open")

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
    scenario_id = "modelo-100-2025-employee-default-minimo"
    payload_path = _REPLAY_DIR / f"{scenario_id}.json"
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


# Profile-variant scenarios that vary the synthetic identification
# (autonomous_community) without touching casilla inputs. The simulator
# recomputes mínimos personal y familiar (parte autonómica) based on
# each CCAA's autonomic schedule; each variant lands a distinct replay
# payload anchoring the corresponding modelo-100-2025-* chain.
# CASADO/A and other status variants need spouse profile data the
# default synthetic profile doesn't provide; they're omitted until the
# profile schema gains spouse fields.
_PROFILE_VARIANT_CAPTURES: tuple[tuple[str, dict[str, str]], ...] = (
    (
        "modelo-100-2025-employee-default-minimo-madrid",
        {"autonomous_community": "MADRID"},
    ),
    (
        "modelo-100-2025-employee-default-minimo-cataluna",
        {"autonomous_community": "CATALUÑA"},
    ),
    (
        "modelo-100-2025-employee-default-minimo-galicia",
        {"autonomous_community": "GALICIA"},
    ),
    (
        "modelo-100-2025-employee-default-minimo-canarias",
        {"autonomous_community": "CANARIAS"},
    ),
)


async def _capture_profile_variant_observation(profile_overrides: dict[str, str]) -> tuple[str, dict[str, str]]:
    """Drive the live simulator with a varied synthetic profile."""

    payload = (
        RentaWebOpenLivePayload(
            timeout_ms=90_000,
            profile=RentaWebOpenSyntheticProfile.model_validate(profile_overrides),
        )
        .model_dump_json()
        .encode("utf-8")
    )
    expected = dict.fromkeys(_BASELINE_EXPECTED, "0.00")
    observation = await collect_renta_web_open_observation(payload, expected=expected)
    return observation.raw_evidence_locator or "", observation.values


@pytest.mark.parametrize(
    ("scenario_id", "profile_overrides"),
    _PROFILE_VARIANT_CAPTURES,
    ids=[entry[0] for entry in _PROFILE_VARIANT_CAPTURES],
)
def test_capture_profile_variant_replay_payload(
    scenario_id: str,
    profile_overrides: dict[str, str],
) -> None:
    """Live-only: capture each profile-variant scenario's Renta WEB Open observation.

    Each variant exercises a different CCAA / civil status / age axis of
    the synthetic profile. The simulator produces distinct mínimos that
    anchor per-CCAA replay payloads under
    ``corpus/parity_replays/renta_web_open/``.
    """

    requires_live_enabled()
    import asyncio

    locator, observed = asyncio.run(_capture_profile_variant_observation(profile_overrides))
    assert observed, f"Renta WEB Open returned no observed values for {scenario_id}"

    _REPLAY_DIR.mkdir(parents=True, exist_ok=True)
    payload_path = _REPLAY_DIR / f"{scenario_id}.json"
    # The live observation IS the oracle truth for this variant — derive
    # the expected block from the observed Spanish-formatted decimals so
    # the replay parity test asserts registry == AEAT for the same
    # profile inputs. (The baseline default values in _BASELINE_EXPECTED
    # only apply to the default-profile capture; CCAA variants produce
    # different autonomic mínimos.)
    expected_by_label = {label: _parse_spanish_decimal(value) for label, value in observed.items()}
    expected_by_casilla = {
        _LABEL_TO_CASILLA[label]: _parse_spanish_decimal(value)
        for label, value in observed.items()
        if label in _LABEL_TO_CASILLA
    }
    observed_by_casilla = {
        _LABEL_TO_CASILLA[label]: value for label, value in observed.items() if label in _LABEL_TO_CASILLA
    }
    document = {
        "scenario_id": scenario_id,
        "profile_overrides": profile_overrides,
        "expected": expected_by_label,
        "observed": observed,
        "expected_by_casilla": expected_by_casilla,
        "observed_by_casilla": observed_by_casilla,
        "raw_evidence_locator": locator,
    }
    payload_path.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
    assert payload_path.exists()


def _parse_spanish_decimal(value: str) -> str:
    """Convert a Spanish-formatted decimal ("5.956,65") to plain form ("5956.65")."""

    return value.replace(".", "").replace(",", ".")
