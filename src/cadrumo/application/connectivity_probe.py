"""The connectivity probe's port and the report every frontend receives.

The probe opens a browser on the tax agency's public landing page and
classifies the answer. It signs in to nothing and sends no taxpayer data. The
browser belongs to an outbound adapter, so the application reaches it through
:class:`ConnectivityProbePort`, bound where a process is composed.
"""

from __future__ import annotations

from typing import Annotated, Final, Literal, Protocol

from pydantic import AwareDatetime, BaseModel, Field, StringConstraints

from ..core.errors.hierarchy import SiteHealthEvidenceLike, SiteHealthState
from ..core.models import STRICT_FROZEN_CONFIG

CONNECTIVITY_TARGET: Final = "aeat_sede"
"""The one site the probe observes."""

type _Marker = Annotated[str, StringConstraints(min_length=1, max_length=128)]


class ObservedSiteEvidence(SiteHealthEvidenceLike, Protocol):
    """The evidence an observation carries, with the bounded page fragment it classified."""

    @property
    def html_fragment(self) -> str:
        """Redacted, bounded text of the answer that was classified."""
        ...


class ObservedSiteHealth(Protocol):
    """One classified answer from the probed site, as the adapter that browsed it reports it."""

    @property
    def state(self) -> SiteHealthState:
        """How the answer was classified."""
        ...

    @property
    def evidence(self) -> ObservedSiteEvidence:
        """What the classification was read from."""
        ...

    @property
    def observed_at(self) -> AwareDatetime:
        """When the answer was classified."""
        ...

    @property
    def retry_after_seconds(self) -> int | None:
        """How long the site asked a caller to wait, when it said."""
        ...


class ConnectivityProbePort(Protocol):
    """Browse to the probed site once and classify what it answered."""

    def __call__(self) -> ObservedSiteHealth:
        """Return the classified answer; a site that is down is an answer, not a failure."""
        ...


class ConnectivityEvidence(BaseModel):
    """What one connectivity classification was read from."""

    model_config = STRICT_FROZEN_CONFIG

    url: Annotated[str, StringConstraints(min_length=1, max_length=2048)]
    http_status: Annotated[int, Field(ge=100, le=599)]
    html_fragment: Annotated[str, StringConstraints(max_length=4096)]
    detected_markers: Annotated[tuple[_Marker, ...], Field(max_length=256)]


class ConnectivityStatus(BaseModel):
    """The classified answer of the probed site."""

    model_config = STRICT_FROZEN_CONFIG

    state: SiteHealthState
    evidence: ConnectivityEvidence
    observed_at: AwareDatetime
    retry_after_seconds: Annotated[int, Field(ge=1)] | None = None


class ConnectivityReport(BaseModel):
    """One probe of one named site."""

    model_config = STRICT_FROZEN_CONFIG

    target: Literal["aeat_sede"]
    status: ConnectivityStatus


def probe_connectivity(probe: ConnectivityProbePort) -> ConnectivityReport:
    """Run ``probe`` once and report what the site answered."""
    observed = probe()
    return ConnectivityReport(
        target=CONNECTIVITY_TARGET,
        status=ConnectivityStatus(
            state=observed.state,
            evidence=ConnectivityEvidence(
                url=str(observed.evidence.url),
                http_status=observed.evidence.http_status,
                html_fragment=observed.evidence.html_fragment,
                detected_markers=tuple(observed.evidence.detected_markers),
            ),
            observed_at=observed.observed_at,
            retry_after_seconds=observed.retry_after_seconds,
        ),
    )


__all__ = [
    "CONNECTIVITY_TARGET",
    "ConnectivityEvidence",
    "ConnectivityProbePort",
    "ConnectivityReport",
    "ConnectivityStatus",
    "ObservedSiteEvidence",
    "ObservedSiteHealth",
    "probe_connectivity",
]
