"""Application policy for portable-profile secure-object custody carry.

The application owns custody-profile normalization, fail-closed full-coverage
policy, and the exported coverage fact. Concrete persistence enumeration,
natural-key recovery, and atomic restoration are provided by the bound profile
custody port.
"""

from __future__ import annotations

from collections.abc import Iterable

from ...core.storage_taxonomy import StorageCustodyProfile
from ...domain.user_profile.errors import ProfileExportError
from ...domain.user_profile.portable_export import CarriedSecureObject, CoverageManifest
from .custody_ports import ProfileCustodyCarryMaterial, profile_custody_port


def normalize_storage_custody_profile(
    custody_profile: StorageCustodyProfile | str,
) -> StorageCustodyProfile:
    """Resolve an operator custody selection into the closed neutral value set."""
    if isinstance(custody_profile, StorageCustodyProfile):
        return custody_profile
    try:
        return StorageCustodyProfile(custody_profile)
    except ValueError as exc:
        raise ProfileExportError(context={"custody_profile": custody_profile}) from exc


def _carry_material(
    *,
    bucket_id: str,
    profile: StorageCustodyProfile,
) -> ProfileCustodyCarryMaterial:
    return profile_custody_port().collect_profile_custody_carry(
        bucket_id=bucket_id,
        profile=profile,
    )


def serialize_carried_objects(
    *,
    bucket_id: str,
    profile: StorageCustodyProfile,
) -> tuple[CarriedSecureObject, ...]:
    """Serialize every generic secure-object row selected by ``profile``."""
    return _carry_material(bucket_id=bucket_id, profile=profile).carried_objects


def build_secure_object_custody_payload(
    *,
    bucket_id: str,
    custody_profile: StorageCustodyProfile,
) -> tuple[tuple[CarriedSecureObject, ...], CoverageManifest]:
    """Build generic custody rows and their exact namespace-coverage fact."""
    material = _carry_material(bucket_id=bucket_id, profile=custody_profile)
    if custody_profile is StorageCustodyProfile.FULL and material.unclassified_namespaces:
        raise ProfileExportError(
            context={
                "unclassified_namespaces": material.unclassified_namespaces,
                "custody_profile": StorageCustodyProfile.FULL.value,
            },
        )
    coverage_manifest = CoverageManifest(
        custody_profile=(
            StorageCustodyProfile.FULL.value
            if custody_profile is StorageCustodyProfile.FULL
            else StorageCustodyProfile.STRUCTURED.value
        ),
        carried_namespaces=material.carried_namespaces,
        excluded_namespaces=material.excluded_namespaces,
        row_counts_by_namespace=material.row_counts_by_namespace,
    )
    return material.carried_objects, coverage_manifest


def restore_carried_objects(
    carried_objects: Iterable[CarriedSecureObject],
    *,
    target_bucket_id: str,
) -> None:
    """Atomically restore carried rows through the bound custody aggregate."""
    carried = tuple(carried_objects)
    if carried:
        profile_custody_port().restore_profile_custody_carry(
            carried,
            target_bucket_id=target_bucket_id,
        )


__all__ = [
    "build_secure_object_custody_payload",
    "normalize_storage_custody_profile",
    "restore_carried_objects",
    "serialize_carried_objects",
]
