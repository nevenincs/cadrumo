"""Registry-backed deadline computation engine.

Takes an :class:`TaxpayerProfile` and a year and produces a deterministic,
typed :class:`Schedule`. Filing windows and applicability conditions are
read from validated calculation registry data supplied by
:class:`ValidatedRegistryAuthority`. Each window is described by the
selection metadata of its owning revision paired with its deadline window
definition. A scheduled coordinate no revision authors a window for is
projected from the governed filing-window rule
(:mod:`cadrumo.domain.deadlines.filing_window_projection`) and is a dated
window like any authored one. Every obligation's status is the posture
:meth:`~cadrumo.domain.deadlines.effective_close.EffectiveFilingDeadline.posture_on`
gives its effective close, whatever the filing year.
"""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Generator, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date
from threading import Lock
from typing import TYPE_CHECKING, Final, Protocol, override, runtime_checkable

from ...core.logging import get_logger
from ...core.modelo import Modelo
from ...core.period import Period
from ...core.time.clock import now, today_madrid
from ..contribuyente.entity_type import EntityType, entity_type_legal_entity_token

# Type-only registry references. Runtime callers below import the
# concrete symbols lazily inside the helpers that use them so importing
# this module does not trigger the ~870ms ValidatedRegistryAuthority
# parse — load it only when a deadline computation actually runs.
if TYPE_CHECKING:
    from ..calculations.registry.authority import PinnedAuthorityOperation
    from ..calculations.registry.authority_artifact import AuthorityGenerationPin
    from ..calculations.registry.schema_deadlines import DeadlineWindowDefinition
    from ..calculations.registry.schema_live_verification import ProfilePredicateDefinition
    from ..calculations.registry.temporal import ModeloRevisionDirectory, RevisionSelectionMetadata

    type DeadlineWindowProjection = tuple[str, RevisionSelectionMetadata, DeadlineWindowDefinition]
    """One projected window: modelo code, its owning revision's selection metadata, and the window."""

from .domiciliation_cutoff import resolve_payment_cutoff
from .effective_close import DEFAULT_DUE_SOON_DAYS, effective_filing_deadline
from .errors import (
    DeadlineValidationError,
    NoDeadlineWindowsError,
    ScheduleComputationError,
)
from .filing_window_projection import (
    ProjectedFilingWindow,
    project_unauthored_filing_windows,
)
from .models import (
    ModeloDeadline,
    ObligationStatus,
    Recovery,
    Schedule,
    TaxpayerProfile,
)
from .recargo import build_recovery_for_overdue

_logger = get_logger(__name__)

#: Locale keys for the two engine refusals, stated here so a reader sees which
#: catalogue entry each raise site resolves through. They are the registered
#: keys of :class:`NoDeadlineWindowsError` and
#: :class:`ScheduleComputationError`; the engine states them rather than reading
#: ``code.message_key`` so the key stays greppable from the raise site, and a
#: gate holds the two spellings equal.
MISSING_WINDOWS_MESSAGE_KEY: Final[str] = "errors.error.error_deadlines_missing_windows"
SCHEDULE_COMPUTATION_MESSAGE_KEY: Final[str] = "errors.error.error_deadlines_schedule_computation"


def window_outside_activity_period(
    *,
    period: Period,
    entity_type: EntityType | None,
    opens_on: date,
    closes_on: date,
    activity_start_date: date | None,
    activity_end_date: date | None,
    legal_entity_token: EntityType | None = None,
) -> bool:
    """Return whether an obligation's tax period is outside the activity period.

    Quarterly, monthly, and annual obligations compare the tax period rather
    than the later filing window. This preserves final-period and annual
    residual obligations after cessation. Event and instalment periods have no
    calendar span, so they retain the filing-window fallback.

    The inclusive boundaries are grounded in RGAT Arts. 9 and 11: a period
    that overlaps either alta or baja remains potentially reportable.
    """
    starts_on = period.start_date if period.has_date_span() else opens_on
    ends_on = period.end_date if period.has_date_span() else closes_on
    if activity_start_date is not None and ends_on < activity_start_date:
        return True
    if legal_entity_token is not None and entity_type == legal_entity_token:
        return False
    return activity_end_date is not None and starts_on > activity_end_date


@dataclass(frozen=True, slots=True)
class DeadlineWindowYearIndex:
    """One filing year's windows from one generation.

    ``dated`` holds every window: the authored ones and the rule projections of
    unauthored scheduled coordinates. ``projected`` maps the identity of each
    projected window to its provenance-bearing projection, so a reader can tell
    it from an authored one; nothing else about it is judged differently.
    """

    dated: tuple[DeadlineWindowProjection, ...]
    projected: Mapping[str, ProjectedFilingWindow]


#: One year's projection, keyed by the generation it was read from. An admitted
#: generation is immutable, so the index is a pure function of that identity and
#: the year, and every calendar build re-projected it: the whole modelo
#: directory walked, the owning revision selected and hydrated per window. The
#: key is the authority's own content identity (logical generation plus reader
#: incarnation), never a path or an object address, so a different generation --
#: or the same content behind a fresh reader -- projects again. Bounded because
#: each entry retains that year's projected windows.
DEADLINE_WINDOW_INDEX: OrderedDict[
    tuple[AuthorityGenerationPin, int],
    DeadlineWindowYearIndex,
] = OrderedDict()
DEADLINE_WINDOW_INDEX_LIMIT: Final = 32
_DEADLINE_WINDOW_INDEX_LOCK: Final = Lock()


def indexed_deadline_window_year(
    operation: PinnedAuthorityOperation,
    year: int,
) -> DeadlineWindowYearIndex:
    """Project one filing year's complete window index from a pinned operation.

    Reused for a generation already projected for this year; see
    :data:`DEADLINE_WINDOW_INDEX`.
    """
    key = (operation.pin(), year)
    with _DEADLINE_WINDOW_INDEX_LOCK:
        cached = DEADLINE_WINDOW_INDEX.get(key)
        if cached is not None:
            DEADLINE_WINDOW_INDEX.move_to_end(key)
            return cached
    projected = project_deadline_windows(operation, year)
    with _DEADLINE_WINDOW_INDEX_LOCK:
        DEADLINE_WINDOW_INDEX[key] = projected
        DEADLINE_WINDOW_INDEX.move_to_end(key)
        while len(DEADLINE_WINDOW_INDEX) > DEADLINE_WINDOW_INDEX_LIMIT:
            DEADLINE_WINDOW_INDEX.popitem(last=False)
    return projected


def _window_owner(
    directory: ModeloRevisionDirectory,
    window: DeadlineWindowDefinition,
) -> RevisionSelectionMetadata | None:
    """Return the revision that owns an authored window's coordinate, or ``None`` when none does.

    The window a past year's revision authors is a dated fact of law whether or
    not the product files that year, so a year the envelope gates is answered by
    the design the law applied to it. It still selects only an exact coordinate.
    """
    from ..calculations.registry.errors import NoRevisionForPeriodError
    from ..calculations.registry.temporal import select_authored_revision_metadata, select_revision_metadata

    support = directory.supported_filing_years
    if support is None or support.admits_filing_year(window.filing_year):
        return select_revision_metadata(
            directory,
            filing_year=window.filing_year,
            period=window.period.registry_token,
        )
    try:
        return select_authored_revision_metadata(
            directory,
            filing_year=window.filing_year,
            period=window.period.registry_token,
        )
    except NoRevisionForPeriodError:
        return None


def _owned_directory_windows(
    directory: ModeloRevisionDirectory,
    year: int,
) -> Iterator[tuple[RevisionSelectionMetadata, DeadlineWindowDefinition]]:
    """Yield, lazily, each ``year`` window whose declaring revision the selector owns."""
    for metadata in directory.revisions:
        for metadata_window in metadata.deadline_windows:
            if metadata_window.filing_year != year:
                continue
            selected = _window_owner(directory, metadata_window)
            if selected is not None and selected.id == metadata.id:
                yield metadata, metadata_window


def _authored_period_tokens(projected: list[DeadlineWindowProjection]) -> dict[str, frozenset[str]]:
    """Map each modelo to the period tokens its authored windows cover."""
    authored: dict[str, set[str]] = {}
    for modelo_id, _metadata, window in projected:
        authored.setdefault(modelo_id, set()).add(window.period.registry_token)
    return {modelo_id: frozenset(tokens) for modelo_id, tokens in authored.items()}


def project_deadline_windows(
    operation: PinnedAuthorityOperation,
    year: int,
) -> DeadlineWindowYearIndex:
    """Walk the directory and project the windows their owning revisions declare for ``year``.

    Ownership is decided on the directory metadata by the same selector
    :meth:`PinnedAuthorityOperation.revision_for_context` uses, which mirrors the
    eager authority's ownership rule. The metadata also carries the owner's
    filing schedules, the only other revision member any consumer of the
    projection reads, so no revision is hydrated.

    Every scheduled coordinate that no owning revision authors a window for is
    then projected from the governed filing-window rule; an authored window
    always wins because its coordinate is never projected.
    """
    projected: list[DeadlineWindowProjection] = []
    for modelo_id in operation.modelo_ids():
        for metadata, metadata_window in _owned_directory_windows(operation.modelo_directory(modelo_id), year):
            if metadata.deadline_windows.count(metadata_window) != 1:
                raise ScheduleComputationError(
                    translated_message=SCHEDULE_COMPUTATION_MESSAGE_KEY,
                    context={
                        "registry_stage": "deadline_window_projection",
                        "modelo": modelo_id,
                        "revision": metadata.id,
                        "filing_year": year,
                    },
                )
            projected.append((modelo_id, metadata, metadata_window))
    rule_projected: dict[str, ProjectedFilingWindow] = {}
    for row in project_unauthored_filing_windows(
        operation,
        year,
        authored=_authored_period_tokens(projected),
    ):
        projected.append((row.modelo, row.revision, row.resolution.window))
        rule_projected[row.resolution.window_id] = row.resolution
    projected.sort(
        key=lambda item: (
            item[2].closes_on,
            item[0],
            item[2].filing_year,
            item[2].period.registry_token,
            "" if item[2].resultado_scope is None else item[2].resultado_scope.value,
            () if item[2].tipo_renta_scope is None else tuple(sorted(item[2].tipo_renta_scope)),
        ),
    )
    return DeadlineWindowYearIndex(dated=tuple(projected), projected=rule_projected)


class DeadlineEngine:
    """Engine that computes typed filing schedules from registry data.

    Attributes:
        due_soon_days: Window before
            :attr:`cadrumo.domain.deadlines.models.ModeloDeadline.closes_on` that
            flags :attr:`cadrumo.domain.deadlines.models.ObligationStatus.DUE_SOON`
            (default 14).
    """

    def __init__(
        self,
        *,
        due_soon_days: int = DEFAULT_DUE_SOON_DAYS,
        authority: PinnedAuthorityOperation | None = None,
    ) -> None:
        """Construct an engine.

        Args:
            due_soon_days: Days before ``closes_on`` that flag
                ``DUE_SOON``. Must be ``>= 0``.
            authority: Optional generation-pinned authority operation. When
                omitted, one indexed operation is opened per public query.

        Raises:
            DeadlineValidationError: If ``due_soon_days`` is negative.
            ScheduleComputationError: If registry loading or validation fails.
        """
        if due_soon_days < 0:
            raise DeadlineValidationError(f"due_soon_days must be >= 0, got {due_soon_days}")
        self.due_soon_days = due_soon_days
        self._authority = authority

    def compute(
        self,
        profile: TaxpayerProfile,
        year: int,
        *,
        today: date | None = None,
    ) -> Schedule:
        """Compute the full :class:`Schedule` for ``profile`` x ``year``.

        Pure function: no I/O, no input mutation. Identical
        ``(profile, year, today)`` always yields an equal schedule
        (modulo :attr:`Schedule.generated_at`).

        Args:
            profile: The :class:`TaxpayerProfile` to compute obligations for.
            year: The fiscal year to compute for.
            today: Reference date for status classification. Defaults
                to the canonical Europe/Madrid civil date returned by
                :func:`cadrumo.core.time.clock.today_madrid`.

        Returns:
            The :class:`Schedule` containing every obligation that
            applies to ``profile`` for ``year``.

        Raises:
            NoDeadlineWindowsError: If no validated registry deadline windows
                are registered for ``year`` — the benign data gap callers
                degrade around.
        """
        reference_today = today or today_madrid()
        _logger.debug("computing schedule year=%d reference_today=%s", year, reference_today)
        with self._operation_context() as operation:
            year_index = self._deadline_window_year(year, operation=operation)
            windows = year_index.dated
            obligations = self._obligations_for_windows(
                profile=profile,
                windows=windows,
                reference_today=reference_today,
                operation=operation,
            )
        obligations.sort(key=lambda o: (o.closes_on, o.modelo, o.period.filing_year, o.period.registry_token))
        if not obligations and not windows:
            raise NoDeadlineWindowsError(
                translated_message=MISSING_WINDOWS_MESSAGE_KEY,
                context={"filing_year": year},
            )
        if obligations:
            _logger.debug("computed schedule year=%d obligations=%d", year, len(obligations))
        else:
            _logger.debug("no filing obligations computed year=%d: profile conditions did not match", year)
        return Schedule(
            profile=profile,
            year=year,
            obligations=tuple(obligations),
            generated_at=now(),
        )

    def _obligations_for_windows(
        self,
        *,
        profile: TaxpayerProfile,
        windows: tuple[DeadlineWindowProjection, ...],
        reference_today: date,
        operation: PinnedAuthorityOperation,
    ) -> list[ModeloDeadline]:
        """Project every applicable dated window, in window order."""
        obligations: list[ModeloDeadline] = []
        for modelo, revision, window in windows:
            obligation = self._obligation_for_window(
                profile=profile,
                modelo=modelo,
                revision=revision,
                window=window,
                reference_today=reference_today,
                operation=operation,
            )
            if obligation is not None:
                obligations.append(obligation)
        return obligations

    def _window_conditions_admit(
        self,
        profile: TaxpayerProfile,
        window: DeadlineWindowDefinition,
        *,
        admit_undecided: bool,
    ) -> bool:
        """Return whether the window's applicability conditions keep it for ``profile``.

        Matched conditions keep the window. With ``admit_undecided``, conditions
        that fail only on facts the profile has not answered keep it too.
        """
        from ..calculations.registry.schedules import undecided_profile_condition_fields

        conditions = window.applicability_conditions
        mode = window.applicability_condition_mode
        if self._evaluate_conditions(profile, conditions, mode=mode) is not None:
            return True
        return admit_undecided and bool(undecided_profile_condition_fields(conditions, profile, mode=mode))

    def _obligation_for_window(
        self,
        *,
        profile: TaxpayerProfile,
        modelo: str,
        revision: RevisionSelectionMetadata,
        window: DeadlineWindowDefinition,
        reference_today: date,
        operation: PinnedAuthorityOperation,
        admit_undecided: bool = False,
    ) -> ModeloDeadline | None:
        """Project one (modelo, revision, window) tuple into a :class:`ModeloDeadline`, or ``None``.

        Returns ``None`` when the window does not apply to this
        profile — either the revision has filing schedules and none
        match for the window's registry period, the applicability
        conditions do not resolve, the window requires post-calculation
        qualifiers, or the window falls outside the profile's activity period.
        Resultado/tipo-renta qualified windows cannot be selected from a static
        taxpayer profile and are resolved by the canonical post-calculation plazo
        path instead. Otherwise builds the obligation
        with its classified status and, for OVERDUE obligations with
        ≥1 day late, a registry-backed recovery payload (None when
        the recovery registry has no entry for the modelo).

        ``admit_undecided`` keeps a window whose applicability conditions fail
        only on facts the taxpayer has not answered. The calendar lists what a
        profile positively owes and leaves it unset; one exact filing target
        asks instead whether the profile excludes the obligation, and an
        unanswered fact excludes nothing.
        """
        from ..calculations.registry.schedules import applicable_filing_schedules

        if window.resultado_scope is not None or window.tipo_renta_scope is not None:
            return None
        registry_period = _window_registry_period(window)
        if revision.filing_schedules and not applicable_filing_schedules(
            revision,
            profile,
            period=registry_period,
        ):
            return None
        if not self._window_conditions_admit(profile, window, admit_undecided=admit_undecided):
            return None
        if window_outside_activity_period(
            period=window.period,
            entity_type=profile.entity_type,
            opens_on=window.opens_on,
            closes_on=window.closes_on,
            activity_start_date=profile.activity_start_date,
            activity_end_date=profile.activity_end_date,
            legal_entity_token=entity_type_legal_entity_token(
                effective_date=window.period.end_date if window.period.has_date_span() else window.closes_on,
            ),
        ):
            return None
        effective = effective_filing_deadline(window.closes_on, modelo=modelo, operation=operation)
        obligation_status = effective.posture_on(reference_today, due_soon_days=self.due_soon_days).status
        # An unknown effective close judges nothing after the nominal date: no
        # lateness, no recargo and no payment cutoff.
        close_known = effective.close_known
        return ModeloDeadline(
            modelo=Modelo(modelo),
            period=window.period,
            opens_on=window.opens_on,
            closes_on=window.closes_on,
            adjusted_closes_on=effective.closes_on,
            holiday_coverage=effective.holiday_coverage,
            shift_reason=effective.shift_reason,
            shift_jurisdictions=effective.jurisdictions,
            shift_holiday_refs=effective.holiday_refs,
            payment_cutoff_on=(
                resolve_payment_cutoff(modelo, window, operation=operation).cutoff_on if close_known else None
            ),
            status=obligation_status,
            boe_references=window.legal_refs,
            recovery=_overdue_recovery_or_none(
                obligation_status=obligation_status,
                reference_today=reference_today,
                closes_on=effective.closes_on,
                window=window,
                modelo=modelo,
                operation=operation,
            ),
        )

    def target_obligation(
        self,
        profile: TaxpayerProfile,
        *,
        modelo: str,
        period: Period,
        today: date | None = None,
    ) -> ModeloDeadline | None:
        """Return the obligation ``profile`` owes for one exact modelo and period, or ``None``.

        The windows are the ones :meth:`compute` reads for the period's own
        filing year, so a past period resolves through the registry envelope
        and its authored or projected windows, never through another year's
        schedule. The obligation stays the same after its window closes: a
        filing after the plazo is extemporánea, which Ley 58/2003 art. 27
        surcharges, not extinguishes.

        Unlike :meth:`compute`, a window condition that fails only on facts the
        taxpayer has not answered keeps the obligation; a declared answer that
        rules it out, a filing schedule that does not select the period, or an
        activity period that excludes it still yield ``None``.

        Raises:
            ScheduleComputationError: If the registry projects more than one
                window for the target, which no consumer may arbitrate.

        ``profile`` is the :class:`TaxpayerProfile` it uses.
        """
        reference_today = today or today_madrid()
        with self._operation_context() as operation:
            year_index = self._deadline_window_year(period.filing_year, operation=operation)
            matches = [
                obligation
                for window_modelo, revision, window in year_index.dated
                if window_modelo == modelo and window.period == period
                for obligation in (
                    self._obligation_for_window(
                        profile=profile,
                        modelo=window_modelo,
                        revision=revision,
                        window=window,
                        reference_today=reference_today,
                        operation=operation,
                        admit_undecided=True,
                    ),
                )
                if obligation is not None
            ]
        if len(matches) > 1:
            raise ScheduleComputationError(
                translated_message=SCHEDULE_COMPUTATION_MESSAGE_KEY,
                context={
                    "registry_stage": "target_obligation",
                    "modelo": modelo,
                    "filing_year": period.filing_year,
                    "period": period.registry_token,
                    "match_count": len(matches),
                },
            )
        return matches[0] if matches else None

    def explain(self, profile: TaxpayerProfile, modelo: str, *, year: int | None = None) -> str:
        """Return registry-backed deadline applicability text for ``modelo``.

        Args:
            profile: The :class:`TaxpayerProfile` to evaluate conditions against.
            modelo: The AEAT modelo identifier to look up.
            year: Optional fiscal year; defaults to the current year.
        """
        selected_year = year or today_madrid().year
        with self._operation_context() as operation:
            windows = [
                window
                for code, revision, window in self._deadline_windows(selected_year, operation=operation)
                if code == modelo and self._schedule_applies(profile, revision, window)
            ]
        if not windows:
            raise NoDeadlineWindowsError(
                translated_message=MISSING_WINDOWS_MESSAGE_KEY,
                context={"modelo": modelo, "filing_year": selected_year},
            )
        condition_text = self._evaluate_conditions(
            profile,
            windows[0].applicability_conditions,
            mode=windows[0].applicability_condition_mode,
        )
        if condition_text is None:
            return "No aplica segun las condiciones registrales del modelo."
        return condition_text

    def applies_to(self, profile: TaxpayerProfile, modelo: str, *, year: int | None = None) -> bool:
        """Return whether registry deadline conditions match for ``modelo``.

        Args:
            profile: The :class:`TaxpayerProfile` to evaluate conditions against.
            modelo: The AEAT modelo identifier to check.
            year: Optional fiscal year; defaults to the current year.
        """
        selected_year = year or today_madrid().year
        with self._operation_context() as operation:
            return any(
                code == modelo
                and self._schedule_applies(profile, revision, window)
                and self._evaluate_conditions(
                    profile,
                    window.applicability_conditions,
                    mode=window.applicability_condition_mode,
                )
                is not None
                for code, revision, window in self._deadline_windows(selected_year, operation=operation)
            )

    @contextmanager
    def _operation_context(self) -> Generator[PinnedAuthorityOperation]:
        """Yield one pinned operation for a complete deadline query."""
        if self._authority is not None:
            yield self._authority
            return
        from ..calculations.registry.authority import bundled_indexed_authority

        with bundled_indexed_authority().operation() as operation:
            yield operation

    def _deadline_windows(
        self,
        year: int,
        *,
        operation: PinnedAuthorityOperation | None = None,
    ) -> tuple[DeadlineWindowProjection, ...]:
        return self._deadline_window_year(year, operation=operation).dated

    def _deadline_window_year(
        self,
        year: int,
        *,
        operation: PinnedAuthorityOperation | None = None,
    ) -> DeadlineWindowYearIndex:
        from ..calculations.registry.errors import RegistryError

        try:
            if operation is not None:
                return indexed_deadline_window_year(operation, year)
            with self._operation_context() as selected_operation:
                return indexed_deadline_window_year(selected_operation, year)
        except RegistryError as exc:
            raise ScheduleComputationError(
                translated_message=SCHEDULE_COMPUTATION_MESSAGE_KEY,
                context={
                    "registry_stage": "validation",
                    "filing_year": year,
                    "registry_error_type": type(exc).__name__,
                },
            ) from exc

    def deadline_windows(self, year: int) -> tuple[DeadlineWindowProjection, ...]:
        """Return validated registry deadline windows for ``year``.

        This read-only facade lets application projections inspect the same
        registry surface used by :meth:`compute` without reaching into engine
        implementation details.
        """
        with self._operation_context() as operation:
            return self._deadline_windows(year, operation=operation)

    @staticmethod
    def _schedule_applies(
        profile: TaxpayerProfile,
        revision: RevisionSelectionMetadata,
        window: DeadlineWindowDefinition,
    ) -> bool:
        from ..calculations.registry.schedules import applicable_filing_schedules

        if not revision.filing_schedules:
            return True
        return bool(applicable_filing_schedules(revision, profile, period=_window_registry_period(window)))

    def schedule_applies(
        self,
        profile: TaxpayerProfile,
        revision: RevisionSelectionMetadata,
        window: DeadlineWindowDefinition,
    ) -> bool:
        """Return whether a validated filing schedule applies to ``profile``.

        Args:
            profile: The :class:`TaxpayerProfile` whose declared facts are
                checked against the schedule.
            revision: The owning revision's selection metadata, whose filing
                schedules are consulted.
            window: The deadline window under evaluation.
        """
        return self._schedule_applies(profile, revision, window)

    @staticmethod
    def _evaluate_conditions(
        profile: TaxpayerProfile,
        conditions: tuple[ProfilePredicateDefinition, ...],
        *,
        mode: str,
    ) -> str | None:
        from ..calculations.registry.errors import RegistryError
        from ..calculations.registry.schedules import evaluate_profile_conditions

        if not conditions:
            return "Aplica segun la ventana registral del modelo."
        try:
            explanations = evaluate_profile_conditions(conditions, profile, mode=mode)
        except RegistryError as exc:
            raise ScheduleComputationError(
                translated_message=SCHEDULE_COMPUTATION_MESSAGE_KEY,
                context={
                    "registry_stage": "profile_condition_evaluation",
                    "condition_count": len(conditions),
                    "condition_mode": mode,
                    "registry_error_type": type(exc).__name__,
                },
            ) from exc
        if explanations is None:
            return None
        return " ".join(explanations)

    def evaluate_conditions(
        self,
        profile: TaxpayerProfile,
        conditions: tuple[ProfilePredicateDefinition, ...],
        *,
        mode: str,
    ) -> str | None:
        """Evaluate one registry applicability-condition tuple.

        Args:
            profile: The :class:`TaxpayerProfile` the conditions are checked
                against.
            conditions: The registry-declared predicate tuple to evaluate.
            mode: The evaluation mode forwarded to the registry evaluator.
        """
        return self._evaluate_conditions(profile, conditions, mode=mode)


def _overdue_recovery_or_none(
    *,
    obligation_status: ObligationStatus,
    reference_today: date,
    closes_on: date,
    window: DeadlineWindowDefinition,
    modelo: str,
    operation: PinnedAuthorityOperation,
) -> Recovery | None:
    """Build a registry-backed recovery payload for ≥1-day-late OVERDUE obligations, or ``None``.

    Same-day OVERDUE (``days_late == 0``) and non-OVERDUE statuses
    yield ``None``. A recovery-registry lookup miss
    (:class:`FileNotFoundError` or :class:`ValueError`) is treated as
    "no recovery defined" rather than fatal so the obligation still
    surfaces — the operator gets a status flag without speculative
    surcharge math.
    """
    if obligation_status is not ObligationStatus.OVERDUE:
        return None
    days_late = (reference_today - closes_on).days
    if days_late < 1:
        return None
    try:
        return build_recovery_for_overdue(
            closes_on=closes_on,
            reference_today=reference_today,
            modelo=modelo,
            period=window.period,
            operation=operation,
        )
    except (FileNotFoundError, ValueError) as exc:
        _logger.debug(
            "no overdue recovery registry entry for modelo=%s period=%s days_late=%d: %s",
            modelo,
            str(window.period),
            days_late,
            exc,
        )
        return None


def _window_registry_period(window: DeadlineWindowDefinition) -> str:
    """Return the bare registry period token for the deadline window."""
    return window.period.registry_token


def next_deadline(schedule: Schedule, today: date | None = None) -> ModeloDeadline | None:
    """Return the next obligation in ``schedule`` that has not yet closed.

    Pure function. Returns ``None`` if every obligation in the schedule
    is already overdue (or the schedule is empty). A window stays open
    through its effective close, the day the filer actually has, so a window
    whose nominal close fell on a non-business day is still next on the
    following business day.

    Args:
        schedule: The :class:`Schedule` to scan for upcoming obligations.
        today: Reference date. Defaults to the canonical Europe/Madrid civil
            date returned by :func:`cadrumo.core.time.clock.today_madrid`.

    Returns:
        The earliest non-overdue :class:`ModeloDeadline`, or ``None``
        if no such obligation exists.
    """
    reference_today = today or today_madrid()
    upcoming = [o for o in schedule.obligations if o.adjusted_closes_on >= reference_today]
    if not upcoming:
        return None
    upcoming.sort(key=lambda o: (o.adjusted_closes_on, o.modelo, o.period.filing_year, o.period.registry_token))
    return upcoming[0]


class ObligationScheduleSource(Protocol):
    """Structural surface over :class:`DeadlineEngine.compute` alone.

    :func:`compute_obligation_schedule` is typed against this Protocol
    rather than the concrete :class:`DeadlineEngine` so the workflow
    engine — which injects a protocol-typed deadline engine — and the
    state projection — which uses a concrete :class:`DeadlineEngine` —
    can both feed the same single-producer function. It asks for nothing
    that function does not read.
    """

    def compute(
        self,
        profile: TaxpayerProfile,
        year: int,
        *,
        today: date | None = None,
    ) -> Schedule:
        """Return a :class:`Schedule` for ``profile`` in ``year``.

        Args:
            profile: The :class:`TaxpayerProfile` to compute obligations for.
            year: The fiscal year to compute for.
            today: Reference date for status classification.
        """
        ...


@runtime_checkable
class ScheduleProducer(ObligationScheduleSource, Protocol):
    """An :class:`ObligationScheduleSource` that also exposes its due-soon window.

    The overview calendar reads ``due_soon_days`` to classify rows it
    projects itself, so it needs this wider surface.
    """

    due_soon_days: int

    @override
    def compute(
        self,
        profile: TaxpayerProfile,
        year: int,
        *,
        today: date | None = None,
    ) -> Schedule:
        """Return a :class:`Schedule` for ``profile`` in ``year``.

        Args:
            profile: The :class:`TaxpayerProfile` to compute obligations for.
            year: The fiscal year to compute for.
            today: Reference date for status classification.
        """
        ...


def compute_obligation_schedule(
    engine: ObligationScheduleSource,
    profile: TaxpayerProfile,
    *,
    today: date,
) -> Schedule:
    """Compute the obligation :class:`Schedule` from one canonical call.

    This is the single producer of the pending-obligation datum. Both
    the operator state read-projection (``pending_obligations``) and the
    :class:`~cadrumo.application.workflow.engine.WorkflowEngine`
    ``NO_PENDING_OBLIGATION`` gate route their schedule computation
    through here, so the gate and the projection cannot draw a divergent
    obligation set: identical ``(engine, profile, today)`` always yields
    an equal schedule (modulo :attr:`Schedule.generated_at`).

    The fiscal year is derived from ``today`` so neither consumer can
    pass a mismatched ``(year, today)`` pair.

    Args:
        engine: The deadline engine to compute with. Any
            :class:`ObligationScheduleSource` — a concrete
            :class:`DeadlineEngine` or the workflow engine's
            protocol-typed injected deadline engine.
        profile: The :class:`TaxpayerProfile` to schedule obligations for.
        today: Reference date; the fiscal year and obligation status
            classification are both derived from it.

    Returns:
        The :class:`Schedule` of obligations applicable to ``profile``
        for ``today``'s fiscal year.
    """
    return engine.compute(profile, today.year, today=today)


def applies_to(profile: TaxpayerProfile, modelo: str) -> bool:
    """Return whether registry deadline conditions match for ``modelo``.

    Args:
        profile: The :class:`TaxpayerProfile` to evaluate conditions against.
        modelo: The AEAT modelo identifier to check.
    """
    return DeadlineEngine().applies_to(profile, modelo)


def explain(profile: TaxpayerProfile, modelo: str) -> str:
    """Return registry-backed deadline applicability text for ``modelo``.

    Args:
        profile: The :class:`TaxpayerProfile` to evaluate conditions against.
        modelo: The AEAT modelo identifier to look up.
    """
    return DeadlineEngine().explain(profile, modelo)
