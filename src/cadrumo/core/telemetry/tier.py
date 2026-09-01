"""Closed remote-telemetry tier enum.

Declared standalone (no dependency on :mod:`~core.config`) so
:class:`~core.config.Settings` can import it without a circular import, per
``aeat-architecture-boundaries``'s closed-value-set discipline (every closed
axis is a :class:`~enum.StrEnum` declared in ``core/``).

See Also:
    :class:`~core.telemetry.TelemetryTier`
        Public facade export of the closed remote-telemetry tier enum.
    :func:`~core.telemetry.telemetry_emit_permitted`
        Consent gate that interprets the tier for each attempted emission.
    :class:`~core.config.Settings`
        Deployment configuration carrying the selected telemetry tier.
"""

from __future__ import annotations

from enum import StrEnum

__all__ = ["TelemetryTier"]


class TelemetryTier(StrEnum):
    """The closed set of remote-telemetry emission tiers.

    Members:
        OFF: No remote emission under any circumstances, regardless of the
            deployment opt-in flag or any per-invocation acknowledgement. This
            is the default and only tier a fresh deployment starts at.
        CRASH_ONLY: Only outcome/error counters (``succeeded``, ``error_kind``)
            are remote-eligible; timing data is never transmitted at this
            tier even when a metric's schema entry marks a timing
            ``remote_allowed``.
        FULL: Counters and timing percentiles are both remote-eligible,
            subject to each individual metric key's own
            :attr:`~core.telemetry.CounterSpec.remote_allowed` /
            :attr:`~core.telemetry.TimingSpec.remote_allowed` declaration.
    """

    OFF = "off"
    CRASH_ONLY = "crash_only"
    FULL = "full"
