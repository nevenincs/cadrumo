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

from .....core.resources import bundled_path
from ..authority import bundled_authority
from ..schema_formula import BracketEntry, ParameterDefinition

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: Rounding band. See the module docstring: cents, not a defect budget.
_TOLERANCE = Decimal("0.02")

#: Rows whose accumulated column contradicts their own tranches, each with the
#: reason. Entries fall into two kinds and the difference decides what to do:
#:
#: - a DEBT, where the registry misstates a consistent published scale. Repair
#:   it, then delete the entry.
#: - FAITHFUL TO SOURCE, where the published norm is itself discontinuous and
#:   the registry transcribes it correctly. Never repair it; the entry is
#:   permanent, because "fixing" it would make the engine disagree with the law.
#:
#: `test_no_stale_accumulated_cuota_exemptions` fails when a listed row becomes
#: consistent, so a repair cannot leave its entry behind. Note what that means
#: for a faithful-to-source row: editing its value to satisfy the arithmetic
#: SILENCES this gate and trips the staleness check instead, whose message then
#: reads as an instruction to delete the entry. Do not follow it. Establish the
#: figure against the cited authority before touching any row listed here.
_KNOWN_BREAKS: dict[tuple[str, str], str] = {
    ("renta-2022-escala-autonomica-murcia-base-general", "2022"): (
        "FAITHFUL TO SOURCE -- do not repair. The discontinuity is in the norm, not "
        "in this table. Decreto-ley 4/2022 de la Region de Murcia, de 22 de "
        "septiembre (BORM 29-09-2022, art. unico, amending DA quinta.4 del Decreto "
        "Legislativo 1/2010), states verbatim: 'Cuando la base liquidable sea "
        "superior a 60.000,00 euros la cuota integra sera de 8.716,67 euros mas la "
        "cantidad resultante de aplicar el tipo del 22,70 % a la parte de base "
        "liquidable que exceda de 60.000 euros.' The AEAT Manual practico Renta 2022 "
        "reproduces that sentence and the four tranches above it verbatim at page "
        "979, bundled at corpus/manuals/renta/2022/part1/source.pdf -- 8.716,67 is "
        "present there and 8.625,84 occurs nowhere in the corpus tree. Murcia "
        "deflated the bounds and rates by 4,1 % (12.450/20.200/34.000 times exactly "
        "1,041) and carried the un-deflated accumulated cuota into the closing "
        "sentence, so the published scale implies 8.625,84 at 60.000 while stating "
        "8.716,67. Both figures are the legislator's; only 8.716,67 is enacted, and "
        "it is what AEAT applies. Encoding the arithmetic instead would compute a "
        "cuota no authority states."
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
        "these rows are consistent now, so their _KNOWN_BREAKS entries look stale.\n"
        "Read the entry before deleting it: for a DEBT that is the right move, but a row marked\n"
        "FAITHFUL TO SOURCE became consistent only because someone changed a value the published\n"
        "norm states, and the fix is to restore the value, not to remove the record of why:\n"
        + "\n".join(f"  {parameter_id} [{revision_id}]" for parameter_id, revision_id in stale)
    )


# ---------------------------------------------------------------------------
# Region de Murcia 2022 -- the enacted top-rung cuota, pinned to its source.
#
# The continuity gate above cannot defend this value: editing it to satisfy the
# arithmetic makes the table self-consistent and turns that gate GREEN. These
# two tests are what stands between a plausible "repair" and a cuota no
# authority states. The corpus half is the load-bearing one -- a bare literal
# is something a future author edits to match a wrong change, while a phrase
# that must appear in the bundled AEAT manual cannot be satisfied that way.
# ---------------------------------------------------------------------------

#: Cuota integra at 60.000,00 EUR, as enacted by Decreto-ley 4/2022 de la Region
#: de Murcia. See the _KNOWN_BREAKS entry for why it exceeds what the tranches
#: beneath it accumulate.
_MURCIA_2022_TOP_RUNG_CUOTA = Decimal("8716.67")

#: The same figure in the Spanish decimal notation the AEAT manual prints.
_MURCIA_2022_TOP_RUNG_CUOTA_AS_PRINTED = "8.716,67"

#: Marginal rate above 60.000,00 EUR: "el tipo del 22,70 %".
_MURCIA_2022_TOP_RUNG_RATE = Decimal("0.227")


def _murcia_2022_top_rung() -> BracketEntry:
    """Return the open top bracket of the Region de Murcia 2022 autonomic scale."""
    for modelo in bundled_authority().modelos:
        for revision_id, revision in modelo.revisions.items():
            if str(revision_id) != "2022":
                continue
            for parameter in getattr(revision, "parameters", ()) or ():
                if parameter.id != "renta-2022-escala-autonomica-murcia-base-general":
                    continue
                top = max(parameter.brackets or (), key=lambda entry: entry.lower_bound)
                return top
    raise AssertionError("renta-2022-escala-autonomica-murcia-base-general [2022] is not in the registry")


def test_murcia_2022_top_rung_matches_the_enacted_cuota() -> None:
    """The registry must state the cuota the norm enacts, not the one its tranches imply."""
    top = _murcia_2022_top_rung()

    assert top.lower_bound == Decimal("60000.00")
    assert top.fixed_addition == _MURCIA_2022_TOP_RUNG_CUOTA
    assert top.marginal_rate == _MURCIA_2022_TOP_RUNG_RATE


def test_murcia_2022_top_rung_cuota_is_printed_in_the_bundled_aeat_manual() -> None:
    """Anchor the pin: the figure must be readable in the bundled source, not merely asserted.

    The AEAT Manual practico Renta 2022 reproduces the Region de Murcia scale and
    its closing sentence at page 979. Without this half, the test above is a
    literal a future author can edit to match a wrong registry change.
    """
    manual = bundled_path("corpus", "manuals", "renta", "2022", "part1") / "source.pdf.extracted.md"
    body = manual.read_text(encoding="utf-8")

    assert _MURCIA_2022_TOP_RUNG_CUOTA_AS_PRINTED in body
    assert "Región de Murcia" in body
    assert "22,70" in body


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
