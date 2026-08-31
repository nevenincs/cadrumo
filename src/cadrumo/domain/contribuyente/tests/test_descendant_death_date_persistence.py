"""Persistence boundary for the ``death_date`` fact, with its anti-tautology proof.

``death_date`` changes a PERSISTED shape, so it needs the roundtrip discipline
the project applies to every such boundary: a save → load → strict-equality cycle
through the real writer and reader with every defaultable field populated
NON-default, and a proof that the cycle would notice if the field stopped
surviving it.

The non-default population is the load-bearing part. A fixture that leaves
``death_date`` at its ``None`` default would pass identically whether the writer
emits the fact or drops it on the floor, which is exactly the
save-drops-field / load-re-defaults-field regression this shape is exposed to.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ....core.descendant_relacion import DescendantRelacion
from ..descendant import DescendantInfo
from ..descendant_facts import (
    descendant_facts_from_list,
    descendant_list_from_facts,
    parse_descendiente_flag,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_DEATH_FACT_PATH = "renta_family.descendiente.0.fallecimiento"


def _fully_populated() -> DescendantInfo:
    """A descendant with every defaultable field set AWAY from its default.

    Deliberately maximal rather than minimal: a roundtrip fixture that accepts
    defaults cannot distinguish a field that survived the cycle from one that
    was dropped and re-defaulted on load.
    """
    return DescendantInfo(
        birth_date=date(2012, 3, 4),
        relacion=DescendantRelacion.ADOPTADO,
        inscripcion_registro_civil_date=date(2013, 5, 6),
        acogimiento_resolucion_date=date(2012, 9, 9),
        death_date=date(2024, 7, 8),
        discapacidad_grado=65,
        convive_con_contribuyente=False,
        dependencia_economica=True,
        custodia_compartida=True,
        rentas_anuales_euros=Decimal("1234.56"),
        presenta_declaracion_propia=True,
        prorrata_minimo=True,
        meses_madre_trabajo=(4, 5, 6, 7, 8, 9, 10),
        alta_posterior_nacimiento_mes=4,
        gastos_guarderia_euros=900,
        nif="12345678Z",
    )


def test_fully_populated_descendant_survives_the_fact_roundtrip() -> None:
    """Save → facts → load → strict equality, every field non-default."""
    original = (_fully_populated(),)
    reloaded = descendant_list_from_facts(dict(descendant_facts_from_list(original)))
    assert reloaded == original


def test_death_date_is_actually_written_as_a_fact() -> None:
    """The writer emits the death fact, and it carries the ISO date.

    Asserted directly on the fact map rather than only through the roundtrip,
    so a writer/reader pair that agreed on the WRONG key would still be caught
    here — two halves of one module can be consistently wrong and a pure
    roundtrip cannot see it.
    """
    facts = dict(descendant_facts_from_list((_fully_populated(),)))
    assert facts[_DEATH_FACT_PATH] == "2024-07-08"


def test_anti_tautology_deleting_the_persisted_death_date_surfaces_inequality() -> None:
    """Mutate the stored payload: drop the death fact, and the reload must differ.

    The proof that the roundtrip above is not vacuous. If this ever passes with
    the boundary broken — that is, if deleting the persisted fact still yields an
    equal record — then the roundtrip is asserting nothing about ``death_date``
    and every other assertion in this module is decoration.

    Inequality rather than a refusal is the correct contract here: an absent
    death fact is a MEANINGFUL state (the descendant did not die), so the reader
    must read it as ``None`` rather than raise. What must not happen is the two
    states being indistinguishable.
    """
    original = _fully_populated()
    facts = dict(descendant_facts_from_list((original,)))
    assert _DEATH_FACT_PATH in facts

    del facts[_DEATH_FACT_PATH]
    reloaded = descendant_list_from_facts(facts)

    assert len(reloaded) == 1
    assert reloaded[0] != original
    assert reloaded[0].death_date is None
    assert reloaded[0].model_copy(update={"death_date": original.death_date}) == original


def test_anti_tautology_corrupting_the_persisted_death_date_is_refused() -> None:
    """A stored value that is not a date refuses rather than silently resolving to None.

    A silent fallback here would point the wrong way: it would erase a declared
    death, restoring the deceased to the birth-order ordering and over-granting
    every younger sibling — the precise defect Art. 61 norma 4ª's second limb
    exists to prevent.
    """
    facts = dict(descendant_facts_from_list((_fully_populated(),)))
    facts[_DEATH_FACT_PATH] = "not-a-date"
    with pytest.raises(ValueError, match="not-a-date"):
        descendant_list_from_facts(facts)


def test_absent_death_date_roundtrips_as_absent() -> None:
    """The ordinary case emits no fact at all, and reloads as ``None``.

    Guards the writer's drop-default rule in the other direction: emitting an
    empty death fact for every living descendant would make every existing
    profile look re-declared.
    """
    original = (DescendantInfo(birth_date=date(2012, 3, 4)),)
    facts = dict(descendant_facts_from_list(original))
    assert _DEATH_FACT_PATH not in facts
    assert descendant_list_from_facts(facts) == original


def test_entry_surface_ships_with_the_field() -> None:
    """The ``--descendiente`` flag can express the fact the record now carries.

    A persisted field with no writer is a dead shape. This asserts the entry
    door exists and lands the value on the canonical record, so the field cannot
    ship write-only.
    """
    parsed = parse_descendiente_flag("NACIMIENTO=2012-03-04,FALLECIMIENTO=2024-07-08")
    assert parsed.death_date == date(2024, 7, 8)


def test_entry_surface_refuses_a_death_before_the_birth() -> None:
    """The flag door inherits the record's ordering refusal rather than bypassing it."""
    with pytest.raises(ValueError, match="precedes birth_date"):
        parse_descendiente_flag("NACIMIENTO=2012-03-04,FALLECIMIENTO=2010-01-01")
