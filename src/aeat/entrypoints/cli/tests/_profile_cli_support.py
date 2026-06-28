"""Small real-CLI helpers shared by profile CLI tests."""

from __future__ import annotations

from click.testing import Result

from ....tests.cli_runner import invoke_cached_cli


def create_quiet_profile(name: str, *options: str) -> Result:
    return invoke_cached_cli(("config", "profile", "create", name, "--quiet", "--accept-defaults", *options))


def edit_quiet_profile(name: str, *options: str) -> Result:
    return invoke_cached_cli(("config", "profile", "edit", name, "--quiet", *options))


def profile_rows(name: str) -> dict[str, str]:
    result = invoke_cached_cli(("config", "profile", "show", name))
    assert result.exit_code == 0, result.output
    rows: dict[str, str] = {}
    for line in result.output.splitlines():
        if "\t" not in line:
            continue
        key, _, value = line.partition("\t")
        rows[key.strip()] = value.strip()
    return rows
