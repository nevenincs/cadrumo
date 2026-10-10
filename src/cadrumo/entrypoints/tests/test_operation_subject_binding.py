"""Every registered definition's declared subject is the one its real validator admits.

The declaration on a definition is what a client is told, and the family's own
check is what the runtime enforces. Nothing in the product compares the two, so
this module does, for every definition the production registry composes: the
subject rendered from the declaration is admitted, and any other is refused.

The seeded requests are the executor conformance matrix's own, so each resolver
is asked about a request its executor really runs.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import BaseModel

from ...application.operations.access_resolution import OperationAccessContext, resolve_operation_access
from ...application.operations.frontend_requests import (
    OperationObservationSuccessV1,
    OperationPublicPhaseEventV1,
)
from ...application.operations.models import OperationRequest
from ...application.operations.registry import OperationFrontendProjection, OperationRegistry
from ...application.operations.subject_reference import expected_operation_subject
from ...application.user_profile.access_contracts import AccessAction, Availability
from ...application.user_profile.access_errors import ProfileAccessRefusedError
from ...core.errors.hierarchy import CadrumoError
from ...core.operations import OperationLifecycle, OperationTerminalCondition, profile_operation_subject
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ..operation_composition import build_production_operation_registry
from .test_registered_executor_conformance import (
    _CloseWitness,
    _model_runtime_for,
    _runtime,
    _seeded_conformance_submission,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_RESOLVED = "resolved"
_DESTINATION = UUID("5aa00000-0000-4000-8000-0000000000bb")
_ANOTHER_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000cc")
_ANOTHER_RECORD = "f" * 64
#: A person's frontends first: a resolver may reserve one act of an operation for a person.
_FRONTEND_PREFERENCE = (
    OperationFrontendProjection.CLI,
    OperationFrontendProjection.TUI,
    OperationFrontendProjection.MCP,
)

_SUBJECT_CHECKED_BY_THE_EXECUTOR: frozenset[str] = frozenset(
    {
        "export.google-sheets",
        "local-reader.provision",
        "user-profile.automation-renew",
        "user-profile.automation-request",
        "user-profile.automation-rotate",
        "user-profile.automation-scope",
    }
)
"""Definitions registered without an access resolver.

No resolver reads their subject, so their executor's own first check is the
validator the declaration is held to, further down."""


_REVIEWED_DECISIONS: frozenset[str] = frozenset(
    {
        "user-profile.automation-approve",
        "user-profile.automation-decline",
    }
)
"""Decisions a person takes on a request they have reviewed.

Their resolver refuses a request that names no review, whatever its subject.
The shared executor scenario names none, because it runs where no trusted
runtime owner exists and so no review does either. These two are held to
their declaration by their own test further down, on a request that names one."""

_PROBE_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_REVIEW_DIGEST = "d" * 64


def _definition_ids(*, resolved: bool) -> tuple[str, ...]:
    registrations = build_production_operation_registry().public_registrations
    return tuple(
        sorted(
            registration.contract.definition_id
            for registration in registrations
            if (registration.access_resolver is not None) is resolved
        )
    )


def _other_subjects(declared: str, profile_id: UUID) -> tuple[str, ...]:
    """What a client could send instead: each other form in use, and a neighbouring profile and record."""
    candidates = (
        profile_operation_subject(str(profile_id)),
        str(profile_id),
        profile_operation_subject(str(_ANOTHER_PROFILE)),
        _ANOTHER_RECORD,
    )
    return tuple(candidate for candidate in candidates if candidate != declared)


def _submission_context(
    registry: OperationRegistry, definition_id: str, *, profile_id: UUID, operation: PinnedAuthorityOperation
) -> OperationAccessContext:
    contract = registry.lookup_public_contract(definition_id)
    frontend = next(item for item in _FRONTEND_PREFERENCE if item in contract.permitted_frontends)
    return OperationAccessContext(
        profile_id=profile_id,
        destination_id=_DESTINATION,
        action=AccessAction.SUBMIT,
        frontend=frontend,
        contract=contract,
        published_authority=Availability.AVAILABLE,
        authority_operation=operation,
    )


def _resolution(
    registry: OperationRegistry,
    definition_id: str,
    subject_ref: str,
    payload: BaseModel,
    context: OperationAccessContext,
) -> str:
    """Ask the registered resolver about one subject and name what it answered."""
    request = OperationRequest[BaseModel](definition_id=definition_id, subject_ref=subject_ref, payload=payload)
    try:
        resolve_operation_access(registry=registry, request=request, context=context)
    except ProfileAccessRefusedError as refused:
        return f"refused:{refused.reason.value}"
    except (CadrumoError, ValueError, LookupError) as error:
        return f"refused:{type(error).__name__}"
    return _RESOLVED


def test_the_definitions_without_an_access_resolver_are_the_ones_named_here() -> None:
    """A definition joins or leaves the executor-checked set only by gaining or losing its resolver."""
    assert set(_definition_ids(resolved=False)) == _SUBJECT_CHECKED_BY_THE_EXECUTOR
    assert set(_definition_ids(resolved=True)) > _REVIEWED_DECISIONS


@pytest.mark.parametrize("definition_id", sorted(_REVIEWED_DECISIONS))
def test_a_reviewed_decision_resolves_on_its_declared_subject_once_it_names_its_review(
    definition_id: str, *, operation: PinnedAuthorityOperation
) -> None:
    """The review is the resolver's other precondition; with it met, the subject alone decides."""
    registry = build_production_operation_registry()
    definition = registry.lookup(definition_id)
    context = _submission_context(registry, definition_id, profile_id=_PROBE_PROFILE, operation=operation)
    fields = {"profile_id": _PROBE_PROFILE, "request_id": UUID(int=1)}
    reviewed = definition.request_type.model_validate({**fields, "review_digest": _REVIEW_DIGEST}, strict=True)
    unreviewed = definition.request_type.model_validate(fields, strict=True)
    declared = expected_operation_subject(definition.subject_reference, profile_id=_PROBE_PROFILE, payload=reviewed)
    assert declared is not None

    assert _resolution(registry, definition_id, declared, reviewed, context) == _RESOLVED
    answers = {
        other: _resolution(registry, definition_id, other, reviewed, context)
        for other in _other_subjects(declared, _PROBE_PROFILE)
    }
    assert answers
    assert set(answers.values()) == {"refused:profile_mismatch"}, answers
    # Without a review the right subject is refused too, which is why the shared scenario proves nothing here.
    assert _resolution(registry, definition_id, declared, unreviewed, context) == "refused:operation_denied"


@pytest.mark.parametrize("definition_id", sorted(set(_definition_ids(resolved=True)) - _REVIEWED_DECISIONS))
def test_the_real_access_resolver_admits_the_declared_subject_and_refuses_any_other(
    tmp_path: Path, definition_id: str, *, operation: PinnedAuthorityOperation
) -> None:
    """A fresh submission resolves on the subject the declaration renders, and on no other."""
    with (
        _model_runtime_for(definition_id),
        _runtime(tmp_path / definition_id, cleanup=_CloseWitness()) as (_driver, registry, profile_id),
    ):
        definition = registry.lookup(definition_id)
        submission = _seeded_conformance_submission(
            definition, profile_id=profile_id, tmp_path=tmp_path, operation=operation
        )
        context = _submission_context(registry, definition_id, profile_id=profile_id, operation=operation)
        declared = definition.subject_reference.model_dump(mode="json")

        admitted = _resolution(registry, definition_id, submission.subject_ref, submission.registered_payload, context)
        assert admitted == _RESOLVED, (
            f"{definition_id} declares {declared}, but its resolver answers {admitted} "
            f"for the subject that renders, {submission.subject_ref!r}"
        )
        answers = {
            other: _resolution(registry, definition_id, other, submission.registered_payload, context)
            for other in _other_subjects(submission.subject_ref, profile_id)
        }
        admitted_others = sorted(other for other, answer in answers.items() if answer == _RESOLVED)
        assert answers
        assert not admitted_others, (
            f"{definition_id} declares {declared}, but its resolver also admits {admitted_others}"
        )


@pytest.mark.parametrize("definition_id", sorted(_SUBJECT_CHECKED_BY_THE_EXECUTOR))
def test_the_real_executor_runs_on_the_declared_subject_and_stops_any_other_before_its_first_phase(
    tmp_path: Path, definition_id: str, *, operation: PinnedAuthorityOperation
) -> None:
    """Each of these executors checks the subject first, so a refused subject publishes no phase at all."""
    with (
        _model_runtime_for(definition_id),
        _runtime(tmp_path / definition_id, cleanup=_CloseWitness()) as (driver, registry, profile_id),
    ):
        definition = registry.lookup(definition_id)
        submission = _seeded_conformance_submission(
            definition, profile_id=profile_id, tmp_path=tmp_path, operation=operation
        )

        def settle(subject_ref: str) -> OperationObservationSuccessV1:
            """Run the operation on one subject and read its settled public observation."""
            submitted, _observed = asyncio.run(
                driver.run(
                    definition_id=definition_id,
                    subject_ref=subject_ref,
                    payload=submission.payload,
                    secret=submission.secret,
                )
            )
            return asyncio.run(driver.observe(submitted.receipt.operation_id))

        def published(observed: OperationObservationSuccessV1) -> list[str]:
            """The definition's own phases the settled operation published."""
            return [
                event.phase_code
                for event in observed.event_page.events
                if isinstance(event, OperationPublicPhaseEventV1) and event.phase_code in definition.phase_codes
            ]

        on_declared = settle(submission.subject_ref)
        assert on_declared.projection.lifecycle is OperationLifecycle.TERMINAL
        assert published(on_declared), (
            f"{definition_id} published no phase on its declared subject {submission.subject_ref!r}"
        )
        for other in _other_subjects(submission.subject_ref, profile_id):
            on_other = settle(other)
            assert on_other.projection.lifecycle is OperationLifecycle.TERMINAL
            assert on_other.projection.terminal_condition in {
                OperationTerminalCondition.REFUSED,
                OperationTerminalCondition.FAILED,
            }, (definition_id, other)
            assert not published(on_other), (
                f"{definition_id} ran past its subject check on {other!r}: {published(on_other)}"
            )
