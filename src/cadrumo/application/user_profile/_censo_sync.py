"""Censo-derived profile signals for downstream consumers.

The live Modelo 036 censo scrape (``config profile censo pull`` and the
``compare`` / ``apply`` family) was retired: AEAT exposes no read-only
"Mis Datos Censales" projection, so censal facts are operator-supplied
through ``config profile edit`` at the operator-declared (non-official)
tier. What survives here is the read-only projection the ledger
proportional-deduction path still consumes: the home-office afectación
ratio derived from the operator-declared ``vivienda_office`` m² facts on
the encrypted profile, plus the two provenance tags the overview
calendar reads to decide whether censo enrolment is AEAT-verified.

``CENSO_SOURCE_TAG`` / ``CENSO_DERIVED_SOURCE_TAG`` remain the markers of
an AEAT-verified censo fact. With the live scrape retired nothing stamps
them, so the overview calendar's verified-key set stays empty and every
censo-derived obligation keeps its ``censo.enrolment_unverified``
posture — the honest default.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, Final

from ...core.logging import get_logger
from ._censo_errors import CensoSyncError

if TYPE_CHECKING:
    from ._repository import UserProfileLifecycleRepository

CENSO_SOURCE_TAG: Final = "aeat_censo_read"
"""``UserProfileFact.source`` value marking an AEAT-verified censo fact."""

CENSO_DERIVED_SOURCE_TAG: Final = "aeat_censo_derived"
"""``UserProfileFact.source`` for facts derived from an AEAT-verified censo."""

_log = get_logger(__name__)


class CensoSyncService:
    """Read-only censo-derived signals for the active profile bucket.

    The service no longer captures, compares, or applies censo snapshots
    (the live scrape was retired); it exposes the single surviving
    read: the home-office afectación ratio the ledger ratios and
    preflight paths consume via :meth:`bound_raw_afectacion_ratio`,
    derived from the operator-declared ``vivienda_office`` m² facts the
    operator maintains through ``config profile edit``.
    """

    def __init__(
        self,
        *,
        bucket_id: str,
        profiles: UserProfileLifecycleRepository | None = None,
    ) -> None:
        self._bucket_id = bucket_id.strip()
        if not self._bucket_id:
            raise CensoSyncError(translated_message="errors.censo.bucket_id_blank")
        self._profiles = profiles

    @property
    def bucket_id(self) -> str:
        return self._bucket_id

    def bound_raw_afectacion_ratio(self, *, profile_id: str) -> Decimal | None:
        """Return ``office_m2 / total_m2`` from the operator-declared profile facts.

        Used by the ledger ratios CLI and the manual-transaction
        classify path to apply the legally-effective
        :func:`cadrumo.application.ledger._ratios.censo_override_warning`
        and :func:`cadrumo.application.ledger._ratios.censo_business_pct_for`
        helpers without each consumer re-implementing the profile-fact
        lookup. Reads the encrypted profile record's canonical path-value
        projection — the same operator-declared facts ``config profile
        edit`` writes and the deadline engine hydrates — so updating the
        ``vivienda_office`` m² through the CLI drives this ratio directly.
        Returns ``None`` when the profile has no persisted record OR when
        either ``vivienda_office.total_m2`` / ``vivienda_office.office_m2``
        is absent / non-decimal / zero.
        """
        from ...domain.user_profile import ProfileNotFoundError
        from ._projections import record_to_path_values
        from ._repository import UserProfileLifecycleRepository

        repository = self._profiles or UserProfileLifecycleRepository(bucket_id=self._bucket_id)
        try:
            record = repository.load(profile_id)
        except ProfileNotFoundError:
            return None
        return _raw_afectacion_ratio(record_to_path_values(record))


def _raw_afectacion_ratio(censo_facts: Mapping[str, str]) -> Decimal | None:
    total_raw = censo_facts.get("vivienda_office.total_m2")
    office_raw = censo_facts.get("vivienda_office.office_m2")
    if total_raw is None or office_raw is None:
        return None
    try:
        total = Decimal(total_raw)
        office = Decimal(office_raw)
    except (InvalidOperation, ValueError):
        _log.debug("censo raw afectacion ratio ignored: non-decimal censo surface", exc_info=True)
        return None
    if total <= Decimal("0") or office < Decimal("0") or office > total:
        _log.debug("censo raw afectacion ratio ignored: invalid censo ratio bounds")
        return None
    return office / total


__all__ = [
    "CENSO_DERIVED_SOURCE_TAG",
    "CENSO_SOURCE_TAG",
    "CensoSyncService",
]
