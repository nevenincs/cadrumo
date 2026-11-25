"""Every Modelo 200 casilla label names no year its own edition's design does not print.

A box's caption in an AEAT record design can name years: a rotating slot names
the ejercicio or a year counted from it, an absolute cohort names its own
generation year, a provision names the year of its law. The label and help an
edition serves for that box, resolved in every locale through the runtime
resolver, may name only years that edition's own design caption for the box
prints. A label that names another edition's year renders the wrong period, so
a text shared across editions must not name a rotating year at all.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from functools import cache

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.schema import ModeloRevision
from cadrumo.domain.calculations.registry.schema_surfaces import CasillaDefinition

from ..compiler.authority import compiled_bundled_authority
from ..compiler.record_design import extract_record_design
from .authored_edition_support import authored_revisions

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_MODELO = "200"
_LOCALES = ("es", "ca", "en", "hu")
_PRINTED_BOX = re.compile(r"\[([0-9]{3,6})\]")
_NUMBERED = re.compile(r"[0-9]{3,6}")
YEAR = re.compile(r"(?<![0-9])(?:19|20)[0-9]{2}(?![0-9])")

type Captions = dict[tuple[str, str], frozenset[str]]
"""Captions an edition's design prints, keyed by (sheet, number) and by (``""``, number) for any sheet."""


@cache
def design_captions(revision_id: str) -> Captions:
    """Return every caption the record design an edition cites prints, per sheet and per number."""
    revision = compiled_bundled_authority().modelo(_MODELO).revisions[revision_id]
    sources = compiled_bundled_authority().catalogues.sources
    (design,) = [ref for ref in revision.source_refs if sources[ref].kind == "record_design"]
    extraction = extract_record_design(bundled_path() / sources[design].corpus_path)
    captions: dict[tuple[str, str], set[str]] = {}
    for sheet in extraction.require_complete():
        for field in sheet.fields:
            for number in _PRINTED_BOX.findall(field.description):
                captions.setdefault((sheet.name.strip(), number), set()).add(field.description)
                captions.setdefault(("", number), set()).add(field.description)
    return {box: frozenset(texts) for box, texts in captions.items()}


def foreign_years(texts: Iterable[str | None], captions: Iterable[str]) -> list[str]:
    """Return the years the texts name that none of the captions prints."""
    printed = {year for caption in captions for year in YEAR.findall(caption)}
    return sorted({year for text in texts if text is not None for year in YEAR.findall(text)} - printed)


def box_captions(casilla: CasillaDefinition, captions: Captions) -> frozenset[str]:
    """Return the captions of the box a row stands for: its own sheet, or any sheet for an unsheeted row."""
    return captions.get((casilla.segmento or "", str(casilla.number)), frozenset[str]())


def _violations(revision: ModeloRevision) -> list[str]:
    captions = design_captions(str(revision.id))
    found = []
    for casilla in revision.casillas:
        if not _NUMBERED.fullmatch(str(casilla.number)):
            continue
        box = box_captions(casilla, captions)
        for locale in _LOCALES:
            years = foreign_years((casilla.get_label(locale), casilla.get_help(locale)), box)
            if years:
                found.append(f"{casilla.id} {locale} names {years}")
    return found


@pytest.mark.parametrize("revision", authored_revisions(_MODELO), ids=lambda revision: str(revision.id))
def test_every_label_and_help_names_only_years_its_own_design_caption_prints(revision: ModeloRevision) -> None:
    violations = _violations(revision)
    assert violations == [], f"{revision.id}: {len(violations)} texts name another edition's year: {violations[:20]}"


def test_the_check_detects_a_label_naming_another_editions_year() -> None:
    """A real caption with a year passes against itself and fails once its year is moved."""
    revision = authored_revisions(_MODELO)[0]
    captions = design_captions(str(revision.id))
    caption = next(
        text
        for texts in captions.values()
        for text in texts
        if len(set(YEAR.findall(text))) == 1 and str(int(YEAR.findall(text)[0]) + 1) not in text
    )
    (year,) = set(YEAR.findall(caption))
    moved = str(int(year) + 1)
    assert foreign_years([caption], [caption]) == []
    assert foreign_years([caption.replace(year, moved)], [caption]) == [moved]
    assert foreign_years(["N(*) Periodificación"], [caption]) == []
