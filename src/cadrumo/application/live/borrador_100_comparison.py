"""Compare the captured Modelo 100 borrador with the saved calculation, box by box.

The two sides hold different grades of evidence. A borrador value is what the
AEAT printed in its draft and was imported here: an observation, never an
authenticated filing. A calculation value was worked out on this computer and
is local. The comparison keeps both values beside each other and never lets one
stand in for the other.

Box identity is the registry's. A borrador snapshot stores its values under the
binding ids of the pinned revision, and a readable snapshot is one whose every
key the law-selected revision re-confirms, so each stored value reaches its
casillas through that revision's own binding map. A stored key is therefore
stable across revisions, and no label is ever matched. A printed box no
binding owns, such as a calculated result, is kept beside the bindings as a
comparison-only observation and reaches its casilla through the registry's
continuity identity for that box. It is compared here and nowhere used as a
calculation input.

A missing capture, a refused capture and a missing calculation each have their
own state, and so does a comparison whose sides no longer describe each other.
None of them is served as agreement: every compared box carries its own
classification and reason, and nothing summarises the boxes as all agreeing;
:class:`ModeloRevision`, the registry revision a modelo is calculated against;
:class:`CalculationRevision`, the saved calculation revision;
:class:`RegistrySnapshot`, the pinned registry snapshot.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Final
from uuid import UUID

from pydantic import BaseModel, Field, NonNegativeInt

from ...core.casilla_id import CasillaId
from ...core.external_constants import OutputLanguage
from ...core.filing_year import FilingYear
from ...core.i18n.render import tr
from ...core.identity.hex_ids import SnapshotId
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.period import Period
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.binding_targets import bound_casilla_binding_ids
from ...domain.calculations.registry.form_codes import form_for_role
from ...domain.calculations.registry.ids import BindingId
from ...domain.calculations.registry.schema import ModeloRevision, RegistrySnapshot
from ...domain.calculations.registry.schema_base import CasillaDataType
from ...domain.calculations.registry.schema_surfaces import CasillaDefinition
from ...domain.filing.schema import ModeloValueKind
from ...domain.modelos.calculation_revision import CalculationRevision, CalculationRevisionState
from ...domain.modelos.codes import ModeloCode
from ...domain.modelos.protocols import (
    CalculationRevisionCatalogueRepositoryProtocol,
    VerificationReportCatalogueRepositoryProtocol,
)
from ...domain.modelos.work_unit_repository import WorkUnitCatalogueRepositoryProtocol
from ..modelo.action_errors import WorkUnitNotFoundError
from ..modelo.calculation_note_gate import calculation_screen_outdated
from ..modelo.printed_boxes import printed_box_number
from ..modelo.work_form_field_vocabulary import ModeloFormText
from ..modelo.work_form_localization import localized_text, unnamed_casilla_label
from ..modelo.work_review import ModeloWorkReview, ModeloWorkReviewCasilla, build_modelo_work_review
from ..operations.public_scalar import PublicDecimal
from .borrador_100 import Borrador100PrintedObservation, Borrador100Snapshot, Borrador100SnapshotReading
from .borrador_100_import import borrador_pdf_extraction_profile
from .borrador_100_keys import borrador_admitted_bindings, printed_box_casilla

_ANNUAL: Final = "0A"

type _Value = Decimal | str


class Borrador100ComparisonStatus(StrEnum):
    """Whether the two sides could be compared, and if not, which side is missing."""

    COMPARED = "compared"
    """Both sides were read and describe the same declaration."""
    STALE = "stale"
    """Both sides were read, but they no longer describe each other; see the stale reasons."""
    NO_CAPTURE = "no_capture"
    """No AEAT draft is imported for the year."""
    CAPTURE_REFUSED = "capture_refused"
    """Drafts are stored for the year, but none can be read under the current rules."""
    NO_CALCULATION = "no_calculation"
    """An AEAT draft is imported, but the declaration has no saved calculation."""


class Borrador100ComparisonStaleReason(StrEnum):
    """Why a comparison whose sides were both read is not current."""

    CALCULATION_USED_OTHER_CAPTURE = "calculation_used_other_capture"
    """The calculation replays a different imported draft than the one compared."""
    NEWER_CAPTURE_REFUSED = "newer_capture_refused"
    """A draft imported after the compared one is stored but cannot be read."""
    CALCULATION_OUTDATED = "calculation_outdated"
    """The rules changed since the calculation was saved, so it needs recalculating."""


class Borrador100ComparisonClassification(StrEnum):
    """How one box's two values stand toward each other."""

    AGREE = "agree"
    DIFFER = "differ"
    ONLY_IN_BORRADOR = "only_in_borrador"
    ONLY_IN_CALCULATION = "only_in_calculation"
    NOT_COMPARABLE = "not_comparable"


class Borrador100ComparisonReason(StrEnum):
    """Why one box got its classification."""

    SAME_VALUE = "same_value"
    TAKEN_FROM_BORRADOR = "taken_from_borrador"
    NOT_APPLICABLE_ZERO = "not_applicable_zero"
    VALUES_DIFFER = "values_differ"
    CALCULATION_NOT_APPLICABLE = "calculation_not_applicable"
    CALCULATION_HAS_NO_VALUE = "calculation_has_no_value"
    BORRADOR_PRINTED_NO_VALUE = "borrador_printed_no_value"
    BORRADOR_VALUE_NOT_KEPT = "borrador_value_not_kept"
    BORRADOR_DOES_NOT_READ_BOX = "borrador_does_not_read_box"
    BORRADOR_VALUE_AMBIGUOUS = "borrador_value_ambiguous"
    CALCULATION_BLOCKED = "calculation_blocked"
    VALUE_KINDS_DIFFER = "value_kinds_differ"


_CLASSIFICATION_OF: Final[Mapping[Borrador100ComparisonReason, Borrador100ComparisonClassification]] = {
    Borrador100ComparisonReason.SAME_VALUE: Borrador100ComparisonClassification.AGREE,
    Borrador100ComparisonReason.TAKEN_FROM_BORRADOR: Borrador100ComparisonClassification.AGREE,
    Borrador100ComparisonReason.NOT_APPLICABLE_ZERO: Borrador100ComparisonClassification.AGREE,
    Borrador100ComparisonReason.VALUES_DIFFER: Borrador100ComparisonClassification.DIFFER,
    Borrador100ComparisonReason.CALCULATION_NOT_APPLICABLE: Borrador100ComparisonClassification.DIFFER,
    Borrador100ComparisonReason.CALCULATION_HAS_NO_VALUE: Borrador100ComparisonClassification.ONLY_IN_BORRADOR,
    Borrador100ComparisonReason.BORRADOR_PRINTED_NO_VALUE: Borrador100ComparisonClassification.ONLY_IN_CALCULATION,
    Borrador100ComparisonReason.BORRADOR_VALUE_NOT_KEPT: Borrador100ComparisonClassification.NOT_COMPARABLE,
    Borrador100ComparisonReason.BORRADOR_DOES_NOT_READ_BOX: Borrador100ComparisonClassification.NOT_COMPARABLE,
    Borrador100ComparisonReason.BORRADOR_VALUE_AMBIGUOUS: Borrador100ComparisonClassification.NOT_COMPARABLE,
    Borrador100ComparisonReason.CALCULATION_BLOCKED: Borrador100ComparisonClassification.NOT_COMPARABLE,
    Borrador100ComparisonReason.VALUE_KINDS_DIFFER: Borrador100ComparisonClassification.NOT_COMPARABLE,
}


_STATUS_LOCALE_KEYS: Final[Mapping[Borrador100ComparisonStatus, str]] = {
    Borrador100ComparisonStatus.COMPARED: "application.live.borrador.comparison.status.compared",
    Borrador100ComparisonStatus.STALE: "application.live.borrador.comparison.status.stale",
    Borrador100ComparisonStatus.NO_CAPTURE: "application.live.borrador.comparison.status.no_capture",
    Borrador100ComparisonStatus.CAPTURE_REFUSED: "application.live.borrador.comparison.status.capture_refused",
    Borrador100ComparisonStatus.NO_CALCULATION: "application.live.borrador.comparison.status.no_calculation",
}

_STALE_LOCALE_KEYS: Final[Mapping[Borrador100ComparisonStaleReason, str]] = {
    Borrador100ComparisonStaleReason.CALCULATION_USED_OTHER_CAPTURE: (
        "application.live.borrador.comparison.stale.calculation_used_other_capture"
    ),
    Borrador100ComparisonStaleReason.NEWER_CAPTURE_REFUSED: (
        "application.live.borrador.comparison.stale.newer_capture_refused"
    ),
    Borrador100ComparisonStaleReason.CALCULATION_OUTDATED: (
        "application.live.borrador.comparison.stale.calculation_outdated"
    ),
}

_CLASSIFICATION_LOCALE_KEYS: Final[Mapping[Borrador100ComparisonClassification, str]] = {
    Borrador100ComparisonClassification.AGREE: "application.live.borrador.comparison.classification.agree",
    Borrador100ComparisonClassification.DIFFER: "application.live.borrador.comparison.classification.differ",
    Borrador100ComparisonClassification.ONLY_IN_BORRADOR: (
        "application.live.borrador.comparison.classification.only_in_borrador"
    ),
    Borrador100ComparisonClassification.ONLY_IN_CALCULATION: (
        "application.live.borrador.comparison.classification.only_in_calculation"
    ),
    Borrador100ComparisonClassification.NOT_COMPARABLE: (
        "application.live.borrador.comparison.classification.not_comparable"
    ),
}

_REASON_LOCALE_KEYS: Final[Mapping[Borrador100ComparisonReason, str]] = {
    Borrador100ComparisonReason.SAME_VALUE: "application.live.borrador.comparison.reason.same_value",
    Borrador100ComparisonReason.TAKEN_FROM_BORRADOR: "application.live.borrador.comparison.reason.taken_from_borrador",
    Borrador100ComparisonReason.NOT_APPLICABLE_ZERO: "application.live.borrador.comparison.reason.not_applicable_zero",
    Borrador100ComparisonReason.VALUES_DIFFER: "application.live.borrador.comparison.reason.values_differ",
    Borrador100ComparisonReason.CALCULATION_NOT_APPLICABLE: (
        "application.live.borrador.comparison.reason.calculation_not_applicable"
    ),
    Borrador100ComparisonReason.CALCULATION_HAS_NO_VALUE: (
        "application.live.borrador.comparison.reason.calculation_has_no_value"
    ),
    Borrador100ComparisonReason.BORRADOR_PRINTED_NO_VALUE: (
        "application.live.borrador.comparison.reason.borrador_printed_no_value"
    ),
    Borrador100ComparisonReason.BORRADOR_VALUE_NOT_KEPT: (
        "application.live.borrador.comparison.reason.borrador_value_not_kept"
    ),
    Borrador100ComparisonReason.BORRADOR_DOES_NOT_READ_BOX: (
        "application.live.borrador.comparison.reason.borrador_does_not_read_box"
    ),
    Borrador100ComparisonReason.BORRADOR_VALUE_AMBIGUOUS: (
        "application.live.borrador.comparison.reason.borrador_value_ambiguous"
    ),
    Borrador100ComparisonReason.CALCULATION_BLOCKED: "application.live.borrador.comparison.reason.calculation_blocked",
    Borrador100ComparisonReason.VALUE_KINDS_DIFFER: "application.live.borrador.comparison.reason.value_kinds_differ",
}

_EVIDENCE_LOCALE_KEYS: Final[Mapping[str, str]] = {
    "calculation": "application.live.borrador.comparison.evidence.calculation",
    "borrador": "application.live.borrador.comparison.evidence.borrador",
}


class Borrador100ComparisonWords(BaseModel):
    """One served token and its words in the requested language."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    token: str = Field(min_length=1)
    words: str = Field(min_length=1)


class Borrador100ComparisonCapture(BaseModel):
    """The imported AEAT draft compared: an AEAT-printed observation, not an authenticated filing."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    snapshot_id: SnapshotId
    captured_at: datetime
    registry_revision_id: str
    evidence: Borrador100ComparisonWords


class Borrador100ComparisonCalculation(BaseModel):
    """The saved calculation compared: worked out on this computer, not filed with the AEAT by this read."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    calculation_revision_id: str
    state: CalculationRevisionState
    created_at: datetime
    registry_revision_id: str
    replayed_snapshot_id: SnapshotId | None
    evidence: Borrador100ComparisonWords


class Borrador100ComparisonRow(BaseModel):
    """One box with each side's value, how they stand and why.

    ``None`` means the side holds no value for the box, never zero.
    ``calculation_absent_by_design`` marks a calculated zero the registry proves
    does not apply, as distinct from a measured zero. ``difference`` is the
    calculation minus the draft, present only when both sides hold amounts.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    casilla_id: CasillaId
    box: str | None
    label: ModeloFormText
    borrador_value: PublicDecimal | str | None
    calculation_value: PublicDecimal | str | bool | None
    calculation_absent_by_design: bool
    difference: PublicDecimal | None
    classification: Borrador100ComparisonWords
    reason: Borrador100ComparisonWords


class Borrador100ComparisonCounts(BaseModel):
    """How many compared boxes fall under each classification."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    agree: NonNegativeInt = 0
    differ: NonNegativeInt = 0
    only_in_borrador: NonNegativeInt = 0
    only_in_calculation: NonNegativeInt = 0
    not_comparable: NonNegativeInt = 0


class Borrador100ComparisonProjection(BaseModel):
    """The comparison of one year's imported AEAT draft with its saved Modelo 100 calculation.

    ``rows`` is empty unless ``status`` is ``compared`` or ``stale``.
    ``refused_captures`` and ``outdated_stored_captures`` count stored drafts
    that could not be read, so an empty comparison is never mistaken for an
    empty store.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    filing_year: FilingYear
    language: OutputLanguage
    status: Borrador100ComparisonWords
    stale_reasons: tuple[Borrador100ComparisonWords, ...]
    capture: Borrador100ComparisonCapture | None
    refused_captures: NonNegativeInt
    outdated_stored_captures: NonNegativeInt
    calculation: Borrador100ComparisonCalculation | None
    rows: tuple[Borrador100ComparisonRow, ...]
    counts: Borrador100ComparisonCounts


@dataclass(frozen=True, slots=True)
class Borrador100ComparisonSources:
    """The profile repositories one comparison reads, bound to one exact profile."""

    bucket_id: str
    work_units: WorkUnitCatalogueRepositoryProtocol
    calculations: CalculationRevisionCatalogueRepositoryProtocol
    verifications: VerificationReportCatalogueRepositoryProtocol


@dataclass(frozen=True, slots=True)
class _SavedCalculation:
    review: ModeloWorkReview
    head: CalculationRevision


def _annual_modelo(operation: PinnedAuthorityOperation) -> ModeloCode:
    """Return the form the registry's role routing names for the annual income tax return."""
    return ModeloCode(form_for_role("renta.annual", authority=operation))


def _words[Token: StrEnum](
    token: Token, locale_keys: Mapping[Token, str], language: OutputLanguage
) -> Borrador100ComparisonWords:
    return Borrador100ComparisonWords(token=token.value, words=tr(locale_keys[token], locale=language.value))


def _evidence(token: str, language: OutputLanguage) -> Borrador100ComparisonWords:
    return Borrador100ComparisonWords(token=token, words=tr(_EVIDENCE_LOCALE_KEYS[token], locale=language.value))


def _saved_calculation(
    sources: Borrador100ComparisonSources, period: Period, operation: PinnedAuthorityOperation
) -> _SavedCalculation | None:
    """Read the declaration's current saved calculation; a missing work unit or head is no calculation."""
    try:
        review = build_modelo_work_review(
            sources.bucket_id,
            _annual_modelo(operation),
            period.filing_year,
            period,
            operation=operation,
            work_unit_repository=sources.work_units,
            calculation_repository=sources.calculations,
            verification_repository=sources.verifications,
        )
    except WorkUnitNotFoundError:
        return None
    if review.calculation_revision_id is None:
        return None
    head = sources.calculations.load(operation=operation).get(review.calculation_revision_id)
    if head is None:
        return None
    return _SavedCalculation(review=review, head=head)


def _calculation_summary(saved: _SavedCalculation, language: OutputLanguage) -> Borrador100ComparisonCalculation:
    head = saved.head
    return Borrador100ComparisonCalculation(
        calculation_revision_id=head.calculation_revision_id,
        state=head.state,
        created_at=head.created_at,
        registry_revision_id=head.registry_snapshot_ref.revision_id,
        replayed_snapshot_id=head.borrador_snapshot_id,
        evidence=_evidence("calculation", language),
    )


def _capture_summary(snapshot: Borrador100Snapshot, language: OutputLanguage) -> Borrador100ComparisonCapture:
    return Borrador100ComparisonCapture(
        snapshot_id=snapshot.snapshot_id,
        captured_at=snapshot.captured_at,
        registry_revision_id=snapshot.registry_snapshot_ref.revision_id,
        evidence=_evidence("borrador", language),
    )


def _stale_reasons(
    snapshot: Borrador100Snapshot,
    reading: Borrador100SnapshotReading,
    saved: _SavedCalculation,
    period: Period,
    operation: PinnedAuthorityOperation,
) -> tuple[Borrador100ComparisonStaleReason, ...]:
    reasons: list[Borrador100ComparisonStaleReason] = []
    replayed = saved.head.borrador_snapshot_id
    if replayed is not None and replayed != snapshot.snapshot_id:
        reasons.append(Borrador100ComparisonStaleReason.CALCULATION_USED_OTHER_CAPTURE)
    if any(item.snapshot.captured_at > snapshot.captured_at for item in reading.refused):
        reasons.append(Borrador100ComparisonStaleReason.NEWER_CAPTURE_REFUSED)
    if calculation_screen_outdated(
        saved.head,
        modelo=str(_annual_modelo(operation)),
        filing_year=period.filing_year,
        period=period,
        operation=operation,
    ):
        reasons.append(Borrador100ComparisonStaleReason.CALCULATION_OUTDATED)
    return tuple(reasons)


def _draft_read_casillas(snapshot: RegistrySnapshot) -> frozenset[str]:
    """The boxes the borrador import reads from the printed draft; none when the revision declares no reading."""
    profile = borrador_pdf_extraction_profile(snapshot)
    if profile is None:
        return frozenset[str]()
    return frozenset(str(target.casilla_id) for target in profile.target_casillas)


def _calculation_value(row: ModeloWorkReviewCasilla | None) -> object | None:
    """The saved value of one box, an integer read as an amount; ``None`` when the calculation holds none."""
    if row is None or row.realised_kind is ModeloValueKind.EMPTY or row.value is None:
        return None
    if isinstance(row.value, int) and not isinstance(row.value, bool):
        return Decimal(row.value)
    return row.value


def _saved_text_answer(
    casilla: CasillaDefinition, owners: tuple[BindingId, ...], head: CalculationRevision
) -> str | None:
    """A text box's saved answer, which the calculation keeps under its binding rather than as a box amount."""
    if casilla.data_type is not CasillaDataType.TEXT:
        return None
    answers = {head.binding_overrides[owner] for owner in owners if owner in head.binding_overrides}
    return answers.pop() if len(answers) == 1 else None


def _same_kind(left: _Value, right: object) -> bool:
    return isinstance(left, Decimal) == isinstance(right, Decimal) and isinstance(left, str) == isinstance(right, str)


@dataclass(frozen=True, slots=True)
class _BoxSides:
    owners: tuple[BindingId, ...]
    observation: Borrador100PrintedObservation | None
    borrador: tuple[_Value, ...]
    calculation: object | None
    row: ModeloWorkReviewCasilla | None
    draft_reads_box: bool


def _uncomparable_calculation(sides: _BoxSides, borrador: _Value) -> Borrador100ComparisonReason | None:
    """Why the calculation's side of a box the draft holds cannot be set against it, if it cannot."""
    calculated = sides.calculation
    if calculated is None:
        return Borrador100ComparisonReason.CALCULATION_HAS_NO_VALUE
    if sides.row is not None and sides.row.blocked_by:
        return Borrador100ComparisonReason.CALCULATION_BLOCKED
    if not _same_kind(borrador, calculated):
        return Borrador100ComparisonReason.VALUE_KINDS_DIFFER
    return None


def _taken_from_borrador(sides: _BoxSides, head: CalculationRevision, snapshot: Borrador100Snapshot) -> bool:
    return head.borrador_snapshot_id == snapshot.snapshot_id and any(
        owner in head.bindings_sourced_from_borrador for owner in sides.owners
    )


def _reason_with_borrador(
    sides: _BoxSides, borrador: _Value, head: CalculationRevision, snapshot: Borrador100Snapshot
) -> Borrador100ComparisonReason:
    uncomparable = _uncomparable_calculation(sides, borrador)
    if uncomparable is not None:
        return uncomparable
    by_design = sides.row is not None and sides.row.absent_by_design
    if borrador != sides.calculation:
        return (
            Borrador100ComparisonReason.CALCULATION_NOT_APPLICABLE
            if by_design
            else Borrador100ComparisonReason.VALUES_DIFFER
        )
    if _taken_from_borrador(sides, head, snapshot):
        return Borrador100ComparisonReason.TAKEN_FROM_BORRADOR
    return Borrador100ComparisonReason.NOT_APPLICABLE_ZERO if by_design else Borrador100ComparisonReason.SAME_VALUE


def _box_reason(
    sides: _BoxSides, head: CalculationRevision, snapshot: Borrador100Snapshot
) -> Borrador100ComparisonReason | None:
    """Classify one box, or ``None`` when neither side holds anything to show.

    A box no binding owns and no printed observation keeps was read from the
    draft by an import that kept nothing for it.
    """
    if not sides.owners and sides.observation is None:
        return Borrador100ComparisonReason.BORRADOR_VALUE_NOT_KEPT
    if len(set(sides.borrador)) > 1:
        return Borrador100ComparisonReason.BORRADOR_VALUE_AMBIGUOUS
    if sides.borrador:
        return _reason_with_borrador(sides, sides.borrador[0], head, snapshot)
    if sides.calculation is None:
        return None
    if sides.draft_reads_box or sides.observation is not None:
        return Borrador100ComparisonReason.BORRADOR_PRINTED_NO_VALUE
    return Borrador100ComparisonReason.BORRADOR_DOES_NOT_READ_BOX


def _public(value: object | None) -> PublicDecimal | str | bool | None:
    if isinstance(value, Decimal):
        return PublicDecimal(decimal=str(value))
    if isinstance(value, (str, bool)):
        return value
    if isinstance(value, date):
        return value.isoformat()
    return None


def _public_borrador(values: tuple[_Value, ...]) -> PublicDecimal | str | None:
    """The draft's one value for a box; none when it holds none or several."""
    if len(set(values)) != 1:
        return None
    value = values[0]
    return PublicDecimal(decimal=str(value)) if isinstance(value, Decimal) else value


def _difference(borrador: tuple[_Value, ...], calculated: object | None) -> PublicDecimal | None:
    if len(borrador) != 1 or not isinstance(borrador[0], Decimal) or not isinstance(calculated, Decimal):
        return None
    return PublicDecimal(decimal=str(calculated - borrador[0]))


def _compared_boxes(revision: ModeloRevision, draft_reads: frozenset[str]) -> tuple[CasillaDefinition, ...]:
    """Every box the draft reads or an AEAT-prefilled binding fills, in the revision's own order."""
    admitted = borrador_admitted_bindings(revision)
    return tuple(
        casilla
        for casilla in revision.casillas
        if casilla.id in draft_reads or any(owner in admitted for owner in bound_casilla_binding_ids(casilla))
    )


def _observations_by_box(
    snapshot: Borrador100Snapshot, revision: ModeloRevision
) -> dict[str, Borrador100PrintedObservation]:
    """Each kept printed observation under the box the law-selected revision identifies it as.

    A readable snapshot's every observation resolves, because the read refuses
    a snapshot holding one that does not.
    """
    boxes: dict[str, Borrador100PrintedObservation] = {}
    for observation in snapshot.printed_observations:
        casilla = printed_box_casilla(
            revision, observation, captured_revision_id=snapshot.registry_snapshot_ref.revision_id
        )
        if casilla is not None:
            boxes[casilla.id] = observation
    return boxes


def _box_sides(
    casilla: CasillaDefinition,
    *,
    admitted: Mapping[BindingId, object],
    snapshot: Borrador100Snapshot,
    observations: Mapping[str, Borrador100PrintedObservation],
    saved: _SavedCalculation,
    review_rows: Mapping[str, ModeloWorkReviewCasilla],
    draft_reads: frozenset[str],
) -> _BoxSides:
    owners = tuple(owner for owner in bound_casilla_binding_ids(casilla) if owner in admitted)
    observation = observations.get(casilla.id)
    printed = () if observation is None or observation.value is None else (observation.value,)
    row = review_rows.get(casilla.id)
    calculated = _calculation_value(row)
    return _BoxSides(
        owners=owners,
        observation=observation,
        borrador=(
            *(snapshot.binding_values[owner] for owner in owners if owner in snapshot.binding_values),
            *printed,
        ),
        calculation=calculated if calculated is not None else _saved_text_answer(casilla, owners, saved.head),
        row=row,
        draft_reads_box=casilla.id in draft_reads,
    )


def _comparison_row(
    casilla: CasillaDefinition, sides: _BoxSides, reason: Borrador100ComparisonReason, language: OutputLanguage
) -> Borrador100ComparisonRow:
    return Borrador100ComparisonRow(
        casilla_id=casilla.id,
        box=printed_box_number(casilla, None),
        label=localized_text(casilla.localization_keys, language) or unnamed_casilla_label(language),
        borrador_value=_public_borrador(sides.borrador),
        calculation_value=_public(sides.calculation),
        calculation_absent_by_design=sides.row is not None and sides.row.absent_by_design,
        difference=_difference(sides.borrador, sides.calculation),
        classification=_words(_CLASSIFICATION_OF[reason], _CLASSIFICATION_LOCALE_KEYS, language),
        reason=_words(reason, _REASON_LOCALE_KEYS, language),
    )


def _rows(
    snapshot: Borrador100Snapshot,
    saved: _SavedCalculation,
    registry: RegistrySnapshot,
    language: OutputLanguage,
) -> tuple[Borrador100ComparisonRow, ...]:
    admitted = borrador_admitted_bindings(registry.revision)
    draft_reads = _draft_read_casillas(registry)
    observations = _observations_by_box(snapshot, registry.revision)
    review_rows = {str(row.casilla_id): row for row in saved.review.casillas}
    rows: list[Borrador100ComparisonRow] = []
    for casilla in _compared_boxes(registry.revision, draft_reads | frozenset(observations)):
        sides = _box_sides(
            casilla,
            admitted=admitted,
            snapshot=snapshot,
            observations=observations,
            saved=saved,
            review_rows=review_rows,
            draft_reads=draft_reads,
        )
        reason = _box_reason(sides, saved.head, snapshot)
        if reason is not None:
            rows.append(_comparison_row(casilla, sides, reason, language))
    return tuple(rows)


def _counts(rows: tuple[Borrador100ComparisonRow, ...]) -> Borrador100ComparisonCounts:
    tally = {classification.value: 0 for classification in Borrador100ComparisonClassification}
    for row in rows:
        tally[row.classification.token] += 1
    return Borrador100ComparisonCounts.model_validate(tally)


def _status(
    snapshot: Borrador100Snapshot | None,
    reading: Borrador100SnapshotReading,
    saved: _SavedCalculation | None,
    stale: tuple[Borrador100ComparisonStaleReason, ...],
) -> Borrador100ComparisonStatus:
    if snapshot is None:
        if reading.refused or reading.outdated_stored_snapshots:
            return Borrador100ComparisonStatus.CAPTURE_REFUSED
        return Borrador100ComparisonStatus.NO_CAPTURE
    if saved is None:
        return Borrador100ComparisonStatus.NO_CALCULATION
    return Borrador100ComparisonStatus.STALE if stale else Borrador100ComparisonStatus.COMPARED


def compare_borrador_100_with_calculation(
    *,
    profile_id: UUID,
    filing_year: int,
    reading: Borrador100SnapshotReading,
    sources: Borrador100ComparisonSources,
    operation: PinnedAuthorityOperation,
    language: OutputLanguage,
) -> Borrador100ComparisonProjection:
    """Compare the year's newest readable imported draft with the declaration's saved calculation.

    ``reading`` is the latest-for-year borrador reading under ``operation``:
    at most one readable snapshot, with every refused one beside it.
    """
    period = Period.from_year_and_code(filing_year, _ANNUAL)
    registry = operation.reading_snapshot(
        str(_annual_modelo(operation)), filing_year=filing_year, period=period.registry_token
    )
    snapshot = reading.readable[0] if reading.readable else None
    saved = _saved_calculation(sources, period, operation)
    stale = (
        _stale_reasons(snapshot, reading, saved, period, operation)
        if snapshot is not None and saved is not None
        else ()
    )
    status = _status(snapshot, reading, saved, stale)
    rows = _rows(snapshot, saved, registry, language) if snapshot is not None and saved is not None else ()
    return Borrador100ComparisonProjection(
        profile_id=profile_id,
        filing_year=filing_year,
        language=language,
        status=_words(status, _STATUS_LOCALE_KEYS, language),
        stale_reasons=tuple(_words(reason, _STALE_LOCALE_KEYS, language) for reason in stale),
        capture=None if snapshot is None else _capture_summary(snapshot, language),
        refused_captures=len(reading.refused),
        outdated_stored_captures=reading.outdated_stored_snapshots,
        calculation=None if saved is None else _calculation_summary(saved, language),
        rows=rows,
        counts=_counts(rows),
    )


__all__ = [
    "Borrador100ComparisonCalculation",
    "Borrador100ComparisonCapture",
    "Borrador100ComparisonClassification",
    "Borrador100ComparisonCounts",
    "Borrador100ComparisonProjection",
    "Borrador100ComparisonReason",
    "Borrador100ComparisonRow",
    "Borrador100ComparisonSources",
    "Borrador100ComparisonStaleReason",
    "Borrador100ComparisonStatus",
    "Borrador100ComparisonWords",
    "compare_borrador_100_with_calculation",
]
