"""Smoke tests for engineer-only profile diagnostics."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from typer.testing import CliRunner

from aeat.adapters.persistence.storage.sql.engine import dispose_engine
from aeat.application.user_profile._orchestration import (
    build_lifecycle_service,
    profile_create_storage_span,
    select_profile_with_lifecycle_span,
)
from aeat.application.user_profile._testing import register_minimal_profile
from aeat.application.workflow._persistence import workflow_state_repository
from aeat.diagnostics.__main__ import app
from aeat.tests.secure_sql import isolated_profile_storage_root

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path) -> Iterator[None]:
    with isolated_profile_storage_root(tmp_path=tmp_path):
        yield


def _seed_profile(profile_id: str) -> None:
    with profile_create_storage_span(profile_id):
        workflow_state_repository().update(
            lambda state: register_minimal_profile(
                state,
                profile_id=profile_id,
                enforce_unique_tax_id=False,
            )
        )
    dispose_engine()


def _read_fact(profile_id: str, path: str) -> str | None:
    from aeat.application.user_profile._orchestration import fact_value, profile_storage_session

    with profile_storage_session(profile_id):
        record = build_lifecycle_service(bucket_id=profile_id).read(profile_id)
    return fact_value(record, path)


def test_profile_get_rejects_unknown_profile_key_with_localized_boundary(runner: CliRunner) -> None:
    result = runner.invoke(app, ["profile", "get", "not.a.profile.key"])

    assert result.exit_code != 0
    assert "not.a.profile.key" in result.output


def test_profile_get_rejects_blank_profile_option_before_storage_lookup(runner: CliRunner) -> None:
    _seed_profile("operator")

    result = runner.invoke(app, ["profile", "get", "identity.tax_id", "--profile", " "])

    assert result.exit_code != 0
    assert "--profile" in result.output


def test_profile_set_explicit_profile_updates_named_bucket_not_active_bucket(runner: CliRunner) -> None:
    _seed_profile("active")
    _seed_profile("named")
    select_profile_with_lifecycle_span("active")
    dispose_engine()

    result = runner.invoke(app, ["profile", "set", "identity.name", "Named Operator", "--profile", "named"])

    assert result.exit_code == 0, result.output
    assert "identity.name\tNamed Operator" in result.output
    assert _read_fact("named", "identity.name") == "Named Operator"
    assert _read_fact("active", "identity.name") == "Test Operator"


def test_profile_get_explicit_profile_reads_named_bucket_not_active_bucket(runner: CliRunner) -> None:
    _seed_profile("active")
    _seed_profile("named")
    select_profile_with_lifecycle_span("active")
    dispose_engine()
    set_result = runner.invoke(app, ["profile", "set", "identity.name", "Named Operator", "--profile", "named"])
    assert set_result.exit_code == 0, set_result.output

    result = runner.invoke(app, ["profile", "get", "identity.name", "--profile", "named"])

    assert result.exit_code == 0, result.output
    assert "identity.name\tNamed Operator" in result.output


def test_profile_get_uses_canonical_case_insensitive_key(runner: CliRunner) -> None:
    _seed_profile("active")
    select_profile_with_lifecycle_span("active")
    dispose_engine()

    result = runner.invoke(app, ["profile", "get", "IDENTITY.NAME"])

    assert result.exit_code == 0, result.output
    assert "identity.name\tTest Operator" in result.output
    assert "IDENTITY.NAME" not in result.output


def test_profile_unset_explicit_profile_updates_named_bucket_not_active_bucket(runner: CliRunner) -> None:
    _seed_profile("active")
    _seed_profile("named")
    select_profile_with_lifecycle_span("active")
    dispose_engine()

    result = runner.invoke(app, ["profile", "unset", "identity.name", "--profile", "named"])

    assert result.exit_code == 0, result.output
    assert "identity.name\t<unset>" in result.output
    assert _read_fact("named", "identity.name") is None
    assert _read_fact("active", "identity.name") == "Test Operator"


def test_profile_unset_uses_canonical_case_insensitive_key(runner: CliRunner) -> None:
    _seed_profile("active")
    select_profile_with_lifecycle_span("active")
    dispose_engine()

    result = runner.invoke(app, ["profile", "unset", "IDENTITY.NAME"])

    assert result.exit_code == 0, result.output
    assert "identity.name\t<unset>" in result.output
    assert "IDENTITY.NAME" not in result.output
    assert _read_fact("active", "identity.name") is None
