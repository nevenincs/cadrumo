"""Modelo 220 liquidacion (III) boxes follow the record design each edition cites.

Record T22009001 is printed by every Modelo 220 record design the registry
enrolls, field for field at the same offsets. Each edition must therefore
declare every box of that record whose printed description identifies it, and
a label naming the periodo impositivo must name the one its own design names.
The pair the design prints with an identical description is not asserted
either way: which of the two is the foral column is not stated by the design.
"""

from __future__ import annotations

import re
from collections import Counter
from functools import cache

import pytest

from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.schema import ModeloRevision

from ..compiler.authority import compiled_bundled_authority
from ..compiler.loader import load_shared_catalogues

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_MODELO = "220"
_PERIOD = "0A"
_RECORD = "T22009001"
_LOCALES = ("es", "en", "ca", "hu")
_FIELD_ROW = re.compile(r"^\d+ \| \d+ \| \d+ \| \w+ \| (?P<description>.*)$")
_BOX = re.compile(r"\[(\d{5})\]")
_PERIOD_YEAR = re.compile(r"período impositivo (\d{4})")


@cache
def _supported_years() -> tuple[int, ...]:
    support = load_shared_catalogues(bundled_path("registry", "aeat")).supported_filing_years
    assert support is not None, "the registry declares no supported filing years"
    return support.years


@cache
def _edition(year: int) -> ModeloRevision:
    return (
        compiled_bundled_authority()
        .snapshot(_MODELO, filing_year=year, period=_PERIOD, grade=RegistryAuthorityGrade.APPLICABILITY)
        .revision
    )


def _design_boxes(revision: ModeloRevision) -> dict[str, str]:
    """Return the record's printed boxes and descriptions from the record design the edition cites."""
    sources = compiled_bundled_authority().catalogues.sources
    designs = [ref for ref in revision.source_refs if sources[ref].kind == "record_design"]
    assert len(designs) == 1, f"edition {revision.id} cites record designs {designs}"
    corpus_path = bundled_path() / sources[designs[0]].corpus_path
    lines = corpus_path.with_name(f"{corpus_path.name}.extracted.md").read_text(encoding="utf-8").splitlines()
    start = lines.index(f"# {_RECORD}")
    boxes: dict[str, str] = {}
    for line in lines[start + 1 :]:
        if line.startswith("# "):
            break
        match = _FIELD_ROW.match(line)
        if match is None:
            continue
        printed = _BOX.findall(match["description"])
        if printed:
            boxes[printed[0]] = match["description"]
    return boxes


def _undeclared_identified_boxes(revision: ModeloRevision) -> list[str]:
    """Return the design's boxes the edition omits, among those whose wording, box number aside, is unique."""
    wording = {box: _BOX.sub("", description).strip() for box, description in _design_boxes(revision).items()}
    repeated = Counter(wording.values())
    declared = {str(casilla.number) for casilla in revision.casillas if casilla.segmento == _RECORD}
    return sorted(box for box, text in wording.items() if repeated[text] == 1 and box not in declared)


@pytest.mark.parametrize("year", _supported_years())
def test_every_identified_liquidacion_iii_box_is_declared(year: int) -> None:
    revision = _edition(year)
    assert _design_boxes(revision), f"{year}: the design edition {revision.id} cites prints no {_RECORD} box"
    assert _undeclared_identified_boxes(revision) == [], f"{year}: edition {revision.id}"


@pytest.mark.parametrize("year", _supported_years())
def test_liquidacion_iii_labels_name_the_period_their_design_names(year: int) -> None:
    revision = _edition(year)
    boxes = _design_boxes(revision)
    checked = 0
    wrong: dict[str, str] = {}
    for casilla in revision.casillas:
        if casilla.segmento != _RECORD:
            continue
        printed = _PERIOD_YEAR.findall(boxes.get(str(casilla.number), ""))
        if not printed:
            continue
        checked += 1
        for locale in _LOCALES:
            label = casilla.get_label(locale)
            if re.findall(r"\b20\d{2}\b", label) != printed:
                wrong[f"{casilla.id}|{locale}"] = label
    assert checked, f"{year}: no declared {_RECORD} box names a periodo impositivo in its design"
    assert wrong == {}, f"{year}: labels name another periodo impositivo than their design: {wrong}"


def test_a_dropped_liquidacion_iii_box_is_reported() -> None:
    revision = _edition(_supported_years()[0])
    declared = [casilla for casilla in revision.casillas if casilla.segmento == _RECORD]
    assert declared, f"edition {revision.id} declares no {_RECORD} box"
    dropped = declared[0]
    reduced = revision.model_copy(update={"casillas": tuple(c for c in revision.casillas if c is not dropped)})
    assert _undeclared_identified_boxes(reduced) == [str(dropped.number)]
