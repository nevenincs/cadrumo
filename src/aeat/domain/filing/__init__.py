"""Filing domain package: records, protocols, validator, repositories.

The :mod:`aeat.domain.filing` subpackage owns the immutable records
that describe a filing draft (and its amendment), the cross-package
Protocols upstream subpackages plug into, the cross-cutting
:class:`FilingValidator`, the FilingDraft <-> Justificante
reconciliation engine, and the governed-persistence repositories
(FINANCIAL drafts and AUDIT amendments).

The orchestration entry points (:func:`aeat.application.filing.build_draft`,
:func:`aeat.application.filing.validate_draft`,
:func:`aeat.application.filing.approve_draft`,
:func:`aeat.application.filing.build_complementaria`,
:func:`aeat.application.filing.import_filing_from_justificante`)
live at :mod:`aeat.application.filing`: domain records are stable
boundary-crossing types; the use cases that compose them belong on
the connector layer.
"""

from __future__ import annotations

from ._amendment import (
    AmendmentKind,
    CasillaChange,
    CasillaDelta,
    CasillaInputs,
    FilingAmendment,
    ModeloCode,
    make_amendment_id,
)
from ._complementaria_repository import (
    FilingAmendmentRepository,
)
from ._errors import (
    FilingAmendmentError,
    FilingAmendmentValidationError,
    FilingBuilderError,
    FilingComputationError,
    FilingDraftError,
    FilingExportError,
    FilingExportValidationError,
    FilingImportError,
    FilingValidationError,
)
from ._protocols import (
    CasillaCollection,
    CasillaSchema,
    CasillaSchemaProvider,
    DeadlineChecker,
    DeadlineStatus,
    FilingInputs,
    FilingProfile,
    ModeloIdentity,
)
from ._repository import (
    FilingDraftRepository,
)
from ._schema import (
    APPROVAL_BASIS_VERSION,
    FilingApprovalBasis,
    FilingBindingValue,
    FilingDraft,
    ModeloDraftStatus,
    FilingScalar,
    FilingValidationFinding,
    FilingValue,
    FilingValueKind,
    compute_draft_id,
)
from ._validator import (
    FilingValidator,
    apply_validation,
    derive_validation_status,
)

__all__ = [
    "APPROVAL_BASIS_VERSION",
    "AmendmentKind",
    "CasillaChange",
    "CasillaCollection",
    "CasillaDelta",
    "CasillaInputs",
    "CasillaSchema",
    "CasillaSchemaProvider",
    "DeadlineChecker",
    "DeadlineStatus",
    "FilingAmendment",
    "FilingAmendmentError",
    "FilingAmendmentRepository",
    "FilingAmendmentValidationError",
    "FilingApprovalBasis",
    "FilingBindingValue",
    "FilingBuilderError",
    "FilingComputationError",
    "FilingDraft",
    "FilingDraftError",
    "FilingDraftRepository",
    "ModeloDraftStatus",
    "FilingExportError",
    "FilingExportValidationError",
    "FilingImportError",
    "FilingInputs",
    "FilingProfile",
    "FilingScalar",
    "FilingValidationError",
    "FilingValidationFinding",
    "FilingValidator",
    "FilingValue",
    "FilingValueKind",
    "ModeloCode",
    "ModeloIdentity",
    "apply_validation",
    "compute_draft_id",
    "derive_validation_status",
    "make_amendment_id",
]
