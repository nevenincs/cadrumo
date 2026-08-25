"""Standing breadth gate: the bindings architecture holds across every modelo.

The bindings-architecture mandate requires that a ``bound`` casilla be resolved
by exactly one canonical mechanism *across every modelo*, "with zero dangling
binds and zero dormant resolvers". A one-off breadth audit proved that invariant
held at HEAD (zero dangling/dormant across the full registry). This gate converts
that single proof into a permanent ``proven-by-gates`` invariant: it walks every
modelo code in the bundled :class:`~cadrumo.domain.calculations.registry.ModeloRevision`
tree, loads each revision's validated :class:`RegistrySnapshot`, and refuses two
fragmentation classes the mandate forbids:

* a ``BOUND`` casilla whose ``binding`` id resolves to no binding in its revision
  (a *dangling bind*), and
* a binding whose ``source`` carries no canonical
  :class:`~cadrumo.application.aggregation.BindingSourceDisposition`
  (ENROLLED / DEFERRED / RESERVED) — a *novel / dormant source*.

A future modelo authored with a dangling bind or an undispositioned source — the
exact drift the breadth audit closed — fails here loudly instead of silently
blanking a casilla on the live calculate path.
"""

from __future__ import annotations

from typing import TypedDict

import pytest

from .....application.aggregation import (
    BindingSourceDisposition,
    build_binding_source_dispositions,
)

# The live enrolled-source set is the single authoritative declaration in
# `_calculation_source_policy` (the union of every active resolver's owned_sources,
# the pre-mesh tiers, and `manual_input`). It is consumed read-only here; the gate
# asserts disposition coverage, not enrollment membership, so it tracks the live
# truth without re-declaring it.
# The policy module made this name public; the underscore form it was imported
# under no longer exists, which stopped this module COLLECTING at all -- a
# gate running zero assertions rather than failing loudly.
from .....application.modelo.calculation_route import CALCULATION_ROUTE_ENROLLED_SOURCES
from .....core import BindingSourceKind
from .. import InputKind, PeriodSelector
from ..authority import bundled_authority

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


class _ScanResult(TypedDict):
    modelos_scanned: set[str]
    revisions_scanned: int
    bound_casillas_scanned: int
    bindings_scanned: int
    dangling_binds: list[str]
    undispositioned_sources: list[str]
    disposition_states: set[BindingSourceDisposition]


def _representative_scope(period_selector: PeriodSelector) -> tuple[int, str]:
    """Return one ``(filing_year, period)`` that the revision's selector covers.

    A revision declares its applicable years as either an explicit ``years``
    tuple or a ``year_from``/``year_to`` window plus a non-empty ``periods``
    tuple. The first declared year and first declared period is a scope the
    selector covers by construction, so the validated snapshot builds for it.
    """
    year = period_selector.years[0] if period_selector.years else period_selector.year_from
    assert year is not None
    return int(year), period_selector.periods[0]


def _scan() -> _ScanResult:
    """Walk every modelo × revision and collect breadth facts and violations.

    Returns a record carrying the traversal counts (for the anti-tautology
    guard) and the two violation lists (dangling binds, undispositioned
    sources). The disposition map is built once from the live enrolled set; a
    source kind absent from it is a novel/dormant source.
    """
    authority = bundled_authority()
    dispositions = build_binding_source_dispositions(CALCULATION_ROUTE_ENROLLED_SOURCES)

    modelos_scanned: set[str] = set()
    revisions_scanned = 0
    bound_casillas_scanned = 0
    bindings_scanned = 0
    dangling_binds: list[str] = []
    undispositioned_sources: list[str] = []

    for modelo in authority.modelos:
        modelos_scanned.add(str(modelo.id))
        for revision_id in modelo.revisions:
            # Resolve through the validated-authority snapshot boundary so the
            # gate exercises the same compiled revision the runtime consumes.
            scope_year, scope_period = _representative_scope(
                modelo.revisions[revision_id].period_selector,
            )
            snapshot = authority.snapshot(
                str(modelo.id),
                filing_year=scope_year,
                period=scope_period,
                # Ask for the rung the revision itself declares. The bindings
                # architecture is asserted at every rung, so a breadth walk
                # demanding FILING of an APPLICABILITY revision -- modelo 036's
                # censal alta/modificacion/baja, filed on AEAT's sede -- refuses
                # the build and takes the whole scan down with it, scanning
                # nothing rather than scanning that revision's bindings.
                grade=modelo.revisions[revision_id].effective_authority_grade,
            )
            revision = snapshot.revision
            revisions_scanned += 1

            binding_ids = {binding.id for binding in revision.bindings}
            bindings_scanned += len(revision.bindings)

            for casilla in revision.casillas:
                if casilla.input_kind is not InputKind.BOUND:
                    continue
                bound_casillas_scanned += 1
                if casilla.binding not in binding_ids:
                    dangling_binds.append(
                        f"{modelo.id}/{revision_id}/{casilla.id} -> {casilla.binding!r}",
                    )
                for binding_id in casilla.alternate_bindings:
                    if binding_id not in binding_ids:
                        dangling_binds.append(
                            f"{modelo.id}/{revision_id}/{casilla.id}.alternate_bindings -> {binding_id!r}",
                        )

            for binding in revision.bindings:
                source = binding.source
                if not isinstance(source, BindingSourceKind) or source not in dispositions:
                    undispositioned_sources.append(
                        f"{modelo.id}/{revision_id}/{binding.id} -> source {source!r}",
                    )

    return {
        "modelos_scanned": modelos_scanned,
        "revisions_scanned": revisions_scanned,
        "bound_casillas_scanned": bound_casillas_scanned,
        "bindings_scanned": bindings_scanned,
        "dangling_binds": dangling_binds,
        "undispositioned_sources": undispositioned_sources,
        "disposition_states": {disposition for disposition in dispositions.values()},
    }


def test_every_bound_casilla_resolves_to_an_existing_binding() -> None:
    """Zero dangling binds: every ``BOUND`` casilla names a binding that exists.

    For every modelo code × every revision, a casilla whose ``input_kind`` is
    ``BOUND`` MUST name a ``binding`` id present in that revision's bindings
    collection. A dangling bind would resolve to nothing on the calculate path
    and silently blank the casilla — the fragmentation this gate refuses.
    """
    scan = _scan()
    dangling = scan["dangling_binds"]
    assert not dangling, (
        "dangling BOUND-casilla binds detected — a bound casilla names a binding "
        "absent from its revision (silent-blank on calculate):\n" + "\n".join(f"  {entry}" for entry in dangling)
    )


def test_every_binding_source_has_a_canonical_disposition() -> None:
    """Zero novel/dormant sources: every binding source is dispositioned.

    For every binding across every revision, its ``source`` MUST be a
    :class:`~cadrumo.core.BindingSourceKind` member that maps to a canonical
    :class:`~cadrumo.application.aggregation.BindingSourceDisposition`
    (ENROLLED / DEFERRED / RESERVED). A source kind outside that union is a
    novel/dormant source that would resolve to no mechanism on the live mesh.
    """
    scan = _scan()
    undispositioned = scan["undispositioned_sources"]
    assert not undispositioned, (
        "undispositioned binding sources detected — a binding declares a source "
        "with no ENROLLED/DEFERRED/RESERVED disposition (novel/dormant source):\n"
        + "\n".join(f"  {entry}" for entry in undispositioned)
    )
    # The disposition taxonomy itself must remain the three-state closed set the
    # mandate names; a regression that drops a state would weaken the union above.
    assert scan["disposition_states"] <= {
        BindingSourceDisposition.ENROLLED,
        BindingSourceDisposition.DEFERRED,
        BindingSourceDisposition.RESERVED,
    }


def test_breadth_scan_is_not_vacuous() -> None:
    """Anti-tautology guard: the scan traversed a meaningful registry surface.

    If a refactor re-rooted the authority or short-circuited the traversal, both
    gates above would pass vacuously. This asserts the scan actually visited the
    breadth the mandate covers (the audit confirmed ~30 modelos / ~46 revisions /
    150+ bound casillas at HEAD), so the gate cannot pass by scanning nothing.
    """
    scan = _scan()
    assert len(scan["modelos_scanned"]) >= 15, (
        f"expected >=15 modelos with at least one revision; scanned "
        f"{len(scan['modelos_scanned'])} — the authority may be mis-rooted"
    )
    assert scan["revisions_scanned"] >= 15, f"expected >=15 revisions traversed; scanned {scan['revisions_scanned']}"
    assert scan["bound_casillas_scanned"] >= 50, (
        f"expected >=50 BOUND casillas across all modelos; scanned "
        f"{scan['bound_casillas_scanned']} — the bound-casilla surface vanished"
    )
    assert scan["bindings_scanned"] >= 50, (
        f"expected >=50 bindings across all modelos; scanned {scan['bindings_scanned']} — the binding surface vanished"
    )
