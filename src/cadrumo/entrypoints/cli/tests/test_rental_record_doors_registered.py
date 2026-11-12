"""The property, lease and position verbs are registered, reachable and worded in every locale."""

from __future__ import annotations

import pytest

from ....core.config import override_settings
from .cli_runner import invoke_cached_cli

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_VERBS = {
    "inmueble": ("add", "edit", "list", "remove"),
    "arrendamiento": ("add", "edit", "end", "list", "remove"),
    "posicion": ("add", "edit", "list", "remove"),
}
_LOCALES = ("en", "es", "ca", "hu")


@pytest.mark.parametrize("family", sorted(_VERBS))
def test_each_family_lists_exactly_its_verbs(family: str) -> None:
    result = invoke_cached_cli(["config", "profile", family, "--help"])

    assert result.exit_code == 0, result.output
    for verb in _VERBS[family]:
        assert verb in result.output


@pytest.mark.parametrize(("family", "verb"), [(family, verb) for family, verbs in _VERBS.items() for verb in verbs])
def test_each_verb_has_help_in_every_locale(family: str, verb: str) -> None:
    for locale in _LOCALES:
        with override_settings(cadrumo_output_language=locale):
            result = invoke_cached_cli(["config", "profile", family, verb, "--help"])
        assert result.exit_code == 0, (locale, result.output)
        assert "cli.config.profile" not in result.output, (locale, result.output)


@pytest.mark.parametrize("family", ["inmueble", "posicion"])
def test_the_edit_verbs_take_values_and_clears(family: str) -> None:
    edit = invoke_cached_cli(["config", "profile", family, "edit", "--help"])

    assert "--value" in edit.output
    assert "--clear" in edit.output


def test_end_takes_a_date() -> None:
    end = invoke_cached_cli(["config", "profile", "arrendamiento", "end", "--help"])

    assert "FECHA" in end.output.upper()
