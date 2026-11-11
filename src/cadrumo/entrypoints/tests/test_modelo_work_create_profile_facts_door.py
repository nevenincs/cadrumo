"""A Modelo work refusal for absent profile facts names them in words and opens the profile questions.

The refusal settles REFUSED with no effect. Its recorded error detail carries the
facts as the schema's own labels with their legal citations in readable form,
never a digest-stamped identifier, and the catalogue action that opens the
profile questions. That the action resolves to the live command leaf is the
command line's own assertion, held in its recorded action target tests.
"""

from __future__ import annotations

import asyncio
import re
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ...adapters.persistence.storage.tests.profile_capsule_runtime import seed_test_profile_record
from ...application.modelo.work_create_operation import ModeloWorkCreateRequest
from ...application.operations.error_detail import OperationErrorDetailV1, operation_error_detail_schema
from ...application.operations.frontend_requests import (
    OperationResultProjectionRequestV1,
    OperationResultProjectionSuccessV1,
)
from ...application.operations.public_period import PublicPeriod
from ...application.operator_surface.action_targets import resolve_recorded_precondition_action
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...core.operator_action_enums import ActionConditionality
from ...core.period import Period
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ...domain.user_profile.values import ProfileSetupState, UserProfileFact, create_user_profile_record
from .modelo_operation_test_support import MODELO_OPERATION_TEST_ACTOR
from .registered_executor_case_support import OperationRuntimeCloseWitness, conformance_operation_runtime

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_CREATE = "modelo.work.create"
_YEAR = filing_year_envelope().horizon
_CLOCK = datetime(_YEAR, 4, 2, 9, 0, tzinfo=UTC)
_PERIOD = Period.from_year_and_code(_YEAR, "1T")
_RAW_TOKEN = re.compile(r"sha256:|[a-z]+-\d+-\d{4}:|:art-|\b[a-z_]+\.[a-z_]+\b")
_DECLARED_FACTS = {
    "preferences.output_language": "en",
    "taxpayer_type.entity_type": "natural_person",
    "taxpayer_type.irpf_income_categories": "actividad_economica",
    "identity.tax_id": "12345678Z",
    "identity.name": "Marta",
    "identity.surnames": "Navarro",
    "censo.large_company": "false",
}


def test_a_missing_profile_facts_refusal_speaks_in_words_and_names_the_profile_questions(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    with conformance_operation_runtime(tmp_path / "runtime", cleanup=OperationRuntimeCloseWitness()) as (
        driver,
        registry,
        profile_id,
    ):
        seed_test_profile_record(
            create_user_profile_record(
                context=operation.profile_create_context(),
                setup_state=ProfileSetupState.COMPLETE,
                profile_id=str(profile_id),
                facts=tuple(UserProfileFact(path=path, value=value) for path, value in _DECLARED_FACTS.items()),
                created_at=_CLOCK,
                updated_at=_CLOCK,
            )
        )
        payload = ModeloWorkCreateRequest(
            profile_id=profile_id,
            modelo="303",
            period=PublicPeriod.from_period(_PERIOD),
            actor=MODELO_OPERATION_TEST_ACTOR,
        )
        _submitted, observed = asyncio.run(
            driver.run(definition_id=_CREATE, subject_ref=profile_operation_subject(str(profile_id)), payload=payload)
        )
        contract = registry.lookup_public_contract(_CREATE)
        resolved = asyncio.run(
            driver.services.result.resolve(
                OperationResultProjectionRequestV1(
                    operation_id=observed.projection.operation_id,
                    terminal_revision=observed.projection.revision,
                    definition_contract_digest=contract.definition_contract_digest,
                    result_schema=operation_error_detail_schema(),
                ),
                OperationErrorDetailV1,
            )
        )

    projection = observed.projection
    assert projection.terminal_condition is OperationTerminalCondition.REFUSED
    assert projection.refusal_ref == "REFUSED_MODELO_PROFILE_READINESS", projection.refusal_ref
    assert projection.effect is OperationEffect.NONE
    assert isinstance(resolved, OperationResultProjectionSuccessV1), resolved
    detail = resolved.projection
    assert isinstance(detail, OperationErrorDetailV1)

    words = detail.refusal_words or ""
    assert words, detail
    assert _RAW_TOKEN.search(words) is None, words
    assert "Ley 37/1992, art.\u00a0122" in words, words

    verdict = detail.precondition_verdict()
    assert verdict is not None
    served = resolve_recorded_precondition_action(verdict)
    assert served.action is not None, "the refusal names no action"
    assert served.action.action_id == "operator.profile.edit"
    assert served.conditionality is ActionConditionality.REQUIRES_ARGUMENTS
    missing = str(verdict.evidence[0].values["missing_fields"]).split(", ")
    assert "activities.description" in missing
