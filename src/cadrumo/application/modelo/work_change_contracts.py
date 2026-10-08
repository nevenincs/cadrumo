"""Closed request and settled result contracts for renaming and discarding modelo work."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from ...core.models import STRICT_FROZEN_CONFIG
from ...domain.modelos.work_unit import WorkUnitState
from ..operations.models import CredentialFreeOperationRequest
from .metadata_projection import ModeloWorkMetadataSnapshot

#: ``pattern=r"\S"`` refuses an all-whitespace id, which ``min_length`` alone
#: admits. An identifier is NOT stripped -- unlike a display name, altering it
#: would change what it addresses -- so the guard requires a non-whitespace
#: character and otherwise leaves the value exactly as given. Without it a
#: request naming "   " is journalled, takes a lease, and is scheduled before
#: failing to resolve at execution: real platform work for something that can
#: never settle.
ModeloWorkUnitSubjectId = Annotated[str, Field(min_length=1, max_length=128, pattern=r"\S")]


#: Mirrors the DOMAIN's own display-name constraint, whitespace stripping
#: included. Without the strip this request type is LOOSER than the type it
#: feeds: "   " passes ``min_length=1`` here and then fails the domain's
#: stripped check at the writer -- so the platform journals a request, takes a
#: lease and schedules work for a rename that can never settle. Matching the
#: domain means the request carries exactly what the domain will store.
ModeloWorkUnitName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class ModeloWorkRenameRequest(CredentialFreeOperationRequest):
    """The addressed unit and the display name to give it.

    Credential-free by construction: a rename names a unit and a label, so the
    request carries nothing that would be unsafe to journal.
    """

    model_config = STRICT_FROZEN_CONFIG

    work_unit_id: ModeloWorkUnitSubjectId
    new_name: ModeloWorkUnitName
    observed_name: ModeloWorkUnitName
    observed_updated_at: datetime

    #: The operator this invocation acts as. The platform binds an actor at
    #: submission, never at composition, so baking one into a definition would
    #: make the production registry per-actor.
    actor: Annotated[str, Field(min_length=1, max_length=128)]


class ModeloWorkRenamePublicResultV2(BaseModel):
    """The committed rename and its writer-returned private metadata snapshot."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", validate_default=True)

    result_version: Literal[2] = 2
    work_unit_id: ModeloWorkUnitSubjectId
    name: ModeloWorkUnitName
    bucket_id: Annotated[str, Field(min_length=1, max_length=128)]
    unit: ModeloWorkMetadataSnapshot

    @model_validator(mode="after")
    def _same_committed_unit(self) -> Self:
        if (self.work_unit_id, self.name, self.bucket_id) != (
            self.unit.work_unit_id,
            self.unit.name,
            self.unit.bucket_id,
        ):
            raise ValueError("rename result must describe its committed unit")
        return self


class ModeloWorkDiscardBaseline(BaseModel):
    """The exact unit an operator approved for discard.

    Discard is destructive, so approval is bound to a state rather than to an
    id: the unit must still be the one that was shown. Carrying the observed
    ``updated_at`` is what makes a stale approval refusable instead of silently
    discarding a unit that moved after the operator looked at it.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", validate_default=True)

    work_unit_id: ModeloWorkUnitSubjectId
    name: ModeloWorkUnitName
    observed_updated_at: datetime


class ModeloWorkDiscardRequest(CredentialFreeOperationRequest):
    """The approved unit and the reason recorded against its discard."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", validate_default=True)

    baseline: ModeloWorkDiscardBaseline
    reason: Annotated[str, Field(min_length=1, max_length=500)] | None = None

    #: The operator this invocation acts as. The platform binds an actor at
    #: submission, never at composition, so baking one into a definition would
    #: make the production registry per-actor.
    actor: Annotated[str, Field(min_length=1, max_length=128)]


class ModeloWorkDiscardPublicResultV2(BaseModel):
    """The committed discard and its writer-returned private metadata snapshot."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", validate_default=True)

    result_version: Literal[2] = 2
    work_unit_id: ModeloWorkUnitSubjectId
    bucket_id: Annotated[str, Field(min_length=1, max_length=128)]
    discarded: Literal[True]
    unit: ModeloWorkMetadataSnapshot

    @model_validator(mode="after")
    def _same_committed_unit(self) -> Self:
        if (self.work_unit_id, self.bucket_id) != (self.unit.work_unit_id, self.unit.bucket_id) or (
            self.unit.state is not WorkUnitState.DESCARTADO
        ):
            raise ValueError("discard result must describe its committed unit")
        return self
