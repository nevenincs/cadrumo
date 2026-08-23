"""Remote-telemetry consent gate.

Mirrors the retired evidence cloud-read gate's exact
shape (gestor-mode absolute bar, then the deployment opt-in flag, then the
tier, then the per-invocation acknowledgement, all ANDed) so the codebase's
off-host consent gates stay uniform. Settings is imported lazily inside the
function body to avoid the circular import that would result from
``core.config`` importing :mod:`~core.telemetry` for
:class:`~core.telemetry.TelemetryTier` at module scope.

See Also:
    :func:`~core.telemetry.emit_telemetry_event`
        Applies this gate before dispatching any remote-eligible payload.
    :class:`~core.telemetry.TelemetryTier`
        Closed tier enum consulted by the gate.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ._tier import TelemetryTier

if TYPE_CHECKING:
    from ..config import Settings

__all__ = ["telemetry_emit_permitted"]


def telemetry_emit_permitted(settings: Settings, *, acknowledged: bool) -> bool:
    """Whether a remote telemetry emission is permitted for THIS invocation.

    All local telemetry stays
    unconditional and unaffected by this gate; it governs only the remote
    exception. A remote emission is permitted only when every one of the
    following holds:

    1. Gestor/professional mode is OFF (``settings.cadrumo_telemetry_gestor_mode``
       is ``False``). This is an absolute, categorical bar: a gestor
       deployment never transmits telemetry regardless of the other three
       conditions.
    2. The deployment has opted in (``settings.cadrumo_telemetry_opt_in`` is
       ``True``).
    3. The configured tier is not :attr:`~core.telemetry.TelemetryTier.OFF`.
    4. The operator acknowledged this specific invocation
       (``acknowledged`` is ``True``). The acknowledgement is never sticky;
       it must be re-affirmed at every call site, mirroring
       the retired evidence cloud-read gate.

    Args:
        settings: Resolved deployment settings carrying the telemetry
            consent posture.
        acknowledged: Whether the operator acknowledged remote telemetry for
            this specific invocation.

    Returns:
        ``True`` only when all four conditions above hold.
    """
    if settings.cadrumo_telemetry_gestor_mode:
        return False
    if not settings.cadrumo_telemetry_opt_in:
        return False
    if settings.cadrumo_telemetry_tier is TelemetryTier.OFF:
        return False
    return acknowledged
