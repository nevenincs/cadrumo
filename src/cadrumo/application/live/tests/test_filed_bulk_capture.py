"""Tests for bulk filed-declaration capture report models."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ....adapters.outbound.aeat.sede import Declaracion, SedeParseError
from ....core import Period
from ..errors import LiveIvaSurfaceTimeoutError
from ..filed_data_capture import (
    _await_filed_register_walk,
    _walk_or_failure_row,
    capture_filed_data_bulk,
    filed_data_capture_failure_row,
    list_filed_data_bulk,
)
from ..remote_state_models import (
    BulkFiledDataCaptureReport,
    FiledDataCaptureFailureRow,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _declaration() -> Declaracion:
    return Declaracion(
        modelo="303",
        ejercicio=2025,
        period=Period.from_year_and_code(2025, "1T"),
        expediente_id="12345678901234567890",
        estado="ALTA",
        presented_at=datetime(2025, 4, 15, 9, 30, tzinfo=UTC),
    )


async def _slow_empty_declarations() -> tuple[Declaracion, ...]:
    await asyncio.sleep(0.05)
    return ()


def test_bulk_failure_row_preserves_declaration_coordinates() -> None:
    row = filed_data_capture_failure_row(
        modelo="303",
        year=2025,
        declaration=_declaration(),
        error=ValueError("AEAT row did not expose a justificante link"),
    )

    assert row == FiledDataCaptureFailureRow(
        modelo="303",
        year=2025,
        period=Period.from_year_and_code(2025, "1T"),
        expediente_id="12345678901234567890",
        error_type="ValueError",
        message="AEAT row did not expose a justificante link",
    )


def test_filed_register_walk_timeout_reports_modelo_year_context() -> None:
    with pytest.raises(LiveIvaSurfaceTimeoutError) as raised:
        asyncio.run(
            _await_filed_register_walk(
                _slow_empty_declarations(),
                modelo="303",
                year=2026,
                timeout_ms=1,
            ),
        )

    assert raised.value.surface == "filed_declarations_register_walk"
    assert raised.value.timeout_ms == 1
    assert raised.value.context is not None
    assert raised.value.context["progress"] == {"modelo": "303", "year": 2026}


def test_bulk_report_counts_successes_and_failures_explicitly() -> None:
    failure = filed_data_capture_failure_row(
        modelo="130",
        year=2025,
        error=RuntimeError("modelo not offered by AEAT form"),
    )

    report = BulkFiledDataCaptureReport(
        output_root="var/aeat/filed-declarations",
        modelos=("130", "303"),
        year_from=2025,
        year_to=2025,
        captured_count=1,
        failed_count=1,
        observation_paths=("303/2025/1T/manifest.json",),
        artefact_refs=("sha256:abc123",),
        casilla_count=12,
        calculation_observation_count=1,
        calculation_observation_keys=("303:2025:1T",),
        failures=(failure,),
    )

    assert report.modelos == ("130", "303")
    assert report.captured_count == 1
    assert report.failed_count == 1
    assert report.failures[0].modelo == "130"


def test_bulk_capture_reports_registry_unsupported_modelos_as_local_boundaries(tmp_path: Path) -> None:
    report = asyncio.run(
        capture_filed_data_bulk(
            year_from=2024,
            year_to=2024,
            output_root=tmp_path,
            modelos=("151", "721"),
        ),
    )

    assert report.modelos == ("151", "721")
    assert report.captured_count == 0
    assert report.failed_count == 2
    failures = {failure.modelo: failure for failure in report.failures}
    assert set(failures) == {"151", "721"}
    assert failures["151"].year == 2024
    assert failures["151"].error_type == "LiveApplicationInputError"
    assert "declares no authenticated filed-declarations read surface" in failures["151"].message
    assert failures["721"].year == 2024
    assert failures["721"].error_type == "LiveApplicationInputError"
    assert "declares no authenticated filed-declarations read surface" in failures["721"].message


def test_bulk_capture_report_exposes_its_evidence_notices_channel(tmp_path: Path) -> None:
    """The report carries ``evidence_notices``, and a caller can read it off the report.

    The per-artefact evidence advisories are raised during enrolment and accumulated
    during capture; the report is what carries them out to a caller. When it did not,
    :func:`pull_filed_history` read the attribute anyway and raised ``AttributeError``
    on a path nothing in this suite executed — so the missing channel and the caller
    that wanted it were both invisible.

    Asserts the attribute READS and is the declared empty tuple, not that it holds any
    particular advisory: this scenario is refused before live contact and captures
    nothing, so an empty channel is the correct answer here and a populated expectation
    would be manufactured from a capture that never happened.
    """
    report = asyncio.run(
        capture_filed_data_bulk(
            year_from=2024,
            year_to=2024,
            output_root=tmp_path,
            modelos=("151",),
        ),
    )

    assert report.evidence_notices == ()


def test_bulk_capture_accepts_limit_for_locally_bounded_unsupported_modelos(tmp_path: Path) -> None:
    report = asyncio.run(
        capture_filed_data_bulk(
            year_from=2024,
            year_to=2024,
            output_root=tmp_path,
            modelos=("151",),
            limit=10,
        ),
    )

    assert report.modelos == ("151",)
    assert report.captured_count == 0
    assert report.failed_count == 1
    assert report.failures[0].modelo == "151"
    assert "declares no authenticated filed-declarations read surface" in report.failures[0].message


def test_bulk_listing_reports_registry_unsupported_modelos_as_local_boundaries() -> None:
    report = asyncio.run(
        list_filed_data_bulk(
            year_from=2024,
            year_to=2024,
            modelos=("151", "721"),
        ),
    )

    assert report.modelos == ("151", "721")
    assert report.row_count == 0
    assert report.failed_count == 2
    failures = {failure.modelo: failure for failure in report.failures}
    assert set(failures) == {"151", "721"}
    assert failures["151"].year == 2024
    assert failures["151"].error_type == "LiveApplicationInputError"
    assert "declares no authenticated filed-declarations read surface" in failures["151"].message
    assert failures["721"].year == 2024
    assert failures["721"].error_type == "LiveApplicationInputError"
    assert "declares no authenticated filed-declarations read surface" in failures["721"].message


def test_truncated_register_read_reuses_the_per_pair_failure_taxonomy() -> None:
    """A refused short register read becomes an ordinary per-pair failure row, not a new channel.

    The bulk sweep's walk arm folds any walk exception into a
    :class:`FiledDataCaptureFailureRow` and moves to the next pair, so a
    register read that refuses because the grid declared more records than it
    rendered needs no bulk-level mechanism of its own -- it only needs to be a
    plain exception the arm already catches, mapped with its type and its
    operator-facing reason intact. Both halves are asserted here: that the
    refusal is catchable by that arm at all, and that nothing about it is lost
    on the way into the report -- the row's message is length-bounded, so a
    refusal wording that pushed its counts past the bound would arrive with the
    only actionable part cut off.
    """
    assert issubclass(SedeParseError, Exception), "the bulk walk arm catches Exception; a refusal outside it escapes"

    refusal = SedeParseError(
        "declaraciones register modelo 100 ejercicio 2026 rendered 3 row(s) but its pager "
        "declares 8 in total; refusing an under-reported filing history",
        context={"modelo": "100", "ejercicio": 2026, "rendered_count": 3, "declared_total": 8},
    )

    row = filed_data_capture_failure_row(modelo="100", year=2026, error=refusal)

    assert row.modelo == "100"
    assert row.year == 2026
    assert row.period is None
    assert row.expediente_id is None
    assert row.error_type == "SedeParseError"
    assert "rendered 3 row(s)" in row.message
    assert "declares 8 in total" in row.message
    assert "under-reported filing history" in row.message
    assert not row.message.endswith("…"), "the refusal wording overran the row's message bound and lost its tail"


async def _refusing_walk() -> tuple[Declaracion, ...]:
    """A real walk coroutine that refuses the way a truncated register read does."""
    raise SedeParseError(
        "declaraciones register modelo 100 ejercicio 2026 rendered 3 row(s) but its pager "
        "declares 8 in total; refusing an under-reported filing history",
        context={"modelo": "100", "ejercicio": 2026, "rendered_count": 3, "declared_total": 8},
    )


async def _one_declaration_walk() -> tuple[Declaracion, ...]:
    """A real walk coroutine that succeeds, standing for a healthy pair."""
    return (_declaration(),)


def test_walk_failure_is_absorbed_into_a_row_and_signals_the_pair_be_skipped() -> None:
    """A refusing walk yields no rows and one failure row; a healthy walk is untouched.

    This covers the PER-PAIR arm only: the failure becomes a typed row and the
    helper returns None so its caller skips that pair. Cross-pair continuation --
    that the sweep goes on to the next pair -- lives in the bulk functions behind
    the live-session gate and is NOT proven here.

    Both coroutines are real: one raises the genuine refusal a truncated register
    read produces, the other returns a real `Declaracion`. Nothing is stubbed and
    no production path is patched.
    """
    failures: list[FiledDataCaptureFailureRow] = []

    refused = asyncio.run(
        _walk_or_failure_row(
            _refusing_walk(),
            modelo="100",
            year=2026,
            timeout_ms=5_000,
            failures=failures,
        ),
    )

    assert refused is None, "an absorbed failure must signal the pair be skipped rather than yield rows"
    assert len(failures) == 1
    assert failures[0].error_type == "SedeParseError"
    assert "declares 8 in total" in failures[0].message

    healthy = asyncio.run(
        _walk_or_failure_row(
            _one_declaration_walk(),
            modelo="303",
            year=2025,
            timeout_ms=5_000,
            failures=failures,
        ),
    )

    assert healthy == (_declaration(),), "a healthy walk must return its rows unchanged"
    assert len(failures) == 1, "a healthy walk must not add a failure row"
