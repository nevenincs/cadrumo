"""Model runs a tax worker asks the agent service to perform through the runtime.

Requests only: neither direction carries a key, a bearer or any credential.
The runtime forwards a run between the worker and the profile's admitted
service under :data:`MODEL_RUN_CAPABILITY` without reading the body, which
travels as bounded secret frames because it may hold taxpayer evidence.
"""

from __future__ import annotations

import base64
import json
from enum import StrEnum
from typing import Annotated, Final, Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field, JsonValue, NonNegativeInt, PositiveInt, field_validator, model_validator

from cadrumo.core.hex import Hex64Str
from cadrumo.core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG

MODEL_RUN_CAPABILITY: Final = "model-run"
"""The service descriptor capability that admits model runs."""

MODEL_RUN_MAX_BODY_BYTES: Final = 32 * 1024 * 1024
"""Upper bound on one encoded run body: prompt, system text and attachments."""

MODEL_RUN_MAX_OUTPUT_BYTES: Final = 1024 * 1024
"""Upper bound on the reply text one run may return."""

MODEL_RUN_MAX_DEADLINE_SECONDS: Final = 900
"""Upper bound on how long one run may take before it is refused as overdue."""

MODEL_RUN_MAX_ATTACHMENTS: Final = 64

MODEL_RUN_MAX_ROLES: Final = 16
"""Upper bound on the roles one selections read may report."""

MODEL_RUN_MIN_CONTEXT_TOKENS: Final = 512
MODEL_RUN_MAX_CONTEXT_TOKENS: Final = 1_048_576
"""The context window bounds the agent admits for a background run."""

MODEL_RUN_MAX_SCHEMA_BYTES: Final = 32_768
"""Upper bound on a response schema, as compact UTF-8 JSON."""

MODEL_RUN_MODEL_ID_MAX_LENGTH: Final = 512
"""The longest model id, in characters, the agent's catalogues carry."""

MODEL_RUN_MODEL_ID_PATTERN: Final = r"^[^\x00-\x1f\x7f]{1,512}$"
"""A model id as the agent's catalogues carry it: 1 to 512 characters, none a C0 control or DEL."""

MODEL_RUN_PROVIDER_ID_MAX_LENGTH: Final = 64
"""The longest provider identity id, in characters: the agent's provider metadata key bound."""

MODEL_RUN_PROVIDER_ID_PATTERN: Final = rf"^[a-z][a-z0-9_]{{0,{MODEL_RUN_PROVIDER_ID_MAX_LENGTH - 1}}}$"
"""A provider identity id: a lowercase storage-safe slug of 1 to 64 characters."""

MODEL_RUN_LANE_ID_MAX_LENGTH: Final = MODEL_RUN_PROVIDER_ID_MAX_LENGTH + len("_api")
"""The longest lane id, in characters: a provider id, an underscore and its three-letter transport."""

MODEL_RUN_LANE_ID_PATTERN: Final = rf"^[a-z][a-z0-9_]{{0,{MODEL_RUN_LANE_ID_MAX_LENGTH - 1}}}$"
"""A lane id: a lowercase storage-safe slug of 1 to 68 characters; ids stored under the earlier 40 still match."""

_PROVIDER_ID = MODEL_RUN_PROVIDER_ID_PATTERN
_LANE_ID = MODEL_RUN_LANE_ID_PATTERN
_TRANSPORT = r"^[a-z][a-z0-9_]{0,15}$"
_MODEL = MODEL_RUN_MODEL_ID_PATTERN
_ROLE = r"^[a-z][a-z0-9_]{0,63}$"


_ContextTokens = Annotated[int, Field(ge=MODEL_RUN_MIN_CONTEXT_TOKENS, le=MODEL_RUN_MAX_CONTEXT_TOKENS)]


def _compact_json(value: dict[str, JsonValue]) -> bytes:
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"), sort_keys=True).encode("utf-8")


class ModelRunRefusalCode(StrEnum):
    """Why a model run produced no usable output; exactly one per refusal."""

    SERVICE_UNAVAILABLE = "service_unavailable"
    NOT_SIGNED_IN = "not_signed_in"
    PROFILE_LOCKED = "profile_locked"
    NO_SELECTION = "no_selection"
    UNKNOWN_ROLE = "unknown_role"
    """The request named a role outside the role vocabulary: a caller defect, not a missing selection."""
    LANE_UNAVAILABLE = "lane_unavailable"
    MODEL_NOT_INSTALLED = "model_not_installed"
    """The selected model is not installed on the lane's local server: the person installs it or selects another."""
    INPUT_NOT_SUPPORTED = "input_not_supported"
    OPTION_NOT_SUPPORTED = "option_not_supported"
    """The run named a reply option its lane does not honour: a caller defect, not a configuration gap."""
    RUN_FAILED = "run_failed"
    OUTPUT_INVALID = "output_invalid"
    DEADLINE_EXCEEDED = "deadline_exceeded"
    REFUSED_BY_PROVIDER = "refused_by_provider"
    CONSENT_MISSING = "consent_missing"


class ModelRunMediaKind(StrEnum):
    """The attachment families a lane's catalog entry may declare it accepts."""

    IMAGE = "image"
    PDF = "pdf"


def model_run_media_kind(media_type: str) -> ModelRunMediaKind | None:
    """Return the family of an attachment's media type, or ``None`` when no family covers it."""
    normalized = media_type.strip().lower()
    if normalized.startswith("image/"):
        return ModelRunMediaKind.IMAGE
    if normalized == "application/pdf":
        return ModelRunMediaKind.PDF
    return None


class ModelRunLicence(BaseModel):
    """The licence the agent's catalogue states for a model; shown to the person, never judged."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    spdx: Annotated[str, Field(min_length=1, max_length=256)] | None
    name: Annotated[str, Field(min_length=1, max_length=256)]
    digest: Annotated[str, Field(pattern=r"^sha256:[0-9a-f]{64}$")]


class ModelRunLane(BaseModel):
    """The lane and model the service resolved for one role; nothing here is secret.

    ``reads_off_host`` is the lane's catalogue declaration of whether a run on
    it sends material off this computer. It has no default: a lane whose
    catalogue entry says nothing is not a lane, so it cannot read as on-host.

    ``licence``, ``size_bytes``, ``vision`` and ``context_length`` are the
    facts the agent's catalogue states for the model. Each is ``None`` when the
    catalogue states nothing for it, and none has a default, so an answer that
    omits one is refused rather than read as unstated.

    ``accepted_media`` is what the provider catalog reports the lane accepts in
    a background run. ``None`` means the catalog says nothing, and the agent
    decides at admission.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    provider_id: Annotated[str, Field(pattern=_PROVIDER_ID)]
    transport: Annotated[str, Field(pattern=_TRANSPORT)]
    model: Annotated[str, Field(pattern=_MODEL)]
    reads_off_host: bool
    licence: ModelRunLicence | None
    size_bytes: NonNegativeInt | None
    """The model's download size in bytes; the agent states ``0`` for an empty or unknown size."""
    vision: bool | None
    context_length: PositiveInt | None
    accepted_media: tuple[ModelRunMediaKind, ...] | None = None


class ModelRunSelectedModel(BaseModel):
    """The lane and model the person stored for one role, as stored; nothing here is secret."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    lane_id: Annotated[str, Field(pattern=_LANE_ID)]
    model: Annotated[str, Field(pattern=_MODEL)]


class ModelRunRoleSelection(BaseModel):
    """One role's selection state: what is selected, and the lane a run would use or why it would refuse.

    ``selected`` is ``None`` when the role has no selection or the selection
    could not be read. Exactly one of ``lane`` and ``refusal`` is present, and
    a usable ``lane`` always comes from a selection.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    role: Annotated[str, Field(pattern=_ROLE)]
    selected: ModelRunSelectedModel | None = None
    lane: ModelRunLane | None = None
    refusal: ModelRunRefusalCode | None = None

    @model_validator(mode="after")
    def _usable_or_refused(self) -> Self:
        if (self.lane is None) == (self.refusal is None):
            raise ValueError("a role's state carries exactly one of a lane or a refusal")
        if self.lane is not None and self.selected is None:
            raise ValueError("a usable lane comes only from a selection")
        return self


class ModelRunConsentBinding(BaseModel):
    """The lane a person's off-host consent was recorded for, carried with the run it permits.

    Only a run on a lane that reads off-host carries one, and the service
    refuses such a run without it.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    evidence_content_address: Hex64Str
    provider_id: Annotated[str, Field(pattern=_PROVIDER_ID)]
    transport: Annotated[str, Field(pattern=_TRANSPORT)]
    model: Annotated[str, Field(pattern=_MODEL)]

    def matches(self, lane: ModelRunLane) -> bool:
        """Return whether ``lane`` is the one this consent was recorded for."""
        return (self.provider_id, self.transport, self.model) == (lane.provider_id, lane.transport, lane.model)


class ModelRunAttachment(BaseModel):
    """One document handed to the model as input, never persisted by any carrier."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    media_type: Annotated[str, Field(min_length=3, max_length=127, pattern=r"^[a-z0-9.+-]+/[a-z0-9.+-]+$")]
    base64_data: Annotated[str, Field(min_length=1)]

    @field_validator("base64_data")
    @classmethod
    def _is_base64(cls, value: str) -> str:
        base64.b64decode(value, validate=True)
        return value


class ModelRunBody(BaseModel):
    """The private part of a run, encoded once and carried only on secret frames."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    system: str | None = None
    prompt: Annotated[str, Field(min_length=1)]
    attachments: tuple[ModelRunAttachment, ...] = Field(default=(), max_length=MODEL_RUN_MAX_ATTACHMENTS)
    max_output_tokens: Annotated[int, Field(ge=1, le=65_536)]
    temperature: Annotated[float, Field(ge=0.0, le=1.0)] | None = None
    context_tokens: _ContextTokens | None = None
    """The context window the run needs; only a lane that honours it receives it."""
    response_schema: dict[str, JsonValue] | None = None
    """A JSON Schema object the reply is constrained to; the caller still extracts and validates the reply."""

    @field_validator("response_schema")
    @classmethod
    def _schema_within_bound(cls, value: dict[str, JsonValue] | None) -> dict[str, JsonValue] | None:
        if value is not None and len(_compact_json(value)) > MODEL_RUN_MAX_SCHEMA_BYTES:
            raise ValueError("response schema exceeds its bound")
        return value


class ModelRunHeader(BaseModel):
    """The non-secret part of a run: the role, the bound on its time and the consent it carries.

    ``consent`` is required when the lane the role resolves to reads
    off-host, and must then name that lane.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    role: Annotated[str, Field(pattern=_ROLE)]
    deadline_seconds: Annotated[int, Field(ge=1, le=MODEL_RUN_MAX_DEADLINE_SECONDS)]
    consent: ModelRunConsentBinding | None = None

    def consent_admits(self, lane: ModelRunLane) -> bool:
        """Return whether this run's consent admits it on ``lane``, the lane its role resolves to now.

        A lane that reads off-host admits only a run carrying consent recorded
        for that lane. A lane that stays on this computer needs none, but
        consent recorded for another lane never admits a run.
        """
        if self.consent is None:
            return not lane.reads_off_host
        return self.consent.matches(lane)


class ModelRunOutput(BaseModel):
    """The run's final reply text and the lane that produced it."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    text: str
    provider_id: Annotated[str, Field(pattern=_PROVIDER_ID)]
    transport: Annotated[str, Field(pattern=_TRANSPORT)]
    model: Annotated[str, Field(pattern=_MODEL)]
    agent_version: Annotated[str, Field(min_length=1, max_length=64)]


class ModelRunRefusal(BaseModel):
    """A run or lookup that produced nothing, for one closed reason."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    code: ModelRunRefusalCode


class ModelRunServed(BaseModel):
    """The lane that ran a request; the reply text travels separately, on secret frames."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    provider_id: Annotated[str, Field(pattern=_PROVIDER_ID)]
    transport: Annotated[str, Field(pattern=_TRANSPORT)]
    model: Annotated[str, Field(pattern=_MODEL)]
    agent_version: Annotated[str, Field(min_length=1, max_length=64)]


class ModelRunOutcome(BaseModel):
    """Exactly one answer to a lookup, a selections read or a run.

    The answer is a lane, every role's state, a served run, or a refusal.

    ``text_byte_count`` is the length of the reply text that follows a served
    run on secret frames, and zero otherwise.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    lane: ModelRunLane | None = None
    selections: tuple[ModelRunRoleSelection, ...] | None = Field(default=None, max_length=MODEL_RUN_MAX_ROLES)
    served: ModelRunServed | None = None
    refusal: ModelRunRefusalCode | None = None
    text_byte_count: Annotated[NonNegativeInt, Field(le=MODEL_RUN_MAX_OUTPUT_BYTES)] = 0

    @model_validator(mode="after")
    def _exactly_one_answer(self) -> Self:
        if sum(value is not None for value in (self.lane, self.selections, self.served, self.refusal)) != 1:
            raise ValueError("a model run outcome carries exactly one lane, selections, served run or refusal")
        if self.selections is not None and len({item.role for item in self.selections}) != len(self.selections):
            raise ValueError("a selections read reports each role once")
        if (self.served is None) != (self.text_byte_count == 0):
            raise ValueError("reply text follows a served run and nothing else")
        return self


class ModelRunRequested(BaseModel):
    """Pushed by the runtime to a profile's admitted service: a lookup or a run waits under ``run_id``.

    It carries nothing private. The service fetches the waiting request, and
    answers it, with requests on its own connection.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    kind: Literal["model_run_requested"] = "model_run_requested"
    runtime_boot_id: UUID
    connection_id: UUID
    profile_id: UUID
    run_id: UUID


class ModelRunFetchRequest(BaseModel):
    """The service asks for the waiting request ``run_id`` under its exact lease."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    action: Literal["model_run_fetch"] = "model_run_fetch"
    request_id: UUID
    profile_id: UUID
    session_id: UUID
    lease_id: UUID
    run_id: UUID


class ModelRunFetched(BaseModel):
    """The waiting request: a run when ``header`` is present, whose body follows, otherwise a read.

    A read names a ``role`` to look up that role's lane, or none to read every
    role's selection state.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    kind: Literal["model_run_fetched"] = "model_run_fetched"
    request_id: UUID
    runtime_boot_id: UUID
    connection_id: UUID
    run_id: UUID
    role: Annotated[str, Field(pattern=_ROLE)] | None
    header: ModelRunHeader | None = None
    body_byte_count: Annotated[NonNegativeInt, Field(le=MODEL_RUN_MAX_BODY_BYTES)] = 0

    @model_validator(mode="after")
    def _run_carries_a_body(self) -> Self:
        if (self.header is None) != (self.body_byte_count == 0):
            raise ValueError("a run carries a body and a lookup carries none")
        if self.header is not None and self.header.role != self.role:
            raise ValueError("a run names the role its header names")
        return self


class ModelRunCompleteRequest(BaseModel):
    """The service answers the request ``run_id``; served reply text follows on secret frames."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    action: Literal["model_run_complete"] = "model_run_complete"
    request_id: UUID
    profile_id: UUID
    session_id: UUID
    lease_id: UUID
    run_id: UUID
    outcome: ModelRunOutcome


class ModelRunCompleted(BaseModel):
    """The runtime took the answer; ``accepted`` is false when nobody waits for it any longer."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    kind: Literal["model_run_completed"] = "model_run_completed"
    request_id: UUID
    runtime_boot_id: UUID
    connection_id: UUID
    run_id: UUID
    accepted: bool


def encode_model_run_body(body: ModelRunBody) -> bytearray:
    """Return the body's bounded encoding, refusing one larger than :data:`MODEL_RUN_MAX_BODY_BYTES`."""
    encoded = bytearray(body.model_dump_json().encode("utf-8"))
    if len(encoded) > MODEL_RUN_MAX_BODY_BYTES:
        encoded[:] = bytes(len(encoded))
        raise ValueError("model run body exceeds its bound")
    return encoded


def decode_model_run_body(encoded: bytes | bytearray) -> ModelRunBody:
    """Validate a received body encoding."""
    if len(encoded) > MODEL_RUN_MAX_BODY_BYTES:
        raise ValueError("model run body exceeds its bound")
    return ModelRunBody.model_validate_json(bytes(encoded))


__all__ = [
    "MODEL_RUN_CAPABILITY",
    "MODEL_RUN_LANE_ID_MAX_LENGTH",
    "MODEL_RUN_LANE_ID_PATTERN",
    "MODEL_RUN_MAX_ATTACHMENTS",
    "MODEL_RUN_MAX_BODY_BYTES",
    "MODEL_RUN_MAX_DEADLINE_SECONDS",
    "MODEL_RUN_MAX_OUTPUT_BYTES",
    "MODEL_RUN_MAX_ROLES",
    "MODEL_RUN_MODEL_ID_MAX_LENGTH",
    "MODEL_RUN_MODEL_ID_PATTERN",
    "MODEL_RUN_PROVIDER_ID_MAX_LENGTH",
    "MODEL_RUN_PROVIDER_ID_PATTERN",
    "ModelRunAttachment",
    "ModelRunBody",
    "ModelRunCompleteRequest",
    "ModelRunCompleted",
    "ModelRunConsentBinding",
    "ModelRunFetchRequest",
    "ModelRunFetched",
    "ModelRunHeader",
    "ModelRunLane",
    "ModelRunLicence",
    "ModelRunMediaKind",
    "ModelRunOutcome",
    "ModelRunOutput",
    "ModelRunRefusal",
    "ModelRunRefusalCode",
    "ModelRunRequested",
    "ModelRunRoleSelection",
    "ModelRunSelectedModel",
    "ModelRunServed",
    "decode_model_run_body",
    "encode_model_run_body",
    "model_run_media_kind",
]
