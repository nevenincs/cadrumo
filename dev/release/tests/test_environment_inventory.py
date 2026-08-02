"""Behavioural proof for the read-only forge environment inventory.

Every subprocess case drives a REAL executable stub through a real
``subprocess.run``, matching the pattern the readiness gate's blocker check
already uses. Nothing here is mocked or patched: the probe's whole value is
that it reports what a real ``gh`` invocation actually returns, and a test that
substituted the call would be asserting the substitution.

The load-bearing property is the three-way distinction. "Rule present", "rule
absent", and "could not be read" must stay three outcomes, because collapsing
the third into the second reports an unreadable forge as a satisfied
obligation - which is the exact shape of the untracked partial executions this
probe exists to make visible.
"""

from __future__ import annotations

import json
import stat
import sys
from pathlib import Path

import pytest

from dev.release import environment_inventory

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _write_probe_gh(bin_dir: Path, *, payload: str, exit_code: int = 0) -> Path:
    """Write a real executable `gh` stub emitting fixed real process output."""
    bin_dir.mkdir(parents=True, exist_ok=True)
    if sys.platform.startswith("win"):
        script = bin_dir / "gh.bat"
        escaped = payload.replace("%", "%%").replace("^", "^^").replace(">", "^>").replace("<", "^<").replace("|", "^|")
        script.write_text(f"@echo off\r\necho {escaped}\r\nexit /b {exit_code}\r\n", encoding="utf-8")
    else:
        script = bin_dir / "gh"
        script.write_text(
            f"#!/usr/bin/env bash\ncat <<'PAYLOAD'\n{payload}\nPAYLOAD\nexit {exit_code}\n", encoding="utf-8"
        )
        script.chmod(script.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return script


def test_reports_the_human_approval_rule_when_it_is_present(tmp_path: Path) -> None:
    """A `release` environment still carrying required_reviewers reports OP-9 outstanding."""
    payload = json.dumps(
        {"name": "release", "protection_rules": [{"type": "required_reviewers"}, {"type": "branch_policy"}]}
    )
    script = _write_probe_gh(tmp_path / "bin", payload=payload)

    records = environment_inventory.fetch_environments(("release",), gh_executable=str(script))

    assert len(records) == 1
    record = records[0]
    assert record.readable is True
    assert record.carries_human_approval_gate is True
    assert record.rule_types == ("required_reviewers", "branch_policy")

    report = environment_inventory.render_report(records)
    assert "OP-9 OUTSTANDING" in report
    # The refusal must not read as "delete the environment": that is the naive
    # reading that breaks OIDC publication outright.
    assert "Keep the environment and its branch_policy" in report


def test_reports_the_rule_absent_once_the_operator_has_removed_it(tmp_path: Path) -> None:
    """branch_policy alone is the satisfied end state, not an empty rule set."""
    payload = json.dumps({"name": "release", "protection_rules": [{"type": "branch_policy"}]})
    script = _write_probe_gh(tmp_path / "bin", payload=payload)

    records = environment_inventory.fetch_environments(("release",), gh_executable=str(script))

    assert records[0].readable is True
    assert records[0].carries_human_approval_gate is False
    assert records[0].rule_types == ("branch_policy",)
    assert "OP-9 satisfied" in environment_inventory.render_report(records)


def test_an_unreadable_environment_is_never_reported_as_satisfied(tmp_path: Path) -> None:
    """A failed read is UNKNOWN, not clean.

    This is the case the whole three-way distinction exists for. An environment
    whose rules could not be determined and an environment with no rules are
    opposite facts, and a probe that renders both as "no required_reviewers"
    would report an unreachable forge as an obligation discharged.
    """
    script = _write_probe_gh(tmp_path / "bin", payload="gh: not found", exit_code=1)

    records = environment_inventory.fetch_environments(("release",), gh_executable=str(script))

    assert records[0].readable is False
    assert records[0].rule_types is None
    assert records[0].carries_human_approval_gate is None
    assert "UNKNOWN" in environment_inventory.render_report(records)
    assert "OP-9 satisfied" not in environment_inventory.render_report(records)


def test_non_json_output_is_unreadable_rather_than_rule_free(tmp_path: Path) -> None:
    """A zero-exit that emits garbage is still an undetermined read."""
    script = _write_probe_gh(tmp_path / "bin", payload="<html>login required</html>")

    records = environment_inventory.fetch_environments(("release",), gh_executable=str(script))

    assert records[0].readable is False
    assert "non-JSON" in records[0].detail


def test_a_missing_gh_yields_unknown_for_every_requested_environment(tmp_path: Path) -> None:
    """Absent tooling degrades to UNKNOWN across the board, never to clean."""
    missing = tmp_path / "bin" / "definitely-not-gh"

    records = environment_inventory.fetch_environments(("release", "docs"), gh_executable=str(missing))

    assert [r.name for r in records] == ["release", "docs"]
    assert all(r.readable is False for r in records)


def test_both_op9_environments_are_inventoried_by_default() -> None:
    """OP-9 covers `release` AND `docs`; a probe that forgot one would hide half of it.

    The docs environment carries the same rule class, and the automated
    documentation consequence would stop at an approval click the moment its
    deploy-role variable lands. Defaulting to only `release` would report the
    obligation complete while half of it stood.
    """
    assert environment_inventory.OP9_ENVIRONMENTS == ("release", "docs")


def test_the_parse_layer_tolerates_a_malformed_neighbour_rule() -> None:
    """A rule with no type is skipped; the rules that did parse still answer.

    Exercised directly on the parse layer because it needs no process at all,
    and because the tolerance is a deliberate choice worth pinning: a
    neighbouring unparseable rule must not silently turn a present human gate
    into an absent one.
    """
    types = environment_inventory.protection_rule_types(
        {"protection_rules": [{"no_type_key": True}, {"type": "required_reviewers"}]}
    )
    assert types == ("required_reviewers",)

    # A payload with no rules key at all is genuinely rule-free, not malformed.
    assert environment_inventory.protection_rule_types({"name": "release"}) == ()


def _write_workflow(workflows_dir: Path, filename: str, *, environment_yaml: str | None) -> None:
    """Write a minimal real workflow file, optionally declaring one job's `environment:`."""
    workflows_dir.mkdir(parents=True, exist_ok=True)
    body = "on: push\njobs:\n  build:\n    runs-on: ubuntu-latest\n"
    if environment_yaml is not None:
        body += f"    environment: {environment_yaml}\n"
    (workflows_dir / filename).write_text(body, encoding="utf-8")


def test_environments_referenced_by_workflows_reads_the_scalar_form(tmp_path: Path) -> None:
    _write_workflow(tmp_path / ".github" / "workflows", "publish-release.yml", environment_yaml="release")
    _write_workflow(tmp_path / ".github" / "workflows", "docs-publish.yml", environment_yaml="docs")

    references = environment_inventory.environments_referenced_by_workflows(tmp_path)

    assert references["release"] == (".github/workflows/publish-release.yml",)
    assert references["docs"] == (".github/workflows/docs-publish.yml",)
    assert "pypi-data-official" not in references


def test_environments_referenced_by_workflows_reads_the_mapping_name_form(tmp_path: Path) -> None:
    workflows_dir = tmp_path / ".github" / "workflows"
    workflows_dir.mkdir(parents=True)
    (workflows_dir / "deploy.yml").write_text(
        "on: push\njobs:\n  build:\n    runs-on: ubuntu-latest\n"
        "    environment:\n      name: release\n      url: https://example.invalid\n",
        encoding="utf-8",
    )

    references = environment_inventory.environments_referenced_by_workflows(tmp_path)

    assert references["release"] == (".github/workflows/deploy.yml",)


def test_environments_referenced_by_workflows_ignores_a_malformed_workflow_file(tmp_path: Path) -> None:
    """A neighbour's YAML error must not blind the scan to every other workflow."""
    workflows_dir = tmp_path / ".github" / "workflows"
    workflows_dir.mkdir(parents=True)
    (workflows_dir / "broken.yml").write_text("jobs: [unterminated\n", encoding="utf-8")
    _write_workflow(workflows_dir, "publish-release.yml", environment_yaml="release")

    references = environment_inventory.environments_referenced_by_workflows(tmp_path)

    assert references["release"] == (".github/workflows/publish-release.yml",)


def test_environments_referenced_by_workflows_returns_empty_without_a_workflows_dir(tmp_path: Path) -> None:
    assert environment_inventory.environments_referenced_by_workflows(tmp_path) == {}


def test_fetch_environments_marks_an_unreferenced_environment_as_orphaned(tmp_path: Path) -> None:
    """The gate case: an environment naming an absent-workflow path is reported orphaned."""
    workflows_dir = tmp_path / ".github" / "workflows"
    _write_workflow(workflows_dir, "publish-release.yml", environment_yaml="release")
    _write_workflow(workflows_dir, "docs-publish.yml", environment_yaml="docs")
    # pypi-data-official's owning workflow (pypi-upload.yml) is absent: no
    # workflow file in this fixture tree declares environment: pypi-data-official.
    payload = json.dumps({"name": "pypi-data-official", "protection_rules": [{"type": "branch_policy"}]})
    script = _write_probe_gh(tmp_path / "bin", payload=payload)

    records = environment_inventory.fetch_environments(
        ("pypi-data-official",),
        gh_executable=str(script),
        repo_root=tmp_path,
    )

    assert len(records) == 1
    record = records[0]
    assert record.readable is True
    assert record.referenced_by == ()
    assert record.is_orphaned is True

    report = environment_inventory.render_report(records)
    assert "OP-12 OUTSTANDING" in report
    assert "ORPHANED" in report
    assert "pypi-data-official" in report


def test_fetch_environments_marks_a_referenced_environment_as_not_orphaned(tmp_path: Path) -> None:
    workflows_dir = tmp_path / ".github" / "workflows"
    _write_workflow(workflows_dir, "publish-release.yml", environment_yaml="release")
    payload = json.dumps({"name": "release", "protection_rules": []})
    script = _write_probe_gh(tmp_path / "bin", payload=payload)

    records = environment_inventory.fetch_environments(
        ("release",),
        gh_executable=str(script),
        repo_root=tmp_path,
    )

    assert records[0].referenced_by == (".github/workflows/publish-release.yml",)
    assert records[0].is_orphaned is False
    assert "OP-12" not in environment_inventory.render_report(records)


def test_is_orphaned_is_unknown_without_a_repo_root_scan(tmp_path: Path) -> None:
    """Omitting repo_root must report unknown, never guess from an unscanned tree."""
    payload = json.dumps({"name": "pypi-data-official", "protection_rules": []})
    script = _write_probe_gh(tmp_path / "bin", payload=payload)

    records = environment_inventory.fetch_environments(("pypi-data-official",), gh_executable=str(script))

    assert records[0].referenced_by is None
    assert records[0].is_orphaned is None
    assert "OP-12" not in environment_inventory.render_report(records)


def test_is_orphaned_is_never_true_for_an_unreadable_environment(tmp_path: Path) -> None:
    """An orphan claim requires confirming the environment still exists on the forge."""
    script = _write_probe_gh(tmp_path / "bin", payload="gh: not found", exit_code=1)

    records = environment_inventory.fetch_environments(
        ("pypi-data-official",),
        gh_executable=str(script),
        repo_root=tmp_path,
    )

    assert records[0].readable is False
    assert records[0].is_orphaned is None


def test_default_inventoried_environments_covers_op9_and_every_orphan_candidate() -> None:
    assert environment_inventory.DEFAULT_INVENTORIED_ENVIRONMENTS == (
        "release",
        "docs",
        "pypi-data-official",
    )


def test_the_module_exposes_no_mutation_path() -> None:
    """The inventory reads. An auditor that could also write would be the risk it audits.

    Pinned rather than assumed: the probe reports on protection rules whose
    removal is an operator decision, so a future 'while we are here, just remove
    it' helper landing in this module would quietly convert an audit surface
    into standing authority over the settings it audits.
    """
    source = Path(environment_inventory.__file__).read_text(encoding="utf-8")
    for verb in ("--method delete", "--method put", "--method patch", "--method post", '"DELETE"', '"PATCH"'):
        assert verb.lower() not in source.lower(), f"the inventory module must not carry a {verb} mutation path"
