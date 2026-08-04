"""Calculate-path advisory for an undeclared Art. 58/61 mínimo por descendientes.

Modelo 100 casillas ``irpf_minimo_descendientes_estatal`` (0513) and
``irpf_minimo_descendientes_autonomico`` (0514) are ``input_kind = computed``: the
Art. 58/61 LIRPF aggregate is derived from the active profile's
``renta_family.descendiente.{n}.*`` facts by
:func:`~application.modelo._profile_binding.inject_derived_minimo_descendientes_facts`.
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
    :func:`~application.modelo._profile_binding.inject_derived_minimo_descendientes_facts`:
        Computes the Art. 58/61 aggregate this collector's zero-check inspects.
    :func:`~domain.contribuyente.parse_descendiente_flag`:
        Parses the ``--descendiente`` flag the advisory's ``next_action`` names.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

from ...core import Modelo
from ...domain.calculations.registry import CasillaId, ModeloRevision
from ...domain.contribuyente import descendant_list_from_facts
from ...domain.user_profile import ProfileNotFoundError
from ..aggregation import CalculationSourceDiagnostic
from ._semantic_role_resolution import AmbiguousSemanticRoleCasillaError, casilla_id_for_unique_revision_semantic_role

__all__ = [
    "collect_descendientes_count_desync_diagnostics",
    "collect_minimo_descendientes_prorrata_inferred_diagnostics",
    "collect_minimo_descendientes_rentas_undeclared_diagnostics",
    "collect_minimo_descendientes_undeclared_diagnostics",
]

_MINIMO_ESTATAL_SEMANTIC_ROLE = "irpf_minimo_descendientes_estatal"
_DESCENDANT_FACT_PREFIX = "renta_family.descendiente."
_DESCENDANTS_COUNT_PATH = "renta_family.descendientes_count"

_UNDECLARED_SOURCE_KIND = "minimo_descendientes_undeclared"
_COUNT_DESYNC_SOURCE_KIND = "descendientes_count_desync"
_PRORRATA_INFERRED_SOURCE_KIND = "minimo_descendientes_prorrata_inferred"
_RENTAS_UNDECLARED_SOURCE_KIND = "minimo_descendientes_rentas_undeclared"


def _has_descendiente_facts(bucket_id: str) -> bool:
    """Return whether the active profile has explicitly declared its descendientes.

    Recognises two forms of an explicit declaration: at least one per-descendant
    ``renta_family.descendiente.{n}.*`` fact (the ``config profile descendiente add``
    entry surface), or an explicit ``renta_family.descendientes_count`` fact (even
    ``0``) -- a persona that positively declares zero children through the aggregate
    count, without ever using the per-descendant entry surface, has still declared
    its family situation and must not be flagged as a silent gap.

    Returns ``False`` when the bucket has no profile yet, mirroring the silent-absent
    handling :func:`~application.modelo._profile_binding.resolve_profile_sourced_bindings`
    already applies to profile-sourced bindings.
    """
    from ..user_profile import UserProfileLifecycleRepository

    try:
        record = UserProfileLifecycleRepository(bucket_id=bucket_id).load(bucket_id)
    except ProfileNotFoundError:
        return False
    return any(
        fact.value is not None
        and (fact.path.startswith(_DESCENDANT_FACT_PREFIX) or fact.path == _DESCENDANTS_COUNT_PATH)
        for fact in record.facts
    )


def _casilla_id_for_role(revision: ModeloRevision, semantic_role: str, *, modelo_id: str) -> CasillaId | None:
    try:
        return casilla_id_for_unique_revision_semantic_role(revision, semantic_role, modelo_id=modelo_id)
    except AmbiguousSemanticRoleCasillaError:
        return None


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
    estatal_id = _casilla_id_for_role(revision, _MINIMO_ESTATAL_SEMANTIC_ROLE, modelo_id=modelo)
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
    return (
        CalculationSourceDiagnostic(
            reason="source_issue",
            source_kind=_UNDECLARED_SOURCE_KIND,
            message=(
                f"casilla {estatal_id!r} (mínimo por descendientes, parte estatal) resolved to zero and "
                "the active profile declares no renta_family.descendiente facts -- if you have children "
                "or other eligible descendants, declare them with `aeat config profile descendiente add "
                "--descendiente NACIMIENTO=YYYY-MM-DD[,...]` before filing, or the Art. 58 LIRPF allowance "
                "is silently omitted"
            ),
            casilla_id=estatal_id,
        ),
    )


def _profile_fact_strings(bucket_id: str) -> dict[str, str] | None:
    """Return every non-null profile fact as a ``{path: str-value}`` map, or ``None``."""
    from ..user_profile import UserProfileLifecycleRepository

    try:
        record = UserProfileLifecycleRepository(bucket_id=bucket_id).load(bucket_id)
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
    (:func:`~application.modelo._profile_binding.second_entitled_filer_indicated`).

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
    estatal_id = _casilla_id_for_role(revision, _MINIMO_ESTATAL_SEMANTIC_ROLE, modelo_id=modelo)
    if estatal_id is None:
        return ()
    if casilla_values.get(estatal_id, Decimal(0)) == Decimal(0):
        # Nothing was granted, so nothing was halved.
        return ()
    facts = _profile_fact_strings(bucket_id)
    if facts is None:
        return ()

    from ._profile_binding import second_entitled_filer_indicated

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
    # ValidationError -- silencing the disclosure the ADR's default rests on,
    # for the filer with the most children at stake.
    named = _name_indices(inferred)
    return (
        CalculationSourceDiagnostic(
            reason="source_issue",
            source_kind=_PRORRATA_INFERRED_SOURCE_KIND,
            message=(
                f"casilla {estatal_id!r} (mínimo por descendientes) was HALVED under Art. 61 norma 1ª "
                f"LIRPF for {named}: the profile indicates a second entitled contribuyente (marital "
                "status, spouse record or declaration type) and no explicit answer was given. That is "
                "an inference, not a declared fact. State it with `descendiente add --descendiente "
                "PRORRATA=false` to claim the full mínimo, or PRORRATA=true to confirm the split"
            ),
            casilla_id=estatal_id,
        ),
    )


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
    estatal_id = _casilla_id_for_role(revision, _MINIMO_ESTATAL_SEMANTIC_ROLE, modelo_id=modelo)
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
    descendant_facts = {key: value for key, value in facts.items() if key.startswith(_DESCENDANT_FACT_PREFIX)}
    undeclared = [
        index
        for index, descendant in enumerate(descendant_list_from_facts(descendant_facts))
        if descendant.rentas_anuales_euros is None and descendant.meets_non_income_conditions(filing_year)
    ]
    if not undeclared:
        return ()
    return (
        CalculationSourceDiagnostic(
            reason="source_issue",
            source_kind=_RENTAS_UNDECLARED_SOURCE_KIND,
            message=(
                f"casilla {estatal_id!r} (mínimo por descendientes) claims a full tranche for "
                f"{_name_indices(undeclared)} with no annual-rentas figure on record. Art. 58.1 LIRPF "
                "withdraws it above the rentas ceiling, and Art. 61 norma 2ª when the descendant files "
                "their own return above that figure; an absent figure exceeds neither. Declare it with "
                "`descendiente add --descendiente RENTAS=N`. RENTAS=0 is a valid answer and silences this"
            ),
            casilla_id=estatal_id,
        ),
    )


def _declared_descendant_row_count(bucket_id: str) -> int | None:
    """Return how many descendant rows the profile carries, or ``None`` if unreadable."""
    from ..user_profile import UserProfileLifecycleRepository

    try:
        record = UserProfileLifecycleRepository(bucket_id=bucket_id).load(bucket_id)
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
    from ..user_profile import UserProfileLifecycleRepository

    try:
        record = UserProfileLifecycleRepository(bucket_id=bucket_id).load(bucket_id)
    except ProfileNotFoundError:
        return None
    for fact in record.facts:
        if fact.path == _DESCENDANTS_COUNT_PATH and fact.value is not None:
            try:
                return Decimal(str(fact.value))
            except (ArithmeticError, ValueError):
                return None
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
    :func:`~application.modelo._profile_binding.inject_derived_minimo_descendientes_facts`
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
    return (
        CalculationSourceDiagnostic(
            reason="source_issue",
            source_kind=_COUNT_DESYNC_SOURCE_KIND,
            message=(
                f"profile fact {_DESCENDANTS_COUNT_PATH!r} declares {stored} but the profile carries "
                f"{rows} renta_family.descendiente row(s). The count feeds its own Modelo 100 binding "
                "while the mínimo por descendientes casillas are computed from the rows, so the filing "
                "would carry two different answers. Re-enter the descendants with `aeat config profile "
                "descendiente add --descendiente NACIMIENTO=YYYY-MM-DD[,...]`, which rewrites the count "
                "and the rows together"
            ),
        ),
    )
