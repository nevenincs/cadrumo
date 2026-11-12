"""Calculation-input, amendment, review-package, selector, export and wallet refusals open the door of their cause.

Each refusal is raised by the owning code from a real trigger and read the way
the operation error detail reads it, through ``nested_terminal_precondition_verdict``.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from ....core.operator_action_enums import ActionArgumentStatus, ActionConditionality, NoRecoveryOutcome
from ....core.period import Period
from ....domain.attachments.errors import AttachmentValidationError
from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.deadlines.models import IVARegime, TaxpayerProfile
from ....domain.modelos.errors import ModeloError, ModeloValidationError
from ....domain.modelos.filing_record import FilingDeclarationKind
from ...aggregation.invoice_retencion import InvoiceWithholdingEvidenceError
from ...cli_exception_preconditions import nested_terminal_precondition_verdict
from ...operator_actions.models import PreconditionVerdict
from ..action_errors import AmendmentKindNotPermittedError
from ..amendment_kind_resolution import assert_amendment_kind_permitted
from ..calculate_input_validation import (
    ModeloCalculateDecimalInputError,
    ModeloCalculateRelationInputError,
    decimal,
    validated_relation_id,
)
from ..export_amendment_evidence import _aggregate_refusal
from ..export_sink import _path_refusal
from ..iva_wallet_seed import ModeloIvaWalletSeedNegativeAmountError, _require_non_negative_wallet_amount
from ..m303_exonerado_390_applicability_attestation import M303Exonerado390ApplicabilityAttestationAdmission
from ..projection_compare import ModeloCompareNeedTwoYearsError, _comparison_year_pair
from ..registry_resources import reject_unknown_revision
from ..review_package import ReviewPackageIntegrityError, verify_review_package
from ..review_package_recipient_registry import (
    RecipientFingerprintRegister,
    RecipientNotRegisteredError,
    get_recipient_fingerprint,
)
from ..review_package_recipient_registry_ports import RecipientFingerprintRegistryPorts
from ..selectors import ModeloCalculationRevisionSelectorNotFoundError, _latest_revision_with_state
from ..semantic_role_resolution import (
    AmbiguousSemanticRoleCasillaError,
    casilla_id_for_unique_revision_semantic_role,
)
from ..value_presentation import UnknownValuePresentationError, value_presentation_kind
from ..work_capture import ModeloWorkCaptureError, _require_work_capture_process_domain

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _verdict(error: BaseException) -> PreconditionVerdict:
    verdict = nested_terminal_precondition_verdict(error)
    assert verdict is not None
    return verdict


def _bound(verdict: PreconditionVerdict) -> dict[str, object]:
    return {
        binding.argument_name: binding.value if binding.status is ActionArgumentStatus.RESOLVED else None
        for binding in verdict.argument_bindings
    }


def _outcome(verdict: PreconditionVerdict) -> NoRecoveryOutcome:
    assert verdict.action is None
    assert verdict.no_recovery_outcome is not None
    return verdict.no_recovery_outcome


def test_a_malformed_casilla_decimal_opens_the_value_edit_of_that_casilla() -> None:
    """Operator input: the edit binds the refused casilla and leaves value and unit to the operator."""
    with pytest.raises(ModeloCalculateDecimalInputError) as refusal:
        decimal("1e5", flag="--casilla", key="0100")

    verdict = _verdict(refusal.value)
    assert verdict.action is not None
    assert verdict.action.action_id == "operator.modelo.work.set_value"
    assert _bound(verdict)["casilla_id"] == "0100"
    assert verdict.conditionality is ActionConditionality.REQUIRES_ARGUMENTS


def test_a_malformed_binding_decimal_opens_the_override_of_that_binding() -> None:
    with pytest.raises(ModeloCalculateDecimalInputError) as refusal:
        decimal("1,5", flag="--binding", key="some.binding")

    verdict = _verdict(refusal.value)
    assert verdict.action is not None
    assert verdict.action.action_id == "operator.modelo.work.override"
    assert _bound(verdict)["binding_id"] == "some.binding"


def test_a_relation_the_revision_does_not_declare_is_the_operators_decision() -> None:
    with pytest.raises(ModeloCalculateRelationInputError) as refusal:
        validated_relation_id("no-such-relation", set())

    assert _outcome(_verdict(refusal.value)) is NoRecoveryOutcome.OPERATOR_DECISION


def test_an_amendment_kind_the_period_does_not_permit_is_the_operators_decision() -> None:
    year = filing_year_envelope().horizon
    with (
        bundled_indexed_authority().operation() as operation,
        validating_governed_facts(operation),
        pytest.raises(AmendmentKindNotPermittedError) as refusal,
    ):
        assert_amendment_kind_permitted(
            modelo="130", period=Period.from_year_and_code(year, "1T"), amendment_kind=FilingDeclarationKind.SUSTITUTIVA
        )

    assert _outcome(_verdict(refusal.value)) is NoRecoveryOutcome.OPERATOR_DECISION


def test_an_unreadable_review_package_stops_at_the_integrity_boundary(tmp_path: Path) -> None:
    package = tmp_path / "package.zip"
    package.write_bytes(b"not an archive")

    with bundled_indexed_authority().operation() as operation, pytest.raises(ReviewPackageIntegrityError) as refusal:
        verify_review_package(package, operation=operation)

    assert _outcome(_verdict(refusal.value)) is NoRecoveryOutcome.SAFETY


class _EmptyRegister:
    def load(self) -> RecipientFingerprintRegister:
        return RecipientFingerprintRegister(records=())

    def save(self, register: RecipientFingerprintRegister) -> None:
        raise AssertionError("a lookup writes nothing")


def test_an_unregistered_recipient_is_the_operators_decision() -> None:
    ports = RecipientFingerprintRegistryPorts(registry_repository=_EmptyRegister())

    with pytest.raises(RecipientNotRegisteredError) as refusal:
        get_recipient_fingerprint("nobody", ports=ports)

    assert _outcome(_verdict(refusal.value)) is NoRecoveryOutcome.OPERATOR_DECISION


def test_no_revision_in_a_state_opens_the_revisions_of_the_unit() -> None:
    from ....domain.modelos.calculation_revision import CalculationRevisionState

    with pytest.raises(ModeloCalculationRevisionSelectorNotFoundError) as refusal:
        _latest_revision_with_state((), state=CalculationRevisionState.BORRADOR)

    verdict = _verdict(refusal.value)
    assert verdict.action is not None
    assert verdict.action.action_id == "operator.modelo.work.revisions"
    assert verdict.missing_argument_names == ("work_unit_id",)


def test_a_work_capture_from_another_process_incarnation_is_terminal() -> None:
    with pytest.raises(ModeloWorkCaptureError) as refusal:
        _require_work_capture_process_domain("domain-minted-elsewhere")

    assert _outcome(_verdict(refusal.value)) is NoRecoveryOutcome.TERMINAL


def test_an_undeclared_revision_opens_the_description_of_the_modelo() -> None:
    with bundled_indexed_authority().operation() as operation, pytest.raises(ModeloError) as refusal:
        reject_unknown_revision(modelo="303", revision_id="no-such-revision", operation=operation)

    verdict = _verdict(refusal.value)
    assert verdict.action is not None
    assert verdict.action.action_id == "operator.modelo.describe"
    assert _bound(verdict)["modelo"] == "303"


def test_one_year_given_to_a_comparison_is_the_operators_decision() -> None:
    with pytest.raises(ModeloCompareNeedTwoYearsError) as refusal:
        _comparison_year_pair([2030])

    assert _outcome(_verdict(refusal.value)) is NoRecoveryOutcome.OPERATOR_DECISION


def test_a_negative_wallet_amount_is_the_operators_decision() -> None:
    with pytest.raises(ModeloIvaWalletSeedNegativeAmountError) as refusal:
        _require_non_negative_wallet_amount(Decimal("-1"))

    assert _outcome(_verdict(refusal.value)) is NoRecoveryOutcome.OPERATOR_DECISION


def test_an_export_path_the_sink_refuses_is_the_operators_decision() -> None:
    assert _outcome(_verdict(_path_refusal("../outside", "traversal"))) is NoRecoveryOutcome.OPERATOR_DECISION


def test_a_presentation_for_an_undeclared_data_type_is_terminal() -> None:
    with pytest.raises(UnknownValuePresentationError) as refusal:
        value_presentation_kind("no-such-data-type")

    assert _outcome(_verdict(refusal.value)) is NoRecoveryOutcome.TERMINAL


def test_a_role_that_two_casillas_claim_is_terminal() -> None:
    revision = SimpleNamespace(
        id="rev",
        casillas=(
            SimpleNamespace(id="0001", semantic_role="shared.role"),
            SimpleNamespace(id="0002", semantic_role="shared.role"),
        ),
    )

    with pytest.raises(AmbiguousSemanticRoleCasillaError) as refusal:
        casilla_id_for_unique_revision_semantic_role(revision, "shared.role", modelo_id="100")

    assert _outcome(_verdict(refusal.value)) is NoRecoveryOutcome.TERMINAL


def test_a_withholding_evidence_the_capture_refuses_is_the_operators_decision() -> None:
    refusal = InvoiceWithholdingEvidenceError("invalid_evidence")

    verdict = _verdict(refusal)
    assert _outcome(verdict) is NoRecoveryOutcome.OPERATOR_DECISION
    assert verdict.evidence[0].values["refusal_code"] == "invalid_evidence"


def test_an_attachment_identity_that_contradicts_its_digest_is_terminal() -> None:
    with pytest.raises(AttachmentValidationError) as refusal:
        M303Exonerado390ApplicabilityAttestationAdmission(attachment_id="a" * 64, sha256="b" * 64)

    assert _outcome(_verdict(refusal.value)) is NoRecoveryOutcome.TERMINAL


def test_an_aggregate_refusal_for_an_unstated_tax_id_opens_the_profile_questions() -> None:
    refusal = _aggregate_refusal(ModeloValidationError("original"), tax_id=None, receipt_matches=lambda _tax_id: True)

    verdict = _verdict(refusal)
    assert verdict.action is not None
    assert verdict.action.action_id == "operator.profile.edit"
    assert verdict.evidence[0].values["missing_fields"] == "identity.tax_id"


def test_an_aggregate_refusal_for_a_foreign_justificante_is_the_operators_decision() -> None:
    with bundled_indexed_authority().operation() as operation, validating_governed_facts(operation):
        tax_id = TaxpayerProfile(tax_id="X0001500M", iva_regime=IVARegime("GENERAL")).tax_id
    refusal = _aggregate_refusal(
        ModeloValidationError("original"), tax_id=tax_id, receipt_matches=lambda _tax_id: False
    )

    assert _outcome(_verdict(refusal)) is NoRecoveryOutcome.OPERATOR_DECISION
