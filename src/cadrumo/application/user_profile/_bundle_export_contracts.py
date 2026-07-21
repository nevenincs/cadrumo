"""Typed contracts for the sole portable profile-bundle export service.

This module owns the closed value sets and typed envelopes the single
:func:`~cadrumo.application.user_profile.export_profile_bundle` authority
composes: the operator :class:`ProfileBundleExportPurpose` (portable transfer
versus subject access), the :class:`ProfileBundleExportTransport` wire
protection, the :class:`ProfileBundleExportRequest` input, the resolved
:class:`ProfileBundleExportTarget` identity used for same-target locking and
operation-state keying, and the published :class:`ProfileBundleExportResult`.

Data categories are derived from the actual :class:`UserProfilePortableExport`
schema fields and the registry namespaces the bundle carries, never from a
static hand-maintained list that silently drifts from what the bundle contains.
The sealed recovery archive is a separate confidentiality and restoration
surface and is deliberately absent here.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field, SecretStr, computed_field

from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN

if TYPE_CHECKING:
    from ...domain.user_profile import UserProfilePortableExport

_CARRIED_NAMESPACE_CATEGORY_PREFIX = "secure_object_namespace:"

# Schema-derived category labels keyed by the actual serialized field name on
# :class:`UserProfilePortableExport`. A field that ceases to exist drops its
# category automatically; a new financial-history field surfaces here rather
# than in a CLI-owned static list.
_CATEGORY_BY_BUNDLE_FIELD: dict[str, str] = {
    "profile": "profile_identity_and_facts",
    "work_units": "modelo_work_units",
    "ledger_transactions": "ledger_transactions",
    "calculation_revisions": "calculation_revisions",
    "filing_records": "filing_records",
}


class ProfileBundleExportPurpose(StrEnum):
    """Operator intent for one portable bundle publication."""

    PORTABLE_TRANSFER = "portable_transfer"
    SUBJECT_ACCESS = "subject_access"


class ProfileBundleExportTransport(StrEnum):
    """Wire protection applied to the published portable bundle."""

    CLEARTEXT_LOCAL = "cleartext_local"
    PASSPHRASE_ENCRYPTED = "passphrase_encrypted"  # noqa: S105 - transport taxonomy, not a secret


class ProfileBundleExportRequest(BaseModel):
    """Typed request for the sole portable profile export operation."""

    model_config = _STRICT_FROZEN

    profile_name: str | None = Field(default=None, min_length=1, max_length=160)
    destination: Path
    purpose: ProfileBundleExportPurpose
    transport: ProfileBundleExportTransport
    passphrase: SecretStr | None = None


class ProfileBundleExportTarget(BaseModel):
    """Resolved destination identity for same-target locking and journal keying.

    Two export requests naming the same file resolve to one canonical
    ``identity`` so the service can hold one exclusive lock per target and key
    a durable operation-state record deterministically, independent of the
    literal spelling the operator supplied.
    """

    model_config = _STRICT_FROZEN

    destination: Path

    # TYPE-IGNORE-RATIONALE-PYDANTIC-COMPUTED-FIELD:
    # pydantic v2 computed_field stacked over property trips the checker's
    # prop-decorator rule; the runtime is the sanctioned pydantic idiom.
    @computed_field  # type: ignore[prop-decorator]
    @property
    def identity(self) -> str:
        """Return the canonical absolute-path identity for this target."""
        return str(self.destination.expanduser().resolve(strict=False))


class ProfileBundleExportResult(BaseModel):
    """Published profile-bundle identity and presentation metadata."""

    model_config = _STRICT_FROZEN

    profile_id: str
    display_name: str
    destination: Path
    bundle_schema_version: int
    purpose: ProfileBundleExportPurpose
    transport: ProfileBundleExportTransport
    data_categories: tuple[str, ...]


def bundle_data_categories(bundle: UserProfilePortableExport) -> tuple[str, ...]:
    """Derive the personal-data categories a bundle carries from its schema.

    The category set is computed from the serialized field names present on
    :class:`UserProfilePortableExport` and the registry namespaces the bundle's
    coverage manifest declares carried, so it cannot silently diverge from the
    bundle's actual contents.
    """
    schema_categories = tuple(
        category
        for field_name in type(bundle).model_fields
        if (category := _CATEGORY_BY_BUNDLE_FIELD.get(field_name)) is not None
    )
    carried = tuple(
        f"{_CARRIED_NAMESPACE_CATEGORY_PREFIX}{namespace}" for namespace in bundle.coverage_manifest.carried_namespaces
    )
    return (*schema_categories, *carried)


__all__ = [
    "ProfileBundleExportPurpose",
    "ProfileBundleExportRequest",
    "ProfileBundleExportResult",
    "ProfileBundleExportTarget",
    "ProfileBundleExportTransport",
    "bundle_data_categories",
]
