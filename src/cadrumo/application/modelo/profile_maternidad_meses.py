"""Resolve the Art. 81.1 maternidad months a profile contributes and derive casilla 0611.

The months and the deduction both come from one reconstruction of the family
record from the profile fact projection.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

from ...domain.calculations.registry.errors import RegistryValidationError
from ...domain.calculations.registry.schema import RegistrySnapshot
from ...domain.contribuyente.deduccion_maternidad import compute_deduccion_maternidad_0611
from ...domain.contribuyente.family_fact_context import FamilyFactResolutionContext
from ...domain.contribuyente.family_profile import RentaFamilyProfile
from ...domain.user_profile.schema import ProfileSchemaDefinition
from ...domain.user_profile.values import UserProfileFactValue
from ..user_profile.projections import profile_fact_index
from .profile_derived_facts import (
    family_fact_context,
    renta_family_profile_from_facts,
    resolved_minimo_descendientes_thresholds,
    snapshot_authored_year,
)

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation


@dataclass(frozen=True, slots=True)
class MaternidadMesesResolution:
    """What the profile contributes to the Art. 81.1 deducción, and what it does not.

    Carries the withheld indices and the ceilings verdict alongside the granted
    pairs because all three come from one evaluation of one predicate over one
    reconstruction of the record. Returning only the pairs would force the
    caller to ask again for the other two, and a second evaluation is how a
    disclosure comes to describe a withholding the grant path never made.
    """

    pairs: tuple[tuple[str, int], ...]
    withheld_indices: tuple[str, ...]
    ceilings_resolved: bool
    declares_meses: bool
    cotizaciones_ceiling_inexpressible: bool = False
    """True when the filing year predates 2023 and the engine cannot apply the ceiling.

    Until 2022 Art. 81.1 limited the deducción to the mother's Social Security
    cotizaciones devengadas in the period. Neither the registry nor the profile
    schema can express that figure for those years -- the binding and the fact are
    both 2024-pinned -- so the deducción is withheld rather than granted
    un-ceilinged, and the caller discloses it.
    """
    alta_posterior_hijos: frozenset[str] = frozenset()
    """``hijo_id`` values from :attr:`pairs` that also carry the Art. 81.1 post-birth

    alta increment (:meth:`~domain.contribuyente.descendant_guarderia.maternidad_alta_posterior_increment_applies`)
    for the resolved filing year. A ``hijo_id`` absent from :attr:`pairs` is never a
    member here even if its record declares a completion month, because a
    withheld pair means the ordinary predicate already excludes the descendant,
    and the increment can only ever add to a contributing pair, never grant one.
    """


def resolve_maternidad_meses(
    record: object,
    snapshot: RegistrySnapshot,
    *,
    schema: ProfileSchemaDefinition | None = None,
    operation: PinnedAuthorityOperation,
) -> MaternidadMesesResolution:
    """Resolve the Art. 81.1 maternidad months a profile record contributes.

    Owns the fact-index projection as well as the predicate, so the calculate
    path asks one question of this module rather than assembling the inputs
    itself. The index is built exactly as profile-sourced bindings build it, so
    the Art. 81.1 eligibility question is asked of the same facts every other
    Art. 58 question is asked of.

    ``ceilings_resolved`` is ``False`` when the revision on the
    :class:`RegistrySnapshot` ``snapshot`` does not declare the
    Art. 58.1 / Art. 61 norma 2ª parameters. The deducción is then withheld
    rather than granted against a fabricated ceiling — the same refusal the
    mínimo aggregate makes, for the same reason — and the caller discloses it
    rather than letting a declared figure vanish.
    """
    if schema is None:
        schema = operation.profile_schema()
    fact_index = profile_fact_index(record, schema)
    return _resolve_maternidad_meses_from_fact_index(
        fact_index,
        snapshot,
        context=family_fact_context(snapshot, operation=operation),
    )


def _fact_index_declares_maternidad_months(fact_index: Mapping[str, UserProfileFactValue]) -> bool:
    """Return whether the profile fact projection declares maternity months."""
    return any(
        key.startswith("renta_family.descendiente.") and key.endswith(".meses_madre_trabajo") for key in fact_index
    )


def _maternidad_ceiling_unavailable_resolution(*, declares_meses: bool) -> MaternidadMesesResolution:
    """Withhold pre-2023 maternity months when the statutory ceiling is unavailable."""
    return MaternidadMesesResolution(
        pairs=(),
        withheld_indices=(),
        ceilings_resolved=True,
        declares_meses=declares_meses,
        cotizaciones_ceiling_inexpressible=True,
    )


def _maternidad_thresholds_unresolved_resolution(*, declares_meses: bool) -> MaternidadMesesResolution:
    """Withhold maternity months when the revision exposes no required thresholds."""
    return MaternidadMesesResolution(
        pairs=(),
        withheld_indices=(),
        ceilings_resolved=False,
        declares_meses=declares_meses,
    )


def _maternidad_withheld_indices(
    profile: RentaFamilyProfile,
    contributed: Mapping[str, int],
) -> tuple[str, ...]:
    """Name descendants declaring months that contributed no eligible months."""
    return tuple(
        str(index)
        for index, descendant in enumerate(profile.descendientes)
        if descendant.meses_madre_trabajo and contributed.get(str(index), 0) == 0
    )


def _maternidad_alta_posterior_hijos(
    profile: RentaFamilyProfile,
    contributed: Mapping[str, int],
    *,
    filing_year: int,
    context: FamilyFactResolutionContext,
) -> frozenset[str]:
    """Return eligible descendants carrying the post-birth alta increment."""
    return frozenset(
        str(index)
        for index, descendant in enumerate(profile.descendientes)
        if contributed.get(str(index), 0) > 0
        and descendant.maternidad_alta_posterior_increment_applies(filing_year, context=context)
    )


def _maternidad_resolved_resolution(
    profile: RentaFamilyProfile,
    pairs: tuple[tuple[str, int], ...],
    *,
    filing_year: int,
    declares_meses: bool,
    context: FamilyFactResolutionContext,
) -> MaternidadMesesResolution:
    """Project eligible pairs and their dependent maternity diagnostics."""
    contributed = dict(pairs)
    return MaternidadMesesResolution(
        pairs=pairs,
        withheld_indices=_maternidad_withheld_indices(profile, contributed),
        ceilings_resolved=True,
        declares_meses=declares_meses,
        alta_posterior_hijos=_maternidad_alta_posterior_hijos(
            profile,
            contributed,
            filing_year=filing_year,
            context=context,
        ),
    )


def _resolve_maternidad_meses_from_fact_index(
    fact_index: Mapping[str, UserProfileFactValue],
    snapshot: RegistrySnapshot,
    *,
    context: FamilyFactResolutionContext,
) -> MaternidadMesesResolution:
    """Resolve maternidad months from the canonical profile fact projection.

    :func:`resolve_maternidad_meses` owns the record-to-fact projection for
    calculate diagnostics.  Derived-profile injection already has that same
    projection while resolving bindings, so it calls this helper rather than
    reconstructing the family a second way.
    """
    declares_meses = _fact_index_declares_maternidad_months(fact_index)
    try:
        cotizaciones_ceiling_retired_year = context.integer("lirpf-art-81-contribution-ceiling-retired-effective-year")
    except RegistryValidationError:
        # The retired-ceiling fact begins with the amendment that removed it.
        # An earlier filing coordinate cannot establish that later legal fact,
        # so preserve the established refusal rather than infer a cutoff.
        return _maternidad_ceiling_unavailable_resolution(
            declares_meses=declares_meses,
        )
    if snapshot.filing_year < cotizaciones_ceiling_retired_year:
        # Until 2022 the deducción was capped at the mother's cotizaciones
        # devengadas in the period. The engine cannot apply that cap: the
        # cotizaciones binding exists only in the 2024 revision and the profile
        # fact is 2024-pinned, so no figure is reachable for these years.
        # Computing anyway would grant an un-ceilinged deducción, which
        # over-grants and therefore under-declares.
        return _maternidad_ceiling_unavailable_resolution(
            declares_meses=declares_meses,
        )
    thresholds = resolved_minimo_descendientes_thresholds(snapshot)
    if thresholds is None:
        return _maternidad_thresholds_unresolved_resolution(
            declares_meses=declares_meses,
        )
    profile = renta_family_profile_from_facts(fact_index)
    # The pairing is the DOMAIN's, asked for rather than recomposed here.
    pairs = profile.meses_maternidad_por_descendiente(snapshot.filing_year, thresholds=thresholds, context=context)
    return _maternidad_resolved_resolution(
        profile,
        pairs,
        filing_year=snapshot.filing_year,
        declares_meses=declares_meses,
        context=context,
    )


def inject_derived_deduccion_maternidad_facts(
    fact_index: dict[str, UserProfileFactValue],
    snapshot: RegistrySnapshot,
    declared_selectors: frozenset[str],
    *,
    context: FamilyFactResolutionContext | None = None,
    operation: PinnedAuthorityOperation,
) -> None:
    """Inject the Art. 81.1 maternidad deduction (casilla 0611) into *fact_index*.

    The registry has no per-descendant fold.  The canonical profile-resolution
    path therefore decides each child's qualifying months and post-birth alta
    cap, then projects the one legally-derived total that the binding-leaf 0611
    formula consumes.  The declared ``profile`` binding is the enrolment switch:
    revisions without it do not gain this producer by accident.

    The producer is deliberately absent when its eligibility thresholds cannot
    be resolved.  A zero would claim that no deduction is due, while absence
    leaves the formula unresolved and lets the calculate-path diagnostic name
    the missing legal basis.  Never preserve a stored value at this synthetic
    selector: it is derived from the descendant record at calculation time.

    Takes ``snapshot`` as a :class:`RegistrySnapshot`.
    """
    if context is None:
        context = family_fact_context(snapshot, operation=operation)
    key = f"renta_family.deduccion_maternidad_{snapshot_authored_year(snapshot)}"
    if key not in declared_selectors:
        return

    resolution = _resolve_maternidad_meses_from_fact_index(fact_index, snapshot, context=context)
    if not resolution.ceilings_resolved or resolution.cotizaciones_ceiling_inexpressible:
        return

    fact_index[key] = Decimal(
        compute_deduccion_maternidad_0611(
            list(resolution.pairs),
            filing_year=snapshot.filing_year,
            alta_posterior_hijos=resolution.alta_posterior_hijos,
        )
    )
