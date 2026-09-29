"""Bind invoice inspection to the worker's exact encrypted profile store."""

from __future__ import annotations

from uuid import UUID

from ..application.invoices.inspection_read_ports import InvoiceInspectionReadPorts
from ..application.user_profile.access_contracts import AccessDenialCode
from ..application.user_profile.access_errors import ProfileAccessRefusedError
from ..core.bucket_pointer import require_active_bucket_id
from ..domain.calculations.registry.authority import PinnedAuthorityOperation


def build_invoice_inspection_read_ports(
    *, bucket_id: str, operation: PinnedAuthorityOperation
) -> InvoiceInspectionReadPorts:
    """Compose the canonical invoice reader without transaction or mutation ports."""
    from ..adapters.persistence.profile.catalogue_reads import InvoiceCatalogueReadAdapter
    from ..adapters.persistence.profile.invoices import InvoiceCatalogueRepository
    from ..adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket

    profile = str(UUID(bucket_id))
    if require_active_bucket_id() != profile:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    return InvoiceInspectionReadPorts(
        bucket_id=profile,
        invoices=InvoiceCatalogueReadAdapter(
            repository=InvoiceCatalogueRepository(
                bucket_id=profile, objects=secure_object_repository_for_bucket(profile)
            )
        ),
    )
