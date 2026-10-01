"""The panel's "Affects" answer says how far a change reaches, and never says nothing reaches where it does not know.

Pure composition over help cards: an unread card says nothing at all; a box
on the way to the result names the chain to it, with the count of other boxes
the change also reaches; a box no calculation leads from to the result says
it does not change the result; the result box says it is the result; and a
form that names no result lists the boxes a box is used in, as before.
"""

from __future__ import annotations

import pytest

from ......application.modelo.casilla_help import ModeloCasillaHelpCardV1, ModeloHelpBoxV1, ModeloHelpReachV1
from ......core.casilla_id import validated_casilla_id
from ......core.config import override_settings
from ......core.external_constants import OutputLanguage
from ......core.i18n.render import tr
from ..editor import affects_text

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_LANGUAGES = tuple(OutputLanguage)


def _box(number: str) -> ModeloHelpBoxV1:
    return ModeloHelpBoxV1(casilla_id=validated_casilla_id(number, surface="test"), box=f"[{number}]")


def _card(
    *, feeds: tuple[str, ...] = (), reach: ModeloHelpReachV1 | None = None, is_result: bool = False
) -> ModeloCasillaHelpCardV1:
    return ModeloCasillaHelpCardV1(
        casilla_id=validated_casilla_id("05", surface="test"),
        formula=None,
        quotes=(),
        legal_basis=(),
        constraints=(),
        origins=(),
        feeds=feeds,
        reach=reach,
        is_result=is_result,
    )


def test_an_unread_card_says_nothing_rather_than_that_nothing_is_affected() -> None:
    assert affects_text(None) is None


@pytest.mark.parametrize("language", _LANGUAGES, ids=lambda language: language.value)
def test_a_box_on_the_way_names_the_chain_and_counts_the_rest(language: OutputLanguage) -> None:
    card = _card(feeds=("[07]",), reach=ModeloHelpReachV1(path=(_box("07"), _box("12"), _box("19")), others=2))

    with override_settings(cadrumo_output_language=language.value):
        text = affects_text(card)
        others = tr("tui.modelo.workbench.editor.affects.others", count=2)

    assert text == f"[07] → [12] → [19]\n{others}"


def test_no_count_follows_a_chain_that_reaches_nothing_else() -> None:
    card = _card(feeds=("[19]",), reach=ModeloHelpReachV1(path=(_box("19"),), others=0))

    assert affects_text(card) == "[19]"


@pytest.mark.parametrize("language", _LANGUAGES, ids=lambda language: language.value)
def test_a_box_that_does_not_reach_the_result_says_so_with_where_it_is_used(language: OutputLanguage) -> None:
    alone = _card(reach=ModeloHelpReachV1(path=(), others=0))
    used = _card(feeds=("[45]",), reach=ModeloHelpReachV1(path=(), others=1))

    with override_settings(cadrumo_output_language=language.value):
        said_alone = affects_text(alone)
        said_used = affects_text(used)
        not_result = tr("tui.modelo.workbench.editor.affects.not_result")
        used_in = tr("tui.modelo.workbench.help.feeds", boxes="[45]")

    assert said_alone == not_result
    assert said_used == f"{not_result}\n{used_in}"


def test_the_result_box_says_it_is_the_result() -> None:
    with override_settings(cadrumo_output_language="en"):
        assert affects_text(_card(is_result=True)) == tr("tui.modelo.workbench.editor.affects.is_result")


def test_a_form_without_a_result_lists_the_boxes_a_box_is_used_in() -> None:
    assert affects_text(_card(feeds=("[03]", "[04]"))) == "[03], [04]"
    assert affects_text(_card()) is None
