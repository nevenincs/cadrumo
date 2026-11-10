"""Temporal coexistence versus bare period-selector overlap.

``revisions_overlap`` answers a selector-only question: do two revisions name
a common filing year and period code. ``revisions_coexist`` adds the half it
omits -- do the revisions' validity windows intersect at all -- and is the
predicate every "are these two editions simultaneous, or is this a temporal
succession" policy needs.

The distinction is not academic. Two successive editions of a census modelo
both serving the period tokens ``alta``/``modificacion``/``baja``, whose
windows meet end-to-start at 2025-02-02/2025-02-03, overlap by selector and
can never be in force at the same instant. Under the selector-only predicate
every continuity chain across such a pair reads as simultaneous, and the
cross-revision checks that only run on a real revision boundary never run at
all.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.modelo_localization import (
    ModeloLocalizationFieldKind,
    casilla_occurrence_locale_key,
)
from cadrumo.domain.calculations.registry.revision_order import (
    revision_windows_intersect,
    revisions_coexist,
    revisions_overlap,
)
from cadrumo.domain.calculations.registry.schema import ModeloRevision
from cadrumo.domain.calculations.registry.schema_references import PeriodSelector
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope

from ..compiler.loader import load_modelo_directory
from ..compiler.validate_cross_revision import declared_cross_revision_continuity_semantic_linkage_failures
from .referential_integrity_support import (
    REFERENCE_LEGAL_ID,
    REFERENCE_SOURCE_ID,
    minimal_application_link,
    minimal_casilla,
    minimal_workbook_ref,
)
from .synthetic_locale_fixtures import (
    synthetic_locale_scope,
    synthetic_locale_state,
    write_test_label,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

__all__ = ["synthetic_locale_scope"]

CENSUS_PERIODS = ("alta", "modificacion", "baja")
# Four consecutive exercises of the support envelope place the synthetic windows.
assert len(filing_year_envelope().years) >= 4, (
    "the support envelope must span at least 4 exercises for these synthetic editions"
)
_A, _B, _C, _D = filing_year_envelope().years[-4:]
# A date later than every exercise the envelope supports.
_BEYOND = filing_year_envelope().horizon + 1
EARLIER_REVISION = f"{_A}-hasta-{_C}-02-02"
LATER_REVISION = f"{_C}-02-03-y-siguientes"


def _revision(
    *,
    revision_id: str,
    valid_from: date,
    valid_to: date | None,
    period_selector: PeriodSelector,
) -> ModeloRevision:
    return ModeloRevision(
        id=revision_id,
        localization_key=f"test.schema.revision.{revision_id}.label",
        valid_from=valid_from,
        valid_to=valid_to,
        period_selector=period_selector,
        legal_refs=(REFERENCE_LEGAL_ID,),
        source_refs=(REFERENCE_SOURCE_ID,),
        orden_aplicabilidad=(REFERENCE_LEGAL_ID,),
        casillas=(minimal_casilla(),),
        workbook_parity_refs=(minimal_workbook_ref(),),
        application_links=(minimal_application_link("filing"),),
    )


class TestRevisionsCoexistPredicate:
    def test_meeting_windows_with_identical_tokens_do_not_coexist(self) -> None:
        """The 036 shape: identical census tokens, windows meeting at 02-02/02-03."""
        earlier = _revision(
            revision_id="test-census-earlier",
            valid_from=date(_A, 1, 1),
            valid_to=date(_C, 2, 2),
            period_selector=PeriodSelector(year_from=_A, year_to=_C, periods=CENSUS_PERIODS),
        )
        later = _revision(
            revision_id="test-census-later",
            valid_from=date(_C, 2, 3),
            valid_to=None,
            period_selector=PeriodSelector(year_from=_C, periods=CENSUS_PERIODS),
        )
        assert revisions_overlap(earlier, later), (
            "the planted selectors no longer share a period token; this gate is vacuous"
        )
        assert not revisions_coexist(earlier, later)

    def test_meeting_windows_with_shared_tokens_do_not_coexist(self) -> None:
        """Consecutive editions sharing their quarter tokens, windows meeting 06-30/07-01."""
        earlier = _revision(
            revision_id="test-quarterly-earlier",
            valid_from=date(_A, 1, 1),
            valid_to=date(_B, 6, 30),
            period_selector=PeriodSelector(year_from=_A, year_to=_B, periods=("1T", "2T", "3T", "4T")),
        )
        later = _revision(
            revision_id="test-quarterly-later",
            valid_from=date(_B, 7, 1),
            valid_to=date(_C, 12, 31),
            period_selector=PeriodSelector(year_from=_B, year_to=_C, periods=("1T", "2T", "3T", "4T")),
        )
        assert revisions_overlap(earlier, later)
        assert not revisions_coexist(earlier, later)

    def test_intersecting_windows_with_shared_tokens_coexist(self) -> None:
        """Variant schemas sharing a window are alternative shapes of one period."""
        left = _revision(
            revision_id="test-variant-a",
            valid_from=date(_B, 1, 1),
            valid_to=date(_B, 12, 31),
            period_selector=PeriodSelector(years=(_B,), periods=CENSUS_PERIODS),
        )
        right = _revision(
            revision_id="test-variant-b",
            valid_from=date(_B, 6, 1),
            valid_to=date(_C, 6, 30),
            period_selector=PeriodSelector(year_from=_B, year_to=_C, periods=CENSUS_PERIODS),
        )
        assert revisions_coexist(left, right)

    def test_single_shared_day_is_an_intersection(self) -> None:
        """Bounds are inclusive on both sides: one shared day is coexistence."""
        left = _revision(
            revision_id="test-touch-a",
            valid_from=date(_B, 1, 1),
            valid_to=date(_B, 6, 30),
            period_selector=PeriodSelector(years=(_B,), periods=CENSUS_PERIODS),
        )
        right = _revision(
            revision_id="test-touch-b",
            valid_from=date(_B, 6, 30),
            valid_to=date(_B, 12, 31),
            period_selector=PeriodSelector(years=(_B,), periods=CENSUS_PERIODS),
        )
        assert revisions_coexist(left, right)

    def test_disjoint_tokens_within_one_year_do_not_coexist(self) -> None:
        """Windows may intersect fully; disjoint period tokens still decide it."""
        left = _revision(
            revision_id="test-disjoint-a",
            valid_from=date(_B, 1, 1),
            valid_to=date(_B, 12, 31),
            period_selector=PeriodSelector(years=(_B,), periods=("alta",)),
        )
        right = _revision(
            revision_id="test-disjoint-b",
            valid_from=date(_B, 1, 1),
            valid_to=date(_B, 12, 31),
            period_selector=PeriodSelector(years=(_B,), periods=("baja",)),
        )
        assert not revisions_overlap(left, right)
        assert not revisions_coexist(left, right)

    def test_open_ended_valid_to_intersects_a_later_window(self) -> None:
        """``valid_to`` of ``None`` is open-ended, not an empty window."""
        open_ended = _revision(
            revision_id="test-open",
            valid_from=date(_A, 1, 1),
            valid_to=None,
            period_selector=PeriodSelector(year_from=_A, periods=CENSUS_PERIODS),
        )
        later = _revision(
            revision_id="test-later",
            valid_from=date(_BEYOND, 1, 1),
            valid_to=date(_BEYOND, 12, 31),
            period_selector=PeriodSelector(years=(_BEYOND,), periods=CENSUS_PERIODS),
        )
        assert revisions_coexist(open_ended, later)

    def test_open_ended_valid_to_does_not_reach_backwards(self) -> None:
        """An open end extends forward only; an earlier closed window is disjoint."""
        earlier = _revision(
            revision_id="test-earlier",
            valid_from=date(_A, 1, 1),
            valid_to=date(_A, 12, 31),
            period_selector=PeriodSelector(year_from=_A, year_to=_BEYOND, periods=CENSUS_PERIODS),
        )
        open_ended = _revision(
            revision_id="test-open",
            valid_from=date(_B, 1, 1),
            valid_to=None,
            period_selector=PeriodSelector(year_from=_B, periods=CENSUS_PERIODS),
        )
        assert revisions_overlap(earlier, open_ended)
        assert not revisions_coexist(earlier, open_ended)

    def test_both_open_ended_windows_always_intersect(self) -> None:
        earlier = _revision(
            revision_id="test-open-a",
            valid_from=date(_A, 1, 1),
            valid_to=None,
            period_selector=PeriodSelector(year_from=_A, periods=CENSUS_PERIODS),
        )
        later = _revision(
            revision_id="test-open-b",
            valid_from=date(_C, 1, 1),
            valid_to=None,
            period_selector=PeriodSelector(year_from=_C, periods=CENSUS_PERIODS),
        )
        assert revisions_coexist(earlier, later)

    def test_coexistence_is_symmetric(self) -> None:
        earlier = _revision(
            revision_id="test-sym-a",
            valid_from=date(_A, 1, 1),
            valid_to=date(_C, 2, 2),
            period_selector=PeriodSelector(year_from=_A, year_to=_C, periods=CENSUS_PERIODS),
        )
        later = _revision(
            revision_id="test-sym-b",
            valid_from=date(_C, 2, 3),
            valid_to=None,
            period_selector=PeriodSelector(year_from=_C, periods=CENSUS_PERIODS),
        )
        assert revisions_coexist(earlier, later) == revisions_coexist(later, earlier)


class TestRevisionWindowsIntersectPredicate:
    """The canonical window predicate, read without the selector half.

    ``revision_windows_intersect`` is the one spelling of "do these two
    revisions' validity windows share a day" that the registry keeps; the
    compiler's ``validate_revision_windows`` guard consumes it rather than
    re-deriving the comparison. These cases pin the two facts that spelling
    turns on -- inclusive bounds, and ``valid_to`` of ``None`` as an open end
    -- independently of any period selector.
    """

    def test_meeting_windows_do_not_intersect_but_overlapping_windows_do(self) -> None:
        """Inclusive bounds: end-to-start is disjoint, a shared day is not."""
        selector = PeriodSelector(year_from=_A, periods=CENSUS_PERIODS)
        earlier = _revision(
            revision_id="test-meet-earlier",
            valid_from=date(_A, 1, 1),
            valid_to=date(_C, 2, 2),
            period_selector=selector,
        )
        meeting_later = _revision(
            revision_id="test-meet-later",
            valid_from=date(_C, 2, 3),
            valid_to=date(_D, 12, 31),
            period_selector=selector,
        )
        assert not revision_windows_intersect(earlier, meeting_later)
        assert not revision_windows_intersect(meeting_later, earlier)

        overlapping_later = _revision(
            revision_id="test-overlap-later",
            valid_from=date(_C, 2, 2),
            valid_to=date(_D, 12, 31),
            period_selector=selector,
        )
        assert revision_windows_intersect(earlier, overlapping_later)
        assert revision_windows_intersect(overlapping_later, earlier)

    def test_open_ended_valid_to_intersects_every_later_window(self) -> None:
        """An open end has no closing date, so nothing starting after it is disjoint."""
        selector = PeriodSelector(year_from=_A, periods=CENSUS_PERIODS)
        open_ended = _revision(
            revision_id="test-intersect-open",
            valid_from=date(_A, 1, 1),
            valid_to=None,
            period_selector=selector,
        )
        for valid_from, valid_to in (
            (date(_A, 1, 1), date(_A, 1, 1)),
            (date(_C, 2, 3), date(_D, 12, 31)),
            (date(_BEYOND, 12, 31), None),
        ):
            later = _revision(
                revision_id="test-intersect-later",
                valid_from=valid_from,
                valid_to=valid_to,
                period_selector=selector,
            )
            assert revision_windows_intersect(open_ended, later)
            assert revision_windows_intersect(later, open_ended)


def _write_census_revision(
    revisions_dir: Path,
    *,
    revision_id: str,
    window: str,
    selector: str,
) -> None:
    """Write one revision directory in the canonical revisions/<id>/ layout."""
    revision_dir = revisions_dir / revision_id
    (revision_dir / "casillas").mkdir(parents=True)
    (revision_dir / "application_links").mkdir(parents=True)
    (revision_dir / "revision.toml").write_text(
        f'''
[revisions."{revision_id}"]
id = "{revision_id}"
casilla_source_refs = ["aeat-manual"]
application_link_source_refs = ["aeat-manual"]
authority_grade = "applicability"
{window}
period_selector = {selector}
orden_aplicabilidad = ["ley-58-2003:art-29"]
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]
'''.lstrip(),
        encoding="utf-8",
    )
    (revision_dir / "casillas" / "cdecl.base__cdecl.base.toml").write_text(
        f'''
[[revisions."{revision_id}".casillas]]
id = "0700"
number = "700"
section = ["test"]
data_type = "money"
continuidad_id = "base"
semantic_role = "base_gate"
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]
'''.lstrip(),
        encoding="utf-8",
    )
    (revision_dir / "application_links" / "0001-application-links.toml").write_text(
        f'''
[[revisions."{revision_id}".application_links]]
id = "modelo-998-filing"
surface = "filing"
consumer = "cadrumo.application.filing"
requires_snapshot = true
legal_refs = ["ley-58-2003:art-29"]
'''.lstrip(),
        encoding="utf-8",
    )


def _write_census_modelo_directory(tmp_path: Path) -> Path:
    """Write a two-edition census modelo whose windows meet end-to-start.

    Both editions serve the identical non-temporal period tokens
    ``alta``/``modificacion``/``baja`` and carry the same continuity chain,
    reproducing the corpus shape that the selector-only predicate misreads.
    """
    target = tmp_path / "998"
    revisions_dir = target / "revisions"
    revisions_dir.mkdir(parents=True)
    (target / "manifest.toml").write_text(
        """
[modelo]
id = "998"
tax_domain = "iva"
cadence = "annual"
jurisdiction = "ES-AEAT"
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]
""".lstrip(),
        encoding="utf-8",
    )
    _write_census_revision(
        revisions_dir,
        revision_id=EARLIER_REVISION,
        window=f"valid_from = {_A}-01-01\nvalid_to = {_C}-02-02",
        selector=f'{{ year_from = {_A}, year_to = {_C}, periods = ["alta", "modificacion", "baja"] }}',
    )
    _write_census_revision(
        revisions_dir,
        revision_id=LATER_REVISION,
        window=f"valid_from = {_C}-02-03",
        selector=f'{{ year_from = {_C}, periods = ["alta", "modificacion", "baja"] }}',
    )
    write_test_label("Census casilla")
    for revision_id in (EARLIER_REVISION, LATER_REVISION):
        key = casilla_occurrence_locale_key("998", revision_id, "0700", ModeloLocalizationFieldKind.LABEL)
        if synthetic_locale_state.root is not None:
            with (synthetic_locale_state.root / "es.yml").open("a", encoding="utf-8") as handle:
                handle.write(f"{json.dumps(key)}: {json.dumps('Census casilla')}\n")
    return target


class TestCrossRevisionBoundaryReachesMeetingEditions:
    def test_meeting_census_editions_cross_a_revision_boundary(self, tmp_path: Path) -> None:
        """A directory-loaded two-edition census modelo has its chain examined.

        The tooth: the same pair is ``revisions_overlap``-true while their
        validity windows do not coexist. The public semantic-linkage audit must
        therefore reach the chain and report its deliberately mismatched role;
        a selector-only short-circuit would return no failure and leave this
        boundary defect invisible.
        """
        modelo = load_modelo_directory(_write_census_modelo_directory(tmp_path))
        earlier = modelo.revisions[EARLIER_REVISION]
        later = modelo.revisions[LATER_REVISION]
        assert revisions_overlap(earlier, later), (
            "the planted editions no longer overlap by selector; the tooth is vacuous"
        )
        assert not revisions_coexist(earlier, later)

        failures = declared_cross_revision_continuity_semantic_linkage_failures((modelo,))
        assert len(failures) == 1
        assert "continuity chain 'base'" in failures[0]
        assert "semantic-role-derived id 'base-gate'" in failures[0]
