"""Canonical telemetry error types.

Declared alongside the schema/consent/emit modules per the project's
error-taxonomy convention: every :class:`~core.errors.CadrumoError`
subclass binds to a registered
:class:`~core.errors.ErrorCode` row (``core/errors/registry/_core.py``).

See Also:
    :class:`~core.telemetry.TelemetrySchemaError`
        Public telemetry schema failure exported by the package facade.
    :data:`~core.telemetry.TELEMETRY_METRIC_REGISTRY`
        Closed metric allowlist whose integrity violations raise this error.
    :func:`~core.telemetry.build_telemetry_payload`
        Payload builder that enforces the registry before emission.
"""

from __future__ import annotations

from ..errors import CoreError

__all__ = ["TelemetrySchemaError"]


class TelemetrySchemaError(CoreError):
    """Raised when a telemetry payload references an unregistered metric key.

    This is a development/authoring-time integrity failure, not an operator-
    facing refusal: the metric-key registry
    (:data:`~core.telemetry.TELEMETRY_METRIC_REGISTRY`) is the closed allowlist
    a telemetry producer must enroll in before it can emit a counter or timing.
    A key that is not registered for its command means a producer was added
    without registering its schema entry first — the exact gap
    ``aeat-calculation-aggregation``'s closed-registry discipline exists to
    catch elsewhere in the codebase.
    """
