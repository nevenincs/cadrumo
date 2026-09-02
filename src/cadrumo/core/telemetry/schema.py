"""Closed remote-telemetry metric-key registry and the allowlisted payload.

Every telemetry emission is shaped by
:class:`~core.telemetry.TelemetryEventPayload`, a ``pydantic`` model whose
field set IS the entire content allowlist: there is no ``extra`` passthrough,
no free-text ``message``/``context`` field, and no string field wide enough to
carry operator-controlled financial or identity content. A producer's counters
and timings are validated against
:data:`~core.telemetry.TELEMETRY_METRIC_REGISTRY` — a closed, code-authored
mapping from command dotted-path to its declared metric keys — so an
unregistered key raises :class:`~core.telemetry.TelemetrySchemaError` rather
than silently passing through, and a registered-but-not-``remote_allowed`` key
is silently dropped from the outgoing payload (it may still exist for
local-only diagnostics; it is simply never remote-eligible).

Extending the registry is a deliberate, reviewable code change — adding a new
command's schema entry, or flipping a key's ``remote_allowed`` — never an
implicit consequence of adding a new local metric elsewhere in the codebase.

See Also:
    :func:`~core.telemetry.build_telemetry_payload`
        Validates producers against this registry before emission.
    :func:`~core.telemetry.emit_telemetry_event`
        The only remote-eligible dispatch point for a validated payload.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

from pydantic import BaseModel, Field

from ..identity import ContentDigest
from ..models import STRICT_FROZEN_CONFIG
from .errors import TelemetrySchemaError

__all__ = [
    "TELEMETRY_METRIC_REGISTRY",
    "CounterSpec",
    "TelemetryEventPayload",
    "TimingSpec",
    "build_telemetry_payload",
]

_SCHEMA_VERSION = 1


class CounterSpec(BaseModel):
    """Declared shape of one counter metric key.

    Attributes:
        description: Short, non-sensitive description of what the counter
            measures (e.g. ``"invocation count"``). Never operator content.
        remote_allowed: Whether this counter is eligible for remote
            transmission at all. ``False`` keeps the key local-only even when
            the deployment opts into remote telemetry.
    """

    model_config = STRICT_FROZEN_CONFIG

    description: str = Field(min_length=1)
    remote_allowed: bool = False


class TimingSpec(BaseModel):
    """Declared shape of one timing metric key (milliseconds).

    Attributes:
        description: Short, non-sensitive description of what the timing
            measures.
        remote_allowed: Whether this timing is eligible for remote
            transmission at all.
    """

    model_config = STRICT_FROZEN_CONFIG

    description: str = Field(min_length=1)
    remote_allowed: bool = False


class MetricSchema(BaseModel):
    """Closed declaration of the counters and timings one command may emit.

    Attributes:
        command: Dotted-path command identifier the schema governs (e.g.
            ``"diagnostics.run_health"``). Matches
            :attr:`~core.telemetry.TelemetryEventPayload.command`.
        counters: Closed mapping of counter key ->
            :class:`~core.telemetry.CounterSpec`.
        timings_ms: Closed mapping of timing key ->
            :class:`~core.telemetry.TimingSpec`.
    """

    model_config = STRICT_FROZEN_CONFIG

    command: str = Field(min_length=1)
    counters: Mapping[str, CounterSpec] = Field(default_factory=dict)
    timings_ms: Mapping[str, TimingSpec] = Field(default_factory=dict)


class TelemetryEventPayload(BaseModel):
    """The one and only shape a telemetry emission may take.

    This model's field set IS the transmission allowlist. There is no
    ``extra`` field (``model_config`` forbids it), no free-text field wide
    enough to carry a NIF, a transaction description, a file path, or any
    other operator-controlled content, and no nested nesting depth that could
    smuggle an unvetted payload through. ``error_kind`` is a short closed
    label (e.g. ``"timeout"``, ``"validation_error"``), never raw exception
    text.

    Attributes:
        schema_version: Payload schema version, for forward compatibility.
        workspace_hash: Stable pseudonymous identifier for the local
            deployment (never the operator's NIF or profile id).
        command: The dotted-path metric-schema key this event belongs to.
        counters: Emitted counter values, restricted to keys registered as
            ``remote_allowed`` for ``command``.
        timings_ms: Emitted timing values (milliseconds), restricted the same
            way.
        succeeded: Whether the measured operation succeeded.
        error_kind: Optional short closed error-kind label when
            ``succeeded`` is ``False``.
        captured_at: ISO-8601 UTC capture timestamp.
    """

    model_config = STRICT_FROZEN_CONFIG

    schema_version: int = Field(default=_SCHEMA_VERSION, ge=1)
    workspace_hash: ContentDigest
    command: str = Field(min_length=1)
    counters: Mapping[str, int] = Field(default_factory=dict)
    timings_ms: Mapping[str, int] = Field(default_factory=dict)
    succeeded: bool
    error_kind: str | None = Field(default=None, max_length=64)
    captured_at: str = Field(min_length=1)


TELEMETRY_METRIC_REGISTRY: Mapping[str, MetricSchema] = MappingProxyType(
    {
        "diagnostics.llm_run": MetricSchema(
            command="diagnostics.llm_run",
            counters={
                "runs": CounterSpec(
                    description="Count of completed local LLM classification/completion runs.",
                    remote_allowed=True,
                ),
                "succeeded": CounterSpec(
                    description="Count of local LLM runs that completed without raising.",
                    remote_allowed=True,
                ),
                "failed": CounterSpec(
                    description="Count of local LLM runs that raised.",
                    remote_allowed=True,
                ),
            },
            timings_ms={
                "duration": TimingSpec(
                    description="Wall-clock local LLM run duration in milliseconds.",
                    remote_allowed=True,
                ),
            },
        ),
    },
)
"""Closed command -> :class:`MetricSchema` registry.

Every entry declares only non-sensitive operational counters/timings: CLI
command-invocation counts and duration, local-LLM-run counts and duration, and
error-kind occurrence frequency. ``error_kind`` on
:class:`~core.telemetry.TelemetryEventPayload` is always a short closed label
(an exception class name such as ``"LLMClassifierError"``, mirroring
:attr:`~adapters.outbound.llm.LLMRunRecord.error_kind`) -- never raw
exception text, a file path, a NIF, or any other operator-controlled content.
No entry here declares a counter/timing keyed by anything financial, personal,
or free-text; extending this registry with such a key is refused structurally
by :class:`~core.telemetry.TelemetryEventPayload`'s ``extra="forbid"``
allowlist regardless of what a producer attempts to pass.
"""


def build_telemetry_payload(
    *,
    workspace_hash: str,
    command: str,
    counters: Mapping[str, int] | None = None,
    timings_ms: Mapping[str, int] | None = None,
    succeeded: bool,
    error_kind: str | None = None,
    captured_at: str,
    registry: Mapping[str, MetricSchema] | None = None,
) -> TelemetryEventPayload:
    """Build an allowlisted payload for ``command``.

    Validates every counter/timing key against
    :data:`~core.telemetry.TELEMETRY_METRIC_REGISTRY`: a key that is not
    declared for ``command`` at all raises
    :class:`~core.telemetry.TelemetrySchemaError` (an authoring error -- the
    producer must register the key first); a key that IS declared but not
    ``remote_allowed`` is silently dropped from the returned payload (it stays
    a valid local-only metric; it is simply never remote-eligible).

    Args:
        workspace_hash: Stable pseudonymous local-deployment identifier.
        command: Dotted-path metric-schema key.
        counters: Raw counter values keyed by metric name.
        timings_ms: Raw timing values (milliseconds) keyed by metric name.
        succeeded: Whether the measured operation succeeded.
        error_kind: Optional short closed error-kind label.
        captured_at: ISO-8601 UTC capture timestamp.
        registry: Metric-schema registry to validate against. Defaults to the
            production :data:`~core.telemetry.TELEMETRY_METRIC_REGISTRY`; tests
            may inject a substitute registry to exercise the validation
            contract without depending on production entries.

    Returns:
        The allowlisted :class:`~core.telemetry.TelemetryEventPayload`, carrying
        only registered, ``remote_allowed`` counter/timing keys.

    Raises:
        :class:`~core.telemetry.TelemetrySchemaError`: When a counter or timing
            key is not declared in the command's :class:`MetricSchema` at all.
    """
    active_registry = registry if registry is not None else TELEMETRY_METRIC_REGISTRY
    schema = active_registry.get(command)
    if schema is None:
        if counters or timings_ms:
            raise TelemetrySchemaError(
                f"telemetry command {command!r} has no registered MetricSchema; "
                "register it in TELEMETRY_METRIC_REGISTRY before emitting counters/timings",
            )
        allowed_counters: dict[str, int] = {}
        allowed_timings: dict[str, int] = {}
    else:
        allowed_counters = {}
        for key, value in (counters or {}).items():
            spec = schema.counters.get(key)
            if spec is None:
                raise TelemetrySchemaError(
                    f"telemetry counter key {key!r} is not registered in the MetricSchema for command {command!r}",
                )
            if spec.remote_allowed:
                allowed_counters[key] = value
        allowed_timings = {}
        for key, value in (timings_ms or {}).items():
            timing_spec = schema.timings_ms.get(key)
            if timing_spec is None:
                raise TelemetrySchemaError(
                    f"telemetry timing key {key!r} is not registered in the MetricSchema for command {command!r}",
                )
            if timing_spec.remote_allowed:
                allowed_timings[key] = value
    return TelemetryEventPayload(
        workspace_hash=workspace_hash,
        command=command,
        counters=allowed_counters,
        timings_ms=allowed_timings,
        succeeded=succeeded,
        error_kind=error_kind,
        captured_at=captured_at,
    )
