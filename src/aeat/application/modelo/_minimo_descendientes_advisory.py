"""Calculate-path advisory collector for the Art. 58/61 mínimo por descendientes.

Modelo 100 casillas ``irpf_minimo_descendientes_estatal`` (0513) and
``irpf_minimo_descendientes_autonomico`` (0514) carry no ``binding`` in any
revision: the operator types the euro figure by hand. Two facts already known
to the active profile (the descendientes list and, per descendant, the
``custodia_compartida`` flag — Art. 61.1ª LIRPF) can silently diverge from what
the operator entered:

* When at least one eligible descendant carries ``custodia_compartida = True``,
  Art. 61.1ª prorrates the mínimo 50/50 between the two entitled progenitores.
  Nothing on the calculate path applies that split to a hand-entered figure, so
  an operator who enters the FULL (un-halved) amount silently over-declares
  the mínimo (advisory ``custodia_compartida_prorrata_advisory``).
* When the profile carries at least one Art. 58.1-eligible descendant but the
  operator left the mínimo casilla at zero, the calculate path never flags the
  omission on its own (advisory ``descendientes_minimo_not_entered``).

Both checks are advisory-only: this module does not compute, override, or
persist casilla 0513/0514. It is the Option B interim collector for the
minimo-por-descendientes engine ADR — the full computed engine (Option A)
remains deferred: the ADR flagged an "Art. 58.4 temporal prorrateo" mechanism
(a within-year birth/adoption cutoff) as blocking for the compute flip, but
the bundled consolidated LIRPF (``ley-35-2006.html``, Art. 58) carries only
two numbered subsections (58.1 ordinary amounts, 58.2 menor-3 supplement) —
no within-year birth/adoption prorrateo of any kind for descendientes exists
in the bundled text. Art. 61 (normas comunes) fixes personal/family
circumstances as of the devengo date (norm 3ª, a snapshot rule) and prorrates
only for a mid-year DEATH (norm 4ª, a fixed reduced amount), and its
half-period residency prorrata (norm 5ª) is scoped explicitly to ascendientes,
not descendientes. Absent a grounded temporal mechanism, Option A stays
deferred rather than encoding an unfounded rule.

See Also:
    :mod:`~aeat.application.modelo._calculation_diagnostics`:
        Post-calculation coordinator that calls this collector with the engine
        casilla values and the owning bucket id.
    :func:`~aeat.domain.contribuyente.family.RentaFamilyProfile.custodia_compartida_advisory`:
        Domain-owned translated advisory string this collector's message text
        is grounded in.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

from ...core import Modelo
from ...domain.calculations.registry import CasillaId, ModeloRevision
from ...domain.contribuyente import DescendantInfo, descendant_list_from_facts
from ...domain.user_profile import ProfileNotFoundError
from ..aggregation import CalculationSourceDiagnostic
from ._semantic_role_resolution import AmbiguousSemanticRoleCasillaError, casilla_id_for_unique_revision_semantic_role

__all__ = ["collect_minimo_descendientes_advisory_diagnostics"]

_MINIMO_ESTATAL_SEMANTIC_ROLE = "irpf_minimo_descendientes_estatal"
_DESCENDANT_FACT_PREFIX = "renta_family.descendiente."

_CUSTODIA_SOURCE_KIND = "minimo_descendientes_custodia_compartida"
_BLANK_SOURCE_KIND = "minimo_descendientes_not_entered"


def _load_descendant_facts(bucket_id: str) -> dict[str, str]:
    """Return the raw ``renta_family.descendiente.*`` fact strings for *bucket_id*.

    Returns an empty mapping when the bucket has no profile yet, mirroring the
    silent-absent handling :func:`~aeat.application.modelo._profile_binding.resolve_profile_sourced_bindings`
    already applies to profile-sourced bindings.
    """
    from ..user_profile import UserProfileLifecycleRepository

    try:
        record = UserProfileLifecycleRepository(bucket_id=bucket_id).load(bucket_id)
    except ProfileNotFoundError:
        return {}
    return {
        fact.path: str(fact.value)
        for fact in record.facts
        if fact.value is not None and fact.path.startswith(_DESCENDANT_FACT_PREFIX)
    }


def _casilla_id_for_role(revision: ModeloRevision, semantic_role: str, *, modelo_id: str) -> CasillaId | None:
    try:
        return casilla_id_for_unique_revision_semantic_role(revision, semantic_role, modelo_id=modelo_id)
    except AmbiguousSemanticRoleCasillaError:
        return None


def collect_minimo_descendientes_advisory_diagnostics(
    revision: ModeloRevision,
    casilla_values: Mapping[CasillaId, Decimal],
    *,
    modelo: str,
    filing_year: int,
    bucket_id: str,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Return mínimo-por-descendientes advisories for a Modelo 100 calculation.

    Both checks read the active profile's ``renta_family.descendiente.*``
    facts and the calculated 0513 (parte estatal) casilla value; the
    revision's mínimo-por-descendientes casillas are located by their stable
    ``semantic_role`` (canonical casilla ids renumber per filing year).

    Args:
        revision: The :class:`~aeat.domain.calculations.registry.ModeloRevision`
            being calculated. Only Modelo 100 revisions declare the
            mínimo-por-descendientes semantic roles; every other modelo
            returns an empty tuple immediately.
        casilla_values: The computed engine values keyed by
            :class:`~aeat.domain.calculations.registry.CasillaId`.
        modelo: The modelo identifier of the filing being calculated.
        filing_year: The ejercicio the descendientes eligibility is evaluated
            against (age-at-year-end, cohabitation).
        bucket_id: Bucket identifier used to load the active profile's
            descendientes facts.

    Returns:
        Tuple of advisory :class:`~aeat.application.aggregation.CalculationSourceDiagnostic`
        rows, or an empty tuple when neither condition fires.
    """
    if modelo != Modelo.M100.value:
        return ()
    estatal_id = _casilla_id_for_role(revision, _MINIMO_ESTATAL_SEMANTIC_ROLE, modelo_id=modelo)
    if estatal_id is None:
        return ()

    descendant_facts = _load_descendant_facts(bucket_id)
    if not descendant_facts:
        return ()
    descendientes = descendant_list_from_facts(descendant_facts)
    if not descendientes:
        return ()

    eligible = [d for d in descendientes if d.is_eligible_ordinary(filing_year)]
    if not eligible:
        return ()

    diagnostics: list[CalculationSourceDiagnostic] = []

    custodia_eligible = [d for d in eligible if d.custodia_compartida]
    if custodia_eligible:
        diagnostics.append(_custodia_compartida_diagnostic(custodia_eligible, estatal_id))

    estatal_value = casilla_values.get(estatal_id, Decimal(0))
    if estatal_value == Decimal(0):
        diagnostics.append(_blank_minimo_diagnostic(len(eligible), estatal_id))

    return tuple(diagnostics)


def _custodia_compartida_diagnostic(
    custodia_eligible: list[DescendantInfo],
    estatal_id: CasillaId,
) -> CalculationSourceDiagnostic:
    return CalculationSourceDiagnostic(
        reason="source_issue",
        source_kind=_CUSTODIA_SOURCE_KIND,
        message=(
            f"{len(custodia_eligible)} descendiente(s) on the active profile carry "
            "custodia_compartida=true; Art. 61.1a LIRPF prorrates the mínimo por "
            f"descendientes 50/50 between the two entitled progenitores. Casilla "
            f"{estatal_id!r} (mínimo por descendientes, parte estatal) is a manual "
            "entry the calculate path does not halve automatically -- confirm the "
            "entered amount already reflects the 50% prorrateo before filing."
        ),
        casilla_id=estatal_id,
    )


def _blank_minimo_diagnostic(eligible_count: int, estatal_id: CasillaId) -> CalculationSourceDiagnostic:
    return CalculationSourceDiagnostic(
        reason="source_issue",
        source_kind=_BLANK_SOURCE_KIND,
        message=(
            f"the active profile declares {eligible_count} descendiente(s) eligible for the "
            f"Art. 58.1 mínimo por descendientes, but casilla {estatal_id!r} (mínimo por "
            "descendientes, parte estatal) resolved to zero -- the calculate path does not "
            "compute this casilla from the descendientes profile; enter the mínimo amount "
            "(--casilla) before filing or the allowance is silently omitted."
        ),
        casilla_id=estatal_id,
    )
