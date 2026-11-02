"""Join a stored source observation to the filing-kind evidence its fold may use.

The relation fold and the clean-state presence check both need, for a matched
source filing, its observed filing kind and the casillas its own registry
revision declares only a complementaria fills. The kind lives on the observation
envelope and the declaration on the source revision, so this module joins the
two once for every consumer.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...domain.calculations.registry.errors import RegistrySnapshotError
from ...domain.calculations.registry.observation_fold import (
    UNKNOWN_SOURCE_FILING_KIND,
    SourceFilingKindEvidence,
    complementaria_only_casilla_ids,
)

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation
    from .observations_repository import ObservationEnvelopePayload


def source_filing_kind_evidence(
    payload: ObservationEnvelopePayload,
    *,
    operation: PinnedAuthorityOperation,
) -> SourceFilingKindEvidence:
    """Return the filing-kind evidence of one stored source observation.

    The complementaria-only declarations are read from the revision the
    observation is stamped with. A stamp the pinned generation cannot resolve
    yields the unknown evidence, so nothing is proven zero from it.
    """
    observation = payload.observation
    try:
        revision = operation.revision(observation.modelo, payload.stamped_revision_id)
    except RegistrySnapshotError:
        return UNKNOWN_SOURCE_FILING_KIND
    return SourceFilingKindEvidence(
        filing_kind=payload.observed_filing_kind,
        complementaria_only_casilla_ids=complementaria_only_casilla_ids(revision),
    )


__all__ = ["source_filing_kind_evidence"]
