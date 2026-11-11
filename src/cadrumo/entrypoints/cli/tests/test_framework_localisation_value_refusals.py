"""A value Typer's Pydantic conversion refuses is worded in the selected locale, never in Pydantic's English."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

import pytest
import typer
from typer._click.exceptions import BadParameter

from ....core.cli_value_parsers import CliChoice
from ....core.config import override_settings
from ..framework_localisation import localised_bad_parameter_message

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_LOCALES = ("es", "en", "ca", "hu")


def _plain_value_error_parser(value: object) -> str:
    if value not in ("es", "en"):
        raise ValueError(f"{value!r} is not one of 'es', 'en'.")
    return str(value)


def _command() -> typer.main.TyperCommand:
    app = typer.Typer()

    @app.command()
    def create(
        year: Annotated[int, typer.Option("--year")] = 0,
        share: Annotated[float, typer.Option("--share")] = 0.0,
        work: Annotated[UUID | None, typer.Option("--work")] = None,
        period: Annotated[str, typer.Option("--period", parser=CliChoice.of(("1T", "2T")))] = "1T",
        language: Annotated[str, typer.Option("--language", parser=_plain_value_error_parser)] = "es",
    ) -> None:
        del year, share, work, period, language

    command = typer.main.get_command(app)
    assert isinstance(command, typer.main.TyperCommand)
    return command


def _refusal(language: str, *arguments: str) -> str:
    with pytest.raises(BadParameter) as refused:
        _command().main(list(arguments), standalone_mode=False)
    with override_settings(cadrumo_output_language=language):
        return localised_bad_parameter_message(refused.value, BadParameter.format_message)


@pytest.mark.parametrize(
    ("language", "expected"),
    [
        ("es", "Valor no válido para '--year': 'abc' no es un entero válido."),
        ("en", "Invalid value for '--year': 'abc' is not a valid integer."),
        ("ca", "Valor no vàlid per a '--year': 'abc' no és un enter vàlid."),
        ("hu", "Érvénytelen érték ehhez: '--year': 'abc' nem érvényes egész szám."),
    ],
)
def test_an_integer_the_parser_refuses_is_worded_in_the_locale(language: str, expected: str) -> None:
    assert _refusal(language, "--year", "abc") == expected


@pytest.mark.parametrize(
    ("language", "expected"),
    [
        ("es", "Valor no válido para '--share': 'half' no es un número válido."),
        ("en", "Invalid value for '--share': 'half' is not a valid number."),
        ("ca", "Valor no vàlid per a '--share': 'half' no és un nombre vàlid."),
        ("hu", "Érvénytelen érték ehhez: '--share': 'half' nem érvényes szám."),
    ],
)
def test_a_number_the_parser_refuses_is_worded_in_the_locale(language: str, expected: str) -> None:
    assert _refusal(language, "--share", "half") == expected


@pytest.mark.parametrize(
    ("language", "expected"),
    [
        ("es", "Valor no válido para '--work': 'w1' no es un valor aceptado."),
        ("en", "Invalid value for '--work': 'w1' is not an accepted value."),
        ("ca", "Valor no vàlid per a '--work': 'w1' no és un valor acceptat."),
        ("hu", "Érvénytelen érték ehhez: '--work': 'w1' nem elfogadott érték."),
    ],
)
def test_any_other_conversion_the_parser_refuses_is_worded_in_the_locale(language: str, expected: str) -> None:
    assert _refusal(language, "--work", "w1") == expected


@pytest.mark.parametrize("language", _LOCALES)
def test_no_pydantic_sentence_reaches_the_operator(language: str) -> None:
    for arguments in (("--year", "abc"), ("--year", "1.5"), ("--share", "half"), ("--work", "w1")):
        refusal = _refusal(language, *arguments)
        assert "Input should be" not in refusal, refusal
        assert "unable to parse" not in refusal, refusal


def test_a_declared_parser_keeps_its_own_sentence() -> None:
    refusal = _refusal("en", "--period", "5T")

    assert refusal == "Invalid value for '--period': '5T' is not one of '1T', '2T'."


def test_a_declared_parser_value_error_keeps_its_own_sentence_without_the_pydantic_prefix() -> None:
    refusal = _refusal("en", "--language", "xx")

    assert refusal == "Invalid value for '--language': 'xx' is not one of 'es', 'en'."
