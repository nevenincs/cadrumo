"""CLI transport for worker-owned censal certificate fact enrollment."""

from __future__ import annotations

import typer

from ....application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ....application.user_profile.censal_file_import_operation import (
    CENSAL_FILE_IMPORT_OPERATION_DEFINITION_ID,
    CensalFileImportFact,
    CensalFileImportOperationRequest,
    CensalFileImportOperationResult,
    CensalFileImportProvenance,
)
from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ....domain.user_profile.values import UserProfileFact
from ..runtime_profile_binding import bound_profile_client
from ..runtime_registered_operation import run_registered_operation, submitted_operation_error


def _operation_facts(facts: tuple[UserProfileFact, ...]) -> tuple[CensalFileImportFact, ...]:
    """Keep the wire input closed to the exact value shape emitted by the adapter."""
    converted: list[CensalFileImportFact] = []
    for fact in facts:
        if type(fact.value) is not str or fact.valid_from is not None or fact.valid_to is not None:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        try:
            converted.append(
                CensalFileImportFact(
                    path=fact.path,
                    value=fact.value,
                    source=CensalFileImportProvenance(fact.source),
                )
            )
        except (TypeError, ValueError, RecursionError):
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME) from None
    return tuple(converted)


def import_censal_file_facts(
    ctx: typer.Context,
    facts: tuple[UserProfileFact, ...],
) -> CensalFileImportOperationResult:
    """Enroll parsed certificate facts through the bound profile's operation runtime."""
    client = bound_profile_client(ctx)
    try:
        request = CensalFileImportOperationRequest(profile_id=client.profile_id, facts=_operation_facts(facts))
    except (TypeError, ValueError, RecursionError):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME) from None
    completed = run_registered_operation(
        client,
        request,
        definition_id=CENSAL_FILE_IMPORT_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=CensalFileImportOperationResult,
        request_version=1,
        result_version=1,
        timeout=60,
    )
    projection = completed.projection
    if (
        completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.refusal_code is not None
        or completed.effect is not OperationEffect.UPDATED
        or projection.profile_id != client.profile_id
        or projection.applied is not True
        or projection.fact_paths != tuple(fact.path for fact in facts)
    ):
        raise submitted_operation_error(
            completed.operation_id,
            RuntimeRefusalCode.INVALID_FRAME.value,
            terminal_condition=completed.terminal_condition,
            effect=completed.effect,
        )
    return projection


__all__ = ["import_censal_file_facts"]
