"""Focused tests for the separate registry lifecycle verdicts."""

from __future__ import annotations

import json
import re
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from cadrumo.domain.calculations.registry.authority_artifact import AuthorityComponentCodecError
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from dev._paths import REPO_ROOT
from dev.registry.analysis import generated_tree_state, registry_status
from dev.registry.pipeline import cli as pipeline_cli
from dev.registry.pipeline.authority_publication import AuthorityDatabaseCurrencyStatus

from .. import cli

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


#: The two-character ``\\t`` as it appears in the CLI module's SOURCE, which is what a
#: scan of that text has to split on. A real tab would match nothing there.
_SOURCE_TAB_ESCAPE = "\\t"


def _authority() -> SimpleNamespace:
    return SimpleNamespace(
        modelos=(SimpleNamespace(revisions={"2025": object()}),),
        catalogues=SimpleNamespace(legal={"legal-1": object()}),
    )


def _indexed_authority() -> SimpleNamespace:
    @contextmanager
    def operation():
        yield SimpleNamespace(modelo_ids=lambda: ("296",), revision_ids=lambda: (("296", "2025"),))

    return SimpleNamespace(operation=operation, close=lambda: None)


def test_valid_is_a_fail_closed_whole_registry_verdict(monkeypatch) -> None:
    monkeypatch.setattr(cli, "validate_registry", lambda **_: _authority())

    result = CliRunner().invoke(cli.app, ["valid", "--json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["status"] == "passed"
    assert payload["revision_count"] == 1


def test_valid_refuses_a_registry_validation_failure(monkeypatch) -> None:
    refusal = RegistryValidationError("malformed registry definition")

    def refuse(**_: object) -> None:
        raise refusal

    monkeypatch.setattr(cli, "validate_registry", refuse)

    result = CliRunner().invoke(cli.app, ["valid"])

    assert result.exit_code == 1
    assert "registry-valid\tstatus=failed" in result.stderr
    assert type(refusal).__name__ in result.stderr
    assert str(refusal) in result.stderr


def test_runtime_load_reports_the_artifact_backed_authority_as_loadable(monkeypatch) -> None:
    monkeypatch.setattr(cli, "load_bundled_runtime_authority", _indexed_authority)

    result = CliRunner().invoke(cli.app, ["runtime-load", "--json"])

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["loadable"] is True


def test_runtime_load_fails_closed_on_an_unreadable_authority(monkeypatch) -> None:
    def refuse() -> None:
        raise AuthorityComponentCodecError("corrupt authority")

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
    advertised = _advertised_follow_ups(result.output)
    assert advertised == {
        "currentness": "check-registry-target-current",
        "publication": "registry-publish-authority-if-authority-stale",
    }
    defined = _justfile_recipe_names()
    missing = sorted(name for name in advertised.values() if name not in defined)
    assert not missing, f"the CLI advertises recipes the justfile does not define: {missing}"


def _advertised_follow_ups(output: str) -> dict[str, str]:
    """Return the ``next`` line's advertised follow-up recipes, keyed by role.

    The CLI prints guidance an operator is expected to run verbatim, so these
    names are a contract with the recipe table rather than decoration.
    """
    for line in output.splitlines():
        if line.startswith("next\t"):
            return dict(field.split("=", 1) for field in line.split("\t")[1:] if "=" in field)
    raise AssertionError(f"the command printed no `next` guidance line: {output!r}")


def _justfile_recipe_names() -> frozenset[str]:
    """Return the names the repository's justfile defines at column zero.

    Parsed from the file rather than ``just --summary`` so the check needs no
    provisioned binary. The parse is deliberately permissive -- assignments
    match too -- because it is only ever asked whether a specific advertised
    name is present, and a superset cannot turn a missing recipe into a pass.
    """
    text = (REPO_ROOT / "justfile").read_text(encoding="utf-8")
    pattern = r"^([a-z0-9][a-z0-9-]*)(?:\s+[^:\n]*)?:"
    return frozenset(str(match.group(1)) for match in re.finditer(pattern, text, re.MULTILINE))


def _advertised_recipe_names_in_source() -> frozenset[str]:
    """Return every recipe name the pipeline CLI's guidance lines advertise.

    Read from the module source rather than by invoking each command, so a
    guidance line added to a verb no test drives is still covered. The names
    are what an operator is told to run next, so every one of them has to
    exist.
    """
    source = Path(pipeline_cli.__file__).read_text(encoding="utf-8")
    names: set[str] = set()
    for chunk in source.split('"next')[1:]:
        literal = chunk.split('"', 1)[0]
        for field in literal.split(_SOURCE_TAB_ESCAPE)[1:]:
            if "=" in field:
                names.add(field.split("=", 1)[1])
    return frozenset(names)


def test_every_advertised_follow_up_names_a_live_recipe() -> None:
    """No guidance line may name a recipe the justfile does not define.

    The CLI has advertised dangling names before, and an assertion on one
    verb's literal output cannot see the next one: it pins the string rather
    than resolving it. This resolves every advertised name against the live
    recipe table instead.
    """
    advertised = _advertised_recipe_names_in_source()
    assert advertised, "no recipe names were scanned out of the guidance lines; the scan is broken"
    defined = _justfile_recipe_names()
    missing = sorted(name for name in advertised if name not in defined)
    assert not missing, f"the pipeline CLI advertises recipes the justfile does not define: {missing}"


def test_status_delegates_axes_and_counts_excluded_targets(monkeypatch) -> None:
    authority = SimpleNamespace(
        modelos=(
            SimpleNamespace(
                id="296",
                revisions={
                    "2024-y-siguientes": SimpleNamespace(
                        bindings=(),
                        casillas=(),
                        formulas=(),
                        export_layouts=(),
                    ),
                    "2025": SimpleNamespace(
                        bindings=(),
                        casillas=(),
                        formulas=(),
                        export_layouts=(),
                    ),
                },
            ),
        ),
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
        "generated_state_inventory",
        lambda *_args, **_kwargs: (
            (
                generated_tree_state.GeneratedTreeState(
                    "296",
                    "2024-y-siguientes",
                    "reproducible",
                    (),
                    (),
                    "reproduces exactly",
                ),
            ),
            (),
        ),
    )
    monkeypatch.setattr(
        registry_status,
        "authority_database_currency",
        lambda *_args, **_kwargs: SimpleNamespace(
            status=AuthorityDatabaseCurrencyStatus.CURRENT,
            detail="",
            recorded_identity_digest=None,
            candidate_identity_digest=None,
        ),
    )
    monkeypatch.setattr(
        registry_status,
        "load_bundled_runtime_authority",
        lambda: calls.append("load") or SimpleNamespace(close=lambda: None),
    )

    status = registry_status.collect_registry_status(
        registry_root=Path("registry"),
        source_root=Path("source"),
        authority_descriptor=Path("authority.current.json"),
    )

    assert status.valid is True
    assert status.oracles is True
    assert dict(status.targets) == {
        "current": 1,
        "explained": 0,
        "stale": 0,
        "drifted": 0,
        "never-committed": 0,
        "unreadable": 1,
    }
    assert status.authority == "current"
    assert status.loadable is True
    assert calls == ["valid", "oracles", "load"]
    assert "excluded by the generated-state owner" in " ".join(status.details)
