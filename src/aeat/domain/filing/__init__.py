"""Filing domain package: records, protocols, validator, repositories.

The :mod:`aeat.domain.filing` subpackage owns the immutable records
that describe a filing draft (and its amendment), the cross-package
Protocols upstream subpackages plug into, the cross-cutting
:class:`ModeloValidator`, the :class:`ModeloDraft` -- Justificante
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

See Also:
    :mod:`aeat.application.filing`
        Application facade that builds, reviews, approves, exports, verifies,
        imports, and amends these draft records.
    :class:`ModeloDraft`
        Registry-backed draft aggregate persisted by
        :class:`ModeloDraftRepository`.
    :class:`ModeloValidator`
        Domain validator used by application review and approval flows.
    :class:`ModeloAmendmentRepository`
        Governed AUDIT persistence for complementaria and sustitutiva records.
    :mod:`aeat.domain.submission`
        Local-only submitted-state lifecycle that consumes approved draft-like
        records before any live-write path is refused elsewhere.
    :mod:`aeat.domain.calculations.registry`
        Registry snapshot and export-layout authority used to construct and
        verify draft casilla payloads.
"""

from __future__ import annotations

from ._amendment import (
    AmendmentKind,
    BaseAmendment,
    CasillaChange,
    CasillaDelta,
    CasillaInputs,
    ModeloCode,
    ModeloComplementaria,
    ModeloSustitutiva,
    make_amendment_id,
)
from ._complementaria_repository import (
    ModeloAmendmentRepository,
)
from ._errors import (
    FilingExportError,
    FilingExportValidationError,
    FilingValidationError,
    ModeloAmendmentError,
    ModeloAmendmentValidationError,
    ModeloBuilderError,
    ModeloComputationError,
    ModeloDraftError,
    ModeloImportError,
)
from ._protocols import (
    CasillaCollection,
    CasillaSchema,
    CasillaSchemaProvider,
    DeadlineChecker,
    DeadlineStatus,
    ModeloIdentity,
    ModeloInputs,
    ModeloInputScalar,
    ModeloInputValue,
    ModeloProfile,
)
from ._repository import (
    ModeloDraftRepository,
)
from ._schema import (
    APPROVAL_BASIS_VERSION,
    ModeloApprovalBasis,
    ModeloBindingValue,
    ModeloCasillaProvenance,
    ModeloDraft,
    ModeloScalar,
    ModeloValidationFinding,
    ModeloValue,
    ModeloValueKind,
    compute_modelo_draft_id,
)
from ._validator import (
    ModeloValidator,
    apply_validation,
    derive_validation_status,
)

__all__ = [
    "APPROVAL_BASIS_VERSION",
    "AmendmentKind",
    "BaseAmendment",
    "CasillaChange",
    "CasillaCollection",
    "CasillaDelta",
    "CasillaInputs",
    "CasillaSchema",
    "CasillaSchemaProvider",
    "DeadlineChecker",
    "DeadlineStatus",
    "FilingExportError",
    "FilingExportValidationError",
    "FilingValidationError",
    "ModeloAmendmentError",
    "ModeloAmendmentRepository",
    "ModeloAmendmentValidationError",
    "ModeloApprovalBasis",
    "ModeloBindingValue",
    "ModeloBuilderError",
    "ModeloCasillaProvenance",
    "ModeloCode",
    "ModeloComplementaria",
    "ModeloComputationError",
    "ModeloDraft",
    "ModeloDraftError",
    "ModeloDraftRepository",
    "ModeloIdentity",
    "ModeloImportError",
    "ModeloInputScalar",
    "ModeloInputValue",
    "ModeloInputs",
    "ModeloProfile",
    "ModeloScalar",
    "ModeloSustitutiva",
    "ModeloValidationFinding",
    "ModeloValidator",
    "ModeloValue",
    "ModeloValueKind",
    "apply_validation",
    "compute_modelo_draft_id",
    "derive_validation_status",
    "make_amendment_id",
]
