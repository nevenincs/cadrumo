"""A Modelo 200 rotating-slot label renders the year its own edition's design prints.

A rotating slot is a box whose caption names a year counted back from the
ejercicio, so each record design prints the box with the year moved on: the
2022 design prints a deduction slot as "2017", the 2023 design as "2018". The
registry declares the slot's offset once, and the label carries a ``{year}``
placeholder that the resolver renders as the ejercicio minus that offset. These
tests render every slot's label and help in every locale for the ejercicio each
edition's own design serves, and compare the year with the design caption.
"""

from __future__ import annotations

import pytest

from cadrumo.domain.calculations.registry.schema import ModeloRevision

from .authored_edition_support import authored_revisions
from .test_modelo_200_labels_name_only_their_own_design_years import (
    YEAR,
    box_captions,
    design_captions,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_MODELO = "200"
_LOCALES = ("es", "ca", "en", "hu")


def _rotating_violations(revision: ModeloRevision) -> tuple[int, list[str]]:
    captions = design_captions(str(revision.id))
    ejercicio = revision.valid_from.year
    slots = 0
    found = []
    for casilla in revision.casillas:
        offset = casilla.rotating_year_offset
        if offset is None:
            continue
        slots += 1
        year = str(ejercicio - offset)
        printed = {
            printed_year for caption in box_captions(casilla, captions) for printed_year in YEAR.findall(caption)
        }
        if year not in printed:
            found.append(f"{casilla.id}: offset {offset} gives {year}, the design prints {sorted(printed)}")
            continue
        for locale in _LOCALES:
            label = casilla.get_label(locale, ejercicio=ejercicio)
            if year not in YEAR.findall(label) or "{" in label:
                found.append(f"{casilla.id} {locale} label {label!r} does not name {year}")
            help_text = casilla.get_help(locale, ejercicio=ejercicio)
            if help_text is not None and "{" in help_text:
                found.append(f"{casilla.id} {locale} help keeps a placeholder: {help_text!r}")
    return slots, found


@pytest.mark.parametrize("revision", authored_revisions(_MODELO), ids=lambda revision: str(revision.id))
def test_every_rotating_slot_label_names_the_year_its_own_design_prints(revision: ModeloRevision) -> None:
    slots, violations = _rotating_violations(revision)
    assert slots, f"{revision.id} declares no rotating slot, so this check proves nothing"
    assert violations == [], f"{revision.id}: {len(violations)} rotating slots: {violations[:20]}"


@pytest.mark.parametrize("revision", authored_revisions(_MODELO), ids=lambda revision: str(revision.id))
def test_a_label_placeholder_belongs_only_to_a_rotating_slot(revision: ModeloRevision) -> None:
    """A ``{year}`` the resolver has no offset for would reach an operator unrendered."""
    stray = [
        f"{casilla.id} {locale}"
        for casilla in revision.casillas
        if casilla.rotating_year_offset is None
        for locale in _LOCALES
        if "{year}" in casilla.get_label(locale) or "{year}" in (casilla.get_help(locale) or "")
    ]
    assert stray == []


def test_a_slot_rendered_without_an_ejercicio_names_its_offset_not_a_year() -> None:
    """With no ejercicio to count from, the label says how far back the year lies."""
    revision = authored_revisions(_MODELO)[0]
    slot = next(
        casilla
        for casilla in revision.casillas
        if casilla.rotating_year_offset is not None and casilla.rotating_year_offset > 0
    )
    label = slot.get_label("es")
    assert f"N-{slot.rotating_year_offset}" in label
    assert "{year}" not in label
