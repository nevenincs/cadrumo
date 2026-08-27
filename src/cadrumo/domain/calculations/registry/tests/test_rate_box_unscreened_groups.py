"""A rate-split group that forms no partition is reported, not silently dropped.

``derive_rate_box_partitions`` forms a partition only when several conditions hold
together, so a group can vanish from the screened population in six different
ways. ``rate_box_coverage_shortfalls`` then reads only what survived. The result
is that an empty shortfall list has two readings that render identically:
everything was checked and was clean, or **nothing was eligible to be checked**.

``rate_box_unscreened_groups`` separates them, and this module gates that it keeps
separating them.

WHY THE OBVIOUS GUARD IS ITSELF VACUOUS. "Assert the partition set is non-empty
before reporting no shortfalls" is the natural fix and it does not work when
applied globally: derivation runs per revision, so a tree-wide assertion is
satisfied by any modelo that partitions while the modelo carrying the defect
contributes zero and sails through. The assertions here are therefore PER
REVISION -- a revision that declares rate-pinned bindings at all must account for
every one of them, as screened or as explicitly unscreened.

THE SEVERE REASON IS NOT THE ONLY ONE, BUT IT IS THE ONE THAT LOSES MONEY.
``no_rate_blind_sibling`` means every binding for a selector identity pins a rate,
so a row whose rate the ledger never recorded matches none of them and reaches no
casilla at all. The other reasons are shapes the partition arithmetic cannot read
rather than rows going missing.

Real-behaviour: the committed registry through the real authority. No mocks,
stubs, skips or xfail.

Non-tautology: the population is derived from the revision, never enumerated
here, and no count is asserted. The M303 identities below are named because they
were measured independently through the resolver -- a rate-unrecorded reduced row
resolves to no binding at all -- so this module asserts a fact established
elsewhere rather than restating its own derivation.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from ..authority import bundled_authority
from ..binding_selector_utils import selector_as_dict
from ..rate_box_partition import _NO_RATE_BLIND_SIBLING, derive_rate_box_partitions, rate_box_unscreened_groups
from ..schema import ModeloRevision

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_SEVERE = _NO_RATE_BLIND_SIBLING

# Selector identities measured to have lost their rate-blind sibling on Modelo
# 303. Established through the resolver, not through this module's derivation: a
# DOMESTIC_REDUCED repercutido row with applied_rate=None resolves to {}. Named
# by the binding whose rows are stranded, so a rename breaks the test loudly
# rather than making it pass vacuously.
_M303_STRANDED_BINDINGS = (
    "modelo-303-iva-repercutido-reducido-base",
    "modelo-303-iva-repercutido-reducido-cuota",
    "modelo-303-iva-repercutido-super-reducido-base",
    "modelo-303-iva-repercutido-super-reducido-cuota",
)


def _revisions() -> Iterator[tuple[str, str, ModeloRevision]]:
    """Yield the live revision for each modelo this module measures."""
    authority = bundled_authority()
    yield "303", "2025-3T", authority.snapshot("303", filing_year=2025, period="3T").revision
    yield "390", "2024-0A", authority.snapshot("390", filing_year=2024, period="0A").revision


def _rate_pinned_binding_ids(revision: ModeloRevision) -> set[str]:
    return {
        binding.id
        for binding in revision.bindings
        if str(binding.source) == "ledger_iva_aggregation" and selector_as_dict(binding).get("applied_rates")
    }


def test_every_rate_pinned_binding_is_screened_or_explicitly_unscreened() -> None:
    """The invariant, asserted PER REVISION so a partitioning modelo cannot mask another.

    This is the assertion a global "the partition set is non-empty" check only
    appears to make. Every rate-pinned binding a revision declares must be
    accounted for: inside a formed partition, or named in the unscreened residue
    with a reason. A binding in neither is a row nothing looked at.
    """
    seen = False
    for modelo, period, revision in _revisions():
        pinned = _rate_pinned_binding_ids(revision)
        if not pinned:
            continue
        seen = True
        screened = {
            binding.id
            for binding in revision.bindings
            if binding.id in pinned
            and any(
                casilla.id
                in {c for partition in derive_rate_box_partitions(revision) for c in partition.box_casilla_ids}
                for casilla in revision.casillas
                if str(casilla.binding) == binding.id
            )
        }
        unscreened = {
            binding_id for group in rate_box_unscreened_groups(revision) for binding_id in group.rated_binding_ids
        }
        unaccounted = sorted(pinned - screened - unscreened)
        assert not unaccounted, (
            f"M{modelo} {period}: {unaccounted} pin a rate but appear in neither a formed "
            f"partition nor the unscreened residue, so nothing measured them"
        )
    assert seen, "no revision declared a rate-pinned binding; every assertion here would be vacuous"


def test_the_m303_stranded_tiers_are_reported_as_unscreened_and_severe() -> None:
    """The positive control: the measured defect must appear, with the severe reason.

    Modelo 303's reducido and super-reducido tiers were narrowed until every
    binding pinned a rate, leaving no blind sibling. The partition derivation
    drops them, so the shortfall screen never sees them. They must surface here
    instead, and specifically under ``no_rate_blind_sibling`` -- reporting them
    under one of the shapes-it-cannot-read reasons would understate them.
    """
    revision = next(rev for modelo, _, rev in _revisions() if modelo == "303")
    groups = rate_box_unscreened_groups(revision)
    assert groups, "M303 reported no unscreened groups; the control cannot pass vacuously"
    severe = {binding_id for group in groups if group.reason == _SEVERE for binding_id in group.rated_binding_ids}
    missing = sorted(set(_M303_STRANDED_BINDINGS) - severe)
    assert not missing, f"M303: {missing} lost their rate-blind sibling but are not reported as {_SEVERE}"


def test_a_group_with_no_rate_pinned_binding_is_never_reported() -> None:
    """The negative control: ordinary rate-blind bindings must not flood the residue.

    Most ledger-IVA bindings pin no rate and form no partition, correctly. If they
    appeared here the real cases would be buried, and the residue would report a
    number that means nothing. Every reported group must name at least one
    rate-pinned binding.
    """
    for modelo, period, revision in _revisions():
        pinned = _rate_pinned_binding_ids(revision)
        for group in rate_box_unscreened_groups(revision):
            assert set(group.rated_binding_ids) <= pinned, (
                f"M{modelo} {period}: group {group.rated_binding_ids} names a binding that pins no rate"
            )
            assert group.rated_binding_ids, f"M{modelo} {period}: a group was reported with no rate-pinned binding"


def test_screened_and_unscreened_are_disjoint() -> None:
    """The three states must stay three: a binding cannot be both checked and not.

    Without this, a derivation change could report a group as unscreened while its
    boxes still sit inside a formed partition, and the residue count would
    overstate while looking more thorough.
    """
    for modelo, period, revision in _revisions():
        partitions = derive_rate_box_partitions(revision)
        box_casillas = {casilla_id for partition in partitions for casilla_id in partition.box_casilla_ids}
        screened_bindings = {
            str(casilla.binding) for casilla in revision.casillas if casilla.id in box_casillas and casilla.binding
        }
        unscreened = {b for group in rate_box_unscreened_groups(revision) for b in group.rated_binding_ids}
        overlap = sorted(screened_bindings & unscreened)
        assert not overlap, f"M{modelo} {period}: {overlap} are reported as both screened and unscreened"


def test_every_reported_reason_is_a_known_one() -> None:
    """A reason is a branch a caller may act on, so an unknown one is a silent bug.

    Derived from the module's own constants rather than restated, so adding a
    reason without exporting it fails here.
    """
    from .. import rate_box_partition as module

    known = {
        value
        for name, value in vars(module).items()
        if name.isupper() is False and name.startswith("_") and isinstance(value, str) and name.endswith("SIBLING")
    }
    known |= {
        module._NO_RATE_BLIND_SIBLING,
        module._MULTIPLE_RATE_BLIND_SIBLINGS,
        module._NO_SINGLE_TOTAL_CASILLA,
        module._TOTAL_CASILLA_EXPORTS,
        module._NO_BOX_CASILLA_EXPORTS,
        module._NO_RATE_KINDS,
    }
    saw_any = False
    for modelo, period, revision in _revisions():
        for group in rate_box_unscreened_groups(revision):
            saw_any = True
            assert group.reason in known, f"M{modelo} {period}: unknown reason {group.reason!r}"
    assert saw_any, "no unscreened group was reported at all; this assertion would be vacuous"
