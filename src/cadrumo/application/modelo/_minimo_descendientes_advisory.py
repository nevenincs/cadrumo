"""Calculate-path advisory for an undeclared Art. 58/61 mínimo por descendientes.

Modelo 100 casillas ``irpf_minimo_descendientes_estatal`` (0513) and
``irpf_minimo_descendientes_autonomico`` (0514) are ``input_kind = computed``: the
Art. 58/61 LIRPF aggregate is derived from the active profile's
``renta_family.descendiente.{n}.*`` facts by
:func:`~application.modelo.profile_binding.inject_derived_minimo_descendientes_facts`.
A profile that carries no descendiente facts at all resolves 0513/0514 to the
legally-correct zero for a genuinely childless filer — but the SAME zero also results
when a filer with real descendants simply never declared them (no live production
surface wrote ``renta_family.descendiente.*`` before
``aeat config profile descendiente add`` was introduced). The two cases are
indistinguishable from the computed value alone, so this collector raises a
non-blocking advisory whenever 0513 resolves to zero AND the profile has NOT
explicitly declared its descendientes situation, pointing the operator at the
entry command (`no-silent-under-declaration`). "Explicitly declared" covers both
a per-descendant ``renta_family.descendiente.{n}.*`` fact (the ``config profile
descendiente add`` entry surface) and a bare ``renta_family.descendientes_count``
fact (even ``0``) written by another surface — a persona that positively declares
zero children is not a silent gap, whether or not any declared descendant turns
out Art. 58.1-eligible.

See Also:
    :mod:`~application.modelo._calculation_diagnostics`:
        Post-calculation coordinator that calls this collector with the engine
        casilla values and the owning bucket id.
    :func:`~application.modelo.profile_binding.inject_derived_minimo_descendientes_facts`:
        Computes the Art. 58/61 aggregate this collector's zero-check inspects.
    :func:`~domain.contribuyente.parse_descendiente_flag`:
        Parses the ``--descendiente`` flag the advisory's ``next_action`` names.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import NamedTuple

from ...core.casilla_id import CasillaId
from ...core.decimal.coercion import coerce_decimal
from ...core.modelo import Modelo
from ...domain.calculations.registry.ids import LegalRefId
from ...domain.calculations.registry.schema import ModeloRevision
from ...domain.contribuyente.descendant import DescendantInfo
from ...domain.contribuyente.descendant_facts import descendant_list_from_facts
from ...domain.contribuyente.family_profile import RentaFamilyProfile
from ...domain.user_profile.errors import ProfileNotFoundError
from ..aggregation import CalculationSourceDiagnostic
from ._semantic_role_resolution import casilla_id_for_unambiguous_revision_semantic_role

__all__ = [
    "collect_descendientes_count_desync_diagnostics",
    "collect_guarderia_madre_meses_undeclared_diagnostics",
    "collect_guarderia_spend_shape_diagnostics",
    "collect_minimo_descendientes_dependencia_diagnostics",
    "collect_minimo_descendientes_entry_date_missing_diagnostics",
    "collect_minimo_descendientes_prorrata_inferred_diagnostics",
    "collect_minimo_descendientes_rentas_undeclared_diagnostics",
    "collect_minimo_descendientes_undeclared_diagnostics",
]

_MINIMO_ESTATAL_SEMANTIC_ROLE = "irpf_minimo_descendientes_estatal"
_DESCENDANT_FACT_PREFIX = "renta_family.descendiente."
#: Filer-level fact the Art. 58 dependency assimilation turns on. Read by
#: `_family_profile_from_facts`, never by a descendant row.
_ANUALIDADES_FACT_KEY = "renta_family.anualidades_alimentos_euros"
_DESCENDANTS_COUNT_PATH = "renta_family.descendientes_count"

_UNDECLARED_SOURCE_KIND = "minimo_descendientes_undeclared"
_COUNT_DESYNC_SOURCE_KIND = "descendientes_count_desync"
_PRORRATA_INFERRED_SOURCE_KIND = "minimo_descendientes_prorrata_inferred"
_RENTAS_UNDECLARED_SOURCE_KIND = "minimo_descendientes_rentas_undeclared"
_ENTRY_DATE_MISSING_SOURCE_KIND = "minimo_descendientes_entry_date_missing"
_DEPENDENCIA_ASSIMILATED_SOURCE_KIND = "minimo_descendientes_dependencia_assimilated"
_DEPENDENCIA_SUPPRESSED_SOURCE_KIND = "minimo_descendientes_dependencia_suppressed"
_GUARDERIA_SHAPE_SOURCE_KIND = "guarderia_spend_needs_monthly_detail"
_SEGUNDO_CICLO_SOURCE_KIND = "guarderia_segundo_ciclo_month_undeclared"
_COTIZACIONES_FACT_KEY = "renta_family.cotizaciones_ss_madre_2024"
_TURNING_THREE_AGE = 3
_COTIZACIONES_CEILING_SOURCE_KIND = "guarderia_cotizaciones_ceiling_unbounded"
_GUARDERIA_MADRE_MESES_SOURCE_KIND = "guarderia_madre_meses_undeclared"

#: The Art. 81.2 guardería increase (Modelo 100 casilla 0613).
_INCREMENTO_GUARDERIA_SEMANTIC_ROLE = "irpf_incremento_maternidad_guarderia"


class _GuarderiaContext(NamedTuple):
    """The casilla, devengo year, and descendant records an Art. 81.3 advisory reads."""

    casilla_id: CasillaId
    filing_year: int
    descendants: tuple[DescendantInfo, ...]


def _has_descendiente_facts(bucket_id: str) -> bool:
    """Return whether the active profile has explicitly declared its descendientes.

    Recognises two forms of an explicit declaration: at least one per-descendant
    ``renta_family.descendiente.{n}.*`` fact (the ``config profile descendiente add``
    entry surface), or an explicit ``renta_family.descendientes_count`` fact (even
    ``0``) -- a persona that positively declares zero children through the aggregate
    count, without ever using the per-descendant entry surface, has still declared
    its family situation and must not be flagged as a silent gap.

    Returns ``False`` when the bucket has no profile yet, mirroring the silent-absent
    handling :func:`~application.modelo.profile_binding.resolve_profile_sourced_bindings`
    already applies to profile-sourced bindings.
    """
    from ..user_profile.profile_record_repository import ProfileRecordRepository

    try:
        record = ProfileRecordRepository.for_current_session(bucket_id).load(bucket_id)
    except ProfileNotFoundError:
        return False
    return any(
        fact.value is not None
        and (fact.path.startswith(_DESCENDANT_FACT_PREFIX) or fact.path == _DESCENDANTS_COUNT_PATH)
        for fact in record.facts
    )


def collect_minimo_descendientes_undeclared_diagnostics(
    revision: ModeloRevision,
    casilla_values: Mapping[CasillaId, Decimal],
    *,
    modelo: str,
    bucket_id: str,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Return an advisory when 0513 resolved to zero with no descendientes declared.

    Args:
        revision: The :class:`ModeloRevision` being calculated. Only Modelo 100
            revisions declare the mínimo por descendientes semantic role; every other
            modelo returns an empty tuple immediately.
        casilla_values: The computed engine values keyed by :class:`CasillaId`.
        modelo: The modelo identifier of the filing being calculated.
        bucket_id: Bucket identifier used to load the active profile's descendientes
            facts.

    Returns:
        A one-element tuple carrying the advisory, or an empty tuple when 0513 is
        nonzero or the profile already declares at least one descendiente fact.
    """
    if modelo != Modelo.M100.value:
        return ()
    estatal_id = casilla_id_for_unambiguous_revision_semantic_role(
        revision,
        _MINIMO_ESTATAL_SEMANTIC_ROLE,
        modelo_id=modelo,
    )
    if estatal_id is None:
        return ()
    estatal_value = casilla_values.get(estatal_id, Decimal(0))
    if estatal_value != Decimal(0):
        return ()
    if _has_descendiente_facts(bucket_id):
        # The profile explicitly declared descendientes (even if none turned out
        # Art. 58.1-eligible, e.g. every child is over 25 and non-discapacitado); a
        # declared zero is not a silent gap.
        return ()
    return (_undeclared_advisory(revision, estatal_id),)


def _family_profile_from_facts(facts: dict[str, str]) -> RentaFamilyProfile:
    """Build the family profile these advisories must judge descendants against.

    The descendant list alone cannot answer the Art. 58 household limb. Whether a
    non-cohabiting descendant reaches the mínimo through the economic-dependency
    assimilation depends on a FILER-level fact -- the judicial anualidades figure
    -- which only the profile carries. An advisory that asks
    :meth:`~domain.contribuyente.DescendantInfo.meets_non_income_conditions`
    without it takes that predicate's ``False`` default and silently drops every
    assimilated descendant from its subject population, while the figure path
    (which does pass the flag at six sites) keeps granting them the mínimo.

    Shared by all four collectors so no caller can reach for the bare descendant
    list again and reintroduce the divergence.
    """
    descendant_facts = {key: value for key, value in facts.items() if key.startswith(_DESCENDANT_FACT_PREFIX)}
    raw_anualidades = facts.get(_ANUALIDADES_FACT_KEY)
    return RentaFamilyProfile(
        descendientes=descendant_list_from_facts(descendant_facts),
        anualidades_alimentos_euros=coerce_decimal(raw_anualidades) if raw_anualidades is not None else None,
    )


def _profile_fact_strings(bucket_id: str) -> dict[str, str] | None:
    """Return every non-null profile fact as a ``{path: str-value}`` map, or ``None``."""
    from ..user_profile.profile_record_repository import ProfileRecordRepository

    try:
        record = ProfileRecordRepository.for_current_session(bucket_id).load(bucket_id)
    except ProfileNotFoundError:
        return None
    return {fact.path: str(fact.value) for fact in record.facts if fact.value is not None}


def collect_minimo_descendientes_prorrata_inferred_diagnostics(
    revision: ModeloRevision,
    casilla_values: Mapping[CasillaId, Decimal],
    *,
    modelo: str,
    bucket_id: str,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Advise when the Art. 61 norma 1ª prorrata was INFERRED rather than answered.

    Norma 1ª halves the mínimo whenever a second contribuyente is also entitled
    to the same descendant. Whether one is is not a fact about the descendant,
    so when the operator has not answered per-descendant the engine derives it
    from marital status, a spouse record and the declaration type
    (:func:`~application.modelo.profile_binding.second_entitled_filer_indicated`).

    A derivation that silently halved a filing's mínimo is exactly the kind of
    inference the operator must be able to see and correct before filing, which
    is why it surfaces here rather than staying internal. The direction of the
    default is deliberate: where the signals indicate a second entitled filer
    the engine prorates rather than claiming the full amount, erring toward
    under-claiming — which this advisory makes visible and correctable —
    instead of toward the silent over-claim `no-silent-under-declaration`
    forbids.

    Fires only when the derivation actually DECIDED something: the aggregate is
    non-zero, the profile indicates a second entitled filer, and at least one
    descendant carries neither an explicit ``prorrata_minimo`` answer nor the
    shared-custody trigger. A descendant whose factor came from an explicit
    answer or from shared custody is not flagged, because nothing was inferred.

    Args:
        revision: The :class:`ModeloRevision` being calculated.
        casilla_values: The computed engine values keyed by :class:`CasillaId`.
        modelo: The modelo identifier of the filing being calculated.
        bucket_id: Bucket whose profile carries the descendant facts.

    Returns:
        A one-element tuple carrying the advisory, or an empty tuple.
    """
    if modelo != Modelo.M100.value:
        return ()
    estatal_id = casilla_id_for_unambiguous_revision_semantic_role(
        revision,
        _MINIMO_ESTATAL_SEMANTIC_ROLE,
        modelo_id=modelo,
    )
    if estatal_id is None:
        return ()
    if casilla_values.get(estatal_id, Decimal(0)) == Decimal(0):
        # Nothing was granted, so nothing was halved.
        return ()
    facts = _profile_fact_strings(bucket_id)
    if facts is None:
        return ()

    from .profile_binding import second_entitled_filer_indicated

    if not second_entitled_filer_indicated(facts):
        return ()
    descendant_facts = {key: value for key, value in facts.items() if key.startswith(_DESCENDANT_FACT_PREFIX)}
    inferred = [
        index
        for index, descendant in enumerate(descendant_list_from_facts(descendant_facts))
        if descendant.prorrata_minimo is None and not descendant.custodia_compartida
    ]
    if not inferred:
        return ()
    # Bounded for the same reason the sibling advisory is: naming every
    # descendant is the only unbounded part of a length-capped message, and a
    # large household would otherwise turn this advisory into a hard
    # ValidationError -- silencing the disclosure the chosen default rests on,
    # for the filer with the most children at stake.
    return (_prorrata_inferred_advisory(revision, inferred, estatal_id),)


#: How many descendant paths a message names before summarising the rest.
#:
#: The diagnostic message is length-bounded by contract, and the naming is the
#: only unbounded part of it: a filer with many descendants would otherwise push
#: the message past the bound and turn an advisory into a hard validation error
#: at exactly the moment it had something to say. Naming a few and counting the
#: remainder keeps it actionable without letting household size decide whether
#: the advisory can be raised at all.
_MAX_NAMED_DESCENDANTS = 3


def _name_indices(indices: list[int]) -> str:
    """Render descendant paths for a message, bounded regardless of household size."""
    shown = ", ".join(f"renta_family.descendiente.{index}" for index in indices[:_MAX_NAMED_DESCENDANTS])
    remainder = len(indices) - _MAX_NAMED_DESCENDANTS
    return f"{shown} and {remainder} more" if remainder > 0 else shown


def _casilla_legal_refs(revision: ModeloRevision, casilla_id: CasillaId) -> tuple[LegalRefId, ...]:
    """Read one casilla's own legal grounding (and its binding's) off ``revision``.

    The casilla-derived path: correct for an advisory whose subject IS the
    casilla's own computation, never minted here. Mirrors
    :func:`~application.aggregation._undeclared_activity_advisory._casilla_grounding`;
    empty when the casilla is absent from the revision or carries no refs of
    its own, which a caller treats as "nothing to attach" rather than an error.
    """
    casilla = next((candidate for candidate in revision.casillas if candidate.id == casilla_id), None)
    if casilla is None:
        return ()
    binding = next((candidate for candidate in revision.bindings if candidate.id == casilla.binding), None)
    binding_legal = binding.legal_refs if binding is not None else ()
    return tuple(dict.fromkeys((*casilla.legal_refs, *binding_legal)))


def _undeclared_advisory(revision: ModeloRevision, casilla_id: CasillaId) -> CalculationSourceDiagnostic:
    return CalculationSourceDiagnostic(
        reason="source_issue",
        source_kind=_UNDECLARED_SOURCE_KIND,
        message=(
            f"casilla {casilla_id!r} (mínimo por descendientes, parte estatal) resolved to zero "
            "because the active profile declares no renta_family.descendiente facts. If you have "
            "children or other eligible descendants, the Art. 58 LIRPF allowance is being silently "
            "omitted"
        ),
        remedy=("Declare each descendant with `descendiente add --descendiente NACIMIENTO=YYYY-MM-DD`, before filing."),
        casilla_id=casilla_id,
        # Casilla-derived: this advisory's subject IS the casilla's own zero, and
        # its own grounding already carries the Art. 58 allowance the message
        # names -- nothing finer is asserted here that the casilla ref lacks.
        legal_refs=_casilla_legal_refs(revision, casilla_id),
    )


def _prorrata_inferred_advisory(
    revision: ModeloRevision,
    indices: list[int],
    casilla_id: CasillaId,
) -> CalculationSourceDiagnostic:
    return CalculationSourceDiagnostic(
        reason="source_issue",
        source_kind=_PRORRATA_INFERRED_SOURCE_KIND,
        message=(
            f"casilla {casilla_id!r} (mínimo por descendientes) was HALVED under Art. 61 norma 1ª "
            f"LIRPF for {_name_indices(indices)}: the profile indicates a second entitled "
            "contribuyente (marital status, spouse record or declaration type) and no explicit "
            "answer was given. That is an inference, not a declared fact"
        ),
        remedy=(
            "State it with `descendiente add --descendiente PRORRATA=false` to claim the full "
            "mínimo, or PRORRATA=true to confirm the split."
        ),
        casilla_id=casilla_id,
        # Casilla-derived, not advisory-asserted: the norma 1ª prorrateo clause is
        # not a sub-entry of its own -- the catalogue's whole-article
        # ley-35-2006:art-61 entry already grounds it at exactly this granularity
        # (its own required_text targets the prorrateo sentence), which is what
        # the casilla already references. Nothing finer exists to declare.
        legal_refs=_casilla_legal_refs(revision, casilla_id),
    )


def _rentas_undeclared_advisory(
    revision: ModeloRevision,
    indices: list[int],
    casilla_id: CasillaId,
) -> CalculationSourceDiagnostic:
    return CalculationSourceDiagnostic(
        reason="source_issue",
        source_kind=_RENTAS_UNDECLARED_SOURCE_KIND,
        message=(
            f"casilla {casilla_id!r} (mínimo por descendientes) claims a full tranche for "
            f"{_name_indices(indices)} with no annual-rentas figure on record. Art. 58.1 LIRPF "
            "withdraws it above the rentas ceiling, and Art. 61 norma 2ª when the descendant files "
            "their own return above that figure; an absent figure exceeds neither"
        ),
        remedy=(
            "Declare it with `descendiente add --descendiente RENTAS=N`. RENTAS=0 is a valid "
            "answer and silences this advisory."
        ),
        casilla_id=casilla_id,
        # Advisory-asserted, not casilla-derived: the casilla carries only the
        # whole-article art-58/art-61 refs, and this message states a claim about
        # TWO specific sub-clauses (the 58.1 rentas ceiling and the 61 norma 2ª
        # own-return exclusion) neither of which the casilla's own ref pins at
        # that granularity.
        asserted_legal_refs=("ley-35-2006:art-58-1", "ley-35-2006:art-61-norma-2"),
    )


def _entry_date_missing_advisory(indices: list[int], casilla_id: CasillaId) -> CalculationSourceDiagnostic:
    return CalculationSourceDiagnostic(
        reason="source_issue",
        source_kind=_ENTRY_DATE_MISSING_SOURCE_KIND,
        message=(
            f"casilla {casilla_id!r} withholds the Art. 58.2 LIRPF increase for "
            f"{_name_indices(indices)}: the relación is an adopción or entitling acogimiento, "
            "granted regardless of age in the entry period and the two following, but no entry "
            "date is on record so the window cannot be measured"
        ),
        remedy=(
            "Declare INSCRIPCION=YYYY-MM-DD (Registro Civil, or the resolución if none required) "
            "or ACOGIMIENTO=YYYY-MM-DD via `descendiente add`. The missing fact is the entry date, "
            "not the birth date."
        ),
        casilla_id=casilla_id,
    )


def _guarderia_shape_advisory(indices: list[int], casilla_id: CasillaId) -> CalculationSourceDiagnostic:
    return CalculationSourceDiagnostic(
        reason="source_issue",
        source_kind=_GUARDERIA_SHAPE_SOURCE_KIND,
        message=(
            f"casilla {casilla_id!r} counts no guardería spend for {_name_indices(indices)}: the "
            "child turns three in this period, so Art. 81.2 LIRPF admits only spend after the "
            "birthday and an annual total cannot be split across it"
        ),
        remedy=(
            "Restate it month by month with `descendiente add --descendiente "
            "GASTOS_GUARDERIA_MENSUAL=MM:N;MM-MM:N`. The eligible months are the ones your centre "
            "reported, so your certificate is the authority."
        ),
        casilla_id=casilla_id,
    )


def _cotizaciones_ceiling_is_unbounded(
    descendants: Sequence[DescendantInfo],
    facts: Mapping[str, str],
    filing_year: int,
) -> bool:
    """Whether an unbounded cotizaciones ceiling can change this filing's outcome.

    Reads the household cotizaciones fact directly rather than through a profile
    object, because this collector already holds the fact strings and rebuilding a
    profile to ask one question would be a second reader of the same data.

    Silent unless a figure is actually declared: with none the ceiling binds at zero
    and the increment is already nil for a reason the operator can see, so the
    advisory would add nothing but noise.
    """
    raw = facts.get(_COTIZACIONES_FACT_KEY, "").strip()
    if not raw:
        return False
    try:
        declared = int(raw)
    except ValueError:
        return False
    if declared <= 0:
        return False
    return any(
        descendant.convive_con_contribuyente
        and descendant.age_at_year_end(filing_year) == _TURNING_THREE_AGE
        and bool(descendant.gastos_guarderia_mensuales)
        for descendant in descendants
    )


def _segundo_ciclo_month_advisory(indices: list[int], casilla_id: CasillaId) -> CalculationSourceDiagnostic:
    """The turning-three window is withheld until the operator declares the month."""
    return CalculationSourceDiagnostic(
        reason="source_issue",
        source_kind=_SEGUNDO_CICLO_SOURCE_KIND,
        message=(
            f"casilla {casilla_id!r} counts no guardería spend for {_name_indices(indices)}: the "
            "child turns three in this period, so Art. 81.2 LIRPF admits spend only up to the "
            "month before the second cycle of educación infantil may begin, and that month is "
            "not declared"
        ),
        remedy=(
            "Declare it with `descendiente add --descendiente SEGUNDO_CICLO_INFANTIL_INICIO_MES=MM`. "
            "The month is the one the second cycle may start for this child, which your región "
            "and centre determine; your centre reports it on the modelo 233."
        ),
        casilla_id=casilla_id,
    )


def _cotizaciones_ceiling_advisory(casilla_id: CasillaId) -> CalculationSourceDiagnostic:
    """The cotizaciones limb is bounded by the same month, and is NOT applied here.

    Disclosed rather than computed: the declared figure is a household annual total
    while the ceiling is per child, and AEAT states no rule for apportioning one
    across several. Computing one would invent the arithmetic this advisory exists
    to keep out of the engine.
    """
    return CalculationSourceDiagnostic(
        reason="source_issue",
        source_kind=_COTIZACIONES_CEILING_SOURCE_KIND,
        message=(
            f"casilla {casilla_id!r} caps the guardería increment with the declared cotizaciones "
            "total as supplied. For a child turning three, Art. 81 counts only the cotizaciones "
            "devengadas up to the month before the second cycle may begin, and this application "
            "does not apply that bound: the figure is a household annual total while the ceiling "
            "is per child"
        ),
        remedy=(
            "Supply the already-bounded figure — the cotizaciones devengadas up to the month "
            "before the second cycle may begin — rather than the full annual total, if the two "
            "differ for this filing."
        ),
        casilla_id=casilla_id,
    )


def _guarderia_madre_meses_advisory(indices: list[int], casilla_id: CasillaId) -> CalculationSourceDiagnostic:
    return CalculationSourceDiagnostic(
        reason="source_issue",
        source_kind=_GUARDERIA_MADRE_MESES_SOURCE_KIND,
        message=(
            f"casilla {casilla_id!r} is zero despite declared guardería spend for "
            f"{_name_indices(indices)}: Art. 81.2 LIRPF raises the maternidad deducción, so it "
            "needs the months the mother met the Art. 81.1 requirement, and none are on record"
        ),
        remedy=(
            "Declare them with `descendiente add --descendiente MESES_TRABAJO=MM-MM`, or leave "
            "the zero if she met it in no month of this period."
        ),
        casilla_id=casilla_id,
    )


def _dependencia_assimilated_advisory(indices: list[int], casilla_id: CasillaId) -> CalculationSourceDiagnostic:
    return CalculationSourceDiagnostic(
        reason="source_issue",
        source_kind=_DEPENDENCIA_ASSIMILATED_SOURCE_KIND,
        message=(
            f"casilla {casilla_id!r} (mínimo por descendientes) grants the Art. 58 allowance for "
            f"{_name_indices(indices)} on DECLARED economic dependency rather than cohabitation. "
            "The authority allows this for a progenitor without custody who pays no judicial "
            "anualidades and still contributes to the descendant's upkeep"
        ),
        remedy="Confirm the declaration holds for the filing year before filing.",
        casilla_id=casilla_id,
    )


def _dependencia_suppressed_advisory(indices: list[int], casilla_id: CasillaId) -> CalculationSourceDiagnostic:
    return CalculationSourceDiagnostic(
        reason="source_issue",
        source_kind=_DEPENDENCIA_SUPPRESSED_SOURCE_KIND,
        message=(
            f"casilla {casilla_id!r} (mínimo por descendientes) WITHHOLDS the Art. 58 dependency "
            f"assimilation for {_name_indices(indices)} because the profile declares judicial "
            "anualidades por alimentos. The statutory carve-out is per-child, but this model "
            "cannot yet attribute a payment to one descendant, so a declared amount suppresses "
            "the assimilation for all of them"
        ),
        remedy=(
            "Where the anualidades are paid for a different descendant this under-grants the "
            "mínimo, so check the figure before filing."
        ),
        casilla_id=casilla_id,
    )


def _count_desync_advisory(stored: Decimal, rows: int) -> CalculationSourceDiagnostic:
    return CalculationSourceDiagnostic(
        reason="source_issue",
        source_kind=_COUNT_DESYNC_SOURCE_KIND,
        message=(
            f"profile fact {_DESCENDANTS_COUNT_PATH!r} declares {stored} but the profile carries "
            f"{rows} renta_family.descendiente row(s). The count feeds its own Modelo 100 binding "
            "while the mínimo por descendientes casillas are computed from the rows, so the filing "
            "would carry two different answers"
        ),
        remedy=("Re-enter the descendants on the active profile, which rewrites the count and the rows together."),
    )


def collect_minimo_descendientes_rentas_undeclared_diagnostics(
    revision: ModeloRevision,
    casilla_values: Mapping[CasillaId, Decimal],
    *,
    modelo: str,
    bucket_id: str,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Advise when a descendant is claiming the mínimo with no rentas figure on record.

    Art. 58.1 conditions the mínimo on the descendant's own annual rentas, and
    Art. 61 norma 2ª on the rentas in any return they file. Both read an ABSENT
    figure as non-excluding, deliberately: treating absence as exclusion would
    zero the allowance for every young child, who is the overwhelming case and
    has no rentas to declare. That default is correct and is not changed here.

    What it leaves is an asymmetry. A descendant who genuinely earns above the
    ceiling but whose figure was never entered still contributes a full tranche,
    and nothing says so. The sibling
    :func:`collect_minimo_descendientes_undeclared_diagnostics` cannot cover it:
    it fires only when the aggregate is ZERO and returns early the moment any
    descendiente fact exists, because its subject is a filer who declared no
    children at all. A declared descendant with an absent figure is the opposite
    state — a non-zero claim — so the two guards do not overlap.

    This is therefore the over-claiming direction of the same gap, which is the
    one that costs tax (`no-silent-under-declaration`).

    NARROW BY CONSTRUCTION, and that is the design rather than an optimisation.
    A blanket "some optional fact is blank" advisory fires on every ordinary
    filer and trains the operator to ignore it, at which point it protects
    nobody. Three conditions must all hold:

    * the aggregate is non-zero, so a mínimo is actually being claimed;
    * the descendant carries NO rentas figure — a declared zero is an answer,
      not an absence, and is silent here;
    * that descendant would contribute, i.e. it meets the non-income conditions
      (:meth:`~domain.contribuyente.DescendantInfo.meets_non_income_conditions`).
      A non-cohabiting or over-25 child changes nothing whether or not its
      figure is known, so flagging it would be noise.

    Args:
        revision: The :class:`ModeloRevision` being calculated. Its ``valid_to``
            supplies the devengo year the age test is anchored to.
        casilla_values: The computed engine values keyed by :class:`CasillaId`.
        modelo: The modelo identifier of the filing being calculated.
        bucket_id: Bucket whose profile carries the descendant facts.

    Returns:
        A one-element tuple carrying the advisory, or an empty tuple.
    """
    if modelo != Modelo.M100.value:
        return ()
    estatal_id = casilla_id_for_unambiguous_revision_semantic_role(
        revision,
        _MINIMO_ESTATAL_SEMANTIC_ROLE,
        modelo_id=modelo,
    )
    if estatal_id is None:
        return ()
    if casilla_values.get(estatal_id, Decimal(0)) == Decimal(0):
        # Nothing is being claimed, so an absent figure changes no outcome.
        return ()
    if revision.valid_to is None:
        # An open-ended revision fixes no devengo date, so the age limb of the
        # contribution test has no anchor. Silent rather than guessing a year.
        return ()
    facts = _profile_fact_strings(bucket_id)
    if facts is None:
        return ()

    filing_year = revision.valid_to.year
    profile = _family_profile_from_facts(facts)
    available = profile.dependencia_assimilation_available
    undeclared = [
        index
        for index, descendant in enumerate(profile.descendientes)
        if descendant.rentas_anuales_euros is None
        and descendant.meets_non_income_conditions(
            filing_year,
            dependencia_assimilation_available=available,
        )
    ]
    if not undeclared:
        return ()
    return (_rentas_undeclared_advisory(revision, undeclared, estatal_id),)


def collect_minimo_descendientes_entry_date_missing_diagnostics(
    revision: ModeloRevision,
    casilla_values: Mapping[CasillaId, Decimal],
    *,
    modelo: str,
    bucket_id: str,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Advise when an adopted or fostered descendant has no Art. 58.2 entry date.

    Art. 58.2 grants the under-three increase "con independencia de la edad del
    menor" for an adopción or an acogimiento preadoptivo o permanente, in the
    period the entry event falls and the two following. The window therefore
    needs an anchor: the Registro Civil inscription (or the resolución where
    inscription is not required) for an adoption, the first entitling resolución
    for an acogimiento.

    Recording the relación WITHOUT its date is a state the model deliberately
    accepts rather than refuses — an operator may know a child is adopted before
    they hold the inscription date, and refusing the record would be worse than
    deferring the grant. The consequence is that the age-independent limb cannot
    fire, so the household the sentence was written for receives nothing, which
    is an under-grant and therefore the safe direction — but a silent one unless
    something says so (`no-silent-under-declaration`).

    Narrow by construction, on the same reasoning as its siblings: a descendant
    already under three takes the increase through the ordinary limb regardless,
    a non-cohabiting one takes no mínimo at all, and a relación the statute
    excludes from the limb (tutela, temporal acogimiento) has no anchor to be
    missing. Only the older adopted or fostered child — exactly the case the
    age-independent clause exists for — is reported.

    Args:
        revision: The :class:`ModeloRevision` being calculated. Its ``valid_to``
            supplies the devengo year the age limb is anchored to.
        casilla_values: The computed engine values keyed by :class:`CasillaId`.
        modelo: The modelo identifier of the filing being calculated.
        bucket_id: Bucket whose profile carries the descendant facts.

    Returns:
        A one-element tuple carrying the advisory, or an empty tuple.
    """
    if modelo != Modelo.M100.value:
        return ()
    estatal_id = casilla_id_for_unambiguous_revision_semantic_role(
        revision,
        _MINIMO_ESTATAL_SEMANTIC_ROLE,
        modelo_id=modelo,
    )
    if estatal_id is None:
        return ()
    if revision.valid_to is None:
        # An open-ended revision fixes no devengo date, so the age limb of the
        # report test has no anchor. Silent rather than guessing a year.
        return ()
    facts = _profile_fact_strings(bucket_id)
    if facts is None:
        return ()
    filing_year = revision.valid_to.year
    profile = _family_profile_from_facts(facts)
    available = profile.dependencia_assimilation_available
    missing = [
        index
        for index, descendant in enumerate(profile.descendientes)
        if descendant.art_58_2_window_anchor_missing(
            filing_year,
            dependencia_assimilation_available=available,
        )
    ]
    if not missing:
        return ()
    return (_entry_date_missing_advisory(missing, estatal_id),)


def collect_guarderia_spend_shape_diagnostics(
    revision: ModeloRevision,
    casilla_values: Mapping[CasillaId, Decimal],
    *,
    modelo: str,
    bucket_id: str,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Advise when a declared guardería figure contributes nothing because of its SHAPE.

    Art. 81.2 extends the increase into the period the child turns three, but
    only for spend "incurridos con posterioridad al cumplimiento de dicha edad".
    An ANNUAL total spans that birthday and cannot be apportioned across it, so
    a child in that period whose spend is on record only as an annual figure
    contributes zero.

    That is the one state where a taxpayer declared real spend, sees it stored,
    and receives nothing — and nothing about the computed value says why. It is
    not a withheld window: the operator can replace the annual figure with the
    month-by-month detail their childcare centre already certified, and the
    months on that certificate are exactly the eligible ones, because the centre
    determines them and reports them to the authority on its own informative
    return. So the advisory points at the document that settles the question
    rather than at a rule this application cannot state (`no-silent-under-declaration`).

    Args:
        revision: The :class:`ModeloRevision` being calculated. Its ``valid_to``
            supplies the devengo year the turning-three test is anchored to.
        casilla_values: The computed engine values keyed by :class:`CasillaId`.
        modelo: The modelo identifier of the filing being calculated.
        bucket_id: Bucket whose profile carries the descendant facts.

    Returns:
        A one-element tuple carrying the advisory, or an empty tuple.
    """
    if modelo != Modelo.M100.value:
        return ()
    casilla_id = casilla_id_for_unambiguous_revision_semantic_role(
        revision,
        _INCREMENTO_GUARDERIA_SEMANTIC_ROLE,
        modelo_id=modelo,
    )
    if casilla_id is None:
        return ()
    if revision.valid_to is None:
        # An open-ended revision fixes no devengo date, so the turning-three
        # test has no anchor. Silent rather than guessing a year.
        return ()
    facts = _profile_fact_strings(bucket_id)
    if facts is None:
        return ()
    filing_year = revision.valid_to.year
    descendant_facts = {key: value for key, value in facts.items() if key.startswith(_DESCENDANT_FACT_PREFIX)}
    affected = [
        index
        for index, descendant in enumerate(descendant_list_from_facts(descendant_facts))
        if descendant.guarderia_needs_monthly_detail(filing_year)
    ]
    descendants = descendant_list_from_facts(descendant_facts)
    needs_month = [
        index
        for index, descendant in enumerate(descendants)
        if descendant.guarderia_needs_segundo_ciclo_month(filing_year)
    ]
    diagnostics: list[CalculationSourceDiagnostic] = []
    if affected:
        diagnostics.append(_guarderia_shape_advisory(affected, casilla_id))
    if needs_month:
        diagnostics.append(_segundo_ciclo_month_advisory(needs_month, casilla_id))
    if _cotizaciones_ceiling_is_unbounded(descendants, facts, filing_year):
        diagnostics.append(_cotizaciones_ceiling_advisory(casilla_id))
    return tuple(diagnostics)


def _guarderia_descendants(revision: ModeloRevision, *, modelo: str, bucket_id: str) -> _GuarderiaContext | None:
    """Resolve the shared preconditions the two Art. 81.3 collectors below need.

    Both ask about the same population against the same casilla and the same
    devengo year, and both are silent for the same three reasons: a different
    modelo, a revision that fixes no devengo date, or an unreadable profile.
    Assembled once so the two cannot drift into disagreeing about when they
    apply.
    """
    if modelo != Modelo.M100.value:
        return None
    casilla_id = casilla_id_for_unambiguous_revision_semantic_role(
        revision,
        _INCREMENTO_GUARDERIA_SEMANTIC_ROLE,
        modelo_id=modelo,
    )
    if casilla_id is None:
        return None
    if revision.valid_to is None:
        return None
    facts = _profile_fact_strings(bucket_id)
    if facts is None:
        return None
    descendant_facts = {key: value for key, value in facts.items() if key.startswith(_DESCENDANT_FACT_PREFIX)}
    return _GuarderiaContext(
        casilla_id=casilla_id,
        filing_year=revision.valid_to.year,
        descendants=tuple(descendant_list_from_facts(descendant_facts)),
    )


def collect_guarderia_madre_meses_undeclared_diagnostics(
    revision: ModeloRevision,
    casilla_values: Mapping[CasillaId, Decimal],
    *,
    modelo: str,
    bucket_id: str,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Advise when declared guardería spend yields nothing for want of the mother's months.

    Art. 81.2 increases the maternidad deducción, so it is available only where
    the Art. 81.1 requirement is met, and Art. 81.3 prorates it by the months
    both hold at once. A filer who never recorded the mother's qualifying months
    carries a zero on that side, and zero months of overlap is zero increase.

    The arithmetic is right and the outcome is still a trap, because the record
    cannot tell a mother who declared no qualifying months from one who was
    never asked: the field simply defaults to zero. So a taxpayer can declare
    real nursery spend, watch it stored and listed back, and receive nothing,
    with no computed value able to say which of the two happened
    (`no-silent-under-declaration`).

    Fires only where spend is actually on record for a child the article admits.
    A filer with no guardería spend at all is not in this state, and telling
    them about the mother's months would be noise.

    Args:
        revision: The :class:`ModeloRevision` being calculated; its ``valid_to``
            supplies the devengo year.
        casilla_values: Computed engine values keyed by :class:`CasillaId`. The
            advisory is scoped to the zero, since a positive increase means the
            months were declared.
        modelo: The modelo identifier of the filing being calculated.
        bucket_id: Bucket whose profile carries the descendant facts.

    Returns:
        A one-element tuple carrying the advisory, or an empty tuple.
    """
    context = _guarderia_descendants(revision, modelo=modelo, bucket_id=bucket_id)
    if context is None:
        return ()
    if casilla_values.get(context.casilla_id, Decimal("0")) != 0:
        return ()
    affected = [
        index
        for index, descendant in enumerate(context.descendants)
        if not descendant.meses_madre_trabajo
        and descendant.guarderia_qualifying_meses(context.filing_year) > 0
        and descendant.guarderia_contributing_spend(context.filing_year) > 0
    ]
    if not affected:
        return ()
    return (_guarderia_madre_meses_advisory(affected, context.casilla_id),)


def collect_minimo_descendientes_dependencia_diagnostics(
    revision: ModeloRevision,
    casilla_values: Mapping[CasillaId, Decimal],
    *,
    modelo: str,
    bucket_id: str,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Disclose the Art. 58 dependency assimilation, in both directions.

    Two advisories from one collector because they are the two sides of one
    staged rule and an operator needs to see whichever applies.

    GRANTED: a non-cohabiting filer is taking the mínimo on a declared
    economic-dependency fact. The authority states that entitlement in terms,
    so this is correct rather than doubtful - but it rests on a judgement the
    operator made, not on an observation, and it is the judgement AEAT would
    ask about. Surfacing it is what keeps a declared fact from behaving like a
    silent one.

    SUPPRESSED: the filer declared judicial anualidades, so every declared
    dependency is withheld. That is this model's staged narrowing rather than
    the law: the statutory carve-out is per-child, and until per-child
    attribution exists a filer paying for one child loses the assimilation for
    another they support outside any court order. It under-grants, which is the
    safe direction, and this is what stops it being a silent one.

    Args:
        revision: The :class:`ModeloRevision` being calculated; its ``valid_to``
            supplies the devengo year.
        casilla_values: The computed engine values keyed by :class:`CasillaId`.
        modelo: The modelo identifier of the filing being calculated.
        bucket_id: Bucket whose profile carries the descendant facts.

    Returns:
        Up to two diagnostics, or an empty tuple when neither state applies.
    """
    if modelo != Modelo.M100.value:
        return ()
    estatal_id = casilla_id_for_unambiguous_revision_semantic_role(
        revision,
        _MINIMO_ESTATAL_SEMANTIC_ROLE,
        modelo_id=modelo,
    )
    if estatal_id is None or revision.valid_to is None:
        return ()
    facts = _profile_fact_strings(bucket_id)
    if facts is None:
        return ()

    profile = _family_profile_from_facts(facts)
    diagnostics: list[CalculationSourceDiagnostic] = []
    granted = profile.dependencia_assimilated_indices(revision.valid_to.year)
    if granted:
        diagnostics.append(_dependencia_assimilated_advisory(list(granted), estatal_id))
    suppressed = profile.dependencia_suppressed_indices()
    if suppressed:
        diagnostics.append(_dependencia_suppressed_advisory(list(suppressed), estatal_id))
    return tuple(diagnostics)


def _declared_descendant_row_count(bucket_id: str) -> int | None:
    """Return how many descendant rows the profile carries, or ``None`` if unreadable."""
    from ..user_profile.profile_record_repository import ProfileRecordRepository

    try:
        record = ProfileRecordRepository.for_current_session(bucket_id).load(bucket_id)
    except ProfileNotFoundError:
        return None
    instances = {
        fact.path.split(".")[2]
        for fact in record.facts
        if fact.value is not None and fact.path.startswith(_DESCENDANT_FACT_PREFIX) and fact.path.count(".") >= 3
    }
    return len(instances)


def _stored_descendientes_count(bucket_id: str) -> Decimal | None:
    """Return the stored aggregate count fact, or ``None`` when absent."""
    from ..user_profile.profile_record_repository import ProfileRecordRepository

    try:
        record = ProfileRecordRepository.for_current_session(bucket_id).load(bucket_id)
    except ProfileNotFoundError:
        return None
    for fact in record.facts:
        if fact.path == _DESCENDANTS_COUNT_PATH and fact.value is not None:
            # Tolerant coercion, not the strict grammar: this is an
            # already-persisted profile fact whose text grammar the entry
            # boundary owns, and the stored value is legitimately a Decimal as
            # well as a string. Returning None on an unreadable value is the
            # existing contract and coerce_decimal's own default, so the
            # desync advisory stays silent rather than firing on a value it
            # could not read -- an unreadable count is not evidence of drift.
            return coerce_decimal(fact.value)
    return None


def collect_descendientes_count_desync_diagnostics(
    *,
    modelo: str,
    bucket_id: str,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Advise when the stored descendientes count contradicts the rows it aggregates.

    ``renta_family.descendientes_count`` is a DERIVED aggregate over the
    ``renta_family.descendiente.{n}.*`` rows: the entry surface, the wizard
    descendant door and the checkpoint projection each rewrite it in the
    same atomic batch as the rows, precisely so the two cannot drift.

    Nothing enforced that afterwards. The count is a declared schema field,
    so the profile manager renders it as an ordinary editable row -- while
    the rows it counts are an indexed fact namespace the manager does not
    render at all. An operator therefore sees a count with nothing beside
    it to contradict, and editing it desyncs silently: measured, writing
    ``7`` through the manager's single-field door against a profile
    carrying two descendant rows leaves the count at ``7`` and the rows at
    two.

    That divergence reaches the filing, and splits it. The registry
    binding ``renta-2024-profile-descendientes-count`` reads the STORED
    count out of the profile fact index, while casillas 0513/0514 are
    injected from the ROWS by
    :func:`~application.modelo.profile_binding.inject_derived_minimo_descendientes_facts`
    -- so one Modelo 100 casilla follows the operator's number and another
    follows the descendants actually on record, with nothing saying they
    disagree (`no-silent-under-declaration`).

    Advisory rather than blocking, deliberately. A bare count with NO rows
    is a supported declaration -- the sibling undeclared-advisory treats it
    as an explicit "this is my family situation", including a positive
    declaration of zero -- so a count standing alone is not a fault and is
    not flagged. Only a count that contradicts rows that exist is, because
    there the profile holds two different answers to one question.

    Args:
        modelo: The modelo identifier being calculated.
        bucket_id: Bucket whose profile carries the descendant facts.

    Returns:
        A one-element tuple carrying the advisory, or an empty tuple when
        the two agree, when no rows exist, or when no count is stored.
    """
    if modelo != Modelo.M100.value:
        return ()
    rows = _declared_descendant_row_count(bucket_id)
    if not rows:
        # No rows to contradict: a standalone count is a supported declaration.
        return ()
    stored = _stored_descendientes_count(bucket_id)
    if stored is None or stored == Decimal(rows):
        return ()
    return (_count_desync_advisory(stored, rows),)
