"""Application-owned profile-sourced binding resolution.

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

from ...core import BindingSourceKind
from ...core.external_constants import UTF_8_ENCODING
from ...core.hashing import sha256_hex
from ...core.logging import get_logger
from ...core.parsing import parse_iso8601_date
from ...domain.calculations.registry import (
    BindingId,
    DataBindingDefinition,
    ParameterDefinition,
    RegistrySnapshot,
    enum_consumed_binding_ids,
    expression_binding_refs,
    expression_date_binding_refs,
    resolve_parameter,
)
from ...domain.contribuyente import (
    CCAA,
    RentaFamilyProfile,
    descendant_list_from_facts,
    marriage_full_year,
    marriage_month_start,
)
from ...domain.modelos import ModeloError
from ...domain.user_profile import (
    ProfileNotFoundError,
    ProfileSchemaDefinition,
    UserProfileFactValue,
    load_user_profile_schema,
    profile_binding_selectors,
)
from ..aggregation import (
    CalculationSourceProvenance,
    CalculationSourceResolution,
)

_PROFILE_RESOLVER_ID = "profile"
_PROFILE_OWNED_SOURCES: tuple[BindingSourceKind, ...] = (BindingSourceKind.PROFILE,)
_MARRIED_STATUS_TOKENS = frozenset({"2", "casado"})
_PARTNERED_STATUS_TOKENS = _MARRIED_STATUS_TOKENS | frozenset({"5", "pareja_hecho", "pareja_hecho_registrada"})
_UNMARRIED_STATUS_TOKENS = frozenset(
    {
        "1",
        "3",
        "4",
        "5",
        "soltero",
        "viudo",
        "separado_divorciado",
        "pareja_hecho",
        "pareja_hecho_registrada",
    }
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


def _profile_fact_index(record: object, schema: ProfileSchemaDefinition) -> dict[str, UserProfileFactValue]:
    """Build a selector -> typed-value index covering both selector forms.

    A profile binding's selector resolves either as the canonical
    ``section.field`` fact path (``profile_key`` form) or as a schema
    ``model_selector`` alias (``profile_model`` + ``field`` form). The
    index exposes each non-null fact under its canonical path AND under
    every ``model_selector`` the schema declares for it, so both
    selector forms find the value.

    Values are preserved as their original :data:`UserProfileFactValue` type
    (``bool``, ``Decimal``, ``date``, ``str``, …) so that downstream
    channel routing can branch on the concrete Python type rather than
    re-parsing a ``str(value)`` rendering.
    """
    selector_index: dict[str, tuple[str, ...]] = {}
    for section in schema.sections:
        for field in section.fields:
            selector_index[f"{section.key}.{field.key}"] = tuple(field.model_selectors)

    index: dict[str, UserProfileFactValue] = {}
    facts = getattr(record, "facts", ())
    for fact in facts:
        if fact.value is None:
            continue
        index[fact.path] = fact.value
        for selector in selector_index.get(fact.path, ()):
            index[selector] = fact.value
    return index


def _inject_derived_marriage_facts(
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


def _inject_derived_family_facts(
    fact_index: dict[str, UserProfileFactValue],
    filing_year: int,
) -> None:
    """Inject computed Art. 81 bis guardería integers into *fact_index* in-place.

    When ``renta_family.descendiente.{n}.birth_date`` facts are present the
    count of children whose age at year-end is < 3 (Art. 58.3 LIRPF) is
    computed and stored as ``renta_family.descendientes_menores_3_{year}``.

    This function is idempotent: keys already present are not overwritten.
    Only the 2024 filing year is handled; other years are ignored until a
    dedicated binding is declared.
    """
    if filing_year != 2024:
        return

    menores_key = "renta_family.descendientes_menores_3_2024"
    if menores_key in fact_index:
        return

    # Reconstruct per-descendant birth_dates from stored facts.
    count_menores = 0
    idx = 0
    while True:
        birth_raw = fact_index.get(f"renta_family.descendiente.{idx}.birth_date")
        if birth_raw is None:
            break
        convivencia_raw = fact_index.get(f"renta_family.descendiente.{idx}.convivencia", "true")
        convive = str(convivencia_raw).lower() not in ("false", "0")
        if convive:
            try:
                birth = parse_iso8601_date(str(birth_raw))
                if birth is None:
                    raise ValueError("birth date parsed as None")
                age_at_year_end = filing_year - birth.year
                if age_at_year_end < 3:
                    count_menores += 1
            except (ValueError, TypeError) as exc:
                get_logger(__name__).debug(
                    "profile-binding: failed to parse birth date for menores count; skipping entry (%s: %s)",
                    type(exc).__name__,
                    exc,
                )
        idx += 1

    fact_index[menores_key] = Decimal(count_menores)


_MINIMO_DESCENDIENTES_FILING_YEARS = frozenset({2020, 2021, 2022, 2023, 2024, 2025})
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
) -> tuple[list[Decimal], Decimal] | None:
    """Resolve the birth-order tranche amounts + menor-3 supplement for *ccaa_infix*.

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
    return birth_order_amounts, menor_tres_supplement


def _inject_derived_minimo_descendientes_facts(
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
    figure per `aeat-schema-central-config`):

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
    calculation outright. Idempotent per key: a key already present (an
    explicit profile fact written by an older tooling version) is not
    overwritten. Only the 2020-2025 filing years are handled; other years are
    ignored until the engine is extended.
    """
    if snapshot.filing_year not in _MINIMO_DESCENDIENTES_FILING_YEARS:
        return

    estatal_key = f"renta_family.descendientes_minimos_aggregate_{snapshot.filing_year}"
    autonomico_key = f"renta_family.descendientes_minimos_aggregate_autonomico_{snapshot.filing_year}"
    if estatal_key in fact_index and autonomico_key in fact_index:
        return

    estatal_tranches = _resolved_minimo_descendientes_tranches(snapshot, ccaa_infix=None)
    if estatal_tranches is None:
        # The revision does not declare the full mínimo-por-descendientes
        # parameter set; leave both aggregates unresolved rather than compute
        # against a partial tranche table.
        return

    descendant_facts = {
        fact_key: str(value)
        for fact_key, value in fact_index.items()
        if fact_key.startswith("renta_family.descendiente.")
    }
    profile = RentaFamilyProfile(descendientes=descendant_list_from_facts(descendant_facts))

    if estatal_key not in fact_index:
        birth_order_amounts, menor_tres_supplement = estatal_tranches
        fact_index[estatal_key] = profile.minimo_descendientes_estatal(
            snapshot.filing_year,
            birth_order_amounts=birth_order_amounts,
            menor_tres_supplement=menor_tres_supplement,
        )

    if autonomico_key not in fact_index:
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
        birth_order_amounts, menor_tres_supplement = autonomico_tranches
        fact_index[autonomico_key] = profile.minimo_descendientes_estatal(
            snapshot.filing_year,
            birth_order_amounts=birth_order_amounts,
            menor_tres_supplement=menor_tres_supplement,
        )


_ANUALIDADES_ELIGIBILITY_FILING_YEARS = frozenset({2020, 2021, 2022, 2023, 2024, 2025})


def _inject_derived_anualidades_eligibility_facts(
    fact_index: dict[str, UserProfileFactValue],
    filing_year: int,
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

    Idempotent: an explicit fact already present is not overwritten. Only the
    revisions carrying the separate-escala régimen are handled.
    """
    if filing_year not in _ANUALIDADES_ELIGIBILITY_FILING_YEARS:
        return
    key = f"renta_family.anualidades_sin_minimo_descendientes_{filing_year}"
    if key in fact_index:
        return
    descendant_facts = {
        fact_key: str(value)
        for fact_key, value in fact_index.items()
        if fact_key.startswith("renta_family.descendiente.")
    }
    shared_custody = any(
        descendant.custodia_compartida and descendant.is_eligible_ordinary(filing_year)
        for descendant in descendant_list_from_facts(descendant_facts)
    )
    fact_index[key] = Decimal("0") if shared_custody else Decimal("1")


_MADRID_CCAA_CODE = "madrid"
_CONJUNTA_DECLARATION_TYPE = "2"
_AUTONOMIC_DEDUCCION_ELIGIBLE_COUNT_KEY = "renta_family.madrid_nacimiento_adopcion_eligible_count"
_UNIDAD_FAMILIAR_OTROS_MIEMBROS_BASE_KEY = "renta_family.unidad_familiar_otros_miembros_base"
_MADRID_AUTONOMIC_DEDUCCION_FILING_YEAR = 2025


def _is_madrid_resident(fact_index: Mapping[str, UserProfileFactValue]) -> bool:
    """Return whether ``tax_residence.ccaa`` names the Comunidad de Madrid."""
    ccaa = fact_index.get("tax_residence.ccaa")
    return isinstance(ccaa, str) and ccaa.strip().lower() == _MADRID_CCAA_CODE


def _is_indeterminate_unidad_familiar(fact_index: Mapping[str, UserProfileFactValue]) -> bool:
    """Return whether the filer's unit is a tributación-conjunta or partnered case.

    This is exactly the condition that makes the Madrid nacimiento/adopción
    over-claim guard fail-closed in :func:`_inject_derived_autonomic_deduccion_facts`
    (research F9 — no persisted spouse base imponible to evaluate the
    unidad-familiar 61.860 € límite). Shared with the verify-path D4 eligibility
    advisory so both surfaces agree on exactly which units are indeterminate.
    """
    declaration_type = str(fact_index.get("filing_export.declaration_type", "")).strip()
    if declaration_type == _CONJUNTA_DECLARATION_TYPE:
        return True
    marital_status = str(fact_index.get("renta_taxpayer.marital_status", "")).strip().lower()
    return marital_status in _PARTNERED_STATUS_TOKENS


def _madrid_nacimiento_adopcion_candidate_weighted_count(
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


def _inject_derived_autonomic_deduccion_facts(
    fact_index: dict[str, UserProfileFactValue],
    filing_year: int,
) -> None:
    """Inject the Madrid nacimiento/adopción deducción derived facts (casilla 1039).

    Companion to :func:`_inject_derived_marriage_facts` and
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
    if filing_year != _MADRID_AUTONOMIC_DEDUCCION_FILING_YEAR:
        return

    # Always supply a neutral 0 default so the casilla-1039 formula's two profile
    # bindings resolve for EVERY M100 2025 filer — non-Madrid, tributación
    # conjunta, or no eligible descendants. The registry formula hard-fails on an
    # unsupplied binding, so the default is what keeps a Cataluña/single filer's
    # calculation from breaking; the Madrid determinable-eligible branch below
    # overrides the count with the real prorrateo-weighted value.
    fact_index.setdefault(_AUTONOMIC_DEDUCCION_ELIGIBLE_COUNT_KEY, Decimal("0"))
    fact_index.setdefault(_UNIDAD_FAMILIAR_OTROS_MIEMBROS_BASE_KEY, Decimal("0"))

    if not _is_madrid_resident(fact_index):
        return
    if _is_indeterminate_unidad_familiar(fact_index):
        return

    weighted_count = _madrid_nacimiento_adopcion_candidate_weighted_count(fact_index, filing_year)
    if weighted_count <= 0:
        return

    fact_index[_AUTONOMIC_DEDUCCION_ELIGIBLE_COUNT_KEY] = weighted_count


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

    Idempotent: if the synthetic key is already present (explicit profile
    fact written by an older tooling version) it is not overwritten.
    """
    synthetic_key = "tax_residence.state_attribution_ratio"
    if synthetic_key in fact_index:
        return
    scope = fact_index.get("tax_residence.jurisdiction_scope")
    if scope == "foral_unsupported":
        # Explicit foral selection: the foral branch is unsupported; the calc
        # downstream emits zero, blocking the filing.
        fact_index[synthetic_key] = Decimal("0")
    else:
        # common_regime, or no scope recorded. Every profile the app accepts
        # carries a común-regime residence — the ``CCAA`` enum is común-only and
        # foral regimes (País Vasco, Navarra) are refused at profile creation with
        # ``ForalRegimeError`` — so the periodic IVA result attributes 100% to the
        # State (Concierto Económico, Ley 12/2002 art. 29). Default the
        # absent-scope case to 100 rather than letting casilla 65 resolve silently
        # to 0, which would zero the headline result (casilla 71) on a real
        # liability — a silent under-declaration.
        fact_index[synthetic_key] = Decimal("100")


def _decimal_value(binding_id: BindingId, value: object) -> Decimal:
    # Boolean-typed profile facts arrive as Python ``bool`` now that
    # ``_profile_fact_index`` preserves the typed value. ``bool`` is a
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
    # A profile binding matters to the calculation source mesh when a formula
    # consumes it, when it feeds a ``bound`` NUMERIC input casilla (e.g. M303
    # casilla 65), or when it is a calculation-only selector. The latter has no
    # XSD/dictionary export address: M202's INCN applicability fact and M036's
    # censo event are registry-owned profile inputs even though neither is read
    # by a numeric formula. Identity/export-layout bindings (NIF, display name,
    # and similar) retain an export address and must not be pushed through a
    # calculation channel.
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

    def is_calculation_only_profile_binding(binding: DataBindingDefinition) -> bool:
        selector = binding.selector
        return not any(
            (
                getattr(selector, "xsd_path", None),
                getattr(selector, "xsd_attribute", None),
                getattr(selector, "dictionary_field", None),
            )
        )

    profile_bindings = [
        binding
        for binding in snapshot.revision.bindings
        if binding.source == BindingSourceKind.PROFILE
        and (
            binding.id in formula_consumed
            or binding.id in formula_date_consumed
            or binding.id in bound_casilla_binding_ids
            or is_calculation_only_profile_binding(binding)
        )
    ]
    if not profile_bindings:
        return CalculationSourceResolution(resolver_id=_PROFILE_RESOLVER_ID, owned_sources=_PROFILE_OWNED_SOURCES)

    record = profile_record
    if record is None:
        from ..user_profile import UserProfileLifecycleRepository

        try:
            record = UserProfileLifecycleRepository(bucket_id=bucket_id).load(bucket_id)
        except ProfileNotFoundError:
            return CalculationSourceResolution(resolver_id=_PROFILE_RESOLVER_ID, owned_sources=_PROFILE_OWNED_SOURCES)
    profile_record_fingerprint = _profile_record_fingerprint(record)

    resolved_schema = schema if schema is not None else load_user_profile_schema()
    fact_index = _profile_fact_index(record, resolved_schema)
    _inject_derived_marriage_facts(fact_index, snapshot.filing_year)
    _inject_derived_family_facts(fact_index, snapshot.filing_year)
    _inject_derived_anualidades_eligibility_facts(fact_index, snapshot.filing_year)
    _inject_derived_autonomic_deduccion_facts(fact_index, snapshot.filing_year)
    _inject_derived_minimo_descendientes_facts(fact_index, snapshot)
    _inject_derived_state_attribution_facts(fact_index)
    enum_bindings = enum_consumed_binding_ids(snapshot.revision)

    channels = _ResolvedBindingChannels()
    for binding in profile_bindings:
        binding_id = binding.id
        if binding_id in caller_binding_ids:
            continue
        value = _resolve_one(binding, fact_index)
        if value is None:
            continue
        _route_resolved_binding(
            binding_id,
            value,
            is_date_channel=binding_id in formula_date_consumed,
            is_enum_channel=binding_id in enum_bindings or binding.typed_enum is not None,
            channels=channels,
        )

    decimal_values = channels.decimal_values
    enum_values = channels.enum_values
    date_values = channels.date_values
    sourced = tuple(sorted(set(decimal_values) | set(enum_values) | set(date_values)))
    fingerprint = profile_record_fingerprint if sourced else None
    return CalculationSourceResolution(
        resolver_id=_PROFILE_RESOLVER_ID,
        owned_sources=_PROFILE_OWNED_SOURCES,
        binding_values=decimal_values,
        enum_binding_values=enum_values,
        date_binding_values=date_values,
        provenance=tuple(
            CalculationSourceProvenance(
                source_kind=BindingSourceKind.PROFILE.value,
                source_ref=f"profile:{bucket_id}:binding:{binding_id}",
                fingerprint=fingerprint,
            )
            for binding_id in sourced
        ),
    )


def _resolve_one(
    binding: DataBindingDefinition,
    fact_index: Mapping[str, UserProfileFactValue],
) -> UserProfileFactValue | None:
    """Return the typed profile fact value for one profile binding, or None if absent."""
    if binding.id.endswith(_ECONOMIC_ACTIVITY_PREDICATE_BINDING_SUFFIX):
        raw_categories = str(fact_index.get("taxpayer_type.irpf_income_categories", ""))
        categories = {token.strip() for token in raw_categories.split(",") if token.strip()}
        return Decimal("1") if _ECONOMIC_ACTIVITY_INCOME_CATEGORY in categories else Decimal("0")
    for selector in profile_binding_selectors(binding.selector):
        value = fact_index.get(selector)
        if value is None:
            continue
        # Blank strings are treated as absent; all other typed values (bool,
        # Decimal, date, int) are non-blank by definition.
        if isinstance(value, str) and not value.strip():
            continue
        return value.strip() if isinstance(value, str) else value
    return None


inject_derived_marriage_facts = _inject_derived_marriage_facts
inject_derived_autonomic_deduccion_facts = _inject_derived_autonomic_deduccion_facts
inject_derived_anualidades_eligibility_facts = _inject_derived_anualidades_eligibility_facts
inject_derived_minimo_descendientes_facts = _inject_derived_minimo_descendientes_facts
profile_fact_index = _profile_fact_index
resolve_profile_binding_value = _resolve_one
is_madrid_resident = _is_madrid_resident
is_indeterminate_unidad_familiar = _is_indeterminate_unidad_familiar
madrid_nacimiento_adopcion_candidate_weighted_count = _madrid_nacimiento_adopcion_candidate_weighted_count


__all__ = [
    "ProfileBindingResolutionError",
    "inject_derived_anualidades_eligibility_facts",
    "inject_derived_autonomic_deduccion_facts",
    "inject_derived_marriage_facts",
    "inject_derived_minimo_descendientes_facts",
    "profile_fact_index",
    "resolve_profile_binding_value",
    "resolve_profile_sourced_bindings",
]
