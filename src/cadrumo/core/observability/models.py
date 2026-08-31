"""Strict pydantic v2 record types for the run-trace observability layer.

Every type is ``strict=True``, ``frozen=True``, ``extra="forbid"``.
Closed sets are :class:`enum.StrEnum`. The :class:`RunEventPayload` is
a tagged union with an exactly-one-variant invariant enforced by a
``model_validator(mode="after")`` — bare ``dict[str, Any]`` is
deliberately absent from the wire so every persisted JSONL line
round-trips through the model.

Audit data policy
-----------------
Run traces are audit artefacts; payloads will contain data that is
sensitive in a tax / PII sense:

* :attr:`FormFillPayload.value` is the literal form-field value — i.e.
  the tax figure the operator put into an AEAT draft. Treat the file as
  containing tax-return data.
* :attr:`NavigationPayload.url` / :attr:`NavigationPayload.description`
  capture the user's navigation path through AEAT sede. URLs may embed
  session identifiers; callers must not record authentication tokens
  here.
* :attr:`ErrorPayload.message` is free-form and may contain traceback
  fragments with file paths or captured user input.
* :class:`ArgumentRecord` values are recorded verbatim. This layer
  performs no redaction of its own, so any producer populating
  :attr:`RunTrace.arguments` must redact secret-named parameters
  against :data:`cadrumo.core.redaction.ALWAYS_REDACT_KEY_TERMS`
  *before* constructing the record — once a value reaches this model it
  is written to the JSONL trace as given.
* :attr:`RunTrace.cert_fingerprint` is a SHA-256 of the configured
  PKCS#12 on disk — a stable identity marker of the operator's cert,
  not a secret, but identifying.

Callers that sync ``var/runs/`` to cloud storage must understand that
every one of these fields is in scope. The framework does not attempt
DLP-style scanning — it trusts callers not to feed secrets into the
payload fields they control.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, Field, model_validator

from ..identity import AeatBoxNumber, ContentDigest, ContentDigestOrAbsent
from ..models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ..time.utc import validate_utc_aware

#: Canonical shape of a run identifier: 16 lowercase hex characters, the form
#: minted by :func:`core.observability.context._mint_run_id`. Declared once here
#: so the observability records, the workflow link, and the on-disk run-directory
#: guard in :mod:`core.observability.store` describe one identity rather than
#: several independent conventions.
RUN_ID_PATTERN = r"^[0-9a-f]{16}$"

#: A run identifier constrained to :data:`RUN_ID_PATTERN`. Applying it on the
#: record types refuses a malformed id where the record is *built*, not only
#: where it is persisted — and because the store derives ``runs_dir / run_id``
#: from this value, an unconstrained id is also a path-traversal surface.
RunId = Annotated[str, Field(pattern=RUN_ID_PATTERN)]


class ArgumentSource(StrEnum):
    """Provenance label for a CLI argument captured on a :class:`RunTrace`.

    ``ENV``, ``CONFIG`` and ``DEFAULT`` values are recorded for audit
    completeness but are not re-emitted on argv during replay.

    Attributes:
        FLAG: Option-style flag (e.g. ``--since 2026-01-01``).
        POSITIONAL: Positional argument that must be re-emitted in the
            original order with no ``--`` prefix during replay
            (e.g. ``notificacion_id`` on a notification-read command).
        ENV: Value sourced from a process environment variable.
        CONFIG: Value sourced from a configuration file.
        DEFAULT: Value sourced from the option's declared default.
    """

    FLAG = "FLAG"
    POSITIONAL = "POSITIONAL"
    ENV = "ENV"
    CONFIG = "CONFIG"
    DEFAULT = "DEFAULT"


class RunEventKind(StrEnum):
    """Closed catalogue of run-event kinds emitted by the observability layer.

    Attributes:
        STEP_START: Boundary marker entering a logical step.
        STEP_END: Boundary marker leaving a logical step.
        NAVIGATION: A page navigation inside the AEAT sede browser.
        FORM_FILL: A form-field value written into an AEAT draft form.
        ASSERTION: A workflow-level expectation evaluation.
        CACHE_HIT: Indicates a cached lookup served the request.
        ERROR: A captured failure surfaced during the run.
        WORKFLOW_STARTED: Links the run to a workflow-engine run id.
        WORKFLOW_COMPLETED: Marks workflow-engine completion.
    """

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
    """Terminal outcome recorded on a :class:`RunTrace`.

    Attributes:
        OK: The yielded body returned cleanly.
        FAILED: The yielded body raised, or never executed because
            ``STEP_START`` itself failed.
        ABORTED: The run was cancelled before completion.
    """

    OK = "OK"
    FAILED = "FAILED"
    ABORTED = "ABORTED"


class ArgumentRecord(BaseModel):
    """A single CLI argument captured for replay.

    Attributes:
        name: Python parameter name as bound by the wrapped command
            (e.g. ``"as_json"``).
        value: Stringified argument value.
        source: Where the value originated; see :class:`ArgumentSource`.
        cli_flag: Optional override carrying the actual Typer option
            spelling (e.g. ``"--json"``) when the Python parameter name
            differs from the user-facing flag. Without the override,
            :func:`cadrumo.core.observability.replay._argv_from_arguments`
            derives the flag by replacing underscores with dashes —
            which is wrong for renamed options like
            ``typer.Option(False, "--json")`` bound to parameter
            ``as_json``.
    """

    model_config = _STRICT_FROZEN

    name: str
    value: str
    source: ArgumentSource
    cli_flag: str | None = None


class NavigationPayload(BaseModel):
    """Payload for :attr:`RunEventKind.NAVIGATION`.

    Attributes:
        url: Destination URL of the navigation event.
        description: Optional human-readable label for the navigation.
    """

    model_config = _STRICT_FROZEN

    url: str
    description: str = ""


class FormFillPayload(BaseModel):
    """Payload for :attr:`RunEventKind.FORM_FILL`.

    Attributes:
        form_id: Identifier of the AEAT form being filled
            (e.g. ``"aeat-130"``).
        display_number: Browser-visible box number within the form.
        value: Literal value written to the box.
    """

    model_config = _STRICT_FROZEN

    form_id: str
    display_number: AeatBoxNumber
    value: str


class AssertionPayload(BaseModel):
    """Payload for :attr:`RunEventKind.ASSERTION`.

    Attributes:
        expectation: Stable string identifying the assertion.
        passed: Whether the assertion held.
        detail: Optional free-form diagnostic text.
    """

    model_config = _STRICT_FROZEN

    expectation: str
    passed: bool
    detail: str = ""


class CacheHitPayload(BaseModel):
    """Payload for :attr:`RunEventKind.CACHE_HIT`.

    Attributes:
        cache_name: Stable identifier of the cache that served the value.
        key: Cache key whose lookup succeeded.
    """

    model_config = _STRICT_FROZEN

    cache_name: str
    key: str


class ErrorPayload(BaseModel):
    """Payload for :attr:`RunEventKind.ERROR`.

    Attributes:
        error_type: Class name of the captured exception.
        message: Free-form diagnostic text; may include traceback
            fragments. See the module docstring for the redaction
            contract this field is subject to.
    """

    model_config = _STRICT_FROZEN

    error_type: str
    message: str


class StepBoundaryPayload(BaseModel):
    """Payload for :attr:`RunEventKind.STEP_START` and :attr:`RunEventKind.STEP_END`.

    Attributes:
        step_id: Identifier of the step the boundary refers to.
        label: Human-readable label (typically the entrypoint string).
    """

    model_config = _STRICT_FROZEN

    step_id: str
    label: str


class WorkflowLinkPayload(BaseModel):
    """Payload for :attr:`RunEventKind.WORKFLOW_STARTED` / ``WORKFLOW_COMPLETED``.

    Links the observability ``run_id`` to a workflow-engine ``run_id``
    via a ``workflow_run_id`` field; the two identifiers are
    deliberately distinct so the observability layer can wrap a workflow
    invocation without conflating its identity.

    Attributes:
        workflow_run_id: Workflow-engine run id linked to this trace.
    """

    model_config = _STRICT_FROZEN

    workflow_run_id: RunId


class GenericPayload(BaseModel):
    """Structured-but-typed key/value payload for ad-hoc events.

    Fields are a tuple of ``(name, str_value)`` pairs so the wire shape
    stays free of bare ``dict[str, Any]`` while still allowing
    extensibility for downstream call sites.

    Attributes:
        fields: Ordered tuple of ``(name, str_value)`` pairs.
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
    """Tagged-union wrapper for the per-event payload variants.

    Exactly one variant field must be set; the invariant is enforced
    post-construction by :meth:`_exactly_one`.

    Attributes:
        navigation: :class:`NavigationPayload` variant, or ``None``.
        form_fill: :class:`FormFillPayload` variant, or ``None``.
        assertion: :class:`AssertionPayload` variant, or ``None``.
        cache_hit: :class:`CacheHitPayload` variant, or ``None``.
        error: :class:`ErrorPayload` variant, or ``None``.
        step: :class:`StepBoundaryPayload` variant, or ``None``.
        workflow_link: :class:`WorkflowLinkPayload` variant, or ``None``.
        generic: :class:`GenericPayload` variant, or ``None``.
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


def _require_tz_aware(value: datetime) -> datetime:
    """Reject naive or non-UTC datetimes at the pydantic boundary.

    The sort in :func:`cadrumo.core.observability.iter_runs` crashes with
    ``TypeError: can't compare offset-naive and offset-aware datetimes``
    if the runs directory mixes both shapes. Every writer inside the
    observability layer constructs datetimes with ``tzinfo=UTC``, but a
    hand-edited or externally-produced ``trace.json`` could slip a
    naive timestamp past strict validation unless this gate enforces
    timezone awareness up front.

    Args:
        value: Datetime to validate.

    Returns:
        The same datetime, unmodified, when it is UTC-aware.
    """
    return validate_utc_aware(value)


class RunEvent(BaseModel):
    """A single observability event captured during a run.

    Attributes:
        run_id: Owning run identifier (16-char lowercase hex).
        step_id: Step identifier active when the event was emitted.
        kind: One of :class:`RunEventKind`.
        payload: Tagged-union payload; see :class:`RunEventPayload`.
        timestamp: UTC capture time; must be timezone-aware.
        module: ``__name__`` of the caller that emitted the event.
    """

    model_config = _STRICT_FROZEN

    run_id: RunId
    step_id: str
    kind: RunEventKind
    payload: RunEventPayload
    timestamp: datetime
    module: str

    @model_validator(mode="after")
    def _require_tz_aware_timestamp(self) -> RunEvent:
        """Reject naive ``timestamp`` values; see :func:`_require_tz_aware`."""
        _require_tz_aware(self.timestamp)
        return self


class RunTrace(BaseModel):
    """Metadata header persisted as ``trace.json`` for a CLI invocation.

    Attributes:
        run_id: 16-char lowercase hex identifier for the run.
        started_at: UTC enter time of the outermost run context.
        finished_at: UTC exit time, or ``None`` if persistence happens
            before exit.
        entrypoint: Stable CLI entrypoint string.
        arguments: Tuple of :class:`ArgumentRecord` captured for replay.
        corpus_sha256: Fingerprint of the effective
            :class:`cadrumo.core.config.Settings` configuration at enter
            time; gates :func:`replay_run`. Production reads no dotenv, so
            the Settings snapshot is the whole configuration surface.
        db_sha256: Fingerprint of the canonical application data root
            (``Settings.cadrumo_local_storage_root``) at enter time.
        cert_fingerprint: SHA-256 of the configured PKCS#12 cert, or
            ``""`` when no cert is configured.
        outcome: Terminal run outcome; see :class:`RunOutcome`.
        replay_of: Run id of the *immediate* original trace when this
            trace was produced by a replay re-entry, otherwise ``None``.
            Replaying a replay produces a new trace whose ``replay_of``
            points at the second-level trace, NOT at the chain root —
            walk the chain by following each ``replay_of`` link until
            you reach ``None``. Each link is a supervised replay in its
            own right.
    """

    model_config = _STRICT_FROZEN

    run_id: RunId
    started_at: datetime
    finished_at: datetime | None
    entrypoint: str
    arguments: tuple[ArgumentRecord, ...]
    corpus_sha256: ContentDigest
    db_sha256: ContentDigest
    cert_fingerprint: ContentDigestOrAbsent
    outcome: RunOutcome
    replay_of: RunId | None = None

    @model_validator(mode="after")
    def _require_tz_aware_timestamps(self) -> RunTrace:
        """Reject naive ``started_at`` / ``finished_at``."""
        _require_tz_aware(self.started_at)
        if self.finished_at is not None:
            _require_tz_aware(self.finished_at)
        return self


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
