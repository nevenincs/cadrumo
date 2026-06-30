"""Relation prefill: resolve registry relations from prior filings.

One of three distinct prefill tiers, NOT to be merged: this is the
RELATION tier (cross-revision aggregations declared as
``RelationDefinition`` records). The other two are the previous-filing
direct-carry tier (:mod:`aeat.application.calculations._binding_prefill`)
and the AEAT borrador pre-fill tier (the registry ``aeat_prefilled`` flag,
an AEAT-live source). Each names a different mechanism and source; they
share only the word "prefill".

Sits between the engine and the local observation store. The engine
asks "what's the resolved value of every relation this revision
declares?" and this module answers by consulting a
:class:`RegistrySnapshot` to enumerate the declared relations:

1. Reading the revision's relations to determine ``source_modelo``,
   ``source_revision_selector``, ``source_periods``, ``source_casilla_id``,
   and ``aggregation.op``.
2. Scanning the local
   :class:`~aeat.application.calculations.CalculationObservationRepository`
   for prior :class:`RegistryModeloObservation` filings matching the source
   quadruple.
3. Folding the source filings' casilla values through the declared
   aggregation op (``sum``, ``copy``).
4. Returning a
   :class:`~aeat.application.storage.calc_sheets._records.RelationValues`
   record stamped with provenance the apply adapter writes onto the workbook
   so the pull adapter can detect stale prefills.

When no prior filings exist for a relation, the resolver returns a
:class:`~aeat.application.storage.calc_sheets._records.RelationValue` with
``value=None`` and ``provenance="operator_manual"`` so the engine emits a
blank cell the operator must fill by hand.

This is the local-tier prefill. The AEAT-live tier (parsing
justificantes from Sede) lives in a separate adapter that produces
the same
:class:`~aeat.application.storage.calc_sheets._records.RelationValues`
shape; callers route between tiers based
on the operator's preferences and the local store's coverage.

See Also:
    :class:`~aeat.application.calculations.RelationPrefillSourceResolver`
        Source-mesh adapter that exposes resolved relations as
        :class:`~aeat.application.aggregation.CalculationSourceResolution`.
    :func:`aeat.domain.calculations.registry.relation_source_requirements`
        Registry authority that derives the source filings required by a
        relation.
    :func:`aeat.domain.calculations.registry.materialize_relation_binding_values`
        Bridge from resolved relation values to declared ``relation_prefill``
        binding slots.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Final

from ...adapters.persistence.storage.errors import ClassificationError, DecryptionError, EnvelopeVersionError
from ...application.storage.calc_sheets._records import RelationValue, RelationValues
from ...core import BindingSourceKind, Modelo, Period
from ...core.logging import get_logger
from ...core.parsing import parse_iso8601_date
from ...core.time import now
from ...domain.calculations.registry import (
    RegistryFoldRequirement,
    RegistryModeloObservation,
    RegistrySnapshot,
    RegistryValidationError,
    RelationId,
    materialize_relation_binding_values,
    relation_source_requirements,
    resolve_observed_requirement_value,
)
from ..aggregation._source_mesh import (
    CalculationSourceContext,
    CalculationSourceDiagnostic,
    CalculationSourceProvenance,
    CalculationSourceResolution,
    storage_degradation_resolution,
)
from ._m111_no_retenciones import (
    is_m111_no_retenciones_period,
    m111_no_retenciones_periods_for_bucket,
)
from ._observations_repository import CalculationObservationRepository
from ._revision_carry_gate import revision_carry_outcome

if TYPE_CHECKING:
    from ...domain.deadlines import EntityType

_LOCAL_FILING_PROVENANCE: Final = "local_filing"
_STORAGE_DEGRADATION_ERRORS = (ClassificationError, DecryptionError, EnvelopeVersionError)
_ECONOMIC_ACTIVITY_CATEGORY: Final = "actividad_economica"
_DIRECT_ESTIMATION_REGIMES: Final = frozenset({"directa_normal", "directa_simplificada"})
_log = get_logger(__name__)


def _gather_observations_for_snapshot(
    snapshot: RegistrySnapshot,
    *,
    repository: CalculationObservationRepository,
    activity_start_date: date | None = None,
    m111_no_retenciones_periods: frozenset[tuple[int, str]] | None = None,
) -> tuple[RegistryModeloObservation, ...]:
    """Collect every observation a relation in ``snapshot.revision`` could need.

    Uses the registry relation requirement resolver to compute the set of
    ``(source_modelo, filing_year, period)`` requirements, and pulls matching
    :class:`RegistryModeloObservation` rows from
    :class:`~aeat.application.calculations.CalculationObservationRepository`.
    Returns the union (deduplicated) so the runtime resolver can fold them
    through the declared aggregation in one pass. ``activity_start_date`` scopes
    out source periods strictly before the operator's activity start (a
    mid-year-start filer has no obligation for the pre-start quarters), so the
    gather set matches the scoped requirement set the resolver folds.
    """
    needed: dict[tuple[str, int, str], RegistryModeloObservation] = {}
    requirements = _scoped_relation_source_requirements(
        snapshot,
        activity_start_date,
        m111_no_retenciones_periods=m111_no_retenciones_periods,
    )
    for requirement in requirements:
        for period in requirement.periods:
            payload = repository.load_observation(
                requirement.source_modelo,
                Period.from_year_and_code(requirement.filing_year, period),
            )
            if payload is None:
                continue
            # R2 carry gate (shared with binding-prefill and cross-period
            # clean-state): re-confirm the carried observation's revision stamp
            # against the law-determined revision. A divergent stamp means the
            # prior was filed under a revision that is no longer the law-determined
            # revision for its source context; drop it from the fold rather than
            # silently injecting a stale-revision value into the relation.
            obs = payload.observation
            diverges, _advisory = revision_carry_outcome(
                payload.stamped_revision_id,
                source_modelo=obs.modelo,
                source_filing_year=obs.filing_year,
                source_period=obs.period,
            )
            if diverges:
                continue
            key = (obs.modelo, obs.filing_year, obs.period)
            needed.setdefault(key, obs)
    return tuple(needed.values())


def _provenance_note(
    relation_id: RelationId,
    source_modelo: str,
    source_periods: tuple[str, ...],
    source_year: int,
    resolved_at: datetime,
) -> str:
    period_text = "+".join(source_periods) if source_periods else "(any)"
    when = resolved_at.isoformat()
    return (
        f"prefilled from operator's local filing of modelo {source_modelo} "
        f"{period_text} {source_year} (resolved {when})"
    )


def _relation_source_filing_year(relation: object, *, filing_year: int) -> int:
    selector = relation.source_revision_selector
    if selector.year is not None:
        return selector.year
    return filing_year + (selector.filing_year_delta or 0)


def _profile_path_values_for_bucket(bucket_id: str) -> dict[str, str] | None:
    """Wizard-free canonical projection of the bucket's profile, or ``None`` when absent.

    Reads the operator profile through the SINGLE projection
    (:func:`record_to_path_values`) WITHOUT building the full
    :class:`TaxpayerProfile` (which calls ``get_setup_flow()`` and so requires
    the wizard ``SETUP_FLOW`` catalogue). This decouples the engine's first-year
    / activity-start derivation from the wizard catalogue, so it resolves
    identically in a non-CLI calc context (where the catalogue may be
    unregistered) instead of silently failing closed — matching the verify
    gate's threaded-in ``workflow_profile.activity_start_date`` semantics.
    Returns ``None`` only when there is genuinely no profile for the bucket.
    """
    from ...domain.user_profile import ProfileNotFoundError
    from ..user_profile._profile_repository import ProfileRepository
    from ..user_profile._projections import record_to_path_values

    try:
        aggregate = ProfileRepository().load(bucket_id)
    except ProfileNotFoundError:
        return None
    return record_to_path_values(aggregate.record)


def _contains_profile_token(raw: object, token: str) -> bool | None:
    """Return whether a profile projection value contains ``token``, or None if absent."""
    if raw is None:
        return None
    if isinstance(raw, str):
        stripped = raw.strip()
        if not stripped:
            return None
        return token in {item.strip() for item in stripped.replace(";", ",").split(",") if item.strip()}
    try:
        return token in set(raw)  # type: ignore[arg-type]
    except TypeError:
        return False


def _pagos_fraccionados_not_applicable_source_modelos(bucket_id: str) -> frozenset[str]:
    """Return M130/M131 source modelos positively not applicable for the bucket profile.

    This mirrors the clean-state profile split: no actividad economica means
    neither quarterly pagos-fraccionados modelo applies; direct estimation means
    M130 applies and M131 does not; objective estimation means M131 applies and
    M130 does not. Missing profile facts fail closed by returning an empty set.
    """
    values = _profile_path_values_for_bucket(bucket_id)
    if values is None:
        return frozenset()

    has_economic_activity = _contains_profile_token(
        values.get("taxpayer_type.irpf_income_categories"),
        _ECONOMIC_ACTIVITY_CATEGORY,
    )
    if has_economic_activity is False:
        return frozenset({str(Modelo.M130), str(Modelo.M131)})
    if has_economic_activity is None:
        return frozenset()

    estimation_regime = str(values.get("irpf.estimation_regime") or "").strip()
    if estimation_regime in _DIRECT_ESTIMATION_REGIMES:
        return frozenset({str(Modelo.M131)})
    if estimation_regime == "objetiva":
        return frozenset({str(Modelo.M130)})
    return frozenset()


def _parse_canonical_iso_date(raw: str | None) -> date | None:
    """Parse a canonical ISO-8601 ``censo.*`` date projection value, or ``None``."""
    return parse_iso8601_date(raw)


def _parse_canonical_decimal(raw: str | None) -> Decimal | None:
    """Parse a canonical decimal projection value, or ``None`` when absent / malformed."""
    if not raw:
        return None
    from decimal import InvalidOperation

    try:
        return Decimal(raw)
    except (InvalidOperation, ValueError):
        return None


def _entity_type_from_token(raw: str | None) -> EntityType | None:
    """Map a raw ``taxpayer_type.entity_type`` token to :class:`EntityType`, or ``None``."""
    if not raw:
        return None
    from ...domain.deadlines import EntityType

    try:
        return EntityType(raw)
    except ValueError:
        return None


def _first_year_modalidad_cuota_no_m202(bucket_id: str, *, filing_year: int) -> bool:
    """Engine-side counterpart of the clean-state first-year-fractional suppression (IS-3).

    Reads the modality inputs (entity type, INCN) and the activity-start date off
    the WIZARD-FREE profile projection (:func:`_profile_path_values_for_bucket`)
    and applies the SINGLE modality definition
    (:func:`modelo_202_modality_from_inputs`) — no duplicated INCN/threshold
    logic, and NO dependency on the wizard ``SETUP_FLOW`` catalogue (so a non-CLI
    calc context resolves the first-year relaxation correctly instead of silently
    failing closed). Fail-closed: a missing profile, an unparsable entity type, a
    missing activity-start date, or any modality other than ``ART_40_2_OPTIONAL``
    (i.e. ``ART_40_3_MANDATORY`` / ``INCOMPLETE``) returns ``False`` — the Modelo
    202 relation stays unresolved and the gate keeps blocking, never a silent
    under-declaration. ADR 2026-06-19-m202-first-period-attestation.
    """
    from ...domain.calculations.registry import Modelo202Modality, modelo_202_modality_from_inputs

    values = _profile_path_values_for_bucket(bucket_id)
    if values is None:
        return False
    modality = modelo_202_modality_from_inputs(
        entity_type=_entity_type_from_token(values.get("taxpayer_type.entity_type")),
        incn_prior_12_months=_parse_canonical_decimal(values.get("taxpayer_type.incn_prior_12_months")),
    ).modality
    if modality is not Modelo202Modality.ART_40_2_OPTIONAL:
        return False
    activity_start_date = _parse_canonical_iso_date(values.get("censo.activity_start_date"))
    if activity_start_date is None:
        return False
    return activity_start_date.year >= filing_year


def _activity_start_date_for_bucket(bucket_id: str) -> date | None:
    """Operator-declared activity-start date for ``bucket_id``, or ``None``.

    Reads ``censo.activity_start_date`` off the WIZARD-FREE profile projection
    (:func:`_profile_path_values_for_bucket`) — the SAME value the cross-period
    clean-state gate partitions against (the verify gate threads it in as
    ``workflow_profile.activity_start_date``), so gate and engine share one
    activity-start source with no wizard-catalogue dependency. Fail-safe: a
    missing profile or an absent / malformed date returns ``None`` — no period is
    scoped and the resolver keeps its full all-quarters behaviour (never a silent
    drop).
    """
    values = _profile_path_values_for_bucket(bucket_id)
    if values is None:
        return None
    return _parse_canonical_iso_date(values.get("censo.activity_start_date"))


def _scoped_relation_source_requirements(
    snapshot: RegistrySnapshot,
    activity_start_date: date | None,
    *,
    m111_no_retenciones_periods: frozenset[tuple[int, str]] | None = None,
) -> tuple[RegistryFoldRequirement, ...]:
    """Return ``relation_source_requirements`` with no-obligation periods scoped out.

    A quarterly source period STRICTLY before the operator-declared activity
    start is a period in which the taxpayer had no filing obligation, so its
    absence must NOT unresolve the whole fold (the partial-year-start
    enhancement for a mid-year-start filer). Reuses the cross-period clean-state
    gate's ``_period_strictly_before_activity_start`` predicate - one shared
    partition governs both the gate and the relation fold-in
    (one-aggregation-path; no parallel scoping math). Non-calendar instalment
    claves (1P/2P/3P) have no date span and are never scoped, so sociedad
    Modelo 202 cumulation is unaffected. A genuinely-absent IN-SCOPE quarter
    still unresolves the requirement downstream, preserving
    ``no-silent-under-declaration``. Returns the requirements unchanged when
    ``activity_start_date`` is ``None`` (the common full-year / fail-closed
    case). Explicit M111 no-retenciones period attestations also scope out only
    the named source periods: AEAT instructions say no M111 should be presented
    when no subject rents were paid, so M190 can fold the remaining filed
    quarters without requiring a nonexistent blank M111.
    """
    requirements = relation_source_requirements(
        snapshot.revision,
        filing_year=snapshot.filing_year,
        period=snapshot.period,
    )
    attested_m111_periods = m111_no_retenciones_periods or frozenset()
    if activity_start_date is None and not attested_m111_periods:
        return requirements

    scoped: list[RegistryFoldRequirement] = []
    for requirement in requirements:
        kept = tuple(
            token
            for token in requirement.periods
            if not _relation_period_scoped_out(
                requirement.source_modelo,
                requirement.filing_year,
                token,
                activity_start_date=activity_start_date,
                m111_no_retenciones_periods=attested_m111_periods,
            )
        )
        if len(kept) == len(requirement.periods):
            scoped.append(requirement)
        elif kept:
            kept_filing = tuple(
                period
                for period in requirement.filing_periods
                if period.registry_token in kept
            )
            scoped.append(requirement.model_copy(update={"periods": kept, "filing_periods": kept_filing}))
        # else: EVERY source period is strictly pre-activity → no obligation at
        # all; drop the requirement (its ``periods`` field is min_length=1 and
        # cannot be emptied). The relation then resolves to None as before.
    return tuple(scoped)


def _relation_period_scoped_out(
    source_modelo: str,
    filing_year: int,
    period_token: str,
    *,
    activity_start_date: date | None,
    m111_no_retenciones_periods: frozenset[tuple[int, str]],
) -> bool:
    """Return whether a relation source period is absent by explicit no-obligation evidence."""
    if is_m111_no_retenciones_period(
        source_modelo=source_modelo,
        filing_year=filing_year,
        period_token=period_token,
        attested_periods=m111_no_retenciones_periods,
    ):
        return True
    if activity_start_date is None:
        return False
    from ._cross_period_clean_state import _period_strictly_before_activity_start

    return _period_strictly_before_activity_start(
        Period.from_year_and_code(filing_year, period_token),
        activity_start_date,
    )


def resolve_relations_from_local_store(
    snapshot: RegistrySnapshot,
    *,
    repository: CalculationObservationRepository | None = None,
    captured_at: datetime | None = None,
    modelo_202_first_year_cuota: bool = False,
    activity_start_date: date | None = None,
    m111_no_retenciones_periods: frozenset[tuple[int, str]] | None = None,
    not_applicable_source_modelos: frozenset[str] | None = None,
) -> RelationValues:
    """Build a relation-value record from the local observation store.

    Args:
        snapshot: The :class:`RegistrySnapshot` whose declared relations are
            resolved from prior observation records in the local store.
        repository: Optional observation repository. Defaults to the active
            profile's
            :class:`~aeat.application.calculations.CalculationObservationRepository`.
        captured_at: Optional timestamp for relation provenance. Defaults to
            the current clock.
        modelo_202_first_year_cuota: When ``True`` (IS-3), an otherwise-unresolved
            Modelo 202 (``source_modelo == "202"``) fold-in relation resolves to
            ``0`` instead of ``None`` — a first-year IS filer under modalidad cuota
            (LIS art. 40.2) has no pago-fraccionado obligation. The caller derives
            this fail-closed (only for a Modelo 200 target); a resolved M202 value
            is never overridden.
        activity_start_date: When set (IRPF-1), source periods strictly before the
            operator's activity start are scoped out of every relation requirement,
            so a mid-year-start filer folds only the quarters it actually had an
            obligation for instead of leaving the annual fold unresolved. ``None``
            (the default / fail-closed case) keeps the full all-quarters behaviour.
        m111_no_retenciones_periods: Explicit ``(year, period)`` M111 no-obligation
            attestations. Each named source period is removed from M111 relation
            folds only; unknown/non-M111 periods keep the normal filing-grade
            requirement.
        not_applicable_source_modelos: Source modelos positively determined as
            not applicable for this bucket profile. M100's mutually exclusive
            M130/M131 pagos-fraccionados relations use this to resolve the absent
            leg to explicit zero instead of requiring fake zero filings.

    Returns a
    :class:`~aeat.application.storage.calc_sheets._records.RelationValues`
    whose ``values`` tuple has one
    :class:`~aeat.application.storage.calc_sheets._records.RelationValue` per
    relation declared in the snapshot's revision, with provenance stamped per
    entry. Relations the local store cannot resolve get ``value=None`` and
    ``provenance="operator_manual"`` so the engine emits a blank cell the
    operator can fill by hand.
    """
    repo = repository if repository is not None else CalculationObservationRepository()
    when = captured_at if captured_at is not None else now()
    if activity_start_date is None:
        # Default to the active bucket's activity start so BOTH live surfaces scope
        # identically (one-aggregation-path: the mesh/calculate path passes an
        # explicit value from its context bucket; the Sheets-pull path calls this
        # bare). An explicit caller value (e.g. a deterministic test) is never
        # overridden; absent an active bucket, derivation returns None (no scoping).
        from ...core import resolve_active_bucket_id

        active_bucket_id = resolve_active_bucket_id()
        if active_bucket_id is not None:
            activity_start_date = _activity_start_date_for_bucket(active_bucket_id)
    if m111_no_retenciones_periods is None:
        from ...core import resolve_active_bucket_id

        active_bucket_id = resolve_active_bucket_id()
        m111_no_retenciones_periods = (
            m111_no_retenciones_periods_for_bucket(active_bucket_id)
            if active_bucket_id is not None
            else frozenset()
        )
    if not_applicable_source_modelos is None:
        from ...core import resolve_active_bucket_id

        active_bucket_id = resolve_active_bucket_id()
        not_applicable_source_modelos = (
            _pagos_fraccionados_not_applicable_source_modelos(active_bucket_id)
            if active_bucket_id is not None
            else frozenset()
        )
    observations = _gather_observations_for_snapshot(
        snapshot,
        repository=repo,
        activity_start_date=activity_start_date,
        m111_no_retenciones_periods=m111_no_retenciones_periods,
    )
    requirements_by_relation = {
        relation_id: requirement
        for requirement in _scoped_relation_source_requirements(
            snapshot,
            activity_start_date,
            m111_no_retenciones_periods=m111_no_retenciones_periods,
        )
        for relation_id in requirement.relation_ids
    }

    resolved_map = _resolve_available_relation_values(observations, requirements_by_relation=requirements_by_relation)

    values: list[RelationValue] = []
    for relation in snapshot.revision.relations:
        requirement = requirements_by_relation.get(relation.id)
        target_year = (
            requirement.filing_year
            if requirement is not None
            else _relation_source_filing_year(relation, filing_year=snapshot.filing_year)
        )
        source_periods = requirement.periods if requirement is not None else tuple(relation.source_periods)
        resolved = resolved_map.get(relation.id)
        if resolved is None:
            # IS-3 / ADR 2026-06-19-m202-first-period-attestation: a first-year IS
            # filer under modalidad cuota (LIS art. 40.2) has no Modelo 202
            # pago-fraccionado obligation, so the M202 fold-in relation has no
            # source filing to resolve. Resolve it to 0 (rather than leaving it
            # None, which would crash draft-build on the cuota-diferencial formula
            # that requires the value). Fail-closed: only when the caller derived
            # the first-year-modalidad-cuota flag AND the source is Modelo 202 — a
            # genuinely-resolved M202 value, modalidad base, or an undeterminable
            # modality is never zeroed here. The clean-state gate surfaces the
            # operator-facing advisory; this mirrors that single determination.
            if (
                modelo_202_first_year_cuota
                and requirement is not None
                and requirement.source_modelo == str(Modelo.M202)
            ):
                values.append(
                    RelationValue(
                        relation=relation.id,
                        value=Decimal("0"),
                        provenance="operator_manual",
                        source_filing_year=target_year,
                        source_periods=source_periods,
                        resolved_at=when,
                        note=(
                            "first-year IS filer under modalidad cuota (LIS art. 40.2): no Modelo 202 "
                            "pago-fraccionado obligation; relation resolved to 0 (see verify advisory)"
                        ),
                    ),
                )
                continue
            if requirement is not None and requirement.source_modelo in not_applicable_source_modelos:
                values.append(
                    RelationValue(
                        relation=relation.id,
                        value=Decimal("0"),
                        provenance="operator_manual",
                        source_filing_year=target_year,
                        source_periods=source_periods,
                        resolved_at=when,
                        note=(
                            f"source modelo {requirement.source_modelo} is not applicable for the bucket "
                            "profile; relation resolved to 0 without a synthetic filing"
                        ),
                    ),
                )
                continue
            values.append(RelationValue(relation=relation.id, value=None))
            continue
        values.append(
            RelationValue(
                relation=relation.id,
                value=Decimal(resolved),
                provenance=_LOCAL_FILING_PROVENANCE,
                source_filing_year=target_year,
                source_periods=source_periods,
                resolved_at=when,
                note=_provenance_note(
                    relation.id,
                    relation.source_modelo,
                    source_periods,
                    target_year,
                    when,
                ),
            ),
        )
    return RelationValues(values=tuple(values))


def _resolve_available_relation_values(
    observations: tuple[RegistryModeloObservation, ...],
    *,
    requirements_by_relation: dict[RelationId, RegistryFoldRequirement],
) -> dict[RelationId, Decimal]:
    """Resolve each relation requirement independently from available observations."""
    by_requirement = {requirement: requirement for requirement in requirements_by_relation.values()}
    resolved: dict[RelationId, Decimal] = {}
    for requirement in by_requirement:
        try:
            value = resolve_observed_requirement_value(requirement, observations)
        except RegistryValidationError as exc:
            _log.warning(
                "relation prefill: relation requirement %s remains operator-manual: %s",
                requirement.relation_ids,
                exc,
            )
            continue
        for relation_id in requirement.relation_ids:
            resolved[relation_id] = value
    return resolved


def _formula_relation_ids(snapshot: RegistrySnapshot) -> frozenset[RelationId]:
    relation_ids: set[RelationId] = set()
    for formula in snapshot.revision.formulas:
        _collect_expression_relation_ids(formula.expression, relation_ids)
    return frozenset(relation_ids)


def _collect_expression_relation_ids(expression: object, relation_ids: set[RelationId]) -> None:
    relation_id = getattr(expression, "relation", None)
    if relation_id is not None:
        relation_ids.add(relation_id)
    for arg in getattr(expression, "args", ()):
        _collect_expression_relation_ids(arg, relation_ids)


def _unresolved_relation_diagnostics(
    *,
    unresolved_relation_ids: frozenset[RelationId],
    requirements_by_relation: Mapping[RelationId, RegistryFoldRequirement],
    resolver_id: str,
) -> tuple[CalculationSourceDiagnostic, ...]:
    diagnostics: list[CalculationSourceDiagnostic] = []
    for relation_id in sorted(unresolved_relation_ids):
        requirement = requirements_by_relation.get(relation_id)
        if requirement is None:
            diagnostics.append(
                CalculationSourceDiagnostic(
                    reason="source_issue",
                    source_kind="relation_prefill",
                    resolver_id=resolver_id,
                    relation_id=relation_id,
                    message=f"relation {relation_id!r} has no resolved source filing",
                ),
            )
            continue
        period_text = ",".join(requirement.periods)
        binding_id = requirement.target_bindings[0] if len(requirement.target_bindings) == 1 else None
        diagnostics.append(
            CalculationSourceDiagnostic(
                reason="source_issue",
                source_kind="relation_prefill",
                resolver_id=resolver_id,
                binding_id=binding_id,
                relation_id=relation_id,
                message=(
                    f"relation {relation_id!r} requires modelo {requirement.source_modelo} "
                    f"{requirement.filing_year} periods {period_text} output {requirement.source_casilla_ids[0]}; "
                    "the source filing is missing or incomplete"
                ),
            ),
        )
    return tuple(diagnostics)


class RelationPrefillSourceResolver:
    """Source-mesh adapter for local ``relation_prefill`` values.

    Resolves registry relations through :func:`resolve_relations_from_local_store`,
    materialises resolved relation values into declared target-binding slots, and
    returns a :class:`~aeat.application.aggregation.CalculationSourceResolution`
    carrying relation values, binding values, diagnostics for unresolved formula
    relations, and provenance for local
    :class:`RegistryModeloObservation` filings.
    """

    resolver_id = "relation_prefill"
    owned_sources: tuple[BindingSourceKind, ...] = (BindingSourceKind.RELATION_PREFILL,)

    def __init__(
        self,
        *,
        repository: CalculationObservationRepository | None = None,
        registry_snapshot: RegistrySnapshot | None = None,
        captured_at: datetime | None = None,
    ) -> None:
        self._repository = repository
        self._registry_snapshot = registry_snapshot
        self._captured_at = captured_at

    def resolve(self, context: CalculationSourceContext) -> CalculationSourceResolution:
        snapshot = self._registry_snapshot
        if snapshot is None:
            from ...core.resources import resources

            snapshot = resources().modelos.authority.snapshot(
                context.modelo,
                filing_year=context.filing_year,
                period=context.period.registry_token,
            )
        # Activity-start scoping (IRPF-1): a mid-year-start filer has no obligation
        # for source quarters strictly before the activity start, so those quarters
        # are scoped out of the relation fold so their absence does not unresolve
        # the whole fold. Derived once from the bucket profile and shared by the
        # resolution and the diagnostic so both see the same scoped requirement set.
        activity_start_date = _activity_start_date_for_bucket(str(context.bucket_id))
        m111_no_retenciones_periods = m111_no_retenciones_periods_for_bucket(str(context.bucket_id))
        not_applicable_source_modelos = _pagos_fraccionados_not_applicable_source_modelos(str(context.bucket_id))
        try:
            relation_values = resolve_relations_from_local_store(
                snapshot,
                repository=self._repository,
                captured_at=self._captured_at or context.calculated_at,
                # Scope the first-year M202 zero-resolution to the Modelo 200 annual
                # fold-in target only — NEVER to a Modelo 202 snapshot's own
                # intra-year cumulation (2P folds 1P, also source_modelo 202), which
                # must keep its real prior-instalment values.
                modelo_202_first_year_cuota=(
                    str(context.modelo) == str(Modelo.M200)
                    and _first_year_modalidad_cuota_no_m202(
                        str(context.bucket_id),
                        filing_year=context.filing_year,
                    )
                ),
                activity_start_date=activity_start_date,
                m111_no_retenciones_periods=m111_no_retenciones_periods,
                not_applicable_source_modelos=not_applicable_source_modelos,
            )
        except _STORAGE_DEGRADATION_ERRORS as exc:
            return storage_degradation_resolution(
                resolver_id=self.resolver_id,
                owned_sources=self.owned_sources,
                source_kinds=self.owned_sources,
                error=exc,
            )
        requirements_by_relation = {
            relation_id: requirement
            for requirement in _scoped_relation_source_requirements(
                snapshot,
                activity_start_date,
                m111_no_retenciones_periods=m111_no_retenciones_periods,
            )
            for relation_id in requirement.relation_ids
        }
        resolved = tuple(item for item in relation_values.values if item.value is not None)
        formula_relation_ids = _formula_relation_ids(snapshot)
        unresolved_relation_ids = frozenset(
            item.relation
            for item in relation_values.values
            if item.value is None and item.relation in formula_relation_ids
        )
        # Narrow silent gap (no-silent-under-declaration): a declared relation
        # that resolves to no value, is referenced by no formula, AND whose
        # ``target_binding`` is NOT a declared binding on the revision produces
        # neither a value, nor a materialised binding slot, nor a diagnostic — its
        # absence reaches nothing observable. Surface a non-blocking advisory for
        # exactly that orphaned case. A non-formula relation whose target_binding
        # IS a declared binding still materialises an (absent/zero) slot the engine
        # threads, which is the intended cold-start behaviour for the cross-modelo
        # carries (M200/M202/M100), so it is deliberately NOT flagged here.
        declared_binding_ids = frozenset(binding.id for binding in snapshot.revision.bindings)
        relation_target_binding = {relation.id: relation.target_binding for relation in snapshot.revision.relations}
        unresolved_non_formula_relation_ids = frozenset(
            item.relation
            for item in relation_values.values
            if item.value is None
            and item.relation not in formula_relation_ids
            and relation_target_binding.get(item.relation) not in declared_binding_ids
        )
        resolved_relation_values = {item.relation: item.value for item in resolved if item.value is not None}
        # Materialise the resolved relation values into their declared
        # ``target_binding`` slots HERE, inside the resolver, so the merged
        # resolution carries them in ``binding_values`` and the mesh
        # ``_claim_binding`` exclusive-ownership guard adjudicates any collision
        # with another resolver loudly (aggregation-taxonomy ADR ruling 4). This
        # replaces the silent post-mesh merge that previously let every other
        # source override a relation-materialised value without a finding.
        binding_values = materialize_relation_binding_values(
            snapshot.revision,
            resolved_relation_values,
            period=context.period.registry_token,
        )
        return CalculationSourceResolution(
            resolver_id=self.resolver_id,
            owned_sources=self.owned_sources,
            relation_values=resolved_relation_values,
            unresolved_relation_ids=tuple(sorted(unresolved_relation_ids)),
            binding_values=binding_values,
            diagnostics=_unresolved_relation_diagnostics(
                unresolved_relation_ids=unresolved_relation_ids,
                requirements_by_relation=requirements_by_relation,
                resolver_id=self.resolver_id,
            )
            + _unresolved_relation_diagnostics(
                unresolved_relation_ids=unresolved_non_formula_relation_ids,
                requirements_by_relation=requirements_by_relation,
                resolver_id=self.resolver_id,
            ),
            provenance=tuple(
                CalculationSourceProvenance(
                    source_kind="relation_prefill",
                    source_ref=(f"{item.relation}:{item.source_filing_year}:{','.join(item.source_periods)}"),
                )
                for item in resolved
            ),
        )


__all__ = ["RelationPrefillSourceResolver", "resolve_relations_from_local_store"]
