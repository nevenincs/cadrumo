"""Filing domain package — records, protocols, builders, validator, repositories.

The :mod:`aeat.domain.filing` subpackage owns the immutable records
that describe a filing draft (and its amendment), the cross-package
Protocols upstream subpackages plug into, the per-modelo builders
that materialise a :class:`FilingDraft` from raw inputs, the
cross-cutting :class:`FilingValidator`, the FilingDraft <->
Justificante reconciliation engine, and the governed-persistence
repositories (FINANCIAL drafts and AUDIT amendments).

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
from ._builder import FilingBuilder
from ._builders import (
    QUARTERLY_303_INPUT_KEY,
    Modelo130Builder,
    Modelo303Builder,
    Modelo390Builder,
    get_builder,
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
    SCHEMA_VERSION_DEFAULT,
    FilingApprovalBasis,
    FilingDraft,
    FilingDraftStatus,
    FilingFindingSeverity,
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
    "QUARTERLY_303_INPUT_KEY",
    "SCHEMA_VERSION_DEFAULT",
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
    "FilingBuilder",
    "FilingBuilderError",
    "FilingComputationError",
    "FilingDraft",
    "FilingDraftError",
    "FilingDraftRepository",
    "FilingDraftStatus",
    "FilingFindingSeverity",
    "FilingImportError",
    "FilingInputs",
    "FilingProfile",
    "FilingScalar",
    "FilingValidationError",
    "FilingValidationFinding",
    "FilingValidator",
    "FilingValue",
    "FilingValueKind",
    "Modelo130Builder",
    "Modelo303Builder",
    "Modelo390Builder",
    "ModeloCode",
    "ModeloIdentity",
    "apply_validation",
    "compute_draft_id",
    "derive_validation_status",
    "get_builder",
    "make_amendment_id",
]
