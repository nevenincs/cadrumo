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
The field-to-label mapping is still authored here, so it is held exhaustive by
construction: every serialized field must be mapped to a category, declared
envelope metadata, or declared carried-namespace derived, and an unclassified
field refuses rather than dropping out of the disclosed set. That refusal is
what lets the subject-access response claim to list every personal-data
category held for the profile.

The sealed recovery archive is a separate confidentiality and restoration
surface and is deliberately absent here.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field, SecretStr, computed_field

from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...domain.user_profile import ProfileExportError

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

# Envelope fields that describe the export itself rather than the subject: the
# integer shape marker the import path gates on, and the provenance timestamp of
# this export run. Neither is personal data held for the profile, so neither
# earns a disclosure category.
_ENVELOPE_METADATA_BUNDLE_FIELDS: frozenset[str] = frozenset(
    {
        "bundle_schema_version",
        "exported_at",
    },
)

# Fields of the generic secure-object carry surface. Their personal data IS
# disclosed, but per registry namespace out of ``coverage_manifest`` (see the
# ``secure_object_namespace:`` categories below) rather than as one flat
# field-level label, because one carried-objects tuple spans every namespace the
# bundle carries.
_CARRIED_NAMESPACE_DERIVED_BUNDLE_FIELDS: frozenset[str] = frozenset(
    {
        "carried_objects",
        "coverage_manifest",
    },
)


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

    Classification of the schema is TOTAL: every serialized field is either
    mapped to a category, declared envelope metadata, or declared
    carried-namespace derived. A field belonging to none of the three refuses
    here rather than being dropped, because this set is what the subject-access
    response presents as every personal-data category held for the profile --
    a silently narrowed set would be a false completeness claim to a data
    subject.

    Raises:
        ProfileExportError: If the bundle schema carries a field with no
            declared personal-data classification.
    """
    field_names = tuple(type(bundle).model_fields)
    _refuse_unclassified_bundle_fields(field_names)
    schema_categories = tuple(
        category for field_name in field_names if (category := _CATEGORY_BY_BUNDLE_FIELD.get(field_name)) is not None
    )
    carried = tuple(
        f"{_CARRIED_NAMESPACE_CATEGORY_PREFIX}{namespace}" for namespace in bundle.coverage_manifest.carried_namespaces
    )
    return (*schema_categories, *carried)


def _refuse_unclassified_bundle_fields(field_names: tuple[str, ...]) -> None:
    """Refuse a bundle schema field carrying no declared disclosure classification."""
    unclassified = tuple(
        sorted(
            field_name
            for field_name in field_names
            if field_name not in _CATEGORY_BY_BUNDLE_FIELD
            and field_name not in _ENVELOPE_METADATA_BUNDLE_FIELDS
            and field_name not in _CARRIED_NAMESPACE_DERIVED_BUNDLE_FIELDS
        ),
    )
    if unclassified:
        raise ProfileExportError(
            "portable profile bundle carries schema fields with no declared personal-data "
            "classification, so the disclosed category set would be incomplete",
            context={"unclassified_fields": ", ".join(unclassified)},
        )


__all__ = [
    "ProfileBundleExportPurpose",
    "ProfileBundleExportRequest",
    "ProfileBundleExportResult",
    "ProfileBundleExportTarget",
    "ProfileBundleExportTransport",
    "bundle_data_categories",
]
