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
