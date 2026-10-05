"""Public ratio-operation scopes and terminal projections are exact and bounded."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel, ValidationError

from ....application.operations.access_resolution import OperationAccessContext, resolve_operation_access
from ....application.operations.models import OperationIdentity, OperationRequest, OperationTerminalReceipt
from ....application.operations.registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationRegistry,
)
from ....application.user_profile.access_contracts import AccessAction, Availability
from ....application.user_profile.access_errors import ProfileAccessRefusedError
from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ....core.time.clock import now
from .. import ratios_contracts as contracts
from .. import ratios_operation as ratios

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_OTHER_PROFILE = UUID("6bb00000-0000-4000-8000-0000000000bb")
_CATEGORY = "vehiculo_combustible"


def _registry() -> tuple[OperationRegistry, dict[str, OperationPublicDefinitionRegistrationV1]]:
    builders = (
        (ratios.build_ledger_ratios_eligible_definition, ratios.build_ledger_ratios_eligible_registration),
        (ratios.build_ledger_ratios_list_definition, ratios.build_ledger_ratios_list_registration),
        (ratios.build_ledger_ratios_set_definition, ratios.build_ledger_ratios_set_registration),
        (ratios.build_ledger_ratios_unset_definition, ratios.build_ledger_ratios_unset_registration),
        (ratios.build_ledger_ratios_validate_definition, ratios.build_ledger_ratios_validate_registration),
    )
    pairs = [(build_definition(), build_registration) for build_definition, build_registration in builders]
    definitions = tuple(sorted((definition for definition, _ in pairs), key=lambda item: item.definition_id))
    registrations = tuple(
        sorted(
            (build_registration(definition) for definition, build_registration in pairs),
            key=lambda item: item.contract.definition_id,
        )
    )
    return (
        OperationRegistry(definitions=definitions, public_registrations=registrations),
        {item.contract.definition_id: item for item in registrations},
    )


def _request(definition_id: str, *, profile_id: UUID = _PROFILE) -> OperationRequest[BaseModel]:
    payload = {
        contracts.LEDGER_RATIOS_LIST_OPERATION_DEFINITION_ID: contracts.LedgerRatiosListRequest(
            profile_id=profile_id, year=2026
        ),
        contracts.LEDGER_RATIOS_SET_OPERATION_DEFINITION_ID: contracts.LedgerRatiosSetRequest(
            profile_id=profile_id, category=_CATEGORY, ratio="0.5", year=2026
        ),
        contracts.LEDGER_RATIOS_UNSET_OPERATION_DEFINITION_ID: contracts.LedgerRatiosUnsetRequest(
            profile_id=profile_id, category=_CATEGORY
        ),
        contracts.LEDGER_RATIOS_ELIGIBLE_OPERATION_DEFINITION_ID: contracts.LedgerRatiosEligibleRequest(
            profile_id=profile_id, year=2026
        ),
        contracts.LEDGER_RATIOS_VALIDATE_OPERATION_DEFINITION_ID: contracts.LedgerRatiosValidateRequest(
            profile_id=profile_id
        ),
    }[definition_id]
    return OperationRequest[BaseModel](
        definition_id=definition_id,
        subject_ref=profile_operation_subject(str(profile_id)),
        payload=payload,
    )


def _receipt(
    definition_id: str,
    *,
    condition: OperationTerminalCondition = OperationTerminalCondition.SUCCEEDED,
    effect: OperationEffect = OperationEffect.NONE,
    refusal_code: str | None = None,
) -> OperationTerminalReceipt:
    refused = condition is OperationTerminalCondition.REFUSED
    return OperationTerminalReceipt(
        identity=OperationIdentity(
            operation_id="a" * 64,
            definition_id=definition_id,
            subject_ref=profile_operation_subject(str(_PROFILE)),
        ),
        revision=1,
        condition=condition,
        effect=effect,
        settled_at=now(),
        result_ref=None if refused else "b" * 64,
        refusal_ref=refusal_code,
        refusal_detail_ref="c" * 64 if refused else None,
    )


@pytest.mark.parametrize(
    ("definition_id", "commit_required"),
    [
        (contracts.LEDGER_RATIOS_LIST_OPERATION_DEFINITION_ID, False),
        (contracts.LEDGER_RATIOS_SET_OPERATION_DEFINITION_ID, True),
        (contracts.LEDGER_RATIOS_UNSET_OPERATION_DEFINITION_ID, True),
        (contracts.LEDGER_RATIOS_ELIGIBLE_OPERATION_DEFINITION_ID, False),
        (contracts.LEDGER_RATIOS_VALIDATE_OPERATION_DEFINITION_ID, False),
    ],
)
def test_every_ratio_operation_is_period_independent_and_mutations_require_commit(
    definition_id: str,
    commit_required: bool,
) -> None:
    registry, registrations = _registry()
    registration = registrations[definition_id]
    request = _request(definition_id)
    destination_id = uuid4()

    resolved = resolve_operation_access(
        registry=registry,
        request=request,
        context=OperationAccessContext(
            profile_id=_PROFILE,
            destination_id=destination_id,
            action=AccessAction.SUBMIT,
            frontend=OperationFrontendProjection.CLI,
            contract=registration.contract,
            published_authority=Availability.AVAILABLE,
        ),
    )

    assert resolved.request.periods == frozenset()
    assert resolved.request.period_independent is True
    assert resolved.policy.requires_all_periods is True
    assert resolved.policy.allow_period_independent is True
    assert (AccessAction.COMMIT in resolved.policy.actions) is commit_required
    assert isinstance(
        request.payload,
        (
            contracts.LedgerRatiosListRequest,
            contracts.LedgerRatiosSetRequest,
            contracts.LedgerRatiosUnsetRequest,
            contracts.LedgerRatiosEligibleRequest,
            contracts.LedgerRatiosValidateRequest,
        ),
    )
    assert request.payload.profile_id == _PROFILE


def test_read_access_refuses_a_foreign_profile_subject() -> None:
    registry, registrations = _registry()
    request = _request(contracts.LEDGER_RATIOS_LIST_OPERATION_DEFINITION_ID, profile_id=_OTHER_PROFILE)

    with pytest.raises(ProfileAccessRefusedError):
        resolve_operation_access(
            registry=registry,
            request=request,
            context=OperationAccessContext(
                profile_id=_PROFILE,
                destination_id=uuid4(),
                action=AccessAction.SUBMIT,
                frontend=OperationFrontendProjection.CLI,
                contract=registrations[request.definition_id].contract,
                published_authority=Availability.AVAILABLE,
            ),
        )


def test_request_schema_is_closed_and_ratio_is_a_bounded_unit_value() -> None:
    request = contracts.LedgerRatiosSetRequest(
        profile_id=_PROFILE,
        category=_CATEGORY,
        ratio="0.50",
        year=2026,
    )
    schema = contracts.LedgerRatiosSetRequest.model_json_schema()

    assert request.category == _CATEGORY
    assert schema["additionalProperties"] is False
    assert schema["properties"]["category"]["type"] == "string"
    assert contracts.LedgerRatiosSetRequest.model_validate_json(request.model_dump_json()) == request
    with pytest.raises(ValidationError):
        contracts.LedgerRatiosSetRequest(
            profile_id=_PROFILE,
            category=_CATEGORY,
            ratio="1.5",
            year=2026,
        )
    with pytest.raises(ValidationError):
        contracts.LedgerRatiosSetRequest(
            profile_id=_PROFILE,
            category=_CATEGORY,
            ratio="0.5",
            year=2026,
            extra="not registered",
        )


def test_list_censo_mismatch_requires_registered_refusal_receipt() -> None:
    result = contracts.LedgerRatiosListResult(
        profile_id=_PROFILE,
        year=2026,
        outcome="censo_mismatch",
        rows=(),
        count=0,
    )
    refusal = _receipt(
        contracts.LEDGER_RATIOS_LIST_OPERATION_DEFINITION_ID,
        condition=OperationTerminalCondition.REFUSED,
        effect=OperationEffect.NONE,
        refusal_code=contracts.LEDGER_RATIOS_CENSO_MISMATCH_REFUSAL_CODE,
    )

    assert ratios._project_list_result(result, refusal).outcome == "censo_mismatch"
    with pytest.raises(ValueError):
        ratios._project_list_result(
            result,
            refusal.model_copy(update={"effect": OperationEffect.UPDATED}),
        )


def test_unset_no_override_projects_only_with_the_registered_refusal_receipt() -> None:
    result = contracts.LedgerRatiosUnsetResult(
        profile_id=_PROFILE,
        requested_category="vehicle-alias",
        category=_CATEGORY,
        outcome="no_override",
        prior_ratio=None,
    )
    refusal = _receipt(
        contracts.LEDGER_RATIOS_UNSET_OPERATION_DEFINITION_ID,
        condition=OperationTerminalCondition.REFUSED,
        effect=OperationEffect.NONE,
        refusal_code=contracts.LEDGER_RATIOS_NO_OVERRIDE_REFUSAL_CODE,
    )

    assert ratios._project_unset_result(result, refusal).requested_category == "vehicle-alias"
    with pytest.raises(ValueError):
        ratios._project_unset_result(
            result,
            refusal.model_copy(update={"refusal_ref": contracts.LEDGER_RATIOS_CENSO_MISMATCH_REFUSAL_CODE}),
        )


def test_set_result_retains_the_raw_category_token_for_bridge_correlation() -> None:
    result = contracts.LedgerRatiosSetResult(
        profile_id=_PROFILE,
        requested_category="vehicle-alias",
        category=_CATEGORY,
        ratio="0.5",
        prior_ratio=None,
    )

    projection = ratios._project_set_result(
        result,
        _receipt(
            contracts.LEDGER_RATIOS_SET_OPERATION_DEFINITION_ID,
            effect=OperationEffect.UPDATED,
        ),
    )

    assert projection.requested_category == "vehicle-alias"
    assert projection.category == _CATEGORY
