"""CLI surface tests for ``aeat app overview explain``."""

from __future__ import annotations

import pytest

from ....tests.cli_runner import invoke_cached_cli
from ..command_api import command_spec_nodes
from ._isolated_profile_storage_fixtures import active_profile_isolated_backend

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]
__all__ = ["active_profile_isolated_backend"]


EXPECTED_OVERVIEW_VERBS: frozenset[str] = frozenset(
    {"status", "calendar", "agenda", "backlog", "explain", "prepare", "pipeline"},
)


def test_overview_verb_roster_locks_five_verb_tree() -> None:
    """Boundary regression: the overview noun-group must expose exactly
    the canonical verb set: status / calendar / agenda / backlog /
    explain / prepare / pipeline. Adding or removing one without
    updating the reviewed surface contract is drift."""

    registered = frozenset(node.spec.token for node in command_spec_nodes() if node.spec.parent_key == "app_overview")
    missing = EXPECTED_OVERVIEW_VERBS - registered
    extras = registered - EXPECTED_OVERVIEW_VERBS
    assert not missing, f"overview verbs disappeared: {sorted(missing)}"
    assert not extras, f"overview verbs added without test update: {sorted(extras)}"


def test_explain_requires_modelo_argument() -> None:
    """The MODELO positional argument is required."""

    result = invoke_cached_cli(["app", "overview", "explain"])
    assert result.exit_code != 0, result.output


def test_explain_renders_envelope_for_known_modelo() -> None:
    """A known modelo with an explicit --year yields the typed envelope
    with applicable + rationale + profile_facts rows."""

    result = invoke_cached_cli(
        ["app", "overview", "explain", "303", "--year", "2026"],
    )
    assert result.exit_code == 0, result.output
    assert "modelo\t303" in result.output
    assert "year\t2026" in result.output
    assert "applicable\t" in result.output
    assert "rationale\t" in result.output
    assert "profile_fact\ttax_id\t" in result.output


def test_explain_refuses_unknown_modelo() -> None:
    """An unknown modelo identifier surfaces as a refusal at the CLI
    exit code rather than a stack trace."""

    result = invoke_cached_cli(
        ["app", "overview", "explain", "999999", "--year", "2026"],
    )
    assert result.exit_code != 0, result.output


def test_explain_help_advertises_local_only() -> None:
    """Help text must signal `local-only` across locales."""

    result = invoke_cached_cli(["app", "overview", "explain", "--help"])
    assert result.exit_code == 0, result.output
    assert any(
        token in result.output.lower() for token in ("local-only", "local;", "nunca", "mai contacta", "csak helyi")
    ), result.output


def test_explain_721_returns_structured_payload_not_crash() -> None:
    """M721 explain must return exit 0 and suppress default false profiles.

    Regression guard for the defect-of-record state where Modelo 721 was absent
    from the registry and ``build_overview_explain`` raised
    ``OverviewExplainError("could not evaluate")``.
    """

    result = invoke_cached_cli(
        ["app", "overview", "explain", "721", "--year", "2024"],
    )
    assert result.exit_code == 0, result.output
    assert "OverviewExplainError" not in result.output, result.output
    assert "could not evaluate" not in result.output, result.output
    assert "applicable\tfalse" in result.output, result.output
    assert "verdict\tincomplete" in result.output, result.output
    assert "profile_fact\tmonedas_virtuales_extranjero_above_threshold\tFalse" in result.output, result.output
    assert "ley-58-2003:da-18" in result.output, result.output
    assert "rd-1065-2007:art-42-quater" in result.output, result.output
    assert "orden-hfp-886-2023:art-2" in result.output, result.output
