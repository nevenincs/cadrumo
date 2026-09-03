"""``aeat app registry replay-parity`` end-to-end, plus its catalogue coverage.

The command replays AEAT's own bundled Renta WEB Open captures through the
parity oracle offline. These tests drive the live parser and the real registry
authority; the only thing asserted about the network is that the command needs
none of it.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from ....core.i18n.render import tr
from ....tests.cli_runner import invoke_cached_cli

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_SUPPORTED_LOCALES: tuple[str, ...] = ("en", "es", "ca", "hu")

_METRIC_KEYS: tuple[str, ...] = (
    "replay_verdict",
    "replay_oracle_id",
    "replay_cross_reference_id",
    "replay_guard_policy_id",
    "replay_registry_validated",
    "replay_payload_count",
    "replay_compared_field_count",
    "replay_matched_payload_count",
    "replay_mismatched_payload_count",
    "replay_unverifiable_payload_count",
    "replay_blocked_payload_count",
)

_TRANSLATION_KEYS: tuple[str, ...] = (
    "cli.registry.replay_parity_help",
    *(f"cli.registry.metrics.{key}" for key in _METRIC_KEYS),
)


@pytest.fixture(scope="module")
def replay_parity_envelope() -> dict[str, Any]:
    """Invoke the command once and return its parsed JSON envelope."""
    result = invoke_cached_cli(["--format", "json", "app", "registry", "replay-parity"])
    assert result.exit_code == 0, result.output
    envelope: dict[str, Any] = json.loads(result.output)
    return envelope


def test_replay_parity_command_reports_the_bundled_corpus(replay_parity_envelope: dict[str, Any]) -> None:
    """The shipped command replays every bundled capture and states its verdict."""
    assert replay_parity_envelope["command"] == "registry.replay.parity"
    payload = replay_parity_envelope["result"]
    assert payload["oracle_id"] == "modelo-100-renta-web-open"
    assert payload["guard_policy_id"] == "modelo-100-renta-web-open-read-only"
    assert payload["registry_validated"] is True
    assert payload["compared_field_count"] > 0
    assert len(payload["payloads"]) == 5
    assert payload["matched_payload_count"] == 5
    assert payload["mismatched_payload_count"] == 0
    assert payload["unverifiable_payload_count"] == 0
    assert payload["blocked_payload_count"] == 0
    assert payload["verdict"] == "match"


def test_replay_parity_command_keeps_every_field_verdict_distinct(
    replay_parity_envelope: dict[str, Any],
) -> None:
    """Field verdicts travel as their own token, never collapsed to a boolean."""
    verdicts = {
        field["verdict"] for capture in replay_parity_envelope["result"]["payloads"] for field in capture["fields"]
    }
    assert verdicts <= {"match", "mismatch", "unverifiable"}
    assert verdicts == {"match"}


@pytest.mark.parametrize("locale", _SUPPORTED_LOCALES)
@pytest.mark.parametrize("translation_key", _TRANSLATION_KEYS)
def test_replay_parity_translation_keys_resolve_in_every_locale(translation_key: str, locale: str) -> None:
    """Each supported catalogue carries real prose, not the key echoed back."""
    rendered = tr(translation_key, locale=locale)
    assert rendered != translation_key
    assert rendered.strip()
