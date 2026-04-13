"""Domain exception hierarchy for the AEAT package.

Every subpackage should raise subclasses of AeatError to ensure
predictable error handling throughout the application.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aeat.status import SiteHealthStatus


class AeatError(Exception):
    """Base exception for all AEAT domain errors."""

    pass


class FixtureProvisioningError(AeatError):
    """Raised when Google Workspace test-fixture provisioning fails.

    Thrown by the provisioning and teardown scripts under ``scripts/``
    whenever a Drive / Sheets / Docs call cannot satisfy the catalogued
    intent (missing parent, quota exhausted, unexpected dedup result, etc).
    """

    pass


class FilingFixtureError(AeatError):
    """Raised when a synthetic filing-history fixture cannot be loaded.

    Thrown by :mod:`aeat.testing` when the fixtures directory cannot be
    resolved, a fixture file cannot be read, JSON decoding fails, or a
    payload fails strict pydantic validation (including the synthetic-
    only invariant checks on the ``synthetic`` and ``_comment`` fields).
    """

    pass


class SiteHealthError(AeatError):
    """Raised when AEAT site-health detection classifies a non-OK state.

    Carries a strict :class:`aeat.status.SiteHealthStatus` attribute
    describing the detected state (mantenimiento, WAF challenge, rate
    limit, unreachable, unknown error) together with the evidence used
    to classify it. The workflow engine catches this error in a typed
    arm that precedes the generic exception handler so a planned
    mantenimiento never collapses into ``UNHANDLED_EXCEPTION``.

    The error lives in :mod:`aeat.errors` (and not in either leaf
    subpackage) to break the circular import between
    :mod:`aeat.browser` (which raises it) and :mod:`aeat.status` /
    :mod:`aeat.workflow` (which consume it).
    """

    def __init__(self, *, status: SiteHealthStatus) -> None:
        """Construct a SiteHealthError carrying a detected status.

        Args:
            status: The strict :class:`aeat.status.SiteHealthStatus`
                instance describing the detected non-OK state.
        """
        super().__init__(status.state.value)
        self.status: SiteHealthStatus = status
