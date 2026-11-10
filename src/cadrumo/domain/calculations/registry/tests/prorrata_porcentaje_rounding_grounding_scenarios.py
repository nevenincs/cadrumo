"""Scenario bodies for test_prorrata_porcentaje_rounding_grounding, called by its authored-source and published-authority tests."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from decimal import Decimal

from cadrumo.domain.iva.prorrata import ProrrataKind

from ....iva.prorrata import ProrrataInputs, compute_prorrata_general
from ..formula_runtime_ops import apply_rounding
from ..schema import RegistrySnapshot
from ..schema_rounding import RegistryRoundingCode
from .authored_editions import filing_year_envelope, supported_authored_exercises
from .prorrata_porcentaje_grounding_support import snapshot_prorrata_percentage

FORMULA_ID = "modelo-303-iva-prorrata-porcentaje"


#: Every supported exercise an authored modelo 303 revision governs, each once,
#: including both epochs of an exercise the registry splits by period. The
#: art. 104.Dos sentence has stood unamended since BOE-A-1992-28740, so it binds
#: all of them. A year no revision governs would die on resolution rather than on
#: the rounding code it asserts, so the exercises are read off the authored
#: editions instead of being named.
LIVE_FILING_YEARS = tuple(dict.fromkeys(supported_authored_exercises("303")))


#: (con-derecho, total) volume pairs whose percentage has a fractional part
#: STRICTLY below one half. These are exactly the ratios on which half-up and
#: round-up disagree; ``test_selected_ratios_discriminate_between_the_two_roundings``
#: proves the discrimination rather than assuming it, and rejected a 76,5 %
#: candidate that half-up already rounds up.
DISCRIMINATING_VOLUMES = (
    (Decimal("552"), Decimal("1000")),
    (Decimal("601"), Decimal("1000")),
    (Decimal("704"), Decimal("1000")),
    (Decimal("764"), Decimal("1000")),
    (Decimal("7600001"), Decimal("10000000")),
)


#: The two ratios the AEAT manual states for the bundled prorrata scenario
#: (32.000 / 44.000 provisional and 25.000 / 45.000 definitiva). Their
#: fractional parts exceed one half, so the correction must leave them where
#: the manual puts them.
MANUAL_VOLUMES = (
    (Decimal("32000"), Decimal("44000")),
    (Decimal("25000"), Decimal("45000")),
)


#: A ratio that is already a whole percentage. "Unidad superior" moves a
#: fractional result up; it does not add a unit to an exact one.
EXACT_VOLUMES = (Decimal("500"), Decimal("1000"))


def domain_percentage(con_derecho: Decimal, total: Decimal) -> Decimal:
    """The same legal quantity via the independent :mod:`domain.iva` authority."""
    return compute_prorrata_general(
        ProrrataInputs(
            operaciones_con_derecho_deduccion=con_derecho,
            operaciones_sin_derecho_deduccion=total - con_derecho,
        ),
        year=filing_year_envelope().horizon,
        kind=ProrrataKind.from_registry("definitiva"),
    ).percentage


def registry_percentage(
    snapshot_of: Callable[..., RegistrySnapshot], filing_year: int, con_derecho: Decimal, total: Decimal
) -> Decimal:
    """The same legal quantity via the real registry snapshot and formula runtime."""
    snapshot = snapshot_of("303", filing_year=filing_year, period="4T")
    return snapshot_prorrata_percentage(snapshot, con_derecho, total, closes_on=date(filing_year, 12, 31))


def check_integer_ceiling_takes_a_fractional_result_to_the_next_unit() -> None:
    """``integer-ceiling`` means "unidad superior": any fraction moves up one unit."""
    assert apply_rounding(Decimal("55.2"), RegistryRoundingCode.INTEGER_CEILING) == Decimal("56")
    assert apply_rounding(Decimal("55.0001"), RegistryRoundingCode.INTEGER_CEILING) == Decimal("56")
    assert apply_rounding(Decimal("55.9"), RegistryRoundingCode.INTEGER_CEILING) == Decimal("56")


def check_integer_ceiling_leaves_an_exact_unit_untouched() -> None:
    """The unidad superior raises a fractional result; it does not inflate an exact one."""
    assert apply_rounding(Decimal("55"), RegistryRoundingCode.INTEGER_CEILING) == Decimal("55")
    assert apply_rounding(Decimal("0"), RegistryRoundingCode.INTEGER_CEILING) == Decimal("0")
    assert apply_rounding(Decimal("100"), RegistryRoundingCode.INTEGER_CEILING) == Decimal("100")


def check_shared_integer_code_is_still_half_up_for_its_other_consumers() -> None:
    """The shared ``integer`` vocabulary must NOT have acquired the new direction.

    ``integer`` is the neutral whole-unit mode used where no provision directs
    a rounding side (the Modelo 123 perceptor-count total). Redefining it to
    round up would silently move every one of those consumers, which is a worse
    defect than the one ``integer-ceiling`` exists to fix.
    """
    assert apply_rounding(Decimal("55.2"), RegistryRoundingCode.INTEGER) == Decimal("55")
    assert apply_rounding(Decimal("55.5"), RegistryRoundingCode.INTEGER) == Decimal("56")
    assert apply_rounding(Decimal("55.9"), RegistryRoundingCode.INTEGER) == Decimal("56")


def check_selected_ratios_discriminate_between_the_two_roundings() -> None:
    """Prove the parity sweep's ratios can actually fail, rather than assuming it.

    Every ``DISCRIMINATING_VOLUMES`` pair must land on a percentage where
    half-up and round-up give different whole units; otherwise the parity test
    below would pass with the defect reinstated.
    """
    for con_derecho, total in DISCRIMINATING_VOLUMES:
        exact = con_derecho * Decimal("100") / total
        half_up = apply_rounding(exact, RegistryRoundingCode.INTEGER)
        ceiling = apply_rounding(exact, RegistryRoundingCode.INTEGER_CEILING)
        assert ceiling == half_up + 1, (
            f"volumes {con_derecho}/{total} give {exact}, on which half-up "
            f"({half_up}) and round-up ({ceiling}) agree — the pair cannot "
            "detect a regression to the shared integer code"
        )


def check_both_live_m303_revisions_declare_the_round_up_code(
    snapshot_of: Callable[..., RegistrySnapshot], filing_year: int
) -> None:
    """Both live revisions must carry ``integer-ceiling`` on the prorrata percentage."""
    snapshot = snapshot_of("303", filing_year=filing_year, period="4T")
    formula = next(entry for entry in snapshot.revision.formulas if entry.id == FORMULA_ID)

    assert formula.rounding == RegistryRoundingCode.INTEGER_CEILING, (
        f"M303 {snapshot.revision.id}: {FORMULA_ID} declares {formula.rounding!r}; "
        "LIVA art. 104.Dos requires the prorrata percentage to be taken to the "
        "unidad superior, so half-up understates the deduction below the half"
    )
    assert "ley-37-1992:art-104" in formula.legal_refs


def check_registry_and_domain_agree_on_the_prorrata_percentage(
    snapshot_of: Callable[..., RegistrySnapshot],
    filing_year: int,
    con_derecho: Decimal,
    total: Decimal,
) -> None:
    """One legal quantity, two implementations, one answer.

    :func:`~domain.iva.compute_prorrata_general` has always applied
    ``ROUND_CEILING`` per art. 104.Dos. The registry formula is the second
    implementation of the same provision, and the two must not be able to
    disagree — the divergence this gate closes was invisible precisely because
    nothing compared them.
    """
    assert registry_percentage(snapshot_of, filing_year, con_derecho, total) == domain_percentage(con_derecho, total)
