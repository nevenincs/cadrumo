"""Registry-backed deadline computation engine.

Takes an :class:`TaxpayerProfile` and a year and produces a deterministic,
typed :class:`Schedule`. Filing windows and applicability conditions are
read from validated calculation registry data supplied by
:class:`ValidatedRegistryAuthority`. Each window is described by a
:class:`ModeloRevision` paired with its deadline window definitions.
"""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Generator
from contextlib import contextmanager
from datetime import date
from threading import Lock
from typing import TYPE_CHECKING, Final, Protocol, runtime_checkable

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
    from ..calculations.registry.schema import ModeloRevision
    from ..calculations.registry.schema_deadlines import DeadlineWindowDefinition
    from ..calculations.registry.schema_verification import ProfilePredicateDefinition

from .errors import (
    DeadlineValidationError,
    NoDeadlineWindowsError,
    ScheduleComputationError,
)
from .models import (
    ModeloDeadline,
    ObligationStatus,
    Recovery,
    Schedule,
    TaxpayerProfile,
)
from .recargo import build_recovery_for_overdue, load_recargo_bands

_logger = get_logger(__name__)

_DEFAULT_DUE_SOON_DAYS = 14

#: Locale keys for the two engine refusals, stated here so a reader sees which
#: catalogue entry each raise site resolves through. They are the registered
#: keys of :class:`NoDeadlineWindowsError` and
#: :class:`ScheduleComputationError`; the engine states them rather than reading
#: ``code.message_key`` so the key stays greppable from the raise site, and a
#: gate holds the two spellings equal.
_MISSING_WINDOWS_MESSAGE_KEY: Final[str] = "errors.error.error_deadlines_missing_windows"
_SCHEDULE_COMPUTATION_MESSAGE_KEY: Final[str] = "errors.error.error_deadlines_schedule_computation"


def classify_obligation_status(closes_on: date, today: date, due_soon_days: int) -> ObligationStatus:
    """Map a window close date to an :class:`ObligationStatus`.

    This is the single owner of the OVERDUE / DUE_TODAY / DUE_SOON / UPCOMING
    boundary rules. The deadline engine applies it to every registry-scheduled
    obligation, and the overview calendar applies it to a locally-created work
    unit after its own filing-pointer gate has run — that gate is the only
    intentional difference between the two callers, and it decides whether to
    call this function at all, never how the boundaries fall.

    Args:
        closes_on: The day the AEAT filing window closes.
        today: The reference date the engine evaluates against.
        due_soon_days: Window (in days) before ``closes_on`` for which
            the obligation is flagged ``DUE_SOON``.

    Returns:
        The :class:`ObligationStatus` for the window.
    """
    if today > closes_on:
        return ObligationStatus.OVERDUE
    if today == closes_on:
        return ObligationStatus.DUE_TODAY
    delta = (closes_on - today).days
    if 1 <= delta <= due_soon_days:
        return ObligationStatus.DUE_SOON
    return ObligationStatus.UPCOMING


def _window_outside_activity_period(
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


#: One year's projection, keyed by the generation it was read from. An admitted
#: generation is immutable, so the index is a pure function of that identity and
#: the year, and every calendar build re-projected it: the whole modelo
#: directory walked, the owning revision selected and hydrated per window. The
#: key is the authority's own content identity (logical generation plus reader
#: incarnation), never a path or an object address, so a different generation --
#: or the same content behind a fresh reader -- projects again. Bounded because
#: each entry retains that year's hydrated revisions.
_DEADLINE_WINDOW_INDEX: OrderedDict[
    tuple[AuthorityGenerationPin, int],
    tuple[tuple[str, ModeloRevision, DeadlineWindowDefinition], ...],
] = OrderedDict()
_DEADLINE_WINDOW_INDEX_LIMIT: Final = 32
_DEADLINE_WINDOW_INDEX_LOCK: Final = Lock()


def indexed_deadline_windows(
    operation: PinnedAuthorityOperation,
    year: int,
) -> tuple[tuple[str, ModeloRevision, DeadlineWindowDefinition], ...]:
    """Project one filing year's deadline windows from a pinned operation.

    Reused for a generation already projected for this year; see
    :data:`_DEADLINE_WINDOW_INDEX`.
    """
    key = (operation.pin(), year)
    with _DEADLINE_WINDOW_INDEX_LOCK:
        cached = _DEADLINE_WINDOW_INDEX.get(key)
        if cached is not None:
            _DEADLINE_WINDOW_INDEX.move_to_end(key)
            return cached
    projected = _project_deadline_windows(operation, year)
    with _DEADLINE_WINDOW_INDEX_LOCK:
        _DEADLINE_WINDOW_INDEX[key] = projected
        _DEADLINE_WINDOW_INDEX.move_to_end(key)
        while len(_DEADLINE_WINDOW_INDEX) > _DEADLINE_WINDOW_INDEX_LIMIT:
            _DEADLINE_WINDOW_INDEX.popitem(last=False)
    return projected


def _project_deadline_windows(
    operation: PinnedAuthorityOperation,
    year: int,
) -> tuple[tuple[str, ModeloRevision, DeadlineWindowDefinition], ...]:
    """Walk the directory and hydrate the revisions that own this year's windows.

    The directory carries the metadata needed to select the owning revision;
    only revisions that canonically own a matching window are then hydrated.
    This mirrors the eager authority's ownership rule without reconstructing a
    whole model graph. Ownership is decided on the directory metadata by the
    same selector :meth:`PinnedAuthorityOperation.revision_for_context` uses,
    because that method hydrates the complete selected revision only for its
    identity to be compared here.
    """
    from ..calculations.registry.temporal import select_revision_metadata

    projected: list[tuple[str, ModeloRevision, DeadlineWindowDefinition]] = []
    for modelo_id in operation.modelo_ids():
        directory = operation.modelo_directory(modelo_id)
        for metadata in directory.revisions:
            for metadata_window in metadata.deadline_windows:
                if metadata_window.filing_year != year:
                    continue
                selected = select_revision_metadata(
                    directory,
                    filing_year=metadata_window.filing_year,
                    period=metadata_window.period.registry_token,
                )
                if selected.id != metadata.id:
                    continue
                revision = operation.revision(modelo_id, str(metadata.id))
                matching = tuple(window for window in revision.deadline_windows if window == metadata_window)
                if len(matching) != 1:
                    raise ScheduleComputationError(
                        translated_message=_SCHEDULE_COMPUTATION_MESSAGE_KEY,
                        context={
                            "registry_stage": "deadline_window_projection",
                            "modelo": modelo_id,
                            "revision": str(metadata.id),
                            "filing_year": year,
                        },
                    )
                projected.append((modelo_id, revision, matching[0]))
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
    return tuple(projected)


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
        due_soon_days: int = _DEFAULT_DUE_SOON_DAYS,
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
        obligations: list[ModeloDeadline] = []
        with self._operation_context() as operation:
            windows = self._deadline_windows(year, operation=operation)
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
        obligations.sort(key=lambda o: (o.closes_on, o.modelo, o.period.filing_year, o.period.registry_token))
        if not obligations and not windows:
            raise NoDeadlineWindowsError(
                translated_message=_MISSING_WINDOWS_MESSAGE_KEY,
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

    def _obligation_for_window(
        self,
        *,
        profile: TaxpayerProfile,
        modelo: str,
        revision: ModeloRevision,
        window: DeadlineWindowDefinition,
        reference_today: date,
        operation: PinnedAuthorityOperation,
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
        condition_text = self._evaluate_conditions(
            profile,
            window.applicability_conditions,
            mode=window.applicability_condition_mode,
        )
        if condition_text is None:
            return None
        if _window_outside_activity_period(
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
        obligation_status = classify_obligation_status(window.closes_on, reference_today, self.due_soon_days)
        return ModeloDeadline(
            modelo=Modelo(modelo),
            period=window.period,
            opens_on=window.opens_on,
            closes_on=window.closes_on,
            payment_cutoff_on=window.payment_cutoff_on,
            status=obligation_status,
            applies_because=condition_text,
            boe_references=window.legal_refs,
            recovery=_overdue_recovery_or_none(
                obligation_status=obligation_status,
                reference_today=reference_today,
                window=window,
                modelo=modelo,
                operation=operation,
            ),
        )

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
                translated_message=_MISSING_WINDOWS_MESSAGE_KEY,
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
    ) -> tuple[tuple[str, ModeloRevision, DeadlineWindowDefinition], ...]:
        from ..calculations.registry.errors import RegistryError

        try:
            if operation is not None:
                return indexed_deadline_windows(operation, year)
            with self._operation_context() as selected_operation:
                return indexed_deadline_windows(selected_operation, year)
        except RegistryError as exc:
            raise ScheduleComputationError(
                translated_message=_SCHEDULE_COMPUTATION_MESSAGE_KEY,
                context={
                    "registry_stage": "validation",
                    "filing_year": year,
                    "registry_error_type": type(exc).__name__,
                },
            ) from exc

    def deadline_windows(self, year: int) -> tuple[tuple[str, ModeloRevision, DeadlineWindowDefinition], ...]:
        """Return validated registry deadline windows for ``year``.

        This read-only facade lets application projections inspect the same
        registry surface used by :meth:`compute` without reaching into engine
        implementation details.
        """
        with self._operation_context() as operation:
            return self._deadline_windows(year, operation=operation)

    @staticmethod
    def _schedule_applies(profile: TaxpayerProfile, revision: ModeloRevision, window: DeadlineWindowDefinition) -> bool:
        from ..calculations.registry.schedules import applicable_filing_schedules

        if not revision.filing_schedules:
            return True
        return bool(applicable_filing_schedules(revision, profile, period=_window_registry_period(window)))

    def schedule_applies(
        self,
        profile: TaxpayerProfile,
        revision: ModeloRevision,
        window: DeadlineWindowDefinition,
    ) -> bool:
        """Return whether a validated filing schedule applies to ``profile``.

        Args:
            profile: The :class:`TaxpayerProfile` whose declared facts are
                checked against the schedule.
            revision: The :class:`ModeloRevision` whose filing schedules are
                consulted.
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
                translated_message=_SCHEDULE_COMPUTATION_MESSAGE_KEY,
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
    days_late = (reference_today - window.closes_on).days
    if days_late < 1:
        return None
    try:
        return build_recovery_for_overdue(
            closes_on=window.closes_on,
            reference_today=reference_today,
            modelo=modelo,
            period=window.period,
            bands=load_recargo_bands(operation=operation),
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
    is already overdue (or the schedule is empty).

    Args:
        schedule: The :class:`Schedule` to scan for upcoming obligations.
        today: Reference date. Defaults to the canonical Europe/Madrid civil
            date returned by :func:`cadrumo.core.time.clock.today_madrid`.

    Returns:
        The earliest non-overdue :class:`ModeloDeadline`, or ``None``
        if no such obligation exists.
    """
    reference_today = today or today_madrid()
    upcoming = [o for o in schedule.obligations if o.closes_on >= reference_today]
    if not upcoming:
        return None
    upcoming.sort(key=lambda o: (o.closes_on, o.modelo, o.period.filing_year, o.period.registry_token))
    return upcoming[0]


@runtime_checkable
class ScheduleProducer(Protocol):
    """Structural surface over :class:`DeadlineEngine.compute`.

    :func:`compute_obligation_schedule` is typed against this Protocol
    rather than the concrete :class:`DeadlineEngine` so the workflow
    engine — which injects a protocol-typed deadline engine — and the
    state projection — which uses a concrete :class:`DeadlineEngine` —
    can both feed the same single-producer function.
    """

    due_soon_days: int

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
    engine: ScheduleProducer,
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
            :class:`ScheduleProducer` — a concrete
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
