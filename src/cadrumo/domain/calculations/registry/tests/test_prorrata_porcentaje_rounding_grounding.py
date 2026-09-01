"""Grounding gate for the rounding DIRECTION of the M303 prorrata percentage.

LIVA art. 104 ("La prorrata general") closes its apartado Dos with a single
sentence that fixes the rounding direction of the deduction percentage::

    La prorrata de deducción resultante de la aplicación de los criterios
    anteriores se redondeará en la unidad superior.

That sentence is carried verbatim as the first ``required_text`` entry of the
``ley-37-1992:art-104`` legal-catalogue entry, whose ``corpus_ref`` resolves
into the bundled consolidated law at the ``#a104`` anchor. It is the only
``redonde*`` clause in the whole of Ley 37/1992, so the direction is not a
matter of interpretation: the percentage goes to the NEXT unit up, never to the
NEAREST one.

The registry declared this formula under the shared ``integer`` rounding code,
which the formula runtime implements as half-up. Half-up and round-up agree
only when the fractional part exceeds one half, and both AEAT manual worked
examples for this scenario (72,72 % and 55,55 %) sit above it — so the two
readings agreed on every figure the corpus could check, and the divergence went
unobserved. On a 55,2 % ratio the half-up reading returned 55 where the law
grants 56, understating the taxpayer's deduction right.

This module pins three things that together make that class of defect visible:
the ``integer-ceiling`` code means what the provision says, the shared
``integer`` code is still half-up for its other consumers, and the registry
engine agrees with the independent :mod:`domain.iva` prorrata authority on
ratios chosen so that the two roundings genuinely disagree.

See Also:
    :class:`~domain.calculations.registry.RegistryRoundingCode`
        Closed rounding-code vocabulary whose ``INTEGER_CEILING`` member
        carries the art. 104.Dos direction.
    :func:`~domain.iva.compute_prorrata_general`
        Independent domain authority for the same legal quantity.
    :class:`~domain.calculations.registry.ModeloRevision`
        Revision whose ``formulas`` carry the declared rounding code.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .....core.casilla_id import CasillaId, validated_casilla_id
from ....iva.prorrata import ProrrataInputs, ProrrataKind, compute_prorrata_general
from ..authority import bundled_authority
from ..bindings import resolve_available_bound_inputs_by_casilla_id
from ..formula_runtime import calculate_registry_snapshot
from ..formula_runtime_ops import apply_rounding
from ..ledger_iva_bindings import resolve_ledger_iva_aggregation_binding_values
from ..schema_rounding import RegistryRoundingCode

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_FORMULA_ID = "modelo-303-iva-prorrata-porcentaje"
_PORCENTAJE_ID: CasillaId = validated_casilla_id("iva.prorrata-porcentaje", surface="test casilla id")
_VOLUMEN_TOTAL_ID: CasillaId = validated_casilla_id("iva.prorrata-volumen-total", surface="test casilla id")
_VOLUMEN_CON_DERECHO_ID: CasillaId = validated_casilla_id(
    "iva.prorrata-volumen-con-derecho",
    surface="test casilla id",
)

#: 2022 resolves to the `2022` revision, 2024 to its early-period epoch.
#: The art. 104.Dos sentence has stood unamended since BOE-A-1992-28740, so it
#: binds both.
#:
#: This named 2020, which resolved to the then-open 2009-2022 span. That span
#: was retired when the revision was renamed to `2022`, so 2020 now resolves to
#: no revision and every case here died on resolution rather than on the
#: rounding code it asserts.
_LIVE_FILING_YEARS = (2022, 2024)

#: (con-derecho, total) volume pairs whose percentage has a fractional part
#: STRICTLY below one half. These are exactly the ratios on which half-up and
#: round-up disagree; ``test_selected_ratios_discriminate_between_the_two_roundings``
#: proves the discrimination rather than assuming it, and rejected a 76,5 %
#: candidate that half-up already rounds up.
_DISCRIMINATING_VOLUMES = (
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
_MANUAL_VOLUMES = (
    (Decimal("32000"), Decimal("44000")),
    (Decimal("25000"), Decimal("45000")),
)

#: A ratio that is already a whole percentage. "Unidad superior" moves a
#: fractional result up; it does not add a unit to an exact one.
_EXACT_VOLUMES = (Decimal("500"), Decimal("1000"))


def _domain_percentage(con_derecho: Decimal, total: Decimal) -> Decimal:
    """The same legal quantity via the independent :mod:`domain.iva` authority."""
    return compute_prorrata_general(
        ProrrataInputs(
            operaciones_con_derecho_deduccion=con_derecho,
            operaciones_sin_derecho_deduccion=total - con_derecho,
        ),
        year=2024,
        kind=ProrrataKind.DEFINITIVA,
    ).percentage


def _registry_percentage(filing_year: int, con_derecho: Decimal, total: Decimal) -> Decimal:
    """The same legal quantity via the real registry snapshot and formula runtime."""
    snapshot = bundled_authority().snapshot("303", filing_year=filing_year, period="4T")
    declared = {binding.id for binding in snapshot.revision.bindings}
    binding_values: dict[str, Decimal] = {
        binding_id: Decimal("100") if binding_id.endswith("state-attribution-ratio") else Decimal("0")
        for binding_id in declared
        & {
            "modelo-303-compensacion-pendiente-anteriores",
            "modelo-303-autoconsumo-promotor-base",
            "modelo-303-profile-state-attribution-ratio",
        }
    }
    binding_values.update(resolve_ledger_iva_aggregation_binding_values(snapshot.revision, ()))
    inputs = {
        **resolve_available_bound_inputs_by_casilla_id(snapshot.revision, binding_values),
        _VOLUMEN_TOTAL_ID: total,
        _VOLUMEN_CON_DERECHO_ID: con_derecho,
    }
    result = calculate_registry_snapshot(
        snapshot,
        inputs=inputs,
        binding_values=binding_values,
        date_context={"filing_period": date(filing_year, 12, 31)},
    )
    return result.values[_PORCENTAJE_ID]


def test_integer_ceiling_takes_a_fractional_result_to_the_next_unit() -> None:
    """``integer-ceiling`` means "unidad superior": any fraction moves up one unit."""
    assert apply_rounding(Decimal("55.2"), RegistryRoundingCode.INTEGER_CEILING) == Decimal("56")
    assert apply_rounding(Decimal("55.0001"), RegistryRoundingCode.INTEGER_CEILING) == Decimal("56")
    assert apply_rounding(Decimal("55.9"), RegistryRoundingCode.INTEGER_CEILING) == Decimal("56")


def test_integer_ceiling_leaves_an_exact_unit_untouched() -> None:
    """The unidad superior raises a fractional result; it does not inflate an exact one."""
    assert apply_rounding(Decimal("55"), RegistryRoundingCode.INTEGER_CEILING) == Decimal("55")
    assert apply_rounding(Decimal("0"), RegistryRoundingCode.INTEGER_CEILING) == Decimal("0")
    assert apply_rounding(Decimal("100"), RegistryRoundingCode.INTEGER_CEILING) == Decimal("100")


def test_shared_integer_code_is_still_half_up_for_its_other_consumers() -> None:
    """The shared ``integer`` vocabulary must NOT have acquired the new direction.

    ``integer`` is the neutral whole-unit mode used where no provision directs
    a rounding side (the Modelo 123 perceptor-count total). Redefining it to
    round up would silently move every one of those consumers, which is a worse
    defect than the one ``integer-ceiling`` exists to fix.
    """
    assert apply_rounding(Decimal("55.2"), RegistryRoundingCode.INTEGER) == Decimal("55")
    assert apply_rounding(Decimal("55.5"), RegistryRoundingCode.INTEGER) == Decimal("56")
    assert apply_rounding(Decimal("55.9"), RegistryRoundingCode.INTEGER) == Decimal("56")


def test_selected_ratios_discriminate_between_the_two_roundings() -> None:
    """Prove the parity sweep's ratios can actually fail, rather than assuming it.

    Every ``_DISCRIMINATING_VOLUMES`` pair must land on a percentage where
    half-up and round-up give different whole units; otherwise the parity test
    below would pass with the defect reinstated.
    """
    for con_derecho, total in _DISCRIMINATING_VOLUMES:
        exact = con_derecho * Decimal("100") / total
        half_up = apply_rounding(exact, RegistryRoundingCode.INTEGER)
        ceiling = apply_rounding(exact, RegistryRoundingCode.INTEGER_CEILING)
        assert ceiling == half_up + 1, (
            f"volumes {con_derecho}/{total} give {exact}, on which half-up "
            f"({half_up}) and round-up ({ceiling}) agree — the pair cannot "
            "detect a regression to the shared integer code"
        )


@pytest.mark.parametrize("filing_year", _LIVE_FILING_YEARS)
def test_both_live_m303_revisions_declare_the_round_up_code(filing_year: int) -> None:
    """Both live revisions must carry ``integer-ceiling`` on the prorrata percentage."""
    snapshot = bundled_authority().snapshot("303", filing_year=filing_year, period="4T")
    formula = next(entry for entry in snapshot.revision.formulas if entry.id == _FORMULA_ID)

    assert formula.rounding == RegistryRoundingCode.INTEGER_CEILING, (
        f"M303 {snapshot.revision.id}: {_FORMULA_ID} declares {formula.rounding!r}; "
        "LIVA art. 104.Dos requires the prorrata percentage to be taken to the "
        "unidad superior, so half-up understates the deduction below the half"
    )
    assert "ley-37-1992:art-104" in formula.legal_refs


@pytest.mark.parametrize("filing_year", _LIVE_FILING_YEARS)
@pytest.mark.parametrize(
    ("con_derecho", "total"),
    (*_DISCRIMINATING_VOLUMES, *_MANUAL_VOLUMES, _EXACT_VOLUMES),
)
def test_registry_and_domain_agree_on_the_prorrata_percentage(
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
    assert _registry_percentage(filing_year, con_derecho, total) == _domain_percentage(con_derecho, total)
