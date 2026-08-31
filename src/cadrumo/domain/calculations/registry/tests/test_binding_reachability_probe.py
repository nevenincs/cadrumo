"""Reachability probes: a binding that can never match anything is refused at build.

The silent-zero class this guards against: a binding whose selector matches no
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
from pydantic import ValidationError

from .....core.modelo import Modelo
from ....iva.flow import IvaFlowDirection
from ....iva.schema import (
    IvaCashAccountingTreatment,
    IvaCategory,
    IvaExemptionArticle,
    IvaLedgerObservationRole,
    IvaRateKind,
)
from ..ledger_iva_bindings import (
    _iva_build_matcher,
    _iva_reachability_probe,
    _IvaLedgerSelector,
)
from ..ledger_renta_gastos_pago_fraccionado_bindings import (
    _renta_gastos_pago_fraccionado_build_matcher,
    _RentaLedgerGastosPagoFraccionadoSelector,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_CATEGORY = next(iter(IvaCategory))
_RATE_KIND = next(iter(IvaRateKind))


def _iva_selector(
    *,
    cash_accounting_treatments: tuple[IvaCashAccountingTreatment, ...] = (IvaCashAccountingTreatment.NONE,),
    observation_roles: tuple[IvaLedgerObservationRole, ...] = (IvaLedgerObservationRole.SETTLEMENT,),
) -> _IvaLedgerSelector:
    """Build an otherwise-valid IVA selector with explicit role and treatment policies."""
    return _IvaLedgerSelector(
        categories=(_CATEGORY,),
        rate_kinds=(_RATE_KIND,),
        flow_direction=IvaFlowDirection.REPERCUTIDO,
        cash_accounting_treatments=cash_accounting_treatments,
        observation_roles=observation_roles,
        fact="iva_amount_sum",
    )


def test_a_reachable_iva_selector_passes_the_probe() -> None:
    """The positive control.

    Without it, a probe that refused every selector would satisfy the
    mutation proof below while blocking every real binding in the registry.
    """
    _iva_reachability_probe(_iva_selector())


def test_iva_selector_refuses_an_implicit_observation_role() -> None:
    """A selector cannot silently acquire a monetary or information role."""
    with pytest.raises(ValidationError, match="observation_roles"):
        _IvaLedgerSelector.model_validate(
            {
                "categories": (_CATEGORY,),
                "rate_kinds": (_RATE_KIND,),
                "flow_direction": IvaFlowDirection.REPERCUTIDO,
                "cash_accounting_treatments": (IvaCashAccountingTreatment.NONE,),
                "fact": "iva_amount_sum",
            },
        )


def test_iva_selector_role_policy_isolates_operation_information_from_settlement() -> None:
    """The real matcher rejects a role mutation while keeping the affiliation unchanged."""
    matcher = _iva_build_matcher(
        _iva_selector(
            cash_accounting_treatments=(IvaCashAccountingTreatment.SUPPLIER_REGIME,),
            observation_roles=(IvaLedgerObservationRole.OPERATION_INFORMATIONAL,),
        ),
    )
    operation_information = _MinimalIvaObservation(
        category=_CATEGORY,
        rate_kind=_RATE_KIND,
        flow_direction=IvaFlowDirection.REPERCUTIDO,
        cash_accounting_treatment=IvaCashAccountingTreatment.SUPPLIER_REGIME,
        observation_role=IvaLedgerObservationRole.OPERATION_INFORMATIONAL,
        exemption_article=None,
    )

    assert matcher(operation_information)
    assert not matcher(
        _MinimalIvaObservation(
            category=_CATEGORY,
            rate_kind=_RATE_KIND,
            flow_direction=IvaFlowDirection.REPERCUTIDO,
            cash_accounting_treatment=IvaCashAccountingTreatment.SUPPLIER_REGIME,
            observation_role=IvaLedgerObservationRole.SETTLEMENT,
            exemption_article=None,
        ),
    )


class _MinimalIvaObservation:
    """Minimal stand-in carrying only the six axes the IVA matcher reads.

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
        observation_role: IvaLedgerObservationRole,
        exemption_article: IvaExemptionArticle | None,
        applied_rate: Decimal | None = None,
    ) -> None:
        self.category = category
        self.rate_kind = rate_kind
        self.flow_direction = flow_direction
        self.cash_accounting_treatment = cash_accounting_treatment
        self.observation_role = observation_role
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

    Reconciled with its apparent opposite
    -------------------------------------
    ``test_reachability_probe_is_not_tautological_against_a_mistyped_casilla_id``
    (in ``test_ledger_renta_gastos_pago_fraccionado_binding.py``) asserts that
    this same probe is NOT tautological. Both are true, and a reader meeting
    one without the other will think the codebase contradicts itself.

    They test different subjects. That test builds a DELIBERATELY MISTYPED
    observation -- an ``int`` casilla id where the registry's is always a
    ``str`` -- and proves the MATCHER discriminates by type rather than
    coercing the digits equal. That is a real and worthwhile property of the
    matcher.

    This test is about the PROBE's own path: the observation the probe itself
    constructs copies ``target_casilla_id`` straight off the selector, with the
    selector's own type, so the comparison the validator actually performs can
    never fail. A matcher that discriminates correctly is still asked a
    question with only one possible answer.

    So: the matcher is honest, and the probe still cannot bite. Fixing the
    second does not follow from having proved the first.
    """
    for casilla_id in ("02", "9999", "definitely-not-a-real-casilla"):
        selector = _RentaLedgerGastosPagoFraccionadoSelector(
            modelo=Modelo.M130,
            target_casilla_id=casilla_id,
            fact="deductible_amount_sum",
        )
        matcher = _renta_gastos_pago_fraccionado_build_matcher(selector)
        probe = _MinimalCasillaObservation(target_casilla_id=selector.target_casilla_id)
        assert matcher(probe), (
            f"the casilla-keyed matcher rejected a probe built from its own selector "
            f"({casilla_id!r}); if the match rule now tests something the probe does not "
            "copy, this family's probe has become capable of failing and this limit "
            "statement must be rewritten rather than relaxed"
        )


class _MinimalCasillaObservation:
    """Minimal stand-in for the attributes the casilla-keyed matcher reads.

    Carries ``deductible_amount`` as well as the casilla id: the matcher only
    reads the id, but the protocol declares both, and a stub that satisfies
    the protocol only by accident is the kind of stand-in that stops being
    valid the moment the matcher reads its second field.
    """

    def __init__(self, *, target_casilla_id: str, deductible_amount: Decimal = Decimal("0")) -> None:
        self.target_casilla_id = target_casilla_id
        self.deductible_amount = deductible_amount
