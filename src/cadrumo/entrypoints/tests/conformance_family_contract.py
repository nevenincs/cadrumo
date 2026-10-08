"""Typed contract a per-family module implements to join the registered-executor matrix.

The matrix in ``test_registered_executor_conformance`` runs every production
operation through the real supervisor. A family owns its expected settlement,
its request construction and its seeding in one support module; the matrix
supplies the composed runtime, runs the operation and asserts the shared
terminal, effect, refusal and phase contract before handing the settled
outcome back to the family for its own result and persistence checks.
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from uuid import UUID

from pydantic import BaseModel

from ...application.operations.frontend_requests import OperationObservationSuccessV1
from ...application.operations.operation_definition import OperationDefinition
from ...core.config import override_settings
from ...core.operations import OperationEffect, OperationTerminalCondition
from ...domain.calculations.registry.authority import PinnedAuthorityOperation


@dataclass(frozen=True, slots=True)
class RegisteredExecutorConformanceCase:
    """The settlement one registered operation must reach through the supervisor.

    ``expected_phase_codes`` of ``None`` only requires that some declared phase
    was published; a tuple pins the exact public phase sequence.
    """

    definition_id: str
    expected_terminal: OperationTerminalCondition
    expected_effect: OperationEffect
    expected_phase_codes: tuple[str, ...] | None = None
    expected_refusal_ref: str | None = None


def closed_model_runtime() -> AbstractContextManager[object]:
    """Point the local model runtime at a closed port so no live runtime is ever reached."""
    return override_settings(cadrumo_llm_ollama_chat_url="http://127.0.0.1:1/api/chat")


@dataclass(frozen=True, slots=True)
class ConformanceFamilyContext:
    """What the composed matrix runtime hands a family before submission.

    The profile is enrolled, logged in and active; ``profile_passphrase`` is
    the credential it was enrolled with. ``input_root`` is an empty
    directory, outside the profile storage root, for files a request names.
    """

    definition: OperationDefinition
    profile_id: UUID
    profile_passphrase: str
    input_root: Path
    operation: PinnedAuthorityOperation


class ConformanceResultResolver(Protocol):
    """Resolve the settled operation's public result through encrypted operand custody."""

    def __call__[ProjectionT: BaseModel](self, projection_type: type[ProjectionT], /) -> ProjectionT:
        """Return the typed public result projection, refusing any other type."""
        ...


@dataclass(frozen=True, slots=True)
class ConformanceOutcome:
    """A terminal operation whose shared settlement contract already held."""

    profile_id: UUID
    operation_id: str
    observed: OperationObservationSuccessV1
    resolve_result: ConformanceResultResolver


@dataclass(frozen=True, slots=True)
class ConformancePreparation:
    """One seeded operation ready for submission, and how its outcome is judged.

    ``expected_result`` is compared for equality with the resolved public
    result of its own type; build it independently of the executor under
    test. ``verify`` receives the outcome for checks equality cannot express,
    such as persisted state or a refusal leaving the store unchanged; capture
    any before-state it needs in its closure during preparation.
    """

    subject_ref: str
    request: BaseModel
    secret: bytes | None = None
    expected_result: BaseModel | None = None
    verify: Callable[[ConformanceOutcome], None] | None = None


@dataclass(frozen=True, slots=True)
class ConformanceFamily:
    """Every scenario one operation family contributes to the matrix.

    ``prepare`` is called once per case, inside the composed runtime, with
    the case's own definition. ``closes_model_runtime`` points the local
    model runtime at a closed port for every case in the family.
    """

    cases: tuple[RegisteredExecutorConformanceCase, ...]
    prepare: Callable[[ConformanceFamilyContext], ConformancePreparation]
    closes_model_runtime: bool = False
