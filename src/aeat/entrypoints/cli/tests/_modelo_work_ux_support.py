"""Shared helpers for Modelo work UX CLI tests."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from ....adapters.persistence.storage.sql.engine import dispose_engine

# Importing the wizard catalogue + persistence modules triggers
# register_wizard_catalogue() at import time, exactly as the production CLI
# startup does.
from ....application.wizard import _catalogue as _wizard_catalogue
from ....application.wizard import _persistence as _wizard_persistence
from ....core.config import override_settings
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_profile_storage_root
from .envelope_helpers import unwrap_schema_envelope as _payload

_WIZARD_REGISTRATION_MODULES = (_wizard_catalogue, _wizard_persistence)
_PROFILE_ID = "operator"


@pytest.fixture(autouse=True)
def _isolated_cli_backend(tmp_path: Path) -> Iterator[None]:
    """Isolated storage root; each invoke opens the active UUID bucket session."""
    dispose_engine()
    with (
        override_settings(aeat_local_storage_root=tmp_path, aeat_output_language="en"),
        isolated_profile_storage_root(tmp_path=tmp_path),
    ):
        try:
            yield
        finally:
            dispose_engine()


def _invoke(args: list[str]):
    return invoke_cached_cli(args)


def _create_profile(*, activity_start_date: str | None = None) -> None:
    args = [
        "config",
        "profile",
        "create",
        "operator",
        "--quiet",
        "--accept-defaults",
        "--entity-type",
        "natural_person",
        "--irpf-income-categories",
        "actividad_economica",
        "--tax-id",
        "12345678Z",
        "--name",
        "Operator",
        "--surnames",
        "Readiness",
        "--activity",
        "design",
    ]
    if activity_start_date is not None:
        args.extend(["--activity-start-date", activity_start_date])
    result = _invoke(args)  # fmt: skip
    assert result.exit_code == 0, result.output


def _create_gb_non_resident_profile() -> None:
    result = _invoke(
        [
            "config", "profile", "create", "operator",
            "--quiet", "--accept-defaults",
            "--entity-type", "natural_person",
            "--tax-id", "12345678Z",
            "--name", "Operator",
            "--surnames", "Readiness",
            "--activity", "Spanish-source rent",
            "--fiscal-residency", "non_resident_irnr",
            "--country-of-fiscal-residence", "GB",
            "--representante-fiscal-nif", "12345678Z",
            "--representante-fiscal-nombre", "Test Representative",
        ],
    )  # fmt: skip
    assert result.exit_code == 0, result.output


def _create_de_nonresident_legal_entity_profile() -> None:
    result = _invoke(
        [
            "config", "profile", "create", "operator",
            "--quiet", "--accept-defaults",
            "--entity-type", "legal_entity",
            "--legal-entity-form", "sl",
            "--tax-id", "B66012345",
            "--legal-name", "NordHaus GmbH",
            "--activity", "Spanish-source services",
            "--fiscal-residency", "non_resident_irnr",
            "--country-of-fiscal-residence", "DE",
            "--iva-regime", "GENERAL",
        ],
    )  # fmt: skip
    assert result.exit_code == 0, result.output


def _attempt_incomplete_profile_create():
    return _invoke(
        [
            "--format", "json",
            "config", "profile", "create", _PROFILE_ID,
            "--quiet", "--accept-defaults",
            "--tax-id", "12345678Z",
            "--activity", "design",
        ],
    )  # fmt: skip


def _create_work_unit() -> str:
    result = _invoke(
        [
            "--format", "json",
            "app", "modelo", "work", "create",
            "--modelo", "130", "--year", "2025", "--period", "1T",
            "--revision", "2019-y-siguientes",
        ],
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    return _payload(result.output)["work_unit_id"]


def _create_calculable_work_unit() -> str:
    """Create a modelo 111 work unit whose `work calculate` succeeds with
    no operator-supplied inputs."""
    result = _invoke(
        [
            "--format", "json",
            "app", "modelo", "work", "create",
            "--modelo", "111", "--year", "2025", "--period", "1T",
            "--revision", "2019-y-siguientes",
        ],
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    return _payload(result.output)["work_unit_id"]
