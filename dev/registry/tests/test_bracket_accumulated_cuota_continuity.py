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

The gate reads every table the resolver can read: the rows in force on each day
a table changes, whichever edition states them. An edition that inherits a
scale's unchanged lower rungs and keys only its changed upper rungs stores one
table under two first days, so grouping rows by validity window would split it
into halves that are each consistent and never compare the seam between an
inherited rung and a re-keyed one.

The comparison allows a two-cent band. Official scales publish the accumulated
column rounded to cents, and rounding each tranche differs from rounding the
total by up to a cent, so exact equality would flag correct tables. The observed
distribution sits far from the band edge: 570 rows exact, 106 within half a cent,
6 at a one-cent convention, and one break two orders of magnitude larger.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date, timedelta
from decimal import Decimal
from itertools import pairwise

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.schema_formula import BracketEntry, ParameterDefinition
from cadrumo.domain.calculations.registry.tests.authored_editions import manual_editions_printing
from dev.registry.compiler.authority import compiled_bundled_authority

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
_KNOWN_BREAKS: dict[tuple[str, int], str] = {
    ("renta-escala-autonomica-murcia-base-general", 2022): (
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


def _in_force(parameter: ParameterDefinition, on: date) -> tuple[BracketEntry, ...]:
    """The rows the resolver reads on ``on``, ordered by lower bound."""
    rows = (row for row in parameter.brackets if row.valid_from <= on and (row.valid_to is None or on <= row.valid_to))
    return tuple(sorted(rows, key=lambda row: row.lower_bound))


def _in_force_tables(parameter: ParameterDefinition) -> Iterator[tuple[date, date | None, tuple[BracketEntry, ...]]]:
    """Every distinct table in force, with the first and last day it is in force.

    The in-force rows change only on a row's first day or the day after its last
    day, so reading the table on each such day reads every table any date sees.
    """
    changes = sorted(
        {row.valid_from for row in parameter.brackets}
        | {row.valid_to + timedelta(days=1) for row in parameter.brackets if row.valid_to is not None}
    )
    if not changes:
        return
    last_days: tuple[date | None, ...] = (*(change - timedelta(days=1) for change in changes[1:]), None)
    for first_day, last_day in zip(changes, last_days, strict=True):
        if rows := _in_force(parameter, first_day):
            yield first_day, last_day, rows


def _accumulated_cuota_breaks(parameter: ParameterDefinition) -> dict[date, list[str]]:
    """Report, by the first day of the table, every rung whose accumulated cuota disagrees with the rungs beneath.

    Each in-force table is read whole, so rungs keyed from different first days
    are compared across their seam exactly as the resolver reads them together.
    """
    breaks: dict[date, list[str]] = {}
    for first_day, _, rows in _in_force_tables(parameter):
        for previous, current in pairwise(rows):
            expected = previous.fixed_addition + previous.marginal_rate * (current.lower_bound - previous.lower_bound)
            if abs(expected - current.fixed_addition) > _TOLERANCE:
                breaks.setdefault(first_day, []).append(
                    f"lower_bound={current.lower_bound}: "
                    f"fixed_addition={current.fixed_addition} but the rows beneath produce {expected}"
                )
    return breaks


def _registry_breaks() -> tuple[dict[tuple[str, int], list[str]], set[tuple[date, date | None]]]:
    """Walk every in-force table of every compiled edition, returning breaks and the spans the tables are in force.

    A break is keyed by parameter and the year its table enters force; an inherited
    table is read in every edition that carries it but reported once.
    """
    found: dict[tuple[str, int], set[str]] = {}
    spans: set[tuple[date, date | None]] = set()
    for modelo in compiled_bundled_authority().modelos:
        for revision_id, revision in modelo.revisions.items():
            for parameter in revision.parameters:
                spans.update((first_day, last_day) for first_day, last_day, _ in _in_force_tables(parameter))
                for first_day, detail in _accumulated_cuota_breaks(parameter).items():
                    found.setdefault((parameter.id, first_day.year), set()).update(
                        f"[{modelo.id} {revision_id} from {first_day}] {line}" for line in detail
                    )
    return {key: sorted(lines) for key, lines in found.items()}, spans


def test_every_bracket_table_accumulated_cuota_is_consistent() -> None:
    """No bracket table in force on any day may over- or under-state the cuota accumulated beneath a rung."""
    breaks, spans = _registry_breaks()

    # Anti-vacuity: every supported filing year must read at least one in-force
    # table, derived from the support declaration rather than a pinned tally.
    unread = [
        year
        for year in compiled_bundled_authority().supported_filing_years().years
        if not any(
            first_day <= date(year, 12, 31) and (last_day is None or last_day >= date(year, 1, 1))
            for first_day, last_day in spans
        )
    ]
    assert not unread, f"no in-force bracket table read for supported years {unread}"

    unexpected = {key: value for key, value in breaks.items() if key not in _KNOWN_BREAKS}
    assert not unexpected, "bracket tables whose accumulated cuota contradicts their own rows:\n" + "\n".join(
        f"  {parameter_id} [{year}]\n    " + "\n    ".join(detail)
        for (parameter_id, year), detail in sorted(unexpected.items())
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
        + "\n".join(f"  {parameter_id} [{year}]" for parameter_id, year in stale)
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

#: The one bundled AEAT Manual practico de Renta edition that prints the Region de
#: Murcia scale Decreto-ley 4/2022 enacts, with its top-rung cuota and rate.
(_MURCIA_DECRETO_LEY_EXERCISE,) = manual_editions_printing("renta", "Región de Murcia", "8.716,67", "22,70")

#: Cuota integra at 60.000,00 EUR, as enacted by Decreto-ley 4/2022 de la Region
#: de Murcia. See the _KNOWN_BREAKS entry for why it exceeds what the tranches
#: beneath it accumulate.
_MURCIA_DECRETO_LEY_TOP_RUNG_CUOTA = Decimal("8716.67")

#: The same figure in the Spanish decimal notation the AEAT manual prints.
_MURCIA_DECRETO_LEY_TOP_RUNG_CUOTA_AS_PRINTED = "8.716,67"

#: Marginal rate above 60.000,00 EUR: "el tipo del 22,70 %".
_MURCIA_DECRETO_LEY_TOP_RUNG_RATE = Decimal("0.227")


def _murcia_decreto_ley_top_rung() -> BracketEntry:
    """Return the top rung of the Region de Murcia autonomic scale in force in the Decreto-ley's exercise."""
    for modelo in compiled_bundled_authority().modelos:
        for revision_id, revision in modelo.revisions.items():
            if str(revision_id) != str(_MURCIA_DECRETO_LEY_EXERCISE):
                continue
            for parameter in revision.parameters:
                if parameter.id != "renta-escala-autonomica-murcia-base-general":
                    continue
                return _in_force(parameter, date(_MURCIA_DECRETO_LEY_EXERCISE, 12, 31))[-1]
    raise AssertionError(
        f"renta-escala-autonomica-murcia-base-general [{_MURCIA_DECRETO_LEY_EXERCISE}] is not in the registry"
    )


def test_murcia_decreto_ley_top_rung_matches_the_enacted_cuota() -> None:
    """The registry must state the cuota the norm enacts, not the one its tranches imply."""
    top = _murcia_decreto_ley_top_rung()

    assert top.lower_bound == Decimal("60000.00")
    assert top.fixed_addition == _MURCIA_DECRETO_LEY_TOP_RUNG_CUOTA
    assert top.marginal_rate == _MURCIA_DECRETO_LEY_TOP_RUNG_RATE


def test_murcia_decreto_ley_top_rung_cuota_is_printed_in_the_bundled_aeat_manual() -> None:
    """Anchor the pin: the figure must be readable in the bundled source, not merely asserted.

    The AEAT Manual practico Renta for that exercise reproduces the Region de Murcia scale and
    its closing sentence at page 979. Without this half, the test above is a
    literal a future author can edit to match a wrong registry change.
    """
    manual = (
        bundled_path("corpus", "manuals", "renta", str(_MURCIA_DECRETO_LEY_EXERCISE), "part1")
        / "source.pdf.extracted.md"
    )
    body = manual.read_text(encoding="utf-8")

    assert _MURCIA_DECRETO_LEY_TOP_RUNG_CUOTA_AS_PRINTED in body
    assert "Región de Murcia" in body
    assert "22,70" in body


def _rung(
    lower: str, upper: str | None, fixed: str, rate: str, valid_from: date, valid_to: date | None = None
) -> BracketEntry:
    return BracketEntry(
        lower_bound=Decimal(lower),
        upper_bound=None if upper is None else Decimal(upper),
        fixed_addition=Decimal(fixed),
        marginal_rate=Decimal(rate),
        valid_from=valid_from,
        valid_to=valid_to,
    )


def _table(*rungs: BracketEntry) -> ParameterDefinition:
    return ParameterDefinition(
        id="test-accumulated-cuota-continuity",
        data_type="bracket_table",
        unit="eur",
        bracket_axis="devengo_date",
        legal_refs=("ley-35-2006:art-63",),
        source_refs=("aeat-renta-2024-manual-parte1",),
        brackets=rungs,
    )


_YEAR_START = date(2024, 1, 1)
_YEAR_END = date(2024, 12, 31)


def _scale(top_fixed_addition: str) -> ParameterDefinition:
    """A two-tranche scale whose upper row carries the caller's accumulated cuota."""
    return _table(
        _rung("0", "10000", "0", "0.10", _YEAR_START, _YEAR_END),
        _rung("10000", None, top_fixed_addition, "0.20", _YEAR_START, _YEAR_END),
    )


def test_the_gate_detects_a_broken_accumulated_column() -> None:
    """Anti-tautology: 10.000 at 10 % accumulates 1.000, so 1.090 must be reported."""
    breaks = _accumulated_cuota_breaks(_scale("1090"))

    assert list(breaks) == [_YEAR_START]
    assert len(breaks[_YEAR_START]) == 1
    assert "1000" in breaks[_YEAR_START][0]


def test_a_consistent_scale_reports_no_break() -> None:
    """Positive control: the check reads arithmetic, not merely the presence of a second row."""
    assert _accumulated_cuota_breaks(_scale("1000")) == {}


def test_cent_rounding_is_not_reported_as_a_break() -> None:
    """The band exists because official scales round; it must actually absorb that."""
    assert _accumulated_cuota_breaks(_scale("1000.01")) == {}


def _inherited_lower_rung_scale(rekeyed_fixed_addition: str) -> ParameterDefinition:
    """A scale whose lower rung stays open from one year and whose upper rung is re-keyed the next.

    The lower rung is stated once and inherited; the upper rung closes at the first
    year's end and a later edition keys its replacement from the next day, carrying
    the caller's accumulated cuota. No two rungs share a validity window.
    """
    next_year = _YEAR_END + timedelta(days=1)
    return _table(
        _rung("0", "10000", "0", "0.10", _YEAR_START),
        _rung("10000", None, "1000", "0.20", _YEAR_START, _YEAR_END),
        _rung("10000", None, rekeyed_fixed_addition, "0.25", next_year),
    )


def test_a_broken_seam_between_an_inherited_and_a_rekeyed_rung_is_detected() -> None:
    """The seam is read in the table in force from the re-key, not only within one validity window."""
    next_year = _YEAR_END + timedelta(days=1)
    breaks = _accumulated_cuota_breaks(_inherited_lower_rung_scale("1100"))

    assert list(breaks) == [next_year]
    assert "1000" in breaks[next_year][0]
    assert _accumulated_cuota_breaks(_inherited_lower_rung_scale("1000")) == {}


def test_each_in_force_table_is_read_once_with_its_span() -> None:
    """The first year's table and the re-keyed table are both read, each with the days it is in force."""
    next_year = _YEAR_END + timedelta(days=1)
    tables = [
        (first_day, last_day, tuple(rung.fixed_addition for rung in rows))
        for first_day, last_day, rows in _in_force_tables(_inherited_lower_rung_scale("1000"))
    ]

    assert tables == [
        (_YEAR_START, _YEAR_END, (Decimal("0"), Decimal("1000"))),
        (next_year, None, (Decimal("0"), Decimal("1000"))),
    ]
