"""Public filing facade for modelo drafts, validation, and amendment records.

The :mod:`domain.filing` subpackage owns the immutable records and
repository contracts that describe registry-backed local drafts:
:class:`ModeloDraft`, :class:`ModeloValue`, :class:`ModeloBindingValue`,
:class:`ModeloCasillaProvenance`, and :class:`ModeloValidationFinding`.
Those records preserve the registry ``snapshot_ref``, casilla values, binding
provenance, and casilla provenance that identify and ground a local draft.

The facade also exports :class:`ModeloValidator`, the protocol contracts
consumed by :mod:`application.filing`, the LGT Art. 122 amendment records
:class:`ModeloComplementaria` and :class:`ModeloSustitutiva`, their
:class:`CasillaChange` deltas, and the governed repository contracts. Drafts
persist through
:class:`~cadrumo.adapters.persistence.profile.filing_drafts.ModeloDraftRepository`
(behind :class:`ModeloDraftRepositoryProtocol`) in FINANCIAL encrypted storage;
amendments persist through
:class:`~cadrumo.adapters.persistence.profile.filing_amendments.ModeloAmendmentRepository`
(behind :class:`ModeloAmendmentRepositoryProtocol`) in AUDIT encrypted storage.

The orchestration entry points (:func:`application.filing.build_draft`,
:func:`application.filing.validate_draft`,
:func:`application.filing.approve_draft`,
:func:`application.filing.build_complementaria`,
:func:`application.filing.import_filing_from_justificante`)
live at :mod:`application.filing`: domain records are stable
boundary-crossing types; the use cases that compose them belong on
the application layer. :class:`domain.justificante.Justificante` data is
receipt metadata and import evidence, not a casilla-value authority; when the
application import path needs an audit baseline, it composes these draft records
with :class:`domain.submission.ModeloPresentado` rather than extending the
draft schema with submission state.

See Also:
    :mod:`application.filing`
        Application facade that builds, reviews, approves, exports, verifies,
        imports, and amends these draft records.
    :class:`ModeloDraft`
        Registry-backed draft aggregate carrying values, binding provenance,
        casilla provenance, and registry snapshot identity.
    :class:`ModeloValidator`
        Domain validator used by application review and approval flows.
    :class:`ModeloAmendmentRepositoryProtocol`
        Narrow domain-facing port for governed AUDIT persistence of
        complementaria and sustitutiva records.
    :mod:`domain.submission`
        Local-only submission audit records paired with imported or historical
        draft baselines without turning draft records into live submissions.
    :mod:`domain.justificante`
        Receipt metadata that filing imports may compose with drafts, without
        treating receipt data as a casilla-value authority.
    :mod:`domain.calculations.registry`
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
from .errors import (
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
    ModeloAmendmentRepositoryProtocol,
    ModeloDraftRepositoryProtocol,
    ModeloInputs,
    ModeloInputScalar,
    ModeloInputValue,
    ModeloProfile,
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
    registry_schema_version,
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
    "ModeloAmendmentRepositoryProtocol",
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
    "ModeloDraftRepositoryProtocol",
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
    "registry_schema_version",
]
