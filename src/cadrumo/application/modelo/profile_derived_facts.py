"""Derive Modelo profile facts from taxpayer and family records."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from ...core.decimal.coercion import coerce_decimal
from ...core.parsing.dates import parse_iso8601_date
from ...domain.calculations.registry.errors import RegistryValidationError
from ...domain.calculations.registry.formula_runtime_ops import resolve_parameter
from ...domain.calculations.registry.m303_schema_vocabulary import (
    m303_tax_territory_state_attribution_ratio,
)
from ...domain.calculations.registry.schema import ModeloRevision, RegistrySnapshot
from ...domain.calculations.registry.schema_formula import ParameterDefinition
from ...domain.contribuyente.deduccion_maternidad import compute_deduccion_maternidad_0611
from ...domain.contribuyente.descendant_facts import descendant_list_from_facts
from ...domain.contribuyente.family_fact_context import FamilyFactResolutionContext
from ...domain.contribuyente.family_profile import RentaFamilyProfile
from ...domain.contribuyente.family_types import MinimoDescendientesThresholds
from ...domain.contribuyente.marriage_facts import marriage_full_year, marriage_month_start
from ...domain.contribuyente.renta_codes import RentaMaritalStatus
from ...domain.modelos.errors import ModeloError
from ...domain.user_profile.registry_contract import profile_binding_selectors
from ...domain.user_profile.schema import ProfileSchemaDefinition
from ...domain.user_profile.values import UserProfileFactValue
from ..user_profile.projections import profile_fact_index

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation


class ProfileBindingResolutionError(ModeloError):
    """Raised when a profile-sourced binding cannot be resolved for a calculation."""


MARRIED_STATUS_TOKENS = frozenset({RentaMaritalStatus.CASADO.value})

PARTNERED_STATUS_TOKENS = MARRIED_STATUS_TOKENS | frozenset({RentaMaritalStatus.PAREJA_HECHO.value})

UNMARRIED_STATUS_TOKENS = frozenset(
    member.value for member in RentaMaritalStatus if member is not RentaMaritalStatus.CASADO
)

_MARRIAGE_DERIVED_MONTH_FACT_PATHS = (
    "renta_taxpayer.marriage_month_start",
    "renta_taxpayer.marriage_month_end",
)

_MARITIME_WORKER_CLASS_FACT_PATH = "maritime_worker.worker_class"

_MARITIME_ORDINARY_WORK_FACTS: tuple[tuple[str, UserProfileFactValue], ...] = (
    ("maritime_worker.exemption_path_rebeca", False),
    ("maritime_worker.gross_navigation_income", Decimal("0")),
    ("maritime_worker.annual_salary", Decimal("0")),
    ("maritime_worker.qualifying_days", Decimal("0")),
)

_MINIMO_DESCENDIENTES_BIRTH_ORDER_SUFFIXES = (
    "primer-hijo",
    "segundo-hijo",
    "tercer-hijo",
    "cuarto-y-siguientes",
)

_MINIMO_DESCENDIENTES_MENOR_TRES_SUFFIX = "menor-tres-anos"

_MINIMO_DESCENDIENTES_AUTONOMICO_CCAA_INFIXES: dict[str, str] = {
    # Ley 22/2009 art. 46.1.a) cedes normative competence over the mínimo
    # personal y familiar's autonómico half to each comunidad, within a ±10%
    # band per concept. Only Comunidad de Madrid's divergent mínimo por
    # descendientes table is wired today (Decreto Legislativo 1/2010, art. 2,
    # grounded verbatim against the bundled AEAT Renta manuals 2020-2025,
    # part 1, "Comunidad de Madrid: Importes del mínimo..."); a CCAA absent
    # from this table falls back to the estatal tranches (the pre-existing
    # mirror-estatal default), matching the 0511/0512 mínimo-del-contribuyente
    # precedent. Other CCAA that publish their own mínimo por descendientes
    # figures for 2025 (Andalucía, Asturias, Baleares, Canarias, Galicia,
    # Comunitat Valenciana per the bundled 2025 manual) are a named follow-up,
    # not silently assumed to mirror estatal forever.
    # The left-hand token is the schema parameter-id segment, not a catalogue
    # lookup.  Keep it as syntax so importing this binding module cannot open
    # an ambient governed-fact scope; the declared profile value is matched
    # against it only after the enclosing snapshot has projected that value.
    "madrid": "madrid",
}

_MINIMO_DESCENDIENTES_FALLECIMIENTO_SUFFIX = "fallecimiento"

_MINIMO_DESCENDIENTES_RENTAS_LIMITE_SUFFIX = "rentas-anuales-limite"

_MINIMO_DESCENDIENTES_DECLARACION_PROPIA_SUFFIX = "declaracion-propia-rentas-limite"

_ANUALIDADES_ALIMENTOS_KEY = "renta_family.anualidades_alimentos_euros"

_MADRID_CCAA_CODE = "madrid"

_CONJUNTA_DECLARATION_TYPE = "2"

_AUTONOMIC_DEDUCCION_ELIGIBLE_COUNT_KEY = "renta_family.madrid_nacimiento_adopcion_eligible_count"

_UNIDAD_FAMILIAR_OTROS_MIEMBROS_BASE_KEY = "renta_family.unidad_familiar_otros_miembros_base"

_MADRID_AUTONOMIC_DEDUCCION_APPLICABILITY_FACT_ID = "madrid-nacimiento-adopcion-applicability"

_GUARDERIA_CAP_PARAMETER_SUFFIX = "guarderia-incremento-cap-anual"


def family_fact_context(
    snapshot: RegistrySnapshot,
    *,
    operation: PinnedAuthorityOperation,
) -> FamilyFactResolutionContext:
    """Compose the family governed-fact context for one modelo snapshot.

    Takes ``snapshot`` as a :class:`RegistrySnapshot`.
    """
    coordinate = date(snapshot.filing_year, 12, 31)
    return FamilyFactResolutionContext(
        authority=operation,
        filing_period=coordinate,
        devengo_date=coordinate,
    )


def inject_ordinary_work_maritime_facts(fact_index: dict[str, UserProfileFactValue]) -> None:
    """Resolve the maritime exemption inputs of a taxpayer with no maritime classification.

    The profile schema states that an unclassified worker receives the ordinary
    treatment of employment income, so neither the art. 7.p LIRPF nor the art.
    75 Ley 19/1994 exemption reaches them: the exemption path is not REBECA and
    every exempt-income input is a proven zero. A taxpayer classified as a
    maritime worker is left untouched, so an incomplete maritime profile still
    refuses the calculation instead of borrowing these values. Facts already
    present are never overwritten.
    """
    if fact_index.get(_MARITIME_WORKER_CLASS_FACT_PATH) is not None:
        return
    for fact_path, value in _MARITIME_ORDINARY_WORK_FACTS:
        fact_index.setdefault(fact_path, value)


def inject_derived_marriage_facts(
    fact_index: dict[str, UserProfileFactValue],
    filing_year: int,
) -> None:
    """Inject computed matrimonio-sobrevenido integers into *fact_index* in-place.

    When ``renta_taxpayer.marriage_date`` is present as a ``date``-typed fact,
    the three derived binding keys (``marriage_full_year``,
    ``marriage_month_start``, ``marriage_month_end``) are computed from the raw
    date and the snapshot's ``filing_year``.  For an explicitly unmarried
    taxpayer the same casillas are neutral zeros: Art. 82 marriage-month facts
    are not applicable, and the CLI must not force a single filer to invent a
    marriage date.  Married taxpayers without a marriage date remain unresolved.
    The two month figures are injected as ``Decimal`` counts. The full-year
    fact is a yes/no question and is injected as a real ``bool``, which is what
    its binding's boolean value contract requires: a ``Decimal("0")`` standing
    in for "not married the whole year" is indistinguishable from a zero-valued
    count once it reaches the Decimal channel.

    This function is idempotent: if the keys are already present (e.g. written
    as explicit profile facts by an older tooling version) they are not
    overwritten.
    """
    raw_date = fact_index.get("renta_taxpayer.marriage_date")
    if not isinstance(raw_date, date):
        marital_status = str(fact_index.get("renta_taxpayer.marital_status", "")).strip().lower()
        if marital_status in UNMARRIED_STATUS_TOKENS:
            fact_index.setdefault("renta_taxpayer.marriage_full_year", False)
            for fact_path in _MARRIAGE_DERIVED_MONTH_FACT_PATHS:
                fact_index.setdefault(fact_path, Decimal("0"))
        return

    month_start = marriage_month_start(raw_date, filing_year)
    if month_start is None:
        # marriage_date is in a future filing year — derived facts not applicable.
        return

    full_year = marriage_full_year(raw_date, filing_year)

    if "renta_taxpayer.marriage_full_year" not in fact_index:
        fact_index["renta_taxpayer.marriage_full_year"] = full_year
    if "renta_taxpayer.marriage_month_start" not in fact_index:
        fact_index["renta_taxpayer.marriage_month_start"] = Decimal(month_start)
    if "renta_taxpayer.marriage_month_end" not in fact_index:
        fact_index["renta_taxpayer.marriage_month_end"] = Decimal("12")


def _authored_year(snapshot: RegistrySnapshot) -> int:
    """Return the year a snapshot's revision was authored for.

    Derived profile selectors and the revision's date context are keyed by it:
    a projected snapshot reuses its source revision's declarations, and a
    snapshot carrying no projection is authored for its own filing year.
    Formatting the optional field directly would key an unprojected snapshot
    as ``..._None``, which no declared selector matches, and the injector
    would skip the fact without a word.
    """
    return snapshot.authored_filing_year or snapshot.filing_year


def declared_profile_selectors(revision: ModeloRevision) -> frozenset[str]:
    """Every selector the revision's ``source = "profile"`` bindings name.

    The gate on whether a derived injector has any consumer at all. Keying on
    this rather than on a hardcoded filing-year set means a new revision needs
    registry work only: declare the binding and the injector starts running.
    A year the registry does not cover has no consuming binding, so the
    injector is a no-op rather than a silent wrong answer -- and if a binding
    IS declared and still resolves to nothing, the derived-scope advisory in
    :func:`_derived_binding_diagnostics` reports it.

    Takes ``revision`` as a :class:`ModeloRevision`.
    """
    return frozenset(
        selector for binding in revision.bindings for selector in profile_binding_selectors(binding.provider)
    )


def renta_family_profile_from_facts(
    fact_index: Mapping[str, UserProfileFactValue],
) -> RentaFamilyProfile:
    """Rebuild the canonical family record from the stored profile facts.

    ONE reconstruction, carrying the UNION of what two used to carry separately.
    That is the point of the function and the reason it must not be simplified
    back: each of the two halves had something the other lacked, so collapsing
    onto either wholesale was a silent regression in a different direction.

    The BIRTH-DATE PRE-CHECK refuses an unparseable stored date by INDEX. The
    canonical reconstruction refuses too, but names the field without saying
    which row carries it, and that diagnostic was written deliberately: an
    unparseable stored date is a data defect the operator can fix once told where
    it is. Skipping the row instead would silently under-count the cap population
    and drop that child's spend. The reconstruction that carried the anualidades
    lacked this, so an operator on that path was told a date was bad and not
    which one.

    The ANUALIDADES figure is what suppresses the Art. 58 dependency assimilation
    for every descendant, so a record rebuilt without it answers "is this
    descendant entitled to the mínimo?" with the assimilation always available —
    over-granting for a filer who pays judicial anualidades. The reconstruction
    that carried the pre-check lacked this.

    Shared rather than rebuilt per consumer because the mínimo aggregate, the
    anualidades régimen flag and the Art. 81.1 deducción por maternidad all ask
    the SAME question of the same descendant in the same calculation — the
    authority defines the qualifying child for the deducción as one "con derecho
    a la aplicación del mínimo por descendientes". Two reconstructions let those
    answers diverge.
    """
    idx = 0
    while True:
        birth_raw = fact_index.get(f"renta_family.descendiente.{idx}.birth_date")
        if birth_raw is None:
            break
        try:
            birth = parse_iso8601_date(str(birth_raw))
        except (ValueError, TypeError) as exc:
            raise ProfileBindingResolutionError(
                f"renta_family.descendiente.{idx}.birth_date is not a valid ISO-8601 date: {birth_raw!r}",
            ) from exc
        if birth is None:
            raise ProfileBindingResolutionError(
                f"renta_family.descendiente.{idx}.birth_date is not a valid ISO-8601 date: {birth_raw!r}",
            )
        idx += 1
    descendant_facts = {
        fact_key: str(value)
        for fact_key, value in fact_index.items()
        if fact_key.startswith("renta_family.descendiente.")
    }
    return RentaFamilyProfile(
        descendientes=descendant_list_from_facts(descendant_facts),
        anualidades_alimentos_euros=_declared_anualidades_alimentos(fact_index),
    )


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
    thresholds = _resolved_minimo_descendientes_thresholds(snapshot)
    if thresholds is None:
        return _maternidad_thresholds_unresolved_resolution(
            declares_meses=declares_meses,
        )
    profile = renta_family_profile_from_facts(fact_index)
    # The pairing is the DOMAIN's, asked for rather than recomposed here. This
    # resolver used to build it inline while `meses_maternidad_por_descendiente`
    # computed the same thing with no production caller -- two authorities for
    # one answer, which is how the guarderia half once drifted from its record.
    pairs = profile.meses_maternidad_por_descendiente(snapshot.filing_year, thresholds=thresholds, context=context)
    return _maternidad_resolved_resolution(
        profile,
        pairs,
        filing_year=snapshot.filing_year,
        declares_meses=declares_meses,
        context=context,
    )


def _minimo_descendientes_parameter(
    snapshot: RegistrySnapshot,
    *,
    suffix: str,
    ccaa_infix: str | None = None,
) -> ParameterDefinition | None:
    """Return the Art. 58 mínimo-por-descendientes registry parameter for *suffix*.

    Parameter ids keep one ``renta-minimo-descendientes-{suffix}`` identity
    across every revision (e.g. ``renta-minimo-descendientes-primer-hijo``);
    the selected revision supplies the figure for its filing year. When
    *ccaa_infix* is supplied the id gains a CCAA segment
    (``renta-minimo-descendientes-{ccaa_infix}-{suffix}``, e.g.
    ``renta-minimo-descendientes-madrid-tercer-hijo``) — the shape a
    comunidad's own Art. 46 Ley 22/2009 divergent figure uses. Returns
    ``None`` when the revision declares no such parameter (a revision that
    does not carry the table, or a CCAA with no published divergent figure
    for this tranche).
    """
    infix = f"{ccaa_infix}-" if (ccaa_infix is not None and ccaa_infix) else ""
    parameter_id = f"renta-minimo-descendientes-{infix}{suffix}"
    for parameter in snapshot.revision.parameters:
        if parameter.id == parameter_id:
            return parameter
    return None


def _minimo_descendientes_autonomico_ccaa_infix(fact_index: Mapping[str, UserProfileFactValue]) -> str | None:
    """Return the CCAA infix for the filer's declared tax-residence CCAA, if wired."""
    ccaa = fact_index.get("tax_residence.ccaa")
    if not isinstance(ccaa, str):
        return None
    return _MINIMO_DESCENDIENTES_AUTONOMICO_CCAA_INFIXES.get(ccaa.strip().lower())


def _resolved_minimo_descendientes_tranches(
    snapshot: RegistrySnapshot,
    *,
    ccaa_infix: str | None,
) -> tuple[list[Decimal], Decimal, Decimal] | None:
    """Resolve the birth-order tranches, menor-3 supplement, and norma 4ª flat cuantía.

    When *ccaa_infix* is ``None`` (or the CCAA-specific parameter for a given
    tranche is absent), that tranche falls back to the estatal Art. 58
    parameter — this is what makes a CCAA's PARTIAL divergence (e.g. Baleares
    regulates only the 2º/3º/4º tranches, leaving 1º at the estatal figure)
    resolve correctly rather than requiring a full parallel table per CCAA.
    Returns ``None`` when the revision does not declare the full estatal
    parameter set (the engine's supported-year gate already filters this, but
    the check stays defensive for any future partial revision).
    """
    # A projected year reuses the authored edition's dated parameter values.
    date_context = {"filing_period": date(_authored_year(snapshot), 12, 31)}

    def _resolve_tranche(suffix: str) -> Decimal | None:
        specific = (
            _minimo_descendientes_parameter(snapshot, suffix=suffix, ccaa_infix=ccaa_infix)
            if (ccaa_infix is not None and ccaa_infix)
            else None
        )
        general = _minimo_descendientes_parameter(snapshot, suffix=suffix)
        chosen = specific if specific is not None else general
        return resolve_parameter(chosen, date_context) if chosen is not None else None

    birth_order_amounts: list[Decimal] = []
    for suffix in _MINIMO_DESCENDIENTES_BIRTH_ORDER_SUFFIXES:
        amount = _resolve_tranche(suffix)
        if amount is None:
            return None
        birth_order_amounts.append(amount)

    menor_tres_supplement = _resolve_tranche(_MINIMO_DESCENDIENTES_MENOR_TRES_SUFFIX)
    if menor_tres_supplement is None:
        return None
    # Art. 61 norma 4ª's death-in-period flat cuantía. Resolved through the same
    # per-tranche CCAA fallback as the rest: no comunidad publishes a divergent
    # death figure today, so every CCAA lands on the estatal parameter, and one
    # that later does is picked up without changing this call. Its own
    # parameter, never ``birth_order_amounts[0]`` — the two figures coincide in
    # every served revision and are not the same authority.
    fallecimiento_amount = _resolve_tranche(_MINIMO_DESCENDIENTES_FALLECIMIENTO_SUFFIX)
    if fallecimiento_amount is None:
        return None
    return birth_order_amounts, menor_tres_supplement, fallecimiento_amount


def _resolved_minimo_descendientes_thresholds(
    snapshot: RegistrySnapshot,
) -> MinimoDescendientesThresholds | None:
    """Resolve the Art. 58.1 / Art. 61 norma 2ª eligibility ceilings for the revision.

    These are the two registry ``money`` parameters carrying the figures
    Art. 58.1 ("rentas anuales, excluidas las exentas, superiores a 8.000
    euros") and Art. 61 norma 2ª ("presenten declaración por este Impuesto con
    rentas superiores a 1.800 euros") state, resolved for the snapshot's filing
    year exactly as the birth-order tranches are. They are never Python
    literals (`aeat-registry-authority-flow`).

    Returns ``None`` when the revision declares neither parameter, which leaves
    the caller to skip the derivation rather than evaluate eligibility against
    a fabricated ceiling.
    """
    # A projected year reuses the authored edition's dated parameter values.
    date_context = {"filing_period": date(_authored_year(snapshot), 12, 31)}

    def _resolve(suffix: str) -> Decimal | None:
        parameter = _minimo_descendientes_parameter(snapshot, suffix=suffix)
        return resolve_parameter(parameter, date_context) if parameter is not None else None

    rentas_limite = _resolve(_MINIMO_DESCENDIENTES_RENTAS_LIMITE_SUFFIX)
    declaracion_limite = _resolve(_MINIMO_DESCENDIENTES_DECLARACION_PROPIA_SUFFIX)
    if rentas_limite is None or declaracion_limite is None:
        return None
    return MinimoDescendientesThresholds(
        rentas_anuales_limite=rentas_limite,
        declaracion_propia_rentas_limite=declaracion_limite,
    )


def second_entitled_filer_indicated(fact_index: Mapping[str, UserProfileFactValue]) -> bool:
    """Derive whether a second contribuyente is also entitled to the mínimo.

    Art. 61 norma 1ª prorates whenever two or more contribuyentes hold the
    right to the same descendant's mínimo. Whether a second filer claims is not
    a fact about the descendant, so it is derived here from signals the profile
    already carries rather than demanded as new operator input.

    An INDIVIDUAL return by a partnered filer IS prorated, because the other
    progenitor is a separate contribuyente entitled to the same descendant —
    the ordinary two-parent household this derivation exists to correct.

    A tributación CONJUNTA return turns on WHO the unidad familiar contains,
    which LIRPF art. 82.1 makes a function of marriage:

    * MARRIED (art. 82.1.1ª) — both progenitores are inside the one unit, it
      files once, and the mínimo is applied once within it. There is no second
      contribuyente to share with, so no prorrateo.
    * NOT married (art. 82.1.2ª) — the unit is ONE progenitor plus the minor
      children, and both progenitores cannot form a single unit at all. The
      other progenitor therefore remains a separate entitled contribuyente and
      norma 1ª still prorates, EVEN THOUGH this return is conjunta.

    Collapsing those two into "conjunta is never prorated" over-grants the
    mínimo for every unmarried cohabiting couple, which is an under-declaration
    of the tax. The AEAT Renta manual's Capítulo 14 worked examples print both
    outcomes and disagree by 2.550 euros on the same three children.

    Returns ``False`` for an unpartnered filer and whenever the signals are
    absent, which claims the full mínimo; the caller raises a visible advisory
    whenever this derivation decided the factor, so a wrong inference is
    correctable rather than silent.
    """
    marital_status = str(fact_index.get("renta_taxpayer.marital_status", "")).strip().lower()
    declaration_type = str(fact_index.get("renta_filing.declaration_type", "")).strip()
    if declaration_type == _CONJUNTA_DECLARATION_TYPE:
        # Only marriage puts the other progenitor inside this same unit.
        return marital_status in PARTNERED_STATUS_TOKENS - MARRIED_STATUS_TOKENS
    if marital_status in PARTNERED_STATUS_TOKENS:
        return True
    return any(
        str(value).strip() != ""
        for key, value in fact_index.items()
        if key.startswith("renta_spouse.") and value is not None
    )


def inject_derived_minimo_descendientes_facts(
    fact_index: dict[str, UserProfileFactValue],
    snapshot: RegistrySnapshot,
    *,
    context: FamilyFactResolutionContext | None = None,
    operation: PinnedAuthorityOperation,
) -> None:
    """Inject the Art. 58/61 LIRPF mínimo por descendientes aggregates (casillas 0513/0514).

    Reads the existing ``renta_family.descendiente.{n}.*`` facts, ranks every
    Art. 58.1-eligible descendant by ``birth_date``, and computes two
    aggregates via
    :meth:`~cadrumo.domain.contribuyente.family_profile.RentaFamilyProfile.minimo_descendientes_estatal`
    (a CCAA-agnostic birth-order-tranche aggregator despite its name — it takes
    the tranche amounts as caller-supplied parameters, never a hardcoded euro
    figure per `aeat-registry-authority-flow`):

    * the ESTATAL aggregate, from the revision's ``renta-{year}-minimo-
      descendientes-{suffix}-{year}`` Art. 58 parameters, projected onto
      ``renta_family.descendientes_minimos_aggregate_{year}`` — a
      user-profile schema field that was previously a dangling selector
      (declared, never populated); this injector retires that gap rather
      than minting a new key. Feeds casilla 0513 via the registry
      binding ``renta-{year}-profile-minimo-descendientes-estatal``.
    * the AUTONÓMICO aggregate, from the SAME estatal parameters UNLESS the
      filer's declared ``tax_residence.ccaa`` has a wired divergent tranche
      table (Ley 22/2009 art. 46.1.a cedes this to each comunidad within a
      ±10% band; see :data:`_MINIMO_DESCENDIENTES_AUTONOMICO_CCAA_INFIXES`),
      projected onto
      ``renta_family.descendientes_minimos_aggregate_autonomico_{year}``.
      Feeds casilla 0514 via the registry binding
      ``renta-{year}-profile-minimo-descendientes-autonomico``. A CCAA absent
      from the wired set mirrors the estatal aggregate exactly (the
      pre-existing default, matching the 0511/0512 mínimo-del-contribuyente
      precedent).

    Always injects both keys (``Decimal("0")`` for a profile with no eligible
    descendant) so a genuinely childless filer's casillas resolve to the
    legally correct zero rather than an unresolved binding failing the
    calculation outright. Computes ALWAYS: both keys are declared derived, so
    a value present at either can only be stale or hand-planted, and deferring
    to it silently substituted an operator's figure for the Art. 58/61
    computation. The write is to the ephemeral per-calculation index and never
    persists.

    No filing-year gate: the parameter-presence checks below already refuse a
    revision that does not declare the full tranche and threshold tables, which
    is the same ground the former year frozenset covered but derived from the
    registry rather than restated as a Python constant.

    Core types:
    :class:`~cadrumo.domain.calculations.registry.schema.RegistrySnapshot`.
    """
    if context is None:
        context = family_fact_context(snapshot, operation=operation)
    estatal_key = f"renta_family.descendientes_minimos_aggregate_{_authored_year(snapshot)}"
    autonomico_key = f"renta_family.descendientes_minimos_aggregate_autonomico_{_authored_year(snapshot)}"

    estatal_tranches = _resolved_minimo_descendientes_tranches(snapshot, ccaa_infix=None)
    if estatal_tranches is None:
        # The revision does not declare the full mínimo-por-descendientes
        # parameter set; leave both aggregates unresolved rather than compute
        # against a partial tranche table.
        return

    thresholds = _resolved_minimo_descendientes_thresholds(snapshot)
    if thresholds is None:
        # The revision declares tranche amounts but not the Art. 58.1 / Art. 61
        # norma 2ª eligibility ceilings. Leave the aggregates unresolved rather
        # than compute an over-granting mínimo that skips both income
        # conditions — a silently inflated figure is the defect this predicate
        # exists to close, so refusing is the safe direction.
        return

    profile = renta_family_profile_from_facts(fact_index)
    second_filer_indicated = second_entitled_filer_indicated(fact_index)

    birth_order_amounts, menor_tres_supplement, fallecimiento_amount = estatal_tranches
    fact_index[estatal_key] = profile.minimo_descendientes_estatal(
        snapshot.filing_year,
        birth_order_amounts=birth_order_amounts,
        menor_tres_supplement=menor_tres_supplement,
        fallecimiento_amount=fallecimiento_amount,
        thresholds=thresholds,
        context=context,
        second_filer_indicated=second_filer_indicated,
    )

    ccaa_infix = _minimo_descendientes_autonomico_ccaa_infix(fact_index)
    autonomico_tranches = (
        _resolved_minimo_descendientes_tranches(snapshot, ccaa_infix=ccaa_infix)
        if ccaa_infix is not None
        else estatal_tranches
    )
    if autonomico_tranches is None:
        # A wired CCAA infix resolved to a partial table (should not
        # happen given the per-tranche estatal fallback in
        # ``_resolved_minimo_descendientes_tranches``, but stays
        # defensive): fall back to the estatal tranches rather than
        # leaving the autonómico casilla unresolved.
        autonomico_tranches = estatal_tranches
    birth_order_amounts, menor_tres_supplement, fallecimiento_amount = autonomico_tranches
    fact_index[autonomico_key] = profile.minimo_descendientes_estatal(
        snapshot.filing_year,
        birth_order_amounts=birth_order_amounts,
        menor_tres_supplement=menor_tres_supplement,
        fallecimiento_amount=fallecimiento_amount,
        thresholds=thresholds,
        context=context,
        second_filer_indicated=second_filer_indicated,
    )


def _declared_anualidades_alimentos(
    fact_index: Mapping[str, UserProfileFactValue],
) -> Decimal | None:
    """Read the filer's declared judicial anualidades, or ``None`` when undeclared.

    Gates the Art. 58 dependency assimilation: a positive figure suppresses it
    for every descendant, because the statutory carve-out is per-child and this
    profile cannot yet attribute a payment to one. An unreadable value is
    treated as undeclared rather than as zero, which leaves the assimilation
    AVAILABLE - so the fail-open direction is deliberate here and is the
    opposite of this module's usual default.

    The reason it is deliberate: the alternative reads a corrupt value as "a
    large payment" and silently withdraws an allowance the authority states the
    filer is entitled to, with nothing said. Leaving it available means the
    assimilation applies only where the operator ALSO explicitly declared
    dependency per descendant, which is a second affirmative act, and the
    calculate path discloses every assimilation it grants.
    """
    raw = fact_index.get(_ANUALIDADES_ALIMENTOS_KEY)
    if raw is None:
        return None
    return coerce_decimal(raw)


def inject_derived_anualidades_eligibility_facts(
    fact_index: dict[str, UserProfileFactValue],
    snapshot: RegistrySnapshot,
    *,
    context: FamilyFactResolutionContext | None = None,
    operation: PinnedAuthorityOperation,
) -> None:
    """Inject the LIRPF art. 64/75 anualidades separate-escala eligibility flag.

    Art. 64 grants judicial anualidades por alimentos a favor de los hijos the
    separate-escala régimen only to a payer "sin derecho a la aplicación por
    estos últimos del mínimo por descendientes previsto en el artículo 58". This
    "no right to the mínimo por descendientes" fact is not derivable from any
    other casilla; it is projected here onto the synthetic Decimal key
    ``renta_family.anualidades_sin_minimo_descendientes_{year}`` the registry
    régimen predicate consumes.

    Form-faithful default: filling casilla 0527 (anualidades por decisión
    judicial) implies the non-custodial payer without the mínimo, so the flag is
    1 (eligible) unless custody is shared. When at least one eligible descendant
    has ``custodia_compartida = true`` the mínimo por descendientes is split
    50/50, the payer retains it, and the régimen does NOT apply (flag 0).

    Eligibility here is the SAME Art. 58.1 / Art. 61 predicate the two
    aggregates use, so a descendant excluded by the rentas ceiling or by the
    norma 2ª own-return rule generates no mínimo, leaves the payer legally sin
    derecho, and correctly RESTORES the separate-escala régimen. Before the
    predicate carried those conditions this flag read ``0`` for such a
    descendant and denied a régimen the payer was entitled to — the one gap in
    this campaign that over-taxes rather than under-declares.

    Computes ALWAYS: the path is declared derived, so a value present there
    can only be stale or hand-planted, and deferring to it silently decided a
    régimen question the law owns. Only the revisions carrying the
    separate-escala régimen are handled, identified by a declared consuming
    binding rather than by a hardcoded filing-year set.

    THE OTHER HALF OF THE ART. 58 DEPENDENCY INCOMPATIBILITY, stated here
    because the two rules are one pair and landing one half of a pair is this
    campaign's most repeated defect. This flag says "the payer has no right to
    the mínimo, so the separate escala applies"; the dependency assimilation
    says "a non-cohabiting supporter DOES hold the mínimo". Both cannot be true
    of the same descendant.

    They cannot collide today, and by construction rather than by luck. The
    assimilation requires the filer to declare NO positive anualidades, while
    this régimen exists only for a filer who pays them. So wherever this flag
    can be 1, the assimilation is already suppressed for every descendant, and
    the eligibility evaluated below therefore passes
    ``dependencia_assimilation_available=False`` explicitly rather than relying
    on the parameter's default - an explicit False documents the reasoning at
    the call site, where the next reader of this function will be.

    When per-child attribution of anualidades lands, that reasoning expires:
    a filer could then pay anualidades for one child and assimilate another,
    and this flag would have to be evaluated per descendant rather than once.
    Whoever lands that attribution must revisit this function in the same
    change.

    Core types:
    :class:`~cadrumo.domain.calculations.registry.schema.RegistrySnapshot`.
    """
    if context is None:
        context = family_fact_context(snapshot, operation=operation)
    filing_year = snapshot.filing_year
    key = f"renta_family.anualidades_sin_minimo_descendientes_{_authored_year(snapshot)}"
    if key not in declared_profile_selectors(snapshot.revision):
        return
    thresholds = _resolved_minimo_descendientes_thresholds(snapshot)
    if thresholds is None:
        # Without the eligibility ceilings this flag cannot be derived on the
        # same predicate as the aggregates; leaving it unresolved keeps the two
        # surfaces from disagreeing about who holds the mínimo.
        return
    descendientes = renta_family_profile_from_facts(fact_index).descendientes
    shared_custody = any(
        descendant.custodia_compartida
        and descendant.is_eligible_ordinary(
            filing_year,
            thresholds=thresholds,
            context=context,
            # Explicitly False: this régimen only exists for a filer who PAYS
            # anualidades, and a paying filer already has the dependency
            # assimilation suppressed for every descendant. See this function's
            # docstring for why the two halves cannot collide, and for what
            # expires when per-child attribution lands.
            dependencia_assimilation_available=False,
        )
        for descendant in descendientes
    )
    fact_index[key] = not shared_custody


def is_madrid_autonomic_deduccion_filing_year(
    filing_year: int,
    *,
    context: FamilyFactResolutionContext | None = None,
    operation: PinnedAuthorityOperation,
) -> bool:
    """Return whether the registry declares the Madrid deduction for *filing_year*."""
    if context is None:
        coordinate = date(filing_year, 12, 31)
        context = FamilyFactResolutionContext(
            authority=operation,
            filing_period=coordinate,
            devengo_date=coordinate,
        )
    try:
        declared_year = context.integer(_MADRID_AUTONOMIC_DEDUCCION_APPLICABILITY_FACT_ID)
    except RegistryValidationError:
        return False
    return filing_year == declared_year


def is_madrid_resident(fact_index: Mapping[str, UserProfileFactValue]) -> bool:
    """Return whether ``tax_residence.ccaa`` names the Comunidad de Madrid."""
    ccaa = fact_index.get("tax_residence.ccaa")
    return isinstance(ccaa, str) and ccaa.strip().lower() == _MADRID_CCAA_CODE


def is_indeterminate_unidad_familiar(fact_index: Mapping[str, UserProfileFactValue]) -> bool:
    """Return whether the filer's unit is a tributación-conjunta or partnered case.

    This is exactly the condition that makes the Madrid nacimiento/adopción
    over-claim guard fail-closed in :func:`inject_derived_autonomic_deduccion_facts`
    (research F9 — no persisted spouse base imponible to evaluate the
    unidad-familiar 61.860 € límite). Shared with the verify-path D4 eligibility
    advisory so both surfaces agree on exactly which units are indeterminate.
    """
    declaration_type = str(fact_index.get("renta_filing.declaration_type", "")).strip()
    if declaration_type == _CONJUNTA_DECLARATION_TYPE:
        return True
    marital_status = str(fact_index.get("renta_taxpayer.marital_status", "")).strip().lower()
    return marital_status in PARTNERED_STATUS_TOKENS


def madrid_nacimiento_adopcion_candidate_weighted_count(
    fact_index: Mapping[str, UserProfileFactValue],
    filing_year: int,
    *,
    context: FamilyFactResolutionContext | None = None,
    operation: PinnedAuthorityOperation,
) -> Decimal:
    """Return the prorrateo-weighted Madrid nacimiento/adopción eligible count.

    Evaluates only the per-descendant window/cohabitation condition (DL 1/2010
    arts. 4 y 18.1); it does NOT gate on CCAA, declaration type, or marital
    status — those over-claim guards are the caller's responsibility. This is
    the shared candidate-count primitive: the injector uses it to populate the
    casilla-1039 binding for the determinable single/monoparental case, and the
    verify-path D4 advisory uses it to detect a would-be-eligible but
    indeterminate (conjunta/married) unit that should not silently resolve to
    zero.
    """
    if context is None:
        coordinate = date(filing_year, 12, 31)
        context = FamilyFactResolutionContext(
            authority=operation,
            filing_period=coordinate,
            devengo_date=coordinate,
        )
    descendant_facts = {
        key: str(value) for key, value in fact_index.items() if key.startswith("renta_family.descendiente.")
    }
    weighted_count = Decimal("0")
    for descendant in descendant_list_from_facts(descendant_facts):
        if descendant.is_nacimiento_adopcion_eligible(filing_year, context=context):
            weighted_count += descendant.nacimiento_adopcion_prorrateo_share(context=context)
    return weighted_count


def inject_derived_autonomic_deduccion_facts(
    fact_index: dict[str, UserProfileFactValue],
    filing_year: int,
    *,
    context: FamilyFactResolutionContext | None = None,
    operation: PinnedAuthorityOperation,
) -> None:
    """Inject the Madrid nacimiento/adopción deducción derived facts (casilla 1039).

    Companion to :func:`inject_derived_marriage_facts`. Reads the existing
    ``renta_family.descendiente.{n}.*`` facts and ``tax_residence.ccaa`` and
    computes the prorrateo-weighted count of descendants inside the Comunidad de
    Madrid nacimiento/adopción applicability window (DL 1/2010 arts. 4 y 18.1)
    who cohabit, projecting it onto the synthetic Decimal keys the registry
    formula on casilla 1039 consumes.

    The trigger is fail-closed: it auto-populates only the unambiguous single /
    monoparental individual filer. A tributación conjunta declaration or a
    married filer needs the spouse's base imponible for the unidad-familiar
    61.860 € límite, which the app does not persist (research F9); for those
    cases no count is injected, the registry formula's binding default resolves
    casilla 1039 to 0, and the operator-facing eligibility advisory surfaces the
    entitlement instead. A deducción's failure mode is over-claim, so silence on
    an indeterminate unidad-familiar aggregate is the safe default.

    Only the registry-declared filing year is handled (the first-slice
    registry formula); other years return early. Idempotent: keys already present are not
    overwritten.
    """
    if context is None:
        coordinate = date(filing_year, 12, 31)
        context = FamilyFactResolutionContext(
            authority=operation,
            filing_period=coordinate,
            devengo_date=coordinate,
        )
    if not is_madrid_autonomic_deduccion_filing_year(filing_year, context=context, operation=operation):
        return

    # Always supply a neutral 0 default so the casilla-1039 formula's two profile
    # bindings resolve for EVERY M100 2025 filer — non-Madrid, tributación
    # conjunta, or no eligible descendants. The registry formula hard-fails on an
    # unsupplied binding, so the default is what keeps a Cataluña/single filer's
    # calculation from breaking; the Madrid determinable-eligible branch below
    # overrides the count with the real prorrateo-weighted value.
    fact_index.setdefault(_AUTONOMIC_DEDUCCION_ELIGIBLE_COUNT_KEY, Decimal("0"))
    fact_index.setdefault(_UNIDAD_FAMILIAR_OTROS_MIEMBROS_BASE_KEY, Decimal("0"))

    if not is_madrid_resident(fact_index):
        return
    if is_indeterminate_unidad_familiar(fact_index):
        return

    weighted_count = madrid_nacimiento_adopcion_candidate_weighted_count(
        fact_index,
        filing_year,
        context=context,
        operation=operation,
    )
    if weighted_count <= 0:
        return

    fact_index[_AUTONOMIC_DEDUCCION_ELIGIBLE_COUNT_KEY] = weighted_count


def _guarderia_cap_anual(snapshot: RegistrySnapshot) -> Decimal | None:
    """Resolve the Art. 81.2 annual cap parameter for the snapshot's filing year.

    Its own registry parameter rather than the inline literal the 0613 formula
    carries: a literal inside a formula expression is registry data the
    application layer cannot read, and the per-child proration is computed
    here. Returns ``None`` when the revision declares no such parameter, which
    leaves the aggregate unresolved rather than proceeding against a guessed
    ceiling.
    """
    parameter_id = f"renta-{_GUARDERIA_CAP_PARAMETER_SUFFIX}"
    for parameter in snapshot.revision.parameters:
        if parameter.id == parameter_id:
            return resolve_parameter(parameter, {"filing_period": date(snapshot.filing_year, 12, 31)})
    return None


def inject_derived_incremento_guarderia_facts(
    fact_index: dict[str, UserProfileFactValue],
    snapshot: RegistrySnapshot,
    declared_selectors: frozenset[str],
    *,
    context: FamilyFactResolutionContext | None = None,
    operation: PinnedAuthorityOperation,
) -> None:
    """Inject the Art. 81.2 guardería increment (casilla 0613) into *fact_index*.

    The increment is prorated per child by the months the Art. 81.1 and 81.2
    requirements hold simultaneously and bounded by that child's own
    non-subsidised spend, both stated by LIRPF art. 81.3 third paragraph, which
    caps at the spend "en relación con ese hijo". The registry schema cannot
    express a per-child fold, so the fold happens here and the registry consumes
    one resolved value — the same division of labour the mínimo por
    descendientes aggregate uses.

    Computes ALWAYS where a consumer is declared, overwriting whatever the index
    holds. The path is derived, so a stored fact at this key can only be stale
    or hand-planted, and deferring to one would substitute an operator's number
    for the law's.

    Leaves the fact ABSENT rather than writing a zero when either the cap
    parameter or the eligibility ceilings are unresolvable. A zero would read as
    a computed "no increment due" and silently withhold a real deducción; an
    absent fact leaves the casilla unresolved, which is visible.

    Gated on a declared consuming binding rather than a hardcoded filing year,
    so extending coverage to another revision is registry work with no code
    change here.

    Takes ``snapshot`` as a :class:`RegistrySnapshot`.
    """
    if context is None:
        context = family_fact_context(snapshot, operation=operation)
    key = f"renta_family.incremento_guarderia_{_authored_year(snapshot)}"
    if key not in declared_selectors:
        return

    cap_anual = _guarderia_cap_anual(snapshot)
    if cap_anual is None:
        return
    thresholds = _resolved_minimo_descendientes_thresholds(snapshot)
    if thresholds is None:
        return

    profile = renta_family_profile_from_facts(fact_index)
    fact_index[key] = profile.incremento_guarderia_0613(
        snapshot.filing_year,
        thresholds=thresholds,
        cap_anual=cap_anual,
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
    key = f"renta_family.deduccion_maternidad_{_authored_year(snapshot)}"
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


def inject_derived_state_attribution_facts(
    fact_index: dict[str, UserProfileFactValue],
    *,
    effective_date: date | None = None,
    operation: PinnedAuthorityOperation,
) -> None:
    """Inject the M303 state-attribution ratio derived from jurisdiction_scope.

    The IVA model attributes the periodic result to the State (territorio
    común) vs the foral administrations as a percentage in casilla 65. The
    profile records the operator's jurisdiction as the registry-projected
    ``tax_residence.jurisdiction_scope`` token. Project that token onto the
    Decimal-channel synthetic key
    ``tax_residence.state_attribution_ratio`` so the registry binding
    consumes it through the existing Decimal-channel resolver without a
    new enum→Decimal transform op.

    The canonical derived key overwrites any legacy stored scalar. Missing or
    unknown territory authority refuses; this function never treats the scalar
    or supported population as authority.
    """
    synthetic_key = "tax_residence.state_attribution_ratio"
    scope = fact_index.get("tax_residence.jurisdiction_scope")
    if scope is None:
        raise ProfileBindingResolutionError(
            "tax_residence.jurisdiction_scope is required; state attribution cannot default to common regime",
        )
    try:
        fact_index[synthetic_key] = m303_tax_territory_state_attribution_ratio(
            scope,
            effective_date=effective_date,
            authority=operation,
        )
    except RegistryValidationError as exc:
        raise ProfileBindingResolutionError(
            f"unsupported tax_residence.jurisdiction_scope {scope!r}; state attribution is unresolved",
        ) from exc
