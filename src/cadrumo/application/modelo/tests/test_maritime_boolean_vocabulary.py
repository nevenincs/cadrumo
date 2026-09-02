"""The maritime reader must understand the words a Spanish operator writes.

These three facts -- ``tuna_fleet``, ``pending_eu_clearance`` and
``retmar_registered`` -- gate exemption pathways, and the reader that
interprets them used to accept ``true``, ``1`` and ``yes`` and nothing else.
Everything it did not recognise became ``False``, silently.

That is a bad failure in any language and a worse one here. The application is
a Spanish tax tool whose operators are Spanish taxpayers, and the filing layer
one package over has always accepted ``si`` -- so the codebase already knew
operators write it. A taxpayer answering ``si`` to "is this a tuna-fleet
vessel" was recorded as having said no, with nothing raised at either the write
or the read.

The reader now shares the one canonical vocabulary in
:func:`cadrumo.core.parsing.parse_bool` rather than carrying its own, so a word
it accepts cannot drift from a word the filing layer accepts.
"""

from __future__ import annotations

import pytest

from ..maritime_preview import _bool_from_raw

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

#: Spanish affirmatives. ``si`` is the damning case -- ordinary Spanish, already
#: accepted one layer over -- and the rest are the spellings that sit beside it.
_SPANISH_YES: tuple[str, ...] = ("si", "sí", "s", "verdadero", "SI", "Sí", "VERDADERO")

_SPANISH_NO: tuple[str, ...] = ("no", "n", "falso", "NO", "FALSO")

_ENGLISH_YES: tuple[str, ...] = ("true", "1", "yes", "y", "TRUE", "Yes")


@pytest.mark.parametrize("token", _SPANISH_YES)
def test_a_spanish_yes_is_read_as_yes(token: str) -> None:
    """Parameterised per word so a failure names the spelling that broke."""
    assert _bool_from_raw(token) is True, (
        f"{token!r} means yes to a Spanish operator and was read as False on a fact that gates an exemption pathway"
    )


@pytest.mark.parametrize("token", _SPANISH_NO)
def test_a_spanish_no_is_read_as_no(token: str) -> None:
    """The negative half. A right answer for the wrong reason is still fragile."""
    assert _bool_from_raw(token) is False


@pytest.mark.parametrize("token", _ENGLISH_YES)
def test_the_english_forms_keep_working(token: str) -> None:
    """Widening the vocabulary must not drop what already worked."""
    assert _bool_from_raw(token) is True


def test_an_absent_fact_is_false_rather_than_an_error() -> None:
    """Absence is a legitimate state here and must stay non-raising.

    Every one of these fields is optional, and
    :class:`~cadrumo.domain.renta.MaritimeWorkerFacts` defaults each to
    ``False`` precisely so a partial profile resolves. Refusing an absent
    fact would turn "the taxpayer has not answered" into a crash.
    """
    assert _bool_from_raw(None) is False
    assert _bool_from_raw("") is False


def test_an_uninterpretable_word_does_not_become_a_yes() -> None:
    """Anti-tautology: a reader returning True for everything passes the cases above.

    The reader still defaults an unreadable word to ``False`` -- the write door
    is where such a word is refused, because that is where the operator can
    still fix it. What must never happen is the opposite: a word nobody can
    read silently claiming the taxpayer said yes to an exemption.
    """
    assert _bool_from_raw("banana") is False
    assert _bool_from_raw("quizás") is False
