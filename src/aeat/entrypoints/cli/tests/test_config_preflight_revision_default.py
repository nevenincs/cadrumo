"""CLI surface tests for `aeat config profile preflight` revision defaulting.

These tests prove the operator-surface decision: ``--revision-id`` is no longer
required. When omitted, the active registry revision for the natural key
(modelo, filing year, period) is resolved through the modelo-addressing
resolver, which consumes the :class:`ValidatedRegistryAuthority`. An explicit
``--revision-id`` is honoured as an exact-replay override. An unresolvable or
ambiguous natural key refuses instructively, never with a bare error.

Every test runs against a real encrypted profile bucket and the real bundled
calculation registry; no mocks, stubs, or patches participate. The ambiguous
case installs a forged twin revision into the live authority's modelo map and
restores it in ``finally`` so the genuine ``select_revision`` dedup branch and
the genuine refusal-translation path are exercised end to end.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from pathlib import Path
from typing import cast

import click
import pytest
from click.testing import CliRunner, Result

from ....application.user_profile._orchestration import profile_create_storage_span
from ....application.user_profile._testing import register_minimal_profile
from ....application.workflow._persistence import workflow_state_repository
from ....core.resources import resources
from ....tests.secure_sql import isolated_profile_storage_root
from .. import app as root_app

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path) -> Iterator[None]:
    with isolated_profile_storage_root(tmp_path=tmp_path):
        yield


def _seed_active_profile(name: str = "operator") -> None:
    """Provision and activate a real minimal profile bucket.

    ``register_minimal_profile`` populates ``identity.tax_id`` and an
    activity so the profile carries the basics; preflight then reports
    only the modelo-specific selectors still missing (or none).
    """
    with profile_create_storage_span(name):
        workflow_state_repository().update(
            lambda state: register_minimal_profile(
                state,
                profile_id=name,
                enforce_unique_tax_id=False,
            )
        )


def _json_payload(result: Result) -> dict[str, object]:
    match = re.search(r"\{.*\}", result.output, re.DOTALL)
    assert match, result.output
    parsed: object = json.loads(match.group(0))
    assert isinstance(parsed, dict)
    return parsed  # ty: ignore[invalid-return-type]  # pyright: ignore[return-value]


def _active_revision_for(modelo: str, *, filing_year: int, period: str) -> str:
    """Resolve the expected active revision from the registry authority.

    Derives the expected value from the same authority the production
    resolver reads, not from a hand-copied literal: a registry edit that
    moves the active revision moves this expectation with it.
    """
    from ....application.modelo import resolve_registry_revision_for_work_target

    return resolve_registry_revision_for_work_target(
        modelo=modelo,
        filing_year=filing_year,
        period=period,
        registry_revision_id=None,
    )


def test_preflight_defaults_revision_from_natural_key(cli_runner: CliRunner) -> None:
    """Preflight answers from modelo, filing year, and period alone."""
    from typer.core import TyperGroup
    from typer.main import get_command

    _seed_active_profile()
    expected_revision = _active_revision_for("303", filing_year=2026, period="1T")

    cmd = get_command(root_app)
    assert isinstance(cmd, (click.Command, TyperGroup))
    result = cli_runner.invoke(
        cast(click.Command, cmd),
        [
            "--format",
            "json",
            "config",
            "profile",
            "preflight",
            "--modelo",
            "303",
            "--filing-year",
            "2026",
            "--period",
            "1T",
        ],
    )

    assert result.exit_code in (0, 2), result.output
    payload = _json_payload(result)
    result_data_obj = payload["result"]
    assert isinstance(result_data_obj, dict)
    result_data: dict[str, object] = result_data_obj  # ty: ignore[invalid-assignment]  # pyright: ignore[assignment]
    assert result_data["modelo"] == "303"
    assert result_data["filing_year"] == 2026
    assert result_data["period"] == "1T"
    # The resolved active revision is reported back, proving the natural-key
    # default fired rather than leaving the field blank or erroring.
    assert result_data["revision_id"] == expected_revision


def test_preflight_explicit_revision_override_is_honoured(cli_runner: CliRunner) -> None:
    """An explicit --revision-id selects that exact revision for replay."""
    from typer.core import TyperGroup
    from typer.main import get_command

    _seed_active_profile()
    expected_revision = _active_revision_for("303", filing_year=2026, period="1T")

    cmd = get_command(root_app)
    assert isinstance(cmd, (click.Command, TyperGroup))
    result = cli_runner.invoke(
        cast(click.Command, cmd),
        [
            "--format",
            "json",
            "config",
            "profile",
            "preflight",
            "--modelo",
            "303",
            "--filing-year",
            "2026",
            "--period",
            "1T",
            "--revision-id",
            expected_revision,
        ],
    )

    assert result.exit_code in (0, 2), result.output
    payload = _json_payload(result)
    result_data_obj = payload["result"]
    assert isinstance(result_data_obj, dict)
    result_data: dict[str, object] = result_data_obj  # ty: ignore[invalid-assignment]  # pyright: ignore[assignment]
    assert result_data["revision_id"] == expected_revision


def test_preflight_refuses_unresolvable_natural_key_with_discovery_pointer(cli_runner: CliRunner) -> None:
    """A period the modelo never declares refuses with a discovery pointer."""
    from typer.core import TyperGroup
    from typer.main import get_command

    _seed_active_profile()

    cmd = get_command(root_app)
    assert isinstance(cmd, (click.Command, TyperGroup))
    result = cli_runner.invoke(
        cast(click.Command, cmd),
        ["config", "profile", "preflight", "--modelo", "303", "--filing-year", "2026", "--period", "ZZ"],
    )

    assert result.exit_code != 0
    # The refusal must point at the discovery command, never a bare error.
    assert "aeat app modelo describe 303" in result.output


def test_preflight_refuses_invalid_explicit_override_with_registered_revisions(cli_runner: CliRunner) -> None:
    """An explicit --revision-id unknown to the modelo refuses instructively."""
    from typer.core import TyperGroup
    from typer.main import get_command

    _seed_active_profile()

    cmd = get_command(root_app)
    assert isinstance(cmd, (click.Command, TyperGroup))
    result = cli_runner.invoke(
        cast(click.Command, cmd),
        [
            "config",
            "profile",
            "preflight",
            "--modelo",
            "303",
            "--filing-year",
            "2026",
            "--period",
            "1T",
            "--revision-id",
            "not-a-real-revision",
        ],
    )

    assert result.exit_code != 0
    assert "aeat app modelo describe 303" in result.output


def test_preflight_refuses_ambiguous_natural_key_with_candidates(cli_runner: CliRunner) -> None:
    """When two revisions match the natural key, preflight lists candidates.

    The bundled registry is authored without overlapping revisions, so a
    real twin revision is installed into the live authority's modelo map for
    the duration of the test and restored afterwards. This exercises the
    genuine ``select_revision`` dedup branch and the genuine candidate-listing
    refusal translation, with no mock or patch object in play.
    """
    from typer.main import get_command

    _seed_active_profile()
    authority = resources().modelos.authority
    definition = authority.modelo("303")
    base_revision = definition.revisions["2023-y-siguientes"]
    twin = base_revision.model_copy(update={"id": "2023-y-siguientes-twin"})
    ambiguous = definition.model_copy(update={"revisions": {**definition.revisions, twin.id: twin}})
    original = authority._modelos_by_id["303"]
    authority._modelos_by_id["303"] = ambiguous
    try:
        from typer.core import TyperGroup
        from typer.main import get_command

        cmd = get_command(root_app)
        assert isinstance(cmd, (click.Command, TyperGroup))
        result = cli_runner.invoke(
            cast(click.Command, cmd),
            ["config", "profile", "preflight", "--modelo", "303", "--filing-year", "2026", "--period", "1T"],
        )
    finally:
        authority._modelos_by_id["303"] = original

    assert result.exit_code != 0
    # Both candidate revision ids must be named so the operator can pick one.
    assert "2023-y-siguientes" in result.output
    assert "2023-y-siguientes-twin" in result.output
    assert "--revision-id" in result.output


def test_ambiguous_resolution_carries_candidates_on_typed_field_not_message() -> None:
    """The preflight resolver discriminates the ambiguous case by exception
    TYPE and reads the candidate ids from the typed field, not by matching a
    substring of the human-readable message.

    This pins the robustness contract: a rewording of the
    ``AmbiguousRevisionSelectionError`` ``str()`` message must NOT break the
    operator-facing candidate listing, because the resolver never parses the
    message. The test installs a real twin revision into the live authority
    (no mock) so the genuine ``select_revision`` dedup branch fires, then
    asserts the refusal context carries both candidate ids verbatim.
    """
    from ....domain.calculations.registry import AmbiguousRevisionSelectionError
    from .._config import _resolve_preflight_revision_id
    from .._errors import CliRefusedBoundaryError

    authority = resources().modelos.authority
    definition = authority.modelo("303")
    base_revision = definition.revisions["2023-y-siguientes"]
    twin = base_revision.model_copy(update={"id": "2023-y-siguientes-twin"})
    ambiguous = definition.model_copy(update={"revisions": {**definition.revisions, twin.id: twin}})
    original = authority._modelos_by_id["303"]
    authority._modelos_by_id["303"] = ambiguous
    try:
        with pytest.raises(CliRefusedBoundaryError) as excinfo:
            _resolve_preflight_revision_id(modelo="303", filing_year=2026, period="1T", revision_id=None)
    finally:
        authority._modelos_by_id["303"] = original

    refusal = excinfo.value
    # The refusal was raised from the typed ambiguous subclass...
    cause = refusal.__cause__
    assert isinstance(cause, AmbiguousRevisionSelectionError)
    # ...and the candidate ids rode on the typed field, sorted.
    assert cause.candidate_ids == ("2023-y-siguientes", "2023-y-siguientes-twin")
    # The refusal context lists both ids so the operator surface stays intact
    # even though no message substring was parsed.
    assert refusal.context is not None
    candidates = refusal.context["candidates"]
    assert isinstance(candidates, str)
    assert "2023-y-siguientes" in candidates
    assert "2023-y-siguientes-twin" in candidates
