"""Registry foundations for the new-tax autoliquidaciones 490, 604 and 763.

490 (Impuesto sobre Determinados Servicios Digitales, Orden HAC/590/2021,
trimestral), 604 (Impuesto sobre las Transacciones Financieras, Orden
HAC/510/2021, mensual) and 763 (Impuesto sobre actividades de juego, Orden
EHA/1881/2011, trimestral) are new taxes classified under the TaxDomain members
IDSD / ITF / JUEGO. Each orden's approval (art 1) and plazo article are
cross-checked verbatim against the bundled BOE corpus, and the deadline windows
reproduce the verbatim plazo (490/763: month following each quarter; 604: days
10-20 of the month following each month). Scheduling/applicability-grade:
declaration-header casillas only, no bundled diseño de registro, so the base/cuota
money-closure casillas are not fabricated.

See Also:
    :class:`~core.TaxDomain`
        Closed tax-family enum that carries the IDSD, ITF and juego members.
    :func:`~domain.calculations.registry.tests._registry_schema_support._committed_modelo`
        Test loader for committed registry definitions and legal catalogues.
    :class:`~dev.registry.compiler.validator.RegistryValidator`
        Registry validator that checks the plazo and legal catalogue references.
    :class:`~core.modelo.Modelo`
        Canonical fleet membership these new-tax registrations extend.
    :data:`~domain.calculations.registry.modelo_obligation_scope.UNMODELED_OBLIGATIONS`
        Former recognized-unmodeled set reduced by these promotions.
    :mod:`~domain.calculations.registry.tests.test_modelo_592_576_121_122_registry`
        Companion registry coverage for the remaining new-tax modelos.
"""

from __future__ import annotations

from datetime import date

import pytest
from _pytest.mark import ParameterSet

from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.core.tax_domain import TaxDomain
from cadrumo.domain.calculations.registry.errors import FilingYearOutsideSupportEnvelopeError, NoRevisionForPeriodError
from cadrumo.domain.calculations.registry.temporal import select_revision
from cadrumo.domain.calculations.registry.tests.authored_editions import authored_revisions
from cadrumo.domain.calculations.registry.tests.snapshot_support import build_snapshot

from ..conformance.registry_schema_support import committed_modelo
from .profile_schema_support import committed_registry_validator

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("governed_fact_scope")]

# (modelo_id, approval, plazo, doc, tax_domain, period_codes_per_filing_year)
_MODELOS = [
    (
        "490",
        "orden-hac-590-2021:art-1",
        "orden-hac-590-2021:art-3",
        "BOE-A-2021-9721",
        TaxDomain("idsd"),
        ("1T", "2T", "3T", "4T"),
    ),
    (
        "604",
        "orden-hac-510-2021:art-1",
        "orden-hac-510-2021:art-3",
        "BOE-A-2021-8878",
        TaxDomain("itf"),
        ("01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12"),
    ),
    (
        "763",
        "orden-eha-1881-2011:art-1",
        "orden-eha-1881-2011:art-4",
        "BOE-A-2011-11704",
        TaxDomain("juego"),
        ("1T", "2T", "3T", "4T"),
    ),
]


@pytest.mark.parametrize("mid,approval,plazo,doc,domain,codes", _MODELOS)
def test_committed_definition_legal_authority_and_deadline_windows(
    mid: str, approval: str, plazo: str, doc: str, domain: TaxDomain, codes: tuple[str, ...]
) -> None:
    """Each new-tax autoliquidacion validates and cites its plazo on every window.

    Counted across the modelo's revisions rather than inside one named revision.
    This test used to pin a revision id, and both pinned ids stopped existing
    when modelo 490 and modelo 604 had their spans split -- the windows did not
    move or change, but the lookup raised ``KeyError`` and the modelo went
    unchecked.

    It then pinned a TOTAL window count, which was the same defect one level up.
    The docstring claimed "the orden fixes how many filing windows the tax has",
    but an orden fixes the CADENCE, not a total: 490 and 763 read 8 because the
    registry happened to enumerate two years of quarters, and 604 read 12 because
    it enumerated one year of months. Authoring modelo 604's 2021-2023 era, whose
    windows are as derivable from the same orden as the ones already present,
    moved the total to 48 and reddened a test that had detected nothing about the
    new windows' correctness.

    What the orden really fixes is that every filing year the registry
    enumerates is COMPLETE for the tax's cadence -- twelve months, or four
    quarters, no duplicates and no holes. That property catches a dropped or
    doubled window, which a total cannot distinguish from a legitimately added
    year, and it stays true as eras are split or extended.
    """
    modelo, catalogues = committed_modelo(mid)
    assert modelo.id == mid
    assert modelo.tax_domain == domain
    committed_registry_validator(catalogues).validate_modelo(modelo)

    for ref in (approval, plazo):
        entry = catalogues.legal[ref]
        assert entry.evidence_tier == "legal_authority"
        assert entry.document_id == doc

    declared = [window for revision in modelo.revisions.values() for window in revision.deadline_windows]
    assert declared, f"modelo {mid} declares no deadline windows at all"
    assert all(plazo in window.legal_refs for window in declared)

    expected_periods_by_year: dict[int, tuple[str, ...]] = {}
    by_year: dict[int, list[str]] = {}
    for window in declared:
        by_year.setdefault(window.filing_year, []).append(window.period.code)
        expected_periods_by_year.setdefault(window.filing_year, codes)
    if mid == "763":
        # The tax opened mid-2012: its first quarter has no filing window,
        # and Orden EHA/1881/2011 art. 4 dates the second through fourth.
        expected_periods_by_year[_OPENING_EXERCISE_763] = ("2T", "3T", "4T")
    for year, found in sorted(by_year.items()):
        assert sorted(found) == sorted(expected_periods_by_year[year]), (
            f"modelo {mid} filing year {year} declares periods {sorted(found)}, "
            f"not the supported cadence {sorted(expected_periods_by_year[year])}; "
            "a filing period is missing, doubled, or unsupported"
        )


_REVISIONS_763 = authored_revisions("763")
_OPENING_EXERCISE_763 = _REVISIONS_763[0].valid_from.year


def _design_763(revision_index: int | None) -> str:
    """The design source a revision cites: the one its own first exercise names, or the enrolled layout."""
    if revision_index is None:
        return "enrolled-modelo-763-layout"
    return f"aeat-dr-763-{_REVISIONS_763[revision_index].valid_from.year}"


def _case_763(
    revision_index: int,
    exercise_offset: int,
    period: str,
    design_index: int | None,
    opens: tuple[int, int, int],
    closes: tuple[int, int, int],
) -> ParameterSet:
    """One evidenced coordinate: its revision, its exercise counted from that revision's first, and its window.

    ``opens`` and ``closes`` are (year offset from the filing year, month, day).
    """
    revision = _REVISIONS_763[revision_index]
    filing_year = revision.valid_from.year + exercise_offset
    return pytest.param(
        filing_year,
        period,
        str(revision.id),
        _design_763(design_index),
        f"modelo-763-{filing_year}-{period.lower()}",
        date(filing_year + opens[0], opens[1], opens[2]),
        date(filing_year + closes[0], closes[1], closes[2]),
    )


@pytest.mark.parametrize(
    ("filing_year", "period", "revision_id", "layout_source", "deadline_id", "opens_on", "closes_on"),
    [
        _case_763(0, 0, "2T", 0, (0, 7, 1), (0, 7, 31)),
        _case_763(0, 0, "3T", 0, (0, 10, 1), (0, 10, 31)),
        # The trimestre the former split served from neither side. Orden EHA/1881/2011 art. 4 puts it
        # in the month after the quarter.
        _case_763(0, 0, "4T", 0, (1, 1, 1), (1, 1, 31)),
        _case_763(0, 1, "1T", 0, (0, 4, 1), (0, 4, 30)),
        _case_763(0, 2, "4T", 0, (1, 1, 1), (1, 1, 31)),
        _case_763(1, 0, "1T", 1, (0, 4, 1), (0, 4, 30)),
        _case_763(1, 2, "4T", 1, (1, 1, 1), (1, 1, 31)),
        _case_763(2, 0, "3T", 1, (0, 10, 1), (0, 10, 31)),
        _case_763(3, 0, "4T", None, (1, 1, 1), (1, 1, 31)),
        _case_763(4, 0, "1T", None, (0, 4, 1), (0, 4, 30)),
    ],
)
def test_modelo_763_selects_each_evidenced_design_era_with_its_deadline(
    filing_year: int,
    period: str,
    revision_id: str,
    layout_source: str,
    deadline_id: str,
    opens_on: date,
    closes_on: date,
) -> None:
    """The law selects each design era with its deadline, inside the support envelope or not."""
    modelo, catalogues = committed_modelo("763")
    committed_registry_validator(catalogues).validate_modelo(modelo)

    revision = select_revision(modelo, filing_year=filing_year, period=period)

    assert revision.id == revision_id
    assert revision.effective_authority_grade is RegistryAuthorityGrade.APPLICABILITY
    assert layout_source in revision.source_refs
    window = next(item for item in revision.deadline_windows if item.id == deadline_id)
    assert (window.opens_on, window.closes_on) == (opens_on, closes_on)

    support = catalogues.require_supported_filing_years()
    if not support.admits_filing_year(filing_year):
        with pytest.raises(FilingYearOutsideSupportEnvelopeError):
            select_revision(modelo, filing_year=filing_year, period=period, support=support)
        return
    snapshot = build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=filing_year,
        period=period,
        grade=RegistryAuthorityGrade.APPLICABILITY,
    )
    assert snapshot.revision.id == revision_id
    assert layout_source in snapshot.sources


def test_modelo_763_projects_the_current_design_through_every_supported_year() -> None:
    """Every year the support envelope admits resolves to the open-ended design era."""
    modelo, catalogues = committed_modelo("763")
    open_revisions = [revision for revision in modelo.revisions.values() if revision.valid_to is None]
    assert len(open_revisions) == 1
    (current,) = open_revisions

    for filing_year in catalogues.require_supported_filing_years().years:
        for period in current.period_selector.periods:
            snapshot = build_snapshot(
                modelo,
                catalogues,
                source_root=bundled_path(),
                filing_year=filing_year,
                period=period,
                grade=RegistryAuthorityGrade.APPLICABILITY,
            )
            assert snapshot.revision.id == current.id
            assert set(current.source_refs) <= set(snapshot.sources) | {
                ref for ref in current.source_refs if ref not in catalogues.sources
            }


@pytest.mark.parametrize("filing_year,period", [(_OPENING_EXERCISE_763 - 1, "4T"), (_OPENING_EXERCISE_763, "1T")])
def test_modelo_763_refuses_the_unevidenced_opening_coordinates(filing_year: int, period: str) -> None:
    """The tax had no filing window before its second 2012 quarter; no cadence inference fills one."""
    modelo, _catalogues = committed_modelo("763")

    with pytest.raises(NoRevisionForPeriodError):
        select_revision(modelo, filing_year=filing_year, period=period)
