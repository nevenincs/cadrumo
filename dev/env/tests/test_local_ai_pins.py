"""Gate: the committed local AI program pins are well formed, declared and exactly what the tool renders.

Nothing here downloads. The defect cases change a copy of the committed table
and must each be reported or refused.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ..local_ai_pins import PINS_PATH, PLATFORM_ASSETS, ProgramPins, check_pins, load_program_pins, render_pins

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.fixture(scope="module")
def committed() -> ProgramPins:
    return load_program_pins()


def test_the_committed_table_pins_every_platform_from_declared_hosts(committed: ProgramPins) -> None:
    assert check_pins(committed, PINS_PATH.read_text(encoding="utf-8")) == []
    assert {pin.platform for pin in committed.archives} == set(PLATFORM_ASSETS)


def test_the_committed_table_is_exactly_what_the_generator_renders(committed: ProgramPins) -> None:
    assert PINS_PATH.read_text(encoding="utf-8") == render_pins(committed)


def test_a_missing_platform_is_reported(committed: ProgramPins) -> None:
    pins = committed.model_copy(update={"archives": committed.archives[1:]})

    assert any("no archive is pinned" in problem for problem in check_pins(pins, render_pins(pins)))


def test_an_undeclared_host_is_reported(committed: ProgramPins) -> None:
    pins = committed.model_copy(update={"hosts": tuple(sorted((*committed.hosts, "mirror.example")))})

    assert any("undeclared hosts" in problem for problem in check_pins(pins, render_pins(pins)))


def test_another_asset_or_executable_is_reported(committed: ProgramPins) -> None:
    first = committed.archives[0]
    moved = first.model_copy(update={"executable": "ollama"})
    pins = committed.model_copy(update={"archives": (moved, *committed.archives[1:])})

    assert any("another asset" in problem for problem in check_pins(pins, render_pins(pins)))


def test_a_hand_edited_table_is_reported(committed: ProgramPins) -> None:
    rendered = render_pins(committed).replace("program = ", "program  = ")

    assert any("not what the generator renders" in problem for problem in check_pins(committed, rendered))


@pytest.mark.parametrize(
    ("old", "new"),
    (
        (
            '"https://github.com/ollama/ollama/releases/download/v',
            '"https://mirror.example/ollama/ollama/releases/download/v',
        ),
        ("releases/download/v0.40.10/", "releases/download/v0.39.0/"),
        ('sha256 = "', 'sha256 = "AB'),
        ('format = "zip"', 'format = "rar"'),
        ('executable = "ollama.exe"', 'executable = "../ollama.exe"'),
        ('  "github.com",\n', '  "github.com",\n  "github.com",\n'),
    ),
)
def test_a_table_that_could_admit_other_bytes_or_sources_is_refused(old: str, new: str) -> None:
    text = PINS_PATH.read_text(encoding="utf-8")
    assert old in text

    with pytest.raises(ValidationError):
        load_program_pins(text.replace(old, new, 1))
