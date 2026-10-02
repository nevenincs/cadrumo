"""Modelo 202 prior-twelve-month INCN input in every year of the support envelope.

LIS art. 40.3 makes the base-imponible modality mandatory once the importe neto
de la cifra de negocios of the twelve months before the tax period exceeds six
million euros, so the INCN decides which modality a filer may use. Every record
design selected inside the envelope carries that six-million-euro flag and every
instructions era states the rule, so the INCN profile binding is authored once
and hydrates in each supported year. Each year's expectation is read from the
record design and the instructions source its own edition cites rather than
restated here.
"""

from __future__ import annotations

import re
from datetime import date
from functools import cache

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.schema import BindingDefinition, ModeloRevision

from ..compiler.authority import compiled_bundled_authority
from ..compiler.loader import load_shared_catalogues

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_MODELO = "202"
_PERIODS = ("1P", "2P", "3P")
_BINDING = "modelo-202-incn-prior-12-months"
_CITED_TEXT = "importe neto de la cifra de negocios"
# The design's own statement of the art. 40.3 threshold flag.
_DESIGN_FLAG = re.compile(r"(12|doce) meses anteriores[^\n]*6\.000\.000")


@cache
def _supported_years() -> tuple[int, ...]:
    support = load_shared_catalogues(bundled_path("registry", "aeat")).supported_filing_years
    assert support is not None, "the registry declares no supported filing years"
    return support.years


@cache
def _edition(year: int, period: str) -> ModeloRevision:
    return compiled_bundled_authority().snapshot(_MODELO, filing_year=year, period=period).revision


def _record_design_text(revision: ModeloRevision) -> str:
    """Return the extracted text of the record design the edition's casillas cite."""
    sources = compiled_bundled_authority().catalogues.sources
    assert revision.casilla_source_refs is not None, f"edition {revision.id} declares no casilla sources"
    designs = {ref for ref in revision.casilla_source_refs if sources[ref].kind == "record_design"}
    assert len(designs) == 1, f"edition {revision.id} cites record designs {sorted(designs)}"
    (design,) = designs
    corpus_path = bundled_path() / sources[design].corpus_path
    return corpus_path.with_name(f"{corpus_path.name}.extracted.md").read_text(encoding="utf-8")


def _incn_binding_problems(revision: ModeloRevision, year: int) -> list[str]:
    """Name every way the edition fails to carry the INCN input grounded for ``year``."""
    bindings = [binding for binding in revision.bindings if binding.id == _BINDING]
    if len(bindings) != 1:
        return [f"{revision.id}: expected one {_BINDING} binding, found {len(bindings)}"]
    (binding,) = bindings
    problems: list[str] = []
    provider = binding.provider.model_dump(mode="python")
    if (provider.get("kind"), provider.get("profile_model"), provider.get("field")) != (
        "profile",
        "taxpayer",
        "incn_prior_12_months",
    ):
        problems.append(f"{revision.id}: {_BINDING} is not the taxpayer INCN profile input")
    if (binding.value.data_type, binding.value.channel) != ("money", "decimal"):
        problems.append(f"{revision.id}: {_BINDING} is not a decimal money value")
    problems.extend(_citation_problems(revision, binding, year))
    return problems


def _citation_problems(revision: ModeloRevision, binding: BindingDefinition, year: int) -> list[str]:
    """Require the binding's citation to name instructions in force for ``year``."""
    sources = compiled_bundled_authority().catalogues.sources
    problems: list[str] = []
    cited = [citation for citation in binding.source_citations if _CITED_TEXT in citation.required_text]
    if not cited:
        return [f"{revision.id}: {_BINDING} cites no instructions text for the INCN input"]
    for citation in cited:
        source = sources[citation.source_ref]
        if source.applies_from is not None and source.applies_from > date(year, 1, 1):
            problems.append(f"{revision.id}: {citation.source_ref} opens after {year}")
        if source.applies_to is not None and source.applies_to < date(year, 12, 31):
            problems.append(f"{revision.id}: {citation.source_ref} closes before {year} ends")
    return problems


@pytest.mark.parametrize("period", _PERIODS)
@pytest.mark.parametrize("year", _supported_years())
def test_each_supported_year_declares_the_incn_input_its_design_lays_out(year: int, period: str) -> None:
    revision = _edition(year, period)

    assert _DESIGN_FLAG.search(_record_design_text(revision)), f"{revision.id} design prints no INCN flag"
    assert _incn_binding_problems(revision, year) == []


def test_every_supported_year_hydrates_one_identical_incn_contract() -> None:
    """The member differs across years only in the instructions it cites."""
    shapes = set()
    for year in _supported_years():
        for period in _PERIODS:
            (binding,) = (item for item in _edition(year, period).bindings if item.id == _BINDING)
            shape = binding.model_dump(mode="json", exclude={"source_citations", "source_refs"})
            shapes.add(repr(sorted(shape.items())))
    assert len(shapes) == 1, shapes


def test_incn_check_detects_a_missing_binding_and_an_out_of_era_citation() -> None:
    """A dropped binding and a citation of instructions outside the year are reported, not passed."""
    year = min(_supported_years())
    revision = _edition(year, _PERIODS[0])
    (binding,) = (item for item in revision.bindings if item.id == _BINDING)

    without = revision.model_copy(update={"bindings": tuple(item for item in revision.bindings if item.id != _BINDING)})
    assert any("expected one" in problem for problem in _incn_binding_problems(without, year))

    later = max(_supported_years())
    (later_binding,) = (item for item in _edition(later, _PERIODS[0]).bindings if item.id == _BINDING)
    miscited = binding.model_copy(update={"source_citations": later_binding.source_citations})
    problems = _citation_problems(revision, miscited, year)
    assert problems, "a citation of later-era instructions must not ground the earliest supported year"
