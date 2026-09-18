"""Temporal selection for registry-backed modelo revisions.

Selects exactly one :class:`ModeloRevision` from a :class:`ModeloDefinition`
given a filing year, period, and optional date constraint.
"""

from __future__ import annotations

from calendar import monthrange
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Literal, Protocol

from pydantic import Field, ValidationError, model_validator

from .errors import (
    AmbiguousRevisionSelectionError,
    EjercicioOrdenNotYetPublishedError,
    FilingYearOutsideSupportEnvelopeError,
    NoRevisionForPeriodError,
    RegistryValidationError,
)
from .ids import RevisionId
from .modelo_inception import ModeloInceptionField
from .modelo_localization import require_modelo_localization
from .modelo_pending_orden import PendingEjercicioOrden, PendingEjercicioOrdenes
from .period_selector_match import selector_token_for_request
from .schema import (
    MODELO_REVISION_IDS_CONTEXT,
    ModeloCadence,
    ModeloDefinition,
    ModeloRevision,
    SupportedFilingYearsCatalogue,
)
from .schema_base import (
    CalculationClass,
    CalculationClassField,
    LegalRefs,
    ModeloFilingCapabilities,
    RegistryModel,
    SensitivityClassField,
    SourceRefs,
)
from .schema_deadlines import DeadlineWindowDefinition
from .schema_references import PeriodSelector, TemporalProjectionDirection


class RevisionSelectionMetadata(RegistryModel):
    """Complete immutable metadata required by the canonical revision selector."""

    id: RevisionId
    valid_from: date
    valid_to: date | None = None
    period_selector: PeriodSelector
    deadline_windows: tuple[DeadlineWindowDefinition, ...] = ()

    def contains_date(self, coordinate: date) -> bool:
        """Return whether the coordinate lies inside the governed period window."""
        return coordinate >= self.valid_from and (self.valid_to is None or coordinate <= self.valid_to)

    @classmethod
    def from_revision(cls, revision: ModeloRevision) -> RevisionSelectionMetadata:
        """Project exactly the fields consumed by temporal selection.

        Core types:
        :class:`~cadrumo.domain.calculations.registry.schema.ModeloRevision`.
        """
        return cls(
            id=revision.id,
            valid_from=revision.valid_from,
            valid_to=revision.valid_to,
            period_selector=revision.period_selector,
            deadline_windows=revision.deadline_windows,
        )


class ModeloDirectoryMetadata(RegistryModel):
    """Complete modelo-level metadata without duplicating revision payloads."""

    id: str
    title_localization_key: str
    official_name_localization_key: str
    tax_domain: str
    cadence: ModeloCadence
    jurisdiction: Literal["ES-AEAT"]
    calculation_class: CalculationClassField = CalculationClass.FILING
    output_sensitivity: SensitivityClassField
    capabilities: ModeloFilingCapabilities = ()
    legal_refs: LegalRefs
    source_refs: SourceRefs
    inception: ModeloInceptionField | None = None
    pending_ejercicio_ordenes: PendingEjercicioOrdenes = ()

    @property
    def title(self) -> str:
        """Return the strict official-Spanish Modelo title, as the materialized view does."""
        return require_modelo_localization((self.title_localization_key,), locale="es")

    @classmethod
    def from_modelo(cls, modelo: ModeloDefinition) -> ModeloDirectoryMetadata:
        """Capture every modelo field needed to reconstruct a selected snapshot.

        Core types:
        :class:`~cadrumo.domain.calculations.registry.schema.ModeloDefinition`.
        """
        return cls(
            id=str(modelo.id),
            title_localization_key=modelo.title_localization_key,
            official_name_localization_key=modelo.official_name_localization_key,
            tax_domain=str(modelo.tax_domain),
            cadence=modelo.cadence,
            jurisdiction=modelo.jurisdiction,
            calculation_class=modelo.calculation_class,
            output_sensitivity=modelo.output_sensitivity,
            capabilities=modelo.capabilities,
            legal_refs=modelo.legal_refs,
            source_refs=modelo.source_refs,
            inception=modelo.inception,
            pending_ejercicio_ordenes=modelo.pending_ejercicio_ordenes,
        )


class RevisionEndpointSourceEnrollment(RegistryModel):
    """Small source-membership projection for one historical endpoint."""

    revision_id: RevisionId
    source_refs: SourceRefs


def revision_endpoint_source_ids(modelo: ModeloDefinition, revision: ModeloRevision) -> tuple[str, ...]:
    """Return the compiler's canonical source-enrollment basis for one endpoint.

    Core types:
    :class:`~cadrumo.domain.calculations.registry.schema.ModeloDefinition`,
    :class:`~cadrumo.domain.calculations.registry.schema.ModeloRevision`.
    """
    enrolled = set(modelo.source_refs) | set(revision.source_refs)
    enrolled.update(source_ref for casilla in revision.casillas for source_ref in casilla.source_refs)
    return tuple(sorted(enrolled))


class ModeloRevisionDirectory(RegistryModel):
    """Point-addressed revision selection metadata for one modelo."""

    modelo_id: str
    modelo: ModeloDirectoryMetadata
    revisions: tuple[RevisionSelectionMetadata, ...] = Field(min_length=1)
    endpoint_source_enrollments: tuple[RevisionEndpointSourceEnrollment, ...] = Field(min_length=1)
    pending_ejercicio_ordenes: tuple[PendingEjercicioOrden, ...] = ()
    supported_filing_years: SupportedFilingYearsCatalogue | None = None

    @model_validator(mode="after")
    def _endpoint_source_enrollment_is_complete(self) -> ModeloRevisionDirectory:
        revision_ids = tuple(revision.id for revision in self.revisions)
        enrollment_ids = tuple(enrollment.revision_id for enrollment in self.endpoint_source_enrollments)
        if len(set(revision_ids)) != len(revision_ids):
            raise ValueError("modelo directory revision metadata must declare unique revision ids")
        if len(set(enrollment_ids)) != len(enrollment_ids) or set(enrollment_ids) != set(revision_ids):
            raise ValueError("modelo directory endpoint source enrollment must cover every revision exactly once")
        return self

    def endpoint_source_ids(self, revision_id: RevisionId) -> tuple[str, ...]:
        """Return the admitted source ids for one exact revision endpoint."""
        return next(
            enrollment.source_refs
            for enrollment in self.endpoint_source_enrollments
            if enrollment.revision_id == revision_id
        )

    def materialize(self, revision: ModeloRevision) -> ModeloDefinition:
        """Reconstruct one immutable modelo view around a selected revision of this directory.

        The view carries only the selected payload; its revision-identity
        references still resolve against every revision this directory declares.

        Raises:
            RegistryValidationError: When the view is not a valid modelo, for
                example when the revision references one its directory lacks.

        Core types:
        :class:`~cadrumo.domain.calculations.registry.schema.ModeloRevision`.
        """
        try:
            return ModeloDefinition.model_validate(
                {**self.modelo.model_dump(), "revisions": {revision.id: revision}},
                context={MODELO_REVISION_IDS_CONTEXT: frozenset(str(metadata.id) for metadata in self.revisions)},
            )
        except ValidationError as exc:
            raise RegistryValidationError(
                f"modelo {self.modelo.id!r} view of revision {revision.id!r} is invalid: {exc}",
            ) from exc

    @classmethod
    def from_modelo(
        cls,
        modelo: ModeloDefinition,
        *,
        support: SupportedFilingYearsCatalogue | None = None,
    ) -> ModeloRevisionDirectory:
        """Build a deterministic directory without embedding revision payloads.

        Core types:
        :class:`~cadrumo.domain.calculations.registry.schema.ModeloDefinition`.
        """
        return cls(
            modelo_id=str(modelo.id),
            modelo=ModeloDirectoryMetadata.from_modelo(modelo),
            revisions=tuple(
                RevisionSelectionMetadata.from_revision(revision)
                for revision in sorted(modelo.revisions.values(), key=lambda item: (item.valid_from, str(item.id)))
            ),
            endpoint_source_enrollments=tuple(
                RevisionEndpointSourceEnrollment(
                    revision_id=revision.id,
                    source_refs=revision_endpoint_source_ids(modelo, revision),
                )
                for revision in sorted(modelo.revisions.values(), key=lambda item: (item.valid_from, str(item.id)))
            ),
            pending_ejercicio_ordenes=modelo.pending_ejercicio_ordenes,
            supported_filing_years=support,
        )


class _SelectableRevision(Protocol):
    id: RevisionId
    valid_from: date
    valid_to: date | None
    period_selector: PeriodSelector
    deadline_windows: tuple[DeadlineWindowDefinition, ...]

    def contains_date(self, coordinate: date) -> bool: ...


@dataclass(frozen=True, slots=True)
class RevisionTemporalResolution[RevisionT: _SelectableRevision]:
    """An authored revision selected for one requested filing coordinate."""

    revision: RevisionT
    requested_filing_year: int
    authored_filing_year: int
    projection_direction: TemporalProjectionDirection


def _require_supported_filing_year(
    modelo_id: str,
    revisions: Sequence[_SelectableRevision],
    *,
    filing_year: int,
    period: str | None,
    support: SupportedFilingYearsCatalogue | None,
) -> None:
    """Refuse a coordinate the envelope gates, naming the envelope as the cause.

    This is the ONE place a support-envelope refusal is decided, and it refuses
    by raising rather than by returning a falsy selection year. The distinction
    is the point: an envelope gate that answers "no candidates" is
    indistinguishable downstream from an authoring gap, and the generic absence
    refusal then reports the authored revisions as evidence for a claim that
    nothing covers the coordinate -- evidence that contradicts its own message
    whenever the corpus does author the year. Every selector that accepts an
    envelope calls this before it searches, so the two states can never merge
    again.

    Callers deliberately resolving OUTSIDE the filing envelope -- reading the
    design the law applied to a past period, or proving the authored source
    itself -- pass ``support=None`` or an authority scoped to the authored
    history, and this gate stands aside for them.
    """
    if support is None or support.admits_filing_year(filing_year):
        return
    raise FilingYearOutsideSupportEnvelopeError(
        modelo_id=modelo_id,
        filing_year=filing_year,
        period="year" if period is None else period,
        floor=support.floor,
        horizon=support.horizon,
        hard_ceiling=support.hard_ceiling,
        covering_revision_ids=tuple(
            str(revision.id)
            for revision in revisions
            if revision.period_selector.includes_year(filing_year)
            and (
                period is None
                or selector_token_for_request(revision.period_selector.periods_for_year(filing_year), period)
                is not None
            )
        ),
    )


def _eligible_authored_years(
    revision: _SelectableRevision,
    *,
    requested_year: int,
    period: str | None,
) -> tuple[int, ...]:
    """Return authored coordinates compatible with one revision branch."""
    selector = revision.period_selector
    if selector.years:
        years = selector.years
    elif selector.year_from is None:
        years = ()
    else:
        last = selector.year_to if selector.year_to is not None else max(requested_year, selector.year_from)
        years = tuple(range(selector.year_from, last + 1))
    return tuple(
        year
        for year in years
        if (period is None or selector_token_for_request(selector.periods_for_year(year), period) is not None)
    )


def _nearest_authored_candidates[RevisionT: _SelectableRevision](
    revisions: Sequence[RevisionT],
    *,
    filing_year: int,
    period: str | None,
    revision_id: RevisionId | None,
    support: SupportedFilingYearsCatalogue | None,
) -> tuple[list[RevisionT], int]:
    """Select authored anchors nearest the request; equal distance prefers earlier."""
    if support is not None and not support.admits_filing_year(filing_year):
        return [], filing_year
    # A pinned revision must be the one the law selects; the anchor year is
    # chosen across every revision before the pin narrows it, so a pin never
    # projects a revision the nearest authored edition displaces.
    exact = [
        revision
        for revision in revisions
        if revision.period_selector.includes_year(filing_year)
        and (
            period is None
            or selector_token_for_request(revision.period_selector.periods_for_year(filing_year), period) is not None
        )
    ]
    if exact or support is None:
        return [revision for revision in exact if revision_id is None or revision.id == revision_id], filing_year
    anchors = [
        (year, revision)
        for revision in revisions
        for year in _eligible_authored_years(revision, requested_year=filing_year, period=period)
    ]
    if not anchors:
        return [], filing_year
    authored_year = min((year for year, _ in anchors), key=lambda year: (abs(year - filing_year), year))
    return [
        revision
        for year, revision in anchors
        if year == authored_year and (revision_id is None or revision.id == revision_id)
    ], authored_year


def revision_temporal_resolution[RevisionT: _SelectableRevision](
    revision: RevisionT,
    *,
    filing_year: int,
    period: str | None,
    support: SupportedFilingYearsCatalogue | None,
) -> RevisionTemporalResolution[RevisionT]:
    """Describe requested identity and authored provenance for a selected revision."""
    _candidates, authored_year = _nearest_authored_candidates(
        (revision,),
        filing_year=filing_year,
        period=period,
        revision_id=revision.id,
        support=support,
    )
    direction = TemporalProjectionDirection.AUTHORED
    if authored_year < filing_year:
        direction = TemporalProjectionDirection.FORWARD
    elif authored_year > filing_year:
        direction = TemporalProjectionDirection.BACKWARD
    return RevisionTemporalResolution(
        revision=revision,
        requested_filing_year=filing_year,
        authored_filing_year=authored_year,
        projection_direction=direction,
    )


def _project_reference_date(on: date | None, *, requested_year: int, selection_year: int) -> date | None:
    """Preserve a reference date's filing-year offset when support projects the year."""
    if on is None or requested_year == selection_year:
        return on
    projected_year = on.year - (requested_year - selection_year)
    projected_day = min(on.day, monthrange(projected_year, on.month)[1])
    return on.replace(year=projected_year, day=projected_day)


def _declared_filing_window_covers(
    revision: _SelectableRevision,
    *,
    on: date,
    filing_year: int,
    period: str | None,
) -> bool:
    """Return whether ``on`` falls inside a filing window this revision declares.

    Scoped to the requested coordinate: a window admits ``on`` only for the
    ``filing_year`` it declares and, when the caller named one, the period it
    declares. A window opened for December's monthly filing must not admit a
    request for the fourth quarter merely because the two are filed together.
    """
    for window in revision.deadline_windows:
        if window.filing_year != filing_year:
            continue
        if period is not None and selector_token_for_request((window.period.registry_token,), period) is None:
            continue
        if window.opens_on <= on <= window.closes_on:
            return True
    return False


def _revision_governs_period_on(revision: _SelectableRevision, on: date) -> bool:
    """Return whether ``on`` falls inside the tax periods a revision governs."""
    return revision.contains_date(on)


def _effective_candidates[RevisionT: _SelectableRevision](
    matching: list[RevisionT],
    *,
    on: date | None,
    filing_year: int,
    period: str | None,
) -> list[RevisionT]:
    """Narrow selector-matched revisions to those applicable on ``on``, in tiers.

    ``valid_from``/``valid_to`` delimit the TAX PERIODS a revision governs, not
    the dates on which it may be filed: the corpus declares them at period
    granularity throughout, down to mid-period design boundaries (modelo 490's
    2022 first quarter closes at 31 March 2022, modelo 763's 2012 revision spans
    only its second and third quarters). Almost every filing is made after the
    period it declares has closed, so testing a filing date against that window
    alone refuses the revision at the very moment it is legally due -- modelo
    390's resumen anual is filed in the thirty first calendar days of the
    January FOLLOWING its ejercicio (Orden EHA/3111/2009, art. 8), which no
    ``valid_to`` of 31 December can contain.

    The filing reach is therefore read from the one place the registry grounds
    it -- the revision's own ``deadline_windows``, each carrying the legal and
    source references that establish it -- rather than by widening a period
    window past the law or inferring a deadline in code.

    The two tiers are ORDERED, not pooled, and the order is what keeps a design
    boundary readable. Across a boundary the outgoing revision's last filing
    window overlaps the incoming revision's first governed periods: on 15
    September 2024 modelo 303's ``2024-hasta-08-y-2t`` is still filable for
    August while ``2024-desde-09-y-3t`` already governs September. Pooling the
    two makes that date ambiguous and refuses a question that has an obvious
    answer. A revision whose governed periods are live is the design in force,
    so the window tier is consulted only once no candidate governs ``on`` --
    which is exactly the after-the-year-closes case the windows exist for.

    A revision declaring no window for the requested coordinate makes no claim
    about being filable outside its periods and is refused exactly as before.
    """
    if on is None:
        return matching
    governing = [revision for revision in matching if _revision_governs_period_on(revision, on)]
    if governing:
        return governing
    return [
        revision
        for revision in matching
        if _declared_filing_window_covers(revision, on=on, filing_year=filing_year, period=period)
    ]


def _absence_refusal(
    modelo_id: str,
    revisions: Sequence[_SelectableRevision],
    pending_ordenes: Sequence[PendingEjercicioOrden],
    *,
    filing_year: int,
    period: str,
    revision_id: RevisionId | None,
) -> NoRevisionForPeriodError:
    """Build the refusal for a year no revision covers, as specific as the corpus allows.

    A modelo that has declared the year awaits its approving Orden gets to say
    so: the request failed for a reason nobody can act on yet, which is a
    different fact from an unattended gap and leads an operator somewhere else.
    Absent a declaration the plain absence refusal stands, so a modelo that has
    simply not been authored cannot borrow the excuse.
    """
    available = tuple(str(revision.id) for revision in revisions)
    pending = next((entry for entry in pending_ordenes if entry.filing_year == filing_year), None)
    if pending is not None:
        return EjercicioOrdenNotYetPublishedError(
            modelo_id=modelo_id,
            filing_year=filing_year,
            period=period,
            revision_id=revision_id,
            available_revision_ids=available,
            rests_on=str(pending.rests_on),
            expected_publication_year=pending.expected_publication_year,
        )
    return NoRevisionForPeriodError(
        modelo_id=modelo_id,
        filing_year=filing_year,
        period=period,
        revision_id=revision_id,
        available_revision_ids=available,
    )


def _select_single_year_revision[RevisionT: _SelectableRevision](
    modelo_id: str,
    revisions: Sequence[RevisionT],
    pending_ordenes: Sequence[PendingEjercicioOrden],
    candidates: list[RevisionT],
    *,
    filing_year: int,
) -> RevisionT:
    """Resolve year candidates, refusing both absence and mid-year ambiguity."""
    if not candidates:
        raise _absence_refusal(
            modelo_id,
            revisions,
            pending_ordenes,
            filing_year=filing_year,
            period="year",
            revision_id=None,
        )
    if len(candidates) > 1:
        # A year-only answer for a year covered by more than one revision is wrong
        # in whichever direction it is given, so this refuses rather than picking.
        # The REMEDY is selected by naming a locale key of its own: the
        # period-scoped selector raises the same error, and telling that caller to
        # supply a period would send it to redo what it already did.
        raise AmbiguousRevisionSelectionError(
            modelo_id=modelo_id,
            candidate_ids=tuple(revision.id for revision in candidates),
            filing_year=filing_year,
            reason=(
                "this filing year carries a mid-year AEAT design boundary, so more than one "
                "revision covers it and no year-only answer is correct"
            ),
            translated_message="errors.snapshot.ambiguous_revision_selection_year_only",
        )
    return candidates[0]


def select_revision_for_year(
    modelo: ModeloDefinition,
    *,
    filing_year: int,
    on: date | None = None,
    support: SupportedFilingYearsCatalogue | None = None,
) -> ModeloRevision:
    """Select exactly one revision for a filing year and effective date.

    This is the year-only authority for read-only revision-wide surfaces such
    as bindings discovery.  Callers that already have its revision may
    materialise a snapshot with that explicit ``revision_id`` rather than
    independently selecting again.

    Args:
        modelo: The :class:`ModeloDefinition` whose declared revisions are
            searched for the one matching ``filing_year`` and ``on``.
        filing_year: AEAT filing year used to narrow revisions by their
            ``period_selector``.
        on: Optional reference date at which the revision must be the
            applicable design: inside the tax periods it governs, or inside a
            filing window it declares for this coordinate.
        support: Optional registry envelope that hard-gates the request and
            carries a year beyond its authored horizon back to that horizon.
    """
    revisions = tuple(modelo.revisions.values())
    _require_supported_filing_year(
        str(modelo.id),
        revisions,
        filing_year=filing_year,
        period=None,
        support=support,
    )
    matching, authored_year = _nearest_authored_candidates(
        revisions,
        filing_year=filing_year,
        period=None,
        revision_id=None,
        support=support,
    )
    return _select_single_year_revision(
        str(modelo.id),
        revisions,
        modelo.pending_ejercicio_ordenes,
        _effective_candidates(
            matching,
            on=_project_reference_date(on, requested_year=filing_year, selection_year=authored_year),
            filing_year=authored_year,
            period=None,
        ),
        filing_year=filing_year,
    )


def select_revision_metadata_for_year(
    directory: ModeloRevisionDirectory,
    *,
    filing_year: int,
    on: date | None = None,
    support: SupportedFilingYearsCatalogue | None = None,
) -> RevisionSelectionMetadata:
    """Select metadata with the exact canonical year-scoped rules."""
    effective_support = directory.supported_filing_years if support is None else support
    _require_supported_filing_year(
        directory.modelo_id,
        directory.revisions,
        filing_year=filing_year,
        period=None,
        support=effective_support,
    )
    matching, authored_year = _nearest_authored_candidates(
        directory.revisions,
        filing_year=filing_year,
        period=None,
        revision_id=None,
        support=effective_support,
    )
    return _select_single_year_revision(
        directory.modelo_id,
        directory.revisions,
        directory.pending_ejercicio_ordenes,
        _effective_candidates(
            matching,
            on=_project_reference_date(on, requested_year=filing_year, selection_year=authored_year),
            filing_year=authored_year,
            period=None,
        ),
        filing_year=filing_year,
    )


def select_revision(
    modelo: ModeloDefinition,
    *,
    filing_year: int,
    period: str,
    on: date | None = None,
    revision_id: RevisionId | None = None,
    support: SupportedFilingYearsCatalogue | None = None,
) -> ModeloRevision:
    """Select exactly one :class:`ModeloRevision` for a filing period.

    Args:
        modelo: The :class:`ModeloDefinition` to select a revision from.
        filing_year: AEAT filing year used to narrow revisions by
            ``period_selector``.
        period: Period token (e.g. ``"1T"``, ``"0A"``, ``"ALTA"``);
            case-insensitive against the revision's declared periods.
        on: Optional reference date at which the revision must be the
            applicable design: inside the tax periods it governs, or inside a
            filing window it declares for this coordinate.
        revision_id: Optional explicit revision id; restricts candidates to
            the matching revision when supplied.
        support: Optional registry envelope that hard-gates the request and
            carries a year beyond its authored horizon back to that horizon.
    """
    revisions = tuple(modelo.revisions.values())
    _require_supported_filing_year(
        str(modelo.id),
        revisions,
        filing_year=filing_year,
        period=period,
        support=support,
    )
    matching, authored_year = _nearest_authored_candidates(
        revisions,
        filing_year=filing_year,
        period=period,
        revision_id=revision_id,
        support=support,
    )
    candidates = _effective_candidates(
        matching,
        on=_project_reference_date(on, requested_year=filing_year, selection_year=authored_year),
        filing_year=authored_year,
        period=period,
    )
    return _select_single_revision(
        str(modelo.id),
        tuple(modelo.revisions.values()),
        modelo.pending_ejercicio_ordenes,
        candidates,
        filing_year=filing_year,
        period=period,
        revision_id=revision_id,
    )


def select_revision_metadata(
    directory: ModeloRevisionDirectory,
    *,
    filing_year: int,
    period: str,
    on: date | None = None,
    revision_id: RevisionId | None = None,
    support: SupportedFilingYearsCatalogue | None = None,
) -> RevisionSelectionMetadata:
    """Select complete revision metadata through the canonical period rules."""
    effective_support = directory.supported_filing_years if support is None else support
    _require_supported_filing_year(
        directory.modelo_id,
        directory.revisions,
        filing_year=filing_year,
        period=period,
        support=effective_support,
    )
    matching, authored_year = _nearest_authored_candidates(
        directory.revisions,
        filing_year=filing_year,
        period=period,
        revision_id=revision_id,
        support=effective_support,
    )
    candidates = _effective_candidates(
        matching,
        on=_project_reference_date(on, requested_year=filing_year, selection_year=authored_year),
        filing_year=authored_year,
        period=period,
    )
    return _select_single_revision(
        directory.modelo_id,
        directory.revisions,
        directory.pending_ejercicio_ordenes,
        candidates,
        filing_year=filing_year,
        period=period,
        revision_id=revision_id,
    )


def select_authored_revision_metadata(
    directory: ModeloRevisionDirectory,
    *,
    filing_year: int,
    period: str,
    on: date | None = None,
) -> RevisionSelectionMetadata:
    """Select the revision the law applies to a coordinate, outside the support envelope.

    The support envelope gates what the product will FILE, not which design the
    law applied to a past period. Reading a carried prior filing needs the latter,
    so this selects only among revisions whose own period selector covers the
    exact coordinate and never projects a year onto another authored edition.
    """
    matching, _authored_year = _nearest_authored_candidates(
        directory.revisions,
        filing_year=filing_year,
        period=period,
        revision_id=None,
        support=None,
    )
    candidates = _effective_candidates(matching, on=on, filing_year=filing_year, period=period)
    return _select_single_revision(
        directory.modelo_id,
        directory.revisions,
        directory.pending_ejercicio_ordenes,
        candidates,
        filing_year=filing_year,
        period=period,
        revision_id=None,
    )


def _select_single_revision[RevisionT: _SelectableRevision](
    modelo_id: str,
    revisions: Sequence[RevisionT],
    pending_ordenes: Sequence[PendingEjercicioOrden],
    candidates: list[RevisionT],
    *,
    filing_year: int,
    period: str,
    revision_id: RevisionId | None,
) -> RevisionT:
    if not candidates:
        raise _absence_refusal(
            modelo_id,
            revisions,
            pending_ordenes,
            filing_year=filing_year,
            period=period,
            revision_id=revision_id,
        )
    if len(candidates) > 1:
        raise AmbiguousRevisionSelectionError(
            modelo_id=modelo_id,
            candidate_ids=tuple(revision.id for revision in candidates),
        )
    return candidates[0]
