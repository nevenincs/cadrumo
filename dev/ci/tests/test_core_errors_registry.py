"""Unit tests for the error-code registry."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from cadrumo.application.modelo.action_errors import WorkUnitAlreadyDiscardedError, WorkUnitMutationRefusedError
from cadrumo.core.access_gate.errors import LiveSubmitForbiddenError
from cadrumo.core.i18n.render import tr
from cadrumo.core.observability.errors import RunContextMissingError, RunTracePersistenceError
from cadrumo.core.errors.error_codes import (
    ErrorCategory,
    ErrorCode,
    get_error_exit_code,
    get_registered_error_code,
    render_error_json,
    render_error_text,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _sample_code(code: str) -> ErrorCode:
    return ErrorCode(
        code=code,
        category=ErrorCategory.ERROR,
        message_key="errors.error.sample_error",
        retryable=False,
        runbook_id=None,
    )


def test_error_code_model_is_frozen() -> None:
    code = _sample_code("ERROR_TEST_SAMPLE")
    with pytest.raises((ValidationError, TypeError), match=r"frozen|Instance is frozen|attribute"):
        setattr(code, "code", "ERROR_TEST_MUTATED")  # noqa: B010 - frozen-model refusal is the assertion


@pytest.mark.parametrize(
    ("forbidden_field", "value"),
    (
        ("default_suggestion", None),
        ("action", None),
        ("no_recovery_outcome", "operator_decision"),
    ),
)
def test_error_code_rejects_retired_and_policy_fields(forbidden_field: str, value: object) -> None:
    """Only application verdicts may carry recovery or terminal policy."""
    payload = _sample_code("ERROR_TEST_RETIRED_FIELD").model_dump(mode="json")
    payload[forbidden_field] = value

    with pytest.raises(ValidationError) as exc_info:
        ErrorCode.model_validate(payload)

    assert forbidden_field not in ErrorCode.model_json_schema()["properties"]
    assert forbidden_field in str(exc_info.value)


def test_bind_error_code_refusal_carries_diagnostic_hints() -> None:
    """The bind-refusal message tells the operator how to act on it.

    The bare ``CadrumoError subclass ... is missing a declared ErrorCode
    registry entry`` ValueError gives no signal that the state could be
    transient (e.g. a concurrent process mid-edit of the registry), so an
    operator could chase it as a defect in their own working tree. This test
    pins the two hints the refusal MUST carry: a registry-side fix
    direction for the genuine-new-class case, and a peer-WIP signal
    pointing the operator at ``git status`` for the collision case.
    """

    from cadrumo.core.errors.hierarchy import CadrumoError

    # bind_error_code fires from __init_subclass__ during class
    # creation, so the diagnostic ValueError lands on the ``class``
    # statement itself. Wrap the declaration in pytest.raises.
    with pytest.raises(ValueError) as exc_info:

        class _UnregisteredDiagnosticTestError(CadrumoError):
            """Synthetic subclass with no registry entry; used by this test only."""

        del _UnregisteredDiagnosticTestError  # unreachable when ValueError fires

    message = str(exc_info.value)
    assert "missing a declared ErrorCode registry entry" in message
    assert "git status" in message, "the peer-WIP hint must be present"
    assert "concurrent process" in message, "the peer-WIP context must be explicit"


def test_core_error_prefixes_are_grep_stable() -> None:
    """Stable upper-case category identifiers survive in JSON; rendered text uses sentence case."""

    for error_factory, expected_category in (
        (LiveSubmitForbiddenError, ErrorCategory.LOCKED),
        (RunContextMissingError, ErrorCategory.INTERNAL),
        (lambda: RunTracePersistenceError(operation="test", path=Path("runs")), ErrorCategory.FAIL),
    ):
        error = error_factory()
        assert error.code.category is expected_category
        rendered_json = render_error_json(error)
        assert f'"category":"{expected_category.value}"' in rendered_json
        rendered_text = render_error_text(error)
        prefix = tr(f"errors.prefix.{expected_category.value.lower()}")
        assert rendered_text.startswith(f"{prefix} ")


def test_modelo_lifecycle_terminal_errors_are_refused() -> None:
    """Terminal lifecycle errors retain the canonical refusal category and exit family."""
    expected_codes = {
        WorkUnitAlreadyDiscardedError: "REFUSED_MODELO_WORK_UNIT_ALREADY_DISCARDED",
        WorkUnitMutationRefusedError: "REFUSED_MODELO_WORK_UNIT_MUTATION_REFUSED",
    }
    for error_type, expected_code in expected_codes.items():
        code = get_registered_error_code(error_type)
        assert code.code == expected_code
        assert code.category is ErrorCategory.REFUSED
        assert get_error_exit_code(code.category) == 2


# ---------------------------------------------------------------------------
# contract — error-registry logger carries SecretScrubbingFilter
# ---------------------------------------------------------------------------
