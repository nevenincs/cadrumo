"""Calculation input validation and diagnostics."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from ...core.casilla_id import CasillaId
from ...domain.contribuyente.descendant_facts import descendant_list_from_facts
from ...domain.contribuyente.descendant_maternity import relacion_is_ambiguous_for_maternidad
from ..aggregation.source_mesh import CalculationSourceDiagnostic

# Intra-package reuse of a sibling module's cap, permitted by the architecture
# rule; only cross-package private reaches are barred, and that gate is separate.
from .minimo_descendientes_advisory import MAX_NAMED_DESCENDANTS
from .work_profile import ModeloWorkProfile

if TYPE_CHECKING:
    pass


_MATERNIDAD_MESES_WITHHELD_SOURCE_KIND = "maternidad_meses_withheld"


_MATERNIDAD_CEILINGS_UNRESOLVED_SOURCE_KIND = "maternidad_eligibility_ceilings_unresolved"


_MATERNIDAD_COTIZACIONES_CEILING_SOURCE_KIND = "maternidad_cotizaciones_ceiling_inexpressible"


_MATERNIDAD_AMBIGUOUS_RELACION_SOURCE_KIND = "maternidad_ambiguous_relacion"


def maternidad_ceilings_unresolved_advisory(
    declares_meses: bool,
    casilla_id: CasillaId,
) -> CalculationSourceDiagnostic | None:
    """Advise when declared months cannot be evaluated for want of the Art. 58.1 ceilings.

    A revision that declares casilla 0611 but not the eligibility parameters
    cannot answer whether a descendant holds the mínimo, so the deducción is
    withheld rather than granted against a fabricated ceiling. That is the safe
    direction and the same refusal the mínimo aggregate makes — but silence here
    is indistinguishable from a taxpayer who declared nothing, which is the state
    this whole Step exists to remove.

    Fires only when months were actually declared, so a filer with no maternidad
    facts is not told about a parameter gap that costs them nothing.
    """
    if not declares_meses:
        return None
    return CalculationSourceDiagnostic(
        reason="source_issue",
        source_kind=_MATERNIDAD_CEILINGS_UNRESOLVED_SOURCE_KIND,
        message=(
            "the active profile declares meses_madre_trabajo but this revision does not declare the "
            "Art. 58.1 rentas ceiling and the Art. 61 norma 2ª own-return ceiling, so entitlement to "
            "the mínimo por descendientes cannot be evaluated and the Art. 81.1 deducción por "
            "maternidad is withheld rather than granted against an unverified ceiling"
        ),
        casilla_id=casilla_id,
    )


def maternidad_cotizaciones_ceiling_advisory(
    withheld_for_ceiling: bool,
    casilla_id: CasillaId,
) -> CalculationSourceDiagnostic | None:
    """Advise when a pre-2023 deducción is withheld because its ceiling is unreachable.

    Until 2022 Art. 81.1 capped the deducción at the mother's "cotizaciones y
    cuotas totales a la Seguridad Social y mutualidades devengadas en cada
    período impositivo"; the Manual Práctico de Renta 2024 records the removal
    "desde el 1 de enero de 2023". The engine cannot apply that cap for the
    affected years, because the cotizaciones binding exists only in the 2024
    revision and the profile fact is 2024-pinned, so no figure is reachable.

    Granting an un-ceilinged deducción for those years would over-grant and
    therefore under-declare. Withholding is the safe direction; withholding
    SILENTLY is not, because the operator declared months and would otherwise
    see them vanish with no reason given. The remedy is theirs rather than the
    engine's: the figure is computable by hand from the certificate they hold.
    """
    if not withheld_for_ceiling:
        return None
    return CalculationSourceDiagnostic(
        reason="source_issue",
        source_kind=_MATERNIDAD_COTIZACIONES_CEILING_SOURCE_KIND,
        message=(
            "the active profile declares meses_madre_trabajo but this filing year predates 2023, when "
            "Art. 81.1 was still capped at the mother's Social Security cotizaciones devengadas in the "
            "period. This application holds no cotizaciones figure for years before 2024, so the cap "
            "cannot be applied and the deducción is withheld rather than granted un-capped. Compute it "
            "by hand as min(months x 100, 1200, cotizaciones devengadas) and enter the result with "
            "`--casilla` if filing this year."
        ),
        casilla_id=casilla_id,
    )


def ambiguous_relacion_hijo_ids(
    contributing_hijo_ids: frozenset[str],
    *,
    profile: ModeloWorkProfile,
) -> frozenset[str]:
    """*contributing_hijo_ids* whose stored ``relacion`` is the unstated default.

    Reads the active profile's descendiente records directly through the same
    canonical reconstruction (:func:`~domain.contribuyente.descendant_facts.descendant_list_from_facts`)
    every other consumer of this fact set uses, rather than adding a field to
    :class:`~application.modelo.profile_derived_facts.MaternidadMesesResolution`: this
    module already owns loading the profile record for
    :func:`_resolved_maternidad_meses`, and the question this asks — which
    contributing descendant's relación is unstated — is orthogonal to the
    months resolution that function answers.

    Which relación is ambiguous is stated once, with the manual's reasoning, by
    :func:`~domain.contribuyente.descendant_maternity.relacion_is_ambiguous_for_maternidad`. The
    reasoning used to be written out here AND at the declaration-time surface
    that asks the same question, so a member added to the axis for either
    population would have had to reach two places that only agreed by hand.

    Returns the empty set when *contributing_hijo_ids* is empty.
    """
    if not contributing_hijo_ids:
        return frozenset[str]()
    facts = {fact.path: str(fact.value) for fact in profile.record.facts if fact.value is not None}
    descendientes = descendant_list_from_facts(facts)
    return frozenset(
        hijo_id
        for hijo_id in contributing_hijo_ids
        if hijo_id.isdigit()
        and int(hijo_id) < len(descendientes)
        and relacion_is_ambiguous_for_maternidad(descendientes[int(hijo_id)].relacion)
    )


def bounded_descendant_ids(ids: Sequence[str]) -> str:
    """Render a descendant-id list for a diagnostic, bounded regardless of household size.

    The diagnostic message is length-capped by contract, and an interpolated
    per-descendant list is the only unbounded term in the messages below. Left
    unbounded it makes household size decide whether the advisory can be raised
    at all: past a threshold the message overruns the cap, the model refuses,
    and a NON-blocking advisory becomes a hard validation error that stops the
    filing -- at exactly the moment it had something to say.

    Shares :data:`MAX_NAMED_DESCENDANTS` with the sibling advisory module that
    first hit this rather than restating the number, so the two bounds cannot
    drift apart. The rendering differs (bare ids here, fact paths there) but the
    judgement being made is one judgement.
    """
    shown = ", ".join(ids[:MAX_NAMED_DESCENDANTS])
    remainder = len(ids) - MAX_NAMED_DESCENDANTS
    return f"{shown} and {remainder} more" if remainder > 0 else shown


def maternidad_ambiguous_relacion_advisory(
    ambiguous_hijo_ids: frozenset[str],
    casilla_id: CasillaId,
) -> CalculationSourceDiagnostic | None:
    """Advise when a contributing descendant's relación cannot rule out an Art. 81.1 exclusion.

    Non-blocking rather than a refusal that withholds the figure or demands an
    explicit override flag before calculating. The overwhelming majority of
    descendientes recorded under the default relación genuinely are a hijo, and
    calculate is a draft step an operator iterates on repeatedly before verify
    and export — a repeated refusal on every recalculation of the ordinary case
    would obstruct the majority for the sake of a minority this application
    cannot itself distinguish. The Notice channel this advisory rides is the
    structured operator surface, where it remains available for filer review,
    matching the established shape of every other unmodelled-eligibility-condition advisory
    on this same casilla (the cotizaciones ceiling above, and the DT 12ª
    antiquity condition elsewhere): disclose rather than silently grant, and
    disclose rather than silently block a filer this application cannot prove
    is wrong.
    """
    if not ambiguous_hijo_ids:
        return None
    return CalculationSourceDiagnostic(
        reason="source_issue",
        source_kind=_MATERNIDAD_AMBIGUOUS_RELACION_SOURCE_KIND,
        message=(
            f"descendiente {bounded_descendant_ids(sorted(ambiguous_hijo_ids))} contributes to the Art. 81.1 "
            "deducción por maternidad under the unstated relación. The manual grants the mínimo but "
            "excludes the deducción for a grandchild/other consanguinidad descendant, or a minor "
            "under judicial guarda y custodia -- the stored fact cannot distinguish either from a "
            "true hijo. Confirm this descendant is a hijo, or restate its relación on the "
            "descendiente record."
        ),
        casilla_id=casilla_id,
    )


def maternidad_meses_withheld_advisory(
    withheld: tuple[str, ...],
    casilla_id: CasillaId,
) -> CalculationSourceDiagnostic | None:
    """Advise when declared maternidad months contribute nothing on eligibility grounds.

    The one state where a taxpayer declared real months, sees them stored, and
    receives nothing — and nothing about the computed value says why. Art. 81.1
    reaches a child under three "con derecho a la aplicación del mínimo por
    descendientes" OR one inside the age-independent adopción/acogimiento
    entry-date window
    (:meth:`~domain.contribuyente.descendant_maternity.DescendantMaternityMixin.maternidad_contributing_meses`),
    so months declared against a descendant BOTH limbs exclude are correctly
    withheld; withholding them SILENTLY is what this reports.

    The remedy must not name the birth date as the fix for every withheld
    case. The entry-date limb reaches an over-three adopción or acogimiento by
    a recorded ``INSCRIPCION``/``ACOGIMIENTO`` date, not by age — so the real
    gap for that population is a missing entry date, and a message that only
    ever suggests the birth date steers that filer toward altering a fact
    that was already correct.

    Nor may the remedy name ``descendiente add`` as the way to CHANGE a
    declared row. That verb only appends, and the paged editing door
    (``aeat config profile descendiente`` with no subcommand) refuses on a
    piped host, which the non-interactive CLI contract
    always is. The actionable route is ``descendiente remove <index>`` then
    ``add`` to restate the row.
    """
    if not withheld:
        return None
    return CalculationSourceDiagnostic(
        reason="source_issue",
        source_kind=_MATERNIDAD_MESES_WITHHELD_SOURCE_KIND,
        message=(
            f"descendiente {bounded_descendant_ids(withheld)} declares meses_madre_trabajo but contributes no "
            "Art. 81.1 deducción por maternidad, which reaches a child under three OR one inside the "
            "adopción/acogimiento entry-date window. An over-three adopción/acogimiento with no entry "
            "date is withheld for a missing INSCRIPCION or ACOGIMIENTO, not a birth date. Restate the "
            "row on the descendiente record, or correct cohabitation or rentas."
        ),
        casilla_id=casilla_id,
    )
