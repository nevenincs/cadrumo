"""Standing gate: every bracket table's accumulated cuota matches its own rows.

``resolve_bracket`` computes ``fixed_addition + marginal_rate * (base -
lower_bound)``, so ``fixed_addition`` is the cuota accumulated up to that row's
``lower_bound``. That makes one invariant true of any progressive scale,
independent of this registry and of the formula under test::

    fixed_addition[i] == fixed_addition[i-1] + marginal_rate[i-1] * (lower[i] - lower[i-1])

A row that breaks it changes the tax due, silently. Bracket *structure* is
already defended -- a gap or a closed top raises ``bracket_no_coverage``, and
``test_bracket_window_overlap`` refuses ambiguous validity windows -- but every
one of those failures is loud. The accumulated column had no guard at all, which
is how a scale that over-charges every filer above its top boundary reached HEAD.

Continuity is also what makes bracket selection safe. ``_resolve_bracket_entry``
matches ``lower_bound <= base <= upper_bound`` with both ends inclusive, so at an
exact boundary two rows match and the lower one wins. Where continuity holds both
return the identical value and the tie cannot matter; where it breaks, the
boundary becomes a step.

The comparison allows a two-cent band. Official scales publish the accumulated
column rounded to cents, and rounding each tranche differs from rounding the
total by up to a cent, so exact equality would flag correct tables. The observed
distribution sits far from the band edge: 570 rows exact, 106 within half a cent,
6 at a one-cent convention, and one break two orders of magnitude larger.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from itertools import pairwise

import pytest

from ..authority import bundled_authority
from ..schema_formula import BracketEntry, ParameterDefinition

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: Rounding band. See the module docstring: cents, not a defect budget.
_TOLERANCE = Decimal("0.02")

#: Known breaks, each with the reason it is not fixed here. An entry is a debt,
#: not a dispensation: `test_no_stale_accumulated_cuota_exemptions` fails when a
#: listed row becomes consistent, so a repair cannot leave its entry behind.
_KNOWN_BREAKS: dict[tuple[str, str], str] = {
    ("renta-2022-escala-autonomica-murcia-base-general", "2022"): (
        "Top rung declares fixed_addition 8716.67 where the rows beneath it produce "
        "8625.84, over-charging every filer with base general above 60.000 EUR by "
        "90,83 EUR. Murcia deflated its 2022 scale by 4,1 %: the three lower bounds "
        "are the standard 12.450/20.200/34.000 times exactly 1,041 while the top "
        "bound stayed 60.000, and recomputing the accumulated cuota with the same "
        "rates but the un-deflated bounds reproduces 8716.67 to the cent, so the top "
        "row was carried over from the un-deflated scale. Two repairs are each "
        "self-consistent (fixed_addition to 8625.84, or top bound to 62.460 with the "
        "addition recomputed) and choosing between them is a tax review against the "
        "published 2022 scale for the Region de Murcia, which is not bundled."
    ),
}


def _accumulated_cuota_breaks(parameter: ParameterDefinition) -> list[str]:
    """Report every row whose accumulated cuota disagrees with the rows beneath it.

    Rows are grouped by validity window before comparison: a table carrying one
    tranche set per filing year holds several independent scales, and comparing
    across them would manufacture breaks no taxpayer can reach.
    """
    breaks: list[str] = []
    windows: dict[tuple[object, object], list[BracketEntry]] = {}
    for entry in parameter.brackets or ():
        windows.setdefault((entry.valid_from, entry.valid_to), []).append(entry)

    for entries in windows.values():
        ordered = sorted(entries, key=lambda entry: entry.lower_bound)
        for previous, current in pairwise(ordered):
            expected = previous.fixed_addition + previous.marginal_rate * (current.lower_bound - previous.lower_bound)
            if abs(expected - current.fixed_addition) > _TOLERANCE:
                breaks.append(
                    f"lower_bound={current.lower_bound}: "
                    f"fixed_addition={current.fixed_addition} but the rows beneath produce {expected}"
                )
    return breaks


def _registry_breaks() -> tuple[dict[tuple[str, str], list[str]], int]:
    """Walk every compiled revision's bracket tables, returning breaks and the scan size."""
    found: dict[tuple[str, str], list[str]] = {}
    scanned = 0
    for modelo in bundled_authority().modelos:
        for revision_id, revision in modelo.revisions.items():
            for parameter in getattr(revision, "parameters", ()) or ():
                if not parameter.brackets:
                    continue
                scanned += 1
                breaks = _accumulated_cuota_breaks(parameter)
                if breaks:
                    found[parameter.id, str(revision_id)] = breaks
    return found, scanned


def test_every_bracket_table_accumulated_cuota_is_consistent() -> None:
    """No bracket table may over- or under-state the cuota accumulated beneath a row."""
    breaks, scanned = _registry_breaks()

    # Anti-vacuity: a walk reaching no bracket table would pass while proving
    # nothing. A floor, deliberately not a pinned tally, so new tables never
    # require editing a constant.
    assert scanned >= 100, f"walk reached only {scanned} bracket tables; the gate is not seeing the registry"

    unexpected = {key: value for key, value in breaks.items() if key not in _KNOWN_BREAKS}
    assert not unexpected, "bracket tables whose accumulated cuota contradicts their own rows:\n" + "\n".join(
        f"  {parameter_id} [{revision_id}]\n    " + "\n    ".join(detail)
        for (parameter_id, revision_id), detail in sorted(unexpected.items())
    )


def test_no_stale_accumulated_cuota_exemptions() -> None:
    """A repaired row must not keep its exemption; the entry goes with the fix."""
    breaks, _ = _registry_breaks()
    stale = sorted(key for key in _KNOWN_BREAKS if key not in breaks)

    assert not stale, (
        "these rows are consistent now, so their _KNOWN_BREAKS entries are stale and must be deleted:\n"
        + "\n".join(f"  {parameter_id} [{revision_id}]" for parameter_id, revision_id in stale)
    )


def _scale(top_fixed_addition: str) -> ParameterDefinition:
    """A two-tranche scale whose upper row carries the caller's accumulated cuota."""
    return ParameterDefinition(
        id="test-accumulated-cuota-continuity",
        data_type="bracket_table",
        unit="eur",
        bracket_axis="devengo_date",
        legal_refs=("ley-35-2006:art-63",),
        source_refs=("aeat-renta-2024-manual-parte1",),
        brackets=(
            BracketEntry(
                lower_bound=Decimal("0"),
                upper_bound=Decimal("10000"),
                fixed_addition=Decimal("0"),
                marginal_rate=Decimal("0.10"),
                valid_from=date(2024, 1, 1),
                valid_to=date(2024, 12, 31),
            ),
            BracketEntry(
                lower_bound=Decimal("10000"),
                upper_bound=None,
                fixed_addition=Decimal(top_fixed_addition),
                marginal_rate=Decimal("0.20"),
                valid_from=date(2024, 1, 1),
                valid_to=date(2024, 12, 31),
            ),
        ),
    )


def test_the_gate_detects_a_broken_accumulated_column() -> None:
    """Anti-tautology: 10.000 at 10 % accumulates 1.000, so 1.090 must be reported."""
    breaks = _accumulated_cuota_breaks(_scale("1090"))

    assert len(breaks) == 1
    assert "1000" in breaks[0]


def test_a_consistent_scale_reports_no_break() -> None:
    """Positive control: the check reads arithmetic, not merely the presence of a second row."""
    assert _accumulated_cuota_breaks(_scale("1000")) == []


def test_cent_rounding_is_not_reported_as_a_break() -> None:
    """The band exists because official scales round; it must actually absorb that."""
    assert _accumulated_cuota_breaks(_scale("1000.01")) == []
