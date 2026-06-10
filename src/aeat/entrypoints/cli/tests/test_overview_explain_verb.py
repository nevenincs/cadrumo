"""CLI surface tests for ``aeat app overview explain``."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ....application.user_profile._orchestration import profile_create_storage_span
from ....application.user_profile._testing import register_minimal_profile
from ....application.workflow._persistence import workflow_state_repository
from ....tests.secure_sql import isolated_profile_storage_root
from .. import app
from .._overview import app as overview_app

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


EXPECTED_OVERVIEW_VERBS: frozenset[str] = frozenset(
    {"status", "calendar", "agenda", "backlog", "explain"},
)


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path) -> Iterator[None]:
    with (
        isolated_profile_storage_root(tmp_path=tmp_path),
        profile_create_storage_span("operator"),
    ):
        workflow_state_repository().update(
            lambda state: register_minimal_profile(state, profile_id="operator"),
        )
        yield


def test_overview_verb_roster_locks_five_verb_tree() -> None:
    """Boundary regression: the overview noun-group must expose exactly
    the five canonical verbs: status / calendar / agenda / backlog /
    explain. Adding or removing one without updating the reviewed
    surface contract is drift."""

    registered = frozenset(cmd.name for cmd in overview_app.registered_commands if cmd.name is not None)
    missing = EXPECTED_OVERVIEW_VERBS - registered
    extras = registered - EXPECTED_OVERVIEW_VERBS
    assert not missing, f"overview verbs disappeared: {sorted(missing)}"
    assert not extras, f"overview verbs added without test update: {sorted(extras)}"


def test_explain_requires_modelo_argument(cli_runner: CliRunner) -> None:
    """The MODELO positional argument is required."""

    result = cli_runner.invoke(app, ["app", "overview", "explain"])
    assert result.exit_code != 0, result.output


def test_explain_renders_envelope_for_known_modelo(cli_runner: CliRunner) -> None:
    """A known modelo with an explicit --year yields the typed envelope
    with applicable + rationale + profile_facts rows."""

    result = cli_runner.invoke(
        app,
        ["app", "overview", "explain", "303", "--year", "2026"],
    )
    assert result.exit_code == 0, result.output
    assert "modelo\t303" in result.output
    assert "year\t2026" in result.output
    assert "applicable\t" in result.output
    assert "rationale\t" in result.output
    assert "profile_fact\ttax_id\t" in result.output


def test_explain_refuses_unknown_modelo(cli_runner: CliRunner) -> None:
    """An unknown modelo identifier surfaces as a refusal at the CLI
    exit code rather than a stack trace."""

    result = cli_runner.invoke(
        app,
        ["app", "overview", "explain", "999999", "--year", "2026"],
    )
    assert result.exit_code != 0, result.output


def test_explain_help_advertises_local_only(cli_runner: CliRunner) -> None:
    """Help text must signal `local-only` across locales."""

    result = cli_runner.invoke(app, ["app", "overview", "explain", "--help"])
    assert result.exit_code == 0, result.output
    assert any(
        token in result.output.lower() for token in ("local-only", "local;", "nunca", "mai contacta", "csak helyi")
    ), result.output


def test_explain_721_returns_structured_payload_not_crash(cli_runner: CliRunner) -> None:
    """M721 applicability rule: ``explain 721`` must return exit 0 with both
    legal refs from Ley 11/2021 DA 10 (obligation) and RD 1065/2007 art. 42
    quater (50,000 EUR threshold) — never a raw OverviewExplainError traceback.

    Regression guard for the defect-of-record state where Modelo 721 was absent
    from the registry and ``build_overview_explain`` raised
    ``OverviewExplainError("could not evaluate")``.

    The prior assertion also required ``orden-hfp-887-2023:art-3`` but that
    slug does not resolve against the registry legal catalogue (no such order
    is grounded). The applicability seed was corrected to the two
    BOE-grounded refs in commit 9be3af126; this test mirrors that grounding.
    """

    result = cli_runner.invoke(
        app,
        ["app", "overview", "explain", "721", "--year", "2024"],
    )
    assert result.exit_code == 0, result.output
    assert "OverviewExplainError" not in result.output, result.output
    assert "could not evaluate" not in result.output, result.output
    # Both grounding legal refs must appear in the CLI output.
    assert "ley-11-2021:da-10" in result.output, result.output
    assert "rd-1065-2007:art-42-quater" in result.output, result.output
