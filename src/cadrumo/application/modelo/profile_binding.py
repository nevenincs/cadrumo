"""Application-owned profile-sourced Modelo binding resolution.

A registry binding with ``source = "profile"`` carries a value the
operator already entered onto their user profile (tax-residence CCAA,
censo status, declaration type, ...). Without an explicit resolution
step the calculation engine never sees those facts: the operator would
have to re-type, via ``--binding KEY=VALUE``, data the profile already
holds, and a formula that consumes an unsupplied profile binding fails
with ``binding ... has no supplied value``.

This module loads the bucket's :class:`UserProfileRecord`, walks every
``source = "profile"`` binding the :class:`RegistrySnapshot` revision declares,
and projects the matching profile fact into the correct engine channel.
The resolved bindings use :class:`ProfileSchemaDefinition` and
:class:`UserProfileFactValue` to translate raw facts.

The :class:`ModeloRevision` on that snapshot is also what decides whether a
derived-fact injector runs at all: the injectors are gated on the revision
declaring a binding that consumes their output, so extending coverage to a
new filing year is registry work rather than a code edit.

Channel selection is the load-bearing decision. The registry runtime
resolves profile bindings through three engine channels:
``date_binding_values`` for date operands, ``enum_binding_values`` for
dispatch keys, and Decimal-valued ``binding_values`` for numeric
operands. The channel is determined by the consumer shape:
:func:`expression_date_binding_refs` finds date operands,
:func:`enum_consumed_binding_ids` finds enum dispatch operands, and
formula-consumed or bound numeric casillas use the Decimal channel. A
calculation-only typed enum also uses the enum channel. Profile bindings
that only populate identity or export-layout fields are intentionally left
out of the calculation source mesh.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from datetime import date
from decimal import Decimal

from pydantic import BaseModel

from ...core import BindingSourceKind, CalculationSourceLineageRole
from ...core.decimal import coerce_decimal
from ...core.external_constants import DEDUCCION_MATERNIDAD_COTIZACIONES_CEILING_RETIRED_FILING_YEAR, UTF_8_ENCODING
from ...core.hashing import sha256_hex
from ...core.parsing import parse_iso8601_date
from ...domain.calculations.registry.binding_selector_utils import selector_as_dict
from ...domain.calculations.registry.formula_runtime_ops import resolve_parameter
from ...domain.calculations.registry.ids import BindingId
from ...domain.calculations.registry.runtime_graph import (
    enum_consumed_binding_ids,
    expression_binding_refs,
    expression_date_binding_refs,
)
from ...domain.calculations.registry.schema import DataBindingDefinition, ModeloRevision, RegistrySnapshot
from ...domain.calculations.registry.schema_formula import ParameterDefinition
from ...domain.contribuyente import (
    CCAA,
    MinimoDescendientesThresholds,
    RentaFamilyProfile,
    RentaMaritalStatus,
    compute_deduccion_maternidad_0611,
    descendant_list_from_facts,
    marriage_full_year,
    marriage_month_start,
)
from ...domain.modelos import ModeloError
from ...domain.user_profile.errors import ProfileNotFoundError
from ...domain.user_profile.loader import load_user_profile_schema
from ...domain.user_profile.registry_contract import profile_binding_selectors
from ...domain.user_profile.schema import ProfileSchemaDefinition, derived_selector_for_path
from ...domain.user_profile.values import UserProfileFactValue
from ..aggregation import (
    CalculationSourceDiagnostic,
    CalculationSourceProvenance,
    CalculationSourceResolution,
)
from ..user_profile.projections import profile_fact_index

_PROFILE_RESOLVER_ID = "profile"
_PROFILE_OWNED_SOURCES: tuple[BindingSourceKind, ...] = (BindingSourceKind.PROFILE,)
# Marital-status token sets, derived from the enum rather than restated.
#
# Every predicate below reads ``renta_taxpayer.marital_status``, which the
# profile schema constrains to :class:`RentaMaritalStatus` -- the AEAT ECIVIL
# filing code, ``'1'``-``'5'``. These sets previously also carried word forms
# (``"casado"``, ``"pareja_hecho_registrada"``, ...) belonging to
# :class:`SituacionFamiliar`, a DIFFERENT taxonomy stored at a different field
# (``renta_family.situacion_familiar``). Those words could never match a value
# this field can hold, so they were dead -- and worse than dead: a test passing
# a word form straight to an injector matched on the dead half while every real
# filer took the code half, so dropping a CODE from the set regressed
# production and failed nothing. Measured: removing ``'5'`` left the word form
# answering True while the code form flipped to False.
#
# Deriving them from the enum removes the foreign vocabulary by construction
# and makes a future divergence a type error rather than a silent miss.
#
# SOURCE CHOICE, deliberate. The Art. 61 norma 1a conjunta question is an
# Art. 82.1 question, and :class:`SituacionFamiliar` is the canonical Art. 82
# authority. This still reads the ECIVIL code because both fields are
# ``required = false`` and are asked side by side in the same setup walk, so
# neither is more reliably populated -- while switching would silently drop the
# prorrata for any profile carrying only the ECIVIL code, which is the
# OVER-granting direction. If the source is ever moved, note that
# ``SituacionFamiliar`` distinguishes registered from unregistered pareja de
# hecho and Art. 82.1.2a is registration-agnostic, so BOTH must count as
# partnered; treating only the registered form as partnered would over-grant
# for an unregistered couple.
_MARRIED_STATUS_TOKENS = frozenset({RentaMaritalStatus.CASADO.value})
_PARTNERED_STATUS_TOKENS = _MARRIED_STATUS_TOKENS | frozenset({RentaMaritalStatus.PAREJA_HECHO.value})
_UNMARRIED_STATUS_TOKENS = frozenset(
    member.value for member in RentaMaritalStatus if member is not RentaMaritalStatus.CASADO
)
_MARRIAGE_DERIVED_FACT_PATHS = (
    "renta_taxpayer.marriage_full_year",
    "renta_taxpayer.marriage_month_start",
    "renta_taxpayer.marriage_month_end",
)
_ECONOMIC_ACTIVITY_INCOME_CATEGORY = "actividad_economica"
_ECONOMIC_ACTIVITY_PREDICATE_BINDING_SUFFIX = "-profile-has-economic-activity"


class ProfileBindingResolutionError(ModeloError):
    """Raised when a profile-sourced binding cannot be resolved for a calculation."""


def _profile_record_fingerprint(profile_record: object | None) -> str | None:
    """Return a stable provenance fingerprint for the loaded profile record."""
    if profile_record is None:
        return None
    payload = profile_record.model_dump_json() if isinstance(profile_record, BaseModel) else repr(profile_record)
    digest = sha256_hex(payload.encode(UTF_8_ENCODING))
    return f"sha256:{digest}"


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
    Values are injected as ``Decimal`` so the Decimal-channel binding resolver
    picks them up without a special case in the main loop.

    This function is idempotent: if the keys are already present (e.g. written
    as explicit profile facts by an older tooling version) they are not
    overwritten.
    """
    raw_date = fact_index.get("renta_taxpayer.marriage_date")
    if not isinstance(raw_date, date):
        marital_status = str(fact_index.get("renta_taxpayer.marital_status", "")).strip().lower()
        if marital_status in _UNMARRIED_STATUS_TOKENS:
            for fact_path in _MARRIAGE_DERIVED_FACT_PATHS:
                fact_index.setdefault(fact_path, Decimal("0"))
        return

    month_start = marriage_month_start(raw_date, filing_year)
    if month_start is None:
        # marriage_date is in a future filing year — derived facts not applicable.
        return

    full_year = marriage_full_year(raw_date, filing_year)

    if "renta_taxpayer.marriage_full_year" not in fact_index:
        fact_index["renta_taxpayer.marriage_full_year"] = Decimal("1") if full_year else Decimal("0")
    if "renta_taxpayer.marriage_month_start" not in fact_index:
        fact_index["renta_taxpayer.marriage_month_start"] = Decimal(month_start)
    if "renta_taxpayer.marriage_month_end" not in fact_index:
        fact_index["renta_taxpayer.marriage_month_end"] = Decimal("12")


def _declared_profile_selectors(revision: ModeloRevision) -> frozenset[str]:
    """Every selector the revision's ``source = "profile"`` bindings name.

    The gate on whether a derived injector has any consumer at all. Keying on
    this rather than on a hardcoded filing-year set means a new revision needs
    registry work only: declare the binding and the injector starts running.
    A year the registry does not cover has no consuming binding, so the
    injector is a no-op rather than a silent wrong answer -- and if a binding
    IS declared and still resolves to nothing, the derived-scope advisory in
    :func:`_derived_binding_diagnostics` reports it.
    """
    return frozenset(
        selector
        for binding in revision.bindings
        if binding.source == BindingSourceKind.PROFILE
        for selector in profile_binding_selectors(binding.selector)
    )


def _inject_derived_family_facts(
    fact_index: dict[str, UserProfileFactValue],
    filing_year: int,
    declared_selectors: frozenset[str],
) -> None:
    """Inject the two Art. 81.2 guardería terms of the 0613 cap into *fact_index*.

    Both are read off :class:`~domain.contribuyente.RentaFamilyProfile` rather
    than re-derived here, and that is the point of this function's present
    shape. It used to carry its own loop summing
    ``renta_family.descendiente.{n}.gastos_guarderia`` under an inline
    ``age < 3`` test, which made it a SECOND aggregation path beside the
    canonical record's. The two then diverged the moment the record learned the
    Art. 81.2 month rules: a descendant declaring only the monthly map
    contributed the annual field's absent zero here, so the taxpayer could enter
    their spend, see it stored, and receive nothing.

    Computes ALWAYS: a value already present at either key is overwritten
    rather than deferred to. Both paths are declared derived, so the engine
    owns them and a stored fact there can only be a stale or hand-planted
    value. Deferring to it silently substituted an operator's number for the
    law's. This mutates the ephemeral per-calculation index and never
    persists, so a stray stored fact becomes inert rather than erased.

    Gated on a consuming binding rather than on a hardcoded filing year: the
    injector runs for whatever year the registry declares a consumer for, so
    extending coverage is registry work with no code edit.

    Note on the count path's NAME, which is now the honest one.
    ``descendientes_guarderia_{year}`` carries the GUARDERÍA population, wider
    than "menor de 3 al devengo" by exactly the period a child turns three since
    the Art. 81.2 month rules landed. It was called
    ``descendientes_menores_3_{year}`` until this rename, and the old name was a
    lie in the load-bearing direction: it named the Art. 58.2 statutory count
    while carrying the wider one, so a reader correcting the mismatch could
    plausibly have narrowed the VALUE to match the NAME. That would cap a
    turning-three child's spend at zero and hand back the under-grant the
    extension exists to close.

    The statutory count keeps the old name, correctly, on
    :meth:`~domain.contribuyente.RentaFamilyProfile.descendientes_menores_3_year_end`.
    The two are different populations and always were; only one of them was
    misnamed.
    """
    guarderia_key = f"renta_family.descendientes_guarderia_{filing_year}"
    gastos_key = f"renta_family.gastos_guarderia_reales_{filing_year}"
    if guarderia_key not in declared_selectors and gastos_key not in declared_selectors:
        return

    profile = _renta_family_profile_from_facts(fact_index)
    fact_index[guarderia_key] = Decimal(profile.descendientes_guarderia_count(filing_year))
    fact_index[gastos_key] = Decimal(profile.gastos_guarderia_reales(filing_year))


def _renta_family_profile_from_facts(
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
    that carried the pre-check lacked this, and the guardería injector used that
    one; the count it feeds does not read anualidades, so adding them there is a
    no-op by inspection rather than by accident, and is stated so no later reader
    reads it as a behaviour change.

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

    alta increment (:meth:`~domain.contribuyente.DescendantInfo.maternidad_alta_posterior_increment_applies`)
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
    fact_index = profile_fact_index(record, schema if schema is not None else load_user_profile_schema())
    return _resolve_maternidad_meses_from_fact_index(fact_index, snapshot)


def _resolve_maternidad_meses_from_fact_index(
    fact_index: Mapping[str, UserProfileFactValue],
    snapshot: RegistrySnapshot,
) -> MaternidadMesesResolution:
    """Resolve maternidad months from the canonical profile fact projection.

    :func:`resolve_maternidad_meses` owns the record-to-fact projection for
    calculate diagnostics.  Derived-profile injection already has that same
    projection while resolving bindings, so it calls this helper rather than
    reconstructing the family a second way.
    """
    declares_meses = any(
        key.startswith("renta_family.descendiente.") and key.endswith(".meses_madre_trabajo") for key in fact_index
    )
    if snapshot.filing_year < DEDUCCION_MATERNIDAD_COTIZACIONES_CEILING_RETIRED_FILING_YEAR:
        # Until 2022 the deducción was capped at the mother's cotizaciones
        # devengadas in the period. The engine cannot apply that cap: the
        # cotizaciones binding exists only in the 2024 revision and the profile
        # fact is 2024-pinned, so no figure is reachable for these years.
        # Computing anyway would grant an un-ceilinged deducción, which
        # over-grants and therefore under-declares.
        return MaternidadMesesResolution(
            pairs=(),
            withheld_indices=(),
            ceilings_resolved=True,
            declares_meses=declares_meses,
            cotizaciones_ceiling_inexpressible=True,
        )
    thresholds = _resolved_minimo_descendientes_thresholds(snapshot)
    if thresholds is None:
        return MaternidadMesesResolution(
            pairs=(),
            withheld_indices=(),
            ceilings_resolved=False,
            declares_meses=declares_meses,
        )
    profile = _renta_family_profile_from_facts(fact_index)
    # The pairing is the DOMAIN's, asked for rather than recomposed here. This
    # resolver used to build it inline while `meses_maternidad_por_descendiente`
    # computed the same thing with no production caller -- two authorities for
    # one answer, which is how the guarderia half once drifted from its record.
    pairs = profile.meses_maternidad_por_descendiente(snapshot.filing_year, thresholds=thresholds)
    contributed = dict(pairs)
    return MaternidadMesesResolution(
        pairs=pairs,
        withheld_indices=tuple(
            str(index)
            for index, descendant in enumerate(profile.descendientes)
            if descendant.meses_madre_trabajo and contributed.get(str(index), 0) == 0
        ),
        ceilings_resolved=True,
        declares_meses=declares_meses,
        # Consulted only for a hijo_id already carried in `pairs` above: the
        # increment can only ever add to a contributing pair, never grant one
        # a withheld or zero-months descendant does not have.
        alta_posterior_hijos=frozenset(
            str(index)
            for index, descendant in enumerate(profile.descendientes)
            if contributed.get(str(index), 0) > 0
            and descendant.maternidad_alta_posterior_increment_applies(snapshot.filing_year)
        ),
    )


_MINIMO_DESCENDIENTES_BIRTH_ORDER_SUFFIXES = (
    "primer-hijo",
    "segundo-hijo",
    "tercer-hijo",
    "cuarto-y-siguientes",
)
_MINIMO_DESCENDIENTES_MENOR_TRES_SUFFIX = "menor-tres-anos"


def _minimo_descendientes_parameter(
    snapshot: RegistrySnapshot,
    *,
    filing_year: int,
    suffix: str,
    ccaa_infix: str | None = None,
) -> ParameterDefinition | None:
    """Return the Art. 58 mínimo-por-descendientes registry parameter for *suffix*.

    Parameter ids follow the uniform ``renta-{year}-minimo-descendientes-
    {suffix}-{year}`` shape across every 2020-2025 revision (e.g.
    ``renta-2024-minimo-descendientes-primer-hijo-2024``). When *ccaa_infix*
    is supplied the id gains a CCAA segment
    (``renta-{year}-minimo-descendientes-{ccaa_infix}-{suffix}-{year}``, e.g.
    ``renta-2024-minimo-descendientes-madrid-tercer-hijo-2024``) — the shape a
    comunidad's own Art. 46 Ley 22/2009 divergent figure uses. Returns
    ``None`` when the revision declares no such parameter (a revision outside
    the engine's supported filing-year set, or a CCAA with no published
    divergent figure for this tranche).
    """
    infix = f"{ccaa_infix}-" if ccaa_infix else ""
    parameter_id = f"renta-{filing_year}-minimo-descendientes-{infix}{suffix}-{filing_year}"
    for parameter in snapshot.revision.parameters:
        if parameter.id == parameter_id:
            return parameter
    return None


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
    CCAA.MADRID.value: "madrid",
}


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
    filing_year = snapshot.filing_year
    date_context = {"filing_period": date(filing_year, 12, 31)}

    def _resolve_tranche(suffix: str) -> Decimal | None:
        specific = (
            _minimo_descendientes_parameter(snapshot, filing_year=filing_year, suffix=suffix, ccaa_infix=ccaa_infix)
            if ccaa_infix
            else None
        )
        general = _minimo_descendientes_parameter(snapshot, filing_year=filing_year, suffix=suffix)
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


_MINIMO_DESCENDIENTES_FALLECIMIENTO_SUFFIX = "fallecimiento"
_MINIMO_DESCENDIENTES_RENTAS_LIMITE_SUFFIX = "rentas-anuales-limite"
_MINIMO_DESCENDIENTES_DECLARACION_PROPIA_SUFFIX = "declaracion-propia-rentas-limite"


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
    filing_year = snapshot.filing_year
    date_context = {"filing_period": date(filing_year, 12, 31)}

    def _resolve(suffix: str) -> Decimal | None:
        parameter = _minimo_descendientes_parameter(snapshot, filing_year=filing_year, suffix=suffix)
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
        return marital_status in _PARTNERED_STATUS_TOKENS - _MARRIED_STATUS_TOKENS
    if marital_status in _PARTNERED_STATUS_TOKENS:
        return True
    return any(
        str(value).strip() != ""
        for key, value in fact_index.items()
        if key.startswith("renta_spouse.") and value is not None
    )


def inject_derived_minimo_descendientes_facts(
    fact_index: dict[str, UserProfileFactValue],
    snapshot: RegistrySnapshot,
) -> None:
    """Inject the Art. 58/61 LIRPF mínimo por descendientes aggregates (casillas 0513/0514).

    Reads the existing ``renta_family.descendiente.{n}.*`` facts, ranks every
    Art. 58.1-eligible descendant by ``birth_date``, and computes two
    aggregates via
    :meth:`~cadrumo.domain.contribuyente.RentaFamilyProfile.minimo_descendientes_estatal`
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
    """
    estatal_key = f"renta_family.descendientes_minimos_aggregate_{snapshot.filing_year}"
    autonomico_key = f"renta_family.descendientes_minimos_aggregate_autonomico_{snapshot.filing_year}"

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

    profile = _renta_family_profile_from_facts(fact_index)
    second_filer_indicated = second_entitled_filer_indicated(fact_index)

    birth_order_amounts, menor_tres_supplement, fallecimiento_amount = estatal_tranches
    fact_index[estatal_key] = profile.minimo_descendientes_estatal(
        snapshot.filing_year,
        birth_order_amounts=birth_order_amounts,
        menor_tres_supplement=menor_tres_supplement,
        fallecimiento_amount=fallecimiento_amount,
        thresholds=thresholds,
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
        second_filer_indicated=second_filer_indicated,
    )


_ANUALIDADES_ALIMENTOS_KEY = "renta_family.anualidades_alimentos_euros"


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
    """
    filing_year = snapshot.filing_year
    key = f"renta_family.anualidades_sin_minimo_descendientes_{filing_year}"
    if key not in _declared_profile_selectors(snapshot.revision):
        return
    thresholds = _resolved_minimo_descendientes_thresholds(snapshot)
    if thresholds is None:
        # Without the eligibility ceilings this flag cannot be derived on the
        # same predicate as the aggregates; leaving it unresolved keeps the two
        # surfaces from disagreeing about who holds the mínimo.
        return
    descendant_facts = {
        fact_key: str(value)
        for fact_key, value in fact_index.items()
        if fact_key.startswith("renta_family.descendiente.")
    }
    shared_custody = any(
        descendant.custodia_compartida
        and descendant.is_eligible_ordinary(
            filing_year,
            thresholds=thresholds,
            # Explicitly False: this régimen only exists for a filer who PAYS
            # anualidades, and a paying filer already has the dependency
            # assimilation suppressed for every descendant. See this function's
            # docstring for why the two halves cannot collide, and for what
            # expires when per-child attribution lands.
            dependencia_assimilation_available=False,
        )
        for descendant in descendant_list_from_facts(descendant_facts)
    )
    fact_index[key] = Decimal("0") if shared_custody else Decimal("1")


_MADRID_CCAA_CODE = "madrid"
_CONJUNTA_DECLARATION_TYPE = "2"
_AUTONOMIC_DEDUCCION_ELIGIBLE_COUNT_KEY = "renta_family.madrid_nacimiento_adopcion_eligible_count"
_UNIDAD_FAMILIAR_OTROS_MIEMBROS_BASE_KEY = "renta_family.unidad_familiar_otros_miembros_base"
MADRID_AUTONOMIC_DEDUCCION_FILING_YEAR = 2025


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
    return marital_status in _PARTNERED_STATUS_TOKENS


def madrid_nacimiento_adopcion_candidate_weighted_count(
    fact_index: Mapping[str, UserProfileFactValue],
    filing_year: int,
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
    descendant_facts = {
        key: str(value) for key, value in fact_index.items() if key.startswith("renta_family.descendiente.")
    }
    weighted_count = Decimal("0")
    for descendant in descendant_list_from_facts(descendant_facts):
        if descendant.is_nacimiento_adopcion_eligible(filing_year):
            weighted_count += descendant.nacimiento_adopcion_prorrateo_share()
    return weighted_count


def inject_derived_autonomic_deduccion_facts(
    fact_index: dict[str, UserProfileFactValue],
    filing_year: int,
) -> None:
    """Inject the Madrid nacimiento/adopción deducción derived facts (casilla 1039).

    Companion to :func:`inject_derived_marriage_facts` and
    :func:`_inject_derived_family_facts`. Reads the existing
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

    Only the 2025 filing year is handled (the first-slice registry formula);
    other years return early. Idempotent: keys already present are not
    overwritten.
    """
    if filing_year != MADRID_AUTONOMIC_DEDUCCION_FILING_YEAR:
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

    weighted_count = madrid_nacimiento_adopcion_candidate_weighted_count(fact_index, filing_year)
    if weighted_count <= 0:
        return

    fact_index[_AUTONOMIC_DEDUCCION_ELIGIBLE_COUNT_KEY] = weighted_count


_GUARDERIA_CAP_PARAMETER_SUFFIX = "guarderia-incremento-cap-anual"


def _guarderia_cap_anual(snapshot: RegistrySnapshot) -> Decimal | None:
    """Resolve the Art. 81.2 annual cap parameter for the snapshot's filing year.

    Its own registry parameter rather than the inline literal the 0613 formula
    carries: a literal inside a formula expression is registry data the
    application layer cannot read, and the per-child proration is computed
    here. Returns ``None`` when the revision declares no such parameter, which
    leaves the aggregate unresolved rather than proceeding against a guessed
    ceiling.
    """
    parameter_id = f"renta-{snapshot.filing_year}-{_GUARDERIA_CAP_PARAMETER_SUFFIX}"
    for parameter in snapshot.revision.parameters:
        if parameter.id == parameter_id:
            return resolve_parameter(parameter, {"filing_period": date(snapshot.filing_year, 12, 31)})
    return None


def _inject_derived_incremento_guarderia_facts(
    fact_index: dict[str, UserProfileFactValue],
    snapshot: RegistrySnapshot,
    declared_selectors: frozenset[str],
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
    """
    key = f"renta_family.incremento_guarderia_{snapshot.filing_year}"
    if key not in declared_selectors:
        return

    cap_anual = _guarderia_cap_anual(snapshot)
    if cap_anual is None:
        return
    thresholds = _resolved_minimo_descendientes_thresholds(snapshot)
    if thresholds is None:
        return

    profile = _renta_family_profile_from_facts(fact_index)
    fact_index[key] = profile.incremento_guarderia_0613(
        snapshot.filing_year,
        thresholds=thresholds,
        cap_anual=cap_anual,
    )


def _inject_derived_deduccion_maternidad_facts(
    fact_index: dict[str, UserProfileFactValue],
    snapshot: RegistrySnapshot,
    declared_selectors: frozenset[str],
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
    """
    key = f"renta_family.deduccion_maternidad_{snapshot.filing_year}"
    if key not in declared_selectors:
        return

    resolution = _resolve_maternidad_meses_from_fact_index(fact_index, snapshot)
    if not resolution.ceilings_resolved or resolution.cotizaciones_ceiling_inexpressible:
        return

    fact_index[key] = Decimal(
        compute_deduccion_maternidad_0611(
            list(resolution.pairs),
            filing_year=snapshot.filing_year,
            alta_posterior_hijos=resolution.alta_posterior_hijos,
        )
    )


def _inject_derived_state_attribution_facts(
    fact_index: dict[str, UserProfileFactValue],
) -> None:
    """Inject the M303 state-attribution ratio derived from jurisdiction_scope.

    The IVA model attributes the periodic result to the State (territorio
    común) vs the foral administrations as a percentage in casilla 65. The
    profile records the operator's jurisdiction as the typed enum
    ``tax_residence.jurisdiction_scope`` with values ``common_regime`` (the
    full State attribution applies) or ``foral_unsupported`` (the foral
    branch is not supported; the calc downstream emits zero, blocking the
    filing). Project the enum onto the Decimal-channel synthetic key
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
    if scope == "foral_unsupported":
        # Explicit foral selection: the foral branch is unsupported; the calc
        # downstream emits zero, blocking the filing.
        fact_index[synthetic_key] = Decimal("0")
    elif scope == "common_regime":
        fact_index[synthetic_key] = Decimal("100")
    else:
        raise ProfileBindingResolutionError(
            f"unsupported tax_residence.jurisdiction_scope {scope!r}; state attribution is unresolved",
        )


def _decimal_value(binding_id: BindingId, value: object) -> Decimal:
    # Boolean-typed profile facts arrive as Python ``bool`` now that
    # ``profile_fact_index`` preserves the typed value. ``bool`` is a
    # subclass of ``int``, so ``isinstance(value, bool)`` must be tested
    # before ``isinstance(value, (int, Decimal))`` to avoid the ``1``/``0``
    # integer path silently accepting booleans.
    if isinstance(value, bool):
        return Decimal("1") if value else Decimal("0")
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int):
        return Decimal(value)
    raise ProfileBindingResolutionError(
        f"profile fact for Decimal-channel binding {binding_id!r} is not decimal-compatible; "
        f"got value type {type(value).__name__!r}. The registry consumes this binding as a "
        f"numeric operand; the profile fact must carry a numeric value",
        translated_message="application.modelo.profile_binding.errors.decimal_value_type_invalid",
        context={"binding_id": binding_id, "value_type": type(value).__name__},
    )


@dataclass(slots=True)
class _ResolvedBindingChannels:
    """Mutable accumulator for the three engine channels a profile binding routes into.

    The Decimal channel carries numeric operands, the enum channel carries
    string dispatch keys, and the date channel carries date-typed facts. Object
    identity of the three dicts is preserved across the resolution loop so
    :func:`_route_resolved_binding` mutates the same accumulator in place.
    """

    decimal_values: dict[BindingId, Decimal] = dataclass_field(default_factory=dict)
    enum_values: dict[BindingId, str] = dataclass_field(default_factory=dict)
    date_values: dict[BindingId, date] = dataclass_field(default_factory=dict)


def _route_resolved_binding(
    binding_id: BindingId,
    value: UserProfileFactValue,
    *,
    is_date_channel: bool,
    is_enum_channel: bool,
    channels: _ResolvedBindingChannels,
) -> None:
    """Route one resolved profile fact into its engine channel on ``channels``.

    The caller has already skipped ``None`` (absent) facts. Date-channel facts
    must be ``date``; enum-channel facts must not be ``bool``; otherwise the fact
    is projected through the Decimal channel via :func:`_decimal_value`.
    """
    if is_date_channel:
        # Date-channel bindings carry date-typed facts (e.g. birth_date)
        # consumed by the age_at_year_end op.  They must not be projected
        # through the Decimal or enum channels.
        if not isinstance(value, date):
            raise ProfileBindingResolutionError(
                f"profile fact for date-channel binding {binding_id!r} must be a date, got {type(value).__name__!r}",
                translated_message="application.modelo.profile_binding.errors.date_value_type_invalid",
                context={"binding_id": binding_id, "value_type": type(value).__name__},
            )
        channels.date_values[binding_id] = value
    elif is_enum_channel:
        # Boolean-typed facts must never reach the enum dispatch channel —
        # enum dispatch keys are string category codes, not yes/no flags.
        # A bool here signals a mis-wired registry binding; refuse early
        # rather than letting the engine silently mismatch the dispatch table.
        if isinstance(value, bool):
            raise ProfileBindingResolutionError(
                f"profile fact for enum-channel binding {binding_id!r} resolved to a boolean "
                f"({value!r}); boolean facts are not valid enum dispatch keys",
                translated_message="application.modelo.profile_binding.errors.enum_boolean_invalid",
                context={"binding_id": binding_id, "value_type": "bool"},
            )
        channels.enum_values[binding_id] = str(value)
    else:
        # The resolver projects profile facts into engine channels; it does not
        # invent values the operator never supplied. Per-verb baselines own the
        # "operator declared nothing" semantics for each call site, because the
        # right default differs per verb (single-filer for projection vs.
        # explicit operator entry for work_calculate). The classifier discovered
        # 9 of 12 M100 profile bindings are core inputs whose zero-default
        # corrupts the calculation, not optional levers — a blanket
        # resolver-side zero is structurally wrong.
        channels.decimal_values[binding_id] = _decimal_value(binding_id, value)


@dataclass(frozen=True, slots=True)
class _ProfileBindingSelection:
    """Profile bindings the source mesh must resolve, plus the date-consumed set."""

    bindings: tuple[DataBindingDefinition, ...]
    formula_date_consumed: frozenset[BindingId]


@dataclass(frozen=True, slots=True)
class _ProfileFacts:
    """The bucket's resolved profile fact index plus its record fingerprint."""

    fact_index: dict[str, UserProfileFactValue]
    fingerprint: str | None


def _is_calculation_only_profile_binding(binding: DataBindingDefinition) -> bool:
    selector = binding.selector
    return not any(
        (
            getattr(selector, "xsd_path", None),
            getattr(selector, "xsd_attribute", None),
            getattr(selector, "dictionary_field", None),
        )
    )


def _is_relevant_profile_binding(
    binding: DataBindingDefinition,
    *,
    formula_consumed: set[BindingId],
    formula_date_consumed: set[BindingId],
    bound_casilla_binding_ids: set[BindingId],
) -> bool:
    return binding.source == BindingSourceKind.PROFILE and (
        binding.id in formula_consumed
        or binding.id in formula_date_consumed
        or binding.id in bound_casilla_binding_ids
        or _is_calculation_only_profile_binding(binding)
    )


def _select_profile_bindings(snapshot: RegistrySnapshot) -> _ProfileBindingSelection:
    """Select the ``source = "profile"`` bindings the source mesh must resolve.

    A profile binding matters to the calculation source mesh when a formula
    consumes it, when it feeds a ``bound`` NUMERIC input casilla (e.g. M303
    casilla 65), or when it is a calculation-only selector. The latter has no
    XSD/dictionary export address: M202's INCN applicability fact and M036's
    censo event are registry-owned profile inputs even though neither is read
    by a numeric formula. Identity/export-layout bindings (NIF, display name,
    and similar) retain an export address and must not be pushed through a
    calculation channel.
    """
    formula_consumed: set[BindingId] = set()
    formula_date_consumed: set[BindingId] = set()
    for formula in snapshot.revision.formulas:
        formula_consumed.update(expression_binding_refs(formula.expression))
        formula_date_consumed.update(expression_date_binding_refs(formula.expression))
    _numeric_casilla_data_types = {"decimal", "money", "integer", "ratio"}
    bound_casilla_binding_ids: set[BindingId] = {
        casilla.binding
        for casilla in snapshot.revision.casillas
        if casilla.binding is not None and casilla.data_type in _numeric_casilla_data_types
    }
    bindings = tuple(
        binding
        for binding in snapshot.revision.bindings
        if _is_relevant_profile_binding(
            binding,
            formula_consumed=formula_consumed,
            formula_date_consumed=formula_date_consumed,
            bound_casilla_binding_ids=bound_casilla_binding_ids,
        )
    )
    return _ProfileBindingSelection(bindings=bindings, formula_date_consumed=frozenset(formula_date_consumed))


def _load_profile_facts(
    snapshot: RegistrySnapshot,
    *,
    bucket_id: str,
    profile_record: object | None,
    schema: ProfileSchemaDefinition | None,
    selected_bindings: tuple[DataBindingDefinition, ...],
) -> _ProfileFacts | None:
    """Load and derive the bucket's profile fact index, or ``None`` when absent."""
    record = profile_record
    if record is None:
        from ..user_profile.profile_record_repository import ProfileRecordRepository

        try:
            record = ProfileRecordRepository.for_current_session(bucket_id).load(bucket_id)
        except ProfileNotFoundError:
            return None
    profile_record_fingerprint = _profile_record_fingerprint(record)
    resolved_schema = schema if schema is not None else load_user_profile_schema()
    fact_index = profile_fact_index(record, resolved_schema)
    inject_derived_marriage_facts(fact_index, snapshot.filing_year)
    declared_selectors = _declared_profile_selectors(snapshot.revision)
    _inject_derived_family_facts(fact_index, snapshot.filing_year, declared_selectors)
    inject_derived_anualidades_eligibility_facts(fact_index, snapshot)
    inject_derived_autonomic_deduccion_facts(fact_index, snapshot.filing_year)
    inject_derived_minimo_descendientes_facts(fact_index, snapshot)
    _inject_derived_deduccion_maternidad_facts(fact_index, snapshot, declared_selectors)
    _inject_derived_incremento_guarderia_facts(fact_index, snapshot, declared_selectors)
    if "tax_residence.state_attribution_ratio" in {
        selector for binding in selected_bindings for selector in profile_binding_selectors(binding.selector)
    }:
        _inject_derived_state_attribution_facts(fact_index)
    return _ProfileFacts(fact_index=fact_index, fingerprint=profile_record_fingerprint)


def _resolve_profile_binding_channels(
    bindings: tuple[DataBindingDefinition, ...],
    fact_index: Mapping[str, UserProfileFactValue],
    *,
    caller_binding_ids: frozenset[BindingId],
    formula_date_consumed: frozenset[BindingId],
    enum_bindings: frozenset[BindingId],
) -> _ResolvedBindingChannels:
    """Resolve each selected binding into the Decimal / enum / date engine channels."""
    channels = _ResolvedBindingChannels()
    for binding in bindings:
        binding_id = binding.id
        if binding_id in caller_binding_ids:
            continue
        value = resolve_profile_binding_value(binding, fact_index)
        if value is None:
            continue
        _route_resolved_binding(
            binding_id,
            value,
            is_date_channel=binding_id in formula_date_consumed,
            is_enum_channel=binding_id in enum_bindings or binding.typed_enum is not None,
            channels=channels,
        )
    return channels


def _profile_value_channel_ids(
    decimal_values: Mapping[BindingId, Decimal],
    enum_values: Mapping[BindingId, str],
    date_values: Mapping[BindingId, date],
) -> frozenset[BindingId]:
    """Union the three value channels a profile resolution populates."""
    return frozenset(set(decimal_values) | set(enum_values) | set(date_values))


def profile_resolved_binding_ids(resolution: CalculationSourceResolution) -> frozenset[BindingId]:
    """Return the binding ids a profile resolution actually satisfied.

    :class:`CalculationSourceResolution` is the shared envelope for every
    source resolver and carries seven value channels; a profile resolution
    populates exactly three of them. Which three is a fact about this
    resolver, so it is stated here once rather than re-encoded by each
    consumer -- the Modelo binding-readiness gate and the operator state
    projection previously open-coded the same union independently, and a
    fourth channel would have been picked up by whichever site was edited.

    Args:
        resolution: The result returned by
            :func:`resolve_profile_sourced_bindings`.

    Returns:
        The binding ids the profile satisfied, across all populated channels.
    """
    return _profile_value_channel_ids(
        resolution.binding_values,
        resolution.enum_binding_values,
        resolution.date_binding_values,
    )


def resolve_profile_sourced_bindings(
    snapshot: RegistrySnapshot,
    *,
    bucket_id: str,
    profile_record: object | None = None,
    caller_binding_ids: frozenset[BindingId] = frozenset(),
    schema: ProfileSchemaDefinition | None = None,
) -> CalculationSourceResolution:
    """Resolve every ``source = "profile"`` binding the revision declares.

    Args:
        snapshot: The :class:`RegistrySnapshot` whose revision's profile bindings
            are resolved against the bucket's user profile facts.
        bucket_id: Stable bucket identifier used to load the user profile.
        profile_record: Optional :class:`UserProfileRecord` override for testing.
        caller_binding_ids: Binding ids already supplied by the caller; these are
            skipped so caller overrides take precedence over the profile.
        schema: Optional profile schema definition override.

    Walks the registry revision's ``source = "profile"`` bindings,
    matches each against a fact on the bucket's user profile, and routes
    the value into the Decimal, enum, or date channel according to the
    consuming formula, bound numeric casilla, or calculation-only selector
    with no export address.

    A binding the profile cannot satisfy is skipped silently: the engine
    surfaces the missing-binding error only if a formula needs it.
    A bucket with no profile yields an empty result.

    Returns a :class:`CalculationSourceResolution` with resolved binding
    values split across the Decimal, enum, and date engine channels and a
    :class:`CalculationSourceProvenance` row per profile-sourced binding.

    See Also:
        :func:`enum_consumed_binding_ids`:
            Identifies profile bindings consumed as enum dispatch keys.
        :func:`expression_date_binding_refs`:
            Identifies profile bindings consumed by date-aware formula ops.
    """
    selection = _select_profile_bindings(snapshot)
    if not selection.bindings:
        return CalculationSourceResolution(resolver_id=_PROFILE_RESOLVER_ID, owned_sources=_PROFILE_OWNED_SOURCES)
    facts = _load_profile_facts(
        snapshot,
        bucket_id=bucket_id,
        profile_record=profile_record,
        schema=schema,
        selected_bindings=selection.bindings,
    )
    if facts is None:
        return CalculationSourceResolution(resolver_id=_PROFILE_RESOLVER_ID, owned_sources=_PROFILE_OWNED_SOURCES)
    channels = _resolve_profile_binding_channels(
        selection.bindings,
        facts.fact_index,
        caller_binding_ids=caller_binding_ids,
        formula_date_consumed=selection.formula_date_consumed,
        enum_bindings=enum_consumed_binding_ids(snapshot.revision),
    )
    decimal_values = channels.decimal_values
    enum_values = channels.enum_values
    date_values = channels.date_values
    sourced = tuple(sorted(_profile_value_channel_ids(decimal_values, enum_values, date_values)))
    fingerprint = facts.fingerprint if sourced else None
    return CalculationSourceResolution(
        resolver_id=_PROFILE_RESOLVER_ID,
        owned_sources=_PROFILE_OWNED_SOURCES,
        binding_values=decimal_values,
        enum_binding_values=enum_values,
        date_binding_values=date_values,
        diagnostics=_derived_binding_diagnostics(
            selection.bindings,
            facts.fact_index,
            schema if schema is not None else load_user_profile_schema(),
            bucket_id=bucket_id,
        ),
        provenance=tuple(
            CalculationSourceProvenance(
                resolver_id=_PROFILE_RESOLVER_ID,
                resolved_binding_source=BindingSourceKind.PROFILE,
                contributor_source_kind=BindingSourceKind.PROFILE.value,
                contributor_binding_source=BindingSourceKind.PROFILE,
                lineage_role=CalculationSourceLineageRole.PRIMARY,
                source_ref=f"profile:{bucket_id}:binding:{binding_id}",
                parent_source_ref=None,
                fingerprint=fingerprint,
            )
            for binding_id in sourced
        ),
    )


def _derived_binding_diagnostics(
    bindings: tuple[DataBindingDefinition, ...],
    fact_index: Mapping[str, UserProfileFactValue],
    schema: ProfileSchemaDefinition,
    *,
    bucket_id: str,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Advise on a SELECTED derived binding that still resolved to nothing.

    Narrow by construction, and that narrowness is the whole design. A blanket
    "profile binding resolved to nothing" advisory would fire constantly on
    optional facts an ordinary filer legitimately leaves blank, and an
    operator who learns to ignore an advisory is worse off than one who never
    saw it.

    A DERIVED path is different: the engine owns it and every derived injector
    now writes unconditionally, with a zero default where the law says zero.
    So a derived binding that is selected and still resolves to nothing cannot
    be an ordinary absence -- no injector claimed it, which means a structural
    gap (a registry year with no injector coverage, or a pattern whose
    consuming binding drifted). Every fire is real.
    """
    diagnostics: list[CalculationSourceDiagnostic] = []
    for binding in bindings:
        if resolve_profile_binding_value(binding, fact_index) is not None:
            continue
        for selector in profile_binding_selectors(binding.selector):
            derived = derived_selector_for_path(selector, schema.derived_selectors)
            if derived is None:
                continue
            diagnostics.append(
                CalculationSourceDiagnostic(
                    reason="unresolved_derived_binding",
                    source_kind=BindingSourceKind.PROFILE.value,
                    resolver_id=_PROFILE_RESOLVER_ID,
                    binding_id=binding.id,
                    source_ref=f"profile:{bucket_id}:binding:{binding.id}",
                    message=(
                        f"binding {binding.id!r} selects the engine-derived path {selector!r} "
                        f"but no value was computed for it; the aggregate derived from "
                        f"{', '.join(derived.derived_from)} is missing from this calculation"
                    ),
                ),
            )
            break
    return tuple(diagnostics)


def resolve_profile_binding_value(
    binding: DataBindingDefinition,
    fact_index: Mapping[str, UserProfileFactValue],
) -> UserProfileFactValue | None:
    """Return the typed profile fact value for one profile binding, or None if absent."""
    if binding.id.endswith(_ECONOMIC_ACTIVITY_PREDICATE_BINDING_SUFFIX):
        raw_categories = str(fact_index.get("taxpayer_type.irpf_income_categories", ""))
        categories = {token.strip() for token in raw_categories.split(",") if token.strip()}
        return Decimal("1") if _ECONOMIC_ACTIVITY_INCOME_CATEGORY in categories else Decimal("0")
    # ``profile_binding_selectors`` returns the binding's DEPENDENCY set -- every
    # fact it references -- and that includes ``required_when_profile_key``. The
    # gate fact states WHETHER the binding applies, never WHAT it holds, so it
    # must not stand in as a value. Without this, a gated binding whose real
    # fact is absent silently resolves to its precondition: a conjunta filing
    # missing the spouse's birth date wrote the declaration type ("2") into
    # DPFNAC_C, and a missing EU country wrote a boolean into ZRUE2 -- wrong
    # values on a filed artefact, indistinguishable from real ones. Measured
    # across the whole registry: 12 gated bindings, all Modelo 100, every one
    # declaring a real profile_key/profile_keys, so skipping the gate here
    # can never leave a binding with nothing to resolve from.
    # Read through the registry's own selector normaliser rather than getattr.
    # ``selector`` is legally ``BindingSelector | Mapping``, and on the Mapping
    # shape a getattr returns None, which does not weaken this gate -- it deletes
    # it, silently, and reinstates exactly the regression described above. The
    # accessor answers both shapes, so the gate cannot be defeated by an input
    # shape the type already permits.
    gate_selector = selector_as_dict(binding).get("required_when_profile_key")
    for selector in profile_binding_selectors(binding.selector):
        if gate_selector is not None and selector == gate_selector:
            continue
        value = fact_index.get(selector)
        if value is None:
            continue
        # Blank strings are treated as absent; all other typed values (bool,
        # Decimal, date, int) are non-blank by definition.
        if isinstance(value, str) and not value.strip():
            continue
        return value.strip() if isinstance(value, str) else value
    return None


__all__ = [
    "MADRID_AUTONOMIC_DEDUCCION_FILING_YEAR",
    "MaternidadMesesResolution",
    "ProfileBindingResolutionError",
    "inject_derived_anualidades_eligibility_facts",
    "inject_derived_autonomic_deduccion_facts",
    "inject_derived_marriage_facts",
    "inject_derived_minimo_descendientes_facts",
    "is_indeterminate_unidad_familiar",
    "is_madrid_resident",
    "madrid_nacimiento_adopcion_candidate_weighted_count",
    "profile_resolved_binding_ids",
    "resolve_maternidad_meses",
    "resolve_profile_binding_value",
    "resolve_profile_sourced_bindings",
    "second_entitled_filer_indicated",
]
