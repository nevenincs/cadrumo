"""Application service for the capital-goods IVA regularización register.

Thin orchestration over
:class:`~aeat.adapters.persistence.profile.bienes_inversion.BienesInversionIvaRegisterRepository`:
the operator declares tracked capital goods and lists them. The register is
authoritative profile-scoped state; this service owns no calculation, only the
declare/list surface the CLI exposes. The art-109 annual compute lives in the
pure domain module :mod:`aeat.domain.bienes_inversion`.
"""

from __future__ import annotations

from ...adapters.persistence.profile.bienes_inversion import (
    BienesInversionIvaRegisterRepository,
)
from ...domain.bienes_inversion import (
    BienesInversionIvaRegister,
    BienInversionIvaRecord,
)


class BienesInversionRegisterService:
    """Declare and list tracked bienes de inversión on the active profile."""

    def __init__(self, *, repository: BienesInversionIvaRegisterRepository | None = None) -> None:
        """Initialise the service, defaulting to the active-bucket register repository."""
        self._repository = repository if repository is not None else BienesInversionIvaRegisterRepository()

    def declare(self, record: BienInversionIvaRecord) -> BienesInversionIvaRegister:
        """Atomically add ``record`` to the register, refusing duplicate identifiers.

        Args:
            record: The capital-good record to persist.

        Returns:
            The updated :class:`BienesInversionIvaRegister`.
        """
        return self._repository.add(record)

    def list_all(self) -> BienesInversionIvaRegister:
        """Return the full register (empty when nothing has been declared)."""
        return self._repository.load()


__all__ = ["BienesInversionRegisterService"]
