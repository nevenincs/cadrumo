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
    :class:`~domain.calculations.registry._validate.RegistryValidator`
        Registry validator that checks the plazo and legal catalogue references.
    :data:`~core.access_gate.CANONICAL_MODELO_FLEET`
        Canonical fleet membership these new-tax registrations extend.
    :data:`~core.UNMODELED_OBLIGATIONS`
        Former recognized-unmodeled set reduced by these promotions.
    :mod:`~domain.calculations.registry.tests.test_modelo_592_576_121_122_registry`
        Companion registry coverage for the remaining new-tax modelos.
"""

from __future__ import annotations

from datetime import date

import pytest

from .....core import RegistryAuthorityGrade, TaxDomain
from .....core.resources import bundled_path
from .._errors import NoRevisionForPeriodError
from .._snapshot import build_snapshot
from .._temporal import select_revision
from .._validate import RegistryValidator
from ._registry_schema_support import _committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

# (modelo_id, approval, plazo, doc, tax_domain, period_codes_per_filing_year)
_MODELOS = [
    (
        "490",
        "orden-hac-590-2021:art-1",
        "orden-hac-590-2021:art-3",
        "BOE-A-2021-9721",
        TaxDomain.IDSD,
        ("1T", "2T", "3T", "4T"),
    ),
    (
        "604",
        "orden-hac-510-2021:art-1",
        "orden-hac-510-2021:art-3",
        "BOE-A-2021-8878",
        TaxDomain.ITF,
        ("01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12"),
    ),
    (
        "763",
        "orden-eha-1881-2011:art-1",
        "orden-eha-1881-2011:art-4",
        "BOE-A-2011-11704",
        TaxDomain.JUEGO,
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
    modelo, catalogues = _committed_modelo(mid)
    assert modelo.id == mid
    assert modelo.tax_domain is domain
    RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(modelo)

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
        # AEAT's historical catalogue names only 2T/3T for 2012. The missing
        # first and fourth quarters are refused rather than completed from the
        # otherwise quarterly cadence.
        expected_periods_by_year[2012] = ("2T", "3T")
    for year, found in sorted(by_year.items()):
        assert sorted(found) == sorted(expected_periods_by_year[year]), (
            f"modelo {mid} filing year {year} declares periods {sorted(found)}, "
            f"not the supported cadence {sorted(expected_periods_by_year[year])}; "
            "a filing period is missing, doubled, or unsupported"
        )


@pytest.mark.parametrize(
    ("filing_year", "period", "revision_id", "layout_source", "deadline_id", "opens_on", "closes_on"),
    [
        (2012, "2T", "2012-2t-3t", "aeat-dr-763-2012", "modelo-763-2012-2t", date(2012, 7, 1), date(2012, 7, 31)),
        (2012, "3T", "2012-2t-3t", "aeat-dr-763-2012", "modelo-763-2012-3t", date(2012, 10, 1), date(2012, 10, 31)),
        (2013, "1T", "2013-2014", "aeat-dr-763-2012", "modelo-763-2013-1t", date(2013, 4, 1), date(2013, 4, 30)),
        (2014, "4T", "2013-2014", "aeat-dr-763-2012", "modelo-763-2014-4t", date(2015, 1, 1), date(2015, 1, 31)),
        (2015, "1T", "2015-2017", "aeat-dr-763-2015", "modelo-763-2015-1t", date(2015, 4, 1), date(2015, 4, 30)),
        (2017, "4T", "2015-2017", "aeat-dr-763-2015", "modelo-763-2017-4t", date(2018, 1, 1), date(2018, 1, 31)),
        (2018, "3T", "2018-1t-3t", "aeat-dr-763-2015", "modelo-763-2018-3t", date(2018, 10, 1), date(2018, 10, 31)),
        (2018, "4T", "2018-4t", "enrolled-modelo-763-layout", "modelo-763-2018-4t", date(2019, 1, 1), date(2019, 1, 31)),
        (2019, "1T", "2019-y-siguientes", "enrolled-modelo-763-layout", "modelo-763-2019-1t", date(2019, 4, 1), date(2019, 4, 30)),
        (2026, "4T", "2019-y-siguientes", "enrolled-modelo-763-layout", "modelo-763-2026-4t", date(2027, 1, 1), date(2027, 1, 31)),
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
    """The selector and deadline stay coupled at every evidence boundary."""
    modelo, catalogues = _committed_modelo("763")
    RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(modelo)

    snapshot = build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=filing_year,
        period=period,
        grade=RegistryAuthorityGrade.APPLICABILITY,
    )

    assert snapshot.revision.id == revision_id
    assert snapshot.revision.effective_authority_grade is RegistryAuthorityGrade.APPLICABILITY
    assert layout_source in snapshot.revision.source_refs
    assert layout_source in snapshot.sources
    window = next(item for item in snapshot.revision.deadline_windows if item.id == deadline_id)
    assert (window.opens_on, window.closes_on) == (opens_on, closes_on)


@pytest.mark.parametrize("filing_year,period", [(2011, "4T"), (2012, "1T"), (2012, "4T")])
def test_modelo_763_refuses_the_unevidenced_opening_coordinates(filing_year: int, period: str) -> None:
    """The historical design title admits 2012 2T/3T only; no cadence inference fills gaps."""
    modelo, _catalogues = _committed_modelo("763")

    with pytest.raises(NoRevisionForPeriodError):
        select_revision(modelo, filing_year=filing_year, period=period)
