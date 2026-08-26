"""Real CLI coverage for registered domestic-partnership marital status."""

from __future__ import annotations

import json
import re

import pytest

from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_cli_backend as _isolated_cli_backend  # noqa: F401 - autouse fixture
from ....tests.user_profile import register_cli_profile

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _json_output(output: str) -> str:
    match = re.search(r"(\{.*\}|\[.*\])", output, re.DOTALL)
    assert match is not None, output
    return match.group(0)


def test_profile_create_show_round_trips_pareja_de_hecho_marital_status() -> None:
    register_cli_profile(
        label="andrea",
        facts={
            "taxpayer_type.entity_type": "natural_person",
            "identity.tax_id": "12345678Z",
            "identity.name": "Andrea",
            "identity.surnames": "High",
            "renta_taxpayer.marital_status": "5",
        },
    )

    shown = invoke_cached_cli(["--format", "json", "config", "profile", "view"])
    assert shown.exit_code == 0, shown.output
    envelope = json.loads(_json_output(shown.output))
    facts = {row["path"]: row["value"] for row in envelope["result"]["facts"]}

    assert facts["renta_taxpayer.marital_status"] == "5"


def test_profile_create_help_advertises_pareja_de_hecho_marital_status() -> None:
    result = invoke_cached_cli(["--language", "en", "config", "profile", "create", "--help"])

    assert result.exit_code == 0, result.output
    compact_help = re.sub(r"\s+", "", result.output)
    assert "1|2|3|4|5" in compact_help
