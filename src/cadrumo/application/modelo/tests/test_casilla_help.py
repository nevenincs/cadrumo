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
from ..casilla_help import build_casilla_help_card, legal_citation_text

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
    assert income.origins == ("from your ledger income",)
    assert "[03]" in income.feeds
    assert "[04]" in net.feeds


def test_missing_constraints_are_said_to_be_undeclared(operation: PinnedAuthorityOperation) -> None:
    snapshot = operation.snapshot("130", filing_year=2026, period="1T")
    unconstrained = next(item for item in snapshot.revision.casillas if item.constraints is None)

    card = build_casilla_help_card(
        unconstrained.id, snapshot=snapshot, operation=operation, language=OutputLanguage.EN, on=_ON
    )

    assert card.constraints == ("No limits are declared for this box.",)


def test_an_undefined_casilla_is_refused(operation: PinnedAuthorityOperation) -> None:
    with pytest.raises(KeyError):
        _card(operation, "999")
