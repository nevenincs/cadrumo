"""Persistence adapters for profile-scoped taxpayer data.

Namespace package whose children hold concrete repositories for taxpayer data a
profile owns beyond its core identity. Repositories and shared persistence
kernels are consumed from their defining child modules directly:

* :mod:`adapters.persistence.profile.inventory` for FINANCIAL secure-object
  stock-valuation ledgers.
* :mod:`adapters.persistence.profile.bienes_inversion` for the FINANCIAL
  secure-object :class:`domain.bienes_inversion.register.BienesInversionIvaRegister`.
* ``adapters.persistence.profile.fincas`` for ORM-backed finca,
  arrendamiento, rendimiento, gasto, and amortización repositories.
* :mod:`adapters.persistence.profile.usage_ratios` for the FINANCIAL
  secure-object :class:`domain.usage_ratios.model.UsageRatioProfile` load / save
  helpers and the censo refuse-load guard.
* :mod:`adapters.persistence.profile.submission` for the AUDIT secure-object
  :class:`domain.submission.models.ModeloPresentado` repository behind the
  :class:`domain.submission.protocols.SubmissionRepositoryProtocol` port.
* :mod:`adapters.persistence.profile.justificante` for the AUDIT secure-object
  :class:`domain.justificante.schema.Justificante` receipt-metadata repository.
* :mod:`adapters.persistence.profile.filing_drafts` for the FINANCIAL
  secure-object :class:`domain.filing.schema.ModeloDraft` repository.
"""

from __future__ import annotations

__all__: tuple[str, ...] = ()
