"""Regression coverage for historical work units on overview surfaces."""

from __future__ import annotations

import sys
from collections.abc import Iterator, Sequence
from contextvars import ContextVar
from pathlib import Path

import pytest
from click.testing import Result

from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....core.bucket_pointer import resolve_active_bucket_id
from ....core.period import Period
from ....core.time.clock import now
from ....domain.calculations.registry.tests.published_authority import published_snapshot
from ....domain.modelos.codes import ModeloCode
from ....domain.modelos.repository import upsert_work_unit
from ....domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from ....tests.cli_envelope import unwrap_schema_envelope as _payload
from ._overview_native_support import invoke_native_overview
from ._runtime_profile_cli_fixture import NativeCliProfileFixture, native_cli_profile_scope

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers"),
]
_ACTIVE_NATIVE: ContextVar[NativeCliProfileFixture | None] = ContextVar("overview_historical_native", default=None)


@pytest.fixture(autouse=True)
def _native_profile(tmp_path: Path) -> Iterator[None]:
    with native_cli_profile_scope(tmp_path) as fixture:
        fixture.register(
            label="Historical overview profile",
            facts={
                "withholding.has_employees": "false",
                "withholding.pays_professionals_with_retencion": "false",
                "irpf.art109_activity_income_withholding_ge_70pct": "false",
                "withholding.pays_rent_with_retencion": "false",
                "withholding.pays_capital_income_with_retencion": "false",
                "iva.does_intracomunitario": "false",
                "obligations.third_party_transactions_above_347_threshold": "false",
            },
        )
        token = _ACTIVE_NATIVE.set(fixture)
        try:
            yield
        finally:
            _ACTIVE_NATIVE.reset(token)


def _invoke(args: Sequence[str]) -> Result:
    fixture = _ACTIVE_NATIVE.get()
    if fixture is None:
        raise AssertionError("historical native fixture is not active")
    return invoke_native_overview(fixture, args)


_FILED_CALCULATION_REVISION_ID = "a" * 64
_CURRENT_FILING_RECORD_ID = "b" * 64


def _revision_for_target(*, modelo: str, year: int, period: str) -> str:
    return str(published_snapshot(modelo, filing_year=year, period=period).revision.id)


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
    repository = WorkUnitCatalogueRepository(bucket_id=bucket_id)
    repository.save(upsert_work_unit(repository.load(), unit))
    return work_unit_id


def _seed_historical_m130_m303_work() -> dict[tuple[str, int, str], str]:
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


def _calendar_entries_by_target(entries: list[dict[str, object]]) -> dict[tuple[str, str], dict[str, object]]:
    """Index compact calendar rows by their public target identity."""
    result: dict[tuple[str, str], dict[str, object]] = {}
    for entry in entries:
        modelo = entry.get("modelo")
        period = entry.get("period")
        if isinstance(modelo, str) and isinstance(period, str):
            result[(modelo, period)] = entry
    return result


def _backlog_entries_by_target(entries: list[dict[str, object]]) -> dict[tuple[str, int, str], dict[str, object]]:
    """Index the detailed backlog rows by their full persisted target identity."""
    result: dict[tuple[str, int, str], dict[str, object]] = {}
    for entry in entries:
        modelo = entry.get("modelo")
        filing_year = entry.get("filing_year")
        period = entry.get("period")
        if isinstance(modelo, str) and isinstance(filing_year, int) and isinstance(period, str):
            result[(modelo, filing_year, period)] = entry
    return result


def test_calendar_surfaces_created_historical_m130_m303_work_units() -> None:
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
    entries = _calendar_entries_by_target(_payload(result.output)["entries"])
    for modelo, year, period in created:
        entry = entries[(modelo, f"{year} {period}")]
        assert entry["user_state"] == "late"


def test_backlog_default_surface_includes_created_historical_m130_m303_work_units() -> None:
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
    items = _backlog_entries_by_target(payload["items"])
    for (modelo, year, period), work_unit_id in created.items():
        item = items[(modelo, year, f"{year} {period}")]
        # The pinned registry now covers these historical windows. The work
        # unit enriches the authoritative deadline row rather than replacing it.
        assert item["source"] == "registry_deadline"
        assert item["local_work_unit_id"] == work_unit_id
        assert item["user_state"] == "late"


def test_filed_historical_work_unit_is_calendar_filed_not_backlog_late() -> None:
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
    entries = _calendar_entries_by_target(_payload(calendar_result.output)["entries"])
    entry = entries[("130", "2022 1T")]
    assert entry["user_state"] == "filed"
    assert entry["local_filing_state"] == "ready_to_file"
