"""Application custody hold-evidence owner orchestration."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Final, Literal
from uuid import UUID

from ...core.paths import effective_storage_root
from ...core.storage_taxonomy import StorageCategory
from ...core.storage_taxonomy_locations import storage_location
from ...core.time.utc import validate_utc_aware
from ..profile_deletion_hold_contract import ProfileDeletionHoldOwnerProjection
from .custody_hold_models import (
    ProfileCustodyHoldAssessment,
    ProfileCustodyHoldEvidence,
    evidence_from_owner_projection,
)
from .custody_ports import ProfileCustodyLocalRecordStore, default_profile_custody_local_record_store
from .custody_transactions import (
    ProfileCustodyTransactionCorruptError,
    ProfileCustodyTransactionError,
    ProfileCustodyTransactionRefusalError,
    canonical_model_bytes,
)

DERIVED_HOLD_EVIDENCE_DIRNAME: Final[str] = (
    storage_location(
        StorageCategory.PROFILE_CUSTODY_HOLD_DERIVED_EVIDENCE,
    )
    .relative_path()
    .name
)
"""The derived join's directory name, read from its one taxonomy declaration.

The storage path registry spells the same segment in this format's grammar, so
the name is declared once and read in both places rather than typed in each.
"""


def _write_canonical_file(path: Path, payload: bytes, store: ProfileCustodyLocalRecordStore) -> None:
    try:
        store.write(path, payload, publish_once=False)
    except Exception as exc:
        raise ProfileCustodyTransactionCorruptError(
            "canonical custody owner record cannot be atomically written"
        ) from exc


class _ProfileCustodyHoldEvidenceOwner:
    """Read and persist a derived evidence projection from one external owner."""

    def __init__(self, *, root: Path | None = None, owner: Literal["legal", "filing"]) -> None:
        self._storage_root = effective_storage_root(root)
        self._owner = owner
        self._root = (
            self._storage_root
            / storage_location(StorageCategory.PROFILE_CUSTODY_HOLD_EVIDENCE).relative_path()
            / DERIVED_HOLD_EVIDENCE_DIRNAME
            / owner
        )

    def refresh(self, profile_id: UUID, *, now: datetime) -> ProfileCustodyHoldEvidence:
        store = default_profile_custody_local_record_store()
        projection = self._owner_projection(profile_id, now=now)
        evidence = evidence_from_owner_projection(projection)
        try:
            store.ensure_directory(self._root.parent.parent)
            store.ensure_directory(self._root.parent)
            store.ensure_directory(self._root)
            with store.lock(self._root / ".evidence.lock"):
                _write_canonical_file(
                    self.path(profile_id),
                    canonical_model_bytes(evidence, maximum_bytes=1024, subject=f"{self._owner} hold evidence"),
                    store,
                )
        except Exception as exc:
            raise ProfileCustodyTransactionCorruptError(
                f"canonical {self._owner} hold evidence cannot be durably refreshed"
            ) from exc
        return evidence

    def _owner_projection(self, profile_id: UUID, *, now: datetime) -> ProfileDeletionHoldOwnerProjection:
        try:
            # Deferred to break the import cycle these owner packages form with
            # custody, not to reach past their facades: each names its owning
            # package's public surface exactly as a module-level import would.
            if self._owner == "legal":
                from ..evidence._profile_legal_hold import LegalHoldCaseAuthority

                return LegalHoldCaseAuthority(root=self._storage_root).project(profile_id, now=now)
            from ..filing._profile_filing_retention import FilingRetentionAuthority

            return FilingRetentionAuthority(root=self._storage_root).project(profile_id, now=now)
        except FileNotFoundError as exc:
            raise ProfileCustodyTransactionRefusalError(f"canonical {self._owner} hold owner facts are absent") from exc
        except ProfileCustodyTransactionError:
            raise
        except Exception as exc:
            raise ProfileCustodyTransactionCorruptError(
                f"canonical {self._owner} hold owner facts cannot be authenticated"
            ) from exc

    def path(self, profile_id: UUID) -> Path:
        return self._root / f"{profile_id}.json"


class ProfileCustodyHoldAuthority:
    """Join independently-owned legal and filing evidence for deletion preflight."""

    def __init__(self, *, root: Path | None = None) -> None:
        """Bind the independently-owned legal and filing evidence owners."""
        self._legal = _ProfileCustodyHoldEvidenceOwner(root=root, owner="legal")
        self._filing = _ProfileCustodyHoldEvidenceOwner(root=root, owner="filing")

    def assess(self, profile_id: UUID, *, now: datetime) -> ProfileCustodyHoldAssessment:
        """Return the joined deletion-preflight assessment for a profile at ``now``."""
        validate_utc_aware(now)
        return ProfileCustodyHoldAssessment.from_owner_evidence(
            legal=self._legal.refresh(profile_id, now=now),
            filing=self._filing.refresh(profile_id, now=now),
        )


__all__ = ["ProfileCustodyHoldAuthority"]
