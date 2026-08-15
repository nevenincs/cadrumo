"""Small real-CLI helpers shared by profile CLI tests."""

from __future__ import annotations

from click.testing import Result

from ....tests.cli_runner import invoke_cached_cli
from ....tests.user_profile import register_cli_profile


def seed_profile(name: str, **facts: str) -> str:
    """Seed one profile through the credential registration door, and return its id.

    Use this wherever a test needs a profile to EXIST. ``create_quiet_profile``
    below still drives the CLI ``create`` verb, which refuses unconditionally;
    it survives only for the handful of tests whose subject is a refusal that
    fires ahead of that check.
    """
    return register_cli_profile(label=name, facts=facts)


def create_quiet_profile(name: str, *options: str) -> Result:
    return invoke_cached_cli(
        (
            "config",
            "profile",
            "create",
            name,
            "--quiet",
            "--accept-defaults",
            *_filing_identity_defaults(name, options),
            *options,
        ),
    )


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


def _filing_identity_defaults(name: str, options: tuple[str, ...]) -> tuple[str, ...]:
    option_set = set(options)
    defaults: list[str] = []
    if "--entity-type" not in option_set:
        defaults.extend(("--entity-type", "natural_person"))
    entity_type = _option_value(options, "--entity-type") or "natural_person"
    if entity_type == "legal_entity":
        if "--legal-name" not in option_set:
            defaults.extend(["--legal-name", f"{name} SL"])
        return tuple(defaults)
    if "--name" not in option_set:
        defaults.extend(["--name", name])
    if entity_type == "natural_person" and "--surnames" not in option_set:
        defaults.extend(["--surnames", "Test"])
    return tuple(defaults)


def _option_value(options: tuple[str, ...], flag: str) -> str | None:
    try:
        index = options.index(flag)
    except ValueError:
        return None
    value_index = index + 1
    if value_index >= len(options):
        return None
    value = options[value_index]
    return None if value.startswith("--") else value
