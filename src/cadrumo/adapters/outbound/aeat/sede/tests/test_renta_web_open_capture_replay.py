"""Opt-in capture of Renta WEB Open replay payloads.

When ``CADRUMO_LIVE_TESTS_ENABLED=1``, these tests drive the live
:class:`RentaWebOpenSedeDriver` through the AEAT open-simulator for
each chain-behaviour scenario and persist the captured observation as
a replay payload at ``corpus/parity_replays/renta_web_open/``, where
the unit-mode parity test
(``test_renta_web_open_replay_payload_matches_registry_via_oracle``)
picks it up automatically on subsequent runs.

This is the capture half of the oracle-linkage gate. Each scenario
declares canonical ``casilla.id`` keyed display overrides and scrape maps
that point each casilla at the Renta WEB summary label or display number
the driver should read.

Replay-mode parity loads the captured payloads through canonical
``expected_by_casilla_id`` / ``observed_by_casilla_id`` maps.
"""

from __future__ import annotations

import json
from decimal import Decimal

import pytest

from cadrumo.domain.calculations.registry.renta_web_open_oracle import (
    RentaWebOpenLivePayload,
    RentaWebOpenSyntheticProfile,
    serialize_renta_web_open_replay_decimal,
)

from ......core import CasillaId, validated_casilla_id
from ......core.resources import bundled_path
from ......tests.live_gate import requires_live_enabled
from .._renta_web_open import collect_renta_web_open_observation

pytestmark = [pytest.mark.aeat_live, pytest.mark.hex_outbound_adapter]

_REPLAY_DIR = bundled_path("corpus", "parity_replays", "renta_web_open")
_RENTA_RESULTADO_CASILLA: CasillaId = validated_casilla_id("0670", surface="_RENTA_RESULTADO_CASILLA")
_RENTA_CUOTA_DIFERENCIAL_CASILLA: CasillaId = validated_casilla_id(
    "0610",
    surface="_RENTA_CUOTA_DIFERENCIAL_CASILLA",
)
_RENTA_MINIMO_ESTATAL_CASILLA: CasillaId = validated_casilla_id("0519", surface="_RENTA_MINIMO_ESTATAL_CASILLA")
_RENTA_MINIMO_AUTONOMICO_CASILLA: CasillaId = validated_casilla_id(
    "0520",
    surface="_RENTA_MINIMO_AUTONOMICO_CASILLA",
)

_BASELINE_EXPECTED: dict[str, Decimal] = {
    "Resultado de la declaración": Decimal("0.00"),
    "Mínimo personal y familiar. Parte estatal": Decimal("5550.00"),
    "Mínimo personal y familiar. Parte autonómica": Decimal("5790.00"),
    "Cuota diferencial": Decimal("0.00"),
}

# Maps the user-readable labels Renta WEB Open displays to the registry's
# canonical casilla ids. Used to dual-key the persisted replay payloads
# so the audit gates (which scan for casilla-id keys)
# resolve coverage correctly without requiring label-aware lookups.
_LABEL_TO_CASILLA: dict[str, CasillaId] = {
    "Resultado de la declaración": _RENTA_RESULTADO_CASILLA,
    "Cuota diferencial": _RENTA_CUOTA_DIFERENCIAL_CASILLA,
    "Mínimo personal y familiar. Parte estatal": _RENTA_MINIMO_ESTATAL_CASILLA,
    "Mínimo personal y familiar. Parte autonómica": _RENTA_MINIMO_AUTONOMICO_CASILLA,
}
_CASILLA_TO_LABEL: dict[CasillaId, str] = {casilla_id: label for label, casilla_id in _LABEL_TO_CASILLA.items()}


def _casilla_id_from_payload(value: object, *, section_name: str) -> CasillaId:
    try:
        return validated_casilla_id(value, surface="test casilla id")
    except ValueError as exc:
        raise AssertionError(f"{section_name} key {value!r} is not a canonical casilla.id") from exc


async def _capture_baseline_observation() -> tuple[str, dict[CasillaId, str]]:
    payload = (
        RentaWebOpenLivePayload(
            timeout_ms=90_000,
            summary_labels_by_casilla_id=_CASILLA_TO_LABEL,
        )
        .model_dump_json()
        .encode("utf-8")
    )
    observation = await collect_renta_web_open_observation(
        payload,
        expected={
            _LABEL_TO_CASILLA[label]: str(value)
            for label, value in _BASELINE_EXPECTED.items()
            if label in _LABEL_TO_CASILLA
        },
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
    # Dual-key the payload: one block keyed by AEAT-readable labels for audit
    # readability and one block keyed by registry casilla ids for the oracle
    # matcher and coverage gates. The label block is legacy evidence only.
    expected_by_label = {label: str(value) for label, value in _BASELINE_EXPECTED.items()}
    expected_by_casilla_id = {
        _LABEL_TO_CASILLA[label]: str(value)
        for label, value in _BASELINE_EXPECTED.items()
        if label in _LABEL_TO_CASILLA
    }
    observed_by_label = {
        label: observed[casilla_id] for casilla_id, label in _CASILLA_TO_LABEL.items() if casilla_id in observed
    }
    document = {
        "expected": expected_by_label,
        "observed": observed_by_label,
        "expected_by_casilla_id": expected_by_casilla_id,
        "observed_by_casilla_id": observed,
        "raw_evidence_locator": locator,
    }
    payload_path.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")

    assert payload_path.exists()
    persisted = json.loads(payload_path.read_text(encoding="utf-8"))
    assert {
        _casilla_id_from_payload(casilla_id, section_name="observed_by_casilla_id"): value
        for casilla_id, value in persisted["observed_by_casilla_id"].items()
    } == observed


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


async def _capture_profile_variant_observation(profile_overrides: dict[str, str]) -> tuple[str, dict[CasillaId, str]]:
    """Drive the live simulator with a varied synthetic profile."""

    payload = (
        RentaWebOpenLivePayload(
            timeout_ms=90_000,
            profile=RentaWebOpenSyntheticProfile.model_validate(profile_overrides),
            summary_labels_by_casilla_id=_CASILLA_TO_LABEL,
        )
        .model_dump_json()
        .encode("utf-8")
    )
    expected = dict.fromkeys(_CASILLA_TO_LABEL, "0.00")
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
    expected_by_label = {
        label: serialize_renta_web_open_replay_decimal(observed[casilla_id])
        for casilla_id, label in _CASILLA_TO_LABEL.items()
        if casilla_id in observed
    }
    expected_by_casilla_id = {
        casilla_id: serialize_renta_web_open_replay_decimal(value) for casilla_id, value in observed.items()
    }
    observed_by_label = {
        label: observed[casilla_id] for casilla_id, label in _CASILLA_TO_LABEL.items() if casilla_id in observed
    }
    document = {
        "scenario_id": scenario_id,
        "profile_overrides": profile_overrides,
        "expected": expected_by_label,
        "observed": observed_by_label,
        "expected_by_casilla_id": expected_by_casilla_id,
        "observed_by_casilla_id": observed,
        "raw_evidence_locator": locator,
    }
    payload_path.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
    assert payload_path.exists()
