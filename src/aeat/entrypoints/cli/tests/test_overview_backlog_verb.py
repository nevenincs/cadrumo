"""CLI surface tests for ``aeat app overview backlog``."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from ....application.user_profile import profile_create_storage_span, register_minimal_profile
from ....application.workflow import workflow_state_repository
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_profile_storage_root

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path) -> Iterator[None]:
    with (
        isolated_profile_storage_root(tmp_path=tmp_path),
        profile_create_storage_span("11111111-1111-4111-8111-111111111111"),
    ):
        workflow_state_repository().update(
            lambda state: register_minimal_profile(state, profile_id="11111111-1111-4111-8111-111111111111"),
        )
        yield


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


def test_work_unit_load_failure_degrades_to_notice_not_refusal(monkeypatch: pytest.MonkeyPatch) -> None:
    # Work units are an optional enrichment; when their load fails the overview
    # must degrade to a schedule-only answer with a WARNING notice, NOT refuse
    # the whole surface — refusing left a behind-but-fresh taxpayer (the
    # regularizar-atrasos persona) unable to answer "what have I missed".
    from ....application import modelo as modelo_app
    from ....core.json_contract import NoticeSeverity
    from .._overview import _local_modelo_work_units

    def _boom(**_kwargs: object) -> object:
        raise RuntimeError("work-unit catalogue store is corrupt")

    monkeypatch.setattr(modelo_app, "list_work_units", _boom)

    units, notice = _local_modelo_work_units(_BUCKET_ID)
    assert units == ()
    assert notice is not None
    assert notice.code == "overview.work_units_degraded"
    assert notice.severity is NoticeSeverity.WARNING


def test_backlog_renders_despite_work_unit_load_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    # End-to-end: with the work-unit load forced to fail, the backlog still
    # renders (exit 0) from the deadline schedule and surfaces the degradation
    # line, rather than exiting non-zero with a "persisted work state" refusal.
    from ....application import modelo as modelo_app

    def _boom(**_kwargs: object) -> object:
        raise RuntimeError("work-unit catalogue store is corrupt")

    monkeypatch.setattr(modelo_app, "list_work_units", _boom)

    result = invoke_cached_cli(
        ["app", "overview", "backlog", "--from", "2026-01-01", "--to", "2026-12-31", "--allow-incomplete"],
    )
    assert result.exit_code == 0, result.output
    assert "late_count\t" in result.output
    assert "work_units_degraded\t" in result.output


def test_backlog_emits_zero_late_count_for_future_window() -> None:
    """A window entirely in the future (but within the registry's known
    year range) has nothing past-due relative to today, so late_count == 0.

    Note: the registry only carries deadline calendars for years it has
    been configured for. Far-future years (e.g. 2099) are outside that
    range and the verb correctly refuses them with a non-zero exit.
    Use the second half of 2026 — a registry-known year that lies
    entirely in the future relative to the test-run date (2026-05-20).
    """

    result = invoke_cached_cli(
        [
            "app",
            "overview",
            "backlog",
            "--from",
            "2026-07-01",
            "--to",
            "2026-12-31",
            "--allow-incomplete",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "late_count\t0" in result.output
