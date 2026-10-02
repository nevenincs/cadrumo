"""Bind the existing maritime preview service to its exact profile worker."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from ..application.modelo.maritime_preview import (
    ModeloMaritimeExemptionPreview,
    preview_maritime_exemption_for_active_profile,
)
from ..application.modelo.maritime_preview_operation import ModeloMaritimePreviewPorts
from ..application.user_profile.access_contracts import AccessDenialCode
from ..application.user_profile.access_errors import ProfileAccessRefusedError
from ..core.bucket_pointer import require_active_bucket_id
from ..domain.calculations.registry.authority import PinnedAuthorityOperation


def build_modelo_maritime_preview_ports(
    *, profile_id: UUID, operation: PinnedAuthorityOperation
) -> ModeloMaritimePreviewPorts:
    """Compose lazily; the canonical service owns fact reading, dates and retry."""

    def require_profile() -> None:
        if require_active_bucket_id() != str(profile_id):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)

    require_profile()

    def preview(
        *, annual_salary: Decimal | None, qualifying_days: int | None, gross_navigation_income: Decimal | None
    ) -> ModeloMaritimeExemptionPreview:
        require_profile()
        result = preview_maritime_exemption_for_active_profile(
            annual_salary=annual_salary,
            qualifying_days=qualifying_days,
            gross_navigation_income=gross_navigation_income,
            operation=operation,
        )
        require_profile()
        return result

    return ModeloMaritimePreviewPorts(profile_id=profile_id, operation=operation, preview=preview)


__all__ = ["build_modelo_maritime_preview_ports"]
