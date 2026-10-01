"""A casilla's help card spells out its formula, official text and law from the registry.

Expectations are written from the official modelo 130 form (box 04 is twenty
per cent of box 03, never below zero) and from the legal identifiers' own
spelling, not read back from the renderer.
"""

from __future__ import annotations

import re
from datetime import date

import pytest

from ....core.external_constants import OutputLanguage
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ..casilla_help import ModeloCasillaHelpCardV1, build_casilla_help_card, legal_citation_text

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_ON = date(2026, 3, 31)


def _card(operation: PinnedAuthorityOperation, casilla_id: str, language: OutputLanguage = OutputLanguage.EN):
    snapshot = operation.snapshot("130", filing_year=2026, period="1T")
    return build_casilla_help_card(casilla_id, snapshot=snapshot, operation=operation, language=language, on=_ON)


def test_a_formula_reads_as_box_arithmetic_in_the_filers_language(operation: PinnedAuthorityOperation) -> None:
    english = _card(operation, "04")
    spanish = _card(operation, "04", OutputLanguage.ES)

    assert english.formula is not None
    assert english.formula.text == "[04] = max(0, 20 % of [03])"
    assert english.formula.complete
    assert spanish.formula is not None
    assert spanish.formula.text == "[04] = máx(0; 20 % de [03])"


def test_official_fragments_are_quoted_with_their_source(operation: PinnedAuthorityOperation) -> None:
    card = _card(operation, "04")

    assert card.quotes
    quote = card.quotes[0]
    assert "20 por 100" in quote.fragments
    assert quote.source == "AEAT instructions for the modelo"
    assert quote.source_url.startswith("https://")


def test_the_legal_basis_is_cited_from_each_reference(operation: PinnedAuthorityOperation) -> None:
    card = _card(operation, "01")

    texts = {citation.text for citation in card.legal_basis}
    assert "Ley 35/2006, art.\u00a099" in texts
    assert "Orden EHA/672/2007, art.\u00a01" in texts
    assert "Real Decreto 439/2007, art.\u00a0110" in texts
    assert all(citation.permalink.startswith("https://") for citation in card.legal_basis)


def test_an_unfamiliar_identifier_falls_back_to_the_official_document_id(operation: PinnedAuthorityOperation) -> None:
    reference = operation.legal_reference("convenio-es-ar-1992:art-19")

    assert legal_citation_text(reference) == f"{reference.document_id}, art.\u00a019"


def test_a_citation_never_breaks_between_the_article_and_its_number(operation: PinnedAuthorityOperation) -> None:
    snapshot = operation.snapshot("390", filing_year=2025, period="0A")
    cited = next(item for item in snapshot.revision.casillas if "rd-1624-1992:art-71" in map(str, item.legal_refs))

    card = build_casilla_help_card(cited.id, snapshot=snapshot, operation=operation, language=OutputLanguage.EN, on=_ON)

    texts = {citation.text for citation in card.legal_basis}
    assert "Real Decreto 1624/1992, art.\u00a071" in texts
    # No citation leaves a space a line may break at between "art." and its number.
    assert not any(re.search(r"art\.[^\S\u00a0]", text) for text in texts)


def test_a_bound_box_says_where_its_value_comes_from_and_what_uses_it(operation: PinnedAuthorityOperation) -> None:
    income = _card(operation, "01")
    net = _card(operation, "03")

    assert income.formula is None
    assert income.origins == ("from your income entries",)
    assert "[03]" in income.feeds
    assert "[04]" in net.feeds


def test_a_box_without_limits_states_none(operation: PinnedAuthorityOperation) -> None:
    """No sentence stands in for limits a box does not have: the card shows limits only where they exist."""
    snapshot = operation.snapshot("130", filing_year=2026, period="1T")
    unconstrained = next(item for item in snapshot.revision.casillas if item.constraints is None)

    card = build_casilla_help_card(
        unconstrained.id, snapshot=snapshot, operation=operation, language=OutputLanguage.EN, on=_ON
    )

    assert card.constraints == ()


def test_an_undefined_casilla_is_refused(operation: PinnedAuthorityOperation) -> None:
    with pytest.raises(KeyError):
        _card(operation, "999")


def _path(card: ModeloCasillaHelpCardV1) -> list[str]:
    assert card.reach is not None
    return [step.box for step in card.reach.path]


def test_a_change_travels_to_the_result_along_the_official_form(operation: PinnedAuthorityOperation) -> None:
    """Modelo 130: [07] = [04] - [05] - [06], [12] = [07] + [11], [14] = [12] - [13], [17] from [14], [19] from [17].

    [14] also feeds [15], which feeds [17] again: a longer route, so [15] is
    counted as another box the change reaches rather than put on the chain.
    """
    instalments = _card(operation, "05")
    income = _card(operation, "01")

    assert _path(instalments) == ["[07]", "[12]", "[14]", "[17]", "[19]"]
    assert _path(income) == ["[03]", "[04]", "[07]", "[12]", "[14]", "[17]", "[19]"]
    assert instalments.reach is not None
    assert instalments.reach.others == 1
    assert not instalments.is_result


def test_a_box_feeding_the_result_directly_is_one_step_from_it(operation: PinnedAuthorityOperation) -> None:
    """Modelo 130's [18] (the earlier return's result being corrected) is subtracted in [19] itself."""
    card = _card(operation, "18")

    assert _path(card) == ["[19]"]
    assert card.reach is not None
    assert card.reach.others == 0


def test_the_result_box_is_marked_and_has_no_chain(operation: PinnedAuthorityOperation) -> None:
    card = _card(operation, "19")

    assert card.is_result
    assert card.reach is None


def _card_303(operation: PinnedAuthorityOperation, casilla_id: str) -> ModeloCasillaHelpCardV1:
    snapshot = operation.snapshot("303", filing_year=2026, period="1T")
    return build_casilla_help_card(
        casilla_id, snapshot=snapshot, operation=operation, language=OutputLanguage.EN, on=_ON
    )


def test_a_303_box_reaches_its_result_and_an_informative_one_does_not(operation: PinnedAuthorityOperation) -> None:
    """Modelo 303: [69] sums [66] with its adjustments and [71] settles [69]; [59] is additional information."""
    general = _card_303(operation, "66")
    informative = _card_303(operation, "59")

    assert _path(general) == ["[69]", "[71]"]
    assert informative.reach is not None
    assert informative.reach.path == ()
    assert not informative.is_result


def test_working_figures_on_the_way_are_left_out_of_the_chain(operation: PinnedAuthorityOperation) -> None:
    """A deductible quota reaches [46] through the total-deductible working figure the form does not print."""
    card = _card_303(operation, "29")

    path = _path(card)
    assert path[0] == "[46]"
    assert path[-1] == "[71]"
    assert all(re.fullmatch(r"\[\d+\]", box) for box in path)
    assert card.reach is not None
    assert card.reach.others > 0, "[46] also reaches [64] and [66], which the shortest chain passes by"


def test_a_modelo_that_names_no_result_gives_no_chain(operation: PinnedAuthorityOperation) -> None:
    snapshot = operation.snapshot("349", filing_year=2026, period="1T")
    casilla = snapshot.revision.casillas[0]

    card = build_casilla_help_card(
        casilla.id, snapshot=snapshot, operation=operation, language=OutputLanguage.EN, on=_ON
    )

    assert card.reach is None
    assert not card.is_result
