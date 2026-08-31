"""Closed value sets for the cross-period prorrata register (LIVA arts. 102-106).

These enums are the register-scoped axes of the provisional-to-definitive IVA
prorrata lifecycle. They are declared in ``core`` per the core-authority
discipline (closed axes live in ``core/``, hydrated at boundaries, asserted as
members in tests) and consumed by the domain :mod:`~domain.prorrata_register`
aggregate and its encrypted persistence.

:class:`ProrrataRegisterRegime` is deliberately a DISTINCT symbol from the
compute-substrate :class:`~domain.iva.ProrrataRegime`. The substrate enum
(``general | especial``) types a prorrata *computation*; this register enum adds
the ``ninguna`` recorded state (the taxpayer is under no prorrata for the
ejercicio — the LIVA art. 94 full-deduction case) and types the regime *in force
for the taxpayer this ejercicio*. Merging the two would loosen the substrate's
``validate_prorrata_reference`` grammar to accept ``ninguna`` in a reference id,
a behaviour change the stable substrate must not take; the register therefore
owns its own three-valued regime axis.

See Also:
    :mod:`~domain.prorrata_register`
        Aggregate that stores these axes on each per-ejercicio register entry
        and resolves the art. 105 provisional precedence ladder.
    :class:`~domain.iva.ProrrataRegime`
        Compute-substrate regime enum intentionally kept narrower than the
        register's taxpayer-state axis.
    :func:`~domain.iva.validate_prorrata_reference`
        Parser whose canonical reference grammar must not accept the register's
        ``ninguna`` state.
    :func:`~application.prorrata_register.seed_carried_prior_definitiva_entry`
        Application seed path that writes the normal art. 105.Uno carried
        provenance into the register.
"""

from __future__ import annotations

from enum import StrEnum


class ProrrataRegisterRegime(StrEnum):
    """The prorrata regime a taxpayer is under for one ejercicio, as recorded in the register.

    The register carries this axis from birth so prorrata especial and sectores
    diferenciados land without a schema migration. Distinct from the
    compute-substrate :class:`~domain.iva.ProrrataRegime`, which types a single
    computation and has no not-applicable member.

    Attributes:
        GENERAL: Prorrata general (LIVA art. 104) — a single deduction
            percentage applies to the deducible cuotas.
        ESPECIAL: Prorrata especial (LIVA art. 106) — per-input classification.
            Recorded from birth; the especial per-input apportionment compute is
            deferred.
        NINGUNA: No prorrata applies — the taxpayer performs only operations that
            grant the right to deduct, so the LIVA art. 94 full-deduction default
            stands and no percentage apportions the cuotas.
    """

    GENERAL = "general"
    ESPECIAL = "especial"
    NINGUNA = "ninguna"


class ProrrataEspecialTransitionKind(StrEnum):
    """Modelo 303 facts that change the voluntary prorrata-especial state.

    A regime is durable state, not proof that an election happened in the
    current ejercicio: a current ``ESPECIAL`` regime may simply continue from a
    prior one, and it must not be mistaken for a current-period option.  These
    two values therefore type the separately evidenced transition that the
    filing surface projects, carried apart from
    :class:`ProrrataRegisterRegime` rather than derived from it.
    """

    OPCION = "opcion"
    REVOCACION = "revocacion"


class ProrrataActivityRowType(StrEnum):
    """Official Modelo 303 type token for one per-activity prorrata row.

    The DP30305 record carries a one-byte ``Tipo de prorrata`` field for each
    of its five activity rows.  It is deliberately distinct from
    :class:`ProrrataRegisterRegime`: the latter is the taxpayer's regime in
    force for an ejercicio, whereas this token is an official-row fact that
    must project as ``G`` or ``E`` at the row's reviewed fixed slot.
    """

    GENERAL = "G"
    ESPECIAL = "E"


class ProrrataProvisionalProvenance(StrEnum):
    """The regulated source of the provisional prorrata percentage in force (LIVA art. 105).

    Art. 105 admits exactly three provenances for the provisional percentage a
    taxpayer applies during the year's liquidations, and the register tags each
    recorded provisional percentage with the one it came from so the precedence
    ladder and the observation cross-check can reason about it.

    Attributes:
        CARRIED_PRIOR_DEFINITIVA: The normal case (art. 105.Uno) — the provisional
            percentage is the prior year's definitive percentage, seeded from the
            stamped prior settlement observation.
        AEAT_AUTORIZADA: The AEAT-authorised distinct provisional percentage
            (art. 105.Dos), recorded with its authorisation reference.
        INICIO_ACTIVIDAD: The inicio-de-actividades proposed percentage
            (art. 105.Tres via art. 111.Dos) for a taxpayer with no prior
            definitive to carry, recorded with its proposal reference.
        INTERRUMPIDA_TRES_ULTIMOS: The art. 105.Cinco interrupted-activity
            percentage — the global percentage over the aggregate volumes of the
            last three activo años naturales (skipping the interruption gap),
            used to seed an ejercicio whose immediately prior year had no
            operations. Computed from the register's own stored volumes, never a
            fabricated default and never silently the single pre-interruption
            year.
    """

    CARRIED_PRIOR_DEFINITIVA = "carried_prior_definitiva"
    AEAT_AUTORIZADA = "aeat_autorizada"
    INICIO_ACTIVIDAD = "inicio_actividad"
    INTERRUMPIDA_TRES_ULTIMOS = "interrumpida_tres_ultimos"


class SectorDiferenciadoLetra(StrEnum):
    """The LIVA art. 9.1.c letra that makes an operator-declared sector differentiated.

    Art. 9, número 1.º, letra c) enumerates the four grounds on which two economic
    activities belong to distinct "sectores diferenciados". The register's
    operator-declared sector definition tags each sector with the letra that makes
    it differentiated so the art. 9.1.c judgment is recorded, not inferred. Distinct
    from :class:`ProrrataRegisterRegime` (the deduction regime in force per sector);
    this axis is *why the sector is a separate sector*, not *how it deducts*.

    Attributes:
        A: Letra a' — distinct CNAE groups whose art. 104 general prorrata
            percentages differ by more than 50 percentage points
            (``PRORRATA_SECTORAL_SEPARATION_SPREAD_PP``). The only ground on which
            the art. 101.Dos AEAT-authorised common regime may later apply.
        B: Letra b' — activities under the regímenes especiales (simplificado,
            agricultura/ganadería/pesca, oro de inversión, recargo de
            equivalencia); their deduction is governed by their special regime.
        C: Letra c' — arrendamiento financiero operations (DA 3.ª Ley 10/2014).
        D: Letra d' — cesión de créditos o préstamos (except factoring).
    """

    A = "a"
    B = "b"
    C = "c"
    D = "d"


#: The regimes under which a percentage apportions the deducible cuotas.
#:
#: Membership is stated rather than derived as "not NINGUNA" so that adding a
#: regime is a decision rather than a default. ``test_prorrata_regime.py`` pins
#: the enum's membership, so a new member reds that test until someone rules on
#: which side it falls -- silently inheriting either answer would change how
#: much input IVA a taxpayer deducts.
_APPORTIONING_REGIMES: frozenset[ProrrataRegisterRegime] = frozenset(
    {ProrrataRegisterRegime.GENERAL, ProrrataRegisterRegime.ESPECIAL},
)


def regime_apportions_deduction(regime: ProrrataRegisterRegime) -> bool:
    """Return whether this regime apportions the deducible cuotas by a percentage.

    ``GENERAL`` (LIVA art. 104) and ``ESPECIAL`` (LIVA art. 106) both ration
    input IVA by a percentage; ``NINGUNA`` leaves the art. 94 full-deduction
    default standing, so no percentage applies and none should be sought.

    This is the single spelling of that question. It was previously written
    three ways across the IVA ledger, the Renta ledger and the prorrata
    regularizacion -- as ``regime not in (GENERAL, ESPECIAL)`` and as
    ``regime is not NINGUNA`` -- which are equivalent only because the enum has
    exactly three members, and would have silently diverged the moment it grew
    a fourth.
    """
    return regime in _APPORTIONING_REGIMES


__all__ = [
    "ProrrataActivityRowType",
    "ProrrataEspecialTransitionKind",
    "ProrrataProvisionalProvenance",
    "ProrrataRegisterRegime",
    "SectorDiferenciadoLetra",
    "regime_apportions_deduction",
]
