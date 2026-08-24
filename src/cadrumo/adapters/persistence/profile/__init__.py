"""Persistence adapters for profile-scoped taxpayer data.

Namespace package whose children hold concrete repositories for taxpayer data a
profile owns beyond its core identity. It exposes one shared symbol at the
package level -- :class:`ProfileBareModelSecurePersistence`, the bare-document
singleton-persistence kernel several of this package's own repositories
compose, and the only piece of this package a caller OUTSIDE it (a namespace
whose on-disk rows are bare JSON, not Envelope-wrapped) has a sanctioned
reason to import directly, per ``aeat-architecture-boundaries``.
Every other repository is consumed from its own child module directly:

* :mod:`adapters.persistence.profile.assets` for the FINANCIAL secure-object
  actividad-económica asset and amortización ledgers.
* :mod:`adapters.persistence.profile.inventory` for FINANCIAL secure-object
  stock-valuation ledgers.
* :mod:`adapters.persistence.profile.bienes_inversion` for the FINANCIAL
  secure-object :class:`domain.bienes_inversion.BienesInversionIvaRegister`.
* :mod:`adapters.persistence.profile.fincas` for ORM-backed finca,
  arrendamiento, rendimiento, gasto, and amortización repositories.
* :mod:`adapters.persistence.profile.usage_ratios` for the FINANCIAL
  secure-object :class:`domain.usage_ratios.UsageRatioProfile` load / save
  helpers and the censo refuse-load guard.
* :mod:`adapters.persistence.profile.submission` for the AUDIT secure-object
  :class:`domain.submission.ModeloPresentado` repository behind the
  :class:`domain.submission.SubmissionRepositoryProtocol` port.
* :mod:`adapters.persistence.profile.justificante` for the AUDIT secure-object
  :class:`domain.justificante.Justificante` receipt-metadata repository.
* :mod:`adapters.persistence.profile.filing_drafts` for the FINANCIAL
  secure-object :class:`domain.filing.ModeloDraft` repository behind the
  :class:`domain.filing.ModeloDraftRepositoryProtocol` port.
* :mod:`adapters.persistence.profile.filing_amendments` for the AUDIT
  secure-object complementaria/sustitutiva amendment repository behind the
  :class:`domain.filing.ModeloAmendmentRepositoryProtocol` port.
"""

from ._secure_model_document import ProfileBareModelSecurePersistence
from .sync_runs import SyncRunRecordRepository

__all__: list[str] = [
    "ProfileBareModelSecurePersistence",
    "SyncRunRecordRepository",
]
