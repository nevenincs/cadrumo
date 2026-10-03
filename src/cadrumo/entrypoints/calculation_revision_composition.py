"""Profile-bound persistence shared by calculation revision entrypoints."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..application.modelo.profile_export_binding import resolve_export_identity
from ..application.user_profile.access_contracts import AccessDenialCode
from ..application.user_profile.access_errors import ProfileAccessRefusedError
from ..domain.calculations.registry.authority import PinnedAuthorityOperation
from ..domain.calculations.registry.tax_id_format import SubjectTaxId

if TYPE_CHECKING:
    from ..adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
    from ..adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
    from ..adapters.persistence.storage.sql.secure_objects import SecureObjectRepository


@dataclass(frozen=True, slots=True)
class CalculationRevisionPersistenceBinding:
    """Hold one profile bucket, encrypted store, authority pin, and taxpayer identity."""

    bucket_id: str
    objects: SecureObjectRepository
    operation: PinnedAuthorityOperation | None
    taxpayer_tax_id: SubjectTaxId | None

    def calculation_repository(self) -> CalculationRevisionCatalogueRepository:
        """Build the calculation catalogue repository from this exact binding."""
        from ..adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository

        return CalculationRevisionCatalogueRepository(
            bucket_id=self.bucket_id,
            objects=self.objects,
            m303_rectificativa_taxpayer_tax_id=self.taxpayer_tax_id,
        )

    def verification_repository(self) -> VerificationReportCatalogueRepository:
        """Build the verification catalogue repository from this exact binding."""
        from ..adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository

        return VerificationReportCatalogueRepository(
            bucket_id=self.bucket_id,
            objects=self.objects,
            m303_rectificativa_taxpayer_tax_id=self.taxpayer_tax_id,
        )


def _calculation_revision_persistence_binding(
    *,
    bucket_id: str,
    objects: SecureObjectRepository,
    operation: PinnedAuthorityOperation | None,
    taxpayer_tax_id: SubjectTaxId | None,
) -> CalculationRevisionPersistenceBinding:
    """Create the immutable representation shared by both provenance routes."""
    resolved_bucket_id = bucket_id.strip()
    if not resolved_bucket_id:
        raise ValueError("calculation persistence requires a profile bucket")

    return CalculationRevisionPersistenceBinding(
        bucket_id=resolved_bucket_id,
        objects=objects,
        operation=operation,
        taxpayer_tax_id=taxpayer_tax_id,
    )


def bind_calculation_revision_persistence_from_profile(
    *,
    bucket_id: str,
    objects: SecureObjectRepository,
    operation: PinnedAuthorityOperation | None,
    profile_record: object | None = None,
) -> CalculationRevisionPersistenceBinding:
    """Bind persistence using identity resolved from this profile's record.

    An explicit ``None`` operation preserves unbound advisory reads: it does
    not select a profile, start an authority operation, or infer taxpayer
    identity from another persisted object. A held operation resolves identity
    from that profile's record using the same operation's schema and decode
    context.
    """
    resolved_bucket_id = bucket_id.strip()
    if not resolved_bucket_id:
        raise ValueError("calculation persistence requires a profile bucket")

    taxpayer_tax_id: SubjectTaxId | None = None
    if operation is not None:
        if profile_record is not None and str(getattr(profile_record, "profile_id", "")) != resolved_bucket_id:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        identity = resolve_export_identity(
            bucket_id=resolved_bucket_id,
            operation=operation,
            profile_record=profile_record,
        )
        if identity is not None:
            taxpayer_tax_id = identity[0].tax_id

    return _calculation_revision_persistence_binding(
        bucket_id=resolved_bucket_id,
        objects=objects,
        operation=operation,
        taxpayer_tax_id=taxpayer_tax_id,
    )


def bind_calculation_revision_persistence_from_resolved_identity(
    *,
    bucket_id: str,
    objects: SecureObjectRepository,
    operation: PinnedAuthorityOperation,
    taxpayer_tax_id: SubjectTaxId,
) -> CalculationRevisionPersistenceBinding:
    """Bind persistence to identity already resolved by the caller's operation."""
    return _calculation_revision_persistence_binding(
        bucket_id=bucket_id,
        objects=objects,
        operation=operation,
        taxpayer_tax_id=taxpayer_tax_id,
    )


__all__ = [
    "CalculationRevisionPersistenceBinding",
    "bind_calculation_revision_persistence_from_profile",
    "bind_calculation_revision_persistence_from_resolved_identity",
]
