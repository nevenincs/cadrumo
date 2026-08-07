"""Reachability probes: a binding that can never match anything is refused at build.

The silent-zero class this Wave targets: a binding whose selector matches no
observation resolves to zero for every taxpayer, forever, and is
indistinguishable from a taxpayer who genuinely had none of that thing. No
runtime ledger data can surface it, because the defect IS the absence of
matches.

These tests do two jobs. They mutation-prove the IVA probe reddens on a
selector retargeted to match nothing, and they pin — as an executable
statement rather than a comment — which families a selector-derived probe can
and cannot bite for. The second is the one worth reading: a probe that cannot
fail is worse than no probe, because it reports green forever while looking
like coverage.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from .....core import Modelo
from ....iva import (
    IvaCashAccountingTreatment,
    IvaCategory,
    IvaExemptionArticle,
    IvaFlowDirection,
    IvaRateKind,
)
from .._errors import RegistryValidationError
from .._ledger_bindings import (
    _iva_build_matcher,
    _iva_reachability_probe,
    _IvaLedgerSelector,
    _renta_gastos_pago_fraccionado_build_matcher,
    _RentaLedgerGastosPagoFraccionadoSelector,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_CATEGORY = next(iter(IvaCategory))
_RATE_KIND = next(iter(IvaRateKind))


def _iva_selector(
    *,
    cash_accounting_treatments: tuple[IvaCashAccountingTreatment, ...],
) -> _IvaLedgerSelector:
    """Build an otherwise-valid IVA selector varying only the unbounded axis."""
    return _IvaLedgerSelector(
        categories=(_CATEGORY,),
        rate_kinds=(_RATE_KIND,),
        flow_direction=IvaFlowDirection.REPERCUTIDO,
        cash_accounting_treatments=cash_accounting_treatments,
        fact="iva_amount_sum",
    )


def test_a_reachable_iva_selector_passes_the_probe() -> None:
    """The positive control.

    Without it, a probe that refused every selector would satisfy the
    mutation proof below while blocking every real binding in the registry.
    """
    _iva_reachability_probe(_iva_selector(cash_accounting_treatments=(IvaCashAccountingTreatment.NONE,)))


def test_the_probe_reddens_on_a_selector_that_can_match_nothing() -> None:
    """The mutation proof: retarget the selector to match nothing, the probe fires.

    ``cash_accounting_treatments`` is the mutation site because it is the only
    set-valued axis on this selector carrying no ``MinLen`` — an empty tuple is
    constructible today. The matcher tests
    ``observation.cash_accounting_treatment in set(...)``, so an empty set
    rejects every treatment the enum defines.

    Mutating the SELECTOR rather than the production matcher is deliberate:
    it needs no edit to a tracked file, so a peer's sweep cannot commit the
    mutation and a crashed run leaves no residue.
    """
    with pytest.raises(RegistryValidationError, match="matches no constructible observation shape"):
        _iva_reachability_probe(_iva_selector(cash_accounting_treatments=()))


def test_the_unmatched_selector_really_matches_every_treatment_never() -> None:
    """Prove the probe's premise independently of the probe.

    The mutation proof above shows the probe raises. This shows WHY: driven
    through the real matcher, the empty-set selector rejects every treatment
    the enum defines. Without this, the probe could be raising for an
    unrelated reason and the test above would not notice.
    """
    matcher = _iva_build_matcher(_iva_selector(cash_accounting_treatments=()))
    verdicts = {
        treatment: matcher(
            _StubIvaObservation(
                category=_CATEGORY,
                rate_kind=_RATE_KIND,
                flow_direction=IvaFlowDirection.REPERCUTIDO,
                cash_accounting_treatment=treatment,
                exemption_article=None,
            ),
        )
        for treatment in IvaCashAccountingTreatment
    }
    assert not any(verdicts.values()), f"expected no treatment to match, got {verdicts}"


class _StubIvaObservation:
    """Minimal stand-in carrying only the five axes the IVA matcher reads.

    Satisfies ``IvaSelectorAxesProtocol`` structurally, which is what makes it
    a legitimate stand-in for the full observation record here.
    """

    def __init__(
        self,
        *,
        category: IvaCategory,
        rate_kind: IvaRateKind,
        flow_direction: IvaFlowDirection,
        cash_accounting_treatment: IvaCashAccountingTreatment,
        exemption_article: IvaExemptionArticle | None,
        applied_rate: Decimal | None = None,
    ) -> None:
        self.category = category
        self.rate_kind = rate_kind
        self.flow_direction = flow_direction
        self.cash_accounting_treatment = cash_accounting_treatment
        self.exemption_article = exemption_article
        # Defaults to the genuinely-unknown rate, which is the shape these
        # tests exercise: they vary the cash-accounting axis and must not
        # accidentally also constrain the rate filter.
        self.applied_rate = applied_rate


def test_a_casilla_keyed_selector_probe_is_structurally_unable_to_fail() -> None:
    """State the limit as an executable fact, not a comment.

    A selector-derived probe only bites where the matcher tests membership in
    a set the selector declares. Where the matcher tests scalar EQUALITY
    against a field the probe itself copies from that same selector, the
    probe is tautological: it asks whether ``x == x``.

    The renta gastos pago-fraccionado family is exactly that shape — its
    matcher compares ``observation.target_casilla_id == selector.target_casilla_id``
    — so its probe passes for every selector, including a nonsense casilla id.
    This is asserted rather than described so that giving that family a real
    matcher (one testing a declared set, or cross-checking the casilla against
    the revision) reddens this test and forces the limit statement to be
    rewritten instead of quietly outliving its truth.

    The meaningful reachability question for a casilla-keyed family is whether
    the target casilla exists on the revision, which is a different check with
    a different input, and is where that guarantee actually lives.
    """
    for casilla_id in ("02", "9999", "definitely-not-a-real-casilla"):
        selector = _RentaLedgerGastosPagoFraccionadoSelector(
            modelo=Modelo.M130,
            target_casilla_id=casilla_id,
            fact="deductible_amount_sum",
        )
        matcher = _renta_gastos_pago_fraccionado_build_matcher(selector)
        probe = _StubCasillaObservation(target_casilla_id=selector.target_casilla_id)
        assert matcher(probe), (
            f"the casilla-keyed matcher rejected a probe built from its own selector "
            f"({casilla_id!r}); if the match rule now tests something the probe does not "
            "copy, this family's probe has become capable of failing and this limit "
            "statement must be rewritten rather than relaxed"
        )


class _StubCasillaObservation:
    """Minimal stand-in for the attributes the casilla-keyed matcher reads.

    Carries ``deductible_amount`` as well as the casilla id: the matcher only
    reads the id, but the protocol declares both, and a stub that satisfies
    the protocol only by accident is the kind of stand-in that stops being
    valid the moment the matcher reads its second field.
    """

    def __init__(self, *, target_casilla_id: str, deductible_amount: Decimal = Decimal("0")) -> None:
        self.target_casilla_id = target_casilla_id
        self.deductible_amount = deductible_amount
