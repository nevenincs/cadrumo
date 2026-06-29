"""CLI work-command tests for the ``aeat ... modelo`` command tree."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from ....core.config import override_settings
from ....domain.calculations.registry import CasillaId, validated_casilla_id
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_cli_runtime_profile

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_VERIFICATION_FINDING_CASILLA: CasillaId = validated_casilla_id(
    "0100",
    surface="_VERIFICATION_FINDING_CASILLA",
)


@pytest.fixture
def _active_cli_profile(tmp_path: Path) -> Iterator[None]:
    with override_settings(aeat_output_language="en"), isolated_cli_runtime_profile(tmp_path=tmp_path):
        yield


def test_work_discard_refuses_without_yes(_active_cli_profile: None) -> None:
    """``work discard`` without ``--yes`` is refused with the exact re-run command.

    The discard gate is symmetric with ``config profile delete``: an
    auditable state transition must not fire on an unconfirmed run.
    """

    work_unit_id = "a" * 64
    result = invoke_cached_cli(["app", "modelo", "work", "discard", work_unit_id])

    assert result.exit_code != 0, result.output
    assert "Traceback" not in result.output
    assert "--yes" in result.output
    assert work_unit_id in result.output.replace("\n", "")


def test_work_discard_help_advertises_yes_flag() -> None:
    """``work discard --help`` advertises the ``--yes`` confirmation flag."""

    result = invoke_cached_cli(["app", "modelo", "work", "discard", "--help"])

    assert result.exit_code == 0, result.output
    assert "--yes" in result.output


def test_work_amend_batch_reports_all_missing_options(_active_cli_profile: None) -> None:
    """``work amend`` with no flags reports every missing required option at once.

    Before fix: typer surfaced the missing options one at a time,
    forcing the operator to rediscover each on a fresh invocation.
    After fix: a single refusal names every absent required flag.
    """

    result = invoke_cached_cli(["app", "modelo", "work", "amend"])

    assert result.exit_code != 0, result.output
    assert "Traceback" not in result.output
    flat = result.output.replace("\n", " ")
    for flag in ("--from-filing-record", "--kind", "--reason", "--set"):
        assert flag in flat, f"{flag} not reported; output: {result.output}"


def test_work_amend_batch_reports_partial_missing_options(_active_cli_profile: None) -> None:
    """A run missing two of four required options reports both, not just one."""

    result = invoke_cached_cli(
        [
            "app",
            "modelo",
            "work",
            "amend",
            "--from-filing-record",
            "f" * 64,
            "--kind",
            "complementaria",
        ],
    )

    assert result.exit_code != 0, result.output
    flat = result.output.replace("\n", " ")
    assert "--reason" in flat
    assert "--set" in flat


def test_work_calculate_help_exposes_by_actor_flag() -> None:
    """``aeat app modelo work calculate --help`` advertises a ``--by ACTOR``
    option so operators can attribute a calculation revision to a specific
    actor; the default factory pulls the active profile display name when
    ``--by`` is omitted."""

    from ....tests.cli_runner import invoke_cached_cli

    result = invoke_cached_cli(["app", "modelo", "work", "calculate", "--help"])
    assert result.exit_code == 0, result.output
    assert "--by" in result.output


# --- Fix 2: work create validates period token eagerly ---


@pytest.mark.parametrize(
    "period",
    [
        "2026Q1",  # year-prefixed form ambiguous to the resolver
        "INVALID",  # completely invalid
        "Q1X",  # garbled quarter token
    ],
)
def test_work_create_rejects_invalid_period_at_create_time(period: str, _active_cli_profile: None) -> None:
    """``work create`` must reject an un-parseable period token immediately
    rather than storing it and failing later at ``calculate`` time.

    Before fix: invalid tokens were accepted and stored as-is, only
    failing when the registry tried to resolve them at calculate time.
    After fix: ``typer.BadParameter`` fires at create time with a
    human-readable message.
    """

    result = invoke_cached_cli(
        [
            "app",
            "modelo",
            "work",
            "create",
            "--modelo",
            "303",
            "--year",
            "2026",
            "--period",
            period,
            "--revision",
            "2009-y-siguientes",
        ],
    )

    assert result.exit_code != 0, f"period {period!r} should be rejected; got: {result.output}"
    assert "Traceback" not in result.output
    output_lower = result.output.lower()
    assert "period must be" in output_lower or "invalid value" in output_lower


def test_work_create_rejects_unknown_modelo(_active_cli_profile: None) -> None:
    """``work create --modelo 999`` is refused naming the registry's known modelos.

    Before fix: an unknown modelo code provisioned a work unit that
    ``calculate`` then silently treated as a Modelo 303 default.
    After fix: a ``typer.BadParameter`` fires at create time grounded
    in the validated registry authority.
    """

    result = invoke_cached_cli(
        [
            "app",
            "modelo",
            "work",
            "create",
            "--modelo",
            "999",
            "--year",
            "2026",
            "--period",
            "1T",
            "--revision",
            "2009-y-siguientes",
        ],
    )

    assert result.exit_code != 0, result.output
    assert "Traceback" not in result.output
    assert "999" in result.output


@pytest.mark.parametrize("year", ["1899", "2100", "1000"])
def test_work_create_rejects_out_of_range_year(year: str, _active_cli_profile: None) -> None:
    """``work create --year 1899`` is refused with the bad year named.

    Before fix: an out-of-range year built a token like ``1899-Q1``,
    passed the period regex, then failed deep in WorkUnit validation
    and surfaced only the generic English "command input failed
    validation" boundary error.
    After fix: the refusal names the year and the supported range.
    """

    result = invoke_cached_cli(
        [
            "app",
            "modelo",
            "work",
            "create",
            "--modelo",
            "303",
            "--year",
            year,
            "--period",
            "Q1",
            "--revision",
            "2009-y-siguientes",
        ],
    )

    assert result.exit_code != 0, result.output
    assert "Traceback" not in result.output
    assert year in result.output
    assert "config repair" not in result.output


def test_work_create_rejects_unknown_revision(_active_cli_profile: None) -> None:
    """``work create --revision nope`` is refused naming the modelo's revisions."""

    result = invoke_cached_cli(
        [
            "app",
            "modelo",
            "work",
            "create",
            "--modelo",
            "303",
            "--year",
            "2026",
            "--period",
            "1T",
            "--revision",
            "nonexistent-revision",
        ],
    )

    assert result.exit_code != 0, result.output
    assert "Traceback" not in result.output
    assert "nonexistent-revision" in result.output
