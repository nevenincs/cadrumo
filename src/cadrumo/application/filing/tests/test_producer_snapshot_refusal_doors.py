"""A producer snapshot refusal names whose fault it is: the operator's missing fact or a design fault.

Each refusal is raised by the real snapshot builder and read through the readers the
operation error detail uses, in every shipped locale.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from ....core.errors.error_codes import resolve_error_message
from ....core.modelo import Modelo
from ....core.operator_action_enums import NoRecoveryOutcome
from ....core.result_disposition import ResultDisposition
from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.deadlines.models import IVARegime, RefundAccount, TaxpayerProfile
from ...cli_exception_preconditions import nested_terminal_precondition_verdict
from ..producer_snapshot import (
    M202_UNSUPPORTED_PRODUCER_IDS,
    FilingProducerSnapshot,
    FilingProducerSnapshotError,
    GeneralFilingProfileFacts,
    Modelo111ProfileFacts,
    Modelo202ProducerProfile,
    build_filing_producer_snapshot,
)
from .producer_snapshot_support import (
    TAXPAYER_TAX_ID,
    elections,
    m303_filing_facts,
    m303_profile,
    producer_snapshot_presenter,
    taxpayer_identity,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_LOCALES = ("es", "ca", "en", "hu")


@pytest.fixture(autouse=True)
def _pinned_authority() -> Iterator[None]:
    with bundled_indexed_authority().operation():
        yield


def _build_303(
    disposition: ResultDisposition,
    *,
    refund_account: RefundAccount | None = None,
    account_page_refund_account: bool = False,
) -> FilingProducerSnapshot:
    return build_filing_producer_snapshot(
        modelo=Modelo("303"),
        taxpayer_tax_id=TAXPAYER_TAX_ID,
        taxpayer_identity=taxpayer_identity(),
        presenter=producer_snapshot_presenter(),
        model_profile=m303_profile(),
        elections=elections(disposition),
        amendment_evidence=None,
        refund_account=refund_account,
        charge_account=None,
        m303_filing_facts=m303_filing_facts(),
        account_page_refund_account=account_page_refund_account,
    )


def _assert_words_served_in_every_locale(error: FilingProducerSnapshotError) -> None:
    for locale in _LOCALES:
        message = resolve_error_message(error, locale=locale)
        assert message
        assert "%{" not in message
        assert error.translated_message is not None
        assert message != error.translated_message


def _assert_outcome(error: FilingProducerSnapshotError, outcome: NoRecoveryOutcome) -> None:
    verdict = nested_terminal_precondition_verdict(error)
    assert verdict is not None
    assert verdict.no_recovery_outcome is outcome


@pytest.mark.parametrize(
    ("disposition", "refund_account", "account_page", "reason"),
    [
        (ResultDisposition.DOMICILIACION, None, False, "charge_account_absent"),
        (ResultDisposition.DEVOLUCION, RefundAccount(iban=None), False, "refund_account_absent"),
        (ResultDisposition.NEGATIVA, None, True, "account_page_refund_account_absent"),
    ],
)
def test_an_account_the_export_already_required_is_a_terminal_design_fault(
    disposition: ResultDisposition,
    refund_account: RefundAccount | None,
    account_page: bool,
    reason: str,
) -> None:
    with pytest.raises(FilingProducerSnapshotError) as raised:
        _build_303(disposition, refund_account=refund_account, account_page_refund_account=account_page)
    assert raised.value.context == {"reason": reason}
    _assert_outcome(raised.value, NoRecoveryOutcome.TERMINAL)
    _assert_words_served_in_every_locale(raised.value)


def test_modelo_202_unsupported_producer_facts_are_an_operator_decision() -> None:
    taxpayer_profile = TaxpayerProfile(tax_id=TAXPAYER_TAX_ID, iva=m303_profile(), iva_regime=IVARegime("GENERAL"))
    with pytest.raises(FilingProducerSnapshotError) as raised:
        build_filing_producer_snapshot(
            modelo=Modelo("202"),
            taxpayer_tax_id=TAXPAYER_TAX_ID,
            taxpayer_identity=taxpayer_identity(),
            presenter=producer_snapshot_presenter(),
            model_profile=Modelo202ProducerProfile(taxpayer_profile=taxpayer_profile, activities=()),
            elections=elections(ResultDisposition.INGRESO),
            amendment_evidence=None,
            refund_account=None,
            charge_account=None,
            m303_filing_facts=None,
        )
    assert raised.value.context == {
        "missing_fact_ids": tuple(item.value for item in M202_UNSUPPORTED_PRODUCER_IDS),
        "reason": "m202_producer_facts_unsupported",
    }
    _assert_outcome(raised.value, NoRecoveryOutcome.OPERATOR_DECISION)
    _assert_words_served_in_every_locale(raised.value)


def test_an_undeclared_colegio_concertado_names_the_profile_edit_that_states_it() -> None:
    with pytest.raises(FilingProducerSnapshotError, match="colegio_concertado") as raised:
        build_filing_producer_snapshot(
            modelo=Modelo("111"),
            taxpayer_tax_id=TAXPAYER_TAX_ID,
            taxpayer_identity=taxpayer_identity(),
            presenter=producer_snapshot_presenter(),
            model_profile=Modelo111ProfileFacts(colegio_concertado=None),
            elections=elections(ResultDisposition.NEGATIVA),
            amendment_evidence=None,
            refund_account=None,
            charge_account=None,
            m303_filing_facts=None,
        )
    verdict = nested_terminal_precondition_verdict(raised.value)
    assert verdict is not None
    assert verdict.action is not None
    assert verdict.action.action_id == "operator.profile.edit"
    assert verdict.no_recovery_outcome is None
    assert raised.value.context == {
        "reason": "m111_colegio_concertado_undeclared",
        "profile_path": "withholding.colegio_concertado",
    }
    _assert_words_served_in_every_locale(raised.value)


def test_a_profile_of_the_wrong_kind_is_a_terminal_design_fault() -> None:
    with pytest.raises(FilingProducerSnapshotError, match="Modelo222ProfileFacts") as raised:
        build_filing_producer_snapshot(
            modelo=Modelo("222"),
            taxpayer_tax_id=TAXPAYER_TAX_ID,
            taxpayer_identity=taxpayer_identity(),
            presenter=producer_snapshot_presenter(),
            model_profile=GeneralFilingProfileFacts(),
            elections=elections(ResultDisposition.NEGATIVA),
            amendment_evidence=None,
            refund_account=None,
            charge_account=None,
            m303_filing_facts=None,
        )
    assert raised.value.context == {"reason": "snapshot_inconsistent"}
    _assert_outcome(raised.value, NoRecoveryOutcome.TERMINAL)
    _assert_words_served_in_every_locale(raised.value)
