"""The declared operational settings validate and project without independent defaults."""

from __future__ import annotations

import json
import os
import re
import sys
import tomllib
from pathlib import Path

import pytest

from dev._paths import REPO_ROOT

from ...command_execution import run_command
from ..application_environment import parse
from ..environment_declaration_primitives import DECLARATION, ApplicationEnvironmentError
from ..generate import generate
from ..operational_settings import defaults, parse_settings, rust_settings

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _entry() -> dict[str, object]:
    return {
        "default": 100,
        "minimum": 0,
        "maximum": 1000,
        "unit": "milliseconds",
        "description": "Delay before retrying a presentation update.",
    }


def test_settings_accept_range_endpoints_and_project_typed_defaults() -> None:
    settings = parse_settings(
        {
            "first_delay_ms": _entry(),
            "largest_count": {
                "default": 2_147_483_647,
                "minimum": 2_147_483_647,
                "maximum": 2_147_483_647,
                "unit": "count",
                "description": "Largest permitted value.",
            },
            "empty_bytes": {
                "default": 0,
                "minimum": 0,
                "maximum": 0,
                "unit": "bytes",
                "description": "A permitted zero.",
            },
        }
    )
    assert defaults(settings) == {"first_delay_ms": 100, "largest_count": 2_147_483_647, "empty_bytes": 0}
    rust = "\n".join(rust_settings(settings))
    assert "pub const SETTING_FIRST_DELAY_MS: u64 = 100;" in rust
    assert "pub const SETTING_LARGEST_COUNT: u64 = 2147483647;" in rust
    assert "pub const SETTING_EMPTY_BYTES: u64 = 0;" in rust


@pytest.mark.parametrize("name", ["", "UpperCase", "two__parts", "_private", "1first", "has-dash", "trailing_"])
def test_invalid_setting_names_are_refused(name: str) -> None:
    with pytest.raises(ApplicationEnvironmentError):
        parse_settings({name: _entry()})


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("default", True),
        ("minimum", False),
        ("maximum", True),
        ("default", -1),
        ("minimum", -1),
        ("maximum", 2_147_483_648),
        ("default", 1010),
        ("minimum", 101),
        ("maximum", 99),
        ("default", 1.5),
        ("unit", "seconds"),
        ("unit", ""),
        ("description", ""),
    ],
)
def test_invalid_values_and_ranges_are_refused(field: str, value: object) -> None:
    entry = _entry()
    entry[field] = value
    with pytest.raises(ApplicationEnvironmentError):
        parse_settings({"retry_delay": entry})


@pytest.mark.parametrize("missing", ["default", "minimum", "maximum", "unit", "description"])
def test_every_field_is_required(missing: str) -> None:
    entry = _entry()
    del entry[missing]
    with pytest.raises(ApplicationEnvironmentError):
        parse_settings({"retry_delay": entry})


def test_unknown_field_and_non_tables_are_refused() -> None:
    entry = {**_entry(), "unexpected": 1}
    for value in ({"retry_delay": entry}, {"retry_delay": []}, []):
        with pytest.raises(ApplicationEnvironmentError):
            parse_settings(value)


def test_application_environment_rejects_malformed_settings() -> None:
    source = (REPO_ROOT / DECLARATION).read_text(encoding="utf-8")
    invalid = (
        "\n[settings.invalid__name]\n"
        'default = 1\nminimum = 0\nmaximum = 2\nunit = "count"\ndescription = "invalid name"\n'
    )
    with pytest.raises(ApplicationEnvironmentError):
        parse(source + invalid)


def test_authored_declaration_and_generated_contract_agree(tmp_path: Path) -> None:
    source = (REPO_ROOT / DECLARATION).read_text(encoding="utf-8")
    authored = tomllib.loads(source)["settings"]
    declaration = parse(source)
    assert declaration.settings == authored
    expected = {name: item["default"] for name, item in authored.items()}
    assert expected
    assert defaults(declaration.settings) == expected

    generate(REPO_ROOT, tmp_path, target="windows-x86-64")
    contract = json.loads((tmp_path / "contract.json").read_text(encoding="utf-8"))
    assert contract["settings"] == expected
    rust = (tmp_path / "contract.rs").read_text(encoding="utf-8")
    projected = {
        name.casefold(): int(value)
        for name, value in re.findall(r"^pub const SETTING_([A-Z0-9_]+): u64 = (\d+);$", rust, re.MULTILINE)
    }
    assert projected == expected

    typescript = (tmp_path / "operational-settings.ts").read_text(encoding="utf-8")
    match = re.fullmatch(
        r"// Generated from native/application-environment\.toml\.\nexport default (\{.*\}) as const;\n",
        typescript,
        re.DOTALL,
    )
    assert match is not None
    assert json.loads(match.group(1)) == expected


def test_desktop_generator_cli_needs_no_publisher_provisioning(tmp_path: Path) -> None:
    source = (REPO_ROOT / DECLARATION).read_text(encoding="utf-8")
    expected = {name: item["default"] for name, item in tomllib.loads(source)["settings"].items()}
    output = tmp_path / "desktop" / "operational-settings.ts"
    environment = {key: value for key, value in os.environ.items() if key.upper() != "CADRUMO_GOOGLE_OAUTH_CLIENT_JSON"}
    result = run_command(
        [sys.executable, "-m", "dev.packaging.native.desktop_settings", "--output", str(output)],
        cwd=REPO_ROOT,
        environment=environment,
        errors="replace",
        timeout_seconds=60,
    )
    assert result.returncode == 0, result.stderr
    match = re.fullmatch(
        r"// Generated from native/application-environment\.toml\.\nexport default (\{.*\}) as const;\n",
        output.read_text(encoding="utf-8"),
        re.DOTALL,
    )
    assert match is not None
    assert json.loads(match.group(1)) == expected
