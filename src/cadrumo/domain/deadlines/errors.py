"""Canonical domain errors for the :mod:`cadrumo.domain.deadlines` subpackage.

Every error inherits from :class:`cadrumo.core.errors.CadrumoError` so callers have
a single root they can catch when integrating with the deadline engine.
"""

from __future__ import annotations

from ...core.errors import CadrumoError


class DeadlineError(CadrumoError):
    """Base class for every error raised by :mod:`cadrumo.domain.deadlines`."""


class ProfileError(DeadlineError):
    """Raised when an :class:`cadrumo.domain.deadlines.TaxpayerProfile` cannot be loaded or validated."""


class ScheduleComputationError(DeadlineError):
    """Raised when the engine cannot produce a valid schedule.

    Often caused by a mismatch between the requested year and the
    registry's coverage, or by profile facts that trigger an
    unknown modelo.

    Two structurally distinct failure classes share this type: the
    benign "no registry deadline windows registered" data gap — raised
    as the :class:`NoDeadlineWindowsError` subclass so callers can
    degrade gracefully around it — and genuine registry-integrity
    faults (validation failure, profile-condition evaluation failure),
    raised as the bare :class:`ScheduleComputationError`. A caller that
    wants the benign degradation must catch the *narrow*
    :class:`NoDeadlineWindowsError`, never the broad base, so a genuine
    fault propagates instead of being masked.
    """


class NoDeadlineWindowsError(ScheduleComputationError):
    """Raised when the registry has no deadline windows for a year/modelo.

    This is the *benign* schedule-computation failure: a registry-track
    data gap (the Modelo 100 / 303 / 347 / 202 windows not yet
    registered), not a corrupt or invalid
    registry. The overview calendar / agenda / explain surfaces catch
    this narrow subtype to degrade gracefully — a year or modelo with
    no window data contributes zero entries while the surface still
    answers for everything that does have data.

    It is deliberately distinct from the bare
    :class:`ScheduleComputationError`, which the engine raises for a
    genuine registry-integrity fault (validation failure,
    profile-condition evaluation failure). Catching only this subtype
    lets those genuine faults propagate and surface instead of being
    silently swallowed.
    """


class DeadlineValidationError(DeadlineError, ValueError):
    """Raised when deadline records violate state or shape invariants.

    Inherits from ValueError to maintain compatibility with Pydantic
    validators.
    """
