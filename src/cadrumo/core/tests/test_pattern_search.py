"""A person's pattern is searched in a child that is ended on overrun, with the meaning ``re`` gives it."""

from __future__ import annotations

import ast
import re
import threading
import time
from pathlib import Path
from typing import Final

import pytest

from .. import pattern_search_worker
from ..pattern_search import (
    PATTERN_SEARCH_BASE_SECONDS,
    PATTERN_SEARCH_MAX_SECONDS,
    PatternSearchOverrunError,
    PatternSearchUnreadableError,
    first_matching_patterns,
    pattern_search_budget_seconds,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_CATASTROPHIC: Final = r"(a+)+$"
_BACKTRACKING_TEXT: Final = "a" * 27 + "!"


def _in_process(patterns: list[str], texts: list[str]) -> tuple[int | None, ...]:
    """The row-by-row first match the child replaced, computed with nothing shared with it."""
    return tuple(
        next((at for at, pattern in enumerate(patterns) if re.search(pattern, text, re.IGNORECASE)), None)
        for text in texts
    )


_TEXTS: Final = [
    "RECIBO TELEFONIA ALBOR MOVIL",
    "fibra albor",
    "",
    "  espacios  ",
    "línea\nsegunda",
    "AÑO ÑANDÚ ß STRASSE",
    chr(0x017F) + " long s " + chr(0x212A),
    chr(0x0130) + "stanbul " + chr(0x0131),
    "emoji \U0001f600 fin",
    "lone \ud83d surrogate",
    "nul\x00byte",
    "a.b",
    "axb",
    "x albor",
    "albor",
    "123,45 EUR 2024-04-10",
    "[corchete] (paréntesis) {llave}",
    "tab\tseparado\r\n",
]

_PATTERNS: Final = [
    "albor",
    "ALBOR",
    r"^albor$",
    r"\Aalbor\Z",
    r"a\.b",
    "a.b",
    "(?i)ALBOR",
    "(?-i:ALBOR)",
    "(?s)línea.segunda",
    "(?m)^segunda$",
    "(?a)\\w+ fin",
    r"(?P<who>albor)",
    r"(?P<q>a)(?P=q)?",
    r"(?<!x )albor",
    r"\d{3},\d{2}",
    r"^\s*$",
    r"",
    "ñandú",
    "ÑANDÚ",
    "strasse",
    "ß",
    "k",
    "s",
    chr(0x0130) + "stanbul",
    r"\x00",
    "\ud83d",
    "\U0001f600",
    r"\[corchete\]",
    r"\bfin\b",
    r"tab\s+",
    r"tab\tseparado$",
    r"(a|b)+x?",
    r"(?:recibo|fibra)\s+\w+",
]


@pytest.mark.parametrize("pattern", _PATTERNS)
def test_one_pattern_means_what_re_says_on_every_text(pattern: str) -> None:
    assert first_matching_patterns([pattern], _TEXTS) == _in_process([pattern], _TEXTS)


def test_a_batch_answers_the_first_pattern_each_text_meets_as_row_by_row_matching_does() -> None:
    assert first_matching_patterns(_PATTERNS, _TEXTS) == _in_process(_PATTERNS, _TEXTS)
    reordered = list(reversed(_PATTERNS))
    assert first_matching_patterns(reordered, _TEXTS) == _in_process(reordered, _TEXTS)


def test_nothing_to_search_starts_nothing_and_finds_nothing() -> None:
    assert first_matching_patterns([], ["a", "b"]) == (None, None)
    assert first_matching_patterns([_CATASTROPHIC], []) == ()


def test_an_overrun_is_ended_within_its_budget_while_this_process_keeps_running() -> None:
    gaps: list[float] = []
    stop = threading.Event()

    def beat() -> None:
        last = time.monotonic()
        while not stop.wait(0.01):
            moment = time.monotonic()
            gaps.append(moment - last)
            last = moment

    beating = threading.Thread(target=beat, daemon=True)
    beating.start()
    started = time.monotonic()
    with pytest.raises(PatternSearchOverrunError) as overrun:
        first_matching_patterns(["fine", _CATASTROPHIC], ["no", _BACKTRACKING_TEXT])
    elapsed = time.monotonic() - started
    stop.set()
    beating.join()
    assert overrun.value.pattern_index == 1
    assert PATTERN_SEARCH_BASE_SECONDS <= elapsed < PATTERN_SEARCH_BASE_SECONDS + 3
    assert max(gaps) < 1.0


def test_an_overrun_past_a_text_an_earlier_pattern_took_is_not_run() -> None:
    assert first_matching_patterns(["a", _CATASTROPHIC], [_BACKTRACKING_TEXT]) == (0,)


@pytest.mark.parametrize("pattern", ["[unclosed", "a{99999999999}", "(" * 2000 + ")" * 2000, "(?L)a"])
def test_what_re_cannot_read_is_named(pattern: str) -> None:
    with pytest.raises(PatternSearchUnreadableError) as unreadable:
        first_matching_patterns(["fine", pattern], ["no"])
    assert unreadable.value.pattern_index == 1


def test_a_large_batch_gets_more_time_up_to_a_ceiling() -> None:
    one = pattern_search_budget_seconds(patterns=1, texts=1)
    large = pattern_search_budget_seconds(patterns=1, texts=50_000)
    assert PATTERN_SEARCH_BASE_SECONDS < one < large < PATTERN_SEARCH_MAX_SECONDS
    assert pattern_search_budget_seconds(patterns=1_000, texts=50_000) == PATTERN_SEARCH_MAX_SECONDS


def test_the_child_starts_on_the_standard_library_alone() -> None:
    tree = ast.parse(Path(pattern_search_worker.__file__).read_text(encoding="utf-8"))
    imported = {
        name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import | ast.ImportFrom)
        for name in ([alias.name for alias in node.names] if isinstance(node, ast.Import) else [node.module])
    }
    assert imported == {"__future__", "json", "re", "sys", "typing"}
