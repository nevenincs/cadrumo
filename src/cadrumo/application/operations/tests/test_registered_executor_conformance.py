"""Conformance matrix for every production-registered operation executor."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from ....adapters.persistence.profile import SyncRunRecordRepository
from ...auth import build_auth_operation_definitions, build_auth_operation_registrations
from ...export import (
    build_google_sheets_export_operation_definition,
    build_google_sheets_export_operation_registration,
)
from ...live import build_filed_history_operation_definition, build_filed_history_operation_registration
from ...user_profile import (
    CENSAL_OPERATION_DEFINITION,
    build_censal_operation_registration,
    build_user_profile_operation_definitions,
    build_user_profile_operation_registrations,
)
from .. import (
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationEffect,
    OperationInteractionKind,
    OperationOwnedResource,
    OperationRegistry,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@dataclass(frozen=True, slots=True)
class _RegisteredExecutorConformanceCase:
    """The supervisor contract every exported production executor must declare."""

    definition_id: str
    interactions: frozenset[OperationInteractionKind]
    cancellation: OperationCancellation
    deadline: OperationDeadline
    permitted_effects: frozenset[OperationEffect]
    owned_resources: frozenset[OperationOwnedResource]


_STANDARD_EFFECTS = frozenset(
    {
        OperationEffect.NONE,
        OperationEffect.UPDATED,
        OperationEffect.UNKNOWN,
    }
)
_REGISTERED_EXECUTOR_MATRIX = (
    _RegisteredExecutorConformanceCase(
        definition_id="auth.profile.login",
        interactions=frozenset(),
        cancellation=OperationCancellation.UNSUPPORTED,
        deadline=OperationDeadline.ABSENT,
        permitted_effects=_STANDARD_EFFECTS,
        owned_resources=frozenset(),
    ),
    _RegisteredExecutorConformanceCase(
        definition_id="auth.provider.configure",
        interactions=frozenset(),
        cancellation=OperationCancellation.UNSUPPORTED,
        deadline=OperationDeadline.ABSENT,
        permitted_effects=_STANDARD_EFFECTS,
        owned_resources=frozenset(),
    ),
    _RegisteredExecutorConformanceCase(
        definition_id="auth.session.acquire",
        interactions=frozenset(),
        cancellation=OperationCancellation.UNSUPPORTED,
        deadline=OperationDeadline.ABSENT,
        permitted_effects=_STANDARD_EFFECTS,
        owned_resources=frozenset(),
    ),
    _RegisteredExecutorConformanceCase(
        definition_id="auth.session.logout",
        interactions=frozenset(),
        cancellation=OperationCancellation.UNSUPPORTED,
        deadline=OperationDeadline.ABSENT,
        permitted_effects=_STANDARD_EFFECTS,
        owned_resources=frozenset(),
    ),
    _RegisteredExecutorConformanceCase(
        definition_id="auth.session.reset",
        interactions=frozenset(),
        cancellation=OperationCancellation.UNSUPPORTED,
        deadline=OperationDeadline.ABSENT,
        permitted_effects=_STANDARD_EFFECTS,
        owned_resources=frozenset(),
    ),
    _RegisteredExecutorConformanceCase(
        definition_id="auth.profile.passphrase-rotate",
        interactions=frozenset(),
        cancellation=OperationCancellation.UNSUPPORTED,
        deadline=OperationDeadline.ABSENT,
        permitted_effects=_STANDARD_EFFECTS,
        owned_resources=frozenset(),
    ),
    _RegisteredExecutorConformanceCase(
        definition_id="user-profile.field-mutation",
        interactions=frozenset(),
        cancellation=OperationCancellation.UNSUPPORTED,
        deadline=OperationDeadline.ABSENT,
        permitted_effects=_STANDARD_EFFECTS,
        owned_resources=frozenset(),
    ),
    _RegisteredExecutorConformanceCase(
        definition_id="user-profile.repeatable-row-mutation",
        interactions=frozenset(),
        cancellation=OperationCancellation.UNSUPPORTED,
        deadline=OperationDeadline.ABSENT,
        permitted_effects=_STANDARD_EFFECTS,
        owned_resources=frozenset(),
    ),
    _RegisteredExecutorConformanceCase(
        definition_id="user-profile.bundle-export",
        interactions=frozenset(),
        cancellation=OperationCancellation.UNSUPPORTED,
        deadline=OperationDeadline.ABSENT,
        permitted_effects=_STANDARD_EFFECTS,
        owned_resources=frozenset(),
    ),
    _RegisteredExecutorConformanceCase(
        definition_id="user-profile.logout",
        interactions=frozenset(),
        cancellation=OperationCancellation.UNSUPPORTED,
        deadline=OperationDeadline.ABSENT,
        permitted_effects=_STANDARD_EFFECTS,
        owned_resources=frozenset(),
    ),
    _RegisteredExecutorConformanceCase(
        definition_id="user-profile.censo-review",
        interactions=frozenset({OperationInteractionKind.REVIEW}),
        cancellation=OperationCancellation.COOPERATIVE,
        deadline=OperationDeadline.COOPERATIVE,
        permitted_effects=_STANDARD_EFFECTS,
        owned_resources=frozenset({OperationOwnedResource.ASYNC_TASK}),
    ),
    _RegisteredExecutorConformanceCase(
        definition_id="live.filed-history.pull",
        interactions=frozenset(),
        cancellation=OperationCancellation.UNSUPPORTED,
        deadline=OperationDeadline.ABSENT,
        permitted_effects=_STANDARD_EFFECTS | frozenset({OperationEffect.PARTIAL}),
        owned_resources=frozenset(),
    ),
    _RegisteredExecutorConformanceCase(
        definition_id="export.google-sheets",
        interactions=frozenset(),
        cancellation=OperationCancellation.UNSUPPORTED,
        deadline=OperationDeadline.ABSENT,
        permitted_effects=_STANDARD_EFFECTS,
        owned_resources=frozenset(),
    ),
)


def _production_registered_executor_registry() -> OperationRegistry:
    """Build the real exported population without owner-specific request fixtures."""
    auth_definitions = build_auth_operation_definitions()
    user_profile_definitions = build_user_profile_operation_definitions()
    filed_history_definition = build_filed_history_operation_definition(
        sync_run_repository_factory=SyncRunRecordRepository
    )
    google_sheets_export_definition = build_google_sheets_export_operation_definition()
    definitions = tuple(
        sorted(
            (
                *auth_definitions,
                *user_profile_definitions,
                CENSAL_OPERATION_DEFINITION,
                filed_history_definition,
                google_sheets_export_definition,
            ),
            key=lambda definition: definition.definition_id,
        )
    )
    registrations = tuple(
        sorted(
            (
                *build_auth_operation_registrations(auth_definitions),
                *build_user_profile_operation_registrations(user_profile_definitions),
                build_censal_operation_registration(CENSAL_OPERATION_DEFINITION),
                build_filed_history_operation_registration(filed_history_definition),
                build_google_sheets_export_operation_registration(google_sheets_export_definition),
            ),
            key=lambda registration: registration.contract.definition_id,
        )
    )
    return OperationRegistry(definitions=definitions, public_registrations=registrations)


def test_every_production_registered_executor_matches_the_shared_conformance_matrix() -> None:
    """Exercise all production registrations without duplicating executor behavior harnesses."""
    registry = _production_registered_executor_registry()
    cases_by_definition_id = {case.definition_id: case for case in _REGISTERED_EXECUTOR_MATRIX}

    assert tuple(cases_by_definition_id) == tuple(case.definition_id for case in _REGISTERED_EXECUTOR_MATRIX)
    assert set(cases_by_definition_id) == {definition.definition_id for definition in registry.definitions}

    for definition in registry.definitions:
        case = cases_by_definition_id[definition.definition_id]
        registration = registry.lookup_public_registration(definition.definition_id)
        executor = definition.executor_factory.create()

        # A declared result type is the success receipt contract. NONE is the
        # no-effect refusal result, and UNKNOWN keeps unexpected failure honest
        # until an owner can narrow the effect from committed evidence.
        assert definition.result_type is not None
        assert OperationEffect.NONE in definition.capabilities.permitted_effects
        assert OperationEffect.UNKNOWN in definition.capabilities.permitted_effects
        assert type(executor) is definition.executor_factory.executor_type
        assert registration.contract.definition_id == definition.definition_id
        assert registration.contract.request_schema.schema_id == f"{definition.definition_id}.request"
        assert registration.contract.interaction_kinds == case.interactions
        assert registration.contract.cancellation is case.cancellation
        assert registration.contract.deadline is case.deadline
        assert registration.contract.permitted_effects == case.permitted_effects
        assert registration.contract.owned_resources == case.owned_resources
        assert registration.contract.close_policy is OperationClosePolicy.DETACH_ALLOWED
