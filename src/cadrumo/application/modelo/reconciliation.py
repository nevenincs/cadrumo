"""Modelo reconciliation: compare work-unit state and computed result against evidence.

``prepare_modelo_reconcile`` accepts a modelo work unit and either an AEAT justificante
PDF or a filed declaración PDF, then produces a :class:`ModeloReconciliationReport`.

For a justificante, the report records whether the work unit's modelo, period,
``ejercicio``, and active-profile tax id match the receipt, AND — where the
revision declares ``reconciliation_total_casilla_ids`` and a persisted
calculation revision exists — whether the receipt's printed total equals the
canonical computed result casilla
(``aeat-calculation-aggregation``). A filed-amount divergence
surfaces as a typed ``total`` diff carrying the reconciling expectation's legal
grounding; where the total could not be reconciled (no map, no revision, no
printed total) a ``totals_not_reconciled`` advisory discloses it so an
identity-only ``matches`` is never a silent false green.

For a filed declaración, the same header comparison runs, and — for the
modelos enrolled in :data:`forms_for_role(_DECLARATION_RECONCILE_ROLE)` — every
casilla the registry's verification policy reconciles is compared, one by one,
against the persisted revision's ``casilla_values`` via
:func:`application.modelo.reconcile_casilla.detect_casilla_divergences`.
A divergence surfaces as a typed ``casilla`` diff
(:class:`ModeloReconciliationDiffKind.CASILLA`). A modelo not yet enrolled in
casilla-level declaration reconcile is refused with
:class:`ReconciliationDeclaracionSourceUnsupportedError` rather than silently
degrading to header-only comparison.

The path-based service is local-only: it never contacts AEAT and never invokes
``require_live_read`` — the computed result is read from the already-persisted
:class:`~CalculationRevision`, never a fresh calculation.
Authenticated live pulls use ``prepare_modelo_reconcile_bytes`` after storing captured
justificante bytes in secure storage.

Both paths persist their outcome twice over, in ONE unit of work: a
:class:`ModeloReconciliationRecord` carrying the grounded diffs and the
advisories into the encrypted reconciliation record store selected by the
bound :class:`ModeloReconciliationPersistencePort`, and a slim ``MODELO_RECONCILED``
:class:`~domain.buckets.event.BucketEvent` carrying the verdict and the divergence
count. The detail lives in the record because a bucket-event payload value is
capped at 500 characters and one grounded Modelo 100 casilla diff already
encodes to a median 303 — two divergences were unpersistable for 99.6% of that
modelo's casillas, and 175 overflowed on the first. ``reconcile list``
reports which fields diverged by reading the record store.

Core types:
:class:`~cadrumo.domain.calculations.registry.schema.RegistrySnapshot`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from ...core.casilla_value_kind import CasillaValueKind
from ...core.decimal.coercion import coerce_decimal_strict
from ...core.errors.hierarchy import CadrumoError
from ...core.identity.bucket import BucketId
from ...core.identity.digest import ContentDigest
from ...core.identity.hex_ids import CalculationRevisionId, WorkUnitId
from ...core.identity.tax_id import same_tax_identifier, tax_id_identity_token
from ...core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core.time.clock import now
from ...domain.calculations.registry.form_codes import forms_for_role
from ...domain.calculations.registry.schema_references import RegistrySnapshotRef
from ...domain.filing.reconciliation.errors import ReconciliationDeclaracionParseError
from ...domain.justificante.errors import JustificanteParseError
from ...domain.modelos.filing_text import ModeloActorLabel
from .action_errors import CalculationRevisionNotFoundError, WorkUnitNotFoundError
from .calculation_repository import calculation_revision_catalogue_repository
from .calculation_revision_gate import require_calculation_revision_coordinates_current
from .reconciliation_comparison import (
    ReconciliationDeclaracionSourceUnsupportedError,
    reconcile_casilla_values,
    reconcile_declaracion_casillas,
    reconcile_receipt_totals,
)
from .reconciliation_evidence_kind import ModeloReconciliationEvidenceKind
from .reconciliation_parsing import (
    ReconciliationDeclaracionObservation,
    reconciliation_evidence_parser,
)
from .reconciliation_records import (
    ModeloReconciliationAdvisory,
    ModeloReconciliationDiff,
    ModeloReconciliationDiffKind,
    ModeloReconciliationRecord,
    ModeloReconciliationVerdict,
    modelo_reconciliation_persistence,
)
from .work_addressing import ModeloWorkUnitNotFoundError
from .work_selection import (
    ModeloWorkSelectorRequest,
    ModeloWorkSelectorState,
    select_modelo_work_resolution,
)
from .work_unit_repository import work_unit_catalogue_repository

#: Width of a bucket-event payload value. Mirrors the constraint declared on the
#: payload-value alias in the buckets domain, which is module-private there and
#: so cannot be imported across the package boundary. The duplication is held
#: honest by behaviour rather than by the literal: the reconcile tests construct
#: a real ``BucketEvent``, so a narrowed cap fails them here.
_MAX_PAYLOAD_VALUE_LENGTH = 500

#: Marks a shortened reference so it cannot be misread as a complete one.
_REFERENCE_ELISION = "..."

if TYPE_CHECKING:
    from ...core.period import Period
    from ...domain.buckets.event import BucketEvent
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation
    from ...domain.justificante.schema import Justificante
    from ...domain.modelos.calculation_revision import CalculationRevision
    from ...domain.modelos.work_unit import WorkUnit, WorkUnitCatalogue
    from ..live.filed_observation_ports import FiledObservationProtocol

_DECLARATION_RECONCILE_ROLE = "filed_declaration_reconciliation.modelos"
"""Modelos enrolled in casilla-level filed-declaration reconciliation.

A modelo not in this set still accepts
:attr:`ModeloReconciliationEvidenceKind.DECLARATION` at the command contract
level but is refused with
:class:`ReconciliationDeclaracionSourceUnsupportedError` — the enrolled set
grows one modelo at a time as each modelo's ``declaracion_pdf`` extraction
profile is confirmed to line up with its registry casilla ids one-to-one (the
same casilla-id vocabulary its
:meth:`~domain.calculations.registry.schema.verification_policy`
reconciles, whether that vocabulary is the printed AEAT box number or an
engine-internal compound id such as ``iva.resultado``).

Modelo 100 (Renta) joins the same post-filing reconcile path for the current
2024/2025 annual declaration profiles, including credit casilla ``0604``.
Modelo 130 and 111 target printed numeric ids directly; Modelo 303 and 390 mix
printed ids with the compound ``iva.*`` ids already extracted and reconciled
pre-filing; Modelo 190 targets the compound ``decl.*`` summary ids. The same
casilla-id vocabulary carries through to the after-filing reconcile here.
A modelo outside this set is refused rather than silently degraded. **This
docstring deliberately no longer enumerates why each one is out**, because that
enumeration has now drifted twice: it first claimed Modelo 202 had no
``declaracion_pdf`` surface (it has one, of four ``bbox_anchored`` targets), and
the correction then claimed its casilla-id alignment was unconfirmed (it is
confirmed complete). A per-modelo reason recorded here is a copy of a fact that
lives in the registry and in the evidence corpus, and it goes stale whenever
either moves, without anything failing.

The two real gates are worth stating once, generically. A modelo needs its
extraction profile's casilla ids to line up with the vocabulary its
``verification_policy`` reconciles, and it needs a real or facsimile render
verified through the real-render gate — registry readiness alone is not
sufficient, because a profile can satisfy it completely and still read almost
nothing off an actual document. To find out where a given modelo stands, read
the registry and the fixture provenance rather than this paragraph.

Real-PDF ``bbox_anchored`` extraction quality for the enrolled modelos remains
Tier-R and is tracked separately, blocked on #332-337.
"""


def _active_reconciliation_catalogue() -> tuple[WorkUnitCatalogue, str]:
    """Capture the active profile's work catalogue at the reconciliation boundary."""
    from ..workflow.persistence import workflow_state_repository

    bucket_id = workflow_state_repository().load().active_profile_bucket_id()
    if bucket_id is None:
        raise WorkUnitNotFoundError(
            translated_message="application.modelo.errors.reconcile_no_active_bucket",
        )
    return work_unit_catalogue_repository(bucket_id=bucket_id).load(), bucket_id


def _resolve_work_unit_for_reconciliation(
    *,
    work_unit_id: WorkUnitId,
    catalogue: WorkUnitCatalogue,
    bucket_id: str,
) -> WorkUnit:
    """Translate canonical selector absence to reconciliation's typed refusal."""
    request = ModeloWorkSelectorRequest(work_unit_id=work_unit_id)
    try:
        resolution = select_modelo_work_resolution(request, catalogue=catalogue, bucket_id=bucket_id)
    except ModeloWorkUnitNotFoundError as exc:
        raise WorkUnitNotFoundError(
            translated_message="application.modelo.errors.work_unit_not_found",
            context={"work_unit_id": work_unit_id},
        ) from exc
    if resolution.state is ModeloWorkSelectorState.ABSENT or resolution.work_unit is None:
        raise WorkUnitNotFoundError(
            translated_message="application.modelo.errors.work_unit_not_found",
            context={"work_unit_id": work_unit_id},
        )
    return resolution.work_unit


class ModeloReconciliationCommand(BaseModel):
    """Strict input contract for ``prepare_modelo_reconcile``.

    ``source_path`` points to the operator-supplied evidence file and
    ``source_kind`` records how that file must be parsed. Justificante PDFs are
    supported for every modelo; declaration PDFs are supported (casilla-level)
    only for modelos under :data:`_DECLARATION_RECONCILE_ROLE` — an
    unenrolled modelo is refused before parsing.
    """

    model_config = _STRICT_FROZEN

    work_unit_id: WorkUnitId
    calculation_revision_id: CalculationRevisionId | None = None
    source_kind: ModeloReconciliationEvidenceKind
    source_path: Path
    actor: ModeloActorLabel = "operator"


class ModeloReconciliationBytesCommand(BaseModel):
    """Strict input contract for reconciling secure-storage justificante bytes.

    Used by authenticated live pulls after the captured justificante has
    already been persisted in secure storage. The raw bytes remain in memory;
    ``source_ref`` is the non-file secure-storage reference recorded in the
    reconciliation event.
    """

    model_config = _STRICT_FROZEN

    work_unit_id: WorkUnitId
    calculation_revision_id: CalculationRevisionId | None = None
    source_kind: ModeloReconciliationEvidenceKind
    source_bytes: bytes = Field(min_length=1)
    # Bounded at the bucket-event payload width, not above it. This reference is
    # an app-generated secure-storage handle rather than an operator path, so a
    # value past the cap is an internal defect and belongs refused at validation
    # where it names the field -- not shortened, which would hide it. The
    # operator-supplied filesystem path on the sibling command has no bound of
    # its own and is instead shortened at construction.
    source_ref: str = Field(min_length=1, max_length=_MAX_PAYLOAD_VALUE_LENGTH)
    actor: ModeloActorLabel = "operator"


class ModeloReconciliationReport(BaseModel):
    """Outcome of ``prepare_modelo_reconcile``.

    The verdict summarises the comparison at the work-unit level. The diff list
    enumerates the disagreements — header-field (modelo, period, ``ejercicio``,
    tax id), the filed justificante ``total`` against the computed result
    casilla where reconciled, and (for a declaración source on an enrolled
    modelo) each per-``casilla`` divergence; empty on ``matches``. The advisory
    list carries non-blocking disclosures (a total or casilla set that could
    not be reconciled, an identity anchor that could not be verified);
    advisories never flip the verdict.
    """

    model_config = _STRICT_FROZEN

    work_unit_id: WorkUnitId
    calculation_revision_id: CalculationRevisionId | None = None
    bucket_id: BucketId
    source_kind: ModeloReconciliationEvidenceKind
    source_path: str
    source_pdf_sha256: ContentDigest | None = None
    verdict: ModeloReconciliationVerdict
    diffs: tuple[ModeloReconciliationDiff, ...] = ()
    advisories: tuple[ModeloReconciliationAdvisory, ...] = ()
    reconciled_at: datetime
    narrative: str = ""
    registry_snapshot_ref: RegistrySnapshotRef | None = None


@dataclass(frozen=True, slots=True)
class PreparedModeloReconciliation:
    """Compared evidence awaiting its single atomic record/event write."""

    report: ModeloReconciliationReport
    record: ModeloReconciliationRecord
    event: BucketEvent

    def persist(self) -> ModeloReconciliationReport:
        """Commit the prepared record and event in one persistence unit."""
        modelo_reconciliation_persistence().persist_with_event(self.record, self.event)
        return self.report


class ReconciliationEvidenceInvalidError(CadrumoError):
    """Raised when the supplied external evidence cannot be parsed.

    Raised for malformed justificantes. The CLI surfaces it as a refusal
    with the canonical recovery hint; downstream consumers branch on it
    without string-matching the message.
    """


def _evidence_invalid_refusal(
    exc: BaseException,
    *,
    source_ref: str,
) -> ReconciliationEvidenceInvalidError:
    """Translate a justificante parse failure into a clean typed refusal.

    The parser raises with a redacted, parser-internal message (e.g.
    ``"pdfplumber failed to open <input-pdf>: PdfminerException"``). Surfacing
    that verbatim leaks the parser backend's exception class to the operator and
    omits the documented "is this the right document?" guidance. This helper
    drops the raw cause into structured ``context`` for diagnostics and routes
    the operator-facing text through the
    ``errors.refused.reconciliation_evidence_invalid`` locale key, which carries
    the documented ``evidence_invalid`` guidance. The exception ``__cause__``
    chain preserves the original parse error for logs.
    """
    return ReconciliationEvidenceInvalidError(
        f"reconciliation evidence {source_ref!r} could not be parsed",
        translated_message="errors.refused.reconciliation_evidence_invalid",
        context={"parse_failure": type(exc).__name__, "source_ref": source_ref},
    )


def _require_declaration_enrolled_modelo(
    work_unit_id: WorkUnitId,
    *,
    catalogue: WorkUnitCatalogue,
    bucket_id: str,
) -> WorkUnit:
    """Refuse an unenrolled modelo before spending effort parsing its PDF.

    Declaración parsing (template detection, registry-profile extraction) is
    real work; a modelo outside :data:`_DECLARATION_RECONCILE_ROLE`
    is refused immediately from the work unit's own declared modelo, before any
    file is opened, rather than only after a parse attempt happens to fail for
    an unrelated reason.

    Returns the loaded :class:`~WorkUnit` so the caller can
    reuse its already-known modelo/filing_year/period as evidence-parser
    overrides, rather than reloading the catalogue a second time.
    """
    work_unit = _resolve_work_unit_for_reconciliation(
        work_unit_id=work_unit_id,
        catalogue=catalogue,
        bucket_id=bucket_id,
    )
    if str(work_unit.modelo) not in forms_for_role(_DECLARATION_RECONCILE_ROLE):
        raise ReconciliationDeclaracionSourceUnsupportedError(
            translated_message="application.modelo.errors.reconcile_declaration_unsupported",
            context={
                "modelo": str(work_unit.modelo),
                "enrolled_modelos": ",".join(sorted(forms_for_role(_DECLARATION_RECONCILE_ROLE))),
            },
        )
    return work_unit


def prepare_modelo_reconcile(
    command: ModeloReconciliationCommand,
    *,
    operation: PinnedAuthorityOperation,
) -> PreparedModeloReconciliation:
    """Parse and compare a local PDF without writing the reconciliation.

    Local-only: never contacts AEAT and never invokes ``require_live_read``.

    For a justificante, compares the neutral observation returned by the bound
    :class:`ReconciliationEvidenceParserPort`. The receipt totals ARE reconciled
    against the persisted revision's computed result where the revision declares
    ``reconciliation_total_casilla_ids``.

    For a declaración, consumes the parser port's structural observation and,
    for modelos enrolled in :data:`forms_for_role(_DECLARATION_RECONCILE_ROLE)`,
    compares every registry-reconciled casilla against the persisted revision's
    ``casilla_values``, surfacing each divergence as a typed ``casilla`` diff. A
    modelo outside that set raises
    :class:`ReconciliationDeclaracionSourceUnsupportedError`.

    Persisting the returned :class:`PreparedModeloReconciliation` emits
    ``MODELO_RECONCILED`` into the bucket-event-history catalogue, with the
    verdict in the event payload so downstream auditors can replay the
    reconciliation timeline without re-parsing the evidence.
    """
    if command.source_kind is ModeloReconciliationEvidenceKind.DECLARATION:
        catalogue, bucket_id = _active_reconciliation_catalogue()
        work_unit = _require_declaration_enrolled_modelo(
            command.work_unit_id,
            catalogue=catalogue,
            bucket_id=bucket_id,
        )

        try:
            # The addressed work unit already knows its own modelo/año/period;
            # forwarding them as overrides lets a declaración PDF that lacks a
            # detectable "Ejercicio: YYYY" header stamp still parse, instead
            # of failing template detection outright. A PDF that genuinely
            # belongs to a different modelo or ejercicio still raises here
            # (`_resolve_template` reconciles a successful detection against
            # the override and raises on conflict) -- the wrong-PDF-mismatch
            # detection this reconcile depends on is unchanged.
            declaracion = reconciliation_evidence_parser().parse_declaracion(
                command.source_path,
                modelo=str(work_unit.modelo),
                filing_year=work_unit.filing_year,
                period=work_unit.period.registry_token,
            )
        except ReconciliationDeclaracionParseError as exc:
            raise _evidence_invalid_refusal(exc, source_ref=str(command.source_path)) from exc
        return prepare_parsed_declaracion(
            work_unit=work_unit,
            source_kind=command.source_kind,
            source_ref=str(command.source_path),
            actor=command.actor,
            calculation_revision_id=command.calculation_revision_id,
            declaracion=declaracion,
            operation=operation,
        )

    try:
        justificante = reconciliation_evidence_parser().parse_justificante(command.source_path)
    except JustificanteParseError as exc:
        raise _evidence_invalid_refusal(exc, source_ref=str(command.source_path)) from exc
    catalogue, bucket_id = _active_reconciliation_catalogue()
    return prepare_parsed_justificante(
        work_unit=_resolve_work_unit_for_reconciliation(
            work_unit_id=command.work_unit_id,
            catalogue=catalogue,
            bucket_id=bucket_id,
        ),
        source_kind=command.source_kind,
        source_ref=str(command.source_path),
        actor=command.actor,
        calculation_revision_id=command.calculation_revision_id,
        justificante=justificante,
        operation=operation,
    )


def prepare_modelo_reconcile_bytes(
    command: ModeloReconciliationBytesCommand,
    *,
    operation: PinnedAuthorityOperation,
) -> PreparedModeloReconciliation:
    """Parse and compare secure-storage bytes without writing a record."""
    if command.source_kind is ModeloReconciliationEvidenceKind.DECLARATION:
        raise ReconciliationDeclaracionSourceUnsupportedError(
            translated_message="application.modelo.errors.reconcile_declaration_unsupported",
        )

    try:
        justificante = reconciliation_evidence_parser().parse_justificante_bytes(command.source_bytes)
    except JustificanteParseError as exc:
        raise _evidence_invalid_refusal(exc, source_ref=command.source_ref) from exc
    catalogue, bucket_id = _active_reconciliation_catalogue()
    return prepare_parsed_justificante(
        work_unit=_resolve_work_unit_for_reconciliation(
            work_unit_id=command.work_unit_id,
            catalogue=catalogue,
            bucket_id=bucket_id,
        ),
        source_kind=command.source_kind,
        source_ref=command.source_ref,
        actor=command.actor,
        calculation_revision_id=command.calculation_revision_id,
        justificante=justificante,
        operation=operation,
    )


def prepare_parsed_justificante(
    *,
    work_unit: WorkUnit,
    source_kind: ModeloReconciliationEvidenceKind,
    source_ref: str,
    actor: str,
    justificante: Justificante,
    operation: PinnedAuthorityOperation,
    calculation_revision_id: CalculationRevisionId | None = None,
) -> PreparedModeloReconciliation:
    """Compare parsed justificante evidence without writing it."""
    active_bucket_id = work_unit.bucket_id

    diffs: list[ModeloReconciliationDiff] = []
    advisories: list[ModeloReconciliationAdvisory] = []
    diffs.extend(
        _identity_header_diffs(
            work_unit=work_unit,
            active_bucket_id=active_bucket_id,
            evidence_modelo=justificante.modelo,
            evidence_ejercicio=justificante.ejercicio,
            evidence_period=justificante.period,
            evidence_tax_id=justificante.tax_id,
            advisories=advisories,
        ),
    )

    filed_revision = _resolve_reconciliation_revision(
        work_unit, operation=operation, calculation_revision_id=calculation_revision_id
    )
    total_diffs, total_advisories = reconcile_receipt_totals(
        work_unit=work_unit,
        justificante=justificante,
        revision=filed_revision,
        operation=operation,
    )
    diffs.extend(total_diffs)
    advisories.extend(total_advisories)

    return _prepare_reconciliation(
        work_unit=work_unit,
        source_kind=source_kind,
        source_ref=source_ref,
        actor=actor,
        diffs=diffs,
        advisories=advisories,
        calculation_revision_id=filed_revision.calculation_revision_id if filed_revision else None,
        narrative_subject=f"modelo {justificante.modelo} for ejercicio {justificante.ejercicio or '?'}",
        source_pdf_sha256=justificante.source_pdf_sha256,
    )


def prepare_parsed_declaracion(
    *,
    work_unit: WorkUnit,
    source_kind: ModeloReconciliationEvidenceKind,
    source_ref: str,
    actor: str,
    declaracion: ReconciliationDeclaracionObservation,
    operation: PinnedAuthorityOperation,
    calculation_revision_id: CalculationRevisionId | None = None,
) -> PreparedModeloReconciliation:
    """Compare parsed declaration evidence without writing it."""
    active_bucket_id = work_unit.bucket_id
    if str(work_unit.modelo) not in forms_for_role(_DECLARATION_RECONCILE_ROLE):
        raise ReconciliationDeclaracionSourceUnsupportedError(
            translated_message="application.modelo.errors.reconcile_declaration_unsupported",
            context={
                "modelo": str(work_unit.modelo),
                "enrolled_modelos": ",".join(sorted(forms_for_role(_DECLARATION_RECONCILE_ROLE))),
            },
        )

    diffs: list[ModeloReconciliationDiff] = []
    advisories: list[ModeloReconciliationAdvisory] = []
    if declaracion.extraction_profile_provisional:
        advisories.append(
            _extraction_profile_provisional_advisory(
                modelo=str(work_unit.modelo),
                extraction_profile_id=declaracion.extraction_profile_id,
            ),
        )
    diffs.extend(
        _identity_header_diffs(
            work_unit=work_unit,
            active_bucket_id=active_bucket_id,
            evidence_modelo=declaracion.modelo,
            evidence_ejercicio=declaracion.ejercicio,
            evidence_period=declaracion.period,
            evidence_tax_id=declaracion.tax_id,
            advisories=advisories,
        ),
    )

    filed_revision = _resolve_reconciliation_revision(
        work_unit, operation=operation, calculation_revision_id=calculation_revision_id
    )
    casilla_diffs, casilla_advisories = reconcile_declaracion_casillas(
        revision=filed_revision,
        work_unit=work_unit,
        declaracion=declaracion,
        operation=operation,
    )
    diffs.extend(casilla_diffs)
    advisories.extend(casilla_advisories)

    return _prepare_reconciliation(
        work_unit=work_unit,
        source_kind=source_kind,
        source_ref=source_ref,
        actor=actor,
        diffs=diffs,
        advisories=advisories,
        calculation_revision_id=filed_revision.calculation_revision_id if filed_revision else None,
        narrative_subject=f"modelo {declaracion.modelo} for ejercicio {declaracion.ejercicio}",
        source_pdf_sha256=declaracion.source_pdf_sha256,
    )


def prepare_filed_observation_reconciliation(
    *,
    work_unit: WorkUnit,
    observation: FiledObservationProtocol,
    source_ref: str,
    actor: str,
    operation: PinnedAuthorityOperation,
    calculation_revision_id: CalculationRevisionId | None = None,
) -> PreparedModeloReconciliation:
    """Compare a persisted authenticated register manifest against saved calculation values."""
    from ..calculations.revision_carry_gate import revision_carry_outcome

    if revision_carry_outcome(observation.registry_snapshot_ref, operation=operation).refused:
        raise ReconciliationEvidenceInvalidError("captured declaration registry coordinates are no longer current")
    if not observation.casillas or not observation.authenticated_identity.strip():
        raise ReconciliationEvidenceInvalidError("captured declaration has no comparable fields or taxpayer identity")
    advisories: list[ModeloReconciliationAdvisory] = []
    if observation.metadata.get("declaration_pdf_extraction_profile_provisional") == "true":
        advisories.append(
            ModeloReconciliationAdvisory(
                code="extraction_profile_provisional",
                message=(
                    "The captured declaration used an unconfirmed PDF extraction profile; "
                    "verify its fields against the source document."
                ),
                context={"modelo": observation.modelo},
            )
        )
    diffs = _identity_header_diffs(
        work_unit=work_unit,
        active_bucket_id=work_unit.bucket_id,
        evidence_modelo=observation.modelo,
        evidence_ejercicio=str(observation.ejercicio),
        evidence_period=observation.period,
        evidence_tax_id=observation.authenticated_identity,
        advisories=advisories,
    )
    values = {
        row.casilla_id: coerce_decimal_strict(row.value)
        for row in observation.casillas
        if row.value_kind is CasillaValueKind.NUMERIC
    }
    if not values:
        raise ReconciliationEvidenceInvalidError("captured declaration has no numeric comparison fields")
    filed_revision = _resolve_reconciliation_revision(
        work_unit, operation=operation, calculation_revision_id=calculation_revision_id
    )
    casilla_diffs, comparison_advisories = reconcile_casilla_values(
        revision=filed_revision,
        work_unit=work_unit,
        filed_values=values,
        operation=operation,
    )
    diffs.extend(casilla_diffs)
    advisories.extend(comparison_advisories)
    return _prepare_reconciliation(
        work_unit=work_unit,
        source_kind=ModeloReconciliationEvidenceKind.DECLARATION,
        source_ref=source_ref,
        actor=actor,
        diffs=diffs,
        advisories=advisories,
        calculation_revision_id=filed_revision.calculation_revision_id if filed_revision else None,
        narrative_subject=f"captured modelo {observation.modelo} for ejercicio {observation.ejercicio}",
        source_pdf_sha256=None,
    )


def _identity_header_diffs(
    *,
    work_unit: WorkUnit,
    active_bucket_id: str,
    evidence_modelo: str,
    evidence_ejercicio: str | None,
    evidence_period: Period,
    evidence_tax_id: str,
    advisories: list[ModeloReconciliationAdvisory],
) -> list[ModeloReconciliationDiff]:
    """Return the shared modelo/ejercicio/period/tax_id header diffs.

    Shared by the justificante and declaración reconcile paths: both evidence
    kinds carry the same four identity anchors, compared the same way against
    the work unit and the active profile. Missing anchors (``ejercicio`` absent
    on the evidence, no ``tax_id`` on the active profile) surface a
    non-blocking advisory rather than a silent skip
    (``no-silent-under-declaration``).
    """
    diffs: list[ModeloReconciliationDiff] = []
    if work_unit.modelo != evidence_modelo:
        diffs.append(
            ModeloReconciliationDiff(
                field_name="modelo",
                work_unit_value=work_unit.modelo,
                evidence_value=evidence_modelo,
                kind="modelo_mismatch",
                diff_kind=ModeloReconciliationDiffKind.HEADER_FIELD,
            ),
        )
    if evidence_ejercicio is None:
        advisories.append(_identity_anchor_unverified("ejercicio", modelo=str(work_unit.modelo)))
    elif str(work_unit.filing_year) != evidence_ejercicio:
        diffs.append(
            ModeloReconciliationDiff(
                field_name="ejercicio",
                work_unit_value=str(work_unit.filing_year),
                evidence_value=evidence_ejercicio,
                kind="ejercicio_mismatch",
                diff_kind=ModeloReconciliationDiffKind.HEADER_FIELD,
            ),
        )
    if work_unit.period != evidence_period:
        diffs.append(
            ModeloReconciliationDiff(
                field_name="period",
                work_unit_value=work_unit.period.registry_token,
                evidence_value=evidence_period.registry_token,
                kind="period_mismatch",
                diff_kind=ModeloReconciliationDiffKind.HEADER_FIELD,
            ),
        )
    profile_tax_id = _active_profile_tax_id(active_bucket_id)
    if not profile_tax_id:
        advisories.append(_identity_anchor_unverified("tax_id", modelo=str(work_unit.modelo)))
    elif not same_tax_identifier(profile_tax_id, evidence_tax_id):
        diffs.append(
            ModeloReconciliationDiff(
                field_name="tax_id",
                work_unit_value=profile_tax_id,
                evidence_value=evidence_tax_id,
                kind="tax_id_mismatch",
                diff_kind=ModeloReconciliationDiffKind.HEADER_FIELD,
            ),
        )
    return diffs


def _prepare_reconciliation(
    *,
    work_unit: WorkUnit,
    source_kind: ModeloReconciliationEvidenceKind,
    source_ref: str,
    actor: str,
    diffs: list[ModeloReconciliationDiff],
    advisories: list[ModeloReconciliationAdvisory],
    narrative_subject: str,
    calculation_revision_id: CalculationRevisionId | None,
    source_pdf_sha256: str | None,
) -> PreparedModeloReconciliation:
    """Build the report, record and event for one later atomic write.

    Shared tail of every reconcile path (justificante or declaración): both
    compute their own ``diffs`` / ``advisories`` lists upstream, then converge
    on the same verdict derivation and report assembly. Preparation performs
    no write; the caller later persists the returned pair.

    The :class:`ModeloReconciliationRecord` and the append-only
    ``MODELO_RECONCILED`` :class:`~domain.buckets.event.BucketEvent` land in ONE
    persistence unit of work through the bound
    :class:`ModeloReconciliationPersistencePort` — the same co-emit discipline
    :func:`~application.modelo.filing_revision_persistence.persist_filed_revision`
    uses to keep the participation index from drifting from the filing
    catalogue. Writing them separately would let a crash between the two leave
    an event log claiming a reconciliation whose detail was never stored, or a
    record with no event.
    """
    from ...domain.buckets.event import BucketEvent, BucketEventObjectType, BucketEventType, derive_bucket_event_id

    verdict = ModeloReconciliationVerdict.MATCHES if not diffs else ModeloReconciliationVerdict.MISMATCHES
    narrative = (
        f"reconciled {narrative_subject} against work unit {work_unit.work_unit_id}; "
        f"verdict={verdict.value}; diffs={len(diffs)}; advisories={len(advisories)}"
    )
    reconciled_at = now()
    snapshot_ref = RegistrySnapshotRef(
        modelo=work_unit.modelo,
        revision_id=work_unit.revision_id,
        modelo_year=work_unit.filing_year,
        period=work_unit.period.registry_token,
    )
    report = ModeloReconciliationReport(
        calculation_revision_id=calculation_revision_id,
        registry_snapshot_ref=snapshot_ref,
        work_unit_id=work_unit.work_unit_id,
        bucket_id=work_unit.bucket_id,
        source_kind=source_kind,
        source_path=source_ref,
        source_pdf_sha256=source_pdf_sha256,
        verdict=verdict,
        diffs=tuple(diffs),
        advisories=tuple(advisories),
        reconciled_at=reconciled_at,
        narrative=narrative,
    )

    # The event carries the verdict and the divergence COUNT only. The
    # per-divergence detail lives in the reconciliation record below: a payload
    # value is capped at 500 characters, and one grounded Modelo 100 casilla
    # diff already encodes to a median 303, so joining them here raised a
    # ValidationError before anything was written at all.
    event_payload = {
        "work_unit_id": work_unit.work_unit_id,
        "source_kind": source_kind.value,
        "source_path": _bounded_payload_reference(source_ref),
        "verdict": verdict.value,
        "diffs": str(len(diffs)),
        "advisories": str(len(advisories)),
        "calculation_revision_id": calculation_revision_id or "unknown",
    }
    actor = actor.strip()
    event_id = derive_bucket_event_id(
        bucket_id=work_unit.bucket_id,
        event_type=BucketEventType.MODELO_RECONCILED,
        occurred_at=reconciled_at,
        actor=actor,
        object_type=BucketEventObjectType.WORK_UNIT,
        object_id=work_unit.work_unit_id,
        payload=event_payload,
    )
    event = BucketEvent(
        event_id=event_id,
        bucket_id=work_unit.bucket_id,
        event_type=BucketEventType.MODELO_RECONCILED,
        occurred_at=reconciled_at,
        actor=actor,
        object_type=BucketEventObjectType.WORK_UNIT,
        object_id=work_unit.work_unit_id,
        payload_version=1,
        payload=event_payload,
    )
    record = ModeloReconciliationRecord(
        bucket_event_id=event_id,
        calculation_revision_id=calculation_revision_id,
        bucket_id=work_unit.bucket_id,
        work_unit_id=work_unit.work_unit_id,
        registry_snapshot_ref=RegistrySnapshotRef(
            modelo=work_unit.modelo,
            revision_id=work_unit.revision_id,
            modelo_year=work_unit.filing_year,
            period=work_unit.period.registry_token,
        ),
        source_kind=source_kind,
        source_ref=source_ref,
        source_pdf_sha256=source_pdf_sha256,
        verdict=verdict,
        diffs=tuple(diffs),
        advisories=tuple(advisories),
        actor=actor,
        reconciled_at=reconciled_at,
    )
    return PreparedModeloReconciliation(report=report, record=record, event=event)


def _extraction_profile_provisional_advisory(
    *,
    modelo: str,
    extraction_profile_id: str,
) -> ModeloReconciliationAdvisory:
    """Advisory: the declaración extraction profile is unconfirmed against a real specimen.

    A ``declaracion_pdf`` registry profile with ``provisional_pending_specimen =
    true`` has its ``bbox_anchored`` anchor positions guessed from the bundled
    AEAT-published Diseño de Registro rather than confirmed against a real
    filed PDF (see ``aeat-quality-gates`` and the profile's
    ``verification_source``). Extraction still fails hard on a real PDF whose
    layout diverges enough that the anchor pattern matches nowhere on the page
    (``no-silent-under-declaration`` is upheld by the parser's coverage gate),
    but a real PDF whose layout coincidentally matches the guessed anchor
    position at the wrong casilla would extract a value with no signal that the
    layout itself is unconfirmed. This advisory discloses that risk on every
    reconcile against a provisional profile so the operator manually verifies
    the extracted values against the printed PDF rather than trusting them as
    confirmed.
    """
    return ModeloReconciliationAdvisory(
        code="extraction_profile_provisional",
        message=(
            f"modelo {modelo} declaración extraction profile {extraction_profile_id!r} "
            "has no real AEAT specimen confirming its printed layout "
            "(provisional_pending_specimen=true); manually verify the extracted "
            "casilla values against the printed PDF before relying on them"
        ),
        context={"modelo": modelo, "extraction_profile_id": extraction_profile_id},
    )


def _identity_anchor_unverified(anchor: str, *, modelo: str) -> ModeloReconciliationAdvisory:
    """Advisory: a receipt / profile identity anchor could not be compared.

    A receipt that omits ``ejercicio``, or an active profile with no ``tax_id``,
    used to drop that anchor from the compare silently and could still reach
    ``matches``. This advisory discloses the skipped anchor so an identity-only
    ``matches`` is never a silent pass on a missing anchor
    (``no-silent-under-declaration``).
    """
    return ModeloReconciliationAdvisory(
        code="identity_anchor_unverified",
        message=(
            f"identity anchor {anchor!r} could not be verified for modelo {modelo}: "
            "the receipt or the active profile did not supply it"
        ),
        context={"anchor": anchor, "modelo": modelo},
    )


def _resolve_reconciliation_revision(
    work_unit: WorkUnit,
    *,
    operation: PinnedAuthorityOperation,
    calculation_revision_id: CalculationRevisionId | None,
) -> CalculationRevision | None:
    """Bind the saved operand once, preserving the default filed-state priority."""
    if calculation_revision_id is None:
        return _filed_revision_for_work_unit(work_unit, operation=operation)
    catalogue = calculation_revision_catalogue_repository(
        bucket_id=work_unit.bucket_id,
        operation=operation,
    ).load(operation=operation)
    revision = catalogue.get(calculation_revision_id)
    expected_ref = RegistrySnapshotRef(
        modelo=work_unit.modelo,
        revision_id=work_unit.revision_id,
        modelo_year=work_unit.filing_year,
        period=work_unit.period.registry_token,
    )
    if (
        revision is None
        or revision.work_unit_id != work_unit.work_unit_id
        or revision.registry_snapshot_ref != expected_ref
    ):
        raise CalculationRevisionNotFoundError(
            "The requested calculation revision does not belong to this work unit.",
            context={"calculation_revision_id": calculation_revision_id, "work_unit_id": work_unit.work_unit_id},
        )
    require_calculation_revision_coordinates_current(revision, operation=operation)
    return revision


def _filed_revision_for_work_unit(
    work_unit: WorkUnit,
    *,
    operation: PinnedAuthorityOperation,
) -> CalculationRevision | None:
    """Return the persisted filed / verified revision selected for ``work_unit``.

    Shared read path for both the receipt-total compare
    (:func:`reconcile_receipt_totals`) and the casilla-level declaración compare
    (:func:`~cadrumo.application.modelo.reconciliation_comparison.reconcile_declaracion_casillas`):
    both must read the exact same persisted revision so a total reconcile and a casilla reconcile can never
    silently disagree about which revision represents "what was filed."
    """
    catalogue = calculation_revision_catalogue_repository(bucket_id=work_unit.bucket_id, operation=operation).load(
        operation=operation
    )
    revision = _select_filed_revision(catalogue.for_work_unit(work_unit.work_unit_id))
    if revision is not None:
        require_calculation_revision_coordinates_current(revision, operation=operation)
    return revision


def _select_filed_revision(revisions: tuple[CalculationRevision, ...]) -> CalculationRevision | None:
    """Pick the revision that best represents what was filed.

    Prefers filed / verified states in priority order (``PRESENTADO`` >
    ``PRESENTADO_SUPERSEDIDO`` > ``VERIFICADO_COMPLETO``), then the most recent
    by ``updated_at``; falls back to the most recent revision of any state so a
    receipt can still be value-reconciled before the filing is recorded in-app.
    """
    from ...domain.modelos.calculation_revision import CalculationRevisionState

    if not revisions:
        return None
    priority = {
        CalculationRevisionState.PRESENTADO: 3,
        CalculationRevisionState.PRESENTADO_SUPERSEDIDO: 2,
        CalculationRevisionState.VERIFICADO_COMPLETO: 1,
    }
    return max(
        revisions,
        key=lambda rev: (priority.get(rev.state, 0), rev.updated_at),
    )


def _bounded_payload_reference(reference: str) -> str:
    """Shorten an evidence reference to fit one bucket-event payload value.

    An evidence reference reaches the payload from an operator-supplied
    filesystem path, which carries no length bound of its own, so a deep
    directory or a long filename would otherwise make the reconciliation
    unrecordable -- failing the whole verb on the length of a diagnostic
    breadcrumb.

    The tail is kept rather than the head because the filename identifies the
    artifact while the directory prefix rarely does, and the result is prefixed
    with an explicit elision marker so a shortened reference is self-evidently
    shortened. Truncating silently would leave a payload that looks like a
    complete path and is not.
    """
    if len(reference) <= _MAX_PAYLOAD_VALUE_LENGTH:
        return reference
    keep = _MAX_PAYLOAD_VALUE_LENGTH - len(_REFERENCE_ELISION)
    return _REFERENCE_ELISION + reference[-keep:]


def _active_profile_tax_id(bucket_id: str) -> str:
    from ...domain.calculations.registry.authority import bundled_indexed_authority
    from ..user_profile.profile_record_repository import ProfileRecordRepository
    from ..user_profile.projections import record_to_path_values, record_to_values

    with bundled_indexed_authority().operation() as operation:
        profile_decode_context = operation.profile_decode_context()
        repository = ProfileRecordRepository.for_current_session(
            bucket_id,
            profile_decode_context=profile_decode_context,
        )
        record = repository.load(bucket_id)
        path_values = record_to_path_values(record)
        profile_tax_id = _normalise_tax_id(path_values.get("identity.tax_id"))
        if profile_tax_id:
            return profile_tax_id
        selector_values = record_to_values(record, schema=profile_decode_context.schema)
        return _normalise_tax_id(selector_values.get("tax.id"))


def _normalise_tax_id(value: object) -> str:
    """Coerce an untyped profile value to the canonical storage-keying token.

    This helper owns only the ``object`` coercion that
    :func:`~core.identity.tax_id.tax_id_identity_token` deliberately does not accept;
    the normal form itself is the canonical one. Its result is a display and
    presence value, never a comparison key -- two identifiers are compared with
    :func:`~core.identity.tax_id.same_tax_identifier`, which strips separators so a
    printed ``B-1234567-4`` matches a stored ``B12345674``.
    """
    return tax_id_identity_token(str(value or ""))


__all__ = [
    "ModeloReconciliationAdvisory",
    "ModeloReconciliationBytesCommand",
    "ModeloReconciliationCommand",
    "ModeloReconciliationDiff",
    "ModeloReconciliationDiffKind",
    "ModeloReconciliationEvidenceKind",
    "ModeloReconciliationReport",
    "ModeloReconciliationVerdict",
    "ReconciliationEvidenceInvalidError",
]
