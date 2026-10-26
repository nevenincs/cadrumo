"""Modelo 322 and 490 editions declare every box their own record design prints.

Each of these editions stores its payload against the edition before it and
states only its differences. That storage choice must not change what an
edition serves: in every supported year and period, the edition the registry
selects declares every bracketed box printed by the record design it cites, so a
box the design adds is present and a reused row is not lost.
"""

from __future__ import annotations

import re
from functools import cache

import pytest

from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.schema import ModeloRevision

from ..compiler.authority import compiled_bundled_authority
from ..compiler.loader import load_shared_catalogues

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_MODELOS = ("322", "490")
_BOX = re.compile(r"\[(\w{1,5})\]")


@cache
def _supported_years() -> tuple[int, ...]:
    support = load_shared_catalogues(bundled_path("registry", "aeat")).supported_filing_years
    assert support is not None, "the registry declares no supported filing years"
    return support.years


@cache
def _editions(modelo_id: str, year: int) -> tuple[ModeloRevision, ...]:
    """Return the distinct editions serving ``year`` over every period the modelo's editions declare."""
    authority = compiled_bundled_authority()
    periods = sorted(
        {
            str(period)
            for revision in authority.modelo(modelo_id).revisions.values()
            for period in revision.period_selector.declared_periods
        }
    )
    selected: dict[str, ModeloRevision] = {}
    for period in periods:
        revision = authority.snapshot(
            modelo_id, filing_year=year, period=period, grade=RegistryAuthorityGrade.APPLICABILITY
        ).revision
        selected.setdefault(str(revision.id), revision)
    return tuple(selected.values())


def _design_boxes(revision: ModeloRevision) -> set[str]:
    sources = compiled_bundled_authority().catalogues.sources
    designs = [ref for ref in revision.source_refs if sources[ref].kind == "record_design"]
    assert len(designs) == 1, f"edition {revision.id} cites record designs {designs}"
    corpus_path = bundled_path() / sources[designs[0]].corpus_path
    text = corpus_path.with_name(f"{corpus_path.name}.extracted.md").read_text(encoding="utf-8")
    return set(_BOX.findall(text))


def _undeclared_boxes(revision: ModeloRevision) -> list[str]:
    declared = {str(casilla.number) for casilla in revision.casillas}
    return sorted(_design_boxes(revision) - declared)


@pytest.mark.parametrize("modelo_id", _MODELOS)
@pytest.mark.parametrize("year", _supported_years())
def test_every_printed_box_is_declared_by_the_selected_edition(modelo_id: str, year: int) -> None:
    editions = _editions(modelo_id, year)
    assert editions, f"modelo {modelo_id} serves no edition in {year}"
    for revision in editions:
        assert _design_boxes(revision), f"{modelo_id} {revision.id}: its record design prints no box"
        assert _undeclared_boxes(revision) == [], f"{modelo_id} {year}: edition {revision.id}"


@pytest.mark.parametrize("modelo_id", _MODELOS)
def test_a_box_lost_by_storage_reuse_is_reported(modelo_id: str) -> None:
    revision = _editions(modelo_id, _supported_years()[-1])[0]
    printed = _design_boxes(revision)
    lost = next(casilla for casilla in revision.casillas if str(casilla.number) in printed)
    reduced = revision.model_copy(update={"casillas": tuple(c for c in revision.casillas if c is not lost)})
    assert _undeclared_boxes(reduced) == [str(lost.number)]
