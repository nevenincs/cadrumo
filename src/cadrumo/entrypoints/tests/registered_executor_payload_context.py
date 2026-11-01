"""Share the request-building context and builder contract of the conformance payload tables."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from pydantic import BaseModel

from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation

from ...application.operations.operation_definition import OperationDefinition
from ...core.operations import profile_operation_subject
from ...domain.calculations.registry.authority_artifact import ProfileDecodeContext

PayloadResult = tuple[str, BaseModel, bytes | None]


@dataclass(frozen=True)
class PayloadContext:
    """Everything one operation's builder may read to seed state and shape its request."""

    definition: OperationDefinition
    profile_id: UUID
    tmp_path: Path
    operation: PinnedAuthorityOperation
    decode_context: ProfileDecodeContext

    @property
    def definition_id(self) -> str:
        return self.definition.definition_id

    @property
    def profile_subject(self) -> str:
        """The subject addressing the profile through the shared operation-subject codec."""
        return profile_operation_subject(str(self.profile_id))

    @property
    def raw_profile_subject(self) -> str:
        """The unqualified ``profile:<id>`` subject several profile operations still declare."""
        return f"profile:{self.profile_id}"

    def request(self, subject_ref: str, values: dict[str, object], secret: bytes | None = None) -> PayloadResult:
        """Validate the values strictly against the exact request type the definition exports."""
        return subject_ref, self.definition.request_type.model_validate(values, strict=True), secret


PayloadBuilder = Callable[[PayloadContext], PayloadResult]
