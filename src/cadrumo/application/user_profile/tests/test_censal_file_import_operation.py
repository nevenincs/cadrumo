"""Secure, exact-profile contracts for censal certificate fact enrollment."""

from __future__ import annotations

from uuid import uuid4

import pytest

from cadrumo.application.operations.access_resolution import OperationAccessContext
from cadrumo.application.operations.capabilities import (
    OperationReplayPolicy,
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
)
from cadrumo.application.operations.models import OperationRequest
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.user_profile.access_contracts import (
    AccessAction,
    AccessDenialCode,
    Availability,
)
from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
from cadrumo.application.user_profile.censal_file_import_operation import (
    CENSAL_FILE_IMPORT_OPERATION_DEFINITION_ID,
    CensalFileImportFact,
    CensalFileImportOperationRequest,
    CensalFileImportProvenance,
    build_censal_file_import_operation_definition,
    build_censal_file_import_operation_registration,
    resolve_censal_file_import_operation_access,
)
from cadrumo.core.operations import profile_operation_subject

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _facts() -> tuple[CensalFileImportFact, ...]:
    return (
        CensalFileImportFact(
            path="contact.fiscal_address",
            value="Calle Mayor 1, Madrid",
            source=CensalFileImportProvenance.ARTEFACT,
        ),
        CensalFileImportFact(
            path="activities.description",
            value="Consultoría",
            source=CensalFileImportProvenance.ARTEFACT,
        ),
        CensalFileImportFact(
            path="activities.1.description",
            value="Gestión",
            source=CensalFileImportProvenance.ARTEFACT,
        ),
    )


def test_file_import_request_accepts_only_canonical_non_official_fact_shapes() -> None:
    profile_id = uuid4()

    request = CensalFileImportOperationRequest(profile_id=profile_id, facts=_facts())

    assert request.profile_id == profile_id
    assert tuple(fact.path for fact in request.facts) == (
        "contact.fiscal_address",
        "activities.description",
        "activities.1.description",
    )


@pytest.mark.parametrize(
    "fact_values",
    [
        (
            _facts()[0].model_dump(mode="python"),
            {
                "path": "tax_residence.kind",
                "value": "resident",
                "source": CensalFileImportProvenance.ARTEFACT,
            },
        ),
        (
            {
                "path": "contact.fiscal_address",
                "value": "Calle Mayor 1, Madrid",
                "source": "aeat_censo_read",
            },
        ),
        (_facts()[1].model_dump(mode="python"),),
        (_facts()[0].model_dump(mode="python"), _facts()[0].model_dump(mode="python")),
        (
            _facts()[0].model_dump(mode="python"),
            _facts()[2].model_dump(mode="python"),
        ),
    ],
)
def test_file_import_request_refuses_unmapped_misprovenanced_or_incomplete_facts(
    fact_values: tuple[dict[str, object], ...],
) -> None:
    with pytest.raises(ValueError):
        CensalFileImportOperationRequest(profile_id=uuid4(), facts=fact_values)


def test_file_import_definition_uses_secure_nonreplayable_input_and_commit_access() -> None:
    definition = build_censal_file_import_operation_definition()
    registration = build_censal_file_import_operation_registration(definition)
    profile_id = uuid4()
    request = OperationRequest(
        definition_id=CENSAL_FILE_IMPORT_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(profile_id)),
        payload=CensalFileImportOperationRequest(profile_id=profile_id, facts=_facts()),
    )
    context = OperationAccessContext(
        profile_id=profile_id,
        destination_id=uuid4(),
        action=AccessAction.COMMIT,
        frontend=OperationFrontendProjection.CLI,
        contract=registration.contract,
        published_authority=Availability.AVAILABLE,
    )

    resolved = resolve_censal_file_import_operation_access(request, context)

    assert definition.capabilities.request_storage is OperationRequestStoragePolicy.SECURE_REFERENCE
    assert definition.capabilities.sensitive_input is OperationSensitiveInputPolicy.SECURE_REFERENCE
    assert definition.capabilities.replay is OperationReplayPolicy.NONE
    assert resolved.request.profile_id == profile_id
    assert resolved.request.action is AccessAction.COMMIT
    assert AccessAction.COMMIT in resolved.policy.actions


def test_file_import_access_refuses_a_foreign_profile() -> None:
    definition = build_censal_file_import_operation_definition()
    registration = build_censal_file_import_operation_registration(definition)
    profile_id = uuid4()
    foreign_profile_id = uuid4()
    request = OperationRequest(
        definition_id=CENSAL_FILE_IMPORT_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(profile_id)),
        payload=CensalFileImportOperationRequest(profile_id=profile_id, facts=_facts()),
    )
    context = OperationAccessContext(
        profile_id=foreign_profile_id,
        destination_id=uuid4(),
        action=AccessAction.COMMIT,
        frontend=OperationFrontendProjection.CLI,
        contract=registration.contract,
        published_authority=Availability.AVAILABLE,
    )

    with pytest.raises(ProfileAccessRefusedError) as refused:
        resolve_censal_file_import_operation_access(request, context)

    assert refused.value.reason is AccessDenialCode.PROFILE_MISMATCH
