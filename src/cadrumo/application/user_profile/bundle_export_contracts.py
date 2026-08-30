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
field refuses rather than dropping out of the disclosed set.

That refusal makes the CARRIED set complete, which is not the same as the
archive being complete. The bundle ships under the structured custody profile,
so whole namespaces -- attachment blobs, purchase invoice evidence, the bucket
event history -- are deliberately left in encrypted storage. A right-of-access
response listing only what it carries would therefore still overstate itself,
so :func:`bundle_excluded_data_categories` derives the omitted set from the
same coverage manifest and the two are always presented together.

The sealed recovery archive is a separate confidentiality and restoration
surface and is deliberately absent here.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field, SecretStr, computed_field

from ...core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core.identity import ProfileId
from ...domain.user_profile.errors import ProfileExportError

if TYPE_CHECKING:
    from ...domain.user_profile.portable_export import UserProfilePortableExport

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
    @computed_field
    @property
    def identity(self) -> str:
        """Return the canonical absolute-path identity for this target."""
        return str(self.destination.expanduser().resolve(strict=False))


class ProfileBundleExportReconcileFailure(BaseModel):
    """One crash-recovery operation the reconciliation sweep could not finalise.

    ``destination`` is ``None`` when the journal itself could not be read, so
    nothing is known about it beyond its identifier. ``reason`` is the refusing
    error's class name -- stable, machine-readable, and carrying no journal
    contents onto an operator-facing surface.
    """

    model_config = _STRICT_FROZEN

    journal_id: str = Field(min_length=1)
    destination: str | None = None
    reason: str = Field(min_length=1)


class ProfileBundleExportResult(BaseModel):
    """Published profile-bundle identity and presentation metadata.

    ``data_categories`` and ``excluded_data_categories`` are stated together on
    purpose: the first alone reads as a completeness claim the structured
    custody profile does not support.

    ``reconcile_failures`` carries whatever the pre-publication crash-recovery
    sweep could not finalise. It rides the result rather than being logged and
    dropped, because a journal left behind may still describe cleartext bundle
    bytes on disk and the operator running the export is the one who needs told.
    """

    model_config = _STRICT_FROZEN

    profile_id: ProfileId
    display_name: str
    destination: Path
    bundle_schema_version: int
    purpose: ProfileBundleExportPurpose
    transport: ProfileBundleExportTransport
    data_categories: tuple[str, ...]
    excluded_data_categories: tuple[str, ...] = ()
    reconcile_failures: tuple[ProfileBundleExportReconcileFailure, ...] = ()


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


def bundle_excluded_data_categories(bundle: UserProfilePortableExport) -> tuple[str, ...]:
    """Derive the personal-data categories a bundle deliberately OMITS.

    The portable bundle defaults to the structured custody profile, so every
    full-custody-only namespace -- attachment blobs and manifests, purchase
    invoice evidence, evidence bundles, apoderado authorisations, the bucket
    event history -- is left in encrypted storage rather than written into the
    cleartext archive. Those omissions are real and correct, but a
    right-of-access response that lists only what it CARRIES states a
    completeness it does not have.

    This is the counterpart of :func:`bundle_data_categories`, derived from the
    same coverage manifest the serializer already computes, so the two sets
    cannot drift from what the bundle actually did.
    """
    return tuple(
        f"{_CARRIED_NAMESPACE_CATEGORY_PREFIX}{namespace}" for namespace in bundle.coverage_manifest.excluded_namespaces
    )


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
            translated_message="errors.fail.profile_export",
            context={
                "unclassified_fields": ", ".join(unclassified),
                "all_fields_classified": False,
            },
        )


__all__ = [
    "ProfileBundleExportPurpose",
    "ProfileBundleExportReconcileFailure",
    "ProfileBundleExportRequest",
    "ProfileBundleExportResult",
    "ProfileBundleExportTarget",
    "ProfileBundleExportTransport",
    "bundle_data_categories",
    "bundle_excluded_data_categories",
]
