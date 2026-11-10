"""Scenario bodies for test_prorrata_porcentaje_zero_volume_grounding, called by its authored-source and published-authority tests."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from decimal import Decimal

from ....iva.prorrata import ProrrataInputs, ProrrataKind, compute_prorrata_general
from ..schema import RegistrySnapshot
from .authored_editions import supported_authored_exercises
from .prorrata_porcentaje_grounding_support import snapshot_prorrata_percentage

#: Every supported exercise an authored modelo 303 revision governs, each once.
#: All of their windows sit inside the unamended art. 102.Uno / art. 104.Uno
#: text, so the same reading binds them. A year no revision governs would die on
#: resolution rather than on the zero-volume grounding it asserts, so the
#: exercises are read off the authored editions instead of being named.
LIVE_FILING_YEARS = tuple(dict.fromkeys(supported_authored_exercises("303")))


#: The percentage a full right to deduct carries. Read off arts. 92/94 (the
#: whole of the input tax is deductible when no prorrata limitation applies),
#: never off the formula under test.
FULL_RIGHT_TO_DEDUCT = Decimal("100")


#: The art. 104.Dos answer for a trader whose operations are ALL exempt without
#: right: numerator zero over a positive denominator.
NO_DEDUCTION_RIGHT = Decimal("0")


#: The settlement period and a mid-year quarter, with the liquidation date each
#: closes on. The prorrata percentage formula carries no date or period term, so
#: it should not move between them; probing both is what makes that a measured
#: fact rather than a reading of the expression.
SETTLEMENT_PERIOD = ("4T", (12, 31))

MID_YEAR_PERIOD = ("1T", (3, 31))


def registry_percentage(
    snapshot_of: Callable[..., RegistrySnapshot],
    filing_year: int,
    con_derecho: Decimal,
    total: Decimal,
    period: tuple[str, tuple[int, int]] = SETTLEMENT_PERIOD,
) -> Decimal:
    """The prorrata percentage via the real registry snapshot and formula runtime."""
    period_token, (close_month, close_day) = period
    snapshot = snapshot_of("303", filing_year=filing_year, period=period_token)
    return snapshot_prorrata_percentage(
        snapshot, con_derecho, total, closes_on=date(filing_year, close_month, close_day)
    )


#: LIVA art. 94 is headed "Operaciones cuya realización origina el derecho a la
#: deducción". It is the article that decides which operations grant the right,
#: so it supplies both the membership rule for the art. 104.Dos regla-1.ª
#: numerator and the full-deduction consequence this branch rests on.
FULL_RIGHT_TO_DEDUCT_ARTICLE = "ley-37-1992:art-94"


PRORRATA_PORCENTAJE_FORMULA_ID = "modelo-303-iva-prorrata-porcentaje"


def prorrata_formula_legal_refs(snapshot_of: Callable[..., RegistrySnapshot], filing_year: int) -> tuple[str, ...]:
    """The prorrata percentage formula's own declared legal refs for one filing year."""
    snapshot = snapshot_of("303", filing_year=filing_year, period="4T")
    formula = next(f for f in snapshot.revision.formulas if f.id == PRORRATA_PORCENTAJE_FORMULA_ID)
    return tuple(formula.legal_refs)


def check_no_volume_data_leaves_the_deduction_right_whole(
    snapshot_of: Callable[..., RegistrySnapshot], filing_year: int
) -> None:
    """A blank prorrata declaration must not cost the taxpayer the deduction right.

    The expected value is the regulated full-deduction default (arts. 92/94,
    reached because art. 102.Uno's *conjuntamente* antecedent is unmet), not a
    re-run of the registry formula.
    """
    snapshot = snapshot_of("303", filing_year=filing_year, period="4T")
    percentage = registry_percentage(snapshot_of, filing_year, Decimal("0"), Decimal("0"))

    assert percentage == FULL_RIGHT_TO_DEDUCT, (
        f"M303 {snapshot.revision.id}: a filing declaring no prorrata volumes "
        f"resolves the percentage to {percentage}; LIVA art. 102.Uno makes the "
        "regla de prorrata inapplicable when no exempt-without-right operations "
        "are declared, so the input tax stays deductible in full (arts. 92/94)"
    )


def check_both_live_revisions_agree_on_the_no_volume_branch(snapshot_of: Callable[..., RegistrySnapshot]) -> None:
    """One legal question, two revisions, one answer.

    Art. 102.Uno has stood in its current form since 01/01/2006 and art. 104's
    only post-2009 amendment (Ley 22/2013) touches apartado Tres.1º, so nothing
    in the earlier revision's applicable law can justify a different branch
    value. A divergence here is a defect, and this is the assertion that
    surfaces one.
    """
    by_revision = {
        snapshot_of("303", filing_year=year, period="4T").revision.id: (
            registry_percentage(snapshot_of, year, Decimal("0"), Decimal("0"))
        )
        for year in LIVE_FILING_YEARS
    }

    assert len(by_revision) == len(LIVE_FILING_YEARS), "the probe years must resolve to distinct revisions"
    assert len(set(by_revision.values())) == 1, (
        f"the live M303 revisions disagree on the no-volume prorrata branch: {by_revision}; "
        "the applicable articles are unamended across both windows, so they must agree"
    )


def check_registry_and_domain_agree_on_the_no_volume_branch(
    snapshot_of: Callable[..., RegistrySnapshot], filing_year: int
) -> None:
    """The independent domain authority is the second reading of the same rule.

    :func:`~domain.iva.compute_prorrata_general` has always reported 100 when
    total operations are zero, grounded in the same full-deduction criterion.
    The registry formula is the second implementation and the two must not be
    able to disagree.
    """
    domain_percentage = compute_prorrata_general(
        ProrrataInputs(
            operaciones_con_derecho_deduccion=Decimal("0"),
            operaciones_sin_derecho_deduccion=Decimal("0"),
        ),
        year=filing_year,
        kind=ProrrataKind.from_registry("definitiva"),
    ).percentage

    assert registry_percentage(snapshot_of, filing_year, Decimal("0"), Decimal("0")) == domain_percentage


def check_prorrata_formula_declares_the_full_right_to_deduct_article(
    snapshot_of: Callable[..., RegistrySnapshot], filing_year: int
) -> None:
    """The article the branch's consequence rests on must be declared on the formula itself.

    Carrying art. 94 only on the enclosing construct leaves a reader of this
    formula unable to see why a blank declaration yields a full deduction, and
    unable to see which article decides what enters the numerator. The
    dependency is the formula's, so the declaration is too.
    """
    refs = prorrata_formula_legal_refs(snapshot_of, filing_year)
    revision_id = snapshot_of("303", filing_year=filing_year, period="4T").revision.id

    assert FULL_RIGHT_TO_DEDUCT_ARTICLE in refs, (
        f"M303 {revision_id}: the prorrata percentage formula declares {refs!r} and omits "
        f"{FULL_RIGHT_TO_DEDUCT_ARTICLE!r}, the article that determines which operations "
        "originate the right to deduct and therefore both what the art. 104.Dos numerator "
        "counts and why a no-volume declaration leaves the deduction whole"
    )


def check_both_live_revisions_declare_the_same_prorrata_formula_grounding(
    snapshot_of: Callable[..., RegistrySnapshot],
) -> None:
    """One legal question, two revisions, one set of citations.

    Art. 94's only amendment (art. 10.14 of Real Decreto-ley 7/2021, in force
    01-07-2021) rewrites apartado Uno número 1.º letra c, the exempt-operations
    enumeration, and leaves the chapeau and the sujetas-y-no-exentas rule this
    formula rests on untouched. Nothing in either window's applicable law can
    justify a different citation set, so a divergence is drift.
    """
    by_revision = {
        snapshot_of("303", filing_year=year, period="4T").revision.id: frozenset(
            prorrata_formula_legal_refs(snapshot_of, year),
        )
        for year in LIVE_FILING_YEARS
    }

    assert len(by_revision) == len(LIVE_FILING_YEARS), "the probe years must resolve to distinct revisions"
    assert len(set(by_revision.values())) == 1, (
        f"the live M303 revisions ground the prorrata percentage formula differently: {by_revision}"
    )


def check_no_volume_branch_holds_in_a_mid_year_period_too(
    snapshot_of: Callable[..., RegistrySnapshot], filing_year: int
) -> None:
    """The branch is not a settlement-period effect, on either revision.

    Modelo 303 genuinely does behave differently at settlement — the art.
    105.Cuatro regularización is due once a year — so "the percentage is the
    same in a mid-year quarter" is worth measuring rather than reading off the
    formula expression. This assertion carries the mid-year axis that the
    single-filing-year Modelo 303 regression used to be the only holder of, so
    retiring that regression loses no coverage.
    """
    percentage = registry_percentage(snapshot_of, filing_year, Decimal("0"), Decimal("0"), period=MID_YEAR_PERIOD)

    assert percentage == FULL_RIGHT_TO_DEDUCT
    assert percentage == registry_percentage(snapshot_of, filing_year, Decimal("0"), Decimal("0")), (
        "the no-volume prorrata percentage must not depend on the filing period"
    )


def check_a_wholly_exempt_trader_still_resolves_to_no_deduction_right(
    snapshot_of: Callable[..., RegistrySnapshot], filing_year: int
) -> None:
    """Prove the branch is a branch, not a blanket 100.

    Without this the assertions above would pass on a formula that answered 100
    for every input, including the one case where art. 104.Dos genuinely yields
    zero: a positive denominator with nothing in the numerator, i.e. a trader
    all of whose operations are exempt without right to deduct.
    """
    assert registry_percentage(snapshot_of, filing_year, Decimal("0"), Decimal("40000")) == NO_DEDUCTION_RIGHT
