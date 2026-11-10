"""Teeth for the historical-carrier admission on the substantive-law window check.

A revision that carries HISTORICAL values legitimately cites the provisions that
governed those periods: a modelo 303 revision can hold the earlier prorrata
especial margin whose wording was repealed before the revision began. The citation defends the
VALUE's window, which sits inside the provision's force, not the revision's,
which does not.

The exemption is deliberately hard to earn, and each test below pins one clause
of it. Containment rather than overlap, a closed value window, a law-fixing axis,
and carrier exclusivity are what stop this from becoming a way to launder a stale
citation, which is the defect the whole window check exists to catch.

A bracket row is dated like a value, so a rate scale whose wording changed by
year earns the same admission through its rows' own windows on the parameter's
bracket axis. The bracket-row tests below run the whole revision check, because
that is where carrier exclusivity is enforced.
"""

from __future__ import annotations

from datetime import date

import pytest

from ..errors import RegistryValidationError
from ..schema import ModeloDefinition, ModeloRevision
from ..schema_catalogues import RegistryCatalogues
from ..schema_formula import BracketEntry, ParameterDefinition
from ..schema_references import LegalReference, PeriodSelector
from ..snapshot import check_revision_scoped_legal_windows, historical_carrier_admits
from .authored_editions import filing_year_envelope

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

# The fixture timeline is anchored on the first exercise after the repealed wording left
# force; every other date is written as a whole number of years from it, so the
# containment relations under test hold wherever the support floor sits.
_FIRST_YEAR = filing_year_envelope().floor
_LAST_YEAR = _FIRST_YEAR + 7
_REVISION_ID = f"{_FIRST_YEAR}-{_LAST_YEAR}"


def _on(years_from_first: int, month: int, day: int) -> date:
    return date(_FIRST_YEAR + years_from_first, month, day)


_GOVERNS_FROM = _on(-22, 1, 1)
_GOVERNS_TO = _on(-1, 12, 31)


def _repealed_reference() -> LegalReference:
    """A substantive-law citation whose wording left force before the first exercise of the fixture timeline."""
    return LegalReference.model_validate(
        {
            "id": "ley-37-1992:art-103-original",
            "evidence_tier": "legal_authority",
            "authority": "boe",
            "kind": "ley",
            "corpus_ref": "corpus/normatives/html/ley-37-1992.html#a103",
            "document_id": "BOE-A-1992-28740",
            "article": "103",
            "permalink": "https://www.boe.es/buscar/act.php?id=BOE-A-1992-28740#a103",
            "published_at": _on(-23, 12, 29),
            "required_text": ("regla de prorrata",),
            "effective_from": _GOVERNS_FROM,
            "effective_to": _GOVERNS_TO,
            "review_status": "agent_reviewed",
            "reviewed_at": date(1980, 9, 4),
            "reviewed_by": "fixture for the historical-carrier gate; not authored into the tree",
        },
    )


def test_a_value_window_inside_the_governed_span_is_admitted() -> None:
    """The case the gate exists to allow: historical value, historical provision."""
    assert historical_carrier_admits(
        _repealed_reference(),
        ((_GOVERNS_FROM, _GOVERNS_TO, "filing_period"),),
    )


def test_a_narrower_contained_window_is_admitted() -> None:
    """Containment, not equality: a value need not span the whole provision."""
    assert historical_carrier_admits(
        _repealed_reference(),
        ((_on(-15, 1, 1), _on(-5, 12, 31), "filing_period"),),
    )


def test_a_current_era_value_grounded_in_repealed_wording_is_refused() -> None:
    """TEETH: the stale-citation defect the whole window check exists to catch."""
    assert not historical_carrier_admits(
        _repealed_reference(),
        ((_on(7, 1, 1), None, "filing_period"),),
    )


def test_an_open_ended_value_window_is_refused() -> None:
    """TEETH: the exemption cannot be bought by declaring an open window.

    An open window can never be contained in a closed governed span, so the
    cheapest route to a false admission is closed off by construction.
    """
    assert not historical_carrier_admits(
        _repealed_reference(),
        ((_GOVERNS_FROM, None, "filing_period"),),
    )


def test_a_closed_but_uncontained_window_is_refused() -> None:
    """TEETH: overlap is not enough, and a post-repeal window earns nothing."""
    assert not historical_carrier_admits(
        _repealed_reference(),
        ((_on(0, 1, 1), _on(6, 12, 31), "filing_period"),),
    )


def test_a_window_straddling_the_repeal_is_refused() -> None:
    """TEETH: partial containment is refused, so a value cannot reach past force."""
    assert not historical_carrier_admits(
        _repealed_reference(),
        ((_on(-5, 1, 1), _on(1, 12, 31), "filing_period"),),
    )


def test_a_submission_date_value_never_earns_the_exemption() -> None:
    """TEETH: when a declaration was filed fixes no applicable law.

    Contained on every other clause, and still refused, so the axis check cannot
    pass vacuously.
    """
    assert not historical_carrier_admits(
        _repealed_reference(),
        ((_GOVERNS_FROM, _GOVERNS_TO, "submission_date"),),
    )


def test_a_reference_cited_outside_parameters_earns_nothing() -> None:
    """TEETH: carrier exclusivity, which the caller enforces by passing no spans.

    A reference some non-parameter record also cites has no parameter carrier to
    defend it, and must be checked against the revision window as before.
    """
    assert not historical_carrier_admits(_repealed_reference(), ())


_CURRENT_WORDING = "ley-35-2006:art-93-fixture-vigente"
_WORDING_MIDDLE = "ley-35-2006:art-93-fixture-middle"
_WORDING_FIRST_YEAR = "ley-35-2006:da-31-fixture"
_SOURCE = "aeat-fixture-procedure"
_MODELO_WIDE_LEGAL = "rd-439-2007:art-113-fixture"


def _wording(legal_id: str, effective_from: date, effective_to: date | None) -> LegalReference:
    """A substantive-law wording of a rate scale, in force over one span."""
    return LegalReference.model_validate(
        {
            "id": legal_id,
            "evidence_tier": "legal_authority",
            "authority": "boe",
            "kind": "ley",
            "corpus_ref": "corpus/normatives/html/ley-35-2006.html#a93",
            "document_id": "BOE-A-2006-20764",
            "article": "93",
            "permalink": "https://www.boe.es/buscar/act.php?id=BOE-A-2006-20764#a93",
            "published_at": _on(-9, 11, 29),
            "required_text": ("escala",),
            "effective_from": effective_from,
            "effective_to": effective_to,
            "review_status": "agent_reviewed",
            "reviewed_at": date(1980, 9, 30),
            "reviewed_by": "fixture for the bracket-row carrier gate; not authored into the tree",
        },
    )


def _catalogues() -> RegistryCatalogues:
    return RegistryCatalogues(
        legal={
            _CURRENT_WORDING: _wording(_CURRENT_WORDING, _on(-8, 1, 1), None),
            _WORDING_MIDDLE: _wording(_WORDING_MIDDLE, _on(0, 1, 1), _on(5, 12, 31)),
            _WORDING_FIRST_YEAR: _wording(_WORDING_FIRST_YEAR, _on(0, 1, 1), _on(0, 12, 31)),
        },
        sources={},
    )


def _top_row(rate: str, valid_from: date, valid_to: date | None) -> BracketEntry:
    """The open-ended tranche above 600.000 euros, dated to one wording."""
    return BracketEntry(
        lower_bound="600000",
        fixed_addition="144000",
        marginal_rate=rate,
        valid_from=valid_from,
        valid_to=valid_to,
    )


def _closed_revision(
    *,
    scale_refs: tuple[str, ...],
    top_rows: tuple[BracketEntry, ...],
    edition_refs: tuple[str, ...] = (_CURRENT_WORDING,),
) -> tuple[ModeloDefinition, ModeloRevision]:
    """A closed multi-exercise edition carrying one two-tranche scale."""
    lower_row = BracketEntry(
        lower_bound="0",
        upper_bound="600000",
        fixed_addition="0",
        marginal_rate="0.24",
        valid_from=_on(0, 1, 1),
    )
    scale = ParameterDefinition(
        id="modelo-fixture.escala-general",
        data_type="bracket_table",
        unit="EUR",
        bracket_axis="filing_period",
        legal_refs=scale_refs,
        source_refs=(_SOURCE,),
        brackets=(lower_row, *top_rows),
    )
    revision = ModeloRevision(
        id=_REVISION_ID,
        localization_key="fixture",
        valid_from=_on(0, 1, 1),
        valid_to=_on(7, 12, 31),
        period_selector=PeriodSelector(year_from=_FIRST_YEAR, year_to=_LAST_YEAR, periods=("0A",)),
        legal_refs=edition_refs,
        source_refs=(_SOURCE,),
        parameters=(scale,),
    )
    modelo = ModeloDefinition(
        id="151",
        title_localization_key="fixture.title",
        official_name_localization_key="fixture.official_name",
        tax_domain="irpf",
        cadence="annual",
        jurisdiction="ES-AEAT",
        legal_refs=(_MODELO_WIDE_LEGAL,),
        source_refs=(_SOURCE,),
        revisions={revision.id: revision},
    )
    return modelo, revision


def test_bracket_rows_inside_each_wording_admit_their_citations() -> None:
    """The case the bracket carrier exists to allow: one dated row per wording."""
    modelo, revision = _closed_revision(
        scale_refs=(_CURRENT_WORDING, _WORDING_MIDDLE, _WORDING_FIRST_YEAR),
        top_rows=(
            _top_row("0.47", _on(0, 1, 1), _on(0, 12, 31)),
            _top_row("0.45", _on(1, 1, 1), _on(5, 12, 31)),
            _top_row("0.47", _on(6, 1, 1), None),
        ),
    )

    check_revision_scoped_legal_windows(modelo, revision, _catalogues())


def test_a_bracket_row_outside_the_cited_wording_is_refused() -> None:
    """TEETH: a closed row dated after the wording left force defends nothing."""
    modelo, revision = _closed_revision(
        scale_refs=(_CURRENT_WORDING, _WORDING_MIDDLE),
        top_rows=(
            _top_row("0.45", _on(6, 1, 1), _on(7, 12, 31)),
            _top_row("0.47", _on(8, 1, 1), None),
        ),
    )

    with pytest.raises(RegistryValidationError, match=_WORDING_MIDDLE):
        check_revision_scoped_legal_windows(modelo, revision, _catalogues())


def test_a_bracket_row_straddling_the_wording_is_refused() -> None:
    """TEETH: containment, so a row cannot reach past the wording it cites."""
    modelo, revision = _closed_revision(
        scale_refs=(_CURRENT_WORDING, _WORDING_FIRST_YEAR),
        top_rows=(
            _top_row("0.47", _on(0, 1, 1), _on(1, 12, 31)),
            _top_row("0.45", _on(2, 1, 1), None),
        ),
    )

    with pytest.raises(RegistryValidationError, match=_WORDING_FIRST_YEAR):
        check_revision_scoped_legal_windows(modelo, revision, _catalogues())


def test_an_edition_citation_no_row_carries_is_refused() -> None:
    """TEETH: an out-of-window wording cited by the edition alone stays refused."""
    modelo, revision = _closed_revision(
        scale_refs=(_CURRENT_WORDING,),
        top_rows=(_top_row("0.47", _on(0, 1, 1), None),),
        edition_refs=(_CURRENT_WORDING, _WORDING_MIDDLE),
    )

    with pytest.raises(RegistryValidationError, match=_WORDING_MIDDLE):
        check_revision_scoped_legal_windows(modelo, revision, _catalogues())


def test_a_wording_the_edition_also_cites_earns_no_bracket_carrier() -> None:
    """TEETH: carrier exclusivity holds for bracket rows as for dated values.

    The row alone would be admitted; the edition's own citation of the same
    wording claims the whole closed window, which that wording does not cover.
    """
    modelo, revision = _closed_revision(
        scale_refs=(_CURRENT_WORDING, _WORDING_MIDDLE),
        top_rows=(
            _top_row("0.45", _on(0, 1, 1), _on(5, 12, 31)),
            _top_row("0.47", _on(6, 1, 1), None),
        ),
        edition_refs=(_CURRENT_WORDING, _WORDING_MIDDLE),
    )

    with pytest.raises(RegistryValidationError, match=_WORDING_MIDDLE):
        check_revision_scoped_legal_windows(modelo, revision, _catalogues())
