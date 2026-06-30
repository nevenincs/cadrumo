"""Operator-facing Modelo 036 censo-sync service.

:class:`CensoSyncService` exposes the four-verb surface the CLI mounts
under ``aeat config profile censo {refresh, show, compare, apply}``.
Persisted profile facts are stamped onto a
:class:`~aeat.domain.user_profile.UserProfileRecord` on ``apply``. AEAT
is the binding legal source of truth for censo data; this service is the
only application path that captures censo facts into the secure store
and stamps them onto the operator's profile.

The service composes:

* :class:`aeat.application.live._censo.CensoSnapshotService` for
  bucket-scoped snapshot persistence,
* :class:`aeat.application.user_profile._repository.UserProfileLifecycleRepository`
  for reading/writing the profile,
* the existing bucket-event-history catalogue for ``CENSO_REFRESHED``
  and ``CENSO_APPLIED`` event emission.

The sede G313 live fetch is injected as a ``fact_source`` callable so
the same service body backs both the production sede adapter and
real-behavior tests without conditional code paths. This service owns
profile-fact writes and ``CENSO_REFRESHED`` / ``CENSO_APPLIED`` event
emission. It does not mutate work units, calculation revisions, drafts,
or filing records directly; consumers that need downstream stale-state
handling react to the bucket events outside this module.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from datetime import datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Final

from pydantic import BaseModel, Field

from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core.identity import ProfileId
from ...core.logging import get_logger
from ...core.time import now
from ...domain.buckets._protocols import BucketEventHistoryRepositoryProtocol
from ...domain.user_profile._values import UserProfileFact, UserProfileRecord
from ..live._censo import (
    CensoSnapshot,
    CensoSnapshotService,
)
from ._censo_errors import (
    CensoApplyConflictError,
    CensoNotAvailableError,
    CensoSyncError,
)
from ._repository import UserProfileLifecycleRepository

CENSO_SOURCE_TAG: Final = "aeat_censo_read"
"""``UserProfileFact.source`` value stamped on every censo-derived fact."""

CENSO_DERIVED_SOURCE_TAG: Final = "aeat_censo_derived"
"""``UserProfileFact.source`` for facts derived from censo plus profile evidence."""

_HOME_OFFICE_DEDUCTION_YEAR: Final[int] = 2025
_NATURAL_PERSON_TAX_ID_RE: Final = re.compile(r"^(?:\d{8}[A-Z]|[XYZ]\d{7}[A-Z])$")

_log = get_logger(__name__)


class CensoComparisonStatus(StrEnum):
    """Per-field comparison outcome between snapshot and profile.

    Attributes:
        MATCHES: Censo and profile values are identical.
        DIVERGES: Both present, values differ.
        PROFILE_ONLY: Operator has a value the censo does not publish.
        CENSO_ONLY: AEAT publishes a value the operator's profile
            does not yet record.
    """

    MATCHES = "matches"
    DIVERGES = "diverges"
    PROFILE_ONLY = "profile_only"
    CENSO_ONLY = "censo_only"


class CensoFieldComparison(BaseModel):
    """One field-by-field row of a :class:`CensoProfileComparison`."""

    model_config = _STRICT_FROZEN

    path: str = Field(min_length=1, max_length=128)
    censo_value: str | None
    profile_value: str | None
    status: CensoComparisonStatus


class CensoProfileComparison(BaseModel):
    """Result of ``censo compare``: full field-by-field diff payload."""

    model_config = _STRICT_FROZEN

    snapshot_id: str = Field(min_length=1)
    profile_id: ProfileId
    captured_at: datetime
    rows: tuple[CensoFieldComparison, ...] = Field(default_factory=tuple)

    @property
    def diverging(self) -> tuple[CensoFieldComparison, ...]:
        return tuple(row for row in self.rows if row.status is CensoComparisonStatus.DIVERGES)

    @property
    def censo_only(self) -> tuple[CensoFieldComparison, ...]:
        return tuple(row for row in self.rows if row.status is CensoComparisonStatus.CENSO_ONLY)

    @property
    def profile_only(self) -> tuple[CensoFieldComparison, ...]:
        return tuple(row for row in self.rows if row.status is CensoComparisonStatus.PROFILE_ONLY)


class CensoApplyResult(BaseModel):
    """Result of ``censo apply``: which facts landed on the profile."""

    model_config = _STRICT_FROZEN

    snapshot_id: str = Field(min_length=1)
    profile_id: ProfileId
    written_paths: tuple[str, ...] = Field(default_factory=tuple)
    unchanged_paths: tuple[str, ...] = Field(default_factory=tuple)
    derived_paths: tuple[str, ...] = Field(default_factory=tuple)
    seeded_home_office_categories: tuple[str, ...] = Field(default_factory=tuple)


CensoFactSource = Callable[[], Mapping[str, str]]
"""Callable returning the AEAT-side censo facts for one refresh.

In production this is wired to the sede G313 adapter; in tests it is
a constant callable returning a fixture dictionary. The service stays
sede-agnostic so the same body covers both call paths.
"""


class CensoSyncService:
    """Four-verb operator-facing service over censo snapshots.

    ``refresh`` captures a new snapshot from AEAT, ``show`` returns
    the active or named snapshot, ``compare`` diffs the snapshot
    against the operator's current profile, and ``apply`` writes the
    snapshot facts onto the profile under the ``aeat_censo_read``
    provenance tag.
    """

    def __init__(
        self,
        *,
        bucket_id: str,
        snapshots: CensoSnapshotService | None = None,
        profiles: UserProfileLifecycleRepository | None = None,
        events: BucketEventHistoryRepositoryProtocol | None = None,
    ) -> None:
        self._bucket_id = bucket_id.strip()
        if not self._bucket_id:
            raise CensoSyncError(translated_message="errors.censo.bucket_id_blank")
        self._snapshots = snapshots or CensoSnapshotService(bucket_id=self._bucket_id)
        self._profiles = profiles or UserProfileLifecycleRepository(bucket_id=self._bucket_id)
        self._events = events

    @property
    def bucket_id(self) -> str:
        return self._bucket_id

    def refresh_censo(
        self,
        *,
        profile_id: str,
        source_url: str,
        fact_source: CensoFactSource,
    ) -> CensoSnapshot:
        """Fetch fresh censo facts, capture them as the new ACTIVE snapshot, and return the :class:`CensoSnapshot`.

        Raises :exc:`CensoNotAvailableError` when ``fact_source``
        returns an empty mapping — AEAT publishes no censo for the
        operator's NIF, so the caller should re-run after enrolment
        (or confirm the certificate is registered against the NIF).
        """
        facts = dict(fact_source())
        if not facts:
            raise CensoNotAvailableError(
                translated_message="errors.censo.sede_no_censo",
                context={"profile_id": profile_id},
            )
        snapshot = self._snapshots.capture(
            profile_id=profile_id,
            captured_at=now(),
            source_url=source_url,
            censo_facts=facts,
        )
        self._emit_censo_event(
            event_type_value="profile.censo.refreshed",
            profile_id=profile_id,
            snapshot_id=snapshot.snapshot_id,
        )
        return snapshot

    async def refresh_censo_from_sede(
        self,
        *,
        profile_id: str,
    ) -> CensoSnapshot:
        """Drive the live G313 Playwright fetch and persist the snapshot.

        Acquires (or refreshes) an authenticated :class:`AeatSession`,
        navigates to the documented G313 launcher, parses the response
        into a :class:`CensoFactSet`, projects it into the dotted
        snapshot mapping, and captures via :meth:`refresh_censo`.

        Args:
            profile_id: The profile id the captured censo snapshot is
                scoped to.

        Returns:
            The persisted :class:`CensoSnapshot` for the profile.

        Raises:
            CensoNotAvailableError: when AEAT publishes no censo for
                the operator's NIF (empty CensoFactSet).
        """
        from ...adapters.outbound.aeat.sede._censo_live import (
            G313_LAUNCHER_URL,
            censo_fact_set_to_mapping,
            fetch_g313_censo,
        )
        from ...core.access_gate import AeatAccessGate
        from ...core.config import load_settings
        from ..auth import ensure_authenticated_aeat_session

        settings = load_settings()
        AeatAccessGate(settings).require_live_read()
        result = await ensure_authenticated_aeat_session(
            settings,
            operation="live-censo-read",
        )
        fact_set = await fetch_g313_censo(result.session, settings=settings)
        facts = censo_fact_set_to_mapping(fact_set)
        if not facts:
            raise CensoNotAvailableError(
                translated_message="errors.censo.sede_g313_no_censo",
                context={"profile_id": profile_id},
            )
        snapshot = self._snapshots.capture(
            profile_id=profile_id,
            captured_at=now(),
            source_url=G313_LAUNCHER_URL,
            censo_facts=facts,
        )
        self._emit_censo_event(
            event_type_value="profile.censo.refreshed",
            profile_id=profile_id,
            snapshot_id=snapshot.snapshot_id,
        )
        return snapshot

    def show_censo(
        self,
        *,
        profile_id: str,
        snapshot_id: str | None = None,
    ) -> CensoSnapshot:
        """Return one :class:`CensoSnapshot` — the latest ACTIVE by default."""
        if snapshot_id is not None:
            snapshot = self._snapshots.resolve_snapshot(snapshot_id)
            if snapshot.profile_id != profile_id.strip():
                raise CensoNotAvailableError(
                    translated_message="errors.censo.snapshot_profile_mismatch",
                    context={
                        "profile_id": profile_id,
                        "snapshot_profile_id": snapshot.profile_id,
                        "snapshot_id": snapshot.snapshot_id,
                    },
                )
            return snapshot
        active = self._snapshots.latest_active(profile_id=profile_id)
        if active is None:
            raise CensoNotAvailableError(
                translated_message="errors.censo.no_snapshot_captured",
                context={"profile_id": profile_id},
            )
        return active

    def compare_censo_with_profile(
        self,
        *,
        profile_id: str,
        snapshot_id: str | None = None,
    ) -> CensoProfileComparison:
        """Compare the active (or named) snapshot to the current profile.

        Returns a :class:`CensoProfileComparison` with one row per
        censo-tracked path, classified into matches / diverges /
        profile_only / censo_only.
        """
        snapshot = self.show_censo(profile_id=profile_id, snapshot_id=snapshot_id)
        profile = self._load_profile_or_empty(profile_id)
        profile_facts = _profile_facts_by_path(profile)
        rows = _compare(snapshot.censo_facts, profile_facts)
        return CensoProfileComparison(
            snapshot_id=snapshot.snapshot_id,
            profile_id=profile_id.strip(),
            captured_at=snapshot.captured_at,
            rows=rows,
        )

    def apply_censo_to_profile(
        self,
        *,
        profile_id: str,
        snapshot_id: str | None = None,
    ) -> CensoApplyResult:
        """Stamp the snapshot facts onto the profile, replacing prior ``aeat_censo_read`` facts.

        Every raw censo fact lands as a
        :class:`~aeat.domain.user_profile.UserProfileFact` with
        ``source = "aeat_censo_read"``. Facts defensibly derived from
        the censo/profile pair land with
        ``source = "aeat_censo_derived"``. Pre-existing facts from
        either censo source are replaced; facts from other sources
        (``manual_cli``, wizard) are preserved untouched so
        operator-entered values stay addressable for the compare verb.

        Emits ``CENSO_APPLIED`` on the bucket-event-history catalogue
        itself so downstream maintenance can react without the CLI
        owning event-enrolment policy.

        Raises :exc:`CensoApplyConflictError` when the profile is
        absent — there is nothing to stamp facts onto.

        Returns:
            :class:`CensoApplyResult`: The apply result details.
        """
        snapshot = self.show_censo(profile_id=profile_id, snapshot_id=snapshot_id)
        if not self._profiles.exists(profile_id):
            raise CensoApplyConflictError(
                translated_message="errors.censo.profile_not_found",
                context={"profile_id": profile_id},
            )
        profile = self._profiles.load(profile_id)
        before = _profile_facts_by_path(profile)
        retained = tuple(
            fact for fact in profile.facts if fact.source not in {CENSO_SOURCE_TAG, CENSO_DERIVED_SOURCE_TAG}
        )
        retained_paths = {fact.path for fact in retained}
        new_censo_facts = tuple(
            UserProfileFact(path=path, value=value, source=CENSO_SOURCE_TAG)
            for path, value in sorted(snapshot.censo_facts.items())
        )
        derived_facts = tuple(
            fact
            for fact in _derive_profile_facts_from_censo(snapshot.censo_facts, before)
            if fact.path not in retained_paths
        )
        updated = profile.model_copy(
            update={
                "facts": retained + new_censo_facts + derived_facts,
                "updated_at": now(),
            },
        )
        self._profiles.save(updated)
        seeded = self._seed_home_office_usage_ratios_from_snapshot(snapshot)
        written: list[str] = []
        unchanged: list[str] = []
        for path, value in sorted(snapshot.censo_facts.items()):
            if before.get(path) == value:
                unchanged.append(path)
            else:
                written.append(path)
        result = CensoApplyResult(
            snapshot_id=snapshot.snapshot_id,
            profile_id=profile_id.strip(),
            written_paths=tuple(written),
            unchanged_paths=tuple(unchanged),
            derived_paths=tuple(sorted(fact.path for fact in derived_facts)),
            seeded_home_office_categories=seeded,
        )
        self._emit_censo_event(
            event_type_value="profile.censo.applied",
            profile_id=profile_id,
            snapshot_id=result.snapshot_id,
        )
        return result

    def _seed_home_office_usage_ratios_from_snapshot(
        self,
        snapshot: CensoSnapshot,
    ) -> tuple[str, ...]:
        """Compute HOME_OFFICE per-category ratios from the snapshot's vivienda_office facts and persist them.

        Returns the canonical category-id list that landed.

        Idempotent: if office_m2 / total_m2 are absent or the derived
        ratio matches what is already persisted, nothing is written and
        the empty tuple is returned. Operator-set overrides on
        non-HOME_OFFICE categories are preserved.
        """
        from ...domain.usage_ratios import (
            UsageRatioProfile,
            derive_home_office_ratios_from_censo,
            load_usage_ratios,
            save_usage_ratios,
        )

        raw_ratio = _raw_afectacion_ratio(snapshot.censo_facts)
        if raw_ratio is None:
            return ()
        derived = derive_home_office_ratios_from_censo(raw_ratio, year=_HOME_OFFICE_DEDUCTION_YEAR)
        current = load_usage_ratios(bucket_id=self._bucket_id)
        seeded: list[str] = []
        merged_ratios = dict(current.ratios)
        for category, value in derived.ratios.items():
            if merged_ratios.get(category) != value:
                merged_ratios[category] = value
                seeded.append(category.value)
        if not seeded:
            return ()
        save_usage_ratios(UsageRatioProfile(ratios=merged_ratios), bucket_id=self._bucket_id)
        return tuple(sorted(seeded))

    def _load_profile_or_empty(self, profile_id: str) -> UserProfileRecord | None:
        if not self._profiles.exists(profile_id):
            return None
        return self._profiles.load(profile_id)

    def bound_raw_afectacion_ratio(self, *, profile_id: str) -> Decimal | None:
        """Return ``office_m2 / total_m2`` from the active censo snapshot.

        Used by the ledger ratios CLI and the manual-transaction
        classify path to apply the legally-effective
        :func:`aeat.application.ledger._ratios.censo_override_warning`
        and :func:`aeat.application.ledger._ratios.censo_business_pct_for`
        helpers without each consumer re-implementing the snapshot
        lookup. Returns ``None`` when no ACTIVE snapshot exists OR when
        either ``vivienda_office.total_m2`` / ``vivienda_office.office_m2``
        is absent / non-decimal / zero.
        """
        snapshot = self._snapshots.latest_active(profile_id=profile_id)
        if snapshot is None:
            return None
        return _raw_afectacion_ratio(snapshot.censo_facts)

    def _emit_censo_event(self, *, event_type_value: str, profile_id: str, snapshot_id: str) -> None:
        if self._events is None:
            return
        from ...domain.buckets import (
            BucketEvent,
            BucketEventObjectType,
            BucketEventType,
            append_bucket_event,
            derive_bucket_event_id,
        )

        event_type = BucketEventType(event_type_value)
        occurred_at = now()
        payload = {"profile_id": profile_id, "snapshot_id": snapshot_id}
        event_id = derive_bucket_event_id(
            bucket_id=self._bucket_id,
            event_type=event_type,
            occurred_at=occurred_at,
            actor="operator",
            object_type=BucketEventObjectType.PROFILE,
            object_id=profile_id,
            payload=payload,
        )
        self._events.save(
            append_bucket_event(
                self._events.load(),
                BucketEvent(
                    event_id=event_id,
                    bucket_id=self._bucket_id,
                    event_type=event_type,
                    occurred_at=occurred_at,
                    actor="operator",
                    object_type=BucketEventObjectType.PROFILE,
                    object_id=profile_id,
                    payload=payload,
                    payload_version=1,
                ),
            ),
        )


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


def _profile_facts_by_path(profile: UserProfileRecord | None) -> dict[str, str]:
    """Flatten a profile's facts into a path → string-value mapping.

    Censo comparison is string-based because the snapshot side is
    string-only (see :class:`aeat.application.live._censo`); the
    profile's typed values are coerced via ``str()`` for the diff.
    """
    if profile is None:
        return {}
    return {fact.path: _coerce_to_str(fact.value) for fact in profile.facts}


def _derive_profile_facts_from_censo(
    censo_facts: Mapping[str, str],
    profile_facts: Mapping[str, str],
) -> tuple[UserProfileFact, ...]:
    """Return taxpayer-model facts proven by censo facts plus profile identity."""
    derived: list[UserProfileFact] = []
    tax_id = (profile_facts.get("identity.tax_id") or profile_facts.get("tax.id") or "").strip().upper()
    is_natural_person = _NATURAL_PERSON_TAX_ID_RE.match(tax_id) is not None
    if is_natural_person:
        derived.append(
            UserProfileFact(
                path="taxpayer_type.entity_type",
                value="natural_person",
                source=CENSO_DERIVED_SOURCE_TAG,
            ),
        )
    iae_epigraph = (censo_facts.get("activities.iae_epigraph") or "").strip()
    if is_natural_person and iae_epigraph:
        derived.append(
            UserProfileFact(
                path="taxpayer_type.irpf_income_categories",
                value="actividad_economica",
                source=CENSO_DERIVED_SOURCE_TAG,
            ),
        )
    return tuple(derived)


def _coerce_to_str(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _compare(
    censo_facts: Mapping[str, str],
    profile_facts: Mapping[str, str],
) -> tuple[CensoFieldComparison, ...]:
    paths = sorted(set(censo_facts) | set(profile_facts))
    rows: list[CensoFieldComparison] = []
    for path in paths:
        censo_value = censo_facts.get(path)
        profile_value = profile_facts.get(path)
        if censo_value is not None and profile_value is not None:
            status = CensoComparisonStatus.MATCHES if censo_value == profile_value else CensoComparisonStatus.DIVERGES
        elif censo_value is not None:
            status = CensoComparisonStatus.CENSO_ONLY
        else:
            status = CensoComparisonStatus.PROFILE_ONLY
        rows.append(
            CensoFieldComparison(
                path=path,
                censo_value=censo_value,
                profile_value=profile_value,
                status=status,
            ),
        )
    return tuple(rows)


__all__ = [
    "CENSO_DERIVED_SOURCE_TAG",
    "CENSO_SOURCE_TAG",
    "CensoApplyResult",
    "CensoComparisonStatus",
    "CensoFactSource",
    "CensoFieldComparison",
    "CensoProfileComparison",
    "CensoSyncService",
]
