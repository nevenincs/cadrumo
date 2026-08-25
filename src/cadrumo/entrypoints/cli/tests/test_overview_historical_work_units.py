"""Regression coverage for historical work units on overview surfaces."""

from __future__ import annotations

from pathlib import Path

import pytest

from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....core import Period
from ....core.bucket_pointer import resolve_active_bucket_id
from ....core.resources import resources
from ....core.time import now
from ....domain.modelos import (
    ModeloCode,
    WorkUnit,
    derive_work_unit_id,
    upsert_work_unit,
)
from ....tests.cli_envelope import unwrap_schema_envelope as _payload
from ....tests.profile_capsule import open_test_profile_session
from ._modelo_work_ux_support import _create_profile, _invoke
from ._modelo_work_ux_support import _isolated_cli_backend as _isolated_cli_backend

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_FILED_CALCULATION_REVISION_ID = "a" * 64
_CURRENT_FILING_RECORD_ID = "b" * 64


def _revision_for_target(*, modelo: str, year: int, period: str) -> str:
    return str(resources().modelos.authority.snapshot(modelo, filing_year=year, period=period).revision.id)


def _create_historical_work_unit(
    *,
    bucket_id: str,
    modelo: str,
    year: int,
    period: str,
    filed_calculation_revision_id: str | None = None,
    current_filing_record_id: str | None = None,
) -> str:
    work_period = Period.from_year_and_code(year, period)
    revision_id = _revision_for_target(modelo=modelo, year=year, period=period)
    work_unit_id = derive_work_unit_id(
        bucket_id=bucket_id,
        modelo=modelo,
        filing_year=year,
        period=work_period,
        revision_id=revision_id,
    )
    created_at = now()
    unit = WorkUnit(
        work_unit_id=work_unit_id,
        bucket_id=bucket_id,
        modelo=ModeloCode(modelo),
        filing_year=year,
        period=work_period,
        revision_id=revision_id,
        name=f"{modelo}-{year}-{period}",
        created_at=created_at,
        updated_at=created_at,
        filed_calculation_revision_id=filed_calculation_revision_id,
        current_filing_record_id=current_filing_record_id,
    )
    with open_test_profile_session(bucket_id):
        repository = WorkUnitCatalogueRepository(bucket_id=bucket_id)
        repository.save(upsert_work_unit(repository.load(), unit))
    return work_unit_id


def _seed_historical_m130_m303_work() -> dict[tuple[str, int, str], str]:
    _create_profile()
    bucket_id = resolve_active_bucket_id()
    assert bucket_id is not None
    targets = (
        ("130", 2022, "1T"),
        ("303", 2022, "1T"),
        ("130", 2023, "2T"),
        ("303", 2023, "2T"),
    )
    return {
        (modelo, year, period): _create_historical_work_unit(
            bucket_id=bucket_id,
            modelo=modelo,
            year=year,
            period=period,
        )
        for modelo, year, period in targets
    }


def _entries_by_target(entries: list[dict[str, object]]) -> dict[tuple[str, int, str], dict[str, object]]:
    result: dict[tuple[str, int, str], dict[str, object]] = {}
    for entry in entries:
        modelo = entry.get("modelo")
        filing_year = entry.get("filing_year")
        period = entry.get("period")
        if isinstance(modelo, str) and isinstance(filing_year, int) and isinstance(period, str):
            result[(modelo, filing_year, period)] = entry
    return result


def _get_nested_dict_value(obj: object, key: str) -> dict[str, object] | None:
    """Safely access a nested dict value from an object-typed dict.

    ``isinstance(value, dict)`` only proves ``value`` is *some* dict, not
    that it matches ``dict[str, object]`` — this data always originates from
    parsed JSON envelope output, so every key is already a ``str``; the
    comprehension re-keys with ``str(k)`` to give the type checker a real,
    honestly-typed ``dict[str, object]`` rather than asserting the shape.
    """
    if isinstance(obj, dict):
        value = obj.get(key)
        if isinstance(value, dict):
            return {str(k): v for k, v in value.items()}
    return None


def test_calendar_surfaces_created_historical_m130_m303_work_units(_isolated_cli_backend: Path) -> None:
    created = _seed_historical_m130_m303_work()

    result = _invoke(
        [
            "--format",
            "json",
            "app",
            "overview",
            "calendar",
            "--from",
            "2022-01-01",
            "--to",
            "2023-12-31",
            "--allow-incomplete",
        ],
    )

    assert result.exit_code == 0, result.output
    entries = _entries_by_target(_payload(result.output)["entries"])
    for (modelo, year, period), work_unit_id in created.items():
        entry = entries[(modelo, year, f"{year} {period}")]
        assert entry["source"] == "local_work_unit"
        assert entry["local_work_unit_id"] == work_unit_id
        assert entry["local_work_unit_revision_id"]
        assert entry["user_state"] == "late"


def test_backlog_default_surface_includes_created_historical_m130_m303_work_units(
    _isolated_cli_backend: Path,
) -> None:
    created = _seed_historical_m130_m303_work()

    result = _invoke(
        [
            "--format",
            "json",
            "app",
            "overview",
            "backlog",
            "--allow-incomplete",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = _payload(result.output)
    assert payload["range"]["from_date"] <= "2022-01-01"
    items = _entries_by_target(payload["items"])
    for (modelo, year, period), work_unit_id in created.items():
        item = items[(modelo, year, f"{year} {period}")]
        assert item["source"] == "local_work_unit"
        assert item["local_work_unit_id"] == work_unit_id
        assert item["user_state"] == "late"


def test_filed_historical_work_unit_is_calendar_filed_not_backlog_late(
    _isolated_cli_backend: Path,
) -> None:
    _create_profile()
    bucket_id = resolve_active_bucket_id()
    assert bucket_id is not None
    work_unit_id = _create_historical_work_unit(
        bucket_id=bucket_id,
        modelo="130",
        year=2022,
        period="1T",
        filed_calculation_revision_id=_FILED_CALCULATION_REVISION_ID,
        current_filing_record_id=_CURRENT_FILING_RECORD_ID,
    )

    backlog_result = _invoke(
        [
            "--format",
            "json",
            "app",
            "overview",
            "backlog",
            "--allow-incomplete",
        ],
    )

    assert backlog_result.exit_code == 0, backlog_result.output
    backlog_payload = _payload(backlog_result.output)
    assert all(item["local_work_unit_id"] != work_unit_id for item in backlog_payload["items"])

    calendar_result = _invoke(
        [
            "--format",
            "json",
            "app",
            "overview",
            "calendar",
            "--from",
            "2022-01-01",
            "--to",
            "2022-12-31",
            "--allow-incomplete",
        ],
    )

    assert calendar_result.exit_code == 0, calendar_result.output
    entries = _entries_by_target(_payload(calendar_result.output)["entries"])
    entry = entries[("130", 2022, "2022 1T")]
    assert entry["source"] == "local_work_unit"
    assert entry["local_work_unit_id"] == work_unit_id
    assert entry["status"] == "FILED"
    assert entry["user_state"] == "filed"
    filing_evidence = _get_nested_dict_value(entry, "filing_evidence")
    assert filing_evidence is not None
    assert filing_evidence.get("local_filing_state") == "ready_to_file"
    assert filing_evidence.get("local_filing_record_id") == _CURRENT_FILING_RECORD_ID
    assert filing_evidence.get("local_calculation_revision_id") == _FILED_CALCULATION_REVISION_ID
    assert filing_evidence.get("aeat_submission_state") == "not_observed"
