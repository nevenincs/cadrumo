"""Validating a binding's registry vocabulary must never read the published bundle.

A ``ledger_iva_aggregation`` binding names IVA rate tiers, and checking that
those tiers are registry-declared means resolving a governed fact. Resolving it
through the published authority is what wedged every process that validated a
revision: decoding the artifact validates the document it just read while
holding the shared-artifact lock, so a validator asking for the bundle asked a
non-reentrant lock for the artifact being decoded, and the process stopped with
no error and no output.

These tests pin the replacement. The rate-kind check reads the governed facts
the validation has in scope -- the candidate being compiled, or the facts
carried by the document being decoded -- and refuses when none is in scope
rather than reaching for the bundle. The reader refuses a re-entrant read for
the same reason: the defect is a validator on the wrong layer, not a lock that
should have been reentrant.
"""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from ....iva.flow import IvaFlowDirection
from ....iva.schema import (
    IvaCashAccountingTreatment,
    IvaCategory,
    IvaLedgerObservationRole,
    IvaRateKind,
)
from ..errors import RegistryValidationError
from ..facts.schema import GovernedFact, GovernedFactCatalogue
from ..governed_fact_scope import CandidateFactAuthority, governed_facts_in_scope, validating_governed_facts
from ..iva_flow_catalogue import require_iva_flow_direction
from ..iva_rate_kind_catalogue import require_registry_declared_iva_rate_kind
from ..ledger_iva_bindings import LedgerIvaProvider

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_LEGAL_ID = "ley-37-1992:art-90"
_EFFECTIVE = date(2025, 6, 1)

# A deliberately narrower vocabulary than the shipped registry declares: the
# reduced and super-reduced tiers are absent, so a test that accepts them proves
# the check consulted something other than the facts it was given.
_SCOPED_ENTRIES = (
    {"key": "rate_kind.order", "value": "general,zero,exempt"},
    {"key": "rate_kind.positive_order", "value": "general"},
    {"key": "rate_kind.zero_token", "value": "zero"},
    {"key": "rate_kind.exempt_token", "value": "exempt"},
    {"key": "rate_kind.non_rate_token", "value": "not_subject"},
    {"key": "rate_kind.general.value", "value": "general"},
    {"key": "rate_kind.general.description", "value": "tipo general"},
    {"key": "rate_kind.general.category", "value": "domestic_general"},
    {"key": "rate_kind.zero.value", "value": "zero"},
    {"key": "rate_kind.zero.description", "value": "tipo cero"},
    {"key": "rate_kind.zero.category", "value": "domestic_zero"},
    {"key": "rate_kind.exempt.value", "value": "exempt"},
    {"key": "rate_kind.exempt.description", "value": "operacion exenta"},
    {"key": "rate_kind.exempt.category", "value": "domestic_exempt"},
)


# The binding also names cash-accounting treatments, which is a second governed
# vocabulary resolved the same way; the candidate declares it so the positive
# case exercises a whole provider rather than one field in isolation.
_SCOPED_CASH_ENTRIES = (
    {"key": "cash_accounting.order", "value": "none,taxpayer_regime,supplier_regime"},
    {"key": "cash_accounting.none_token", "value": "none"},
    {"key": "cash_accounting.supplier_regime_token", "value": "supplier_regime"},
    {"key": "cash_accounting.none.value", "value": "none"},
    {"key": "cash_accounting.none.description", "value": "sin criterio de caja"},
    {"key": "cash_accounting.taxpayer_regime.value", "value": "taxpayer_regime"},
    {"key": "cash_accounting.taxpayer_regime.description", "value": "acogido al criterio de caja"},
    {"key": "cash_accounting.supplier_regime.value", "value": "supplier_regime"},
    {"key": "cash_accounting.supplier_regime.description", "value": "proveedor acogido al criterio de caja"},
)

_SCOPED_FLOW_ENTRIES = (
    {"key": "flow_direction.order", "value": "repercutido,soportado,inversion_sujeto_pasivo,operacion_con_inversion"},
    {"key": "flow_direction.issued_token", "value": "repercutido"},
    {"key": "flow_direction.received_token", "value": "soportado"},
    {"key": "flow_direction.recipient_reverse_charge_token", "value": "inversion_sujeto_pasivo"},
    {"key": "flow_direction.supplier_reverse_charge_token", "value": "operacion_con_inversion"},
    {"key": "flow_direction.repercutido.value", "value": "repercutido"},
    {"key": "flow_direction.repercutido.description", "value": "output"},
    {"key": "flow_direction.repercutido.legal_refs", "value": _LEGAL_ID},
    {"key": "flow_direction.repercutido.settlement_sides", "value": "devengada"},
    {"key": "flow_direction.soportado.value", "value": "soportado"},
    {"key": "flow_direction.soportado.description", "value": "input"},
    {"key": "flow_direction.soportado.legal_refs", "value": _LEGAL_ID},
    {"key": "flow_direction.soportado.settlement_sides", "value": "deducible"},
    {"key": "flow_direction.inversion_sujeto_pasivo.value", "value": "inversion_sujeto_pasivo"},
    {"key": "flow_direction.inversion_sujeto_pasivo.description", "value": "recipient reverse charge"},
    {"key": "flow_direction.inversion_sujeto_pasivo.legal_refs", "value": _LEGAL_ID},
    {"key": "flow_direction.inversion_sujeto_pasivo.settlement_sides", "value": "devengada,deducible"},
    {"key": "flow_direction.operacion_con_inversion.value", "value": "operacion_con_inversion"},
    {"key": "flow_direction.operacion_con_inversion.description", "value": "supplier reverse charge"},
    {"key": "flow_direction.operacion_con_inversion.legal_refs", "value": _LEGAL_ID},
    {"key": "flow_direction.operacion_con_inversion.settlement_sides", "value": "none"},
    {"key": "flow_direction.settlement_side_order", "value": "devengada,deducible"},
    {"key": "flow_direction.no_settlement_token", "value": "none"},
    {"key": "flow_direction.settlement_side.devengada.value", "value": "devengada"},
    {"key": "flow_direction.settlement_side.devengada.description", "value": "output"},
    {"key": "flow_direction.settlement_side.devengada.legal_refs", "value": _LEGAL_ID},
    {"key": "flow_direction.settlement_side.deducible.value", "value": "deducible"},
    {"key": "flow_direction.settlement_side.deducible.description", "value": "input"},
    {"key": "flow_direction.settlement_side.deducible.legal_refs", "value": _LEGAL_ID},
)


def _mapping_fact(fact_id: str, *, date_axis: str, entries: tuple[dict[str, str], ...]) -> GovernedFact:
    return GovernedFact.model_validate(
        {
            "fact_id": fact_id,
            "family": "mapping",
            "provider_id": "scope-fixture",
            "variants": (
                {
                    "variant_id": f"{fact_id}:scope-fixture",
                    "date_axis": date_axis,
                    "valid_from": date(2020, 1, 1),
                    "legal_refs": (_LEGAL_ID,),
                    "review_status": "agent_reviewed",
                    "ownership": "authored",
                    "payload": {"kind": "mapping", "entries": entries},
                },
            ),
        },
    )


def _scoped_facts() -> CandidateFactAuthority:
    """Build a candidate fact authority over a narrow registry vocabulary."""
    facts = (
        _mapping_fact("iva-rate-slot-catalogue", date_axis="devengo_date", entries=_SCOPED_ENTRIES),
        _mapping_fact(
            "iva-statutory-schema-vocabulary",
            date_axis="filing_period",
            entries=_SCOPED_CASH_ENTRIES,
        ),
        _mapping_fact(
            "iva-invoice-classification-catalogue",
            date_axis="filing_period",
            entries=_SCOPED_FLOW_ENTRIES,
        ),
    )
    return CandidateFactAuthority(GovernedFactCatalogue(facts={fact.fact_id: fact for fact in facts}))


def _provider_payload(rate_kinds: tuple[IvaRateKind, ...], *, flow_direction: IvaFlowDirection) -> dict[str, object]:
    return {
        "categories": (IvaCategory("domestic_general"),),
        "rate_kinds": rate_kinds,
        "flow_direction": flow_direction,
        "observation_roles": (IvaLedgerObservationRole("settlement"),),
        "cash_accounting_treatments": (IvaCashAccountingTreatment("none"),),
    }


def _projected_flow() -> IvaFlowDirection:
    return require_iva_flow_direction("repercutido", effective_date=_EFFECTIVE)


def test_a_rate_kind_declared_by_the_scoped_facts_is_accepted() -> None:
    with validating_governed_facts(_scoped_facts()):
        assert require_registry_declared_iva_rate_kind("general", effective_date=_EFFECTIVE) == IvaRateKind("general")


def test_a_rate_kind_the_scoped_facts_do_not_declare_is_refused() -> None:
    """The scoped facts decide, so a tier they omit is refused even though the enum has it."""
    with validating_governed_facts(_scoped_facts()), pytest.raises(RegistryValidationError, match="not declared"):
        require_registry_declared_iva_rate_kind(IvaRateKind("reduced"), effective_date=_EFFECTIVE)


def test_validation_outside_a_scope_refuses_instead_of_reading_the_published_authority() -> None:
    assert governed_facts_in_scope() is None
    with pytest.raises(RegistryValidationError, match="published authority artifact"):
        require_registry_declared_iva_rate_kind("general", effective_date=_EFFECTIVE)


def test_a_binding_validates_its_rate_tiers_against_the_scoped_facts() -> None:
    """The real provider model, not a stand-in, resolves through the scope."""
    with validating_governed_facts(_scoped_facts()):
        provider = LedgerIvaProvider.model_validate(
            _provider_payload((IvaRateKind("general"),), flow_direction=_projected_flow())
        )

    assert provider.rate_kinds == (IvaRateKind("general"),)


def test_a_binding_declaring_an_undeclared_rate_tier_is_refused() -> None:
    with validating_governed_facts(_scoped_facts()), pytest.raises(ValidationError) as refusal:
        LedgerIvaProvider.model_validate(
            _provider_payload((IvaRateKind("super_reduced"),), flow_direction=_projected_flow())
        )

    assert "not declared by the facts registry" in str(refusal.value)


def test_a_binding_validated_outside_a_scope_never_reaches_the_bundle() -> None:
    """Absence of scoped facts is a refusal, which is what keeps the reader out of the loop."""
    with validating_governed_facts(_scoped_facts()):
        flow_direction = _projected_flow()
    with pytest.raises(ValidationError) as refusal:
        LedgerIvaProvider.model_validate(_provider_payload((IvaRateKind("general"),), flow_direction=flow_direction))

    message = str(refusal.value)
    assert "published authority artifact" in message
    assert "rate_kinds" in message
