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

__all__: tuple[str, ...] = ()
