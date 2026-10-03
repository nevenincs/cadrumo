"""Filed-history discovery contracts, projections, and profile/register signals."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, Protocol

from pydantic import BaseModel, Field, field_validator

from ...core.casilla_id import CasillaId
from ...core.casilla_value_kind import CasillaValueKind
from ...core.errors.hierarchy import CadrumoError, InternalInvariantError, pydantic_validation_boundary
from ...core.filed_history_discovery_signal import FiledHistoryDiscoverySignal
from ...core.filing_year import FilingYear
from ...core.i18n.render import tr
from ...core.json_contract import Notice, NoticeSeverity
from ...core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core.period import Period
from ...core.register_scoping_signal import RegisterScopingSignal
from ...domain.calculations.registry.authority import bundled_indexed_authority
from ...domain.calculations.registry.bindings import RegistryModeloObservation
from ...domain.calculations.registry.verification_tolerance import verification_tolerance_or_exact
from ..calculations.observations_repository import require_observation_envelope_coordinates_current
from ..calculations.ports import ObservedCasillaValueProtocol
from ..storage.sync_runs.records import (
    SyncRunRecordReference,
)
from .filed_data_ports import (
    FiledDataCapturePort,
    FiledDeclarationAvailabilityReportProtocol,
    FiledEffectGuard,
)
from .filed_observation_ports import FiledObservationProtocol
from .remote_state_models import (
    FiledCapturePairOutcome,
)
from .session import SessionWriteReporter

if TYPE_CHECKING:
    from datetime import date

    from ...domain.calculations.registry.authority import PinnedAuthorityOperation
    from ...domain.deadlines.models import TaxpayerProfile
    from ..calculations.observations_repository import ObservationEnvelopePayload


class _RecaptureObservationRepository(Protocol):
    """Minimal persisted-observation read surface for divergence checks."""

    def load_observation(self, modelo: str, period: Period) -> ObservationEnvelopePayload | None:
        """Load the prior envelope for one modelo and period."""
        ...


async def discover_filed_history(
    *,
    filed_data_port: FiledDataCapturePort,
    profile: TaxpayerProfile | None = None,
    today: date | None = None,
    operation: PinnedAuthorityOperation | None = None,
    effect_guard: FiledEffectGuard | None = None,
    on_session_write: SessionWriteReporter | None = None,
) -> FiledHistoryDiscoveryReport:
    """Discover what history to walk, unioning both signals into one grid.

    Reads the register's offered option lists through the SAME verified-session
    bring-up every filed-capture path uses, so a missing or unverified auth
    session refuses here exactly as it does on the capture path rather than with
    a discovery-specific error nobody has seen before.

    Nothing is persisted and no pair is queried: this is a read of the register's
    own controls plus a pure derivation over already-persisted profile data.

    ``profile`` is optional so the register-options read can be exercised on its
    own, but omitting it means the report carries NO taxpayer-specific
    denominator — see
    :attr:`FiledHistoryDiscoveryReport.carries_a_taxpayer_specific_denominator`,
    which is the flag a caller must check before making any coverage claim.

    Args:
        filed_data_port: Filed-data capability used to discover register availability.
        profile: The taxpayer's declared :class:`TaxpayerProfile`, supplying the load-bearing
            :attr:`~core.filed_history_discovery_signal.FiledHistoryDiscoverySignal.PROFILE_APPLICABILITY`
            signal. ``None`` yields a register-options-only report.
        today: Reference date for applicability and the year span's upper bound.
            Defaults to the Madrid civil date the rest of the CLI resolves
            filing dates against.
        operation: Caller-held generation-pinned registry authority for both
            profile-derived coverage signals.
        effect_guard: Optional authorization fence around provider session publication.
        on_session_write: Record any provider session write in the operation receipt.

    Returns:
        The union :class:`FiledHistoryDiscoveryReport`.

    Raises:
        SedeNavigationError: When the session carries no persisted browser state,
            propagated unchanged from the shared register bring-up.
    """
    from ...core.time.clock import today_madrid

    availability = await filed_data_port.discover_availability(
        operation="live-expedientes-read", effect_guard=effect_guard, on_session_write=on_session_write
    )
    resolved_today = today or today_madrid()
    expected = (
        expected_filed_declaration_grid(profile, today=resolved_today, operation=operation)
        if profile is not None
        else ExpectedFiledDeclarationGrid()
    )
    scoping_signal = (
        classify_register_scoping_signal(profile, availability, today=resolved_today, operation=operation)
        if profile is not None
        else RegisterScopingSignal.INCONCLUSIVE
    )
    return filed_history_discovery_report(
        expected=expected,
        availability=availability,
        scoping_signal=scoping_signal,
    )


class ExpectedFiledDeclarationGrid(BaseModel):
    """The ``(modelo, ejercicio)`` pairs the taxpayer's OWN declared facts expect.

    Tagged :attr:`~core.filed_history_discovery_signal.FiledHistoryDiscoverySignal.PROFILE_APPLICABILITY`. This
    is the load-bearing denominator: every value in it comes from data the
    taxpayer declared during setup, walked through the same applicability
    machinery the overview calendar already reconciles obligations with, so it is
    taxpayer-specific by construction and needs no authenticated session.

    Attributes:
        modelos: Registry modelos this profile's declared facts do not rule out,
            in sorted order. A modelo the applicability engine positively
            answers "no" for is absent, and so is one the registry does not model
            at all — the latter because no declared fact feeds a verdict for it,
            so nominating it would manufacture an expectation the profile never
            made.
        ejercicios: The filing years spanned by the declared activity dates,
            newest first.
        activity_start_declared: Whether the profile declared an
            ``activity_start_date``. When ``False``, ``ejercicios`` is EMPTY and
            this grid makes no claim: it is "cannot say", never "nothing
            expected". A consumer must surface that distinction rather than
            reporting a clean zero, because a silently empty profile signal
            leaves only the signal whose informativeness is unconfirmed.
        activity_end_declared: Whether the profile declared an
            ``activity_end_date``, which caps the span. A taxpayer who ceased
            activity is not expected to have filed afterwards, and flagging
            those years as expected-but-not-found would be a false anomaly.
    """

    model_config = _STRICT_FROZEN

    modelos: tuple[str, ...] = ()
    ejercicios: tuple[int, ...] = ()
    activity_start_declared: bool = False
    activity_end_declared: bool = False

    @property
    def pairs(self) -> tuple[tuple[str, int], ...]:
        """Return every expected ``(modelo, ejercicio)`` pair, newest year first."""
        return tuple((modelo, ejercicio) for modelo in self.modelos for ejercicio in self.ejercicios)


class FiledHistoryDiscoveryPair(BaseModel):
    """One ``(modelo, ejercicio)`` pair to walk, carrying which signal nominated it.

    The signal set is what makes a zero-row outcome readable, so it travels with
    the pair rather than being discarded once the union is built. The two
    predicates below exist so no consumer re-derives the asymmetry: a caller asks
    the pair whether a zero-row result is an anomaly instead of re-checking tags
    and possibly getting the rule wrong in one of several places.

    Attributes:
        modelo: Modelo code.
        ejercicio: Filing year.
        signals: Every signal that nominated this pair, in the canonical enum
            declaration order, deduplicated. Never empty — a pair nominated by
            nothing is not walked.
    """

    model_config = _STRICT_FROZEN

    modelo: str = Field(min_length=1, max_length=8)
    ejercicio: FilingYear
    signals: tuple[FiledHistoryDiscoverySignal, ...] = Field(min_length=1)

    @field_validator("signals")
    @classmethod
    @pydantic_validation_boundary
    def _canonical_signal_order(
        cls,
        value: tuple[FiledHistoryDiscoverySignal, ...],
    ) -> tuple[FiledHistoryDiscoverySignal, ...]:
        """Dedup and canonicalise the signal set so equal nominations compare equal."""
        seen = set(value)
        return tuple(signal for signal in FiledHistoryDiscoverySignal if signal in seen)

    @property
    def expected_by_profile(self) -> bool:
        """Whether the taxpayer's own declared facts expected a filing for this pair."""
        return FiledHistoryDiscoverySignal.PROFILE_APPLICABILITY in self.signals

    @property
    def zero_rows_is_an_anomaly(self) -> bool:
        """Whether finding no declaración for this pair is worth an advisory.

        True only when the profile signal nominated the pair: the taxpayer's own
        declared facts expected a filing that was not found. A pair nominated
        ONLY by the register's option list is a plain negative however empty it
        comes back, because whether that list is scoped to this NIF at all is
        unconfirmed — treating its emptiness as a finding would raise an alert
        from a signal that may carry no information about this taxpayer.
        """
        return self.expected_by_profile


class FiledHistoryDiscoveryReport(BaseModel):
    """The union walk grid, with every pair tagged by the signal(s) behind it.

    The union is deliberately additive: the register's offered option set can
    only ever WIDEN the grid the profile expects, never narrow it and never
    substitute for it. That is why a pair present in only one signal is still
    walked, while only the profile-nominated ones can produce an anomaly.

    Attributes:
        pairs: Every pair to walk, sorted by modelo then descending ejercicio so
            recent filings are reached first.
        profile_year_span_determined: Whether the profile declared the activity
            start date the year axis needs. When ``False`` the profile signal
            contributed nothing and the report says so, rather than presenting a
            register-options-only grid as though both signals had agreed.
        register_options_read: Whether the register's option lists were read at
            all. ``False`` on the profile-only path (no live session), which is
            not a failure — the design ships fully functional without it.
    """

    model_config = _STRICT_FROZEN

    pairs: tuple[FiledHistoryDiscoveryPair, ...] = ()
    profile_year_span_determined: bool = False
    register_options_read: bool = False
    scoping_signal: RegisterScopingSignal = RegisterScopingSignal.INCONCLUSIVE

    @property
    def walk_pairs(self) -> tuple[tuple[str, int], ...]:
        """Return the plain ``(modelo, ejercicio)`` pairs to query, in walk order."""
        return tuple((pair.modelo, pair.ejercicio) for pair in self.pairs)

    @property
    def profile_expected_pairs(self) -> tuple[FiledHistoryDiscoveryPair, ...]:
        """Return only the pairs the taxpayer's declared facts expected a filing for."""
        return tuple(pair for pair in self.pairs if pair.expected_by_profile)

    @property
    def register_options_only_pairs(self) -> tuple[FiledHistoryDiscoveryPair, ...]:
        """Return the pairs nominated ONLY by the unconfirmed register option list."""
        return tuple(pair for pair in self.pairs if not pair.expected_by_profile)

    @property
    def carries_a_taxpayer_specific_denominator(self) -> bool:
        """Whether any coverage claim this report supports rests on taxpayer facts.

        ``False`` means every walked pair came from the register's offered option
        list, whose scoping is unconfirmed, so the report supports NO completeness
        claim at all — only a record of what was queried.
        """
        return bool(self.profile_expected_pairs)


def expected_filed_declaration_grid(
    profile: TaxpayerProfile,
    *,
    today: date,
    operation: PinnedAuthorityOperation | None = None,
) -> ExpectedFiledDeclarationGrid:
    """Derive the taxpayer-specific candidate grid from the profile's declared facts.

    The modelo axis reuses
    :func:`~application.overview.coverage.build_obligation_coverage`, which already
    partitions the whole AEAT obligation universe against a
    :class:`~domain.deadlines.models.TaxpayerProfile` into surfaced / confidently
    excluded / advised / out-of-scope. Nothing is re-derived here: a modelo is a
    candidate when that partition does NOT place it in a confident negative or
    out of scope.

    Two exclusions are deliberate. A modelo the registry does not model at all
    is dropped, because no declared fact produced its verdict — nominating it
    would invent an expectation the taxpayer never made and then report the
    inevitable zero rows as an anomaly. And the year axis is capped by a declared
    ``activity_end_date``, because a taxpayer who ceased activity is not expected
    to have filed afterwards.

    ``surfaced_modelos`` is passed empty on purpose. The partition is total, so
    with nothing surfaced every non-negative verdict lands in ``advised``; the
    union taken below covers both tuples anyway, so the result does not depend on
    which side a candidate falls out of.

    Args:
        profile: The taxpayer's declared three-axis :class:`TaxpayerProfile`.
        today: Reference date for applicability evaluation and the year span's
            upper bound.
        operation: Caller-held generation-pinned registry authority.

    Returns:
        The :class:`ExpectedFiledDeclarationGrid`. When the profile declared no
        activity start date the grid carries no ejercicios and says so through
        ``activity_start_declared``.
    """
    # Deferred to keep application.live's import-time graph free of the overview
    # package, which reaches back into this package for its evidence snapshots.
    # The same reason _coverage.py defers its own application.modelo lookup.
    from ..overview.coverage import CoverageAdviceReason, build_obligation_coverage

    coverage = build_obligation_coverage(profile, (), today=today, operation=operation)
    candidates = {
        *coverage.surfaced,
        *(item.modelo for item in coverage.advised if item.reason is not CoverageAdviceReason.REGISTRY_UNMODELED),
    }

    start = profile.activity_start_date
    end = profile.activity_end_date
    if start is None:
        ejercicios: tuple[int, ...] = ()
    else:
        last_year = min(today.year, end.year) if end is not None else today.year
        ejercicios = tuple(range(last_year, start.year - 1, -1))

    return ExpectedFiledDeclarationGrid(
        modelos=tuple(sorted(candidates)),
        ejercicios=ejercicios,
        activity_start_declared=start is not None,
        activity_end_declared=end is not None,
    )


def casillas_a_recapture_would_change(
    fresh: FiledObservationProtocol,
    stored: RegistryModeloObservation,
    *,
    tolerance: Decimal = Decimal("0"),
) -> tuple[CasillaId, ...]:
    """Return every casilla whose freshly captured value disagrees with the stored one.

    Derived from the observed casilla set rather than from a hand-listed field
    list, for the same reason the invoice reconfirm diff is: the failure this
    exists to catch is a comparison that OMITS a casilla, and a hand-listed set is
    precisely how that omission arrives. A newly-extracted casilla is compared the
    moment it is captured.

    Only casillas present on BOTH sides are compared. A casilla the fresh capture
    read and the stored revision never held is not a changed value -- it is a
    wider extraction -- and reporting it as a divergence would fire the advisory
    on every extraction improvement.

    NOT substitutable with the tree's other per-casilla comparators, and the
    intersection rule above is why. ``detect_casilla_divergences`` REPORTS
    absence, as missing-on-one-side rows, and the revision-vs-revision delta in
    ``application/modelo/projection.py`` treats an absent casilla as zero.
    Both of those contracts would fire this advisory on an extraction
    improvement, which is the one thing it must never do. The absence contract
    is the discriminator, not the tolerance.

    Args:
        fresh: The newly captured observation.
        stored: The prior stamped registry observation for the same key.
        tolerance: Maximum absolute delta that does not count as a change. The
            registry owns this value through
            :func:`~cadrumo.domain.calculations.registry.verification_tolerance.verification_tolerance_or_exact`.
            The default is exact equality, matching the caller's resolved
            fallback for a triple with no published contract.

    Returns:
        The changed casilla ids, sorted, so the notice text is deterministic.
    """
    # Both sides already carry the typed CasillaId, so neither is stringified:
    # erasing the alias at this boundary was drift, not normalisation.
    stored_values = {observation.casilla_id: observation.value for observation in stored.observations}
    changed: set[CasillaId] = set()
    for observed in fresh.casillas:
        casilla_id = observed.casilla_id
        if casilla_id not in stored_values:
            continue
        if observed.value_kind is not CasillaValueKind.NUMERIC:
            continue
        # The amount is read through the observation's own numeric accessor, so
        # a carrier that does not offer one is reported rather than converted by
        # hand from its lexical value.
        if not isinstance(observed, ObservedCasillaValueProtocol):
            raise InternalInvariantError("filed casilla observation carries no numeric accessor")
        try:
            fresh_value = observed.decimal_value()
        except InvalidOperation:
            # An unreadable fresh token is not evidence of a CHANGED value, and
            # claiming one would put a false amendment in front of the operator.
            # The kind check above is what makes InvalidOperation the only
            # reachable failure here: a non-numeric casilla never reaches the
            # conversion, so its own refusal cannot arrive.
            continue
        stored_value = stored_values[casilla_id]
        if not isinstance(stored_value, Decimal):
            continue
        if abs(fresh_value - stored_value) > tolerance:
            changed.add(casilla_id)
    return tuple(sorted(changed))


def classify_register_scoping_signal(
    profile: TaxpayerProfile,
    availability: FiledDeclarationAvailabilityReportProtocol,
    *,
    today: date,
    operation: PinnedAuthorityOperation | None = None,
) -> RegisterScopingSignal:
    """Say what the offered modelo set SUGGESTS about its own scoping, for free.

    The question this addresses -- is the declaraciones register's option list
    scoped to the authenticated NIF, or a static universal catalogue -- cannot be
    settled without an authorised live probe against an account with real filing
    history. Nobody has authorised one, and the design never depended on it
    resolving. What it does have is a cheap, offline, taxpayer-specific
    discriminator nobody was reading: if the register offers a modelo the
    taxpayer's own declared facts positively EXCLUDE, the list is offering
    something this taxpayer cannot have filed, which is what a universal
    catalogue looks like.

    The result is advisory only and changes nothing about what is walked. The
    offered set is unioned in additively either way, so a reading here can
    neither widen nor narrow the grid, and it MUST NOT be rendered as a settled
    answer -- see :class:`~core.register_scoping_signal.RegisterScopingSignal`, whose members are all
    hedges precisely so that it cannot be.

    The evidence is asymmetric, and so is the confidence.
    :attr:`~core.register_scoping_signal.RegisterScopingSignal.LIKELY_UNIVERSAL` is a positive
    observation: an excluded modelo was offered. Its counterpart is only ever the
    ABSENCE of that observation, which a universal catalogue also produces for a
    taxpayer whose profile excludes nothing the register lists -- so it stays
    ``LIKELY_NIF_SCOPED``, never confirmation.

    Args:
        profile: The taxpayer's declared :class:`TaxpayerProfile`, supplying the
            positively-excluded modelo set.
        availability: The register's offered option set.
        today: Reference date for applicability evaluation.
        operation: Caller-held generation-pinned registry authority.

    Returns:
        The :class:`~core.register_scoping_signal.RegisterScopingSignal` reading.
        :attr:`~core.register_scoping_signal.RegisterScopingSignal.INCONCLUSIVE` when either side of the
        comparison is empty, because then the comparison discriminates nothing.
    """
    from ..overview.coverage import build_obligation_coverage

    offered = {item.modelo for item in availability.items}
    excluded = set(build_obligation_coverage(profile, (), today=today, operation=operation).confidently_excluded)
    if not offered or not excluded:
        return RegisterScopingSignal.INCONCLUSIVE
    if offered & excluded:
        return RegisterScopingSignal.LIKELY_UNIVERSAL
    return RegisterScopingSignal.LIKELY_NIF_SCOPED


def filed_history_discovery_report(
    *,
    expected: ExpectedFiledDeclarationGrid,
    availability: FiledDeclarationAvailabilityReportProtocol | None = None,
    scoping_signal: RegisterScopingSignal = RegisterScopingSignal.INCONCLUSIVE,
) -> FiledHistoryDiscoveryReport:
    """Union the two discovery signals into one provenance-tagged walk grid.

    A pair nominated by both signals carries both tags; a pair nominated by one
    carries only that one. The union never drops a pair either signal offered,
    which is what makes the register's contribution purely coverage-widening: it
    cannot remove anything the profile expected, and it cannot lend its own pairs
    the profile signal's standing.

    Args:
        expected: The taxpayer-specific grid from
            :func:`expected_filed_declaration_grid`.
        availability: The register's offered option set, or ``None`` when the
            option lists were not read (no live session). ``None`` is a supported
            mode, not a degraded one.
        scoping_signal: Hedged reading derived while both the taxpayer profile
            and offered register options are available.

    Returns:
        The :class:`FiledHistoryDiscoveryReport` walk grid.
    """
    signals_by_pair: dict[tuple[str, int], set[FiledHistoryDiscoverySignal]] = {}
    for pair in expected.pairs:
        signals_by_pair.setdefault(pair, set()).add(FiledHistoryDiscoverySignal.PROFILE_APPLICABILITY)
    if availability is not None:
        for pair in availability.offered_pairs:
            signals_by_pair.setdefault(pair, set()).add(FiledHistoryDiscoverySignal.AEAT_REGISTER_OPTIONS)

    return FiledHistoryDiscoveryReport(
        pairs=tuple(
            FiledHistoryDiscoveryPair(modelo=modelo, ejercicio=ejercicio, signals=tuple(signals))
            for (modelo, ejercicio), signals in sorted(
                signals_by_pair.items(),
                key=lambda item: (item[0][0], -item[0][1]),
            )
        ),
        profile_year_span_determined=expected.activity_start_declared,
        register_options_read=availability is not None,
        scoping_signal=scoping_signal,
    )


class FiledHistoryPairOutcome(BaseModel):
    """What one walked pair produced, keeping a refusal distinct from a zero.

    ``refused`` is not derivable from ``row_count``. The register walker refuses a
    page whose grid declares more records than it rendered, and that refusal is
    absorbed into a failure row upstream — so a refused walk reports zero rows,
    while capture or finalization failures retain the completed walk's positive
    row count. Reading a failed walk's zero as "nothing filed" is the silent
    under-report this feature exists to remove, which is why the refusal is its
    own field and why the notices below branch on it.
    """

    model_config = _STRICT_FROZEN

    modelo: str = Field(min_length=1, max_length=8)
    ejercicio: FilingYear
    signals: tuple[FiledHistoryDiscoverySignal, ...] = Field(min_length=1)
    walk_attempted: bool
    walk_completed: bool
    row_count: int = Field(default=0, ge=0)
    reached_count: int = Field(ge=0)
    captured_count: int = Field(default=0, ge=0)
    refused: bool = False
    failure_type: str | None = Field(default=None, min_length=1, max_length=128)
    failure_message: str | None = Field(default=None, min_length=1, max_length=2048)

    def require_consistent(self) -> None:
        """Require the same actual-walk and counter invariants as bulk accounting."""
        FiledCapturePairOutcome(
            modelo=self.modelo,
            year=self.ejercicio,
            walk_attempted=self.walk_attempted,
            walk_completed=self.walk_completed,
            row_count=self.row_count,
            reached_count=self.reached_count,
            captured_count=self.captured_count,
        ).require_consistent()

    @property
    def expected_by_profile(self) -> bool:
        """Whether the taxpayer's own declared facts expected a filing here."""
        return FiledHistoryDiscoverySignal.PROFILE_APPLICABILITY in self.signals

    @property
    def is_a_genuine_empty(self) -> bool:
        """Whether this pair answered, and the answer was no filings.

        False for a refused pair however few rows it reported: a refusal is not
        an answer, so it is not an empty one either.
        """
        return self.walk_completed and not self.refused and self.row_count == 0


class FiledHistoryOnboardingRun(BaseModel):
    """One history-onboarding sweep: what was walked, captured and reconciled.

    Carries no completeness ratio, deliberately. Part of the walked grid comes
    from AEAT's offered option list, whose scoping to this NIF is unconfirmed, so
    any fraction over the grid would look like coverage while resting on a
    denominator that may have nothing to do with this taxpayer.
    :attr:`denominator_note` states in prose what the denominator was — the
    honest form of the same information.
    """

    model_config = _STRICT_FROZEN

    pairs: tuple[FiledHistoryPairOutcome, ...] = ()
    dry_run: bool = False
    captured_count: int = Field(default=0, ge=0)
    #: Units this sweep REACHED, from the accumulator tally counted in every
    #: mode. Carried separately from ``captured_count`` because that one is
    #: ``len(observation_paths)``, which a preview leaves empty -- so it
    #: cannot answer "was this sweep truncated" on the very path where the
    #: question matters most.
    reached_count: int = Field(default=0, ge=0)
    scoping_signal: RegisterScopingSignal = RegisterScopingSignal.INCONCLUSIVE
    carries_a_taxpayer_specific_denominator: bool = False
    iva_wallet_status: str = Field(default="not_attempted", min_length=1, max_length=64)
    iva_wallet_divergence: str | None = Field(default=None, min_length=1, max_length=64)
    iva_wallet_blocked: bool = False
    notificaciones_status: str = Field(default="not_attempted", min_length=1, max_length=64)
    notificaciones_row_count: int = Field(default=0, ge=0)
    stage_failures: tuple[str, ...] = ()
    sync_run_ref: SyncRunRecordReference | None = None
    evidence_notices: tuple[Notice, ...] = ()
    #: One advisory per re-captured filing whose casilla values this sweep
    #: changed, forwarded from the capture that read them before its upsert.
    recapture_notices: tuple[Notice, ...] = ()
    """Per-artefact evidence advisories raised during capture, each keeping its own reason."""

    @property
    def refused_pairs(self) -> tuple[FiledHistoryPairOutcome, ...]:
        """Return pairs that produced a failure row instead of an answer."""
        return tuple(pair for pair in self.pairs if pair.refused)

    @property
    def genuinely_empty_pairs(self) -> tuple[FiledHistoryPairOutcome, ...]:
        """Return pairs that answered with no filings."""
        return tuple(pair for pair in self.pairs if pair.is_a_genuine_empty)

    @property
    def denominator_note(self) -> str:
        """State what the coverage denominator was, and what it does not establish."""
        expected = sum(1 for pair in self.pairs if pair.expected_by_profile)
        offered_only = len(self.pairs) - expected
        if not expected:
            return tr(
                "live.filed.pull_all.denominator_note_register_only",
                offered_only=offered_only,
            )
        return tr(
            "live.filed.pull_all.denominator_note_profile",
            expected=expected,
            offered_only=offered_only,
        )


def expected_but_not_found_notice(run: FiledHistoryOnboardingRun) -> Notice | None:
    """Warn for every pair the profile expected that produced no declaración.

    Fires ONLY for pairs carrying
    :attr:`~core.filed_history_discovery_signal.FiledHistoryDiscoverySignal.PROFILE_APPLICABILITY`. A pair
    nominated only by the register's option list is never named here however
    empty it came back, because that list's informativeness for this taxpayer is
    unconfirmed — an alert raised from it could be pure noise, and an advisory
    only earns trust if every firing is a real finding.

    A REFUSED pair is also never named. It did not answer, so "the profile
    expected a filing that was not found" is not what happened; the refusal
    travels as its own failure row and its own reporting.

    Returns ``None`` when nothing qualifies, so a clean run stays quiet.
    """
    missing = tuple(pair for pair in run.pairs if pair.expected_by_profile and pair.is_a_genuine_empty)
    if not missing:
        return None
    named = ", ".join(f"{pair.modelo}/{pair.ejercicio}" for pair in missing)
    return Notice(
        severity=NoticeSeverity.WARNING,
        code="live.filed.pull_all.expected_but_not_found",
        message=tr(
            "live.filed.pull_all.expected_but_not_found",
            count=len(missing),
            pairs=named,
        ),
        context={
            "missing_count": str(len(missing)),
            "pairs": named,
            "signal": FiledHistoryDiscoverySignal.PROFILE_APPLICABILITY.value,
        },
    )


def recapture_divergence_notices(
    captured: tuple[FiledObservationProtocol, ...],
    *,
    repository: _RecaptureObservationRepository,
    operation: PinnedAuthorityOperation | None = None,
) -> tuple[Notice, ...]:
    """Warn for every re-captured filing whose casilla values changed.

    A re-capture is an unconditional upsert, so without this a corrected filing
    silently overwrites the previously observed values and the operator never
    learns their history changed. Refusing the write outright would be wrong —
    AEAT legitimately permits a complementaria — so this mirrors the shipped
    censo-divergence shape: a standing advisory, never a silent auto-resolve.

    Read BEFORE the capture is persisted; afterwards the prior values are gone.
    """
    if operation is None:
        with bundled_indexed_authority().operation() as indexed_operation:
            return recapture_divergence_notices(
                captured,
                repository=repository,
                operation=indexed_operation,
            )
    notices: list[Notice] = []
    for observation in captured:
        stored = repository.load_observation(observation.modelo, observation.period)
        if stored is None:
            continue
        require_observation_envelope_coordinates_current(stored, operation=operation)
        try:
            snapshot = operation.snapshot(
                observation.modelo,
                filing_year=observation.ejercicio,
                period=observation.period.registry_token,
            )
        except (LookupError, KeyError, AttributeError, ValueError, CadrumoError):
            tolerance = Decimal("0")
        else:
            tolerance = verification_tolerance_or_exact(snapshot)
        changed = casillas_a_recapture_would_change(observation, stored.observation, tolerance=tolerance)
        if not changed:
            continue
        named = ", ".join(changed)
        notices.append(
            Notice(
                severity=NoticeSeverity.WARNING,
                code="live.filed.pull_all.recapture_divergence",
                message=tr(
                    "live.filed.pull_all.recapture_divergence",
                    modelo=observation.modelo,
                    period=observation.period.registry_token,
                    ejercicio=observation.ejercicio,
                    count=len(changed),
                    casillas=named,
                ),
                context={
                    "modelo": observation.modelo,
                    "ejercicio": str(observation.ejercicio),
                    "period": observation.period.registry_token,
                    "changed_casillas": named,
                    "expediente_id": observation.expediente_id,
                },
            ),
        )
    return tuple(notices)


__all__ = [
    "ExpectedFiledDeclarationGrid",
    "FiledHistoryDiscoveryPair",
    "FiledHistoryDiscoveryReport",
    "FiledHistoryOnboardingRun",
    "FiledHistoryPairOutcome",
    "casillas_a_recapture_would_change",
    "classify_register_scoping_signal",
    "discover_filed_history",
    "expected_but_not_found_notice",
    "expected_filed_declaration_grid",
    "filed_history_discovery_report",
    "recapture_divergence_notices",
]
