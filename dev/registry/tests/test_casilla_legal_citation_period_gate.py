"""Casilla citation period correctness over the bundled corpus, excepted only per citation.

Every casilla's cited legal rows must govern the casilla's own edition. The
citations that do not are admitted only by name, one classified ledger entry
per citation. The gate fails on a refused citation the ledger does not name, on
a ledger entry whose citation no longer needs it, and on an entry whose
category contradicts the catalogue. Planted citations on a copy of a real
modelo show the rule refusing a drifting row, including one the modelo also
lists as cross-year authority, and admitting a governing one.
"""

from __future__ import annotations

import collections
from collections.abc import Mapping
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.authority import bundled_authority
from cadrumo.domain.calculations.registry.casilla_legal_citation_period import (
    CasillaCitationKey,
    CitationPeriodRefusal,
    casilla_citation_period_refusals,
    citation_period_correctness,
)
from cadrumo.domain.calculations.registry.schema import ModeloDefinition
from cadrumo.domain.calculations.registry.schema_references import LegalReference

from ..analysis.corpus import bundled_modelo_ids
from ..analysis.legal_citation_period_ledger import (
    CitationException,
    category_disagreements,
    load_citation_exceptions,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_SHOWN = 20


@pytest.fixture(scope="module")
def corpus() -> tuple[ModeloDefinition, ...]:
    authority = bundled_authority()
    return tuple(authority.modelo(modelo_id) for modelo_id in bundled_modelo_ids())


@pytest.fixture(scope="module")
def legal() -> Mapping[str, LegalReference]:
    return bundled_authority().catalogues.legal


@pytest.fixture(scope="module")
def refusals(
    corpus: tuple[ModeloDefinition, ...], legal: Mapping[str, LegalReference]
) -> Mapping[CasillaCitationKey, CitationPeriodRefusal]:
    return {refusal.key: refusal for modelo in corpus for refusal in casilla_citation_period_refusals(modelo, legal)}


@pytest.fixture(scope="module")
def ledger() -> Mapping[CasillaCitationKey, CitationException]:
    return load_citation_exceptions()


def _describe(label: str, lines: list[str]) -> str:
    return f"{len(lines)} {label}; first {_SHOWN}:\n  " + "\n  ".join(lines[:_SHOWN])


def test_every_refused_citation_is_excepted_by_name_in_the_ledger(
    corpus: tuple[ModeloDefinition, ...],
    legal: Mapping[str, LegalReference],
    ledger: Mapping[CasillaCitationKey, CitationException],
) -> None:
    report = citation_period_correctness(corpus, legal, ledger.keys())
    problems = []
    if report.uncovered:
        by_modelo = collections.Counter(refusal.key.modelo for refusal in report.uncovered)
        problems.append(
            _describe(
                f"refused citations the ledger does not name, by modelo {dict(sorted(by_modelo.items()))}",
                [refusal.describe() for refusal in report.uncovered],
            )
        )
    if report.stale:
        problems.append(
            _describe(
                "ledger exceptions whose citation now governs its edition or is gone",
                [f"{key.modelo} {key.revision} {key.casilla} {key.reference}" for key in report.stale],
            )
        )
    assert report.is_correct, "\n".join(problems)


def test_every_ledger_category_agrees_with_the_catalogue(
    ledger: Mapping[CasillaCitationKey, CitationException],
    refusals: Mapping[CasillaCitationKey, CitationPeriodRefusal],
) -> None:
    disagreeing = category_disagreements(ledger, refusals)
    assert not disagreeing, _describe(
        "ledger categories that contradict the catalogue's governing rows",
        [f"{ledger[key].category} but {refusals[key].describe()}" for key in disagreeing],
    )


def test_the_known_drifting_citations_are_refused_by_name(
    refusals: Mapping[CasillaCitationKey, CitationPeriodRefusal],
) -> None:
    anachronistic = refusals[CasillaCitationKey("100", "2020", "0066", "ley-35-2006:art-23")]
    assert anachronistic.alternatives == ()
    message = anachronistic.describe()
    for fragment in ("modelo 100", "edition 2020", "[2020-01-01..2020-12-31]", "casilla 0066", "ley-35-2006:art-23"):
        assert fragment in message

    later_orden = refusals[CasillaCitationKey("190", "2024", "decl.complementaria", "orden-hac-1431-2025:art-2")]
    assert later_orden.alternatives == ()


def test_a_planted_superseded_citation_names_the_governing_alternative(
    corpus: tuple[ModeloDefinition, ...], legal: Mapping[str, LegalReference]
) -> None:
    """The corpus carries no superseded-with-alternative citation once every real one is re-cited.

    ``ley-35-2006:art-23-2021`` governs 2021-2023; the base ``ley-35-2006:art-23`` row governs
    only from 2024. Planting the superseded reference on a casilla that does not already cite
    it demonstrates the refusal names its governing alternative, the same shape a real drifting
    citation would take.
    """
    modelo = _modelo(corpus, "100")
    planted = _plant(modelo, "2022", "0066", "ley-35-2006:art-23")
    new = set(casilla_citation_period_refusals(planted, legal)) - set(casilla_citation_period_refusals(modelo, legal))
    assert [refusal.key for refusal in new] == [CasillaCitationKey("100", "2022", "0066", "ley-35-2006:art-23")]
    (refusal,) = new
    assert refusal.alternatives == ("ley-35-2006:art-23-2021",)


def test_dropping_one_real_exception_exposes_its_citation(
    corpus: tuple[ModeloDefinition, ...],
    legal: Mapping[str, LegalReference],
    ledger: Mapping[CasillaCitationKey, CitationException],
) -> None:
    baseline = citation_period_correctness(corpus, legal, ledger.keys())
    dropped = min(ledger)
    report = citation_period_correctness(corpus, legal, set(ledger) - {dropped})
    assert {refusal.key for refusal in report.uncovered} - {refusal.key for refusal in baseline.uncovered} == {dropped}
    assert report.stale == baseline.stale


def test_an_exception_naming_a_governing_citation_is_stale(
    corpus: tuple[ModeloDefinition, ...],
    legal: Mapping[str, LegalReference],
    ledger: Mapping[CasillaCitationKey, CitationException],
) -> None:
    governing = CasillaCitationKey("100", "2024", "0066", "ley-35-2006:art-22")
    assert governing in _citations(corpus)
    baseline = citation_period_correctness(corpus, legal, ledger.keys())
    report = citation_period_correctness(corpus, legal, {*ledger, governing})
    assert set(report.stale) - set(baseline.stale) == {governing}
    assert report.uncovered == baseline.uncovered


def test_a_planted_drifting_citation_is_refused(
    corpus: tuple[ModeloDefinition, ...], legal: Mapping[str, LegalReference]
) -> None:
    modelo = _modelo(corpus, "100")
    planted = _plant(modelo, "2024", "0066", "ley-35-2006:art-52-2015")
    new = set(casilla_citation_period_refusals(planted, legal)) - set(casilla_citation_period_refusals(modelo, legal))
    assert [refusal.key for refusal in new] == [CasillaCitationKey("100", "2024", "0066", "ley-35-2006:art-52-2015")]
    (refusal,) = new
    assert refusal.alternatives == ("ley-35-2006:art-52",)
    assert "[2015-01-01..2020-12-31]" in refusal.describe()


def test_a_planted_citation_the_modelo_lists_as_cross_year_authority_is_still_refused(
    corpus: tuple[ModeloDefinition, ...], legal: Mapping[str, LegalReference]
) -> None:
    modelo = _modelo(corpus, "100")
    reference = "ley-35-2006:art-23"
    assert reference in modelo.legal_refs
    casilla = next(
        str(casilla.id) for casilla in modelo.revisions["2020"].casillas if reference not in casilla.legal_refs
    )
    planted = _plant(modelo, "2020", casilla, reference)
    new = {refusal.key for refusal in casilla_citation_period_refusals(planted, legal)} - {
        refusal.key for refusal in casilla_citation_period_refusals(modelo, legal)
    }
    assert new == {CasillaCitationKey("100", "2020", casilla, reference)}


def test_a_planted_governing_citation_is_admitted(
    corpus: tuple[ModeloDefinition, ...], legal: Mapping[str, LegalReference]
) -> None:
    modelo = _modelo(corpus, "100")
    planted = _plant(modelo, "2024", "0066", "ley-35-2006:art-52")
    assert casilla_citation_period_refusals(planted, legal) == casilla_citation_period_refusals(modelo, legal)


def test_a_planted_unresolved_citation_is_refused(
    corpus: tuple[ModeloDefinition, ...], legal: Mapping[str, LegalReference]
) -> None:
    modelo = _modelo(corpus, "100")
    planted = _plant(modelo, "2024", "0066", "ley-35-2006:art-9999")
    new = set(casilla_citation_period_refusals(planted, legal)) - set(casilla_citation_period_refusals(modelo, legal))
    (refusal,) = new
    assert refusal.governs_from is None
    assert "resolves to no legal catalogue row" in refusal.describe()


def _citations(corpus: tuple[ModeloDefinition, ...]) -> set[CasillaCitationKey]:
    return {
        CasillaCitationKey(modelo.id, str(revision.id), str(casilla.id), reference)
        for modelo in corpus
        for revision in modelo.revisions.values()
        for casilla in revision.casillas
        for reference in casilla.legal_refs
    }


def _modelo(corpus: tuple[ModeloDefinition, ...], modelo_id: str) -> ModeloDefinition:
    return next(modelo for modelo in corpus if modelo.id == modelo_id)


def _plant(modelo: ModeloDefinition, revision_id: str, casilla_id: str, reference: str) -> ModeloDefinition:
    """Return a copy of ``modelo`` whose one casilla also cites ``reference``."""
    revision = modelo.revisions[revision_id]
    casillas = tuple(
        casilla.model_copy(update={"legal_refs": (*casilla.legal_refs, reference)})
        if str(casilla.id) == casilla_id
        else casilla
        for casilla in revision.casillas
    )
    planted = revision.model_copy(update={"casillas": casillas})
    return modelo.model_copy(update={"revisions": {**modelo.revisions, revision_id: planted}})


_ENTRY = (
    'modelo = "100"\nrevision = "2020"\nreference = "ley-35-2006:art-23"\n'
    'category = "{category}"\nreason = "{reason}"\ncasillas = {casillas}\n'
)


def _ledger(tmp_path: Path, *entries: str) -> Path:
    path = tmp_path / "ledger.toml"
    path.write_text("".join(f"[[exception]]\n{entry}\n" for entry in entries), encoding="utf-8")
    return path


def test_the_ledger_reader_admits_a_well_formed_exception(tmp_path: Path) -> None:
    entry = _ENTRY.format(category="no_governing_row_catalogued", reason="no row", casillas='["0066", "0100"]')
    assert set(load_citation_exceptions(_ledger(tmp_path, entry))) == {
        CasillaCitationKey("100", "2020", "0066", "ley-35-2006:art-23"),
        CasillaCitationKey("100", "2020", "0100", "ley-35-2006:art-23"),
    }


def test_the_ledger_reader_refuses_an_exception_without_a_reason(tmp_path: Path) -> None:
    entry = _ENTRY.format(category="no_governing_row_catalogued", reason=" ", casillas='["0066"]')
    with pytest.raises(ValueError, match="has no reason"):
        load_citation_exceptions(_ledger(tmp_path, entry))


def test_the_ledger_reader_refuses_an_unknown_category(tmp_path: Path) -> None:
    entry = _ENTRY.format(category="looks_fine", reason="no row", casillas='["0066"]')
    with pytest.raises(ValueError, match="unknown category"):
        load_citation_exceptions(_ledger(tmp_path, entry))


def test_the_ledger_reader_refuses_an_exception_naming_no_casilla(tmp_path: Path) -> None:
    entry = _ENTRY.format(category="no_governing_row_catalogued", reason="no row", casillas="[]")
    with pytest.raises(ValueError, match="names no casillas"):
        load_citation_exceptions(_ledger(tmp_path, entry))


def test_the_ledger_reader_refuses_a_citation_named_twice(tmp_path: Path) -> None:
    entry = _ENTRY.format(category="no_governing_row_catalogued", reason="no row", casillas='["0066"]')
    with pytest.raises(ValueError, match="a second time"):
        load_citation_exceptions(_ledger(tmp_path, entry, entry))
