"""Domain-report tests for the bundled Renta WEB Open replay evidence."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from ..errors import RegistryValidationError
from ..live_parity import ParityVerdictKind
from ..renta_web_open_replay_corpus import (
    RentaWebOpenReplayParityReport,
    build_renta_web_open_replay_parity,
    verify_bundled_renta_web_open_replays,
)
from ..schema import ModeloDefinition

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.fixture(scope="module")
def replay_report() -> RentaWebOpenReplayParityReport:
    """Run the shipped, offline evidence fold once for report assertions."""
    return verify_bundled_renta_web_open_replays()


def test_bundled_replay_report_is_validated_offline_match(replay_report: RentaWebOpenReplayParityReport) -> None:
    assert replay_report.registry_validated is True
    assert replay_report.verdict == ParityVerdictKind.MATCH
    assert replay_report.payloads
    assert replay_report.compared_field_count() > 0
    assert all(payload.verdict == ParityVerdictKind.MATCH for payload in replay_report.payloads)
    assert all(payload.fields for payload in replay_report.payloads)


def _modelos_with_conflicting_replay_cross_reference() -> tuple[ModeloDefinition, ...]:
    """Build only the structural cross-reference shape the resolver consumes."""
    references = (
        SimpleNamespace(id="modelo-100-renta-web-open", guard_policy_id="replay-guard-one"),
        SimpleNamespace(id="modelo-100-renta-web-open", guard_policy_id="replay-guard-two"),
    )
    revision = SimpleNamespace(live_cross_references=references)
    modelo = SimpleNamespace(revisions={"test": revision})
    return cast(tuple[ModeloDefinition, ...], (modelo,))


def test_malformed_replay_cross_reference_refuses_before_any_payload_report() -> None:
    with pytest.raises(RegistryValidationError, match="conflicting guard policies"):
        build_renta_web_open_replay_parity(
            _modelos_with_conflicting_replay_cross_reference(),
            payload_paths=(Path("this-payload-must-not-be-read.json"),),
            registry_validated=True,
        )


def test_same_policy_cross_revision_replay_duplicates_refuse_before_any_payload_report() -> None:
    reference = SimpleNamespace(id="modelo-100-renta-web-open", guard_policy_id="replay-guard")
    modelo = SimpleNamespace(
        revisions={
            "first": SimpleNamespace(live_cross_references=(reference,)),
            "second": SimpleNamespace(live_cross_references=(reference,)),
        },
    )
    modelos = cast(tuple[ModeloDefinition, ...], (modelo,))

    with pytest.raises(RegistryValidationError, match="duplicate declarations name the same guard policy"):
        build_renta_web_open_replay_parity(
            modelos,
            payload_paths=(Path("this-payload-must-not-be-read.json"),),
            registry_validated=True,
        )
