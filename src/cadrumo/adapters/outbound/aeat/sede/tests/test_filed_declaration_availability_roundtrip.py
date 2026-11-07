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
from ......core.filing_year import FOUR_DIGIT_YEAR_FIRST
from ......domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ..schema import FiledDeclarationAvailability, FiledDeclarationAvailabilityReport

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_YEAR = filing_year_envelope().horizon
_DISCOVERED_AT = datetime(_YEAR, 8, 7, 9, 30, 15, tzinfo=UTC)


def _populated_report() -> FiledDeclarationAvailabilityReport:
    """Build a report with every defaultable field set to a non-default value."""
    return FiledDeclarationAvailabilityReport(
        items=(
            FiledDeclarationAvailability(modelo="303", ejercicios=(_YEAR, _YEAR - 1, _YEAR - 2)),
            FiledDeclarationAvailability(modelo="100", ejercicios=(_YEAR - 1,)),
        ),
        discovered_at=_DISCOVERED_AT,
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
        ("303", _YEAR),
        ("303", _YEAR - 1),
        ("303", _YEAR - 2),
        ("100", _YEAR - 1),
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
    corrupted["discovered_at"] = _DISCOVERED_AT.replace(tzinfo=None).isoformat()
    with pytest.raises(ValidationError, match="discovered_at"):
        FiledDeclarationAvailabilityReport.model_validate_json(json.dumps(corrupted))


def test_availability_refuses_an_out_of_range_ejercicio() -> None:
    with pytest.raises(ValidationError, match="ejercicios"):
        FiledDeclarationAvailability(modelo="303", ejercicios=(FOUR_DIGIT_YEAR_FIRST - 1,))


def test_availability_refuses_an_unknown_field() -> None:
    corrupted = json.loads(_populated_report().model_dump_json())
    corrupted["items"][0]["scoping_confirmed"] = True
    with pytest.raises(ValidationError, match="scoping_confirmed"):
        FiledDeclarationAvailabilityReport.model_validate_json(json.dumps(corrupted))
