"""Designs scoped on a non-ejercicio axis must stay visibly unattributed, never enumerated.

The relayout module reports every bundled design it cannot attribute to an
ejercicio, and that report is a LEDGER rather than a backlog. Its own reasoning
says so: Modelo 036's designs are scoped by an in-force DATE and Modelo 210's by
a DEVENGO SPAN, so they have real coverage expressed on an axis that is not an
ejercicio, and "enumerating those into years would invent years".

THE HAZARD THIS GUARDS. The report reads like work to be closed, and closing it
is a one-line change: give these designs a year list and the ledger shrinks.
That is precisely the error, because a design attributed to years it never
claimed is compared against designs from those years, and a false comparison
puts a filing year under another year's layout. The near-miss is what makes it
tempting -- an orden-named design plausibly runs from promulgation until
superseded -- and the relayout module records the measurement that refutes it:
``03-180-orden-hap-1732-2014`` states ``Ejercicio 2021``, seven years off.

WHAT IT ASSERTS. Not that these designs are undocumented -- they are documented,
on their own axis, in the source catalogue, and that is asserted too. Only that
nobody has back-filled an ejercicio the design does not state. The two halves
together are the point: real coverage declared where it belongs, and no invented
coverage where it does not.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ._registry_schema_support import _committed_registry_tree
from .test_revision_span_matches_published_designs import (
    _design_coverage_years,
    _design_sources,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: Designs whose coverage AEAT states on an axis that is not an ejercicio, with
#: the axis each one uses. Sourced from the relayout module's own reasoning.
_NON_EJERCICIO_AXIS = {
    "01-036-diseno-de-registro-del-modelo-m036-03-02-2025-y-siguientes-124-kb-xlsx.xlsx": "in-force date",
    "02-036-diseno-de-registro-del-modelo-m036-03-02-2025-y-siguientes-provisional-107-kb-xlsx.xlsx": "in-force date",
    "01-210-devengos-a-partir-de-2026.xlsx": "devengo span",
    "02-210-devengos-entre-01-06-2022-y-01-01-2026.xls": "devengo span",
}


def _registered_designs(catalogues) -> dict[str, str]:
    """Return ``design filename -> source id`` for every registered record design."""
    return {
        str(source.corpus_path).rsplit("/", 1)[-1]: source_id
        for source_id, source in catalogues.sources.items()
        if source.kind == "record_design"
    }


def _paths_by_name() -> dict[str, Path]:
    found: dict[str, Path] = {}
    for modelo_id in ("036", "210"):
        for path in _design_sources(modelo_id):
            found[path.name] = path
    return found


def test_every_design_this_module_names_is_still_bundled() -> None:
    """A renamed or removed file must fail here rather than silently empty the module."""
    present = set(_paths_by_name())

    missing = sorted(set(_NON_EJERCICIO_AXIS) - present)
    assert not missing, f"these designs are no longer bundled under the names this module knows: {missing}"


@pytest.mark.parametrize("name", sorted(_NON_EJERCICIO_AXIS))
def test_no_ejercicio_has_been_back_filled(name: str) -> None:
    """The guard proper: the ledger must not have been shortened by inventing years."""
    path = _paths_by_name()[name]

    years = _design_coverage_years(path)

    assert years == (), (
        f"{name} is scoped by {_NON_EJERCICIO_AXIS[name]}, not by ejercicio, yet it now claims "
        f"coverage of {years}. A design compared against years it never stated puts a filing year "
        "under another year's layout."
    )


def test_a_registered_design_states_its_coverage_on_its_own_axis() -> None:
    """The other half: unattributed-by-ejercicio must not mean undocumented.

    Modelo 210's pair is registered with an explicit epoch, so its coverage IS
    stated -- on the devengo axis AEAT used. Without this, the back-fill guard
    above would also pass on a design nobody had documented at all.
    """
    _modelos, catalogues = _committed_registry_tree()
    registered = _registered_designs(catalogues)

    checked = 0
    for name in sorted(_NON_EJERCICIO_AXIS):
        source_id = registered.get(name)
        if source_id is None:
            continue
        source = catalogues.sources[source_id]
        assert getattr(source, "record_design_epoch", None), (
            f"{name} is registered as {source_id} but declares no record_design_epoch, so its "
            "coverage is stated on no axis at all"
        )
        checked += 1

    assert checked, "none of these designs is registered, so this asserts nothing"


def test_only_the_provisional_design_is_left_unregistered() -> None:
    """Exactly one of these four is not registered as a source, and it is the draft.

    AEAT published Modelo 036's 2025 design twice: a definitive file and a
    PROVISIONAL one alongside it. The definitive design is registered and
    carries its epoch; the provisional is a superseded draft, so it governs no
    window and has nothing to declare. Being bundled without being registered is
    the right outcome for it -- the corpus keeps the draft, the catalogue does
    not claim it applies to anything.

    Pinned as an equality so the set cannot grow silently: a second unregistered
    design would be a new gap wearing this one's explanation.
    """
    _modelos, catalogues = _committed_registry_tree()
    registered = _registered_designs(catalogues)

    unregistered = {name for name in _NON_EJERCICIO_AXIS if name not in registered}

    assert unregistered == {
        "02-036-diseno-de-registro-del-modelo-m036-03-02-2025-y-siguientes-provisional-107-kb-xlsx.xlsx",
    }, sorted(unregistered)


def test_the_bundled_corpus_still_attributes_the_ordinary_designs() -> None:
    """Non-vacuity: attribution works generally, so the empty results above are meaningful."""
    attributed = [
        path.name for modelo_id in ("303", "347") for path in _design_sources(modelo_id) if _design_coverage_years(path)
    ]

    assert attributed, "no design in the sample modelos attributes to any year; attribution has broken"
