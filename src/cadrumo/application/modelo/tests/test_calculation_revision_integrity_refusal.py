"""A saved calculation revision that contradicts itself is a terminal integrity refusal in every locale."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from ....core.errors.error_codes import get_registered_error_code, resolve_error_message
from ....core.operator_action_enums import NoRecoveryOutcome
from ....domain.calculations.registry.schema_references import RegistrySnapshotRef
from ....domain.calculations.registry.tests.authored_editions import open_ended_revision
from ....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from ....domain.modelos.errors import CalculationRevisionIntegrityError
from ...cli_exception_preconditions import nested_terminal_precondition_verdict

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_WORK_UNIT_ID = "f" * 64
_CASILLA = "0001"
_REVISION = open_ended_revision("303")
_CREATED = datetime(_REVISION.valid_from.year, _REVISION.valid_from.month, _REVISION.valid_from.day, 10, tzinfo=UTC)


def _revision_fields(**overrides: object) -> dict[str, object]:
    created = _CREATED
    fields: dict[str, object] = {
        "calculation_revision_id": derive_calculation_revision_id(
            work_unit_id=_WORK_UNIT_ID,
            input_values_by_casilla_id={},
            binding_overrides={},
            casilla_values={},
            filing_instance_evidence=None,
            source_provenance=(),
        ),
        "work_unit_id": _WORK_UNIT_ID,
        "registry_snapshot_ref": RegistrySnapshotRef(
            modelo="303", revision_id=_REVISION.id, modelo_year=_REVISION.valid_from.year, period="1T"
        ),
        "state": CalculationRevisionState.BORRADOR,
        "casilla_values": {},
        "created_at": created,
        "updated_at": created,
        "filing_instance_evidence": None,
        "source_provenance": (),
    }
    fields.update(overrides)
    return fields


def _refused(**overrides: object) -> CalculationRevisionIntegrityError:
    with pytest.raises(ValidationError) as refused:
        CalculationRevision.model_validate(_revision_fields(**overrides))
    cause = refused.value.errors()[0]["ctx"]["error"]
    assert isinstance(cause, ValueError)
    registered = cause.__cause__
    assert isinstance(registered, CalculationRevisionIntegrityError)
    return registered


def test_a_revision_that_still_validates_is_not_refused() -> None:
    assert CalculationRevision.model_validate(_revision_fields()).casilla_values == {}


@pytest.mark.parametrize("locale", ["es", "ca", "en", "hu"])
@pytest.mark.parametrize(
    "overrides",
    [
        {"updated_at": _CREATED - timedelta(hours=1)},
        {"casilla_values": {_CASILLA: Decimal("1.00")}},
    ],
    ids=["updated_before_created", "values_without_observations"],
)
def test_a_self_contradicting_revision_is_terminal_and_worded_in_every_locale(
    overrides: dict[str, object], locale: str
) -> None:
    refusal = _refused(**overrides)

    verdict = nested_terminal_precondition_verdict(refusal)
    assert verdict is not None
    assert verdict.no_recovery_outcome is NoRecoveryOutcome.TERMINAL
    assert get_registered_error_code(refusal).code == "INTEGRITY_MODELOS_CALCULATION_REVISION"
    message = resolve_error_message(refusal, locale=locale)
    assert "%{" not in message
