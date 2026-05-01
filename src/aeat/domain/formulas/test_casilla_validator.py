"""Mandatory-citation validator tests for :class:`CasillaDefinition` (#339).

EPIC #316 audit finding: a ``computed=True`` casilla without a non-empty
``legal_basis`` ships unverifiable tax math. The validator under test
locks this convention as a hard import-time invariant. The 18 landed
rulesets already honour the convention; these tests are the unit-level
proof that the rule is enforced and the regression guard for any future
ruleset that bypasses the convention.
"""

from __future__ import annotations

from datetime import date

import pytest

from ...core.errors import RulesetValidationError
from ...core.i18n import Translatable
from ..casillas import CasillaDataType
from ..modelos import LegalCitation, LegalCitationSource
from ._casilla import CasillaDefinition

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


_LABEL: Translatable = {
    "es": "Rendimiento neto",
    "en": "Net return",
    "hu": "Nettó eredmény",
}


def _citation() -> LegalCitation:
    """Return a real :class:`LegalCitation` for use in fixtures."""
    return LegalCitation(
        source=LegalCitationSource.REAL_DECRETO,
        article="110",
        url=None,
        quoted_text_es=(
            "RD 439/2007 art. 110 — fixture-only citation for the casilla "
            "validator unit tests; not authored as a binding ruleset reference."
        ),
        retrieval_date=date(2026, 4, 25),
        is_curated_summary=True,
    )


def test_computed_casilla_with_citation_constructs() -> None:
    """A ``computed=True`` casilla with one citation passes the validator."""
    citation = _citation()
    casilla_def = CasillaDefinition(
        casilla_id="03",
        label=_LABEL,
        computed=True,
        data_type=CasillaDataType.CURRENCY_EUR,
        legal_basis=(citation,),
    )
    assert casilla_def.casilla_id == "03"
    assert casilla_def.computed is True
    assert casilla_def.legal_basis == (citation,)


def test_computed_casilla_without_citation_raises() -> None:
    """A ``computed=True`` casilla with empty ``legal_basis`` fails import.

    Pydantic v2 wraps validator-raised :class:`ValueError` in
    :class:`pydantic.ValidationError`, but lets non-``ValueError``
    exceptions propagate raw. The validator raises
    :class:`RulesetValidationError` directly — same pattern as
    :meth:`Ruleset.model_post_init` — so the test catches that class
    directly.
    """
    with pytest.raises(RulesetValidationError) as exc_info:
        CasillaDefinition(
            casilla_id="04",
            label=_LABEL,
            computed=True,
            data_type=CasillaDataType.CURRENCY_EUR,
            legal_basis=(),
        )
    message = str(exc_info.value)
    assert "'04'" in message
    assert "legal_basis" in message
    assert "BOE" in message or "Ley" in message or "RD" in message


def test_informational_casilla_without_citation_constructs() -> None:
    """A ``computed=False`` casilla without citations is allowed.

    User-input rows (caller-supplied values, cross-quarter accumulators,
    income amounts, etc.) carry their legal anchoring on the surrounding
    instructions, not on the casilla itself. The validator targets only
    the engine-derived rows where the absence of a citation makes the
    calculation unverifiable.
    """
    casilla_def = CasillaDefinition(
        casilla_id="01",
        label=_LABEL,
        computed=False,
        data_type=CasillaDataType.CURRENCY_EUR,
        legal_basis=(),
    )
    assert casilla_def.computed is False
    assert casilla_def.legal_basis == ()


def test_computed_casilla_with_multiple_citations_constructs() -> None:
    """The validator accepts any non-empty tuple of citations."""
    primary = _citation()
    secondary = LegalCitation(
        source=LegalCitationSource.LEY,
        article="99",
        url=None,
        quoted_text_es=(
            "Ley 35/2006 art. 99 — fixture-only secondary citation for the "
            "casilla validator unit tests; not authored as a binding ruleset "
            "reference."
        ),
        retrieval_date=date(2026, 4, 25),
        is_curated_summary=True,
    )
    casilla_def = CasillaDefinition(
        casilla_id="04",
        label=_LABEL,
        computed=True,
        data_type=CasillaDataType.CURRENCY_EUR,
        legal_basis=(primary, secondary),
    )
    assert len(casilla_def.legal_basis) == 2
