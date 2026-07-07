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


__all__ = [
    "ProrrataProvisionalProvenance",
    "ProrrataRegisterRegime",
]
