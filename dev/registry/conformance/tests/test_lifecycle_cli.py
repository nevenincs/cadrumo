"""Focused tests for the separate registry lifecycle verdicts."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from cadrumo.domain.calculations.registry.authority_artifact import AuthorityArtifactError
from dev.registry.analysis import generated_tree_state, registry_status
from dev.registry.pipeline import cli as pipeline_cli
from dev.registry.pipeline.authority_publication import AuthorityArtifactCurrencyStatus

from .. import cli

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _authority() -> SimpleNamespace:
    return SimpleNamespace(
        modelos=(SimpleNamespace(revisions={"2025": object()}),),
        catalogues=SimpleNamespace(legal={"legal-1": object()}),
    )


def test_valid_is_a_fail_closed_whole_registry_verdict(monkeypatch) -> None:
    monkeypatch.setattr(cli, "validate_registry", lambda **_: _authority())

    result = CliRunner().invoke(cli.app, ["valid", "--json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["status"] == "passed"
    assert payload["revision_count"] == 1


def test_valid_refuses_a_registry_validation_failure(monkeypatch) -> None:
    monkeypatch.setattr(cli, "validate_registry", lambda **_: (_ for _ in ()).throw(ValueError("malformed")))

    result = CliRunner().invoke(cli.app, ["valid"])

    assert result.exit_code == 1
    assert "registry-valid\tstatus=failed" in result.stderr


def test_runtime_load_reports_the_artifact_backed_authority_as_loadable(monkeypatch) -> None:
    monkeypatch.setattr(cli, "load_bundled_runtime_authority", _authority)

    result = CliRunner().invoke(cli.app, ["runtime-load", "--json"])

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["loadable"] is True


def test_runtime_load_fails_closed_on_an_unreadable_authority(monkeypatch) -> None:
    def refuse() -> None:
        raise AuthorityArtifactError("corrupt authority")

    monkeypatch.setattr(cli, "load_bundled_runtime_authority", refuse)

    result = CliRunner().invoke(cli.app, ["runtime-load"])

    assert result.exit_code == 1
    assert "registry-runtime-load\tstatus=failed\tloadable=false" in result.stderr


def test_pipeline_help_exposes_distinct_lifecycle_entry_points() -> None:
    result = CliRunner().invoke(pipeline_cli.app, ["--help"])

    assert result.exit_code == 0, result.output
    for command in ("target-current", "publish-target", "republish-target", "publish-authority"):
        assert command in result.output


def test_target_mutation_reports_follow_up_currentness_and_publication(monkeypatch) -> None:
    monkeypatch.setattr(pipeline_cli, "_run", lambda *_args, **_kwargs: None)

    result = CliRunner().invoke(
        pipeline_cli.app,
        ["publish-target", "296", "2024-y-siguientes", "aeat-dr-296-2024", "2024", "0A"],
    )

    assert result.exit_code == 0, result.output
    assert "next\tcurrentness=check-registry-target-current" in result.output
    assert "publication=registry-publish-authority-if-authority-stale" in result.output


def test_status_delegates_axes_and_counts_excluded_targets(monkeypatch) -> None:
    authority = SimpleNamespace(
        modelos=(SimpleNamespace(id="296", revisions={"2024-y-siguientes": object(), "2025": object()}),),
    )
    calls: list[str] = []

    monkeypatch.setattr(registry_status, "validate_registry", lambda **_: calls.append("valid") or authority)
    monkeypatch.setattr(
        registry_status,
        "audit_registry_oracles",
        lambda *_args, **_kwargs: calls.append("oracles") or SimpleNamespace(failures=()),
    )
    monkeypatch.setattr(
        generated_tree_state,
        "generated_state_facts",
        lambda *_args, **_kwargs: (
            generated_tree_state.GeneratedTreeState(
                "296",
                "2024-y-siguientes",
                "reproducible",
                (),
                (),
                "reproduces exactly",
            ),
        ),
    )
    monkeypatch.setattr(
        registry_status,
        "authority_artifact_currency",
        lambda *_args, **_kwargs: SimpleNamespace(status=AuthorityArtifactCurrencyStatus.CURRENT, detail=""),
    )
    monkeypatch.setattr(
        registry_status,
        "load_bundled_runtime_authority",
        lambda: calls.append("load") or authority,
    )

    status = registry_status.collect_registry_status(
        registry_root=Path("registry"),
        source_root=Path("source"),
        authority_artifact=Path("authority.json"),
    )

    assert status.valid is True
    assert status.oracles is True
    assert dict(status.targets) == {
        "current": 1,
        "stale": 0,
        "drifted": 0,
        "never-committed": 0,
        "unreadable": 1,
    }
    assert status.authority == "current"
    assert status.loadable is True
    assert calls == ["valid", "oracles", "load"]
    assert "excluded by the generated-state owner" in " ".join(status.details)
