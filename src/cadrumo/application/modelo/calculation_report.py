"""The typed calculation report one sealed modelo revision produces.

A calculation report is the local, human- and machine-readable record of what a
verified or filed calculation revision holds: header facts that identify the
revision, the taxpayer and the authority it was calculated against, then one row
per casilla the revision carries, in the registry's section order and casilla
numbering.

This module is the single place that decides what a report contains. A
serialiser renders the report and adds nothing of its own, so two formats of the
same revision cannot disagree, and a later format needs no new content decision.
The one canonical byte spelling of a report is
:meth:`ModeloCalculationReport.canonical_bytes`, and
:attr:`ModeloCalculationReport.report_sha256` is the digest over exactly those
bytes -- not over a re-encoding of them -- so a consumer that embeds the
machine-readable form embeds what the digest describes.

Three value states stay distinct on every row, because collapsing any pair of
them into a figure would misstate a return: a measured value (including a proven
zero), an absent value the revision never realised, and a value the registry
proved does not apply to this period. Every row also carries a role, so a reader
can tell an operator input from a derived figure, a settlement subtotal and the
declaration's result without consulting the registry.

Two kinds of identity are treated as opposites here. The TAXPAYER'S own NIF and
name are shown in full: the report is the operator's record of their own
declaration, and a masked identity would leave an accountant unable to tell
whose return they are reading. A THIRD PARTY's identity is never shown: a source
reference can name a perceptor, so every reference is carried as a keyed digest
(:mod:`cadrumo.application.modelo.calculation_report_provenance_key`).

Casilla labels are the registry's own official wording and are not translated.
The label is the legal name of the box on AEAT's form; the report's language
selects its chrome, not the vocabulary of the declaration.

See Also:
    :func:`~cadrumo.application.modelo.work_review.build_modelo_work_review_casillas`:
        The canonical row assembly this builder projects.
    :mod:`cadrumo.application.modelo.calculation_report_document`:
        Serialises a report into the operator's chosen document format.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from enum import StrEnum
from types import MappingProxyType
from typing import TYPE_CHECKING, Final

from pydantic import BaseModel, Field, NonNegativeInt, model_validator

from ...core.aggregation import BindingSourceKind, CalculationSourceLineageRole
from ...core.casilla_id import CasillaId
from ...core.errors.hierarchy import CadrumoError, pydantic_validation_boundary
from ...core.external_constants import OutputLanguage
from ...core.filing_year import FilingYear
from ...core.hashing import canonical_json_bytes, sha256_hex
from ...core.i18n.render import lookup_translation
from ...core.identity.digest import ContentDigest
from ...core.identity.hex_ids import (
    CalculationRevisionId,
    FilingRecordId,
    VerificationReportId,
    WorkUnitId,
)
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.period import Period
from ...core.time.utc import UtcInstant
from ...domain.calculations.registry.ids import FormulaId, LegalRefId, SourceRefId
from ...domain.calculations.registry.schema_input_kind import InputKind
from ...domain.calculations.registry.schema_references import RegistrySnapshotRef
from ...domain.filing.schema import ModeloScalar, ModeloValueKind
from ...domain.filing.software_identity import AeatSoftwareIdentityGrade
from ...domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    CalculationSourceRef,
)
from ...domain.modelos.codes import ModeloCode
from ...domain.modelos.verification_report import VerificationCompletenessStatus
from ...domain.modelos.work_unit import WorkUnit
from .settlement_casilla import DECLARATION_RESULT_SEMANTIC_ROLES, SETTLEMENT_SEMANTIC_ROLES
from .work_review import ModeloWorkReviewCasilla

if TYPE_CHECKING:
    from .calculation_report_provenance_key import CalculationReportProvenanceKey

CALCULATION_REPORT_NOTICE_LOCALE_KEY: Final[str] = "application.modelo.calculation_report.local_calculation_notice"
"""Locale key of the statement every calculation report carries about what it is.

Owned here rather than by a serialiser so both formats state the same thing, and
read from the catalogue rather than hard-coded so the statement is in the
report's own language.
"""

CALCULATION_REPORT_CONTENT_VERSION: Final[int] = 1
"""Version of the canonical payload shape.

Part of the digest input, so a later change to which facts the canonical form
covers cannot silently produce the same digest for a different report.
"""


class CalculationReportNoticeUnavailableError(CadrumoError):
    """The catalogue carries no local-calculation statement for the report.

    A refusal rather than a blank or a humanised key: the statement is what tells
    a reader the artefact is not AEAT evidence, and a report that cannot make it
    must not be produced.
    """


class CalculationReportValueState(StrEnum):
    """Whether a reported casilla carries a figure, and why when it does not.

    Attributes:
        VALUE: The revision realised a figure for the casilla. A proven zero is
            a value and uses this state; it is not an absence.
        ABSENT: The revision carries no observation for the casilla, so no figure
            exists for it. Nothing is claimed about whether one should.
        NOT_APPLICABLE: The revision realised the casilla as absent by design --
            its declared binding produced no source anchor for this period, so
            the registry proved the casilla does not apply here.
    """

    VALUE = "value"
    ABSENT = "absent"
    NOT_APPLICABLE = "not_applicable"


class CalculationReportRowRole(StrEnum):
    """What one reported row does in the declaration.

    Derived from the registry's declared ``input_kind`` and ``semantic_role`` and
    from nothing else: never from a casilla number, a position, or a label that
    reads like a total. The set is total over
    :class:`~cadrumo.domain.calculations.registry.schema_input_kind.InputKind`, so
    every row has exactly one role and none is guessed.

    Attributes:
        INPUT: A figure supplied to the calculation, by the operator or by a
            resolved binding.
        COMPUTED: A registry formula derived it from other rows.
        SUBTOTAL: A settlement-chain figure short of the declaration's result --
            the liquidación cell an operator reads on the way to the total.
        RESULT: The figure the declaration settles.
        INFORMATIONAL: Declared informational: reported but outside the
            settlement arithmetic.
        PROJECTION_ONLY: Declared for projection only, so it reaches the filed
            artefact without taking part in the calculation.
    """

    INPUT = "input"
    COMPUTED = "computed"
    SUBTOTAL = "subtotal"
    RESULT = "result"
    INFORMATIONAL = "informational"
    PROJECTION_ONLY = "projection_only"


_ROLE_BY_INPUT_KIND: Final[Mapping[InputKind, CalculationReportRowRole]] = MappingProxyType(
    {
        InputKind.MANUAL: CalculationReportRowRole.INPUT,
        InputKind.BOUND: CalculationReportRowRole.INPUT,
        InputKind.COMPUTED: CalculationReportRowRole.COMPUTED,
        InputKind.INFORMATIONAL: CalculationReportRowRole.INFORMATIONAL,
        InputKind.PROJECTION_ONLY: CalculationReportRowRole.PROJECTION_ONLY,
    },
)
"""The role every declared input kind maps to, absent a settlement role.

A table rather than a chain of branches so an input kind with no role is a
missing enrolment the owning test detects, not a branch that quietly defaults.
"""


class ModeloCalculationReportSourceProvenance(BaseModel):
    """One resolver-level source trace the revision recorded for a casilla.

    The report-facing projection of
    :class:`~cadrumo.domain.modelos.calculation_revision.CalculationSourceRef`,
    narrowed to what a reader needs in order to recognise the source object
    without learning who it belongs to: which resolver produced the row, the
    upstream taxonomy token it came from, a keyed digest of the reference to the
    source object, and the content digest of that object when the resolver
    produced one. Regulatory grounding is not repeated here -- the row that
    carries this trace already carries the casilla's own legal and source
    references.

    **A source reference can name a third party.** A retenciones resolver builds
    its reference from a perceptor's tax identifier, so the persisted trace for
    such a row carries a NIF belonging to somebody other than the filer. That
    value never reaches this model: ``source_ref_digest`` is the keyed digest the
    profile's derived provenance key produces, with only the reference's family
    left legible. The digesting happens at the builder, so every serialisation of
    a report inherits the property rather than each having to re-apply it.
    """

    model_config = STRICT_FROZEN_CONFIG

    resolver_id: str = Field(min_length=1, max_length=128)
    resolved_binding_source: BindingSourceKind
    contributor_source_kind: str = Field(min_length=1, max_length=64)
    lineage_role: CalculationSourceLineageRole
    #: ``<family>:hmac-sha256:<hex>`` over the persisted reference.
    source_ref_digest: str = Field(min_length=1, max_length=256)
    #: ``sha256:<hex>`` or ``hmac-sha256:<hex>`` over the source object's content,
    #: or ``None`` when the resolver emitted a reference without a digest. Absence
    #: is carried as absence: it means the resolver recorded no content address,
    #: never that the object is unchanged.
    source_content_digest: str | None = Field(default=None, min_length=1, max_length=256)

    @classmethod
    def from_revision_source_ref(
        cls,
        source_ref: CalculationSourceRef,
        *,
        provenance_key: CalculationReportProvenanceKey,
    ) -> ModeloCalculationReportSourceProvenance:
        """Project one persisted revision source trace onto the report shape.

        The resolver identity and the taxonomy token are product vocabulary and
        pass through unchanged; the two free-form fields are digested.
        """
        return cls(
            resolver_id=source_ref.resolver_id,
            resolved_binding_source=source_ref.resolved_binding_source,
            contributor_source_kind=source_ref.contributor_source_kind,
            lineage_role=source_ref.lineage_role,
            source_ref_digest=provenance_key.reference_digest(source_ref.source_ref),
            source_content_digest=(
                None if source_ref.fingerprint is None else provenance_key.content_digest(source_ref.fingerprint)
            ),
        )


class ModeloCalculationReportRow(BaseModel):
    """One casilla of the reported revision, with its role, state and grounding.

    ``value`` is the typed scalar the revision realised and is ``None`` for
    every state but :attr:`CalculationReportValueState.VALUE`. A reader must
    read ``value_state`` first: a ``None`` value means "this row carries no
    figure", and which of the two reasons applies is the state's job to say.
    """

    model_config = STRICT_FROZEN_CONFIG

    casilla_id: CasillaId
    number: str = Field(min_length=1)
    section_path: tuple[str, ...]
    #: The registry's official wording for the casilla, untranslated.
    label: str
    #: The registry's declared role for the casilla, when it declares one. It is
    #: the evidence behind ``row_role`` and is carried so a reader can see what
    #: the classification rests on.
    semantic_role: str | None = None
    declared_input_kind: InputKind
    row_role: CalculationReportRowRole
    #: The registry formula that produced the value, or ``None`` for a row the
    #: operator or a binding supplied.
    formula_id: FormulaId | None = None
    realised_kind: ModeloValueKind
    value_state: CalculationReportValueState
    value: ModeloScalar
    legal_refs: tuple[LegalRefId, ...]
    source_refs: tuple[SourceRefId, ...]
    source_provenance: tuple[ModeloCalculationReportSourceProvenance, ...] = ()

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _value_matches_its_state(self) -> ModeloCalculationReportRow:
        if self.value_state is CalculationReportValueState.VALUE:
            if self.value is None:
                raise ValueError("a value-bearing calculation report row cannot carry a null value")
            return self
        if self.value is not None:
            raise ValueError(
                f"a calculation report row in state {self.value_state.value!r} cannot carry a value",
            )
        return self


class ModeloCalculationReportHeader(BaseModel):
    """The facts that identify one calculation report and what produced it.

    Every field is a traceability coordinate or the report's own language rather
    than a presentation choice, so a later document format renders these facts
    without deciding anything.

    ``modelo``, ``filing_year`` and ``period`` are the filing coordinates the
    operator addressed; ``registry_snapshot_ref`` is the registry authority the
    revision was calculated against and is carried separately because the two
    can differ in the revision dimension -- a filing period may resolve to an
    authored revision of another year.

    ``taxpayer_tax_id`` and ``taxpayer_name`` are the filer's own identity, shown
    in full. ``verification_report_id`` and ``verification_outcome`` are present
    when a verification run decided this revision, ``filing_record_id`` when it
    was filed. ``ledger_filing_snapshot_fingerprint`` is the content address of
    the ledger state behind the revision when it carries one.
    ``software_identity_grade`` is the grade the filing file for this modelo would
    stamp into its envelope header, and is ``None`` when its layout reserves no
    such slot -- never a guess that one exists.
    """

    model_config = STRICT_FROZEN_CONFIG

    modelo: ModeloCode
    filing_year: FilingYear
    period: Period
    #: Validated upstream by the profile identity boundary
    #: (``resolve_export_identity``), which is where a malformed identifier is
    #: refused; re-validating here would add a governed-facts scope requirement
    #: to a fact that is already proven.
    taxpayer_tax_id: str = Field(min_length=1, max_length=64)
    taxpayer_name: str = Field(min_length=1, max_length=256)
    calculation_revision_id: CalculationRevisionId
    calculation_revision_state: CalculationRevisionState
    work_unit_id: WorkUnitId
    verification_report_id: VerificationReportId | None = None
    verification_outcome: VerificationCompletenessStatus | None = None
    filing_record_id: FilingRecordId | None = None
    registry_snapshot_ref: RegistrySnapshotRef
    authority_logical_generation: ContentDigest
    ledger_filing_snapshot_fingerprint: ContentDigest | None = None
    software_identity_grade: AeatSoftwareIdentityGrade | None = None
    report_language: OutputLanguage
    exported_at: UtcInstant
    row_count: NonNegativeInt
    local_calculation_notice: str = Field(min_length=1)


class ModeloCalculationReport(BaseModel):
    """One sealed revision's header facts and its casilla rows.

    Rows are in the registry's own casilla order, which is its section order and
    casilla numbering.
    """

    model_config = STRICT_FROZEN_CONFIG

    header: ModeloCalculationReportHeader
    rows: tuple[ModeloCalculationReportRow, ...]

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _row_count_describes_the_rows(self) -> ModeloCalculationReport:
        if self.header.row_count != len(self.rows):
            raise ValueError(
                f"calculation report row_count {self.header.row_count} does not match its {len(self.rows)} rows",
            )
        return self

    def canonical_payload(self) -> dict[str, object]:
        """Return the JSON-compatible payload the canonical bytes encode.

        ``model_dump(mode="json")`` renders every typed value -- Decimal, date,
        enum, period -- into its stable string form, so the payload holds no
        Python object whose encoding could vary.
        """
        return {
            "content_version": CALCULATION_REPORT_CONTENT_VERSION,
            "header": self.header.model_dump(mode="json"),
            "rows": [row.model_dump(mode="json") for row in self.rows],
        }

    def canonical_bytes(self) -> bytes:
        """Return the report's canonical bytes: the exact input to its digest.

        Sorted keys, compact separators, UTF-8, defined once on the model so
        there is no second encoding of the same report. A consumer that embeds
        the machine-readable form embeds these bytes, so the digest a reader
        recomputes over what it received is the digest the builder published.
        """
        return canonical_json_bytes(self.canonical_payload())

    @property
    def report_sha256(self) -> ContentDigest:
        """SHA-256 over :meth:`canonical_bytes`.

        Derived rather than stored: a digest field on the record would have to be
        excluded from its own preimage, and a stored value that disagrees with
        the content it describes would then be constructible. Two builds from the
        same stored revision under the same authority generation, language and
        export instant produce the same bytes and therefore the same digest.
        """
        return sha256_hex(self.canonical_bytes())


def local_calculation_report_notice(language: OutputLanguage) -> str:
    """Return the local-calculation statement in ``language``.

    Spanish is the source language of every catalogue entry, so a language whose
    own value is absent falls back to Spanish rather than to a humanised key.
    Spanish absent as well is a refusal.

    Raises:
        CalculationReportNoticeUnavailableError: Neither the requested language
            nor Spanish carries the statement.
    """
    notice = lookup_translation(CALCULATION_REPORT_NOTICE_LOCALE_KEY, locale=language.value)
    if notice is None and language is not OutputLanguage.ES:
        notice = lookup_translation(CALCULATION_REPORT_NOTICE_LOCALE_KEY, locale=OutputLanguage.ES.value)
    if notice is None:
        raise CalculationReportNoticeUnavailableError(
            translated_message="application.modelo.errors.calculation_report_notice_unavailable",
            context={"report_language": language.value, "translation_key": CALCULATION_REPORT_NOTICE_LOCALE_KEY},
        )
    return notice


def calculation_report_row_role(
    *,
    declared_input_kind: InputKind,
    semantic_role: str | None,
) -> CalculationReportRowRole:
    """Classify one row's function from the registry's own declarations.

    A settlement role wins over the input kind, because the terminal liquidación
    cells are computed rows whose job is what a reader is looking for. The
    settlement roles come from
    :mod:`cadrumo.application.modelo.settlement_casilla`, which is the one place
    the product decides which casilla settles a declaration, so the report cannot
    name a different result row than the rest of the product does.

    Raises:
        ValueError: ``declared_input_kind`` has no enrolled role.
    """
    if semantic_role is not None:
        if semantic_role in DECLARATION_RESULT_SEMANTIC_ROLES:
            return CalculationReportRowRole.RESULT
        if semantic_role in SETTLEMENT_SEMANTIC_ROLES:
            return CalculationReportRowRole.SUBTOTAL
    role = _ROLE_BY_INPUT_KIND.get(declared_input_kind)
    if role is None:
        raise ValueError(f"declared input kind {declared_input_kind.value!r} has no calculation report row role")
    return role


def _row_value_state(row: ModeloWorkReviewCasilla) -> CalculationReportValueState:
    """Classify one review row into the report's three value states."""
    if row.realised_kind is ModeloValueKind.EMPTY:
        return CalculationReportValueState.ABSENT
    if row.absent_by_design:
        return CalculationReportValueState.NOT_APPLICABLE
    return CalculationReportValueState.VALUE


def _source_provenance_by_casilla(
    revision: CalculationRevision,
    *,
    provenance_key: CalculationReportProvenanceKey,
) -> dict[CasillaId, tuple[ModeloCalculationReportSourceProvenance, ...]]:
    """Group the revision's source traces by the casilla each resolution feeds.

    A trace whose resolver recorded no casilla association is not attached to a
    row: the revision carries it as "not linked at resolution time", and
    spreading it across every row would claim a subject the resolver did not.
    """
    grouped: dict[CasillaId, list[ModeloCalculationReportSourceProvenance]] = {}
    for source_ref in revision.source_provenance:
        projected = ModeloCalculationReportSourceProvenance.from_revision_source_ref(
            source_ref,
            provenance_key=provenance_key,
        )
        for casilla_id in source_ref.source_casilla_ids:
            grouped.setdefault(casilla_id, []).append(projected)
    return {casilla_id: tuple(refs) for casilla_id, refs in grouped.items()}


def build_modelo_calculation_report(
    *,
    revision: CalculationRevision,
    work_unit: WorkUnit,
    review_casillas: tuple[ModeloWorkReviewCasilla, ...],
    taxpayer_tax_id: str,
    taxpayer_name: str,
    verification_report_id: VerificationReportId | None,
    verification_outcome: VerificationCompletenessStatus | None,
    filing_record_id: FilingRecordId | None,
    authority_logical_generation: str,
    software_identity_grade: AeatSoftwareIdentityGrade | None,
    provenance_key: CalculationReportProvenanceKey,
    report_language: OutputLanguage,
    exported_at: datetime,
) -> ModeloCalculationReport:
    """Assemble the calculation report for one sealed revision.

    Args:
        revision: The sealed revision being reported. Its persisted source
            traces ground each row.
        work_unit: The revision's parent work unit, which owns the filing
            coordinates the operator addressed.
        review_casillas: The canonical review rows for the revision, already in
            registry order.
        taxpayer_tax_id: The filer's own tax identifier, shown in full.
        taxpayer_name: The filer's own name, shown in full.
        verification_report_id: Id of the verification run that decided the
            revision, or ``None`` when none did.
        verification_outcome: That run's completeness verdict, or ``None``.
        filing_record_id: Id of the filing record for this revision, or ``None``
            when the revision was never filed.
        authority_logical_generation: Logical generation of the published
            authority the caller's operation is pinned to.
        software_identity_grade: Grade of the identity the filing file for this
            modelo would stamp, or ``None`` when its layout stamps none.
        provenance_key: The profile's derived key every source reference is
            digested with.
        report_language: Language the report's chrome is rendered in, and a fact
            the digest covers.
        exported_at: UTC instant the report was produced.

    Returns:
        :class:`ModeloCalculationReport`: The header facts and the casilla rows.
    """
    provenance = _source_provenance_by_casilla(revision, provenance_key=provenance_key)
    rows = tuple(
        ModeloCalculationReportRow(
            casilla_id=row.casilla_id,
            number=row.number,
            section_path=row.section_path,
            label=row.label,
            semantic_role=row.semantic_role,
            declared_input_kind=row.declared_input_kind,
            row_role=calculation_report_row_role(
                declared_input_kind=row.declared_input_kind,
                semantic_role=row.semantic_role,
            ),
            formula_id=row.formula_id,
            realised_kind=row.realised_kind,
            value_state=state,
            value=row.value if state is CalculationReportValueState.VALUE else None,
            legal_refs=row.legal_refs,
            source_refs=row.source_refs,
            source_provenance=provenance.get(row.casilla_id, ()),
        )
        for row, state in ((row, _row_value_state(row)) for row in review_casillas)
    )
    snapshot = revision.ledger_filing_snapshot
    return ModeloCalculationReport(
        header=ModeloCalculationReportHeader(
            modelo=work_unit.modelo,
            filing_year=work_unit.filing_year,
            period=work_unit.period,
            taxpayer_tax_id=taxpayer_tax_id,
            taxpayer_name=taxpayer_name,
            calculation_revision_id=revision.calculation_revision_id,
            calculation_revision_state=revision.state,
            work_unit_id=work_unit.work_unit_id,
            verification_report_id=verification_report_id,
            verification_outcome=verification_outcome,
            filing_record_id=filing_record_id,
            registry_snapshot_ref=revision.registry_snapshot_ref,
            authority_logical_generation=authority_logical_generation,
            ledger_filing_snapshot_fingerprint=None if snapshot is None else snapshot.snapshot_fingerprint,
            software_identity_grade=software_identity_grade,
            report_language=report_language,
            exported_at=exported_at,
            row_count=len(rows),
            local_calculation_notice=local_calculation_report_notice(report_language),
        ),
        rows=rows,
    )


__all__ = [
    "CALCULATION_REPORT_CONTENT_VERSION",
    "CALCULATION_REPORT_NOTICE_LOCALE_KEY",
    "CalculationReportNoticeUnavailableError",
    "CalculationReportRowRole",
    "CalculationReportValueState",
    "ModeloCalculationReport",
    "ModeloCalculationReportHeader",
    "ModeloCalculationReportRow",
    "ModeloCalculationReportSourceProvenance",
    "build_modelo_calculation_report",
    "calculation_report_row_role",
    "local_calculation_report_notice",
]
