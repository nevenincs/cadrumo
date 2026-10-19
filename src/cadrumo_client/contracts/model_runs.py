"""Model runs a tax worker asks the agent service to perform through the runtime.

Requests only: neither direction carries a key, a bearer or any credential.
The runtime forwards a run between the worker and the profile's admitted
service under :data:`MODEL_RUN_CAPABILITY` without reading the body, which
travels as bounded secret frames because it may hold taxpayer evidence.
"""

from __future__ import annotations

import base64
from enum import StrEnum
from typing import Annotated, Final

from pydantic import BaseModel, Field, field_validator

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

_LANE_ID = r"^[a-z][a-z0-9_]{0,39}$"
_TRANSPORT = r"^[a-z][a-z0-9_]{0,15}$"
_MODEL = r"^[\x21-\x7e]{1,256}$"
_ROLE = r"^[a-z][a-z0-9_]{0,63}$"


class ModelRunRefusalCode(StrEnum):
    """Why a model run produced no usable output; exactly one per refusal."""

    SERVICE_UNAVAILABLE = "service_unavailable"
    NOT_SIGNED_IN = "not_signed_in"
    PROFILE_LOCKED = "profile_locked"
    NO_SELECTION = "no_selection"
    LANE_UNAVAILABLE = "lane_unavailable"
    INPUT_NOT_SUPPORTED = "input_not_supported"
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


class ModelRunLane(BaseModel):
    """The lane and model the service resolved for one role; nothing here is secret.

    ``accepted_media`` is what the provider catalog reports the lane accepts in
    a background run. ``None`` means the catalog says nothing, and the agent
    decides at admission.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    provider_id: Annotated[str, Field(pattern=_LANE_ID)]
    transport: Annotated[str, Field(pattern=_TRANSPORT)]
    model: Annotated[str, Field(pattern=_MODEL)]
    accepted_media: tuple[ModelRunMediaKind, ...] | None = None


class ModelRunConsentBinding(BaseModel):
    """The lane a person's off-host consent was recorded for, carried with the run it permits."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    evidence_content_address: Hex64Str
    provider_id: Annotated[str, Field(pattern=_LANE_ID)]
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


class ModelRunHeader(BaseModel):
    """The non-secret part of a run: the role, the bound on its time and the consent it carries."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    role: Annotated[str, Field(pattern=_ROLE)]
    deadline_seconds: Annotated[int, Field(ge=1, le=MODEL_RUN_MAX_DEADLINE_SECONDS)]
    consent: ModelRunConsentBinding | None = None


class ModelRunOutput(BaseModel):
    """The run's final reply text and the lane that produced it."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    text: str
    provider_id: Annotated[str, Field(pattern=_LANE_ID)]
    transport: Annotated[str, Field(pattern=_TRANSPORT)]
    model: Annotated[str, Field(pattern=_MODEL)]
    agent_version: Annotated[str, Field(min_length=1, max_length=64)]


class ModelRunRefusal(BaseModel):
    """A run or lookup that produced nothing, for one closed reason."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    code: ModelRunRefusalCode


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
    "MODEL_RUN_MAX_ATTACHMENTS",
    "MODEL_RUN_MAX_BODY_BYTES",
    "MODEL_RUN_MAX_DEADLINE_SECONDS",
    "MODEL_RUN_MAX_OUTPUT_BYTES",
    "ModelRunAttachment",
    "ModelRunBody",
    "ModelRunConsentBinding",
    "ModelRunHeader",
    "ModelRunLane",
    "ModelRunMediaKind",
    "ModelRunOutput",
    "ModelRunRefusal",
    "ModelRunRefusalCode",
    "decode_model_run_body",
    "encode_model_run_body",
    "model_run_media_kind",
]
