"""Application service for the capital-goods IVA regularización register.

Thin orchestration over
:class:`adapters.persistence.profile.bienes_inversion.BienesInversionIvaRegisterRepository`:
the operator declares tracked capital goods and lists them. The register is
authoritative profile-scoped state; this service owns no calculation, only the
declare/list surface the CLI exposes. The art-109 annual compute lives in the
pure domain module :mod:`domain.bienes_inversion`.

The register is source evidence for the live
``bienes_inversion_regularizacion`` calculation source: application calculation
code can project it into governed Modelo 303 casilla 43 / Modelo 390
regularización binding values once definitive prorrata facts exist, and into a
non-blocking advisory when those facts are still pending. This facade does not
derive definitive prorrata percentages or write binding values.

See Also:
    :mod:`domain.bienes_inversion`
        Pure LIVA arts. 107-110 register records and annual regularización
        computations.
    :mod:`adapters.persistence.profile.bienes_inversion`
        FINANCIAL secure-object repository that stores the profile-scoped
        register singleton.
    :mod:`application.calculations`
        Calculation-source and advisory surfaces that can project the register
        once definitive prorrata inputs exist.
    :mod:`domain.iva`
        Legal IVA prorrata substrate that supplies the separate definitive
        percentage input; usage ratios are not a substitute.
"""

from __future__ import annotations

from ...adapters.persistence.profile.bienes_inversion import (
    BienesInversionIvaRegisterRepository,
)
from ...domain.bienes_inversion.register import BienesInversionIvaRegister, BienInversionIvaRecord


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
        """Return the full active-profile register.

        Returns:
            A :class:`BienesInversionIvaRegister`; empty when nothing has been
            declared.
        """
        return self._repository.load()
