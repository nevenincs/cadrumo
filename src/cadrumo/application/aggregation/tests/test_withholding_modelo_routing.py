"""The withholding routes are read from the published fact, through each real consumer."""

from __future__ import annotations

import pytest

from cadrumo.application.aggregation.ledger_payment_withholding import (
    LedgerPaymentWithholdingEvidenceRequest,
)
from cadrumo.application.aggregation.withholding_modelo_routing import (
    INVOICE_EVIDENCED_INCOME_KINDS,
    LEDGER_PAID_INCOME_KINDS,
    annual_source_observations_modelo,
    annual_withholding_composition,
    invoice_evidence_modelos,
    ledger_payment_modelos,
    modelo_for_income_kind,
    periodic_withholding_modelos,
)
from cadrumo.application.aggregation.withholding_producer import WithholdingProducerError, _modelo_for
from cadrumo.application.aggregation.withholding_recognition import WithholdingIncomeKind
from cadrumo.core.aggregation import RetencionScheme
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.calculations.registry.form_codes import resolve_form_codes

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _declared() -> dict[str, str]:
    with bundled_indexed_authority().operation() as operation:
        return dict(resolve_form_codes("withholding-modelo-routing", authority=operation).entries)


def test_each_route_a_consumer_reads_is_the_declared_entry() -> None:
    declared = _declared()
    assert ",".join(periodic_withholding_modelos()) == declared["periodic.modelos"]
    for kind in WithholdingIncomeKind:
        assert modelo_for_income_kind(kind) == declared.get(f"income_kind.{kind.value}")


def test_evidence_scopes_follow_the_routes_of_the_kinds_they_prove() -> None:
    declared = _declared()
    assert ledger_payment_modelos() == {declared[f"income_kind.{kind.value}"] for kind in LEDGER_PAID_INCOME_KINDS}
    assert invoice_evidence_modelos() == {
        declared[f"income_kind.{kind.value}"] for kind in INVOICE_EVIDENCED_INCOME_KINDS
    }


def test_every_routed_modelo_is_periodic_and_published() -> None:
    periodic = set(periodic_withholding_modelos())
    routed = {modelo_for_income_kind(kind) for kind in WithholdingIncomeKind} - {None}
    assert routed
    assert routed <= periodic
    with bundled_indexed_authority().operation() as operation:
        assert periodic <= set(operation.modelo_ids())


def test_a_modelo_no_route_names_reads_its_own_window() -> None:
    composition = annual_withholding_composition("no-such-form")
    assert composition.periodic_source is None
    assert annual_source_observations_modelo("no-such-form") is None


def test_each_annual_route_draws_on_a_periodic_modelo() -> None:
    periodic = set(periodic_withholding_modelos())
    declared = _declared()
    annual = [key.rsplit(".", 1)[1] for key in declared if key.startswith("annual.periodic_percepciones.")]
    annual += [key.rsplit(".", 1)[1] for key in declared if key.startswith("annual.capital_disclosure_retenciones.")]
    assert annual
    for modelo in annual:
        source = annual_withholding_composition(modelo).periodic_source
        assert source is not None
        assert source.value in periodic


def test_the_producer_refuses_a_scheme_of_another_income_kind() -> None:
    scheme = RetencionScheme("rendimientos_trabajo")
    with pytest.raises(WithholdingProducerError, match="scheme_income_kind_mismatch") as raised:
        _modelo_for(WithholdingIncomeKind.URBAN_RENT, scheme)
    assert raised.value.refusal_code == "scheme_income_kind_mismatch"


def test_a_ledger_payment_request_refuses_a_kind_its_payment_cannot_prove() -> None:
    assert WithholdingIncomeKind.URBAN_RENT not in LEDGER_PAID_INCOME_KINDS
    with pytest.raises(ValueError, match="work or ordinary movable capital"):
        LedgerPaymentWithholdingEvidenceRequest._only_ledger_paid_income(WithholdingIncomeKind.URBAN_RENT)
