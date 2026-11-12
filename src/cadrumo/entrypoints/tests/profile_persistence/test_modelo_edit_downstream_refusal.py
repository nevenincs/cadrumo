"""An edit whose value was admitted but whose recalculation refused settles under the recalculation's refusal.

The filer types an amount on a Modelo 130 while the profile, changed since the
edit began, no longer makes the declaration applicable. The value is admitted;
the recalculation refuses under the profile readiness code. The edit settles
under that code with its own door, writes nothing and carries no value. A
value the edit itself refuses still settles as the edit refusal.

Real behaviour throughout: an isolated encrypted profile, the bundled
authority, the production admission and edit executor.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from ....adapters.persistence.storage.tests.profile_capsule_runtime import upsert_test_profile_facts
from ....application.cli_exception_preconditions import nested_terminal_precondition_verdict
from ....application.modelo.action_errors import ModeloEditRefusedError
from ....application.modelo.edit_models import (
    ModeloEditScalarAddressV1,
    ModeloEditScalarIntentKind,
    ModeloScalarEditIntentV1,
)
from ....application.operations.error_detail import UNWORDED_REGISTERED_ERROR_LOCALE_KEY
from ....core.casilla_id import validated_casilla_id
from ....core.errors.error_codes import get_registered_error_code, resolve_error_message
from ....core.errors.hierarchy import CadrumoError, RecordedRegisteredError
from ....core.external_constants import OutputLanguage
from ....core.i18n.render import extract_placeholders, tr
from ....core.operations import OperationEffect
from ....core.operator_action_enums import NoRecoveryOutcome
from ....domain.modelos.calculation_revision import CalculationRevision
from ....domain.user_profile.values import UserProfileFact
from ..modelo_operator_work_storage import AppliedEdit, seeded_operator_work

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_READINESS_CODE = "REFUSED_MODELO_PROFILE_READINESS"
#: A synthetic amount the filer types; it must never reach the settled refusal.
_TYPED = "4321.98"


def _set_box_06(value: str) -> ModeloScalarEditIntentV1:
    return ModeloScalarEditIntentV1(
        address=ModeloEditScalarAddressV1(casilla_id=validated_casilla_id("06")),
        kind=ModeloEditScalarIntentKind.SET_TYPED_VALUE,
        value=value,
    )


@dataclass(frozen=True, slots=True)
class _Refused:
    applied: AppliedEdit
    head_after: CalculationRevision | None


@pytest.fixture(scope="module")
def refused(tmp_path_factory: pytest.TempPathFactory) -> _Refused:
    """Admit an edit, then take the declaration out of scope before it applies: the recalculation refuses."""
    with seeded_operator_work(tmp_path_factory.mktemp("downstream")) as work:
        baseline = work.baseline()
        # Objective estimation takes the declaration out of Modelo 130's scope.
        upsert_test_profile_facts(
            work.work_unit.bucket_id, (UserProfileFact(path="irpf.estimation_regime", value="objetiva"),)
        )
        applied = work.apply(scalar=(_set_box_06(_TYPED),), baseline=baseline)
        return _Refused(applied=applied, head_after=work.head())


def _error(refused: _Refused) -> CadrumoError:
    error = refused.applied.refusal
    assert error is not None
    return error


def test_an_admitted_value_whose_recalculation_refuses_settles_under_that_refusal(refused: _Refused) -> None:
    error = _error(refused)

    assert isinstance(error, RecordedRegisteredError)
    assert get_registered_error_code(error).code == _READINESS_CODE
    assert refused.applied.effects[-1] is OperationEffect.NONE
    assert refused.head_after is None


@pytest.mark.parametrize("language", list(OutputLanguage))
def test_the_settled_refusal_is_worded_in_every_language(refused: _Refused, language: OutputLanguage) -> None:
    """The readiness sentence needs the modelo and its legal references, which do not travel,
    so the served words are the sentence that names the refusal's code."""
    words = resolve_error_message(_error(refused), locale=language.value)

    assert words == tr(UNWORDED_REGISTERED_ERROR_LOCALE_KEY, locale=language.value, error_code=_READINESS_CODE)
    assert _READINESS_CODE in words
    assert not extract_placeholders(words)
    assert _TYPED not in words


def test_the_settled_refusal_opens_the_recalculations_door(refused: _Refused) -> None:
    door = nested_terminal_precondition_verdict(_error(refused))

    assert door is not None
    assert door.failed_condition_id == "modelo.refusal.modelo_not_applicable.holds"
    assert door.no_recovery_outcome is NoRecoveryOutcome.OPERATOR_DECISION


def test_no_value_reaches_the_settled_refusal(refused: _Refused) -> None:
    error = _error(refused)

    assert error.context == {"error_code": _READINESS_CODE}
    assert _TYPED not in repr(error.args)


def test_a_value_the_edit_refuses_still_settles_as_the_edit_refusal(tmp_path: Path) -> None:
    with seeded_operator_work(tmp_path) as work:
        applied = work.apply(scalar=(_set_box_06("-100"),))
        head_after = work.head()

    assert type(applied.refusal) is ModeloEditRefusedError
    assert get_registered_error_code(applied.refusal).code == "REFUSED_MODELO_EDIT_REFUSED"
    assert applied.effects[-1] is OperationEffect.NONE
    assert head_after is None
