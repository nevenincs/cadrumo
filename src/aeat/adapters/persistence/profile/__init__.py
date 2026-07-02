"""Persistence adapters for profile-scoped taxpayer data.

Namespace package whose children hold concrete repositories for taxpayer data a
profile owns beyond its core identity. It exposes no symbols of its own;
consume the child modules directly:

* :mod:`adapters.persistence.profile.assets` for the FINANCIAL secure-object
  actividad-económica asset and amortización ledgers.
* :mod:`adapters.persistence.profile.inventory` for FINANCIAL secure-object
  stock-valuation ledgers.
* :mod:`adapters.persistence.profile.bienes_inversion` for the FINANCIAL
  secure-object :class:`domain.bienes_inversion.BienesInversionIvaRegister`.
* :mod:`adapters.persistence.profile.fincas` for ORM-backed finca,
  arrendamiento, rendimiento, gasto, and amortización repositories.
"""

__all__: list[str] = []
