"""Focused unit tests for the temporal-revision-selection helper.

`select_revision` funnels every snapshot resolution. It has three
failure modes (no-match, ambiguous-selection, mismatching revision_id)
and four filter modes (filing_year, period, on= date window, and
revision_id). Indirect coverage exists through the snapshot suite,
but the committed registry is designed without overlapping revisions
so the `ambiguous revision selection` branch is never exercised in
the registry-load tests. A regression in the dedup check would
otherwise land silently.
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest

from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.domain.calculations.registry.errors import (
    AmbiguousRevisionSelectionError,
    FilingYearOutsideSupportEnvelopeError,
    NoRevisionForPeriodError,
    RegistrySnapshotError,
)
from cadrumo.domain.calculations.registry.relations import relation_source_requirements
from cadrumo.domain.calculations.registry.revision_contracts import NoPredecessor
from cadrumo.domain.calculations.registry.schema import ModeloDefinition
from cadrumo.domain.calculations.registry.schema_deadlines import DeadlineWindowDefinition
from cadrumo.domain.calculations.registry.schema_references import TemporalProjectionDirection
from cadrumo.domain.calculations.registry.snapshot_globals import SupportedFilingYearsCatalogue
from cadrumo.domain.calculations.registry.temporal import (
    ModeloRevisionDirectory,
    revision_temporal_resolution,
    select_authored_revision_metadata,
    select_revision,
    select_revision_for_year,
    select_revision_metadata,
    select_revision_metadata_for_year,
)
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope, split_exercise_revisions
from dev.registry.compiler.loader import load_modelo_directory

from ..compiler.validate_revision_rules import validate_revision_windows
from ..conformance.registry_schema_support import (
    committed_modelo,
    committed_registry_tree,
    committed_snapshot,
)
from .authored_edition_support import (
    authored_revisions,
    newest_authored_edition,
    oldest_authored_edition,
    revision_covering,
)
from .profile_schema_support import committed_supported_filing_years

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _committed_modelo_100() -> ModeloDefinition:
    return load_modelo_directory(
        Path(__file__).parents[3] / "src" / "cadrumo" / "_data" / "registry" / "aeat" / "modelos" / "100"
    )


def _m100_ids() -> tuple[str, ...]:
    """The authored modelo 100 revision ids, oldest first."""
    return tuple(str(revision.id) for revision in authored_revisions("100"))


def _newest_year() -> int:
    return newest_authored_edition("100")


def _oldest_year() -> int:
    return oldest_authored_edition("100")


def _year_of(revision_id: str) -> int:
    return next(revision.valid_from.year for revision in authored_revisions("100") if str(revision.id) == revision_id)


def test_select_revision_returns_the_matching_year_revision() -> None:
    modelo = _committed_modelo_100()
    year = _newest_year()

    revision = select_revision(modelo, filing_year=year, period="0A")

    assert revision.id == str(revision_covering("100", year).id)


def _support() -> SupportedFilingYearsCatalogue:
    """An envelope whose floor sits just above the oldest authored edition and whose horizon is one past the newest."""
    return SupportedFilingYearsCatalogue(floor=_oldest_year() + 1, horizon=_newest_year() + 1)


def test_nearest_authored_projection_works_backward_forward_and_across_gaps() -> None:
    modelo = _committed_modelo_100()
    ids = _m100_ids()
    newest = ids[-1]
    only_newest = modelo.model_copy(update={"revisions": {newest: modelo.revisions[newest]}})
    support = _support()
    assert select_revision(only_newest, filing_year=support.floor, period="0A", support=support).id == newest
    assert select_revision(only_newest, filing_year=support.horizon, period="0A", support=support).id == newest

    removed = set(ids[-3:-1])
    gap = modelo.model_copy(
        update={"revisions": {key: value for key, value in modelo.revisions.items() if key not in removed}}
    )
    assert select_revision(gap, filing_year=_year_of(ids[-2]), period="0A", support=support).id == newest


def test_supported_request_can_project_from_an_authored_anchor_before_the_global_floor() -> None:
    modelo = _committed_modelo_100()
    oldest = _m100_ids()[0]
    historical = modelo.model_copy(update={"revisions": {oldest: modelo.revisions[oldest]}})
    support = _support()
    assert _oldest_year() < support.floor

    assert select_revision(historical, filing_year=support.floor, period="0A", support=support).id == oldest


def test_equal_distance_projection_uses_the_earlier_authored_anchor() -> None:
    modelo = _committed_modelo_100()
    ids = _m100_ids()
    earlier, between, later = ids[-3], ids[-2], ids[-1]
    gap = modelo.model_copy(update={"revisions": {key: modelo.revisions[key] for key in (earlier, later)}})

    selected = select_revision(gap, filing_year=_year_of(between), period="0A", support=_support())

    assert selected.id == earlier


def test_projection_obeys_global_boundaries_and_reports_actual_no_source() -> None:
    """The two gates and the authoring gap are separately typed refusals.

    Below the floor and above a hard ceiling the ENVELOPE refused; inside the
    envelope with an undeclared period the CORPUS has nothing. They are not the
    same fact and no longer share an error type.
    """
    modelo = _committed_modelo_100()
    support = _support()

    assert (
        select_revision(modelo, filing_year=support.floor, period="0A", support=support).id
        == revision_covering("100", support.floor).id
    )
    assert select_revision(modelo, filing_year=support.horizon, period="0A", support=support).id == _m100_ids()[-1]
    with pytest.raises(FilingYearOutsideSupportEnvelopeError):
        select_revision(modelo, filing_year=support.floor - 1, period="0A", support=support)
    assert select_revision(modelo, filing_year=support.horizon + 1, period="0A", support=support).id == _m100_ids()[-1]
    closed = support.model_copy(update={"hard_ceiling": support.horizon})
    with pytest.raises(FilingYearOutsideSupportEnvelopeError):
        select_revision(modelo, filing_year=closed.horizon + 1, period="0A", support=closed)
    with pytest.raises(NoRevisionForPeriodError):
        select_revision(modelo, filing_year=support.floor, period="3T", support=support)


def test_an_envelope_refusal_names_the_envelope_and_the_revisions_that_do_cover_it() -> None:
    """The committed floor sits above modelo 100's oldest authored ejercicio.

    That coordinate IS authored, so the old shared refusal said "no revision for
    year=2020" while listing 2020 among the revisions the modelo declares -- its
    own evidence contradicting its own claim, and the single most expensive
    triage trap in this resolver. The refusal now states the cause it actually
    had, so a reader is sent to the envelope rather than to the corpus.
    """
    modelo = _committed_modelo_100()
    support = _support()
    oldest = _m100_ids()[0]
    oldest_year = _oldest_year()
    assert modelo.revisions[oldest].period_selector.includes_year(oldest_year)

    with pytest.raises(FilingYearOutsideSupportEnvelopeError) as excinfo:
        select_revision(modelo, filing_year=oldest_year, period="0A", support=support)

    err = excinfo.value
    assert isinstance(err, RegistrySnapshotError)
    # Not a NoRevisionForPeriodError: a handler meaning "nothing was authored"
    # must not absorb an envelope refusal, which is why it is a sibling type.
    assert not isinstance(err, NoRevisionForPeriodError)
    assert err.modelo_id == "100"
    assert err.filing_year == oldest_year
    assert err.period == "0A"
    assert err.floor == support.floor
    assert err.horizon == support.horizon
    assert err.hard_ceiling is None
    assert oldest in err.covering_revision_ids
    assert "outside the registry support envelope" in str(err)


def test_every_envelope_gated_selector_refuses_with_the_envelope_error() -> None:
    """One gate, so all four envelope-taking selectors report one cause."""
    modelo = _committed_modelo_100()
    support = _support()
    directory = ModeloRevisionDirectory.from_modelo(modelo, support=support)
    below = _oldest_year()

    with pytest.raises(FilingYearOutsideSupportEnvelopeError):
        select_revision(modelo, filing_year=below, period="0A", support=support)
    with pytest.raises(FilingYearOutsideSupportEnvelopeError):
        select_revision_for_year(modelo, filing_year=below, support=support)
    with pytest.raises(FilingYearOutsideSupportEnvelopeError):
        select_revision_metadata(directory, filing_year=below, period="0A")
    with pytest.raises(FilingYearOutsideSupportEnvelopeError) as excinfo:
        select_revision_metadata_for_year(directory, filing_year=below)

    # The year-only selectors name the coordinate they were actually given.
    assert excinfo.value.period == "year"


def test_resolving_outside_the_filing_envelope_stays_available_to_its_owners() -> None:
    """The gate refuses a FILING request, never a reading of authored history.

    Both escapes from the envelope keep working: the selector that deliberately
    takes no envelope, and a caller resolving against an authority whose
    envelope reaches the authored history. Without them the new refusal would
    have turned a diagnosis into a dead end.
    """
    modelo = _committed_modelo_100()
    directory = ModeloRevisionDirectory.from_modelo(modelo, support=_support())
    oldest, oldest_year = _m100_ids()[0], _oldest_year()

    assert select_revision(modelo, filing_year=oldest_year, period="0A", support=None).id == oldest
    assert select_authored_revision_metadata(directory, filing_year=oldest_year, period="0A").id == oldest
    reaching = _support().model_copy(update={"floor": oldest_year})
    assert select_revision(modelo, filing_year=oldest_year, period="0A", support=reaching).id == oldest


def test_technical_root_does_not_disable_projection_or_invent_continuity() -> None:
    modelo = _committed_modelo_100()
    newest = _m100_ids()[-1]
    authored = modelo.revisions[newest]
    source = authored.model_copy(
        update={
            "predecessor": NoPredecessor(
                reason="technical converter refusal",
                legal_refs=authored.legal_refs[:1],
                source_refs=authored.source_refs[:1],
            )
        }
    )
    isolated = modelo.model_copy(update={"revisions": {newest: source}})
    support = _support()

    projected = select_revision(isolated, filing_year=support.horizon, period="0A", support=support)

    assert projected is source
    assert projected.model_dump() == source.model_dump()
    assert (projected.review_status, projected.reviewed_by, projected.reviewed_at, projected.reviewed_against) == (
        source.review_status,
        source.reviewed_by,
        source.reviewed_at,
        source.reviewed_against,
    )


def test_source_and_indexed_directory_select_the_same_authored_anchor() -> None:
    modelo = _committed_modelo_100()
    support = _support()
    directory = ModeloRevisionDirectory.from_modelo(modelo, support=support)

    source = select_revision(modelo, filing_year=support.horizon, period="0A", support=support)
    indexed = select_revision_metadata(directory, filing_year=support.horizon, period="0A")

    assert indexed.id == source.id == _m100_ids()[-1]


def test_resolution_exposes_requested_identity_and_authored_provenance() -> None:
    support = _support()
    revision = select_revision(_committed_modelo_100(), filing_year=support.horizon, period="0A", support=support)
    resolution = revision_temporal_resolution(
        revision,
        filing_year=support.horizon,
        period="0A",
        support=support,
    )

    assert resolution.requested_filing_year == support.horizon
    assert resolution.revision.id == _m100_ids()[-1]
    assert resolution.authored_filing_year == _newest_year()
    assert resolution.projection_direction is TemporalProjectionDirection.FORWARD


def test_snapshot_normalises_a_case_variant_period_to_the_declared_token() -> None:
    """A valid lower-case token must not survive into the snapshot verbatim.

    ``select_revision`` matches selectors case-insensitively and returns the
    caller's token unchanged, so the snapshot boundary is where the canonical
    form is resolved. Without it the snapshot disagreed with itself: its
    ``filing_period`` normalised through ``Period`` while ``period`` did not.
    """
    year = _newest_year()
    snapshot = committed_snapshot("100", year, "0a", grade=RegistryAuthorityGrade.CALCULATION)

    assert snapshot.period == "0A"
    assert snapshot.filing_period is not None
    assert snapshot.filing_period.code == snapshot.period
    assert (
        snapshot.revision.id
        == committed_snapshot("100", year, "0A", grade=RegistryAuthorityGrade.CALCULATION).revision.id
    )


def test_case_variant_periods_activate_the_same_relation_requirements() -> None:
    """Relation activation is exact-membership, so case must not silence it.

    A lower-case ``0a`` selected the same M100 revision as ``0A`` while
    activating none of its relation declarations -- the caller got a successful
    snapshot and a clean-looking empty obligation set instead of the required
    cross-model inputs.
    """
    year = _newest_year()
    canonical = committed_snapshot("100", year, "0A", grade=RegistryAuthorityGrade.CALCULATION)
    variant = committed_snapshot("100", year, "0a", grade=RegistryAuthorityGrade.CALCULATION)

    canonical_requirements = relation_source_requirements(
        canonical.revision,
        filing_year=year,
        period=canonical.period,
    )
    variant_requirements = relation_source_requirements(
        variant.revision,
        filing_year=year,
        period=variant.period,
    )

    assert canonical_requirements, "the M100 2025 revision must declare relation requirements"
    assert variant_requirements == canonical_requirements


def test_case_variant_period_still_refuses_an_undeclared_token() -> None:
    """Normalisation must not widen the accepted set beyond declared periods."""
    modelo = _committed_modelo_100()

    with pytest.raises(RegistrySnapshotError, match="no revision for"):
        select_revision(modelo, filing_year=_newest_year(), period="0b")


def test_select_revision_raises_when_no_revision_matches_year() -> None:
    modelo = _committed_modelo_100()

    with pytest.raises(RegistrySnapshotError, match="no revision for"):
        select_revision(modelo, filing_year=filing_year_envelope().horizon + 1, period="0A")


def test_select_revision_raises_when_period_not_declared_by_selector() -> None:
    """Renta is annual-only — period='0A' is the lone declared period."""
    modelo = _committed_modelo_100()

    with pytest.raises(RegistrySnapshotError, match="no revision for"):
        select_revision(modelo, filing_year=_newest_year(), period="3T")


def test_select_revision_honours_explicit_revision_id_filter() -> None:
    modelo = _committed_modelo_100()

    revision_id = _m100_ids()[-2]

    revision = select_revision(modelo, filing_year=_year_of(revision_id), period="0A", revision_id=revision_id)

    assert revision.id == revision_id


def test_select_revision_rejects_mismatching_revision_id_filter() -> None:
    modelo = _committed_modelo_100()

    with pytest.raises(RegistrySnapshotError, match="no revision for"):
        select_revision(modelo, filing_year=_year_of(_m100_ids()[-2]), period="0A", revision_id="not-a-real-id")


def test_select_revision_filters_by_on_date_outside_validity_window() -> None:
    """An on= date well before every revision's valid_from must surface
    as no-revision, not silently pick the closest revision."""
    modelo = _committed_modelo_100()

    with pytest.raises(RegistrySnapshotError, match="no revision for"):
        select_revision(modelo, filing_year=_newest_year(), period="0A", on=date(1900, 1, 1))


def test_select_revision_raises_on_ambiguous_selection() -> None:
    """The dedup check fires when two revisions both match the
    requested year + period (+ optional on= window). Forge a twin
    revision so the candidates list grows past length 1."""
    modelo = _committed_modelo_100()
    original = modelo.revisions[_m100_ids()[-1]]
    twin = original.model_copy(update={"id": f"{original.id}-twin"})
    mutated = modelo.model_copy(update={"revisions": {**modelo.revisions, twin.id: twin}})

    with pytest.raises(RegistrySnapshotError, match="ambiguous revision selection"):
        select_revision(mutated, filing_year=_newest_year(), period="0A")


def test_no_revision_raises_typed_subclass_with_structured_natural_key() -> None:
    """The no-candidate branch raises the typed subclass carrying the
    natural key as structured fields, not only inside the message.

    A consumer dispatches by ``except NoRevisionForPeriodError`` and reads
    ``modelo_id`` / ``filing_year`` / ``period`` / ``revision_id`` from the
    typed fields. The subclass is still catchable as the parent type, so
    every existing ``except RegistrySnapshotError`` site keeps working."""
    modelo = _committed_modelo_100()
    unauthored = _newest_year() + 1

    with pytest.raises(NoRevisionForPeriodError) as excinfo:
        select_revision(modelo, filing_year=unauthored, period="0A", revision_id="r9")

    err = excinfo.value
    assert isinstance(err, RegistrySnapshotError)
    assert err.modelo_id == "100"
    assert err.filing_year == unauthored
    assert err.period == "0A"
    assert err.revision_id == "r9"


def test_an_absent_horizon_edition_projects_the_nearest_authored_revision() -> None:
    """The absent horizon edition projects from the newest authored one instead of becoming a support gap.

    Modelo 100 authors no edition for the horizon year: AEAT has not released that
    Renta form, so the year is answered from the newest edition it has.
    """
    support = committed_supported_filing_years()
    newest_authored = newest_authored_edition("100")
    assert newest_authored < support.horizon
    revision = select_revision(_committed_modelo_100(), filing_year=support.horizon, period="0A", support=support)
    resolution = revision_temporal_resolution(
        revision,
        filing_year=support.horizon,
        period="0A",
        support=support,
    )

    assert resolution.revision.id == str(newest_authored)
    assert resolution.requested_filing_year == support.horizon
    assert resolution.authored_filing_year == newest_authored
    assert resolution.projection_direction is TemporalProjectionDirection.FORWARD


def test_ambiguous_selection_raises_typed_subclass_with_candidate_ids() -> None:
    """The dedup branch raises the typed subclass carrying the candidate
    revision ids as a structured, sorted tuple — independent of the
    human-readable message wording (the whole point of the refactor).

    Designed so a rewording of the ``str()`` message would not change the
    assertion: the candidate ids are read from ``candidate_ids``, never
    parsed out of the message."""
    modelo = _committed_modelo_100()
    original = modelo.revisions[_m100_ids()[-1]]
    twin = original.model_copy(update={"id": f"{original.id}-twin"})
    mutated = modelo.model_copy(update={"revisions": {**modelo.revisions, twin.id: twin}})

    with pytest.raises(AmbiguousRevisionSelectionError) as excinfo:
        select_revision(mutated, filing_year=_newest_year(), period="0A")

    err = excinfo.value
    assert isinstance(err, RegistrySnapshotError)
    assert err.modelo_id == "100"
    # Sorted tuple of every matching revision id, read from the typed field.
    assert err.candidate_ids == (original.id, twin.id)


def test_revision_validation_reports_non_adjacent_overlap_before_runtime_ambiguity() -> None:
    """A long revision cannot hide its overlap behind a shorter middle revision."""

    modelo = _committed_modelo_100()
    template = modelo.revisions[_m100_ids()[-1]]
    year = _newest_year()
    revision_a = template.model_copy(
        update={"id": "window-a", "valid_from": date(year - 5, 1, 1), "valid_to": date(year + 5, 12, 31)},
    )
    revision_b = template.model_copy(
        update={"id": "window-b", "valid_from": date(year - 4, 1, 1), "valid_to": date(year - 3, 12, 31)},
    )
    revision_c = template.model_copy(
        update={"id": "window-c", "valid_from": date(year, 1, 1), "valid_to": date(year + 1, 12, 31)},
    )
    mutated = modelo.model_copy(
        update={"revisions": {revision.id: revision for revision in (revision_a, revision_b, revision_c)}},
    )

    failures = validate_revision_windows(mutated)

    assert "modelo 100: revisions 'window-a' and 'window-c' overlap on period selector" in failures
    with pytest.raises(AmbiguousRevisionSelectionError) as excinfo:
        select_revision(mutated, filing_year=year, period="0A", on=date(year, 6, 1))
    assert excinfo.value.candidate_ids == ("window-a", "window-c")


def test_revision_validation_accepts_disjoint_windows_with_shared_period_selector() -> None:
    """Period-selector reuse remains valid when every date window is disjoint."""

    modelo = _committed_modelo_100()
    template = modelo.revisions[_m100_ids()[-1]]
    year = _newest_year()
    revisions = tuple(
        template.model_copy(update={"id": revision_id, "valid_from": valid_from, "valid_to": valid_to})
        for revision_id, valid_from, valid_to in (
            ("window-a", date(year - 5, 1, 1), date(year - 3, 12, 31)),
            ("window-b", date(year - 2, 1, 1), date(year - 1, 12, 31)),
            ("window-c", date(year, 1, 1), date(year + 1, 12, 31)),
        )
    )
    mutated = modelo.model_copy(update={"revisions": {revision.id: revision for revision in revisions}})

    assert validate_revision_windows(mutated) == []


def test_revision_validation_separates_meeting_windows_from_a_single_shared_day() -> None:
    """The window guard reads the canonical inclusive-bounds predicate.

    Windows that meet end-to-start are a temporal succession and stay silent
    however identical their period selectors; windows sharing even one day are
    a genuine simultaneity and must be reported.
    """

    modelo = _committed_modelo_100()
    template = modelo.revisions[_m100_ids()[-1]]
    year = _newest_year()

    def _pair(later_valid_from: date) -> ModeloDefinition:
        revisions = (
            template.model_copy(
                update={"id": "window-a", "valid_from": date(year - 2, 1, 1), "valid_to": date(year, 2, 2)},
            ),
            template.model_copy(
                update={"id": "window-b", "valid_from": later_valid_from, "valid_to": None},
            ),
        )
        return modelo.model_copy(update={"revisions": {revision.id: revision for revision in revisions}})

    assert validate_revision_windows(_pair(date(year, 2, 3))) == []
    assert validate_revision_windows(_pair(date(year, 2, 2))) == [
        "modelo 100: revisions 'window-a' and 'window-b' overlap on period selector",
    ]


def _declared_filing_windows() -> list[tuple[str, str, DeadlineWindowDefinition]]:
    """``(modelo id, revision id, window)`` for every filing window the corpus declares."""
    modelos, _catalogues = committed_registry_tree()
    return [
        (modelo.id, str(revision_id), window)
        for modelo in modelos
        for revision_id, revision in modelo.revisions.items()
        for window in revision.deadline_windows
    ]


def test_every_revision_resolves_on_the_filing_dates_it_declares() -> None:
    """A modelo must be selectable on the dates it says it is filed.

    THE GENERAL PROPERTY, not one coordinate. ``valid_from``/``valid_to`` bound
    the tax PERIODS a revision governs, and almost every return is filed after
    its period has closed -- modelo 390's resumen anual in the thirty first
    calendar days of the following January (Orden EHA/3111/2009, art. 8), modelo
    100's renta campaign the following April to June, every fourth-quarter and
    December coordinate in the January after. Testing a filing date against the
    period window alone refuses each of them at the exact moment it is due.

    The expectation is not hand-authored: each window is the registry's own
    declaration, carrying the legal and source references that ground it, so
    this asserts self-consistency between what a revision says its filing dates
    are and what the selector will admit on them. A single-coordinate test would
    not have caught this -- the defect held for 120 of the 1686 window
    boundaries the corpus declares, across 24 modelos and 53 revisions.
    """
    windows = _declared_filing_windows()
    assert windows, "the corpus must declare filing windows for this property to mean anything"

    unresolvable = []
    for modelo_id, revision_id, window in windows:
        modelo, _catalogues = committed_modelo(modelo_id)
        for edge in (window.opens_on, window.closes_on):
            try:
                selected = select_revision(
                    modelo,
                    filing_year=window.filing_year,
                    period=window.period.registry_token,
                    on=edge,
                )
            except (NoRevisionForPeriodError, AmbiguousRevisionSelectionError) as exc:
                unresolvable.append(f"{modelo_id}/{revision_id} window {window.id} on {edge}: {type(exc).__name__}")
                continue
            if selected.id != revision_id:
                unresolvable.append(
                    f"{modelo_id}/{revision_id} window {window.id} on {edge}: resolved to {selected.id}",
                )

    assert not unresolvable, "revisions unresolvable on their own declared filing dates: " + "; ".join(unresolvable)


def test_a_filing_window_admits_only_the_coordinate_it_declares() -> None:
    """The window widens nothing beyond the period it was declared for.

    THE FAIL-CLOSED HALF, and the reason this is not a blanket date widening.
    Modelo 303 declares, for a revision, a November and a December window that
    close on different days: November's monthly filing in the first days of the
    following January, December's near its end. On the middle of that January
    both periods are outside the governed year, and only the one whose window is
    still open may resolve. A revision admitted for any period once admitted for
    one would pass the sibling assertion above while quietly making November
    filable a month late.
    """
    modelo, _catalogues = committed_modelo("303")
    windows = {
        (revision_id, window.filing_year, window.period.registry_token): window
        for modelo_id, revision_id, window in _declared_filing_windows()
        if modelo_id == "303"
    }
    checked = 0
    for (revision_id, filing_year, period), december in windows.items():
        november = windows.get((revision_id, filing_year, "11"))
        on = date(filing_year + 1, 1, 15)
        valid_to = modelo.revisions[revision_id].valid_to
        if (
            period != "12"
            or november is None
            or valid_to is None
            or not (valid_to < on and november.closes_on < on <= december.closes_on)
        ):
            continue
        checked += 1
        assert select_revision(modelo, filing_year=filing_year, period="12", on=on).id == revision_id
        with pytest.raises(NoRevisionForPeriodError):
            select_revision(modelo, filing_year=filing_year, period="11", on=on)

    assert checked, "the corpus must declare a November window closed and a December window open mid-January"


def test_a_revision_is_refused_once_every_declared_window_has_closed() -> None:
    """Past the last declared filing date the revision stops resolving.

    Modelo 390's annual window closes on the thirtieth calendar day of January
    (Orden EHA/3111/2009, art. 8). That day resolves and the next does not: the
    reach is the declared window, not the following year.
    """
    modelo, _catalogues = committed_modelo("390")
    annual = [
        (revision_id, window)
        for modelo_id, revision_id, window in _declared_filing_windows()
        if modelo_id == "390" and window.period.registry_token in {"0A"}
    ]
    assert annual, "modelo 390 must declare annual filing windows"

    for revision_id, window in annual:
        closing = window.closes_on
        assert select_revision(modelo, filing_year=window.filing_year, period="0A", on=closing).id == revision_id
        with pytest.raises(NoRevisionForPeriodError):
            select_revision(modelo, filing_year=window.filing_year, period="0A", on=closing + timedelta(days=1))


def test_a_revision_declaring_no_filing_window_claims_no_reach_beyond_its_periods() -> None:
    """Absence of a declaration is refusal, never an inferred deadline.

    Modelo 390's oldest revision is ``applicability`` grade and declares no
    filing window at all. The selector must not deduce one from the article
    that governs its later siblings: an undeclared window is an undeclared
    window, and it stays refused exactly as it was before the window tier
    existed.
    """
    modelo, _catalogues = committed_modelo("390")
    windowless = [revision for revision in modelo.revisions.values() if not revision.deadline_windows]
    assert windowless, "modelo 390 must author a revision that declares no filing window"

    for revision in windowless:
        year = revision.valid_from.year
        with pytest.raises(NoRevisionForPeriodError):
            select_revision(modelo, filing_year=year, period="0A", on=date(year + 1, 1, 20))


def test_a_live_governed_period_outranks_a_still_open_filing_window() -> None:
    """At a design boundary the revision that governs the date wins outright.

    On 15 September 2024 modelo 303's ``2024-hasta-08-y-2t`` is still filable
    for August while ``2024-desde-09-y-3t`` already governs September. Pooling
    the period tier and the window tier makes that date ambiguous and refuses a
    year-only question that has one obvious answer, so the window tier is
    consulted only when no candidate governs the date. Both period-scoped
    answers stay reachable.
    """
    modelo, _catalogues = committed_modelo("303")
    early, late = split_exercise_revisions("303", early_period="08", late_period="3T")
    year = early.valid_from.year
    boundary = late.valid_from.replace(day=15)

    assert select_revision_for_year(modelo, filing_year=year, on=boundary).id == late.id
    assert select_revision(modelo, filing_year=year, period="3T", on=boundary).id == late.id
    assert select_revision(modelo, filing_year=year, period="08", on=boundary).id == early.id
