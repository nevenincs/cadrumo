"""The recorded ECB answers still match what the live Data Portal publishes.

Lane suites convert currency against the recording, so a recording that has
drifted from the published series would make them assert stale euro figures.
Every recorded request is re-issued against the live host and compared as the
provider reads it: the parsed daily observations, not the raw bytes.
"""

from __future__ import annotations

import pytest

from .....tests.live_gate import requires_live_enabled
from ..ecb_provider import https_fetch, parse_observations
from .recorded_ecb_rates import recorded_ecb_answers

pytestmark = [pytest.mark.aeat_live, pytest.mark.hex_outbound_adapter]


def test_every_recorded_answer_matches_the_live_series() -> None:
    requires_live_enabled()
    answers = recorded_ecb_answers()
    assert answers, "the recording is empty"

    drifted: list[str] = []
    for url, body in answers.items():
        live_body = https_fetch(url)
        assert live_body is not None, f"the recorded ECB series is no longer published: {url}"
        if parse_observations(live_body) != parse_observations(body):
            drifted.append(url)

    assert not drifted, f"{len(drifted)} recorded ECB answers no longer match the live series: {drifted[:3]}"
