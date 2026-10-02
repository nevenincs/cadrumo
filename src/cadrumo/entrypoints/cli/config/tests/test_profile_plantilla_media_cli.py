"""Real CLI coverage for the year-keyed average-workforce subject."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.tests.profile_registration import register_cli_profile

from .....adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from .....adapters.persistence.storage.tests.profile_storage_root_fixture import profile_storage_root_fixture
from .....core.config import load_settings
from .....tests.cli_envelope import unwrap_schema_envelope
from ...tests.cli_runner import invoke_cached_cli
from .isolated_storage_fixture import native_profile_view_server

__all__ = ["profile_storage_root_fixture"]

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.serial,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile runtime"),
]


def _run(name: str, *argv: str) -> tuple[int, str]:
    secret = load_settings().cadrumo_dev_test_database_password.get_secret_value()
    result = invoke_cached_cli(
        (
            "--format",
            "json",
            "--profile",
            name,
            "--profile-secrets-stdin",
            "config",
            "profile",
            "plantilla-media",
            *argv,
        ),
        input=json.dumps({"profile_passphrase": secret}),
    )
    return result.exit_code, result.output


def _years(output: str) -> list[tuple[int, str, str]]:
    payload = unwrap_schema_envelope(output)
    years = payload["years"]
    assert isinstance(years, list)
    return [(item["year"], str(item["average_workforce"]), item["state"]) for item in years]


def test_years_are_set_replaced_listed_and_withdrawn(profile_storage_root: Path) -> None:
    register_cli_profile(
        label="plantilla-media-operator",
        facts={
            "identity.tax_id": "12345678Z",
            "taxpayer_type.entity_type": "natural_person",
            "identity.name": "Plantilla",
            "identity.surnames": "Media",
        },
        log_in=False,
    )
    close_active_bucket_session()

    with native_profile_view_server(profile_storage_root):
        first = _run(
            "plantilla-media-operator", "set", "--year", "2025", "--average-workforce", "12.50", "--state", "committed"
        )
        second = _run(
            "plantilla-media-operator", "set", "--year", "2024", "--average-workforce", "10", "--state", "observed"
        )
        replaced = _run(
            "plantilla-media-operator", "set", "--year", "2025", "--average-workforce", "11.75", "--state", "observed"
        )
        listed = _run("plantilla-media-operator", "list")
        removed = _run("plantilla-media-operator", "remove", "2024")

    assert first[0] == 0, first[1]
    assert second[0] == 0, second[1]
    assert replaced[0] == 0, replaced[1]
    assert _years(replaced[1]) == [(2024, "10", "observed"), (2025, "11.75", "observed")]
    assert listed[0] == 0, listed[1]
    assert _years(listed[1]) == _years(replaced[1])
    assert removed[0] == 0, removed[1]
    assert _years(removed[1]) == [(2025, "11.75", "observed")]


def test_an_undeclared_year_and_a_non_number_refuse_without_writing(profile_storage_root: Path) -> None:
    register_cli_profile(
        label="plantilla-media-refusals",
        facts={
            "identity.tax_id": "12345678Z",
            "taxpayer_type.entity_type": "natural_person",
            "identity.name": "Plantilla",
            "identity.surnames": "Refusal",
        },
        log_in=False,
    )
    close_active_bucket_session()

    with native_profile_view_server(profile_storage_root):
        undeclared = _run("plantilla-media-refusals", "remove", "2030")
        not_a_number = _run(
            "plantilla-media-refusals", "set", "--year", "2025", "--average-workforce", "doce", "--state", "observed"
        )
        extra_places = _run(
            "plantilla-media-refusals", "set", "--year", "2025", "--average-workforce", "12.505", "--state", "observed"
        )
        listed = _run("plantilla-media-refusals", "list")

    assert undeclared[0] != 0
    assert not_a_number[0] != 0
    assert extra_places[0] != 0
    assert listed[0] == 0, listed[1]
    assert _years(listed[1]) == []
