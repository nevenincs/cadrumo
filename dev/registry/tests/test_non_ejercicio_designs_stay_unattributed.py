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
from ._revision_span_design_support import _design_coverage_years, _design_sources

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

    The demand falls on the designs the registry may actually SELECT, and
    selection needs an ``applies_from``: a record design with no window start is
    never resolved for a filing coordinate, so it states no coverage because it
    governs none. A superseded draft is exactly that -- its bytes are pinned as
    evidence and the catalogue withholds any claim that it applies to anything.
    Each half is asserted in its own direction, so neither reading can be
    reached by leaving a field blank.
    """
    _modelos, catalogues = _committed_registry_tree()
    registered = _registered_designs(catalogues)

    selectable = 0
    pinned = 0
    for name in sorted(_NON_EJERCICIO_AXIS):
        source_id = registered.get(name)
        if source_id is None:
            continue
        source = catalogues.sources[source_id]
        if source.applies_from is None:
            assert source.record_design_epoch is None, (
                f"{name} is registered as {source_id} with no applies_from, so nothing can select "
                f"it, yet it declares the epoch {source.record_design_epoch!r}"
            )
            pinned += 1
            continue
        assert source.record_design_epoch, (
            f"{name} is registered as {source_id} but declares no record_design_epoch, so its "
            "coverage is stated on no axis at all"
        )
        selectable += 1

    assert selectable, "no selectable design among these is registered, so this asserts nothing"
    assert pinned, "no pinned-evidence design among these is registered, so its half asserts nothing"


def test_only_the_provisional_design_is_pinned_rather_than_selectable() -> None:
    """Exactly one of these four governs nothing, and it is the draft.

    AEAT published Modelo 036's 2025 design twice: a definitive file and a
    PROVISIONAL one alongside it. The definitive design carries its epoch and its
    window; the provisional is a superseded draft, so it governs neither. It is
    still registered, because the corpus holds its bytes and a registration is
    what hash-pins them -- what the catalogue withholds is the claim that it
    applies to anything, and the absent ``applies_from`` is that withholding:
    record-design selection needs a window start, so a row without one is
    evidence the catalogue holds and never resolves.

    Pinned as an equality so the set cannot grow silently: a second design
    demoted out of selection would be a new gap wearing this one's explanation.
    """
    _modelos, catalogues = _committed_registry_tree()
    registered = _registered_designs(catalogues)

    assert not set(_NON_EJERCICIO_AXIS) - set(registered), (
        f"these designs are bundled but registered by no source, so nothing hash-pins them: "
        f"{sorted(set(_NON_EJERCICIO_AXIS) - set(registered))}"
    )
    pinned = {
        name
        for name, source_id in registered.items()
        if name in _NON_EJERCICIO_AXIS and catalogues.sources[source_id].applies_from is None
    }

    assert pinned == {
        "02-036-diseno-de-registro-del-modelo-m036-03-02-2025-y-siguientes-provisional-107-kb-xlsx.xlsx",
    }, sorted(pinned)


def test_the_bundled_corpus_still_attributes_the_ordinary_designs() -> None:
    """Non-vacuity: attribution works generally, so the empty results above are meaningful."""
    attributed = [
        path.name for modelo_id in ("303", "347") for path in _design_sources(modelo_id) if _design_coverage_years(path)
    ]

    assert attributed, "no design in the sample modelos attributes to any year; attribution has broken"
