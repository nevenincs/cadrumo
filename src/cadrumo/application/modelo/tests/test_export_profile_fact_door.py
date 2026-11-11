"""An export that needs a fact about the filer gives the door to state it, and a guard the design owns reads as integrity.

Each refusal is raised by the real renderer function and passed through the
export boundary, so the served words, the door and the next step are read from
the error the operation would report.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest

from ....core.errors.error_codes import ErrorCategory, get_registered_error_code, resolve_error_message
from ....core.external_constants import OutputLanguage
from ....core.filing_producer_key import FilingProducerKey
from ....core.modelo import Modelo
from ....core.operator_action_enums import NoRecoveryOutcome
from ....core.period import Period
from ....domain.calculations.registry.export_semantics import ExportComputedKey
from ....domain.calculations.registry.schema_exports import ExportFieldDefinition, FilingEnvelopePrefixRole
from ....domain.filing.declared_party_name_filing import DECLARED_PARTY_NAME_DOOR_ACTION_ID
from ....domain.filing.errors import (
    FilingExportDeclaredPartyNameMissingError,
    FilingExportDesignIntegrityError,
    FilingExportProfileFactMissingError,
)
from ....domain.filing.schema import ModeloDraft
from ....domain.modelos.errors import ModeloExportDeclaredPartyNameError
from ...cli_exception_preconditions import nested_terminal_precondition_verdict
from ...filing.export_envelope import render_envelope_prefix_field
from ...filing.producer_snapshot import FilingProducerSnapshot
from ...filing.record_field_renderer import COMPUTED_VALUE_PRODUCERS, header_field_value
from ...operations.next_step import OperationOpenProfileFieldStepV1, error_next_step
from ..action_errors import ModeloProfileReadinessError
from ..export import export_write_failure
from ..export_contracts import ModeloExportCommand

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_LOCALES = ("es", "ca", "en", "hu")
_PROFILE_EDIT_ACTION = "operator.profile.edit"


def _required_field(producer_key: FilingProducerKey) -> ExportFieldDefinition:
    return ExportFieldDefinition.model_validate(
        {
            "id": "probe-field",
            "offset": 1,
            "length": 20,
            "kind": "header",
            "producer_key": producer_key,
            "data_type": "text",
            "required": True,
            "padding": "right_space",
            "justification": "left",
            "signed": False,
            "legal_refs": ("orden-eha-3111-2009:art-1",),
            "source_refs": ("aeat-dr-390-2025",),
        }
    )


def _refusal(producer_key: FilingProducerKey) -> FilingExportProfileFactMissingError:
    with pytest.raises(FilingExportProfileFactMissingError) as refused:
        header_field_value(_required_field(producer_key), {})
    return refused.value


def _command() -> ModeloExportCommand:
    return ModeloExportCommand.model_construct(calculation_revision_id="revision-1")


def test_a_blank_identity_fact_refuses_with_the_profile_edit_door_and_the_fact_it_names() -> None:
    failure = export_write_failure(_command(), _refusal(FilingProducerKey.TAXPAYER_GIVEN_NAME))

    assert isinstance(failure, ModeloProfileReadinessError)
    assert get_registered_error_code(failure).code == "REFUSED_MODELO_PROFILE_READINESS"
    verdict = nested_terminal_precondition_verdict(failure)
    assert verdict is not None
    assert verdict.action is not None
    assert verdict.action.action_id == _PROFILE_EDIT_ACTION
    assert verdict.evidence[0].values["missing_fields"] == "identity.name"


def test_a_blank_identity_fact_offers_opening_the_profile_detail_in_the_refusals_language() -> None:
    failure = export_write_failure(_command(), _refusal(FilingProducerKey.TAXPAYER_GIVEN_NAME))

    step = error_next_step(failure, OutputLanguage.EN)

    assert isinstance(step, OperationOpenProfileFieldStepV1)
    assert step.path == "identity.name"


def test_a_name_read_from_two_facts_names_both_and_opens_the_first() -> None:
    failure = export_write_failure(_command(), _refusal(FilingProducerKey.TAXPAYER_SURNAMES_OR_LEGAL_NAME))

    verdict = nested_terminal_precondition_verdict(failure)
    assert verdict is not None
    assert verdict.evidence[0].values["missing_fields"] == "identity.surnames, identity.legal_name"
    step = error_next_step(failure, OutputLanguage.EN)
    assert isinstance(step, OperationOpenProfileFieldStepV1)
    assert step.path == "identity.surnames"


@pytest.mark.parametrize("locale", _LOCALES)
def test_the_boundary_keeps_the_served_words_naming_the_fact(locale: str) -> None:
    failure = export_write_failure(_command(), _refusal(FilingProducerKey.TAXPAYER_TAX_ID))

    message = resolve_error_message(failure, locale=locale)

    assert "identity.tax_id" in message
    assert "%{" not in message


def test_a_producer_fact_no_profile_question_states_refuses_with_an_operator_decision_and_no_step() -> None:
    failure = export_write_failure(_command(), _refusal(FilingProducerKey.CONTACT_PERSON_EMAIL))

    verdict = nested_terminal_precondition_verdict(failure)
    assert verdict is not None
    assert verdict.action is None
    assert verdict.no_recovery_outcome is NoRecoveryOutcome.OPERATOR_DECISION
    assert error_next_step(failure, OutputLanguage.EN) is None
    assert FilingProducerKey.CONTACT_PERSON_EMAIL.value in resolve_error_message(failure, locale="en")


def _prefix_refusal(role: FilingEnvelopePrefixRole) -> FilingExportDesignIntegrityError:
    with pytest.raises(FilingExportDesignIntegrityError) as refused:
        render_envelope_prefix_field(
            role,
            length=1,
            modelo=Modelo("303"),
            period=Period.model_construct(),
            product_software_identity=None,
        )
    return refused.value


def _sepa_refusal() -> FilingExportDesignIntegrityError:
    snapshot = FilingProducerSnapshot.model_construct(selected_account=object())
    with pytest.raises(FilingExportDesignIntegrityError) as refused:
        COMPUTED_VALUE_PRODUCERS[ExportComputedKey.SEPA_MARCA](ModeloDraft.model_construct(), snapshot, None)
    return refused.value


@pytest.mark.parametrize("locale", _LOCALES)
@pytest.mark.parametrize(
    "refusal",
    (
        lambda: _prefix_refusal(FilingEnvelopePrefixRole.DECLARANT_TAX_ID),
        lambda: _prefix_refusal(FilingEnvelopePrefixRole.LANGUAGE),
        _sepa_refusal,
    ),
    ids=("declarant_tax_id", "language", "sepa_marker"),
)
def test_a_guard_the_design_owns_refuses_as_integrity_with_served_words_and_a_terminal_door(
    refusal: Callable[[], FilingExportDesignIntegrityError], locale: str
) -> None:
    raised = refusal()

    registered = get_registered_error_code(raised)
    assert registered.category is ErrorCategory.INTEGRITY
    assert "%{" not in resolve_error_message(raised, locale=locale)
    verdict = nested_terminal_precondition_verdict(raised)
    assert verdict is not None
    assert verdict.no_recovery_outcome is NoRecoveryOutcome.TERMINAL


def test_a_party_name_slot_without_a_filing_name_refuses_with_the_counterparty_filing_name_door() -> None:
    party = "B11111112"
    refusal = FilingExportDeclaredPartyNameMissingError(
        modelo="347",
        export_record_id="probe-record",
        export_field_id="probe-field",
        field_length=40,
        door_action_id=DECLARED_PARTY_NAME_DOOR_ACTION_ID,
        tax_identifier=party,
        country_code="ES",
    )

    failure = export_write_failure(_command(), refusal)

    assert isinstance(failure, ModeloExportDeclaredPartyNameError)
    verdict = nested_terminal_precondition_verdict(failure)
    assert verdict is not None
    assert verdict.action is not None
    assert verdict.action.action_id == DECLARED_PARTY_NAME_DOOR_ACTION_ID
    assert set(verdict.missing_argument_names) == {"tax_identifier", "country_code"}
    assert party not in verdict.model_dump_json()
