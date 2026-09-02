"""Modelo reconciliation: compare work-unit state and computed result against evidence.

``modelo_reconcile`` accepts a modelo work unit and either an AEAT justificante
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
modelos enrolled in :data:`_DECLARATION_CASILLA_RECONCILE_MODELOS` — every
casilla the registry's verification policy reconciles is compared, one by one,
against the persisted revision's ``casilla_values`` via
:func:`application.modelo._reconcile_casilla.detect_casilla_divergences`.
A divergence surfaces as a typed ``casilla`` diff
(:class:`ModeloReconciliationDiffKind.CASILLA`). A modelo not yet enrolled in
casilla-level declaration reconcile is refused with
:class:`ReconciliationDeclaracionSourceUnsupportedError` rather than silently
degrading to header-only comparison.

The path-based service is local-only: it never contacts AEAT and never invokes
``require_live_read`` — the computed result is read from the already-persisted
:class:`~CalculationRevision`, never a fresh calculation.
Authenticated live pulls use ``modelo_reconcile_bytes`` after storing captured
justificante bytes in secure storage.

Both paths persist their outcome twice over, in ONE unit of work: a
:class:`ModeloReconciliationRecord` carrying the grounded diffs and the
advisories into the encrypted reconciliation record store selected by the
bound :class:`ModeloReconciliationPersistencePort`, and a slim ``MODELO_RECONCILED``
:class:`~domain.buckets.BucketEvent` carrying the verdict and the divergence
count. The detail lives in the record because a bucket-event payload value is
capped at 500 characters and one grounded Modelo 100 casilla diff already
encodes to a median 303 — two divergences were unpersistable for 99.6% of that
modelo's casillas, and 175 overflowed on the first. ``reconcile list``
reports which fields diverged by reading the record store.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from ...core.errors.hierarchy import CadrumoError
from ...core.identity import BucketId, WorkUnitId, same_tax_identifier, tax_id_identity_token
from ...core.modelo import Modelo
from ...core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core.time.clock import now
from ...domain.filing.reconciliation.errors import ReconciliationDeclaracionParseError
from ...domain.justificante import JustificanteParseError
from ._reconcile_casilla import CasillaDivergence, CasillaDivergenceKind, detect_casilla_divergences
from .action_errors import WorkUnitNotFoundError
from .calculation_repository import calculation_revision_catalogue_repository
from .reconciliation_parsing import (
    ReconciliationDeclaracionObservation,
    reconciliation_evidence_parser,
)
from .reconciliation_records import (
    ModeloReconciliationAdvisory,
    ModeloReconciliationDiff,
    ModeloReconciliationDiffKind,
    ModeloReconciliationEvidenceKind,
    ModeloReconciliationRecord,
    ModeloReconciliationVerdict,
    modelo_reconciliation_persistence,
)
from .work_addressing import (
    ModeloWorkSelectorRequest,
    ModeloWorkSelectorState,
    ModeloWorkUnitNotFoundError,
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
    from ...domain.calculations.registry.schema_surfaces import CasillaDefinition
    from ...domain.justificante import Justificante
    from ...domain.modelos.calculation_revision import CalculationRevision
    from ...domain.modelos.work_unit import WorkUnit, WorkUnitCatalogue

_DECLARATION_CASILLA_RECONCILE_MODELOS: frozenset[Modelo] = frozenset(
    {Modelo.M100, Modelo.M111, Modelo.M130, Modelo.M190, Modelo.M303, Modelo.M390}
)
"""Modelos enrolled in casilla-level filed-declaration reconciliation.

A modelo not in this set still accepts
:attr:`ModeloReconciliationEvidenceKind.DECLARATION` at the command contract
level but is refused with
:class:`ReconciliationDeclaracionSourceUnsupportedError` — the enrolled set
grows one modelo at a time as each modelo's ``declaracion_pdf`` extraction
profile is confirmed to line up with its registry casilla ids one-to-one (the
same casilla-id vocabulary its
:meth:`~domain.calculations.registry.RegistrySnapshot.verification_policy`
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
    """Strict input contract for ``modelo_reconcile``.

    ``source_path`` points to the operator-supplied evidence file and
    ``source_kind`` records how that file must be parsed. Justificante PDFs are
    supported for every modelo; declaration PDFs are supported (casilla-level)
    only for modelos in :data:`_DECLARATION_CASILLA_RECONCILE_MODELOS` — an
    unenrolled modelo is refused before parsing.
    """

    model_config = _STRICT_FROZEN

    work_unit_id: WorkUnitId
    source_kind: ModeloReconciliationEvidenceKind
    source_path: Path
    actor: str = Field(default="operator", min_length=1, max_length=64)


class ModeloReconciliationBytesCommand(BaseModel):
    """Strict input contract for reconciling secure-storage justificante bytes.

    Used by authenticated live pulls after the captured justificante has
    already been persisted in secure storage. The raw bytes remain in memory;
    ``source_ref`` is the non-file secure-storage reference recorded in the
    reconciliation event.
    """

    model_config = _STRICT_FROZEN

    work_unit_id: WorkUnitId
    source_kind: ModeloReconciliationEvidenceKind
    source_bytes: bytes = Field(min_length=1)
    # Bounded at the bucket-event payload width, not above it. This reference is
    # an app-generated secure-storage handle rather than an operator path, so a
    # value past the cap is an internal defect and belongs refused at validation
    # where it names the field -- not shortened, which would hide it. The
    # operator-supplied filesystem path on the sibling command has no bound of
    # its own and is instead shortened at construction.
    source_ref: str = Field(min_length=1, max_length=_MAX_PAYLOAD_VALUE_LENGTH)
    actor: str = Field(default="operator", min_length=1, max_length=64)


class ModeloReconciliationReport(BaseModel):
    """Outcome of ``modelo_reconcile``.

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
    bucket_id: BucketId
    source_kind: ModeloReconciliationEvidenceKind
    source_path: str
    verdict: ModeloReconciliationVerdict
    diffs: tuple[ModeloReconciliationDiff, ...] = ()
    advisories: tuple[ModeloReconciliationAdvisory, ...] = ()
    reconciled_at: datetime
    narrative: str = ""


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


class ReconciliationDeclaracionSourceUnsupportedError(CadrumoError):
    """Raised when a declaración reconcile targets a modelo not yet enrolled.

    Casilla-level declaración reconciliation is enrolled one modelo at a time
    in :data:`_DECLARATION_CASILLA_RECONCILE_MODELOS`; a modelo outside that set
    refuses cleanly rather than silently degrading to a header-only compare.
    """


def _require_declaration_enrolled_modelo(
    work_unit_id: WorkUnitId,
    *,
    catalogue: WorkUnitCatalogue,
    bucket_id: str,
) -> WorkUnit:
    """Refuse an unenrolled modelo before spending effort parsing its PDF.

    Declaración parsing (template detection, registry-profile extraction) is
    real work; a modelo outside :data:`_DECLARATION_CASILLA_RECONCILE_MODELOS`
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
    if str(work_unit.modelo) not in _DECLARATION_CASILLA_RECONCILE_MODELOS:
        raise ReconciliationDeclaracionSourceUnsupportedError(
            translated_message="application.modelo.errors.reconcile_declaration_unsupported",
            context={
                "modelo": str(work_unit.modelo),
                "enrolled_modelos": ",".join(sorted(_DECLARATION_CASILLA_RECONCILE_MODELOS)),
            },
        )
    return work_unit


def modelo_reconcile(command: ModeloReconciliationCommand) -> ModeloReconciliationReport:
    """Reconcile a modelo work unit against a justificante or declaración PDF file.

    Local-only: never contacts AEAT and never invokes ``require_live_read``.

    For a justificante, compares the neutral observation returned by the bound
    :class:`ReconciliationEvidenceParserPort`. The receipt totals ARE reconciled
    against the persisted revision's computed result where the revision declares
    ``reconciliation_total_casilla_ids``.

    For a declaración, consumes the parser port's structural observation and —
    for modelos enrolled in :data:`_DECLARATION_CASILLA_RECONCILE_MODELOS` —
    compares every registry-reconciled casilla against the persisted revision's
    ``casilla_values``, surfacing each divergence as a typed ``casilla`` diff. A
    modelo outside that set raises
    :class:`ReconciliationDeclaracionSourceUnsupportedError`.

    Emits ``MODELO_RECONCILED`` into the bucket-event-history catalogue.
    The verdict is included in the event payload so downstream
    auditors can replay the reconciliation timeline without
    re-parsing the evidence.

    Returns:
        A :class:`ModeloReconciliationReport`.
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
        return _reconcile_parsed_declaracion(
            work_unit=work_unit,
            source_kind=command.source_kind,
            source_ref=str(command.source_path),
            actor=command.actor,
            declaracion=declaracion,
        )

    try:
        justificante = reconciliation_evidence_parser().parse_justificante(command.source_path)
    except JustificanteParseError as exc:
        raise _evidence_invalid_refusal(exc, source_ref=str(command.source_path)) from exc
    catalogue, bucket_id = _active_reconciliation_catalogue()
    return _reconcile_parsed_justificante(
        work_unit=_resolve_work_unit_for_reconciliation(
            work_unit_id=command.work_unit_id,
            catalogue=catalogue,
            bucket_id=bucket_id,
        ),
        source_kind=command.source_kind,
        source_ref=str(command.source_path),
        actor=command.actor,
        justificante=justificante,
    )


def modelo_reconcile_bytes(command: ModeloReconciliationBytesCommand) -> ModeloReconciliationReport:
    """Reconcile secure-storage evidence bytes without materialising a plaintext file.

    Declaración reconciliation is not offered on this bytes path, but not
    because a filed declaración's bytes cannot exist here: the filed-history
    sweep (:mod:`application.live`) already captures filed declaración
    observations, complete with per-casilla values and their own artefact
    bytes, into secure storage. What this command still lacks is a way to
    reconcile THOSE bytes: it accepts only justificante-shaped evidence a
    caller uploads. A pulled declaración never needs uploading in the first
    place — its per-casilla values are already reconciled against the
    taxpayer's own local calculation by
    :func:`application.modelo.pulled_filing_divergence_findings`, which reads
    both sides out of the same bucket the sweep already populated. Use
    :func:`modelo_reconcile` with a local declaración PDF file for
    casilla-level reconcile of a declaración held only on disk.

    Returns:
        The :class:`ModeloReconciliationReport` comparing the parsed
        justificante metadata to the work unit and active profile.
    """
    if command.source_kind is ModeloReconciliationEvidenceKind.DECLARATION:
        raise ReconciliationDeclaracionSourceUnsupportedError(
            translated_message="application.modelo.errors.reconcile_declaration_unsupported",
        )

    try:
        justificante = reconciliation_evidence_parser().parse_justificante_bytes(command.source_bytes)
    except JustificanteParseError as exc:
        raise _evidence_invalid_refusal(exc, source_ref=command.source_ref) from exc
    catalogue, bucket_id = _active_reconciliation_catalogue()
    return _reconcile_parsed_justificante(
        work_unit=_resolve_work_unit_for_reconciliation(
            work_unit_id=command.work_unit_id,
            catalogue=catalogue,
            bucket_id=bucket_id,
        ),
        source_kind=command.source_kind,
        source_ref=command.source_ref,
        actor=command.actor,
        justificante=justificante,
    )


def _reconcile_parsed_justificante(
    *,
    work_unit: WorkUnit,
    source_kind: ModeloReconciliationEvidenceKind,
    source_ref: str,
    actor: str,
    justificante: Justificante,
) -> ModeloReconciliationReport:
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

    total_diffs, total_advisories = _reconcile_receipt_totals(work_unit=work_unit, justificante=justificante)
    diffs.extend(total_diffs)
    advisories.extend(total_advisories)

    return _finalise_reconciliation(
        work_unit=work_unit,
        source_kind=source_kind,
        source_ref=source_ref,
        actor=actor,
        diffs=diffs,
        advisories=advisories,
        narrative_subject=f"modelo {justificante.modelo} for ejercicio {justificante.ejercicio or '?'}",
    )


def _reconcile_parsed_declaracion(
    *,
    work_unit: WorkUnit,
    source_kind: ModeloReconciliationEvidenceKind,
    source_ref: str,
    actor: str,
    declaracion: ReconciliationDeclaracionObservation,
) -> ModeloReconciliationReport:
    active_bucket_id = work_unit.bucket_id
    if str(work_unit.modelo) not in _DECLARATION_CASILLA_RECONCILE_MODELOS:
        raise ReconciliationDeclaracionSourceUnsupportedError(
            translated_message="application.modelo.errors.reconcile_declaration_unsupported",
            context={
                "modelo": str(work_unit.modelo),
                "enrolled_modelos": ",".join(sorted(_DECLARATION_CASILLA_RECONCILE_MODELOS)),
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

    casilla_diffs, casilla_advisories = _reconcile_declaracion_casillas(work_unit=work_unit, declaracion=declaracion)
    diffs.extend(casilla_diffs)
    advisories.extend(casilla_advisories)

    return _finalise_reconciliation(
        work_unit=work_unit,
        source_kind=source_kind,
        source_ref=source_ref,
        actor=actor,
        diffs=diffs,
        advisories=advisories,
        narrative_subject=f"modelo {declaracion.modelo} for ejercicio {declaracion.ejercicio}",
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


def _finalise_reconciliation(
    *,
    work_unit: WorkUnit,
    source_kind: ModeloReconciliationEvidenceKind,
    source_ref: str,
    actor: str,
    diffs: list[ModeloReconciliationDiff],
    advisories: list[ModeloReconciliationAdvisory],
    narrative_subject: str,
) -> ModeloReconciliationReport:
    """Build the report, persist record and event together, and return the report.

    Shared tail of every reconcile path (justificante or declaración): both
    compute their own ``diffs`` / ``advisories`` lists upstream, then converge
    on the same verdict derivation, report assembly, and persistence.

    The :class:`ModeloReconciliationRecord` and the append-only
    ``MODELO_RECONCILED`` :class:`~domain.buckets.BucketEvent` land in ONE
    persistence unit of work through the bound
    :class:`ModeloReconciliationPersistencePort` — the same co-emit discipline
    :func:`~application.modelo.revision_persistence.persist_filed_revision`
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
    report = ModeloReconciliationReport(
        work_unit_id=work_unit.work_unit_id,
        bucket_id=work_unit.bucket_id,
        source_kind=source_kind,
        source_path=source_ref,
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
        bucket_id=work_unit.bucket_id,
        work_unit_id=work_unit.work_unit_id,
        source_kind=source_kind,
        source_ref=source_ref,
        verdict=verdict,
        diffs=tuple(diffs),
        advisories=tuple(advisories),
        actor=actor,
        reconciled_at=reconciled_at,
    )
    modelo_reconciliation_persistence().persist_with_event(record, event)

    return report


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


def _totals_not_reconciled(reason: str, *, modelo: str, detail: str = "") -> ModeloReconciliationAdvisory:
    """Advisory: the filed totals were not value-reconciled against the engine.

    Emitted when the revision declares no ``reconciliation_total_casilla_ids``
    map, no persisted calculation revision exists, the receipt printed no total,
    or the receipt's total kind is unmapped. The verdict stays scoped to
    identity; this advisory prevents a false green by disclosing that the filed
    amount was not checked against the computed result.
    """
    context = {"reason": reason, "modelo": modelo}
    if detail:
        context["detail"] = detail
    return ModeloReconciliationAdvisory(
        code="totals_not_reconciled",
        message=(
            f"filed totals were not reconciled against the computed result for modelo {modelo} "
            f"({reason}); verdict reflects receipt identity only"
        ),
        context=context,
    )


def _reconcile_receipt_totals(
    *,
    work_unit: WorkUnit,
    justificante: Justificante,
) -> tuple[list[ModeloReconciliationDiff], list[ModeloReconciliationAdvisory]]:
    """Reconcile the receipt total against the canonical computed result casilla.

    Resolves the registry snapshot for ``work_unit``, reads the
    ``reconciliation_total_casilla_ids`` map its verification expectations
    declare (the same map ``calculation_result_summary`` consumes), loads the
    filed / verified persisted :class:`~CalculationRevision`,
    and compares the receipt's printed total against
    ``revision.casilla_values[target_casilla]`` at the expectation's declared
    tolerance. A divergence is a typed ``total`` diff carrying the reconciling
    expectation's ``legal_refs`` / ``source_refs``. Every branch that cannot
    perform the comparison returns a ``totals_not_reconciled`` advisory instead
    of silently passing.
    """
    modelo = str(work_unit.modelo)
    try:
        targets = _total_targets_for_work_unit(work_unit)
    except (LookupError, KeyError, AttributeError, ValueError, CadrumoError):
        return [], [_totals_not_reconciled("snapshot_unavailable", modelo=modelo)]
    if not targets:
        return [], [_totals_not_reconciled("map_not_declared", modelo=modelo)]

    receipt_kind, receipt_total = _receipt_total(justificante)
    if receipt_kind is None or receipt_total is None:
        return [], [_totals_not_reconciled("receipt_has_no_total", modelo=modelo)]

    target = targets.get(receipt_kind)
    if target is None:
        return [], [_totals_not_reconciled("receipt_kind_unmapped", modelo=modelo, detail=receipt_kind)]

    try:
        computed = _computed_result_value(work_unit, target.casilla_id)
    except (LookupError, KeyError, AttributeError, ValueError, CadrumoError):
        return [], [_totals_not_reconciled("no_persisted_revision", modelo=modelo)]
    if computed is None:
        return [], [_totals_not_reconciled("no_persisted_revision", modelo=modelo)]

    # The receipt prints a non-negative magnitude under its ingresar/devolver
    # heading; the result casilla carries its own sign convention. Compare the
    # magnitudes so a devolver casilla stored negative still reconciles, while a
    # genuine sign flip (result 0 vs a printed total) still surfaces.
    if abs(receipt_total - abs(computed)) <= target.tolerance:
        return [], []
    return (
        [
            ModeloReconciliationDiff(
                field_name=f"total_{receipt_kind}",
                work_unit_value=_format_decimal(abs(computed)),
                evidence_value=_format_decimal(receipt_total),
                kind=f"total_{receipt_kind}_mismatch",
                diff_kind=ModeloReconciliationDiffKind.TOTAL,
                legal_refs=target.legal_refs,
                source_refs=target.source_refs,
            ),
        ],
        [],
    )


class _TotalTarget:
    """A declared receipt-total → canonical result-casilla reconciliation target."""

    __slots__ = ("casilla_id", "legal_refs", "source_refs", "tolerance")

    def __init__(
        self,
        *,
        casilla_id: str,
        tolerance: Decimal,
        legal_refs: tuple[str, ...],
        source_refs: tuple[str, ...],
    ) -> None:
        self.casilla_id = casilla_id
        self.tolerance = tolerance
        self.legal_refs = legal_refs
        self.source_refs = source_refs


def _total_targets_for_work_unit(work_unit: WorkUnit) -> dict[str, _TotalTarget]:
    """Collect the ``{ingresar|devolver: _TotalTarget}`` map from the snapshot.

    First declaration wins per kind (mirroring ``calculation_result_summary``),
    so a revision that repeats a total across expectations resolves
    deterministically to one target casilla.
    """
    from ._calculation_helpers import resolve_registry_snapshot_for_work_unit

    snapshot = resolve_registry_snapshot_for_work_unit(work_unit)
    # Deliberately NOT folded through fold_reconciliation_total_casilla_ids.
    # That fold answers "which casilla is the total for this kind" and returns
    # the mapping alone; this site needs the tolerance, legal_refs and
    # source_refs of the EXPECTATION THAT DECLARED THE KIND, and the fold
    # discards that linkage. Consuming it here would mean re-deriving the owning
    # expectation from the casilla id, which is the coupling the fold removes.
    targets: dict[str, _TotalTarget] = {}
    for expectation in snapshot.revision.verification_expectations:
        for kind, casilla_id in expectation.reconciliation_total_casilla_ids.items():
            targets.setdefault(
                str(kind),
                _TotalTarget(
                    casilla_id=str(casilla_id),
                    tolerance=Decimal(expectation.tolerance),
                    legal_refs=tuple(str(ref) for ref in expectation.legal_refs),
                    source_refs=tuple(str(ref) for ref in expectation.source_refs),
                ),
            )
    return targets


def _reconcile_declaracion_casillas(
    *,
    work_unit: WorkUnit,
    declaracion: ReconciliationDeclaracionObservation,
) -> tuple[list[ModeloReconciliationDiff], list[ModeloReconciliationAdvisory]]:
    """Compare every registry-reconciled casilla against the filed declaración.

    Resolves the registry snapshot for ``work_unit`` and folds its verification
    expectations into the canonical
    :class:`~domain.calculations.registry.RegistryVerificationPolicy` — the
    registry's own declared reconciliation scope, never an ad
    hoc casilla list. ``computed_casilla_ids`` (the coverage-gated set) is
    compared in full, so a casilla the computed revision resolved but the
    declaración omitted surfaces as ``MISSING_IN_FILED``.
    ``reconcile_when_present_casilla_ids`` is value-reconciled only when the
    declaración actually prints it (omission is
    legitimate — that is exactly why the casilla is excluded from the coverage
    denominator — so it never surfaces ``MISSING_IN_FILED``).

    Reads the persisted filed / verified
    :class:`~CalculationRevision` (never a fresh
    calculation), decodes the declaración's
    :class:`ReconciliationCasillaObservation` rows into decimals, and
    delegates the comparison to
    :func:`application.modelo._reconcile_casilla.detect_casilla_divergences`.
    Every branch that cannot perform the comparison returns a
    ``totals_not_reconciled``-shaped advisory instead of silently passing
    (``no-silent-under-declaration``); the advisory code is reused across the
    total and casilla surfaces because both disclose the same thing — a
    comparison the reconcile could not perform.
    """
    modelo = str(work_unit.modelo)
    try:
        from ._calculation_helpers import resolve_registry_snapshot_for_work_unit

        snapshot = resolve_registry_snapshot_for_work_unit(work_unit)
        policy = snapshot.verification_policy()
    except (LookupError, KeyError, AttributeError, ValueError, CadrumoError):
        return [], [_totals_not_reconciled("snapshot_unavailable", modelo=modelo)]
    if not policy.computed_casilla_ids and not policy.reconcile_when_present_casilla_ids:
        return [], [_totals_not_reconciled("map_not_declared", modelo=modelo)]

    revision = _filed_revision_for_work_unit(work_unit)
    if revision is None:
        return [], [_totals_not_reconciled("no_persisted_revision", modelo=modelo)]

    from ...domain.calculations.registry.casilla_membership import casillas_by_id

    revision_casillas = casillas_by_id(snapshot.revision)
    filed_values = _decimal_declaracion_values(declaracion)
    computed_values: Mapping[str, Decimal] = revision.casilla_values

    # A casilla carrying an export exemption files no slot on the official
    # record, so the printed declaración cannot carry it either and the
    # extraction profile never targets it. Comparing it against a PDF asserts a
    # comparison this surface cannot perform: `filed` can never hold the id, so
    # every such casilla yields MISSING_IN_FILED whatever the taxpayer declared
    # -- including when the computed value is NON-zero, which is a false finding
    # against a box we never read.
    #
    # Excluding them silences nothing observable. The two FEEDS_ADDRESSED_CASILLA
    # cases are already reconciled under the numbered box their projection
    # addresses (27 and 45 are both enrolled AND extracted), so the observable
    # comparison continues; the NOT_IN_RECORD_DESIGN cases have no printed
    # counterpart to observe. Deliberately NOT collapsed into id alignment: the
    # semantic source is exempt PRECISELY BECAUSE it feeds the addressed box, so
    # merging the two ids would leave that exemption with no subject.
    #
    # Narrowed here rather than on the policy because the exemption is a fact
    # about the PRINTED record; a fichero-side consumer of
    # ``computed_casilla_ids`` is asking a different question.
    reconcilable = dict.fromkeys(
        casilla_id
        for casilla_id in policy.computed_casilla_ids
        if getattr(revision_casillas.get(casilla_id), "export_exemption_reason", None) is None
    )

    divergences = detect_casilla_divergences(
        computed=computed_values,
        filed=filed_values,
        scope=reconcilable,
        tolerance=policy.tolerance,
    )
    # reconcile-when-present casillas: value-reconcile only when both sides
    # actually carry a value; an omission on either side is legitimate here and
    # must never surface as MISSING_IN_FILED / EXTRA_IN_FILED.
    present_on_both = {
        casilla_id: None
        for casilla_id in policy.reconcile_when_present_casilla_ids
        if casilla_id in computed_values and casilla_id in filed_values
    }
    if present_on_both:
        divergences += detect_casilla_divergences(
            computed=computed_values,
            filed=filed_values,
            scope=present_on_both,
            tolerance=policy.tolerance,
        )
    diffs = [_casilla_divergence_diff(divergence, revision_casillas=revision_casillas) for divergence in divergences]
    return diffs, []


_CASILLA_DIVERGENCE_KIND_TOKEN: dict[CasillaDivergenceKind, str] = {
    CasillaDivergenceKind.VALUE_MISMATCH: "casilla_value_mismatch",
    CasillaDivergenceKind.MISSING_IN_FILED: "casilla_missing_in_filed",
    CasillaDivergenceKind.EXTRA_IN_FILED: "casilla_extra_in_filed",
}


def _casilla_divergence_diff(
    divergence: CasillaDivergence,
    *,
    revision_casillas: Mapping[str, CasillaDefinition],
) -> ModeloReconciliationDiff:
    """Project one :class:`CasillaDivergence` onto a typed :class:`ModeloReconciliationDiff`.

    Grounds the diff in the casilla's own registry-declared ``legal_refs`` /
    ``source_refs``, so the per-casilla divergence carries the same legal
    grounding a ``total`` diff carries (``aeat-calculation-grounding``).

    A divergence is always drawn from ``computed_casilla_ids``, so its casilla
    is always declared in the revision. Falling back to empty grounding when the
    lookup missed would emit a value diff that claims no legal basis, which
    ``ModeloReconciliationDiff`` now refuses; the miss is surfaced here as a
    named failure rather than laundered into an ungrounded record.

    Raises:
        ReconciliationDeclaracionSourceUnsupportedError: The divergence names a
            casilla the revision does not declare, so no grounding exists.
    """
    casilla = revision_casillas.get(divergence.casilla_id)
    if casilla is None:
        raise ReconciliationDeclaracionSourceUnsupportedError(
            translated_message="errors.refused.reconciliation_declaration_source_unsupported",
            context={
                "casilla_id": str(divergence.casilla_id),
                "declared_by_revision": False,
            },
        )
    legal_refs = tuple(str(ref) for ref in casilla.legal_refs)
    source_refs = tuple(str(ref) for ref in casilla.source_refs)
    return ModeloReconciliationDiff(
        field_name=divergence.casilla_id,
        work_unit_value=_format_decimal(divergence.computed_value) if divergence.computed_value is not None else "",
        evidence_value=_format_decimal(divergence.filed_value) if divergence.filed_value is not None else "",
        kind=_CASILLA_DIVERGENCE_KIND_TOKEN[divergence.kind],
        diff_kind=ModeloReconciliationDiffKind.CASILLA,
        legal_refs=legal_refs,
        source_refs=source_refs,
    )


def _decimal_declaracion_values(declaracion: ReconciliationDeclaracionObservation) -> dict[str, Decimal]:
    """Return decimal printed values keyed by canonical casilla id.

    A declaración's :class:`ReconciliationCasillaObservation` rows may
    carry a ``Decimal``, an ``int``, or a non-numeric printed value (text/enum
    casillas); only the numeric rows participate in a value-level reconcile.
    """
    values: dict[str, Decimal] = {}
    for extracted in declaracion.values:
        printed = extracted.printed_value
        if isinstance(printed, Decimal):
            values[extracted.casilla_id] = printed
        elif isinstance(printed, int) and not isinstance(printed, bool):
            values[extracted.casilla_id] = Decimal(printed)
    return values


def _computed_result_value(work_unit: WorkUnit, casilla_id: str) -> Decimal | None:
    """Return the canonical computed value of ``casilla_id`` for ``work_unit``.

    Reads the persisted filed / verified calculation revision (never a fresh
    calculation — the reconcile path stays local-only), so the value compared is
    the same canonical ``revision.casilla_values`` the result-summary and export
    surfaces render (``aeat-calculation-aggregation``). Returns
    ``None`` when no persisted revision carries the casilla.
    """
    revision = _filed_revision_for_work_unit(work_unit)
    if revision is None:
        return None
    return revision.casilla_values.get(casilla_id)


def _filed_revision_for_work_unit(work_unit: WorkUnit) -> CalculationRevision | None:
    """Return the persisted filed / verified revision selected for ``work_unit``.

    Shared read path for both the receipt-total compare
    (:func:`_computed_result_value`) and the casilla-level declaración compare
    (:func:`_reconcile_declaracion_casillas`): both must read the exact same
    persisted revision so a total reconcile and a casilla reconcile can never
    silently disagree about which revision represents "what was filed."
    """
    catalogue = calculation_revision_catalogue_repository(bucket_id=str(work_unit.bucket_id)).load()
    return _select_filed_revision(catalogue.for_work_unit(str(work_unit.work_unit_id)))


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


def _receipt_total(justificante: Justificante) -> tuple[str | None, Decimal | None]:
    """Return the receipt's printed total as a ``(kind, magnitude)`` pair.

    A justificante prints at most one of ``total_a_ingresar`` /
    ``total_a_devolver``. ``ingresar`` takes precedence when both are present.
    """
    if justificante.total_a_ingresar is not None:
        return "ingresar", abs(justificante.total_a_ingresar)
    if justificante.total_a_devolver is not None:
        return "devolver", abs(justificante.total_a_devolver)
    return None, None


def _format_decimal(value: Decimal) -> str:
    return f"{value:.2f}"


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
    from ..user_profile.profile_record_repository import ProfileRecordRepository
    from ..user_profile.projections import record_to_path_values, record_to_values

    record = ProfileRecordRepository.for_current_session(bucket_id).load(bucket_id)
    path_values = record_to_path_values(record)
    profile_tax_id = _normalise_tax_id(path_values.get("identity.tax_id"))
    if profile_tax_id:
        return profile_tax_id
    selector_values = record_to_values(record)
    return _normalise_tax_id(selector_values.get("tax.id"))


def _normalise_tax_id(value: object) -> str:
    """Coerce an untyped profile value to the canonical storage-keying token.

    This helper owns only the ``object`` coercion that
    :func:`~core.identity.tax_id_identity_token` deliberately does not accept;
    the normal form itself is the canonical one. Its result is a display and
    presence value, never a comparison key -- two identifiers are compared with
    :func:`~core.identity.same_tax_identifier`, which strips separators so a
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
    "ReconciliationDeclaracionSourceUnsupportedError",
    "ReconciliationEvidenceInvalidError",
    "WorkUnitNotFoundError",
    "modelo_reconcile",
    "modelo_reconcile_bytes",
]
