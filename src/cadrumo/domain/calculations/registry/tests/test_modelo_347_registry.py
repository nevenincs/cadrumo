"""Tests for committed Modelo 347 registry foundation."""

from __future__ import annotations

from datetime import date

import pytest

from .....core.resources.bundled_data import bundled_path
from .....tests.aeat_literal_fixtures import aeat_host
from .....tests.registry_snapshot import build_snapshot
from .._validate import RegistryValidator
from ..errors import NoRevisionForPeriodError
from ..schema_input_kind import InputKind
from ._registry_schema_support import _committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]
_WWW1_HOST = aeat_host("www1")
_WWW6_HOST = aeat_host("www6")


def _load_modelo_347():
    return _committed_modelo("347")


_FORBIDDEN_REMOTE_ACTIONS = frozenset(
    [
        "server-side-save",
        "signing",
        "presentation",
        "payment",
        "amendment",
        "cancellation",
        "document-submission",
        "declaration-submission",
    ],
)


def test_committed_modelo_347_validates_against_catalogues() -> None:
    modelo, catalogues = _load_modelo_347()
    RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(modelo)
    assert set(modelo.revisions) == {"2011-2024", "2025-y-siguientes"}


@pytest.mark.parametrize("filing_year", [2011, 2018, 2024, 2026])
def test_committed_modelo_347_resolves_revision_by_filing_year(filing_year: int) -> None:
    modelo, catalogues = _load_modelo_347()
    snapshot = build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=filing_year,
        period="0A",
    )
    # The split at the 2024/2025 boundary means the year decides the half, and
    # that is the fact worth pinning: the two carry different byte layouts, so a
    # year resolving to the wrong one would build cleanly and file at the wrong
    # offsets.
    assert snapshot.revision.id == ("2025-y-siguientes" if filing_year >= 2025 else "2011-2024")
    # Orden HAC/1431/2025 takes effect in December 2025, so it applies to the
    # later half only. Asserting both on every year would credit the earlier
    # revision with an orden that post-dates every filing it governs.
    assert snapshot.revision.orden_aplicabilidad == (
        ("orden-eha-3012-2008:art-1", "orden-hac-1431-2025:art-1")
        if filing_year >= 2025
        else ("orden-eha-3012-2008:art-1",)
    )


@pytest.mark.parametrize("filing_year", [2008, 2009, 2010])
def test_the_pre_2011_ejercicios_resolve_to_no_revision(filing_year: int) -> None:
    """2008-2010 are deliberately unserved, and must REFUSE rather than resolve.

    The revision covering them cited ``aeat-dr-347-2011`` -- a design AEAT
    published for ejercicio 2011 onward -- so those years were being written at
    2011 offsets. Narrowing it to 2011-2024 removed that, and the years are now
    uncovered until their own designs are authored.

    Asserted rather than dropped from the parametrisation above, because a year
    that silently resolves to a NEIGHBOURING revision is the exact failure the
    narrowing exists to prevent: it would build cleanly and file wrong bytes.
    """
    modelo, catalogues = _load_modelo_347()

    with pytest.raises(NoRevisionForPeriodError) as caught:
        build_snapshot(
            modelo,
            catalogues,
            source_root=bundled_path(),
            filing_year=filing_year,
            period="0A",
        )

    assert "347" in str(caught.value) or str(filing_year) in str(caught.value), (
        f"the refusal must name the modelo or the year it could not serve: {caught.value}"
    )


def test_committed_modelo_347_is_informative_only() -> None:
    modelo, _ = _load_modelo_347()
    assert modelo.calculation_class == "informative", (
        "Modelo 347 must be declared calculation_class='informative' in its manifest"
    )
    for revision in modelo.revisions.values():
        assert revision.formulas == (), revision.id
        assert revision.relations == (), revision.id
        for casilla in revision.casillas:
            assert casilla.input_kind in {InputKind.INFORMATIONAL, InputKind.MANUAL}, casilla.id


def test_committed_modelo_347_workbook_parity_refs_resolve_to_corpus() -> None:
    modelo, catalogues = _load_modelo_347()

    assert catalogues.sources["aeat-modelo-347-procedure"].evidence_tier == "official_source_guidance"
    assert catalogues.sources["boe-modelo-347-2008-form"].evidence_tier == "layout_authority"
    assert catalogues.sources["boe-modelo-347-2011-amendment"].evidence_tier == "layout_authority"
    for revision_id, revision in modelo.revisions.items():
        sources_seen = {ref.workbook_source for ref in revision.workbook_parity_refs}
        # Each revision is checked against the design IT emits, so the parity
        # refs must be exactly the record designs that revision cites. Pinning a
        # fixed pair here was right while one revision carried both designs and
        # became wrong the moment the split gave each half its own -- the
        # relationship survives the next split, the literal set does not.
        declared = {ref for ref in revision.source_refs if ref.startswith("aeat-dr-347-")}
        assert sources_seen == declared, (revision_id, sources_seen, declared)
        for ref in revision.workbook_parity_refs:
            assert ref.formula_coverage == "record_design_layout"
            assert ref.runner_required is False
            source = catalogues.sources[ref.workbook_source]
            assert source.evidence_tier == "layout_authority"
            assert (bundled_path() / source.corpus_path).is_file()


def test_committed_modelo_347_static_cross_reference_forbids_remote_writes() -> None:
    modelo, _ = _load_modelo_347()
    for revision in modelo.revisions.values():
        decision = next(ref for ref in revision.live_cross_references if ref.surface == "static_official_documentation")
        assert decision.requires_authentication is False
        assert decision.synthetic_data_allowed is False
        assert _FORBIDDEN_REMOTE_ACTIONS.issubset(decision.forbidden_actions), revision.id


def test_committed_modelo_347_authenticated_read_surface_is_read_only_and_guarded() -> None:
    modelo, _ = _load_modelo_347()
    for revision in modelo.revisions.values():
        decision = next(ref for ref in revision.live_cross_references if ref.surface == "authenticated_read_surface")
        assert decision.requires_authentication is True
        assert decision.requires_aeat_authorization is True
        assert decision.synthetic_data_allowed is False
        assert set(decision.allowed_methods) <= {"GET", "HEAD", "OPTIONS"}, revision.id
        assert set(decision.allowed_hosts) == {
            _WWW1_HOST,
            _WWW6_HOST,
        }, revision.id
        assert _FORBIDDEN_REMOTE_ACTIONS.issubset(decision.forbidden_actions), revision.id


def test_committed_modelo_347_filing_schedule_is_annual() -> None:
    modelo, _ = _load_modelo_347()
    for revision in modelo.revisions.values():
        assert revision.filing_schedules, revision.id
        for schedule in revision.filing_schedules:
            assert schedule.period_kind == "annual"
            assert schedule.periods == ("0A",)


@pytest.mark.parametrize(
    ("filing_year", "expected_open", "expected_close"),
    [
        # Plazo per Orden EHA/3012/2008 art. 10: durante el mes de febrero,
        # shifted by the AEAT annual calendar when February ends on a non-working day.
        (2018, date(2019, 2, 1), date(2019, 2, 28)),
        (2019, date(2020, 2, 1), date(2020, 2, 29)),
        (2024, date(2025, 2, 1), date(2025, 2, 28)),
        (2025, date(2026, 2, 1), date(2026, 3, 2)),
    ],
)
def test_committed_modelo_347_deadline_window_matches_official_calendar(
    filing_year: int,
    expected_open: date,
    expected_close: date,
) -> None:
    modelo, _ = _load_modelo_347()
    windows = [
        window
        for revision in modelo.revisions.values()
        for window in revision.deadline_windows
        if window.filing_year == filing_year
    ]
    assert len(windows) == 1, filing_year
    window = windows[0]
    assert window.period_kind == "annual"
    assert window.opens_on == expected_open
    assert window.closes_on == expected_close
    assert "aeat-modelo-347-procedure" in window.source_refs
    if filing_year == 2025:
        assert "aeat-calendario-contribuyente-2026-hasta-2-marzo" in window.source_refs


def test_committed_modelo_347_construct_includes_revision_members() -> None:
    modelo, _ = _load_modelo_347()
    for revision in modelo.revisions.values():
        assert len(revision.constructs) == 1, revision.id
        construct = revision.constructs[0]
        # Coverage, not ordering. `ConstructDefinition` validates that members
        # are unique and that each names a declared entity; it does not fix their
        # order, and the construct's 44 ids diverged from the revision's fragment
        # merge order while covering exactly the same set. Requiring identical
        # tuples asserted the merge order rather than the membership, so adding
        # or renaming a casilla fragment reddened it with nothing wrong.
        declared_casillas = tuple(c.id for c in revision.casillas)
        assert set(construct.casilla_ids) == set(declared_casillas), revision.id
        assert len(construct.casilla_ids) == len(declared_casillas), revision.id
        assert construct.extraction_profiles == tuple(p.id for p in revision.extraction_profiles)
        assert construct.verification_expectations == tuple(e.id for e in revision.verification_expectations)
        assert construct.workbook_parity_refs == tuple(w.id for w in revision.workbook_parity_refs)
        assert construct.deadline_windows == tuple(w.id for w in revision.deadline_windows)
        assert construct.filing_schedules == tuple(s.id for s in revision.filing_schedules)
        link_surfaces = {link.surface for link in revision.application_links}
        assert {"portal", "filing", "extractor", "deadline"} <= link_surfaces, revision.id
