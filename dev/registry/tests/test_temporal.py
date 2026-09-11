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

from datetime import date

import pytest

from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.core.errors.error_codes import resolve_error_message
from cadrumo.domain.calculations.registry.authority import bundled_authority
from cadrumo.domain.calculations.registry.errors import (
    AmbiguousRevisionSelectionError,
    NoRevisionForPeriodError,
    RegistrySnapshotError,
)
from cadrumo.domain.calculations.registry.relations import relation_source_requirements
from cadrumo.domain.calculations.registry.schema import ModeloDefinition
from cadrumo.domain.calculations.registry.schema_deadlines import DeadlineWindowDefinition
from cadrumo.domain.calculations.registry.temporal import select_revision, select_revision_for_year

from ..compiler.validate_revision_rules import validate_revision_windows
from ..conformance.registry_schema_support import (
    committed_modelo as _committed_modelo,
)
from ..conformance.registry_schema_support import (
    committed_registry_tree as _committed_registry_tree,
)
from ..conformance.registry_schema_support import (
    committed_snapshot as _committed_snapshot,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _committed_modelo_100() -> ModeloDefinition:
    modelo, _catalogues = _committed_modelo("100")
    return modelo


def test_select_revision_returns_the_matching_year_revision() -> None:
    modelo = _committed_modelo_100()

    revision = select_revision(modelo, filing_year=2025, period="0A")

    assert revision.id == "2025"


def test_snapshot_normalises_a_case_variant_period_to_the_declared_token() -> None:
    """A valid lower-case token must not survive into the snapshot verbatim.

    ``select_revision`` matches selectors case-insensitively and returns the
    caller's token unchanged, so the snapshot boundary is where the canonical
    form is resolved. Without it the snapshot disagreed with itself: its
    ``filing_period`` normalised through ``Period`` while ``period`` did not.
    """
    snapshot = _committed_snapshot("100", 2025, "0a", grade=RegistryAuthorityGrade.CALCULATION)

    assert snapshot.period == "0A"
    assert snapshot.filing_period is not None
    assert snapshot.filing_period.code == snapshot.period
    assert (
        snapshot.revision.id
        == _committed_snapshot("100", 2025, "0A", grade=RegistryAuthorityGrade.CALCULATION).revision.id
    )


def test_case_variant_periods_activate_the_same_relation_requirements() -> None:
    """Relation activation is exact-membership, so case must not silence it.

    A lower-case ``0a`` selected the same M100 revision as ``0A`` while
    activating none of its relation declarations -- the caller got a successful
    snapshot and a clean-looking empty obligation set instead of the required
    cross-model inputs.
    """
    canonical = _committed_snapshot("100", 2025, "0A", grade=RegistryAuthorityGrade.CALCULATION)
    variant = _committed_snapshot("100", 2025, "0a", grade=RegistryAuthorityGrade.CALCULATION)

    canonical_requirements = relation_source_requirements(
        canonical.revision,
        filing_year=2025,
        period=canonical.period,
    )
    variant_requirements = relation_source_requirements(
        variant.revision,
        filing_year=2025,
        period=variant.period,
    )

    assert canonical_requirements, "the M100 2025 revision must declare relation requirements"
    assert variant_requirements == canonical_requirements


def test_case_variant_period_still_refuses_an_undeclared_token() -> None:
    """Normalisation must not widen the accepted set beyond declared periods."""
    modelo = _committed_modelo_100()

    with pytest.raises(RegistrySnapshotError, match="no revision for"):
        select_revision(modelo, filing_year=2025, period="0b")


def test_select_revision_raises_when_no_revision_matches_year() -> None:
    modelo = _committed_modelo_100()

    with pytest.raises(RegistrySnapshotError, match="no revision for"):
        select_revision(modelo, filing_year=2099, period="0A")


def test_select_revision_raises_when_period_not_declared_by_selector() -> None:
    """Renta is annual-only — period='0A' is the lone declared period."""
    modelo = _committed_modelo_100()

    with pytest.raises(RegistrySnapshotError, match="no revision for"):
        select_revision(modelo, filing_year=2025, period="3T")


def test_select_revision_honours_explicit_revision_id_filter() -> None:
    modelo = _committed_modelo_100()

    revision = select_revision(modelo, filing_year=2024, period="0A", revision_id="2024")

    assert revision.id == "2024"


def test_select_revision_rejects_mismatching_revision_id_filter() -> None:
    modelo = _committed_modelo_100()

    with pytest.raises(RegistrySnapshotError, match="no revision for"):
        select_revision(modelo, filing_year=2024, period="0A", revision_id="not-a-real-id")


def test_select_revision_filters_by_on_date_outside_validity_window() -> None:
    """An on= date well before every revision's valid_from must surface
    as no-revision, not silently pick the closest revision."""
    modelo = _committed_modelo_100()

    with pytest.raises(RegistrySnapshotError, match="no revision for"):
        select_revision(modelo, filing_year=2025, period="0A", on=date(1900, 1, 1))


def test_select_revision_raises_on_ambiguous_selection() -> None:
    """The dedup check fires when two revisions both match the
    requested year + period (+ optional on= window). Forge a twin
    revision so the candidates list grows past length 1."""
    modelo = _committed_modelo_100()
    original = modelo.revisions["2025"]
    twin = original.model_copy(update={"id": "2025-twin"})
    mutated = modelo.model_copy(update={"revisions": {**modelo.revisions, twin.id: twin}})

    with pytest.raises(RegistrySnapshotError, match="ambiguous revision selection"):
        select_revision(mutated, filing_year=2025, period="0A")


def test_no_revision_raises_typed_subclass_with_structured_natural_key() -> None:
    """The no-candidate branch raises the typed subclass carrying the
    natural key as structured fields, not only inside the message.

    A consumer dispatches by ``except NoRevisionForPeriodError`` and reads
    ``modelo_id`` / ``filing_year`` / ``period`` / ``revision_id`` from the
    typed fields. The subclass is still catchable as the parent type, so
    every existing ``except RegistrySnapshotError`` site keeps working."""
    modelo = _committed_modelo_100()

    with pytest.raises(NoRevisionForPeriodError) as excinfo:
        select_revision(modelo, filing_year=2099, period="0A", revision_id="r9")

    err = excinfo.value
    assert isinstance(err, RegistrySnapshotError)
    assert err.modelo_id == "100"
    assert err.filing_year == 2099
    assert err.period == "0A"
    assert err.revision_id == "r9"


def test_modelo_390_2026_refusal_lists_the_enrolled_revision_set() -> None:
    """The live Modelo 390 refusal distinguishes missing authority from failure.

    The set is read from the bundled authority at the temporal raiser, not
    reconstructed by a caller. This keeps the operator-facing fallback message
    and machine-readable context synchronized with the enrolled registry.
    """
    with pytest.raises(NoRevisionForPeriodError) as excinfo:
        bundled_authority().snapshot("390", filing_year=2026, period="0A")

    err = excinfo.value
    assert err.available_revision_ids == ("2021", "2022", "2023", "2024", "2025")
    assert err.context == {
        "modelo_id": "390",
        "filing_year": 2026,
        "period": "0A",
        "revision_id": "",
        "available_revision_ids": "2021,2022,2023,2024,2025",
    }
    assert str(err) == (
        "modelo 390: no revision for year=2026 period='0A' revision=None; "
        "modelo 390 declares: 2021, 2022, 2023, 2024, 2025"
    )


@pytest.mark.parametrize("locale", ("en", "es", "ca", "hu"))
def test_modelo_390_2026_localized_refusal_lists_the_enrolled_revision_set(locale: str) -> None:
    """The canonical renderer preserves the accepted set in every shipped locale."""
    with pytest.raises(NoRevisionForPeriodError) as excinfo:
        bundled_authority().snapshot("390", filing_year=2026, period="0A")

    assert "2021,2022,2023,2024,2025" in resolve_error_message(excinfo.value, locale=locale)


def test_ambiguous_selection_raises_typed_subclass_with_candidate_ids() -> None:
    """The dedup branch raises the typed subclass carrying the candidate
    revision ids as a structured, sorted tuple — independent of the
    human-readable message wording (the whole point of the refactor).

    Designed so a rewording of the ``str()`` message would not change the
    assertion: the candidate ids are read from ``candidate_ids``, never
    parsed out of the message."""
    modelo = _committed_modelo_100()
    original = modelo.revisions["2025"]
    twin = original.model_copy(update={"id": "2025-twin"})
    mutated = modelo.model_copy(update={"revisions": {**modelo.revisions, twin.id: twin}})

    with pytest.raises(AmbiguousRevisionSelectionError) as excinfo:
        select_revision(mutated, filing_year=2025, period="0A")

    err = excinfo.value
    assert isinstance(err, RegistrySnapshotError)
    assert err.modelo_id == "100"
    # Sorted tuple of every matching revision id, read from the typed field.
    assert err.candidate_ids == ("2025", "2025-twin")


def test_revision_validation_reports_non_adjacent_overlap_before_runtime_ambiguity() -> None:
    """A long revision cannot hide its overlap behind a shorter middle revision."""

    modelo = _committed_modelo_100()
    template = modelo.revisions["2025"]
    revision_a = template.model_copy(
        update={"id": "window-a", "valid_from": date(2020, 1, 1), "valid_to": date(2030, 12, 31)},
    )
    revision_b = template.model_copy(
        update={"id": "window-b", "valid_from": date(2021, 1, 1), "valid_to": date(2022, 12, 31)},
    )
    revision_c = template.model_copy(
        update={"id": "window-c", "valid_from": date(2025, 1, 1), "valid_to": date(2026, 12, 31)},
    )
    mutated = modelo.model_copy(
        update={"revisions": {revision.id: revision for revision in (revision_a, revision_b, revision_c)}},
    )

    failures = validate_revision_windows(mutated)

    assert "modelo 100: revisions 'window-a' and 'window-c' overlap on period selector" in failures
    with pytest.raises(AmbiguousRevisionSelectionError) as excinfo:
        select_revision(mutated, filing_year=2025, period="0A", on=date(2025, 6, 1))
    assert excinfo.value.candidate_ids == ("window-a", "window-c")


def test_revision_validation_accepts_disjoint_windows_with_shared_period_selector() -> None:
    """Period-selector reuse remains valid when every date window is disjoint."""

    modelo = _committed_modelo_100()
    template = modelo.revisions["2025"]
    revisions = tuple(
        template.model_copy(update={"id": revision_id, "valid_from": valid_from, "valid_to": valid_to})
        for revision_id, valid_from, valid_to in (
            ("window-a", date(2020, 1, 1), date(2022, 12, 31)),
            ("window-b", date(2023, 1, 1), date(2024, 12, 31)),
            ("window-c", date(2025, 1, 1), date(2026, 12, 31)),
        )
    )
    mutated = modelo.model_copy(update={"revisions": {revision.id: revision for revision in revisions}})

    assert validate_revision_windows(mutated) == []


def _declared_filing_windows() -> list[tuple[str, str, DeadlineWindowDefinition]]:
    """``(modelo id, revision id, window)`` for every filing window the corpus declares."""
    modelos, _catalogues = _committed_registry_tree()
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
        modelo, _catalogues = _committed_modelo(modelo_id)
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
    Modelo 303's 2023 revision declares two windows that close on different
    days: November's monthly filing on 2 January 2024, December's on the 30th.
    On 15 January both periods are outside the governed year, and only the one
    whose window is still open may resolve. A revision admitted for any period
    once admitted for one would pass the sibling assertion above while quietly
    making November filable a month late.
    """
    modelo, _catalogues = _committed_modelo("303")

    assert select_revision(modelo, filing_year=2023, period="12", on=date(2024, 1, 15)).id == "2023"
    with pytest.raises(NoRevisionForPeriodError):
        select_revision(modelo, filing_year=2023, period="11", on=date(2024, 1, 15))


def test_a_revision_is_refused_once_every_declared_window_has_closed() -> None:
    """Past the last declared filing date the revision stops resolving.

    Modelo 390's 2025 window closes on 30 January 2026 (the thirtieth calendar
    day of January, Orden EHA/3111/2009, art. 8). The 30th resolves and the 31st
    does not: the reach is the declared window, not the following year.
    """
    modelo, _catalogues = _committed_modelo("390")

    assert select_revision(modelo, filing_year=2025, period="0A", on=date(2026, 1, 30)).id == "2025"
    with pytest.raises(NoRevisionForPeriodError):
        select_revision(modelo, filing_year=2025, period="0A", on=date(2026, 1, 31))


def test_a_revision_declaring_no_filing_window_claims_no_reach_beyond_its_periods() -> None:
    """Absence of a declaration is refusal, never an inferred deadline.

    Modelo 390's 2021 revision is ``applicability`` grade and declares no
    filing window at all. The selector must not deduce one from the article
    that governs its 2022-2025 siblings: an undeclared window is an undeclared
    window, and it stays refused exactly as it was before the window tier
    existed.
    """
    modelo, _catalogues = _committed_modelo("390")
    revision = modelo.revisions["2021"]
    assert not revision.deadline_windows

    with pytest.raises(NoRevisionForPeriodError):
        select_revision(modelo, filing_year=2021, period="0A", on=date(2022, 1, 20))


def test_a_live_governed_period_outranks_a_still_open_filing_window() -> None:
    """At a design boundary the revision that governs the date wins outright.

    On 15 September 2024 modelo 303's ``2024-hasta-08-y-2t`` is still filable
    for August while ``2024-desde-09-y-3t`` already governs September. Pooling
    the period tier and the window tier makes that date ambiguous and refuses a
    year-only question that has one obvious answer, so the window tier is
    consulted only when no candidate governs the date. Both period-scoped
    answers stay reachable.
    """
    modelo, _catalogues = _committed_modelo("303")
    boundary = date(2024, 9, 15)

    assert select_revision_for_year(modelo, filing_year=2024, on=boundary).id == "2024-desde-09-y-3t"
    assert select_revision(modelo, filing_year=2024, period="3T", on=boundary).id == "2024-desde-09-y-3t"
    assert select_revision(modelo, filing_year=2024, period="08", on=boundary).id == "2024-hasta-08-y-2t"
