"""Relation prefill: resolve registry relations from prior filings.

One of three distinct prefill tiers, NOT to be merged: this is the
RELATION tier (cross-revision aggregations declared as
``RelationDefinition`` records). The other two are the previous-filing
direct-carry tier (:mod:`application.calculations._binding_prefill`)
and the AEAT borrador pre-fill tier (the registry ``aeat_prefilled`` flag,
an AEAT-live source). Each names a different mechanism and source; they
share only the word "prefill".

Sits between the engine and the local observation store. The engine
asks "what's the resolved value of every relation this revision
declares?" and this module answers by consulting a
:class:`RegistrySnapshot` to enumerate the declared relations. The
same-modelo first-period default resolver reads the relations and
bindings declared on one :class:`ModeloRevision` directly:

1. Reading the revision's relations to determine ``source_modelo``,
   ``source_revision_selector``, ``source_periods``, ``source_casilla_id``,
   and ``aggregation.op``.
2. Scanning the local
   :class:`~application.calculations.CalculationObservationRepository`
   for prior :class:`RegistryModeloObservation` filings matching the source
   quadruple.
3. Folding the source filings' casilla values through the declared
   aggregation op (``sum``, ``copy``).
4. Returning a
   :class:`~application.storage.calc_sheets.RelationValues`
   record stamped with provenance the apply adapter writes onto the workbook
   so the pull adapter can detect stale prefills.

When no prior filings exist for a relation, the resolver returns a
:class:`~application.storage.calc_sheets.RelationValue` with
``value=None`` and ``provenance="operator_manual"`` so the engine emits a
blank cell the operator must fill by hand.

This is the local-tier prefill. The AEAT-live tier (parsing
justificantes from Sede) lives in a separate adapter that produces
the same
:class:`~application.storage.calc_sheets.RelationValues`
shape; callers route between tiers based
on the operator's preferences and the local store's coverage.

See Also:
    :class:`~application.calculations.RelationPrefillSourceResolver`
        Source-mesh adapter that exposes resolved relations as
        :class:`~application.aggregation.CalculationSourceResolution`.
    :func:`domain.calculations.registry.relation_source_requirements`
        Registry authority that derives the source filings required by a
        relation.
    :func:`domain.calculations.registry.materialize_relation_binding_values`
        Bridge from resolved relation values to declared ``relation_prefill``
        binding slots.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, ClassVar, Final, NamedTuple, TypedDict

from ...adapters.persistence.storage import ClassificationError, DecryptionError, EnvelopeVersionError
from ...core.modelo import Modelo
from ...core.period import Period
from ...core.casilla_id import CasillaId
from ...core.aggregation import BindingSourceKind, CalculationSourceLineageRole
from ...core.decimal import try_parse_canonical_decimal
from ...core.logging import get_logger
from ...core.parsing import parse_iso8601_date
from ...core.time import now
from ...domain.calculations.registry.authority import bundled_authority
from ...domain.calculations.registry.bindings import RegistryModeloObservation
from ...domain.calculations.registry.errors import RegistryValidationError
from ...domain.calculations.registry.handoffs import (
    relation_consumption_channels,
    relation_consumption_index,
)
from ...domain.calculations.registry.ids import (
    BindingId,
    LegalRefId,
    ModeloId,
    RelationId,
    RevisionId,
    SourceRefId,
)
from ...domain.calculations.registry.iva_wallet_relation_targets import is_iva_wallet_owned_relation_target
from ...domain.calculations.registry.observation_fold import resolve_observed_requirement_value
from ...domain.calculations.registry.queries import relations_by_target_binding
from ...domain.calculations.registry.relations import (
    RegistryFoldRequirement,
    materialize_relation_binding_values,
    relation_requirement_index,
    relation_source_requirements,
)
from ...domain.calculations.registry.schema import ModeloRevision, RegistrySnapshot
from ...domain.calculations.registry.schema_surfaces import RelationDefinition
from ..aggregation import (
    CalculationSourceContext,
    CalculationSourceDiagnostic,
    CalculationSourceProvenance,
    CalculationSourceResolution,
    storage_degradation_resolution,
)
from ..storage.calc_sheets import (
    RelationValue,
    RelationValues,
)
from ._revision_carry_gate import revision_carry_outcome
from .m111_no_retenciones import (
    is_m111_no_retenciones_period,
    m111_no_retenciones_periods_for_bucket,
)
from .observations_repository import CalculationObservationRepository

if TYPE_CHECKING:
    from ...domain.deadlines.models import EntityType

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
    :class:`~application.calculations.CalculationObservationRepository`.
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
            # against the law-determined revision. A divergent or unreconfirmable
            # stamp is dropped from the fold rather than silently injecting a
            # stale value into the relation.
            obs = payload.observation
            refused = revision_carry_outcome(
                payload.stamped_revision_id,
                source_modelo=obs.modelo,
                source_filing_year=obs.filing_year,
                source_period=obs.period,
            ).refused
            if refused:
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


class _RelationGrounding(TypedDict):
    """Registry relation source identity and grounding, keyed for ``RelationValue`` unpacking."""

    source_modelo: ModeloId
    source_casilla_ids: tuple[CasillaId, ...]
    dependency_treatment: str
    legal_refs: tuple[LegalRefId, ...]
    source_refs: tuple[SourceRefId, ...]


def _relation_value_grounding(
    relation: RelationDefinition,
    requirement: RegistryFoldRequirement | None,
) -> _RelationGrounding:
    """Project registry relation source identity and grounding onto a scalar relation value."""
    return {
        "source_modelo": requirement.source_modelo if requirement is not None else relation.source_modelo,
        "source_casilla_ids": (
            requirement.source_casilla_ids if requirement is not None else (relation.source_casilla_id,)
        ),
        # Carried from the requirement, which already holds the registry's declared
        # treatment. Empty when no requirement resolved it, which is not a treatment.
        "dependency_treatment": (requirement.dependency_treatment or "") if requirement is not None else "",
        "legal_refs": tuple(relation.legal_refs),
        "source_refs": tuple(relation.source_refs),
    }


def _relation_provenance_ref(item: RelationValue) -> str:
    source_modelo = item.source_modelo or "unknown-modelo"
    source_year = str(item.source_filing_year) if item.source_filing_year is not None else "unknown-year"
    source_periods = ",".join(item.source_periods) if item.source_periods else "unknown-period"
    source_casillas = ",".join(item.source_casilla_ids) if item.source_casilla_ids else "unknown-casilla"
    return f"{item.relation}:{source_modelo}:{source_year}:{source_periods}:{source_casillas}"


def _relation_source_filing_year(relation: RelationDefinition, *, filing_year: int) -> int:
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
    from ...domain.user_profile.errors import ProfileNotFoundError
    from ..user_profile.profile_record_repository import ProfileRecordRepository
    from ..user_profile.projections import record_to_path_values

    try:
        record = ProfileRecordRepository.for_current_session(bucket_id).load(bucket_id)
    except ProfileNotFoundError:
        return None
    return record_to_path_values(record)


def _contains_profile_token(raw: str | None, token: str) -> bool | None:
    """Return whether a profile projection value contains ``token``, or None if absent.

    ``raw`` is a :func:`_profile_path_values_for_bucket` projection leaf, always a
    plain ``str`` (the projection renders every fact value to text) or ``None``
    when the fact is absent.
    """
    if raw is None:
        return None
    stripped = raw.strip()
    if not stripped:
        return None
    return token in {item.strip() for item in stripped.replace(";", ",").split(",") if item.strip()}


def _economic_activity_conditional_source_modelos(snapshot: RegistrySnapshot) -> frozenset[str]:
    """Return the revision's source modelos whose obligation is conditional on economic activity.

    The revision's ``dependency_classifications`` rows are the authority for
    WHICH cross-period source modelos exist only when the taxpayer carries on an
    economic activity - the mutually exclusive pagos-fraccionados pair (M130
    estimación directa / M131 estimación objetiva). Reading them keeps the
    candidate set owned by the :class:`ModeloRevision` under calculation rather
    than by a modelo list written into this module.

    Deliberately NARROWER than the clean-state gate's ``_non_filer_modelos``,
    which also carries the ``taxpayer_files_source = false`` arm (the suffered
    retenciones sources - 111, 123, 184, 190, 193 on Modelo 100). Those sources
    must never reach the zero-resolution below: they are absent because the
    PAYER files them, not because no obligation exists, and the retención the
    taxpayer suffered is a real credit that must be declared. Their relations
    stay unresolved and operator-supplied; folding them in as zero would strip
    the credit from the declaration.
    """
    return frozenset(
        classification.source_modelo
        for classification in snapshot.revision.dependency_classifications
        if classification.conditional_on_economic_activity
    )


def _not_applicable_source_modelos_for_bucket(snapshot: RegistrySnapshot, bucket_id: str) -> frozenset[str]:
    """Return the revision's economic-activity-conditional sources not applicable to the bucket.

    The registry classification bounds the candidate set
    (:func:`_economic_activity_conditional_source_modelos`); the profile decides
    the verdict within it. No actividad económica means no quarterly
    pagos-fraccionado obligation at all; estimación directa means M130 applies
    and M131 does not; estimación objetiva means M131 applies and M130 does not
    (RIRPF art. 110 - the two methods are mutually exclusive). Every arm
    intersects the registry candidate set, so a source the revision does not
    declare conditional can never be suppressed here.

    Fail-closed throughout: an absent profile, undeclared income categories, and
    an economic activity whose estimation regime is undeclared all return the
    empty set, leaving every source enforced and its relation unresolved rather
    than folding in a zero the operator never declared.
    """
    candidates = _economic_activity_conditional_source_modelos(snapshot)
    if not candidates:
        return frozenset[str]()
    values = _profile_path_values_for_bucket(bucket_id)
    if values is None:
        return frozenset[str]()

    has_economic_activity = _contains_profile_token(
        values.get("taxpayer_type.irpf_income_categories"),
        _ECONOMIC_ACTIVITY_CATEGORY,
    )
    if has_economic_activity is False:
        return candidates
    if has_economic_activity is None:
        return frozenset[str]()

    estimation_regime = str(values.get("irpf.estimation_regime") or "").strip()
    if estimation_regime in _DIRECT_ESTIMATION_REGIMES:
        return candidates & frozenset({str(Modelo.M131)})
    if estimation_regime == "objetiva":
        return candidates & frozenset({str(Modelo.M130)})
    return frozenset[str]()


def _parse_canonical_iso_date(raw: str | None) -> date | None:
    """Parse a canonical ISO-8601 ``censo.*`` date projection value, or ``None``."""
    return parse_iso8601_date(raw)


def _parse_canonical_decimal(raw: str | None) -> Decimal | None:
    """Parse a canonical decimal projection value, or ``None`` when absent / malformed.

    "Canonical" is now enforced rather than asserted: the projection value is
    judged by :func:`~core.decimal.try_parse_canonical_decimal`, so a stored
    token carrying scientific notation, a leading ``+``, a comma decimal, or
    ``NaN``/``Infinity`` resolves to ``None`` (absent) instead of a value whose
    numeric meaning is not what it appears. Fractional digits stay uncapped: a
    projection value may legitimately carry sub-cent precision.
    """
    if not raw:
        return None
    return try_parse_canonical_decimal(raw)


def _entity_type_from_token(raw: str | None) -> EntityType | None:
    """Map a raw ``taxpayer_type.entity_type`` token to :class:`EntityType`, or ``None``."""
    if not raw:
        return None
    from ...domain.deadlines.models import EntityType

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
    under-declaration.
    """
    from ...domain.calculations.registry.applicability_modelo202 import (
        Modelo202Modality,
        modelo_202_modality_from_inputs,
    )

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


def activity_start_date_for_bucket(bucket_id: str) -> date | None:
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
            kept_filing = tuple(period for period in requirement.filing_periods if period.registry_token in kept)
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
    from .cross_period_models import period_strictly_before_activity_start

    return period_strictly_before_activity_start(
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
            :class:`~application.calculations.CalculationObservationRepository`.
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
    :class:`~application.storage.calc_sheets.RelationValues`
    whose ``values`` tuple has one
    :class:`~application.storage.calc_sheets.RelationValue` per
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
        from ...core.bucket_pointer import resolve_active_bucket_id

        active_bucket_id = resolve_active_bucket_id()
        if active_bucket_id is not None:
            activity_start_date = activity_start_date_for_bucket(active_bucket_id)
    if m111_no_retenciones_periods is None:
        from ...core.bucket_pointer import resolve_active_bucket_id

        active_bucket_id = resolve_active_bucket_id()
        m111_no_retenciones_periods = (
            m111_no_retenciones_periods_for_bucket(active_bucket_id)
            if active_bucket_id is not None
            else frozenset[tuple[int, str]]()
        )
    if not_applicable_source_modelos is None:
        from ...core.bucket_pointer import resolve_active_bucket_id

        active_bucket_id = resolve_active_bucket_id()
        not_applicable_source_modelos = (
            _not_applicable_source_modelos_for_bucket(snapshot, active_bucket_id)
            if active_bucket_id is not None
            else frozenset[str]()
        )
    observations = _gather_observations_for_snapshot(
        snapshot,
        repository=repo,
        activity_start_date=activity_start_date,
        m111_no_retenciones_periods=m111_no_retenciones_periods,
    )
    requirements_by_relation = relation_requirement_index(
        _scoped_relation_source_requirements(
            snapshot,
            activity_start_date,
            m111_no_retenciones_periods=m111_no_retenciones_periods,
        ),
    )

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
        grounding = _relation_value_grounding(relation, requirement)
        resolved = resolved_map.get(relation.id)
        if resolved is None:
            # A first-year IS
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
                        **grounding,
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
                        **grounding,
                        resolved_at=when,
                        note=(
                            f"source modelo {requirement.source_modelo} is not applicable for the bucket "
                            "profile; relation resolved to 0 without a synthetic filing"
                        ),
                    ),
                )
                continue
            values.append(RelationValue(relation=relation.id, value=None, **grounding))
            continue
        values.append(
            RelationValue(
                relation=relation.id,
                value=Decimal(resolved),
                provenance=_LOCAL_FILING_PROVENANCE,
                source_filing_year=target_year,
                source_periods=source_periods,
                **grounding,
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
            # A requirement with no single observed source filing stays
            # operator-manual. This is a developer breadcrumb only: the
            # operator-facing form rides the typed Notice channel
            # (aeat-cli-contract) as a
            # relation-prefill advisory built in the resolver boundary from the
            # unresolved set, not this stderr log — which was also
            # environment-inconsistent (present under one logging config, absent
            # under another), making replay goldens unportable.
            _log.debug(
                "relation prefill: relation requirement %s remains operator-manual: %s",
                requirement.relation_ids,
                exc,
            )
            continue
        for relation_id in requirement.relation_ids:
            resolved[relation_id] = value
    return resolved


def _requirement_periods_are_datable(requirement: RegistryFoldRequirement) -> bool:
    """Whether every source period of ``requirement`` can be positioned against a date.

    The activity-start scoping that keeps the absent-bound-carry advisory honest
    can only suppress a period it can place on a calendar: a non-calendar
    instalment clave (1P/2P/3P) has no span and is documented as never suppressed.
    For such a period the scoping cannot establish that the taxpayer HAD the
    obligation, so the advisory must not claim they did — a sociedad whose activity
    began after the first instalment window would otherwise be told a filing it
    never owed is missing.

    Silence is the fail-closed direction here, and deliberately so: it preserves
    the prior behaviour for exactly the periods where the obligation is
    undeterminable, rather than guessing.
    """
    for token in requirement.periods:
        try:
            period = Period.from_year_and_code(requirement.filing_year, token)
        except Exception:
            # A token that will not construct a Period is by definition undatable.
            return False
        if not period.has_date_span():
            return False
    return True


def _absent_bound_carry_diagnostics(
    *,
    unresolved_relation_ids: frozenset[RelationId],
    requirements_by_relation: Mapping[RelationId, RegistryFoldRequirement],
    relation_target_binding: Mapping[RelationId, BindingId],
    resolver_id: str,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Advise on a bound carry whose source filing is absent, so the slot threads a zero.

    Distinct from the orphaned-relation advisory in what it tells the operator.
    An orphan reaches nothing; this one reaches a casilla, as a zero, and every
    carry on this path reduces the amount owed — a prior instalment already paid,
    a loss carried forward, an opening stock. So the zero does not look wrong. It
    looks like a taxpayer who had no prior filing, and it declares more tax than
    is owed.

    The advisory is non-blocking, and it does not fire for a filer who genuinely
    had no obligation: those source periods are scoped out upstream against the
    declared activity start before any requirement reaches here.

    The message states the FACT and the remedy names only what the operator can
    always do. It deliberately does not tell them to capture or file the source
    period, because whether that is possible depends on the source modelo: the
    declarations register does not serve every modelo, and Sociedades in
    particular. An instruction an agent-operator will follow and cannot satisfy is
    worse than no instruction, so the capture route is omitted here rather than
    asserted, and stating what AEAT does or does not offer is left to whoever
    measures it rather than inferred from this registry's own silence.
    """
    diagnostics: list[CalculationSourceDiagnostic] = []
    for relation_id in sorted(unresolved_relation_ids):
        requirement = requirements_by_relation.get(relation_id)
        binding_id = relation_target_binding.get(relation_id)
        if requirement is None:
            diagnostics.append(
                CalculationSourceDiagnostic(
                    reason="source_issue",
                    source_kind="relation_prefill",
                    resolver_id=resolver_id,
                    binding_id=binding_id,
                    relation_id=relation_id,
                    message=(
                        f"carry {relation_id!r} has no resolved source filing, so its bound casilla "
                        "declares zero; a carry that reduces the amount owed is missing, which "
                        "over-declares"
                    ),
                    remedy=(
                        "Supply the value for this casilla directly, through a binding override on "
                        "calculate, if you hold the prior return."
                    ),
                ),
            )
            continue
        diagnostics.append(
            CalculationSourceDiagnostic(
                reason="source_issue",
                source_kind="relation_prefill",
                resolver_id=resolver_id,
                binding_id=binding_id,
                relation_id=relation_id,
                message=(
                    f"carry {relation_id!r} found no modelo {requirement.source_modelo} "
                    f"{requirement.filing_year} {','.join(requirement.periods)} filing in the local "
                    f"store, so its bound casilla declares zero rather than the carried "
                    f"{requirement.source_casilla_ids[0]}. That reduces no liability and therefore "
                    "over-declares."
                ),
                remedy=(
                    "Supply the value for this casilla directly, through a binding override on "
                    "calculate, if you hold the prior return."
                ),
            ),
        )
    return tuple(diagnostics)


class _UnresolvedRelationIds(NamedTuple):
    """The three silences an unresolved relation can be, kept apart on purpose.

    They are separate sets because their CONSEQUENCES differ, not because the
    predicates do. Collapsing them would make one advisory speak for three
    outcomes, only one of which over-declares.
    """

    formula_fed: frozenset[RelationId]
    """Unresolved and read by a formula: the value feeds a computed casilla."""

    orphaned: frozenset[RelationId]
    """Unresolved and reaches no declared consumption channel.

    Produces no value, no slot and nothing observable, so its absence reaches
    nothing at all.
    """

    bound: frozenset[RelationId]
    """Unresolved and consumed through a primary or alternate casilla binding.

    The subtle one, and the reason this set exists. It was once left silent as
    "intended cold-start behaviour", but cold start is not what that silence
    protected: a source period the taxpayer had no obligation for is already
    removed upstream against the declared activity start, so a genuine
    first-ejercicio filer's prior-year carries never reach here. What the
    silence additionally covered was the filer who DID have the obligation and
    whose filing is simply not in the store -- and there the engine threads the
    absent slot as a zero, which reduces no liability and therefore
    over-declares (no-silent-under-declaration).
    """


class _RelationConsumption(NamedTuple):
    """Canonical registry channels projected for one unresolved-value pass."""

    formula_fed: frozenset[RelationId]
    bound: frozenset[RelationId]
    consumed: frozenset[RelationId]
    target_bindings: dict[RelationId, BindingId]


def _unresolved_relation_ids(
    snapshot: RegistrySnapshot,
    *,
    relation_values: RelationValues,
    requirements_by_relation: Mapping[RelationId, RegistryFoldRequirement],
    modelo_id: str,
) -> _UnresolvedRelationIds:
    """Partition the unresolved relations by what their silence actually reaches.

    Three narrowings keep the ``bound`` advisory honest, and each is
    load-bearing rather than incidental:

    * membership in ``requirements_by_relation``, which is built from the SCOPED
      requirement set -- testing ``value is None`` alone would fire on every
      genuine first-ejercicio filer, because a scoped-out relation still appears
      here unresolved;
    * ``taxpayer_files_source``, because a carry the taxpayer does not FILE (a
      retención suffered, where the payer files the source modelo) cannot be
      remedied by capturing or filing anything, so advising on it would put an
      unactionable line in front of every filer who simply had no such
      withholding. That axis is registry-declared per dependency, never
      inferred;
    * ownership, because the Modelo 303 compensación slot belongs to the IVA
      wallet decision under the one-mechanism-per-calculation-type taxonomy, so
      advising on it here would be a second mechanism speaking about a value it
      does not own. The check is the registry's own predicate rather than a
      binding-id comparison invented here.
    """
    consumption = _relation_consumption(snapshot)
    unresolved_ids = frozenset(item.relation for item in relation_values.values if item.value is None)
    taxpayer_filed_source_modelos = frozenset(
        classification.source_modelo
        for classification in snapshot.revision.dependency_classifications
        if classification.taxpayer_files_source
    )
    return _UnresolvedRelationIds(
        formula_fed=unresolved_ids & consumption.formula_fed,
        orphaned=unresolved_ids - consumption.consumed,
        bound=_unresolved_bound_relation_ids(
            unresolved_ids,
            consumption=consumption,
            requirements_by_relation=requirements_by_relation,
            taxpayer_filed_source_modelos=taxpayer_filed_source_modelos,
            modelo_id=modelo_id,
            revision_id=str(snapshot.revision.id),
        ),
    )


def _relation_consumption(snapshot: RegistrySnapshot) -> _RelationConsumption:
    """Derive only the registry's four declared relation consumption channels."""
    consumption_index = relation_consumption_index(snapshot.revision)
    channels_by_relation = {
        relation.id: relation_consumption_channels(relation, consumption_index)
        for relation in snapshot.revision.relations
    }
    return _RelationConsumption(
        formula_fed=_relation_ids_for_channels(
            channels_by_relation,
            "formula_relation",
            "formula_binding",
        ),
        bound=_relation_ids_for_channels(
            channels_by_relation,
            "primary_binding",
            "alternate_binding",
        ),
        consumed=_consumed_relation_ids(channels_by_relation),
        target_bindings=_relation_target_bindings(snapshot),
    )


def _relation_ids_for_channels(
    channels_by_relation: Mapping[RelationId, tuple[str, ...]],
    *required_channels: str,
) -> frozenset[RelationId]:
    required = frozenset(required_channels)
    return frozenset(
        relation_id for relation_id, channels in channels_by_relation.items() if required.intersection(channels)
    )


def _consumed_relation_ids(
    channels_by_relation: Mapping[RelationId, tuple[str, ...]],
) -> frozenset[RelationId]:
    return frozenset(relation_id for relation_id, channels in channels_by_relation.items() if channels)


def _relation_target_bindings(snapshot: RegistrySnapshot) -> dict[RelationId, BindingId]:
    return {relation.id: relation.target_binding for relation in snapshot.revision.relations}


def _unresolved_bound_relation_ids(
    unresolved_ids: frozenset[RelationId],
    *,
    consumption: _RelationConsumption,
    requirements_by_relation: Mapping[RelationId, RegistryFoldRequirement],
    taxpayer_filed_source_modelos: frozenset[ModeloId],
    modelo_id: str,
    revision_id: RevisionId,
) -> frozenset[RelationId]:
    """Keep only actionable, non-wallet unresolved bound carries."""
    return frozenset(
        relation_id
        for relation_id in unresolved_ids
        if _is_actionable_unresolved_bound_relation(
            relation_id,
            consumption=consumption,
            requirements_by_relation=requirements_by_relation,
            taxpayer_filed_source_modelos=taxpayer_filed_source_modelos,
            modelo_id=modelo_id,
            revision_id=revision_id,
        )
    )


def _is_actionable_unresolved_bound_relation(
    relation_id: RelationId,
    *,
    consumption: _RelationConsumption,
    requirements_by_relation: Mapping[RelationId, RegistryFoldRequirement],
    taxpayer_filed_source_modelos: frozenset[ModeloId],
    modelo_id: str,
    revision_id: RevisionId,
) -> bool:
    if relation_id in consumption.formula_fed or relation_id not in requirements_by_relation:
        return False
    requirement = requirements_by_relation[relation_id]
    if requirement.source_modelo not in taxpayer_filed_source_modelos:
        return False
    if not _requirement_periods_are_datable(requirement) or relation_id not in consumption.bound:
        return False
    return not is_iva_wallet_owned_relation_target(
        modelo_id=modelo_id,
        revision_id=revision_id,
        relation_id=str(relation_id),
        target_binding=str(consumption.target_bindings.get(relation_id)),
    )


def _unresolved_relation_diagnostics(
    *,
    unresolved_relation_ids: frozenset[RelationId],
    requirements_by_relation: Mapping[RelationId, RegistryFoldRequirement],
    resolver_id: str,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Advise once per ABSENT SOURCE FILING, not once per relation reading it.

    Measured on Modelo 190 for 2025 with an empty store and a long-running
    filer: ten annual-summary relations each read a different fact off the
    SAME absent Modelo 111 return, so the un-grouped form produced ten lines
    naming one root cause. Grouped by ``(source_modelo, filing_year,
    periods)`` — deliberately NOT including ``source_casilla_ids``, since the
    casilla read is exactly the axis that varies across the grouped
    relations and enumerating it is the "affected facts" the grouped
    advisory names. A relation with no requirement at all (an orphan the
    scoped requirement set never produced) has no source coordinate to group
    by and stays one diagnostic per relation — there is no shared cause to
    fold it into.
    """
    diagnostics: list[CalculationSourceDiagnostic] = []
    orphaned_ids: list[RelationId] = []
    grouped: dict[tuple[str, int, tuple[str, ...]], list[tuple[RelationId, RegistryFoldRequirement]]] = {}
    for relation_id in sorted(unresolved_relation_ids):
        requirement = requirements_by_relation.get(relation_id)
        if requirement is None:
            orphaned_ids.append(relation_id)
            continue
        key = (requirement.source_modelo, requirement.filing_year, requirement.periods)
        grouped.setdefault(key, []).append((relation_id, requirement))

    for relation_id in orphaned_ids:
        diagnostics.append(
            CalculationSourceDiagnostic(
                reason="source_issue",
                source_kind="relation_prefill",
                resolver_id=resolver_id,
                relation_id=relation_id,
                message=f"relation {relation_id!r} has no resolved source filing",
            ),
        )

    for (source_modelo, filing_year, periods), members in sorted(grouped.items()):
        member_relation_ids = tuple(sorted(relation_id for relation_id, _ in members))
        binding_ids = {
            requirement.target_bindings[0] for _, requirement in members if len(requirement.target_bindings) == 1
        }
        binding_id = next(iter(binding_ids)) if len(binding_ids) == 1 else None
        period_text = ",".join(periods)
        # Facts (the casilla ids the group reads) come first, so a long group's
        # elision cuts into the trailing relation-id listing rather than the
        # facts themselves; `relation_ids` above is the full, un-elided,
        # machine-readable membership regardless of what the prose keeps.
        facts_text = ", ".join(sorted({str(requirement.source_casilla_ids[0]) for _, requirement in members}))
        relation_ids_text = ", ".join(member_relation_ids)
        diagnostics.append(
            CalculationSourceDiagnostic(
                reason="source_issue",
                source_kind="relation_prefill",
                resolver_id=resolver_id,
                binding_id=binding_id,
                relation_id=member_relation_ids[0],
                relation_ids=member_relation_ids,
                message=(
                    f"modelo {source_modelo} {filing_year} periods {period_text} is missing or "
                    f"incomplete in the local store; {len(members)} relation(s) read it, needing: "
                    f"{facts_text}. Affected relations: {relation_ids_text}"
                ),
            ),
        )
    return tuple(diagnostics)


class RelationPrefillSourceResolver:
    """Source-mesh adapter for local ``relation_prefill`` values.

    Resolves registry relations through :func:`resolve_relations_from_local_store`,
    materialises resolved relation values into declared target-binding slots, and
    returns a :class:`~application.aggregation.CalculationSourceResolution`
    carrying relation values, binding values, diagnostics for unresolved formula
    relations, and provenance for local
    :class:`RegistryModeloObservation` filings.
    """

    resolver_id: ClassVar[str] = "relation_prefill"
    owned_sources: ClassVar[tuple[BindingSourceKind, ...]] = (BindingSourceKind.RELATION_PREFILL,)

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
            snapshot = bundled_authority().snapshot(
                context.modelo,
                filing_year=context.filing_year,
                period=context.period.registry_token,
            )
        # Activity-start scoping (IRPF-1): a mid-year-start filer has no obligation
        # for source quarters strictly before the activity start, so those quarters
        # are scoped out of the relation fold so their absence does not unresolve
        # the whole fold. Derived once from the bucket profile and shared by the
        # resolution and the diagnostic so both see the same scoped requirement set.
        activity_start_date = activity_start_date_for_bucket(str(context.bucket_id))
        m111_no_retenciones_periods = m111_no_retenciones_periods_for_bucket(str(context.bucket_id))
        not_applicable_source_modelos = _not_applicable_source_modelos_for_bucket(snapshot, str(context.bucket_id))
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
        requirements_by_relation = relation_requirement_index(
            _scoped_relation_source_requirements(
                snapshot,
                activity_start_date,
                m111_no_retenciones_periods=m111_no_retenciones_periods,
            ),
        )
        resolved = tuple(item for item in relation_values.values if item.value is not None)
        unresolved = _unresolved_relation_ids(
            snapshot,
            relation_values=relation_values,
            requirements_by_relation=requirements_by_relation,
            modelo_id=str(context.modelo),
        )
        unresolved_relation_ids = unresolved.formula_fed
        unresolved_non_formula_relation_ids = unresolved.orphaned
        unresolved_bound_relation_ids = unresolved.bound
        # Still needed below: the bound-silence diagnostic names each relation's
        # target binding, so the caller keeps the lookup the partition also used.
        relation_target_binding = {relation.id: relation.target_binding for relation in snapshot.revision.relations}
        resolved_relation_values = {item.relation: item.value for item in resolved if item.value is not None}
        # Materialise the resolved relation values into their declared
        # ``target_binding`` slots HERE, inside the resolver, so the merged
        # resolution carries them in ``binding_values`` and the mesh
        # ``_claim_binding`` exclusive-ownership guard adjudicates any collision
        # with another resolver loudly. This
        # replaces the silent post-mesh merge that previously let every other
        # source override a relation-materialised value without a finding.
        binding_values = materialize_relation_binding_values(
            snapshot.revision,
            resolved_relation_values,
            period=context.period.registry_token,
        )
        binding_values = {
            **_modelo_202_first_period_previous_payment_defaults(
                snapshot.revision,
                modelo=str(context.modelo),
                period=context.period.registry_token,
            ),
            **binding_values,
        }
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
            )
            + _absent_bound_carry_diagnostics(
                unresolved_relation_ids=unresolved_bound_relation_ids,
                requirements_by_relation=requirements_by_relation,
                relation_target_binding=relation_target_binding,
                resolver_id=self.resolver_id,
            ),
            provenance=tuple(
                CalculationSourceProvenance(
                    resolver_id=self.resolver_id,
                    resolved_binding_source=BindingSourceKind.RELATION_PREFILL,
                    contributor_source_kind="relation_prefill",
                    contributor_binding_source=BindingSourceKind.RELATION_PREFILL,
                    lineage_role=CalculationSourceLineageRole.PRIMARY,
                    source_ref=_relation_provenance_ref(item),
                    parent_source_ref=None,
                    relation_id=item.relation,
                    source_modelo=item.source_modelo,
                    source_filing_year=item.source_filing_year,
                    source_periods=item.source_periods,
                    source_casilla_ids=item.source_casilla_ids,
                    legal_refs=item.legal_refs,
                    source_refs=item.source_refs,
                    dependency_treatment=item.dependency_treatment,
                )
                for item in resolved
            ),
        )


def relation_prefill_period_zero_default_binding_ids(
    revision: ModeloRevision,
    *,
    modelo: str,
    period: str,
) -> frozenset[BindingId]:
    """Return the relation-prefill binding ids calculate resolves to zero for ``period``.

    ``revision`` is the :class:`ModeloRevision` whose bindings are inspected.

    A Modelo 202 same-model previous-payment carry (``previous_period`` relation
    sourcing the same modelo) has no upstream filing before its first target
    period, so the resolver materialises its ``target_binding`` slot as zero
    rather than leaving it absent. This is the single authority for "which
    relation-prefill bindings are pre-satisfied with a zero default in this
    period"; both the calculate resolver
    (:func:`_modelo_202_first_period_previous_payment_defaults`) and the
    readiness missing-bindings projection consume it, so readiness and calculate
    agree on the missing set by construction
    (``aeat-calculation-aggregation``).
    """
    if modelo != Modelo.M202.value:
        return frozenset[BindingId]()
    relations_by_target = relations_by_target_binding(revision)
    zero_defaulted: set[BindingId] = set()
    for binding in revision.bindings:
        if binding.source is not BindingSourceKind.RELATION_PREFILL:
            continue
        relations = relations_by_target.get(binding.id, ())
        if not relations:
            continue
        if any(not relation.target_periods or period in relation.target_periods for relation in relations):
            continue
        if all(relation.kind == "previous_period" and str(relation.source_modelo) == modelo for relation in relations):
            zero_defaulted.add(binding.id)
    return frozenset(zero_defaulted)


def _modelo_202_first_period_previous_payment_defaults(
    revision: ModeloRevision,
    *,
    modelo: str,
    period: str,
) -> dict[BindingId, Decimal]:
    """Resolve M202 same-model previous-payment carries to zero before their first target period."""
    return {
        binding_id: Decimal("0")
        for binding_id in relation_prefill_period_zero_default_binding_ids(
            revision,
            modelo=modelo,
            period=period,
        )
    }


__all__ = [
    "RelationPrefillSourceResolver",
    "relation_prefill_period_zero_default_binding_ids",
    "resolve_relations_from_local_store",
]
