"""Operator-facing 036 census-sync service.

`CensoSyncService` exposes the four-verb surface the CLI mounts under
``aeat config profile census {refresh, show, compare, apply}``. AEAT is
the binding legal source of truth per the 2026-05-16 amendment to the
modelo-036-037-foundation ADR; this service is the only path that
captures census facts into the secure store and stamps them onto the
operator's profile.

The service composes:

* :class:`aeat.application.live._censo.CensoSnapshotService` for
  bucket-scoped snapshot persistence,
* :class:`aeat.application.user_profile._repository.UserProfileLifecycleRepository`
  for reading/writing the profile,
* the existing bucket-event-history catalogue for ``CENSUS_REFRESHED``
  and ``CENSUS_APPLIED`` event emission.

The sede G313 live fetch is injected as a ``fact_source`` callable so
the same service body backs both the production sede adapter and
test scaffolding without conditional code paths. The dependent-
stamping walker (mark CalculationRevision / WorkUnit / FilingDraft /
ModeloRecord as CENSUS_STALE on apply) is the P05 follow-on; this
service emits ``CENSUS_APPLIED`` so the walker can hook in via that
event without further coupling.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Final

from pydantic import BaseModel, ConfigDict, Field

from ...domain.user_profile._values import UserProfileFact, UserProfileRecord
from ..live._censo import (
    CensoSnapshot,
    CensoSnapshotService,
)
from ..user_profile._repository import UserProfileLifecycleRepository
from ._censo_errors import (
    CensoApplyConflictError,
    CensoNotAvailableError,
)


_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")

CENSUS_SOURCE_TAG: Final = "aeat_census_read"
"""``UserProfileFact.source`` value stamped on every census-derived fact."""


class CensoComparisonStatus(StrEnum):
    """Per-field comparison outcome between snapshot and profile.

    Attributes:
        MATCHES: Census and profile values are identical.
        DIVERGES: Both present, values differ.
        PROFILE_ONLY: Operator has a value the census does not publish.
        CENSUS_ONLY: AEAT publishes a value the operator's profile
            does not yet record.
    """

    MATCHES = "matches"
    DIVERGES = "diverges"
    PROFILE_ONLY = "profile_only"
    CENSUS_ONLY = "census_only"


class CensoFieldComparison(BaseModel):
    """One field-by-field row of a :class:`CensoProfileComparison`."""

    model_config = _STRICT_FROZEN

    path: str = Field(min_length=1, max_length=128)
    census_value: str | None
    profile_value: str | None
    status: CensoComparisonStatus


class CensoProfileComparison(BaseModel):
    """Result of ``census compare``: full field-by-field diff payload."""

    model_config = _STRICT_FROZEN

    snapshot_id: str = Field(min_length=1)
    profile_id: str = Field(min_length=1)
    captured_at: datetime
    rows: tuple[CensoFieldComparison, ...] = Field(default_factory=tuple)

    @property
    def diverging(self) -> tuple[CensoFieldComparison, ...]:
        return tuple(row for row in self.rows if row.status is CensoComparisonStatus.DIVERGES)

    @property
    def census_only(self) -> tuple[CensoFieldComparison, ...]:
        return tuple(row for row in self.rows if row.status is CensoComparisonStatus.CENSUS_ONLY)

    @property
    def profile_only(self) -> tuple[CensoFieldComparison, ...]:
        return tuple(row for row in self.rows if row.status is CensoComparisonStatus.PROFILE_ONLY)


class CensoApplyResult(BaseModel):
    """Result of ``census apply``: which facts landed on the profile."""

    model_config = _STRICT_FROZEN

    snapshot_id: str = Field(min_length=1)
    profile_id: str = Field(min_length=1)
    written_paths: tuple[str, ...] = Field(default_factory=tuple)
    unchanged_paths: tuple[str, ...] = Field(default_factory=tuple)
    seeded_home_office_categories: tuple[str, ...] = Field(default_factory=tuple)


CensoFactSource = Callable[[], Mapping[str, str]]
"""Callable returning the AEAT-side census facts for one refresh.

In production this is wired to the sede G313 adapter; in tests it is
a constant callable returning a fixture dictionary. The service stays
sede-agnostic so the same body covers both call paths.
"""


class CensoSyncService:
    """Four-verb operator-facing service over census snapshots.

    ``refresh`` captures a new snapshot from AEAT, ``show`` returns
    the active or named snapshot, ``compare`` diffs the snapshot
    against the operator's current profile, and ``apply`` writes the
    snapshot facts onto the profile under the ``aeat_census_read``
    provenance tag.
    """

    def __init__(
        self,
        *,
        bucket_id: str,
        snapshots: CensoSnapshotService | None = None,
        profiles: UserProfileLifecycleRepository | None = None,
    ) -> None:
        self._bucket_id = bucket_id.strip()
        if not self._bucket_id:
            raise ValueError("bucket_id must not be blank")
        self._snapshots = snapshots or CensoSnapshotService(bucket_id=self._bucket_id)
        self._profiles = profiles or UserProfileLifecycleRepository(bucket_id=self._bucket_id)

    @property
    def bucket_id(self) -> str:
        return self._bucket_id

    def refresh_census(
        self,
        *,
        profile_id: str,
        source_url: str,
        fact_source: CensoFactSource,
    ) -> CensoSnapshot:
        """Fetch fresh census facts and capture them as the new ACTIVE snapshot.

        Raises :exc:`CensoNotAvailableError` when ``fact_source``
        returns an empty mapping — AEAT publishes no census for the
        operator's NIF, so the caller should re-run after enrolment
        (or confirm the certificate is registered against the NIF).
        """

        facts = dict(fact_source())
        if not facts:
            raise CensoNotAvailableError(
                f"sede returned no parseable census for profile {profile_id!r}",
            )
        return self._snapshots.capture(
            profile_id=profile_id,
            captured_at=datetime.now(UTC),
            source_url=source_url,
            census_facts=facts,
        )

    async def refresh_census_from_sede(
        self,
        *,
        profile_id: str,
    ) -> CensoSnapshot:
        """Drive the live G313 Playwright fetch and persist the snapshot.

        Acquires (or refreshes) an authenticated :class:`AeatSession`,
        navigates to the documented G313 launcher, parses the response
        into a :class:`CensoFactSet`, projects it into the dotted
        snapshot mapping, and captures via :meth:`refresh_census`.

        Raises:
            :exc:`CensoNotAvailableError`: when AEAT publishes no
                census for the operator's NIF (empty CensoFactSet).
            Any auth-layer or sede-layer error: propagated for the CLI
                handler to surface.
        """

        from ...adapters.outbound.aeat.sede._censo_live import (
            G313_LAUNCHER_URL,
            census_fact_set_to_mapping,
            fetch_g313_census,
        )
        from ...core.access_gate import AeatAccessGate
        from ...core.config import load_settings
        from ..auth import ensure_authenticated_aeat_session

        settings = load_settings()
        AeatAccessGate(settings).require_live_read()
        result = await ensure_authenticated_aeat_session(
            settings,
            operation="live-census-read",
        )
        fact_set = await fetch_g313_census(result.session, settings=settings)
        facts = census_fact_set_to_mapping(fact_set)
        if not facts:
            raise CensoNotAvailableError(
                f"sede G313 returned no parseable census for profile {profile_id!r}; "
                "confirm your certificate / cl@ve is registered against this NIF",
            )
        return self._snapshots.capture(
            profile_id=profile_id,
            captured_at=datetime.now(UTC),
            source_url=G313_LAUNCHER_URL,
            census_facts=facts,
        )

    def show_census(
        self,
        *,
        profile_id: str,
        snapshot_id: str | None = None,
    ) -> CensoSnapshot:
        """Return one snapshot — the latest ACTIVE by default."""

        if snapshot_id is not None:
            return self._snapshots.resolve_snapshot(snapshot_id)
        active = self._snapshots.latest_active(profile_id=profile_id)
        if active is None:
            raise CensoNotAvailableError(
                f"no census snapshot captured for profile {profile_id!r}",
            )
        return active

    def compare_census_with_profile(
        self,
        *,
        profile_id: str,
        snapshot_id: str | None = None,
    ) -> CensoProfileComparison:
        """Compare the active (or named) snapshot to the current profile.

        Returns a :class:`CensoProfileComparison` with one row per
        census-tracked path, classified into matches / diverges /
        profile_only / census_only.
        """

        snapshot = self.show_census(profile_id=profile_id, snapshot_id=snapshot_id)
        profile = self._load_profile_or_empty(profile_id)
        profile_facts = _profile_facts_by_path(profile)
        rows = _compare(snapshot.census_facts, profile_facts)
        return CensoProfileComparison(
            snapshot_id=snapshot.snapshot_id,
            profile_id=profile_id.strip(),
            captured_at=snapshot.captured_at,
            rows=rows,
        )

    def apply_census_to_profile(
        self,
        *,
        profile_id: str,
        snapshot_id: str | None = None,
    ) -> CensoApplyResult:
        """Stamp the snapshot facts onto the profile, replacing prior ``aeat_census_read`` facts.

        Every census fact lands as a :class:`UserProfileFact` with
        ``source = "aeat_census_read"``. Pre-existing
        ``aeat_census_read`` facts are replaced; facts from other
        sources (``manual_cli``, wizard) are preserved untouched so
        operator-entered values stay addressable for the compare verb.

        Emits no events itself; the caller (CLI handler) is responsible
        for surfacing ``CENSUS_APPLIED`` on the bucket-event-history
        catalogue so the stale-cascade walker can react.

        Raises :exc:`CensoApplyConflictError` when the profile is
        absent — there is nothing to stamp facts onto.
        """

        snapshot = self.show_census(profile_id=profile_id, snapshot_id=snapshot_id)
        if not self._profiles.exists(profile_id):
            raise CensoApplyConflictError(
                f"profile {profile_id!r} does not exist; create it before applying census",
            )
        profile = self._profiles.load(profile_id)
        before = _profile_facts_by_path(profile)
        retained = tuple(fact for fact in profile.facts if fact.source != CENSUS_SOURCE_TAG)
        new_census_facts = tuple(
            UserProfileFact(path=path, value=value, source=CENSUS_SOURCE_TAG)
            for path, value in sorted(snapshot.census_facts.items())
        )
        updated = profile.model_copy(
            update={
                "facts": retained + new_census_facts,
                "updated_at": datetime.now(UTC),
            },
        )
        self._profiles.save(updated)
        seeded = self._seed_home_office_usage_ratios_from_snapshot(snapshot)
        written: list[str] = []
        unchanged: list[str] = []
        for path, value in sorted(snapshot.census_facts.items()):
            if before.get(path) == value:
                unchanged.append(path)
            else:
                written.append(path)
        return CensoApplyResult(
            snapshot_id=snapshot.snapshot_id,
            profile_id=profile_id.strip(),
            written_paths=tuple(written),
            unchanged_paths=tuple(unchanged),
            seeded_home_office_categories=seeded,
        )

    def _seed_home_office_usage_ratios_from_snapshot(
        self, snapshot: CensoSnapshot,
    ) -> tuple[str, ...]:
        """Compute HOME_OFFICE per-category ratios from the snapshot's
        vivienda_office facts and persist them into the usage-ratios
        store. Returns the canonical category-id list that landed.

        Idempotent: if office_m2 / total_m2 are absent or the derived
        ratio matches what is already persisted, nothing is written and
        the empty tuple is returned. Operator-set overrides on
        non-HOME_OFFICE categories are preserved.
        """

        from ...domain.usage_ratios import (
            UsageRatioProfile,
            derive_home_office_ratios_from_census,
            load_usage_ratios,
            save_usage_ratios,
        )

        total_raw = snapshot.census_facts.get("vivienda_office.total_m2")
        office_raw = snapshot.census_facts.get("vivienda_office.office_m2")
        if total_raw is None or office_raw is None:
            return ()
        try:
            total = Decimal(total_raw)
            office = Decimal(office_raw)
        except (InvalidOperation, ValueError):
            return ()
        if total <= Decimal("0") or office < Decimal("0") or office > total:
            return ()
        raw_ratio = office / total
        derived = derive_home_office_ratios_from_census(raw_ratio, year=2025)
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
        """Return ``office_m2 / total_m2`` from the active census snapshot.

        Used by the ledger ratios CLI and the manual-transaction
        classify path to apply the legally-effective
        :func:`aeat.application.ledger._ratios.census_override_warning`
        and :func:`aeat.application.ledger._ratios.census_business_pct_for`
        helpers without each consumer re-implementing the snapshot
        lookup. Returns ``None`` when no ACTIVE snapshot exists OR when
        either ``vivienda_office.total_m2`` / ``vivienda_office.office_m2``
        is absent / non-decimal / zero.
        """

        snapshot = self._snapshots.latest_active(profile_id=profile_id)
        if snapshot is None:
            return None
        total_raw = snapshot.census_facts.get("vivienda_office.total_m2")
        office_raw = snapshot.census_facts.get("vivienda_office.office_m2")
        if total_raw is None or office_raw is None:
            return None
        try:
            total = Decimal(total_raw)
            office = Decimal(office_raw)
        except (InvalidOperation, ValueError):
            return None
        if total <= Decimal("0") or office < Decimal("0"):
            return None
        ratio = office / total
        if ratio > Decimal("1"):
            return None
        return ratio


def _profile_facts_by_path(profile: UserProfileRecord | None) -> dict[str, str]:
    """Flatten a profile's facts into a path → string-value mapping.

    Census comparison is string-based because the snapshot side is
    string-only (see :class:`aeat.application.live._censo`); the
    profile's typed values are coerced via ``str()`` for the diff.
    """

    if profile is None:
        return {}
    return {fact.path: _coerce_to_str(fact.value) for fact in profile.facts}


def _coerce_to_str(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _compare(
    census_facts: Mapping[str, str],
    profile_facts: Mapping[str, str],
) -> tuple[CensoFieldComparison, ...]:
    paths = sorted(set(census_facts) | set(profile_facts))
    rows: list[CensoFieldComparison] = []
    for path in paths:
        census_value = census_facts.get(path)
        profile_value = profile_facts.get(path)
        if census_value is not None and profile_value is not None:
            status = (
                CensoComparisonStatus.MATCHES
                if census_value == profile_value
                else CensoComparisonStatus.DIVERGES
            )
        elif census_value is not None:
            status = CensoComparisonStatus.CENSUS_ONLY
        else:
            status = CensoComparisonStatus.PROFILE_ONLY
        rows.append(
            CensoFieldComparison(
                path=path,
                census_value=census_value,
                profile_value=profile_value,
                status=status,
            ),
        )
    return tuple(rows)


__all__ = [
    "CENSUS_SOURCE_TAG",
    "CensoApplyResult",
    "CensoComparisonStatus",
    "CensoFactSource",
    "CensoFieldComparison",
    "CensoProfileComparison",
    "CensoSyncService",
]
