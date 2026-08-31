"""CLI surface tests for ``aeat app overview backlog``."""

from __future__ import annotations

import json

import pytest

from ....adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
from ....core.classification.policies import SensitivityClass
from ....core.time.clock import now
from ....tests.cli_runner import invoke_cached_cli
from ._isolated_profile_storage_fixtures import active_profile_isolated_backend

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]
__all__ = ["active_profile_isolated_backend"]


def test_backlog_renders_envelope_with_explicit_window() -> None:
    """A concrete --from / --to window renders the backlog envelope
    including the range echo, as_of, and late_count header."""

    result = invoke_cached_cli(
        [
            "app",
            "overview",
            "backlog",
            "--from",
            "2026-01-01",
            "--to",
            "2026-12-31",
            "--allow-incomplete",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "from\t2026-01-01" in result.output
    assert "to\t2026-12-31" in result.output
    assert "as_of\t" in result.output
    assert "late_count\t" in result.output


def test_backlog_json_preserves_exact_modelo_303_2025_quarterly_coordinates() -> None:
    result = invoke_cached_cli(
        [
            "--format",
            "json",
            "app",
            "overview",
            "backlog",
            "--from",
            "2025-01-01",
            "--to",
            "2026-02-28",
            "--allow-incomplete",
        ],
    )

    assert result.exit_code == 0, result.output
    items = json.loads(result.output)["result"]["items"]
    coordinates = tuple(
        (item["modelo"], item["period"])
        for item in items
        if item["modelo"] == "303" and item["period"].startswith("2025 ")
    )

    assert coordinates == (
        ("303", "2025 1T"),
        ("303", "2025 2T"),
        ("303", "2025 3T"),
        ("303", "2025 4T"),
    )


def test_backlog_rejects_malformed_from_date() -> None:
    """A non-ISO --from is rejected by the parsing boundary."""

    result = invoke_cached_cli(
        ["app", "overview", "backlog", "--from", "not-a-date"],
    )
    assert result.exit_code != 0, result.output


def test_backlog_rejects_malformed_to_date() -> None:
    """A non-ISO --to is rejected by the parsing boundary."""

    result = invoke_cached_cli(
        ["app", "overview", "backlog", "--to", "not-a-date"],
    )
    assert result.exit_code != 0, result.output


def test_backlog_help_advertises_local_only() -> None:
    """Help text must signal `local-only` across locales."""

    result = invoke_cached_cli(["app", "overview", "backlog", "--help"])
    assert result.exit_code == 0, result.output
    assert any(
        token in result.output.lower() for token in ("local-only", "local;", "nunca", "mai contacta", "csak helyi")
    ), result.output


_BUCKET_ID = "11111111-1111-4111-8111-111111111111"
_WORK_UNIT_NAMESPACE = "cadrumo.domain.modelos.work_units"
_WORK_UNIT_OBJECT_KEY = "catalogue"


def _persist_invalid_work_unit_catalogue_payload(bucket_id: str) -> None:
    secure_object_repository_for_bucket(bucket_id).save(
        namespace=_WORK_UNIT_NAMESPACE,
        object_key=_WORK_UNIT_OBJECT_KEY,
        classification=SensitivityClass.FINANCIAL,
        schema_version=1,
        written_at=now(),
        payload=b'{"status":"invalid work-unit catalogue envelope"',
    )


def test_work_unit_load_failure_degrades_to_notice_not_refusal() -> None:
    # Work units are an optional enrichment; when their load fails the overview
    # must degrade to a schedule-only answer with a WARNING notice, NOT refuse
    # the whole surface — refusing left a behind-but-fresh taxpayer (the
    # regularizar-atrasos persona) unable to answer "what have I missed".
    from ....core.json_contract import NoticeSeverity
    from .._overview import _local_modelo_work_units

    _persist_invalid_work_unit_catalogue_payload(_BUCKET_ID)

    units, notice = _local_modelo_work_units(_BUCKET_ID)
    assert units == ()
    assert notice is not None
    assert notice.code == "overview.work_units_degraded"
    assert notice.severity is NoticeSeverity.WARNING


def test_backlog_renders_despite_work_unit_load_failure() -> None:
    # End-to-end: with the work-unit load forced to fail, the backlog still
    # renders (exit 0) from the deadline schedule and surfaces the degradation
    # line, rather than exiting non-zero with a "persisted work state" refusal.
    _persist_invalid_work_unit_catalogue_payload(_BUCKET_ID)

    result = invoke_cached_cli(
        ["app", "overview", "backlog", "--from", "2026-01-01", "--to", "2026-12-31", "--allow-incomplete"],
    )
    assert result.exit_code == 0, result.output
    assert "late_count\t" in result.output
    assert "work_units_degraded\t" in result.output
