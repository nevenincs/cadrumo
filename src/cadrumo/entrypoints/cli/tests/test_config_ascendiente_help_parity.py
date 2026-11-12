"""Every key the ``--ascendiente`` help advertises is one the grammar honours, in every locale."""

from __future__ import annotations

import re

import pytest
import typer
from typer.core import TyperGroup

from ....core.i18n.render import tr
from ..config.ascendiente_flag import parse_ascendiente_flag
from .cli_runner import cadrumo_click_command

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_HELP_KEY = "cli.config.profile.ascendiente.add_flag_help"
_LOCALES = ("en", "es", "ca", "hu")
_TOKEN_RE = re.compile(r"([A-Za-zÀ-ÿ_]+)=")
_BASELINE = "NACIMIENTO=1948-03-04"
#: One probe value per key; the parsed leaves differ from the baseline only when the key was honoured.
_PROBES = {
    "NACIMIENTO": "NACIMIENTO=1950-01-01",
    "NIF": "NIF=12345678Z",
    "APELLIDOS_NOMBRE": "APELLIDOS_NOMBRE=Roca Carmen",
    "FALLECIMIENTO": "FALLECIMIENTO=2025-02-01",
    "CONVIVIENTES": "CONVIVIENTES=2",
    "RENTAS": "RENTAS=7200.00",
    "DECLARACION_PROPIA": "DECLARACION_PROPIA=false",
    "DISCAPACIDAD": "DISCAPACIDAD=33",
}


def _leaves(raw: str) -> dict[str, str]:
    return {fact.field_key: fact.value for fact in parse_ascendiente_flag(raw).facts}


def _group_at(*path: str) -> TyperGroup:
    group = cadrumo_click_command()
    for name in path:
        assert isinstance(group, TyperGroup)
        group = group.get_command(typer.Context(group), name)
        assert group is not None, f"live command tree has no {name!r} group"
    assert isinstance(group, TyperGroup)
    return group


@pytest.mark.parametrize("locale", _LOCALES)
def test_the_help_advertises_exactly_the_keys_the_grammar_honours(locale: str) -> None:
    advertised = set(_TOKEN_RE.findall(tr(_HELP_KEY, locale=locale)))
    assert advertised == set(_PROBES), f"{locale}: help advertises {sorted(advertised)}"
    baseline = _leaves(_BASELINE)
    for key, fragment in _PROBES.items():
        probed = _leaves(fragment if key == "NACIMIENTO" else f"{_BASELINE},{fragment}")
        assert probed != baseline, f"{locale}: {key} was ignored"


def test_the_rendered_commands_expose_the_flag_and_the_none_form() -> None:
    group = _group_at("config", "profile", "ascendiente")
    assert sorted(group.list_commands(typer.Context(group))) == ["add", "edit", "list", "remove"]
    add = group.get_command(typer.Context(group), "add")
    assert add is not None
    options = {param.name: param for param in add.params}
    assert {"ascendiente", "none"} <= set(options)
    assert not options["ascendiente"].required
    assert set(_TOKEN_RE.findall(getattr(options["ascendiente"], "help", None) or "")) == set(_PROBES)


@pytest.mark.parametrize("locale", _LOCALES)
def test_the_edit_help_names_every_key_the_grammar_honours(locale: str) -> None:
    named = set(
        re.findall(r"\b[A-Z][A-Z_]+[A-Z]\b", tr("cli.config.profile.ascendiente.edit_flag_help", locale=locale))
    )
    assert set(_PROBES) <= named, f"{locale}: edit help omits {sorted(set(_PROBES) - named)}"


def test_the_rendered_edit_takes_the_row_index_the_replacements_and_the_clears() -> None:
    group = _group_at("config", "profile", "ascendiente")
    edit = group.get_command(typer.Context(group), "edit")
    assert edit is not None
    params = {param.name: param for param in edit.params}
    assert {"index", "ascendiente", "clear"} <= set(params)
    assert params["index"].required
    assert params["ascendiente"].multiple and params["clear"].multiple


def test_the_descendant_add_offers_the_same_none_form_and_no_longer_requires_a_row() -> None:
    group = _group_at("config", "profile", "descendiente")
    add = group.get_command(typer.Context(group), "add")
    assert add is not None
    options = {param.name: param for param in add.params}
    assert {"descendiente", "none"} <= set(options)
    assert not options["descendiente"].required
