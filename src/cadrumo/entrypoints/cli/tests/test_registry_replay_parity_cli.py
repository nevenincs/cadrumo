"""JSON contract for the offline bundled Renta WEB Open replay command."""

from __future__ import annotations

import json

import pytest

from .._registry_payloads import RegistryReplayParityResult
from ._registry_cli_support import invoke_cached_cli

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@pytest.fixture(scope="module")
def replay_parity_payload() -> RegistryReplayParityResult:
    """Run the expensive validated replay command once for its JSON contract."""
    result = invoke_cached_cli(["--format", "json", "app", "registry", "replay-parity"])
    assert result.exit_code == 0, result.output
    envelope = json.loads(result.output)
    assert envelope["command"] == "registry.replay.parity"
    return RegistryReplayParityResult.model_validate(envelope["result"])


def test_replay_parity_cli_emits_validated_matching_offline_evidence(
    replay_parity_payload: RegistryReplayParityResult,
) -> None:
    assert replay_parity_payload.oracle_id == "modelo-100-renta-web-open"
    assert replay_parity_payload.cross_reference_id == replay_parity_payload.oracle_id
    assert replay_parity_payload.guard_policy_id == "modelo-100-renta-web-open-read-only"
    assert replay_parity_payload.registry_validated is True
    assert replay_parity_payload.verdict == "match"
    assert replay_parity_payload.compared_field_count > 0
    assert replay_parity_payload.payloads
    assert replay_parity_payload.matched_payload_count == len(replay_parity_payload.payloads)
    assert replay_parity_payload.mismatched_payload_count == 0
    assert replay_parity_payload.unverifiable_payload_count == 0
    assert replay_parity_payload.blocked_payload_count == 0
    assert all(payload.verdict == "match" and payload.fields for payload in replay_parity_payload.payloads)
    assert all(field.verdict == "match" for payload in replay_parity_payload.payloads for field in payload.fields)
