"""An edit whose recalculation lacks required inputs is refused naming those inputs.

The required-binding gate names every declared Modelo 202 binding the
recalculation could not resolve. The edit's refusal settles under the same
registered code and carries those binding ids, as the revision declares them,
into the served refusal, so the filer sees which input to state instead of a
refusal that names none. Real gate error, real revision from the published
authority, real refusal translation.
"""

from __future__ import annotations

import pytest

from ....core.errors.error_codes import get_registered_error_code
from ....core.errors.hierarchy import RecordedRegisteredError
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ..action_errors import ModeloRequiredBindingsMissingError, modelo_edit_refusal_error
from ..edit_execution import pre_effect_refusal
from ..edit_models import ModeloEditDomainRefusalV1
from ..refusal_door_verdicts import caller_defect_verdict

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_CODE = "REFUSED_MODELO_REQUIRED_BINDINGS_MISSING"
_PRIOR_PAYMENTS = "modelo-202-pagos-fraccionados-anteriores"
_UNDECLARED = "modelo-202-not-a-declared-binding"


def _gate_error(*missing: str) -> ModeloRequiredBindingsMissingError:
    return ModeloRequiredBindingsMissingError(
        context={"missing_binding_count": len(missing), "missing_bindings": missing},
        precondition_verdict=caller_defect_verdict("required_bindings_gate_action"),
    )


def test_the_edit_refusal_names_the_missing_inputs(authority_operation: PinnedAuthorityOperation) -> None:
    revision = authority_operation.revision_for_context(
        "202", filing_year=filing_year_envelope().horizon - 1, period="3P"
    )
    outcome = pre_effect_refusal(_gate_error(_PRIOR_PAYMENTS, _UNDECLARED), revision=revision)
    refusal = outcome.refusal
    assert isinstance(refusal, ModeloEditDomainRefusalV1)
    # Only the bindings the edited revision declares travel; an undeclared id never does.
    assert refusal.evidence == (_PRIOR_PAYMENTS,)

    error = modelo_edit_refusal_error(refusal)

    assert isinstance(error, RecordedRegisteredError)
    assert get_registered_error_code(error).code == _CODE
    assert error.context == {"bindings": _PRIOR_PAYMENTS}
    assert error.translated_message == "application.modelo.errors.edit_required_bindings_missing"
    assert error.terminal_precondition_verdict is not None


def test_a_refusal_naming_no_declared_input_keeps_the_value_family(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    revision = authority_operation.revision_for_context(
        "202", filing_year=filing_year_envelope().horizon - 1, period="3P"
    )
    refusal = pre_effect_refusal(_gate_error(_UNDECLARED), revision=revision).refusal
    assert isinstance(refusal, ModeloEditDomainRefusalV1)
    assert refusal.evidence == ()

    error = modelo_edit_refusal_error(refusal)

    assert get_registered_error_code(error).code == "REFUSED_MODELO_EDIT_REFUSED"
