"""Build-time gate: a ``previous_filing`` binding's source must cover every year it can ask for.

A consumer revision's own coverage and its ``previous_filing`` source's coverage
are declared independently, so nothing stops a consumer's range from outliving
its source's — the failure then surfaces far downstream, at the resolve-time
snapshot lookup, as a silent blank rather than at build time as a named defect.
This module closes that at the source: for every ``previous_filing`` binding,
it derives the exact source-year interval the binding's own revision could ask
for and verifies the source modelo's revisions cover it.

Two exclusions are STRUCTURAL — grounded in facts the schema and the corpus
already state, never in a tax judgement about when a given return first
existed:

- A required year below :data:`_REGISTRY_MIN_FILING_YEAR` is outside the
  registry's own representable range (every ``modelo_year`` field in this
  package is bounded ``ge=2000``), so no revision could ever model it
  regardless of content.
- A required year beyond the SOURCE modelo's own latest published year is not
  yet published by AEAT for ANYONE — that is the expected state of the world
  today, not a corpus omission, and it resolves itself the moment a new source
  revision ships. Clipping the requirement there is what keeps an open-ended
  consumer revision (most of them: a modelo's current revision typically
  declares no ``year_to`` at all) from failing this gate every single year
  regardless of whether the source has actually fallen behind.

What remains after both exclusions is a genuine, currently-unmodelled gap in
the SOURCE corpus. Those are real findings, not gate defects, and they are
recorded in :data:`_ALLOWANCES` rather than silently passed: each entry names
the binding, the source modelo, the first missing year, why the gap exists
today, and what would discharge it. An entry that no longer matches a real
failure is itself a build failure — the allowlist must not silently outlive
the gap it was written for.

See Also:
    :mod:`cadrumo.domain.calculations.registry._validate_previous_filing_sources`
        Sibling closure validation: does a period-shape-compatible source
        revision exist at all. This module answers a different question —
        does the source's revision set span every YEAR the binding could ask
        for — and is a genuine gap in that sibling's coverage rather than a
        duplicate of it.
    :mod:`cadrumo.domain.calculations.registry._validate_relation_periods`
        The relation-source sibling gate
        (:func:`validate_relation_source_coordinate_coverage`), which the
        registry build already runs for relations; this module is the
        ``previous_filing`` counterpart the build was missing.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from ....core import BindingSourceKind, Modelo
from ._bindings_previous_filing import previous_filing_source_reference
from ._errors import RegistryValidationError
from ._ids import BindingId, ModeloId
from ._schema import DataBindingDefinition, ModeloDefinition, ModeloRevision

#: The registry's own representable floor. Matches the ``ge=2000`` bound
#: already declared on every ``modelo_year`` field in this package (see
#: ``RegistrySnapshotRef.modelo_year``) — a schema fact, not a tax judgement
#: about when any particular return first existed.
_REGISTRY_MIN_FILING_YEAR = 2000


@dataclass(frozen=True, slots=True)
class _PreviousFilingYearCoverageAllowance:
    """One documented, currently-necessary previous-filing source-year gap.

    Every field is required so the entry states its own argument rather than
    being a bare exemption a later reader has to reconstruct the reason for.
    Matched by ``(binding_id, source_modelo, missing_from_year,
    missing_through_year)`` — the FULL range, never just the start, so a gap
    that WIDENS while keeping the same start year (a further regression, not
    the one this entry was written for) is NOT silently absorbed by an entry
    that under-states it. Never matched by line number, so a registry reflow
    cannot silently detach an entry from the finding it was written for.
    """

    binding_id: BindingId
    source_modelo: ModeloId
    missing_from_year: int
    missing_through_year: int
    reason: str
    discharge: str


_ALLOWANCES: tuple[_PreviousFilingYearCoverageAllowance, ...] = (
    _PreviousFilingYearCoverageAllowance(
        binding_id="irpf.previous_year_economic_activity_net_income",
        source_modelo=Modelo.M100.value,
        missing_from_year=2018,
        missing_through_year=2019,
        reason=(
            "Modelo 130's only modelled revision (2019-y-siguientes, open-ended) reads the "
            "immediately prior year's Modelo 100 net income (filing_year_delta=-1). Its own "
            "first modelled year (2019) already needs a 2018 Modelo 100 revision, and every "
            "year before Modelo 100's own corpus floor (2020) needs one likewise -- 2018 and "
            "2019 are both unmodelled in Modelo 100 today."
        ),
        discharge=(
            "Author Modelo 100 registry revisions for filing years 2018 and 2019, or narrow "
            "Modelo 130's own period_selector floor to 2020 if those years are out of campaign "
            "scope."
        ),
    ),
    _PreviousFilingYearCoverageAllowance(
        binding_id="modelo-720-prior-year-cuentas-valoracion-baseline",
        source_modelo=Modelo.M720.value,
        missing_from_year=2011,
        missing_through_year=2011,
        reason=(
            "Modelo 720's own revision (2013-y-siguientes) floors at filing year 2012 and reads "
            "its own prior-year baseline (filing_year_delta=-1, self-referencing), so its first "
            "modelled year needs a 2011 Modelo 720 revision that does not exist. Every later "
            "year is covered by the same open-ended revision reading its own immediately "
            "preceding year, so the gap is exactly one year wide."
        ),
        discharge=(
            "Author a Modelo 720 registry revision for filing year 2011, or confirm 2012 is the "
            "informative obligation's own first year and narrow the binding accordingly."
        ),
    ),
    _PreviousFilingYearCoverageAllowance(
        binding_id="modelo-720-prior-year-valores-valoracion-baseline",
        source_modelo=Modelo.M720.value,
        missing_from_year=2011,
        missing_through_year=2011,
        reason=(
            "Same shape as modelo-720-prior-year-cuentas-valoracion-baseline (see that entry): "
            "self-referencing prior-year baseline, one-year gap at the corpus floor."
        ),
        discharge="Same discharge as modelo-720-prior-year-cuentas-valoracion-baseline.",
    ),
    _PreviousFilingYearCoverageAllowance(
        binding_id="modelo-720-prior-year-inmuebles-valoracion-baseline",
        source_modelo=Modelo.M720.value,
        missing_from_year=2011,
        missing_through_year=2011,
        reason=(
            "Same shape as modelo-720-prior-year-cuentas-valoracion-baseline (see that entry): "
            "self-referencing prior-year baseline, one-year gap at the corpus floor."
        ),
        discharge="Same discharge as modelo-720-prior-year-cuentas-valoracion-baseline.",
    ),
)


def _revision_year_interval(revision: ModeloRevision) -> tuple[int, int | None]:
    """Return one revision's own ``(min_year, max_year_or_open)``."""
    selector = revision.period_selector
    if selector.years:
        return min(selector.years), max(selector.years)
    # `PeriodSelector`'s own validator guarantees `year_from` is set when
    # `years` is empty.
    assert selector.year_from is not None
    return selector.year_from, selector.year_to


def _upper_year_bound(revisions: tuple[ModeloRevision, ...]) -> int | None:
    """Return the latest year ANY of ``revisions`` models, or ``None`` if one is open-ended.

    ``revisions`` is always the caller's already period-matched candidate
    set: a revision under a different period shape cannot cover the
    requirement regardless of the year it models, so it must not contribute
    to the ceiling either.
    """
    bound: int | None = None
    for revision in revisions:
        _, revision_end = _revision_year_interval(revision)
        if revision_end is None:
            return None
        bound = revision_end if bound is None else max(bound, revision_end)
    return bound


def _period_matching_revisions(
    source_modelo: ModeloDefinition,
    *,
    required_periods: tuple[str, ...],
) -> tuple[ModeloRevision, ...]:
    return tuple(
        revision
        for revision in source_modelo.revisions.values()
        if not required_periods or set(required_periods).issubset(set(revision.period_selector.periods))
    )


def _open_ended_source_start(period_matching_revisions: tuple[ModeloRevision, ...]) -> int | None:
    """Return the earliest year of a period-matching OPEN-ENDED source revision, if any."""
    open_starts = [
        start
        for revision in period_matching_revisions
        for start, end in (_revision_year_interval(revision),)
        if end is None
    ]
    return min(open_starts) if open_starts else None


def _clipped_required_interval(
    *,
    required_start: int,
    required_end: int | None,
    source_upper_bound: int | None,
) -> tuple[int, int | None] | None:
    """Clip a raw requirement to what a genuine corpus gap could mean.

    Returns ``None`` when the clipped interval is empty -- the requirement is
    entirely structural (before the registry floor, or entirely beyond what
    the source has published) and there is nothing left to check.
    """
    clipped_start = max(required_start, _REGISTRY_MIN_FILING_YEAR)
    if source_upper_bound is None:
        clipped_end = required_end
    else:
        clipped_end = source_upper_bound if required_end is None else min(required_end, source_upper_bound)
    if clipped_end is not None and clipped_start > clipped_end:
        return None
    return clipped_start, clipped_end


def _missing_years(
    *,
    start: int,
    end: int | None,
    period_matching_revisions: tuple[ModeloRevision, ...],
) -> tuple[int, ...]:
    """Return every year in ``[start, end]`` no period-matching source revision covers.

    ``end is None`` only reaches this function when the source modelo itself
    carries an open-ended period-matching revision (see
    :func:`_clipped_required_interval`'s ``source_upper_bound is None`` arm),
    so :func:`_open_ended_source_start` is guaranteed to resolve: the walk
    stops the year before that revision starts, because every year at or
    after it is covered by construction.
    """
    if end is None:
        open_start = _open_ended_source_start(period_matching_revisions)
        assert open_start is not None
        walk_end = open_start - 1
    else:
        walk_end = end
    if walk_end < start:
        return ()
    return tuple(
        year
        for year in range(start, walk_end + 1)
        if not any(revision.period_selector.includes_year(year) for revision in period_matching_revisions)
    )


def _contiguous_runs(years: tuple[int, ...]) -> tuple[tuple[int, int], ...]:
    """Group a sorted, deduplicated year tuple into ``(run_start, run_end)`` pairs."""
    if not years:
        return ()
    runs: list[list[int]] = [[years[0]]]
    for year in years[1:]:
        if year == runs[-1][-1] + 1:
            runs[-1].append(year)
        else:
            runs.append([year])
    return tuple((run[0], run[-1]) for run in runs)


def _previous_filing_bindings(
    modelos: Iterable[ModeloDefinition],
) -> Iterable[tuple[ModeloDefinition, ModeloRevision, DataBindingDefinition]]:
    """Yield every previous-filing binding with its owning modelo and revision."""
    for modelo in modelos:
        for revision in modelo.revisions.values():
            for binding in revision.bindings:
                if binding.source == BindingSourceKind.PREVIOUS_FILING:
                    yield modelo, revision, binding


def _source_year_gap(
    *,
    revision: ModeloRevision,
    binding: DataBindingDefinition,
    modelos_by_id: Mapping[str, ModeloDefinition],
) -> tuple[ModeloId, tuple[tuple[int, int], ...]] | None:
    """Return the genuine missing source-year runs for one previous-filing binding."""
    try:
        source_reference = previous_filing_source_reference(binding)
    except RegistryValidationError:
        return None
    if source_reference.has_variable_year_offset:
        return None

    source_modelo = modelos_by_id.get(source_reference.source_modelo)
    if source_modelo is None:
        return None
    period_matching_revisions = _period_matching_revisions(
        source_modelo,
        required_periods=source_reference.required_periods,
    )
    if not period_matching_revisions:
        return None

    consumer_start, consumer_end = _revision_year_interval(revision)
    clipped = _clipped_required_interval(
        required_start=consumer_start + source_reference.filing_year_delta,
        required_end=(None if consumer_end is None else consumer_end + source_reference.filing_year_delta),
        source_upper_bound=_upper_year_bound(period_matching_revisions),
    )
    if clipped is None:
        return None
    clipped_start, clipped_end = clipped
    missing = _missing_years(
        start=clipped_start,
        end=clipped_end,
        period_matching_revisions=period_matching_revisions,
    )
    return source_reference.source_modelo, _contiguous_runs(missing)


def _append_previous_filing_gap_failures(
    failures: list[str],
    *,
    prefix: str,
    binding: DataBindingDefinition,
    source_modelo: ModeloId,
    missing_runs: tuple[tuple[int, int], ...],
    allowances_by_key: Mapping[tuple[BindingId, ModeloId, int, int], _PreviousFilingYearCoverageAllowance],
    consumed_allowances: set[tuple[BindingId, ModeloId, int, int]],
) -> None:
    """Record missing years or consume the exact documented allowance."""
    for run_start, run_end in missing_runs:
        key = (binding.id, source_modelo, run_start, run_end)
        allowance = allowances_by_key.get(key)
        if allowance is not None:
            consumed_allowances.add(key)
            continue
        year_label = str(run_start) if run_start == run_end else f"{run_start}-{run_end}"
        failures.append(
            f"{prefix}: binding {binding.id!r} lacks {source_modelo!r} "
            f"source revision coverage for filing year(s) {year_label}",
        )


def _stale_allowance_failures(
    allowances_by_key: Mapping[tuple[BindingId, ModeloId, int, int], _PreviousFilingYearCoverageAllowance],
    *,
    consumed_allowances: set[tuple[BindingId, ModeloId, int, int]],
    encountered_binding_ids: set[BindingId],
) -> list[str]:
    """Report allowances that no longer describe an encountered real gap."""
    failures: list[str] = []
    for key, allowance in allowances_by_key.items():
        if key in consumed_allowances or allowance.binding_id not in encountered_binding_ids:
            continue
        failures.append(
            f"stale previous-filing year-coverage allowance: binding {allowance.binding_id!r} "
            f"source {allowance.source_modelo!r} from {allowance.missing_from_year} through "
            f"{allowance.missing_through_year} no longer matches a real gap; remove the entry "
            "from _ALLOWANCES",
        )
    return failures


def validate_previous_filing_source_year_coverage(
    modelos: Iterable[ModeloDefinition],
    modelos_by_id: Mapping[str, ModeloDefinition],
) -> list[str]:
    """Validate that every ``previous_filing`` source spans every year its binding could ask for.

    Args:
        modelos: Iterable of :class:`ModeloDefinition` entries whose
            ``previous_filing`` bindings are checked.
        modelos_by_id: Mapping of modelo id to :class:`ModeloDefinition`
            used to resolve each binding's source modelo.
    """
    failures: list[str] = []
    consumed_allowances: set[tuple[BindingId, ModeloId, int, int]] = set()
    #: Every allowance whose binding was actually reachable in THIS call's
    #: modelo set. Many registry tests validate a synthetic single-modelo
    #: fixture rather than the full bundled tree, and an allowance whose
    #: binding lives on a modelo absent from that fixture is simply not a
    #: question this call can answer -- neither consumed nor stale, just not
    #: applicable. Without this distinction every such test would report all
    #: four allowances stale, because "consumed" would stay empty for a
    #: reason that has nothing to do with any of them actually closing.
    encountered_binding_ids: set[BindingId] = set()
    allowances_by_key = {
        (allowance.binding_id, allowance.source_modelo, allowance.missing_from_year, allowance.missing_through_year): (
            allowance
        )
        for allowance in _ALLOWANCES
    }
    allowance_binding_ids = {allowance.binding_id for allowance in _ALLOWANCES}

    for modelo, revision, binding in _previous_filing_bindings(modelos):
        prefix = f"modelo {modelo.id} revision {revision.id}"
        if binding.id in allowance_binding_ids:
            encountered_binding_ids.add(binding.id)
        gap = _source_year_gap(revision=revision, binding=binding, modelos_by_id=modelos_by_id)
        if gap is None:
            continue
        source_modelo, missing_runs = gap
        _append_previous_filing_gap_failures(
            failures,
            prefix=prefix,
            binding=binding,
            source_modelo=source_modelo,
            missing_runs=missing_runs,
            allowances_by_key=allowances_by_key,
            consumed_allowances=consumed_allowances,
        )

    failures.extend(
        _stale_allowance_failures(
            allowances_by_key,
            consumed_allowances=consumed_allowances,
            encountered_binding_ids=encountered_binding_ids,
        ),
    )
    return failures


__all__ = ["validate_previous_filing_source_year_coverage"]
