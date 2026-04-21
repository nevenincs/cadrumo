"""Strict pydantic v2 record types for the run-trace observability layer (#99).

Every type is ``strict=True``, ``frozen=True``, ``extra="forbid"``. Closed
sets are :class:`enum.StrEnum`. The :class:`RunEventPayload` is a tagged
union with an exactly-one-variant invariant enforced by a
``model_validator(mode="after")`` — we deliberately avoid bare
``dict[str, Any]`` anywhere on the wire so every persisted JSONL line
round-trips through the model.

Audit data policy (#99, live-write safety charter #116)
-------------------------------------------------------
Run traces are audit artefacts; payloads will contain data that is
sensitive in a tax / PII sense:

- :class:`FormFillPayload.value` is the literal casilla value — i.e.
  the tax figure the operator put into an AEAT draft. Treat this file
  as containing tax-return data.
- :class:`NavigationPayload.url` / ``description`` capture the user's
  navigation path through AEAT sede. URLs may embed session
  identifiers; callers must not record authentication tokens here.
- :class:`ErrorPayload.message` is free-form and may contain
  traceback fragments with file paths or captured user input.
- :class:`ArgumentRecord` values are redacted for secret-named
  parameters by :func:`aeat.cli._observability.build_arguments`
  (``password`` / ``secret`` / ``token`` / etc. → ``"***"``). Other
  argument values are recorded verbatim.
- :class:`RunTrace.cert_fingerprint` is a SHA-256 of the configured
  PKCS#12 on disk — a stable identity marker of the operator's cert,
  not a secret, but identifying.

Callers that sync ``var/runs/`` to cloud storage must understand
that every one of these fields is in scope. The framework does not
attempt DLP-style scanning — it trusts callers not to feed secrets
into the payload fields they control.

See [[2026-04-14-run-trace-adr]] decision D3 for the rationale.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, model_validator

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")


class ArgumentSource(StrEnum):
    """Where a CLI argument value originated from.

    ``FLAG`` captures option-style flags (e.g. ``--since 2026-01-01``).
    ``POSITIONAL`` captures positional arguments that must be
    re-emitted in the original order with no ``--`` prefix during
    replay (e.g. ``notificacion_id`` on ``aeat inbox show``). ``ENV``,
    ``CONFIG`` and ``DEFAULT`` are captured for audit completeness but
    are not re-emitted on argv.
    """

    FLAG = "FLAG"
    POSITIONAL = "POSITIONAL"
    ENV = "ENV"
    CONFIG = "CONFIG"
    DEFAULT = "DEFAULT"


class RunEventKind(StrEnum):
    """Closed catalogue of run-event kinds emitted by the observability layer."""

    STEP_START = "STEP_START"
    STEP_END = "STEP_END"
    NAVIGATION = "NAVIGATION"
    FORM_FILL = "FORM_FILL"
    ASSERTION = "ASSERTION"
    CACHE_HIT = "CACHE_HIT"
    ERROR = "ERROR"
    WORKFLOW_STARTED = "WORKFLOW_STARTED"
    WORKFLOW_COMPLETED = "WORKFLOW_COMPLETED"


class RunOutcome(StrEnum):
    """Terminal outcome recorded on a :class:`RunTrace`."""

    OK = "OK"
    FAILED = "FAILED"
    ABORTED = "ABORTED"


class ArgumentRecord(BaseModel):
    """A single CLI argument captured for replay."""

    model_config = _STRICT_FROZEN

    name: str
    value: str
    source: ArgumentSource


class NavigationPayload(BaseModel):
    """Payload for :attr:`RunEventKind.NAVIGATION`."""

    model_config = _STRICT_FROZEN

    url: str
    description: str = ""


class FormFillPayload(BaseModel):
    """Payload for :attr:`RunEventKind.FORM_FILL`."""

    model_config = _STRICT_FROZEN

    form_id: str
    casilla: str
    value: str


class AssertionPayload(BaseModel):
    """Payload for :attr:`RunEventKind.ASSERTION`."""

    model_config = _STRICT_FROZEN

    expectation: str
    passed: bool
    detail: str = ""


class CacheHitPayload(BaseModel):
    """Payload for :attr:`RunEventKind.CACHE_HIT`."""

    model_config = _STRICT_FROZEN

    cache_name: str
    key: str


class ErrorPayload(BaseModel):
    """Payload for :attr:`RunEventKind.ERROR`."""

    model_config = _STRICT_FROZEN

    error_type: str
    message: str


class StepBoundaryPayload(BaseModel):
    """Payload for :attr:`RunEventKind.STEP_START` / ``STEP_END``."""

    model_config = _STRICT_FROZEN

    step_id: str
    label: str


class WorkflowLinkPayload(BaseModel):
    """Payload for ``WORKFLOW_STARTED`` / ``WORKFLOW_COMPLETED`` events.

    Links the observability ``run_id`` to a workflow-engine ``run_id``
    via a ``workflow_run_id`` field (the two identifiers are
    deliberately distinct — see ADR D2).
    """

    model_config = _STRICT_FROZEN

    workflow_run_id: str


class GenericPayload(BaseModel):
    """Free-form, structured-but-typed kv payload.

    Fields are a tuple of ``(name, str_value)`` pairs so the wire shape
    stays free of bare ``dict[str, Any]`` while still allowing
    extensibility for downstream call sites.
    """

    model_config = _STRICT_FROZEN

    fields: tuple[tuple[str, str], ...] = ()


_PAYLOAD_FIELDS: tuple[str, ...] = (
    "navigation",
    "form_fill",
    "assertion",
    "cache_hit",
    "error",
    "step",
    "workflow_link",
    "generic",
)


class RunEventPayload(BaseModel):
    """Tagged-union payload wrapper.

    Exactly one variant field must be set; enforced by a
    ``model_validator(mode="after")``.
    """

    model_config = _STRICT_FROZEN

    navigation: NavigationPayload | None = None
    form_fill: FormFillPayload | None = None
    assertion: AssertionPayload | None = None
    cache_hit: CacheHitPayload | None = None
    error: ErrorPayload | None = None
    step: StepBoundaryPayload | None = None
    workflow_link: WorkflowLinkPayload | None = None
    generic: GenericPayload | None = None

    @model_validator(mode="after")
    def _exactly_one(self) -> RunEventPayload:
        """Enforce that exactly one variant field is populated."""
        set_fields = [name for name in _PAYLOAD_FIELDS if getattr(self, name) is not None]
        if len(set_fields) != 1:
            raise ValueError(
                f"RunEventPayload must set exactly one variant, got {set_fields}",
            )
        return self


class RunEvent(BaseModel):
    """A single observability event captured during a run."""

    model_config = _STRICT_FROZEN

    run_id: str
    step_id: str
    kind: RunEventKind
    payload: RunEventPayload
    timestamp: datetime
    module: str


class RunTrace(BaseModel):
    """The metadata header for a single CLI invocation."""

    model_config = _STRICT_FROZEN

    run_id: str
    started_at: datetime
    finished_at: datetime | None
    entrypoint: str
    arguments: tuple[ArgumentRecord, ...]
    corpus_sha256: str
    db_sha256: str
    cert_fingerprint: str
    outcome: RunOutcome


__all__ = [
    "ArgumentRecord",
    "ArgumentSource",
    "AssertionPayload",
    "CacheHitPayload",
    "ErrorPayload",
    "FormFillPayload",
    "GenericPayload",
    "NavigationPayload",
    "RunEvent",
    "RunEventKind",
    "RunEventPayload",
    "RunOutcome",
    "RunTrace",
    "StepBoundaryPayload",
    "WorkflowLinkPayload",
]
