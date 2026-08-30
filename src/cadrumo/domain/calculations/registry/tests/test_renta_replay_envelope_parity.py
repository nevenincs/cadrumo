"""The Renta corpus satisfies grounding and replay on the same terms.

The bundled Renta WEB Open captures are read by TWO contracts: the grounding
side validates them as :class:`RentaWebOpenReplayPayload` (a
``BundledOraclePayload``, evidence locator required, up to 1024 characters),
and the production ``RentaWebOpenReplayDriver`` decodes them through the
generic checker :class:`ReplayPayload` (locator optional, formerly capped at
512). One corpus, two disagreeing envelopes: a capture with a 596-character
locator grounded but failed replay, and a capture with no locator at all
reached the driver while grounding refused it.

The evidence-locator bound and the required-locator rule now have one
declaration, applied on both sides. These tests assert AGREEMENT rather than
either verdict on its own: a gate that only checked the driver would pass
again the moment the two bounds drifted apart in the other direction.

The expected-value map is deliberately NOT unified. A replay driver reads the
OBSERVED figures and receives expected ones as a separate argument, so a
hand-written non-corpus capture legitimately omits it; that asymmetry is a
contract difference with a reason, not drift.
"""

from __future__ import annotations

import json

import pytest

from .....core.casilla_id import CasillaId, validated_casilla_id
from ..external_grounding import (
    BUNDLED_ORACLE_EVIDENCE_LOCATOR_MAX_LENGTH,
    RentaWebOpenReplayPayload,
)
from ..renta_web_open_oracle import RentaWebOpenReplayDriver

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


_CASILLA: CasillaId = validated_casilla_id("0001", surface="renta replay envelope parity test casilla id")
_SHORT_LOCATOR = "corpus/aeat_official/renta_web_open/sample.json"
#: Longer than the generic replay envelope's former 512 cap, well inside the
#: bundled-oracle bound, so it separates the two contracts precisely.
_LONG_LOCATOR = "corpus/aeat_official/renta_web_open/" + ("x" * 560)


def _capture(**overrides: object) -> dict[str, object]:
    document: dict[str, object] = {
        "observed": {"Resultado": "1.00"},
        "observed_by_casilla_id": {_CASILLA: "1.00"},
        "expected": {"Resultado": "1.00"},
        "expected_by_casilla_id": {_CASILLA: "1.00"},
        "raw_evidence_locator": _SHORT_LOCATOR,
    }
    document.update(overrides)
    return document


def _grounding_accepts(document: dict[str, object]) -> bool:
    try:
        RentaWebOpenReplayPayload.model_validate(document)
    except Exception:  # any refusal is a refusal for this comparison
        return False
    return True


def _driver_accepts(document: dict[str, object]) -> bool:
    driver = RentaWebOpenReplayDriver()
    try:
        driver.collect_observation(json.dumps(document).encode("utf-8"), expected={})
    except Exception:  # any refusal is a refusal for this comparison
        return False
    return True


def test_long_locator_is_accepted_or_refused_by_both_contracts() -> None:
    """A grounding-valid locator longer than 512 must also survive replay."""
    document = _capture(raw_evidence_locator=_LONG_LOCATOR)

    assert len(_LONG_LOCATOR) > 512
    assert len(_LONG_LOCATOR) <= BUNDLED_ORACLE_EVIDENCE_LOCATOR_MAX_LENGTH
    assert _grounding_accepts(document) is _driver_accepts(document)
    assert _grounding_accepts(document) is True


def test_missing_locator_is_refused_by_both_contracts() -> None:
    """A capture with no evidence provenance must not reach the driver."""
    document = {key: value for key, value in _capture().items() if key != "raw_evidence_locator"}

    assert _grounding_accepts(document) is _driver_accepts(document)
    assert _driver_accepts(document) is False


def test_over_long_locator_is_refused_by_both_contracts() -> None:
    """Past the shared bound, both sides refuse — the cap is one declaration."""
    over_long = "x" * (BUNDLED_ORACLE_EVIDENCE_LOCATOR_MAX_LENGTH + 1)
    document = _capture(raw_evidence_locator=over_long)

    assert _grounding_accepts(document) is _driver_accepts(document)
    assert _driver_accepts(document) is False


def test_control_capture_is_accepted_by_both_contracts() -> None:
    """Anti-vacuity: a well-formed capture is accepted, not merely refused alike."""
    document = _capture()

    assert _grounding_accepts(document) is True
    assert _driver_accepts(document) is True
