"""Tests for revision-span filing coverage and declaration evidence."""

from __future__ import annotations

from itertools import combinations
from pathlib import Path

import pytest

from .....core.directory_scan import DirectoryEntryKind, scan_directory
from .....core.resources.bundled_data import bundled_path
from .....tests.registry_tree import bundled_registry_tree
from ._revision_span_coverage_support import (
    _covers_year,
    _current_filing_year,
    _earliest_declared_year,
    _offset_annual_modelo,
    _period_overlap,
)
from ._revision_span_declaration_support import (
    _NON_EJERCICIO_COVERAGE_AXIS,
    _OPEN_BOUNDED_ERA_DESIGNS,
)
from ._revision_span_design_support import (
    _DESIGN_ROOT_PARTS,
    _design_coverage_years,
    _design_sources,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_every_modelo_resolves_exactly_one_revision_for_every_filing_year_through_today() -> None:
    """HARD FAIL: a coverage HOLE or OVERLAP in filing-year resolution, tree-wide.

    Complements, and does not replace, the relayout-crossing gate above. That
    gate asks whether a declared span is too WIDE -- crossing a design boundary
    inside years it already claims. This one asks the orthogonal question: is a
    span too NARROW, does a gap sit BETWEEN two declared spans, or is the most
    recent span CLOSED past the point it should still be open? None of those
    three shapes is visible to boundary-diffing, because boundary-diffing only
    ever compares years a span already claims -- it cannot see a year no span
    claims at all.

    Modelo 390 is why a PAIRWISE abutment check would have been wrong here.
    Measured 2026-08-14 via the raw loader (``bundled_authority()`` itself
    refuses to build, over an unrelated export-layout-completeness gate, so
    this reads the same tier the relayout gate does), every revision is
    closed-ended --

        2022 | valid_from 2022-01-01 | valid_to 2022-12-31
        2023 | valid_from 2023-01-01 | valid_to 2023-12-31
        2024 | valid_from 2024-01-01 | valid_to 2024-12-31
        2025 | valid_from 2025-01-01 | valid_to 2025-12-31

    The revisions abut each other with no gap BETWEEN them, so a check that
    only compares consecutive revisions to EACH OTHER would call this clean
    and never notice the TAIL -- whether the last revision still reaches the
    present. This check does reach the tail: it sweeps every year through
    today. But "today" is not the same question for every modelo, which is
    the second thing this check gets right.

    THE HORIZON IS OFFSET-AWARE, NOT A FLAT "THROUGH TODAY" FOR EVERY MODELO.
    Operator directive, verbatim in substance: an annual return is filed IN
    ARREARS -- ejercicio 2025's Renta is filed in 2026, ejercicio 2026's is
    not filed until 2027 -- while a periodic modelo (quarterly, monthly)
    files WITHIN its own ejercicio. A flat "must resolve through this
    calendar year" horizon is wrong for the first shape: it would demand a
    2026 revision for Modelo 390 (the annual IVA summary) today, when AEAT's
    own filing window for ejercicio 2026 does not open until 2027 and no
    operator could file it even if the revision existed. :func:`_offset_annual_modelo`
    derives which shape a modelo is from its ALREADY-DECLARED period cadence
    -- no new field, an arithmetic ceiling instead of a stored exemption --
    and the sweep's upper bound becomes last year for an arrears modelo,
    this year for a periodic one. Measured 2026-08-14: modelos 100, 189,
    280, 289, 345, 390 and 714 are ALL annual-in-arrears (confirmed against
    their own declared ``deadline_windows``, not assumed), so none of their
    "missing 2026" cases were live gaps -- every one was premature, and the
    gate now correctly does not ask the question until the year the filing
    window could actually open. No periodic modelo carries a coverage hole
    at all; if one ever does, it is live TODAY, not next year, and this
    gate's horizon does not soften that case.

    PASS requires, per modelo, for every filing year from its earliest declared
    coverage (:func:`_earliest_declared_year`) through its own horizon
    (:func:`_current_filing_year`, offset back one year by
    :func:`_offset_annual_modelo`): at least one revision resolves
    (:func:`_covers_year`), and no two resolving revisions genuinely COLLIDE.
    Zero resolving revisions is a HOLE -- this application cannot even attempt
    the calculation for that year. A collision is an OVERLAP -- two revisions
    both claim the SAME period token (or one restricts nothing at all) inside
    that year, so which applies is undefined.

    OVERLAP IS PERIOD-TOKEN AWARE, NOT A BARE "MORE THAN ONE REVISION" COUNT
    (:func:`_period_overlap`), because more than one revision legitimately
    resolving a single year is a real, correct shape here -- AEAT splits some
    modelos mid-year by PERIOD (Modelo 303's 2024) and runs others as parallel
    REGIME tracks that share no period vocabulary at all (Modelo 369's three
    'esquema' revisions). A bare per-year count flags both as false positives;
    checking whether the resolving revisions' period tokens actually intersect
    does not.

    Checked against TODAY, never against the bundled corpus's own design years.
    There does not need to be a published AEAT record design for 2026 for a
    2026 coverage hole to be real -- resolving a revision at all is a
    law-determined prerequisite to attempting the calculation, per
    ``aeat-registry-authority-flow``'s revision-resolution mandate, and is
    upstream of whether a design exists to export it against.

    NO ALLOWLIST. NO PER-MODELO EXEMPTION. The offset horizon is the ONLY
    per-modelo variation this check makes, and it is computed fresh every run
    from the modelo's own declared period cadence -- never a stored flag, a
    disposition, or a list of modelo ids to skip. A closed-ended tail reads
    as tidy, deliberate structure right up until the calendar passes it,
    which is exactly why a static snapshot of this check would rot: it would
    go green the day it is authored and silently start lying every January
    after -- and an arrears modelo's horizon rolls forward with it the SAME
    way, computed from ``date.today()`` on every run, never pinned.

    Measured at authoring time (2026-08-14): PASSES. Zero holes, zero
    overlaps, tree-wide. This is not a weakened result -- the seven prior
    "holes" were re-classified, not deleted: their offset status is verified
    against real declared ``deadline_windows`` data, not asserted, and every
    one of them still resolves its own current-arrears year (2025). No
    periodic modelo has ever failed this check.
    """
    modelos, _catalogues = bundled_registry_tree()
    today_year = _current_filing_year()

    holes: list[str] = []
    overlaps: list[str] = []
    for modelo in modelos:
        revisions = list(modelo.revisions.items())
        earliest = _earliest_declared_year(revisions)
        if earliest is None:
            continue
        # An annual-in-arrears modelo's most recent FILEABLE ejercicio is last
        # year, not this one -- its filing window for this year's ejercicio has
        # not opened yet, arithmetic derived from the declared period cadence
        # (see :func:`_offset_annual_modelo`), never a stored exemption.
        horizon = today_year - 1 if _offset_annual_modelo(revisions) else today_year
        for year in range(earliest, horizon + 1):
            covering = [(rid, rev) for rid, rev in revisions if _covers_year(rev, year)]
            if not covering:
                holes.append(f"modelo {modelo.id}: no revision resolves filing year {year}")
                continue
            for (id_a, rev_a), (id_b, rev_b) in combinations(covering, 2):
                collision = _period_overlap(id_a, rev_a.period_selector.periods, id_b, rev_b.period_selector.periods)
                if collision:
                    overlaps.append(f"modelo {modelo.id} filing year {year}: {collision}")

    assert not holes and not overlaps, (
        "every modelo must resolve EXACTLY ONE revision for every filing year from its earliest "
        "declared coverage through today -- a hole means this application cannot even attempt the "
        "calculation for that year at all; an overlap means two revisions both claim it with no "
        "tie-break. Neither shape is visible to the relayout-crossing gate above, which only "
        "compares years a span already claims.\n"
        "HOLES -- no revision covers this year, most often a closed-ended tail the calendar has now "
        "passed:\n  " + "\n  ".join(sorted(holes)) + "\n"
        "OVERLAPS -- two or more revisions both claim this year:\n  " + "\n  ".join(sorted(overlaps))
    )


def test_every_non_ejercicio_declaration_is_still_earned() -> None:
    """Each declared non-ejercicio design must still exist AND still state no ejercicio.

    Two ways an entry goes stale, and both must fail rather than pass quietly. The
    design can be renamed or dropped from the corpus, leaving an entry that excuses
    nothing. Or the design can BECOME attributable -- a better title read, a widened
    filename pattern -- at which point the entry silently suppresses a design the
    module can now measure, which is precisely the invisibility the assertion above
    was written against.

    Keyed by ``(modelo, filename)`` so a rename fails loudly instead of drifting onto
    whatever file happens to sit at some position.
    """
    design_root = bundled_path(*_DESIGN_ROOT_PARTS)
    on_disk: dict[tuple[str, str], Path] = {}
    for directory in scan_directory(design_root, pattern="modelo_*", select=DirectoryEntryKind.DIRECTORIES):
        modelo_id = directory.name.removeprefix("modelo_")
        for path in _design_sources(modelo_id):
            on_disk[(modelo_id, path.name)] = path

    assert _NON_EJERCICIO_COVERAGE_AXIS, "the declaration is empty; this audit would be vacuous"

    missing = sorted(key for key in _NON_EJERCICIO_COVERAGE_AXIS if key not in on_disk)
    assert not missing, (
        "these designs are declared non-ejercicio-scoped but are no longer bundled under that "
        f"name, so the declaration excuses nothing: {missing}"
    )

    now_attributable = sorted(key for key in _NON_EJERCICIO_COVERAGE_AXIS if _design_coverage_years(on_disk[key]))
    assert not now_attributable, (
        "these designs now yield ejercicio coverage, so the declaration is suppressing a design "
        f"the module can measure -- remove the entry: {now_attributable}"
    )

    unreasoned = sorted(k for k, why in _NON_EJERCICIO_COVERAGE_AXIS.items() if len(why.strip()) < 30)
    assert not unreasoned, f"every entry must state the axis the file itself uses: {unreasoned}"


def test_every_open_bounded_era_declaration_is_still_earned() -> None:
    """Each open-bounded design must still exist AND still yield no year list.

    The same two staleness directions the non-ejercicio audit checks, for the same
    reason: an entry naming a design the corpus no longer holds excuses nothing, and
    an entry whose design BECAME enumerable is suppressing a design this module can
    now measure. Kept separate from that audit rather than folded into it, because
    the two declarations answer different questions and a single audit would let an
    entry drift between them unnoticed.
    """
    design_root = bundled_path(*_DESIGN_ROOT_PARTS)
    on_disk: dict[tuple[str, str], Path] = {}
    for directory in scan_directory(design_root, pattern="modelo_*", select=DirectoryEntryKind.DIRECTORIES):
        modelo_id = directory.name.removeprefix("modelo_")
        for path in _design_sources(modelo_id):
            on_disk[(modelo_id, path.name)] = path

    assert _OPEN_BOUNDED_ERA_DESIGNS, "the declaration is empty; this audit would be vacuous"

    overlap = sorted(set(_OPEN_BOUNDED_ERA_DESIGNS) & set(_NON_EJERCICIO_COVERAGE_AXIS))
    assert not overlap, f"these designs are declared under BOTH classifications, so one of them is wrong: {overlap}"

    missing = sorted(key for key in _OPEN_BOUNDED_ERA_DESIGNS if key not in on_disk)
    assert not missing, (
        "these designs are declared as open-bounded but are no longer bundled under that name, "
        f"so the declaration excuses nothing: {missing}"
    )

    now_attributable = sorted(key for key in _OPEN_BOUNDED_ERA_DESIGNS if _design_coverage_years(on_disk[key]))
    assert not now_attributable, (
        "these designs now yield ejercicio coverage, so the declaration is suppressing a design "
        f"the module can measure -- remove the entry: {now_attributable}"
    )
