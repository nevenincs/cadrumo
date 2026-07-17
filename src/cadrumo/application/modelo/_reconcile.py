"""Modelo reconciliation: compare work-unit state and computed result against evidence.

``modelo_reconcile`` accepts a modelo work unit and either an AEAT justificante
PDF or a filed declaración PDF, then produces a :class:`ModeloReconciliationReport`.

For a justificante, the report records whether the work unit's modelo, period,
``ejercicio``, and active-profile tax id match the receipt, AND — where the
revision declares ``reconciliation_total_casilla_ids`` and a persisted
calculation revision exists — whether the receipt's printed total equals the
canonical computed result casilla
(``one-aggregation-path-pull-equals-calculate``). A filed-amount divergence
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
:class:`~domain.modelos.CalculationRevision`, never a fresh calculation.
Authenticated live pulls use ``modelo_reconcile_bytes`` after storing captured
justificante bytes in secure storage. Both paths append a ``MODELO_RECONCILED``
:class:`~domain.buckets.BucketEvent` through
:class:`~domain.buckets.BucketEventHistoryRepository`, persisting the
structured diffs so ``reconcile history`` reports which fields diverged.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core import Modelo
from ...core.errors import CadrumoError
from ...core.identity import BucketId
from ...core.time import now
from ...domain.modelos import WorkUnitId
from ._action_errors import WorkUnitNotFoundError
from ._reconcile_casilla import CasillaDivergence, CasillaDivergenceKind, detect_casilla_divergences

if TYPE_CHECKING:
    from ...adapters.inbound.declaracion import InboundDeclaracionObservation
    from ...core import Period
    from ...domain.calculations.registry import CasillaDefinition
    from ...domain.justificante import Justificante
    from ...domain.modelos import CalculationRevision, WorkUnit

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
Modelos whose extraction profile has not yet been authored (e.g. Modelo 200,
Modelo 202 — no ``declaracion_pdf`` surface at all) or whose casilla-id
alignment has not yet been confirmed stay outside this set and are refused;
real-PDF ``bbox_anchored`` extraction quality for the newly enrolled modelos
remains Tier-R and is tracked separately, blocked on #332-337.
"""


class ModeloReconciliationEvidenceKind(StrEnum):
    """Closed external-evidence labels accepted by reconciliation commands.

    ``DECLARATION`` performs casilla-level reconciliation for modelos in
    :data:`_DECLARATION_CASILLA_RECONCILE_MODELOS`; other modelos raise
    :class:`ReconciliationDeclaracionSourceUnsupportedError`.
    """

    JUSTIFICANTE = "justificante"
    DECLARATION = "declaration"


class ModeloReconciliationVerdict(StrEnum):
    """Closed verdict catalogue for :class:`ModeloReconciliationReport`.

    Closed set: ``matches`` / ``mismatches``. A reconcile that reaches a report
    has already parsed its evidence; an unparseable justificante is surfaced as
    the typed ``ReconciliationEvidenceInvalidError`` refusal
    (``REFUSED_RECONCILIATION_EVIDENCE_INVALID``) before any report is built, so
    there is no ``evidence_invalid`` verdict shell. Any expansion requires a
    design decision and must not add shells.
    """

    MATCHES = "matches"
    MISMATCHES = "mismatches"


class ModeloReconciliationDiffKind(StrEnum):
    """Closed category for a :class:`ModeloReconciliationDiff`.

    ``header_field`` — a receipt-identity disagreement (modelo, ejercicio,
    period, tax id). ``total`` — a filed-amount disagreement between the
    receipt total and the canonical computed result casilla. ``casilla`` — a
    per-casilla value disagreement between the persisted computed revision and
    a filed declaración, emitted for modelos enrolled in
    :data:`_DECLARATION_CASILLA_RECONCILE_MODELOS`
    (:func:`application.modelo._reconcile_casilla.detect_casilla_divergences`).
    """

    HEADER_FIELD = "header_field"
    TOTAL = "total"
    CASILLA = "casilla"


class ModeloReconciliationHistoryEntry(BaseModel):
    """One past reconciliation read back from the bucket event history.

    ``modelo_reconcile`` persists no stored record: a reconciliation is
    repeatable on demand from the justificante, so the durable trace is the
    append-only ``MODELO_RECONCILED`` :class:`~domain.buckets.BucketEvent`
    it emits. This typed entry projects one such event so the operator can
    enumerate past reconciliation verdicts without re-parsing any evidence.
    The read path is the same bucket-event catalogue the write path appends
    into — there is no parallel reconciliation store.
    """

    model_config = _STRICT_FROZEN

    event_id: str = Field(min_length=1, max_length=128)
    bucket_id: BucketId
    work_unit_id: WorkUnitId
    source_kind: ModeloReconciliationEvidenceKind
    source_path: str
    verdict: ModeloReconciliationVerdict
    diff_count: int = Field(ge=0)
    diffs: tuple[ModeloReconciliationDiff, ...] = ()
    actor: str = Field(min_length=1, max_length=64)
    reconciled_at: datetime


class ModeloReconciliationDiff(BaseModel):
    """One disagreement between work unit / profile / computed state and evidence.

    ``diff_kind`` is the closed category (header field, filed total, or
    per-casilla). ``kind`` remains the specific mismatch token
    (``modelo_mismatch``, ``total_ingresar_mismatch``,
    ``casilla_value_mismatch``, ``casilla_missing_in_filed``,
    ``casilla_extra_in_filed``, …). A ``total`` or ``casilla`` diff carries the
    reconciling verification expectation's / casilla's ``legal_refs`` /
    ``source_refs`` so the divergence surfaces with its legal grounding
    (``aeat-calculation-grounding``); header diffs carry empty grounding. For a
    ``casilla`` diff, ``field_name`` is the casilla id and ``work_unit_value`` /
    ``evidence_value`` carry the computed / filed decimal strings (empty when
    the corresponding side carried no value, per
    :class:`~application.modelo._reconcile_casilla.CasillaDivergenceKind`).
    """

    model_config = _STRICT_FROZEN

    field_name: str = Field(min_length=1)
    work_unit_value: str = ""
    evidence_value: str = ""
    kind: str = Field(min_length=1)
    diff_kind: ModeloReconciliationDiffKind = ModeloReconciliationDiffKind.HEADER_FIELD
    legal_refs: tuple[str, ...] = ()
    source_refs: tuple[str, ...] = ()


class ModeloReconciliationAdvisory(BaseModel):
    """One non-blocking reconciliation advisory (surfaced as a CLI ``Notice``).

    Carries a stable ``code`` (``totals_not_reconciled`` /
    ``identity_anchor_unverified``), an operator-facing ``message``, and
    structured ``context`` (the reason, the anchor, the modelo). The CLI folds
    each advisory into a typed :class:`~core.json_contract.Notice` on the
    envelope's ``notices`` channel per
    ``cli-notices-are-the-only-diagnostic-channel`` — an advisory is never a
    bespoke result field. Advisories never flip the verdict: they disclose that
    a comparison could not be performed (so identity-only ``matches`` is never a
    silent false green), not that a value diverged.
    """

    model_config = _STRICT_FROZEN

    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    context: Mapping[str, str] = Field(default_factory=dict)


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
    source_ref: str = Field(min_length=1, max_length=512)
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
        suggestion="aeat app modelo reconcile file WORK_UNIT_ID --file PATH/TO/justificante.pdf",
    )


class ReconciliationDeclaracionSourceUnsupportedError(CadrumoError):
    """Raised when a declaración reconcile targets a modelo not yet enrolled.

    Casilla-level declaración reconciliation is enrolled one modelo at a time
    in :data:`_DECLARATION_CASILLA_RECONCILE_MODELOS`; a modelo outside that set
    refuses cleanly rather than silently degrading to a header-only compare.
    """


class ReconciliationCrossBucketRefusedError(CadrumoError):
    """Raised when the addressed work unit belongs to a different bucket than the active profile bucket.

    Every event is scoped to a bucket id. Allowing the service to emit
    into a non-active bucket would let any caller write into other
    operators' history. The check is enforced at the application service
    so neither the CLI nor any future caller can bypass it.
    """


def _require_declaration_enrolled_modelo(work_unit_id: WorkUnitId) -> WorkUnit:
    """Refuse an unenrolled modelo before spending effort parsing its PDF.

    Declaración parsing (template detection, registry-profile extraction) is
    real work; a modelo outside :data:`_DECLARATION_CASILLA_RECONCILE_MODELOS`
    is refused immediately from the work unit's own declared modelo, before any
    file is opened, rather than only after a parse attempt happens to fail for
    an unrelated reason.

    Returns the loaded :class:`~domain.modelos.WorkUnit` so the caller can
    reuse its already-known modelo/filing_year/period as
    :func:`adapters.inbound.declaracion.parse_declaracion` overrides,
    rather than reloading the catalogue a second time.
    """
    from ...adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository

    catalogue = WorkUnitCatalogueRepository().load()
    work_unit = catalogue.work_units.get(work_unit_id)
    if work_unit is None:
        raise WorkUnitNotFoundError(
            f"work unit {work_unit_id!r} not found in the active bucket catalogue",
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

    For a justificante, reimplements the metadata comparison inline against the
    justificante parser at :mod:`adapters.inbound.justificante`. The
    receipt totals ARE reconciled against the persisted revision's computed
    result where the revision declares ``reconciliation_total_casilla_ids``.

    For a declaración, parses via
    :func:`adapters.inbound.declaracion.parse_declaracion` and — for
    modelos enrolled in :data:`_DECLARATION_CASILLA_RECONCILE_MODELOS` — compares
    every registry-reconciled casilla against the persisted revision's
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
        work_unit = _require_declaration_enrolled_modelo(command.work_unit_id)

        from ...adapters.inbound.declaracion import DeclaracionParseError, parse_declaracion

        try:
            # The addressed work unit already knows its own modelo/año/period;
            # forwarding them as overrides lets a declaración PDF that lacks a
            # detectable "Ejercicio: YYYY" header stamp still parse, instead
            # of failing template detection outright. A PDF that genuinely
            # belongs to a different modelo or ejercicio still raises here
            # (`_resolve_template` reconciles a successful detection against
            # the override and raises on conflict) -- the wrong-PDF-mismatch
            # detection this reconcile depends on is unchanged.
            declaracion = parse_declaracion(
                command.source_path,
                modelo_override=str(work_unit.modelo),
                año_override=work_unit.filing_year,
                period_override=work_unit.period.registry_token,
            )
        except DeclaracionParseError as exc:
            raise _evidence_invalid_refusal(exc, source_ref=str(command.source_path)) from exc
        return _reconcile_parsed_declaracion(
            work_unit_id=command.work_unit_id,
            source_kind=command.source_kind,
            source_ref=str(command.source_path),
            actor=command.actor,
            declaracion=declaracion,
        )

    from ...adapters.inbound.justificante import parse_justificante
    from ...domain.justificante import JustificanteParseError

    try:
        justificante = parse_justificante(command.source_path)
    except JustificanteParseError as exc:
        raise _evidence_invalid_refusal(exc, source_ref=str(command.source_path)) from exc
    return _reconcile_parsed_justificante(
        work_unit_id=command.work_unit_id,
        source_kind=command.source_kind,
        source_ref=str(command.source_path),
        actor=command.actor,
        justificante=justificante,
    )


def modelo_reconcile_bytes(command: ModeloReconciliationBytesCommand) -> ModeloReconciliationReport:
    """Reconcile secure-storage evidence bytes without materialising a plaintext file.

    Declaración reconciliation is not offered on the bytes path: the only
    authenticated live-capture flow today captures justificante snapshots
    (:func:`application.live.capture_justificante_snapshot`), never a filed
    declaración. Use :func:`modelo_reconcile` with a local declaración PDF
    file for casilla-level reconcile.

    Returns:
        The :class:`ModeloReconciliationReport` comparing the parsed
        justificante metadata to the work unit and active profile.
    """
    if command.source_kind is ModeloReconciliationEvidenceKind.DECLARATION:
        raise ReconciliationDeclaracionSourceUnsupportedError(
            translated_message="application.modelo.errors.reconcile_declaration_unsupported",
        )

    from ...adapters.inbound.justificante import parse_justificante_bytes
    from ...domain.justificante import JustificanteParseError

    try:
        justificante = parse_justificante_bytes(command.source_bytes)
    except JustificanteParseError as exc:
        raise _evidence_invalid_refusal(exc, source_ref=command.source_ref) from exc
    return _reconcile_parsed_justificante(
        work_unit_id=command.work_unit_id,
        source_kind=command.source_kind,
        source_ref=command.source_ref,
        actor=command.actor,
        justificante=justificante,
    )


def _reconcile_parsed_justificante(
    *,
    work_unit_id: WorkUnitId,
    source_kind: ModeloReconciliationEvidenceKind,
    source_ref: str,
    actor: str,
    justificante: Justificante,
) -> ModeloReconciliationReport:
    from ...adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
    from ..workflow import workflow_state_repository

    active_bucket_id = workflow_state_repository().load().active_profile_bucket_id()
    if active_bucket_id is None:
        raise WorkUnitNotFoundError(
            translated_message="application.modelo.errors.reconcile_no_active_bucket",
        )

    catalogue = WorkUnitCatalogueRepository().load()
    work_unit = catalogue.work_units.get(work_unit_id)
    if work_unit is None:
        raise WorkUnitNotFoundError(
            f"work unit {work_unit_id!r} not found in the active bucket catalogue",
        )
    if work_unit.bucket_id != active_bucket_id:
        raise ReconciliationCrossBucketRefusedError(
            f"work unit {work_unit_id!r} belongs to bucket "
            f"{work_unit.bucket_id!r} but the active profile bucket is "
            f"{active_bucket_id!r}; switch profile before reconciling",
        )

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
    work_unit_id: WorkUnitId,
    source_kind: ModeloReconciliationEvidenceKind,
    source_ref: str,
    actor: str,
    declaracion: InboundDeclaracionObservation,
) -> ModeloReconciliationReport:
    from ...adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
    from ..workflow import workflow_state_repository

    active_bucket_id = workflow_state_repository().load().active_profile_bucket_id()
    if active_bucket_id is None:
        raise WorkUnitNotFoundError(
            translated_message="application.modelo.errors.reconcile_no_active_bucket",
        )

    catalogue = WorkUnitCatalogueRepository().load()
    work_unit = catalogue.work_units.get(work_unit_id)
    if work_unit is None:
        raise WorkUnitNotFoundError(
            f"work unit {work_unit_id!r} not found in the active bucket catalogue",
        )
    if work_unit.bucket_id != active_bucket_id:
        raise ReconciliationCrossBucketRefusedError(
            f"work unit {work_unit_id!r} belongs to bucket "
            f"{work_unit.bucket_id!r} but the active profile bucket is "
            f"{active_bucket_id!r}; switch profile before reconciling",
        )
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
    elif profile_tax_id != _normalise_tax_id(evidence_tax_id):
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
    """Build the report, persist the ``MODELO_RECONCILED`` event, and return the report.

    Shared tail of every reconcile path (justificante or declaración): both
    compute their own ``diffs`` / ``advisories`` lists upstream, then converge
    on the same verdict derivation, report assembly, and append-only
    bucket-event persistence.
    """
    from ...adapters.persistence.profile.buckets import BucketEventHistoryRepository
    from ...domain.buckets import (
        BucketEvent,
        BucketEventObjectType,
        BucketEventType,
        append_bucket_event,
        derive_bucket_event_id,
    )

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

    event_payload = {
        "work_unit_id": work_unit.work_unit_id,
        "source_kind": source_kind.value,
        "source_path": source_ref,
        "verdict": verdict.value,
        "diffs": str(len(diffs)),
        "diffs_detail": _encode_diffs(diffs),
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
    catalogue_repo = BucketEventHistoryRepository()
    next_catalogue = append_bucket_event(
        catalogue_repo.load(),
        BucketEvent(
            event_id=event_id,
            bucket_id=work_unit.bucket_id,
            event_type=BucketEventType.MODELO_RECONCILED,
            occurred_at=reconciled_at,
            actor=actor,
            object_type=BucketEventObjectType.WORK_UNIT,
            object_id=work_unit.work_unit_id,
            payload_version=1,
            payload=event_payload,
        ),
    )
    catalogue_repo.save(next_catalogue)

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
    filed PDF (see ``fixture-provenance-declared-in-sidecar`` and the profile's
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
    filed / verified persisted :class:`~domain.modelos.CalculationRevision`,
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
    declaracion: InboundDeclaracionObservation,
) -> tuple[list[ModeloReconciliationDiff], list[ModeloReconciliationAdvisory]]:
    """Compare every registry-reconciled casilla against the filed declaración.

    Resolves the registry snapshot for ``work_unit`` and folds its verification
    expectations into a :class:`~domain.calculations.registry.RegistryVerificationPolicy`
    (the same policy :func:`application.verification.verify_declaracion`
    consumes) — the registry's own declared reconciliation scope, never an ad
    hoc casilla list. ``computed_casilla_ids`` (the coverage-gated set) is
    compared in full, so a casilla the computed revision resolved but the
    declaración omitted surfaces as ``MISSING_IN_FILED``.
    ``reconcile_when_present_casilla_ids`` mirrors
    :func:`application.verification.verify_declaracion`'s treatment: it is
    value-reconciled only when the declaración actually prints it (omission is
    legitimate — that is exactly why the casilla is excluded from the coverage
    denominator — so it never surfaces ``MISSING_IN_FILED``).

    Reads the persisted filed / verified
    :class:`~domain.modelos.CalculationRevision` (never a fresh
    calculation), decodes the declaración's
    :class:`~adapters.inbound.pdf.ExtractedCasilla` rows into decimals, and
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

    from ...domain.calculations.registry import casillas_by_id

    revision_casillas = casillas_by_id(snapshot.revision)
    filed_values = _decimal_declaracion_values(declaracion)
    computed_values: Mapping[str, Decimal] = revision.casilla_values

    divergences = detect_casilla_divergences(
        computed=computed_values,
        filed=filed_values,
        scope=dict.fromkeys(policy.computed_casilla_ids),
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
    ``source_refs`` when the casilla is declared (it always is for a divergence
    drawn from ``computed_casilla_ids``, but the lookup stays defensive), so the
    per-casilla divergence carries the same legal grounding a ``total`` diff
    carries (``aeat-calculation-grounding``).
    """
    casilla = revision_casillas.get(divergence.casilla_id)
    legal_refs = tuple(str(ref) for ref in casilla.legal_refs) if casilla is not None else ()
    source_refs = tuple(str(ref) for ref in casilla.source_refs) if casilla is not None else ()
    return ModeloReconciliationDiff(
        field_name=divergence.casilla_id,
        work_unit_value=_format_decimal(divergence.computed_value) if divergence.computed_value is not None else "",
        evidence_value=_format_decimal(divergence.filed_value) if divergence.filed_value is not None else "",
        kind=_CASILLA_DIVERGENCE_KIND_TOKEN[divergence.kind],
        diff_kind=ModeloReconciliationDiffKind.CASILLA,
        legal_refs=legal_refs,
        source_refs=source_refs,
    )


def _decimal_declaracion_values(declaracion: InboundDeclaracionObservation) -> dict[str, Decimal]:
    """Return decimal printed values keyed by canonical casilla id.

    Mirrors :func:`application.verification._verify._decimal_extracted_values`:
    a declaración's :class:`~adapters.inbound.pdf.ExtractedCasilla` rows may
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
    surfaces render (``one-aggregation-path-pull-equals-calculate``). Returns
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
    from ...adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository

    catalogue = CalculationRevisionCatalogueRepository().load()
    return _select_filed_revision(catalogue.for_work_unit(str(work_unit.work_unit_id)))


def _select_filed_revision(revisions: tuple[CalculationRevision, ...]) -> CalculationRevision | None:
    """Pick the revision that best represents what was filed.

    Prefers filed / verified states in priority order (``PRESENTADO`` >
    ``PRESENTADO_SUPERSEDIDO`` > ``VERIFICADO_COMPLETO``), then the most recent
    by ``updated_at``; falls back to the most recent revision of any state so a
    receipt can still be value-reconciled before the filing is recorded in-app.
    """
    from ...domain.modelos import CalculationRevisionState

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


def _encode_diffs(diffs: list[ModeloReconciliationDiff]) -> str:
    """Serialise the structured diffs for the ``MODELO_RECONCILED`` payload.

    History persisted only a diff *count*; this JSON string carries *which*
    fields diverged so ``reconcile history`` is auditable after the fact.
    """
    return json.dumps([diff.model_dump(mode="json") for diff in diffs], separators=(",", ":"))


def _decode_diffs(raw: str) -> tuple[ModeloReconciliationDiff, ...]:
    if not raw:
        return ()
    try:
        payload = json.loads(raw)
    except (ValueError, TypeError):
        return ()
    decoded: list[ModeloReconciliationDiff] = []
    for item in payload:
        # The strict frozen model does not coerce JSON lists into its
        # ``tuple[str, ...]`` grounding fields; normalise them on the way in.
        normalised = dict(item)
        for grounding in ("legal_refs", "source_refs"):
            if grounding in normalised:
                normalised[grounding] = tuple(normalised[grounding])
        if "diff_kind" in normalised:
            normalised["diff_kind"] = ModeloReconciliationDiffKind(normalised["diff_kind"])
        decoded.append(ModeloReconciliationDiff.model_validate(normalised))
    return tuple(decoded)


def _active_profile_tax_id(bucket_id: str) -> str:
    from ..user_profile import build_lifecycle_service, record_to_path_values, record_to_values

    record = build_lifecycle_service(bucket_id=bucket_id).read(bucket_id)
    path_values = record_to_path_values(record)
    profile_tax_id = _normalise_tax_id(path_values.get("identity.tax_id"))
    if profile_tax_id:
        return profile_tax_id
    selector_values = record_to_values(record)
    return _normalise_tax_id(selector_values.get("tax.id"))


def _normalise_tax_id(value: object) -> str:
    return str(value or "").strip().upper()


def list_modelo_reconciliations(
    *,
    bucket_id: BucketId,
    work_unit_id: WorkUnitId | None = None,
) -> tuple[ModeloReconciliationHistoryEntry, ...]:
    """Return every recorded reconciliation in ``bucket_id`` as typed entries.

    ``modelo_reconcile`` stores no record; its durable trace is the
    ``MODELO_RECONCILED`` :class:`~domain.buckets.BucketEvent` it appends.
    This read-back enumerates those events from the same
    :class:`~domain.buckets.BucketEventHistoryRepository` catalogue the
    write path appends into (no parallel read path), filtered to the active
    ``bucket_id`` and ordered oldest-first by ``occurred_at``. Each event is
    projected onto a typed :class:`ModeloReconciliationHistoryEntry` — the
    verdict, source kind, diff count, actor, and reconciliation instant are
    preserved, never collapsed to a flat ``dict[str, Any]``.

    An optional ``work_unit_id`` narrows the result to one work unit's
    reconciliation history. An empty result (no reconciliations recorded, or
    none for the requested work unit) returns an empty tuple — the clean "no
    reconciliations recorded yet" signal, not an error.
    """
    from ...adapters.persistence.profile.buckets import BucketEventHistoryRepository
    from ...domain.buckets import BucketEventType

    catalogue = BucketEventHistoryRepository().load()
    events = catalogue.for_bucket(bucket_id, event_types=(BucketEventType.MODELO_RECONCILED,))
    entries: list[ModeloReconciliationHistoryEntry] = []
    for event in events:
        payload = dict(event.payload)
        event_work_unit_id = payload.get("work_unit_id", event.object_id)
        if work_unit_id is not None and event_work_unit_id != work_unit_id:
            continue
        entries.append(
            ModeloReconciliationHistoryEntry(
                event_id=event.event_id,
                bucket_id=event.bucket_id,
                work_unit_id=event_work_unit_id,
                source_kind=ModeloReconciliationEvidenceKind(payload["source_kind"]),
                source_path=payload.get("source_path", ""),
                verdict=ModeloReconciliationVerdict(payload["verdict"]),
                diff_count=int(payload.get("diffs", "0")),
                diffs=_decode_diffs(payload.get("diffs_detail", "")),
                actor=event.actor,
                reconciled_at=event.occurred_at,
            ),
        )
    return tuple(entries)


__all__ = [
    "ModeloReconciliationAdvisory",
    "ModeloReconciliationBytesCommand",
    "ModeloReconciliationCommand",
    "ModeloReconciliationDiff",
    "ModeloReconciliationDiffKind",
    "ModeloReconciliationEvidenceKind",
    "ModeloReconciliationHistoryEntry",
    "ModeloReconciliationReport",
    "ModeloReconciliationVerdict",
    "ReconciliationCrossBucketRefusedError",
    "ReconciliationDeclaracionSourceUnsupportedError",
    "ReconciliationEvidenceInvalidError",
    "WorkUnitNotFoundError",
    "list_modelo_reconciliations",
    "modelo_reconcile",
    "modelo_reconcile_bytes",
]
