"""The help card names what a box's formula reads off the form, and cites its law in words.

Cards are built over the published registry. Modelo 303 box 28 sums two
ledger figures the official form does not print, so its card names both, owned
by the ledger; box 27 reads a working figure the application computes, which
no area owns. The legal basis is cited from each reference's own identifier.
"""

from __future__ import annotations

from datetime import date

import pytest

from ....core.external_constants import OutputLanguage
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ..casilla_help import ModeloCasillaHelpCardV1, build_casilla_help_card
from ..source_policy import SourceSurface
from .work_form_fixture import form_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _card(operation: PinnedAuthorityOperation, casilla_id: str) -> ModeloCasillaHelpCardV1:
    snapshot = form_snapshot(operation, "303", 2026, "1T")
    return build_casilla_help_card(
        casilla_id, snapshot=snapshot, operation=operation, language=OutputLanguage.EN, on=date(2026, 3, 31)
    )


def test_a_box_names_the_ledger_figures_its_formula_reads_off_the_form(operation: PinnedAuthorityOperation) -> None:
    card = _card(operation, "28")

    figures = {figure.casilla_id: figure.surface for figure in card.outside_figures}

    assert figures == {
        "iva.soportado.interiores.base": SourceSurface.LEDGER,
        "iva.autorepercutido.interior.deducible.base": SourceSurface.LEDGER,
    }
    assert all(figure.label and figure.binding_id is None for figure in card.outside_figures)


def test_a_working_figure_no_area_owns_is_named_with_no_surface(operation: PinnedAuthorityOperation) -> None:
    card = _card(operation, "27")

    assert [(figure.casilla_id, figure.surface) for figure in card.outside_figures] == [
        ("iva.cuota-devengada-total", SourceSurface.NONE)
    ]


def test_the_legal_basis_is_cited_in_words_with_its_official_link(operation: PinnedAuthorityOperation) -> None:
    card = _card(operation, "28")

    assert [citation.text for citation in card.legal_basis][:2] == [
        "Ley 37/1992, art.\u00a092",
        "Ley 37/1992, art.\u00a094",
    ]
    assert all(citation.permalink.startswith("https://") for citation in card.legal_basis)
