"""Application service for the cross-period IVA prorrata register.

Thin orchestration over
:class:`adapters.persistence.profile.prorrata_register.ProrrataRegisterRepository`:
the caller declares a per-ejercicio prorrata entry, lists the register, and reads
one entry by ``(ejercicio, sector)`` key. The register is authoritative
profile-scoped state; this service owns no calculation, only the declare/list/get
surface. The LIVA arts. 102-106 compute substrate lives in the pure domain module
:mod:`domain.iva`, and the precedence-ladder resolution lives in
:mod:`domain.prorrata_register`.

The seed from the stamped prior settlement observation (art. 105.Uno), the
provenance-tagged art. 105.Dos/Tres overrides, and the settlement write-back are
built on top of this facade in later waves; this module is only the persistence
surface they compose over.

See Also:
    :mod:`domain.prorrata_register`
        Pure register records and the precedence-ladder resolver.
    :mod:`adapters.persistence.profile.prorrata_register`
        FINANCIAL secure-object repository that stores the profile-scoped
        register singleton.
    :mod:`domain.iva`
        Legal IVA prorrata substrate that supplies the definitive percentage
        and the art. 105.Cuatro regularisation cuota.
"""

from __future__ import annotations

__all__: tuple[str, ...] = ()
