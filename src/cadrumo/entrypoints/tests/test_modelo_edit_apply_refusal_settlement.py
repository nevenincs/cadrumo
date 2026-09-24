"""A refused modelo edit settles as a localized refusal through the production supervisor.

Each scenario seeds a real calculated revision, drives the registered
``modelo.edit.apply`` operation through the composed services, and checks the
public projection an operator sees: a REFUSED terminal under the refusal
family's registered code, no effect, a localized explanation, and catalogues
left exactly as they were.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from decimal import Decimal
from pathlib import Path

import pytest

from ...adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ...adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ...adapters.persistence.storage.runtime_repository import secure_object_repository_for_active_bucket
from ...application.modelo.calculation_actions import calculate_modelo_revision
from ...application.modelo.edit_contract import ModeloEditMutationFamily
from ...application.modelo.edit_models import (
    ModeloEditScalarAddressV1,
    ModeloEditScalarIntentKind,
    ModeloEditSubmissionV1,
    ModeloScalarEditIntentV1,
)
from ...application.modelo.edit_services import writable_scalar_entry
from ...application.modelo.operation_definitions import (
    ModeloEditApplyOperationRequestV1,
    ModeloEditApplySubmissionV1,
)
from ...core.casilla_id import validated_casilla_id
from ...core.errors.error_codes import get_registered_error_code_by_code
from ...core.hashing import content_hash_hex
from ...core.i18n.render import tr
from ...core.operations import OperationEffect, OperationLifecycle, OperationTerminalCondition
from ...domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ..adapter_composition import build_calculation_action_ports
from ..tui.operations.refusal_explanation import public_refusal_explanation
from .test_registered_executor_conformance import (
    _ACTOR,
    _FIRST_QUARTER_PRIOR_PERIOD_BINDINGS,
    _CloseWitness,
    _runtime,
    _seeded_modelo_edit_submission,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_EDIT_APPLY = "modelo.edit.apply"


def _catalogue_digests() -> tuple[str, str]:
    """Fingerprint the active bucket's work and calculation catalogues."""
    objects = secure_object_repository_for_active_bucket()
    return (
        content_hash_hex(WorkUnitCatalogueRepository(objects=objects).load().model_dump(mode="json")),
        content_hash_hex(CalculationRevisionCatalogueRepository(objects=objects).load().model_dump(mode="json")),
    )


def _recalculate_after_the_baseline(submission: ModeloEditSubmissionV1) -> ModeloEditSubmissionV1:
    """Change the declaration after its baseline was captured, leaving the submission itself unchanged."""
    baseline = submission.baseline
    with bundled_indexed_authority().operation() as operation:
        calculate_modelo_revision(
            baseline.work_unit_id,
            ports=build_calculation_action_ports(bucket_id=baseline.bucket_id, operation=operation),
            actor=_ACTOR,
            # The same free casilla the seeded revision was calculated from,
            # now with another amount, so a new revision supersedes it.
            casilla_inputs={validated_casilla_id("06"): Decimal("7")},
            binding_values=_FIRST_QUARTER_PRIOR_PERIOD_BINDINGS,
        )
    return submission


def _ask_for_recalculation(submission: ModeloEditSubmissionV1) -> ModeloEditSubmissionV1:
    """Request the recalculate family, which this executor cannot apply yet."""
    baseline = submission.baseline.model_copy(update={"mutation_family": ModeloEditMutationFamily.RECALCULATE})
    return ModeloEditSubmissionV1(
        baseline=baseline,
        mutation_family=ModeloEditMutationFamily.RECALCULATE,
        scalar_intents=submission.scalar_intents,
    )


def _address_a_casilla_outside_the_surface(submission: ModeloEditSubmissionV1) -> ModeloEditSubmissionV1:
    """Target a casilla the baseline's permitted surface never admitted."""
    outside = next(
        candidate
        for candidate in (validated_casilla_id(f"{number:02d}") for number in range(1, 100))
        if writable_scalar_entry(submission.baseline, candidate) is None
    )
    return ModeloEditSubmissionV1(
        baseline=submission.baseline,
        mutation_family=submission.mutation_family,
        scalar_intents=(
            ModeloScalarEditIntentV1(
                address=ModeloEditScalarAddressV1(casilla_id=outside),
                kind=ModeloEditScalarIntentKind.SET_TYPED_VALUE,
                value="100.00",
            ),
        ),
    )


@pytest.mark.parametrize(
    ("variant", "expected_code"),
    [
        (_recalculate_after_the_baseline, "REFUSED_MODELO_EDIT_BASELINE_STALE"),
        (_ask_for_recalculation, "REFUSED_MODELO_EDIT_INTENT_UNSUPPORTED"),
        (_address_a_casilla_outside_the_surface, "REFUSED_MODELO_EDIT_REFUSED"),
    ],
    ids=["stale-baseline", "unsupported-intent", "disallowed-intent"],
)
@pytest.mark.timeout(90)
def test_a_refused_edit_settles_refused_with_its_family_code_and_writes_nothing(
    tmp_path: Path,
    variant: Callable[[ModeloEditSubmissionV1], ModeloEditSubmissionV1],
    expected_code: str,
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    """The operator sees a localized refusal naming the family, and no catalogue changed."""
    with _runtime(tmp_path / "runtime", cleanup=_CloseWitness()) as (driver, registry, profile_id):
        definition = registry.lookup(_EDIT_APPLY)
        work_unit_id, wire = _seeded_modelo_edit_submission(profile_id, operation=operation)
        assert isinstance(wire, ModeloEditApplySubmissionV1)
        refused = ModeloEditApplySubmissionV1.from_submission(variant(wire.to_submission()))
        payload = definition.request_type.model_validate({"submission": refused}, strict=True)
        assert isinstance(payload, ModeloEditApplyOperationRequestV1)
        catalogues_before = _catalogue_digests()

        _submitted, observed = asyncio.run(
            driver.run(definition_id=_EDIT_APPLY, subject_ref=work_unit_id, payload=payload)
        )
        catalogues_after = _catalogue_digests()

    projection = observed.projection
    assert projection.lifecycle is OperationLifecycle.TERMINAL
    assert projection.terminal_condition is OperationTerminalCondition.REFUSED
    assert projection.refusal_ref == expected_code
    assert projection.effect is OperationEffect.NONE
    assert projection.result_ref is None
    assert projection.diagnostic_ref is None
    assert catalogues_after == catalogues_before

    registered = get_registered_error_code_by_code(expected_code)
    explanation = public_refusal_explanation(projection.refusal_ref)
    assert explanation is not None
    assert explanation == tr(registered.message_key)
    assert explanation.strip()
    assert explanation != registered.message_key
    assert work_unit_id not in explanation
