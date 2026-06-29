"""CLI coverage for config profile preflight scope wording."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from ....adapters.persistence.storage.sql.engine import dispose_engine
from ....core.config import override_settings
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_profile_storage_root

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@pytest.fixture(autouse=True)
def _isolated_cli_backend(tmp_path: Path) -> Iterator[None]:
    dispose_engine()
    with (
        override_settings(aeat_local_storage_root=tmp_path, aeat_output_language="en"),
        isolated_profile_storage_root(tmp_path=tmp_path),
    ):
        try:
            yield
        finally:
            dispose_engine()


def _create_defaulted_natural_person_profile(profile_name: str) -> None:
    created = invoke_cached_cli(
        [
            "config", "profile", "create", profile_name,
            "--quiet", "--accept-defaults",
            "--entity-type", "natural_person",
            "--tax-id", "12345678Z",
            "--name", "Lucia",
            "--surnames", "Navarro",
        ],
    )  # fmt: skip
    assert created.exit_code == 0, created.output


def test_profile_preflight_names_profile_only_scope_for_m100() -> None:
    created = invoke_cached_cli(
        [
            "config", "profile", "create", "operator",
            "--quiet", "--accept-defaults",
            "--entity-type", "natural_person",
            "--irpf-income-categories", "actividad_economica",
            "--tax-id", "12345678Z",
            "--name", "Daniel",
            "--surnames", "Ruiz Martin",
            "--activity", "software consulting",
            "--activity-start-date", "2025-01-01",
            "--tax-residence-ccaa", "madrid",
            "--taxation-type", "1",
            "--irpf-estimation-regime", "directa_simplificada",
            "--taxpayer-sex", "H",
            "--taxpayer-marital-status", "1",
            "--situacion-familiar", "soltero",
            "--taxpayer-birth-date", "1980-01-01",
        ],
    )  # fmt: skip
    assert created.exit_code == 0, created.output

    result = invoke_cached_cli(
        [
            "config", "profile", "preflight",
            "--modelo", "100",
            "--filing-year", "2025",
            "--period", "0A",
            "--revision-id", "2025",
        ],
    )  # fmt: skip

    assert result.exit_code == 0, result.output
    lines = result.output.splitlines()
    assert "profile_readiness\tready\tmissing=0" in result.output
    assert "readiness\tready\tmissing=0" not in lines
    assert "readiness_scope\tprofile_fields_only" in result.output
    assert (
        "full_modelo_readiness_command\t"
        "aeat app modelo readiness --modelo 100 --revision-id 2025 --year 2025 --period 0A"
    ) in result.output


@pytest.mark.parametrize(
    ("profile_name", "modelo", "filing_year", "period", "revision_id"),
    (
        ("lucia_defaults_broken", "303", "2024", "1T", "2023-y-siguientes"),
        ("marta_defaults_broken", "100", "2025", "0A", "2025"),
    ),
    ids=("m303-defaulted-profile", "m100-defaulted-profile"),
)
def test_defaulted_profile_readiness_surfaces_block_before_modelo_work(
    profile_name: str,
    modelo: str,
    filing_year: str,
    period: str,
    revision_id: str,
) -> None:
    _create_defaulted_natural_person_profile(profile_name)

    validate = invoke_cached_cli(["config", "profile", "validate", profile_name])
    assert validate.exit_code == 2, validate.output
    assert "readiness\tblocked" in validate.output
    assert "modelo_work_profile_baseline_missing\tactivities.description" in validate.output
    assert "readiness\tready" not in validate.output

    preflight = invoke_cached_cli(
        [
            "config", "profile", "preflight",
            "--modelo", modelo,
            "--filing-year", filing_year,
            "--period", period,
        ],
    )  # fmt: skip
    assert preflight.exit_code == 2, preflight.output
    assert "profile_readiness\tmissing\tmissing=1" in preflight.output
    assert "missing\tactivities\tdescription\tactivities.description" in preflight.output
    assert "profile_readiness\tready" not in preflight.output

    readiness = invoke_cached_cli(
        [
            "app", "modelo", "readiness",
            "--modelo", modelo,
            "--revision-id", revision_id,
            "--year", filing_year,
            "--period", period,
        ],
    )  # fmt: skip
    assert readiness.exit_code == 0, readiness.output
    assert "ready\tFalse" in readiness.output
    assert "profile_ready\tFalse" in readiness.output
    assert "activities.description\tactivities.description" in readiness.output

    work_create = invoke_cached_cli(
        [
            "app", "modelo", "work", "create",
            "--modelo", modelo,
            "--year", filing_year,
            "--period", period,
        ],
    )  # fmt: skip
    assert work_create.exit_code == 2, work_create.output
    assert "activities.description" in work_create.output
    assert "work_unit_id" not in work_create.output
