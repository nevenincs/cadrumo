"""Strict roundtrip and provenance pinning for the register-availability records.

The availability report crosses the adapter boundary into the application layer
and out again onto a JSON envelope, so it gets the same treatment as any other
record that travels: a strict JSON roundtrip with EVERY defaultable field
carrying a non-default value, so a save-drops-field / load-re-defaults-field
drift shows up as inequality rather than as a silently thinner report.

Anti-tautology: :func:`test_report_refuses_a_payload_missing_discovered_at`
deletes ``discovered_at`` from the serialised text and asserts the load refuses
by naming that field. It parses JSON TEXT rather than a dict, because these
models are strict and a dict parse refuses on type coercion before it ever
reaches the deleted field — a proof that goes green for the wrong reason.

:func:`test_report_refuses_the_taxpayer_specific_signal` is the load-bearing
one. The provenance tag is a pinned literal, so this record cannot be relabelled
as the taxpayer-specific applicability signal; if that pin were widened, an
unconfirmed AEAT-offered option set could be presented to an operator as the
taxpayer's own declared expectation.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from ......core.filed_history_discovery_signal import FiledHistoryDiscoverySignal
from ..schema import FiledDeclarationAvailability, FiledDeclarationAvailabilityReport

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


def _populated_report() -> FiledDeclarationAvailabilityReport:
    """Build a report with every defaultable field set to a non-default value."""
    return FiledDeclarationAvailabilityReport(
        items=(
            FiledDeclarationAvailability(modelo="303", ejercicios=(2026, 2025, 2024)),
            FiledDeclarationAvailability(modelo="100", ejercicios=(2025,)),
        ),
        discovered_at=datetime(2026, 8, 7, 9, 30, 15, tzinfo=UTC),
        signal=FiledHistoryDiscoverySignal.AEAT_REGISTER_OPTIONS,
        mode="read",
    )


def test_report_survives_a_strict_json_roundtrip() -> None:
    saved = _populated_report()
    loaded = FiledDeclarationAvailabilityReport.model_validate_json(saved.model_dump_json())
    assert loaded == saved


def test_offered_pairs_flattens_every_modelo_ejercicio_combination() -> None:
    report = _populated_report()
    assert report.offered_pairs == (
        ("303", 2026),
        ("303", 2025),
        ("303", 2024),
        ("100", 2025),
    )


def test_report_refuses_a_payload_missing_discovered_at() -> None:
    corrupted = json.loads(_populated_report().model_dump_json())
    del corrupted["discovered_at"]
    with pytest.raises(ValidationError, match="discovered_at"):
        FiledDeclarationAvailabilityReport.model_validate_json(json.dumps(corrupted))


def test_report_refuses_the_taxpayer_specific_signal() -> None:
    corrupted = json.loads(_populated_report().model_dump_json())
    corrupted["signal"] = FiledHistoryDiscoverySignal.PROFILE_APPLICABILITY.value
    with pytest.raises(ValidationError, match="signal"):
        FiledDeclarationAvailabilityReport.model_validate_json(json.dumps(corrupted))


def test_report_refuses_a_naive_discovered_at() -> None:
    corrupted = json.loads(_populated_report().model_dump_json())
    corrupted["discovered_at"] = "2026-08-07T09:30:15"
    with pytest.raises(ValidationError, match="discovered_at"):
        FiledDeclarationAvailabilityReport.model_validate_json(json.dumps(corrupted))


def test_availability_refuses_an_out_of_range_ejercicio() -> None:
    with pytest.raises(ValidationError, match="ejercicios"):
        FiledDeclarationAvailability(modelo="303", ejercicios=(1999,))


def test_availability_refuses_an_unknown_field() -> None:
    corrupted = json.loads(_populated_report().model_dump_json())
    corrupted["items"][0]["scoping_confirmed"] = True
    with pytest.raises(ValidationError, match="scoping_confirmed"):
        FiledDeclarationAvailabilityReport.model_validate_json(json.dumps(corrupted))
