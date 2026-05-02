"""Pure-function applicability rules for the autónomo modelo set.

Each rule answers a single question: "must this profile file this
modelo?". The decisions are derived from the BOE order and Manual
práctico citations attached to each rule, never invented.

Adding a new modelo means:

* Cite the governing BOE order on the rule.
* Add an entry to :data:`_RULES`.
* Add the canonical window to
  :mod:`aeat.domain.deadlines._calendar`.
* Add a truth-table case to
  :mod:`aeat.domain.deadlines.test_applies`.

Public entry points are :func:`applies_to` (boolean predicate) and
:func:`explain` (Spanish-language reason).
"""

from __future__ import annotations

from collections.abc import Callable

from pydantic import BaseModel, ConfigDict

from ._errors import ScheduleComputationError
from ._models import AutonomoProfile, IVARegime


class _Rule(BaseModel):
    """Internal applicability rule. Not exported."""

    model_config = ConfigDict(
        strict=True,
        frozen=True,
        extra="forbid",
        arbitrary_types_allowed=True,
    )

    predicate: Callable[[AutonomoProfile], bool]
    explanation: str


def _has_withholding_outflows(profile: AutonomoProfile) -> bool:
    """Return whether the profile must remit work/professional withholdings."""
    return profile.has_employees or profile.pays_professionals_with_retencion


def _applies_130(profile: AutonomoProfile) -> bool:
    """Modelo 130 - IRPF pagos fraccionados (estimación directa).

    Applies for the direct-estimation autónomo set except when the
    professional-income exception is active: at least 70% of the prior
    year's professional income was already subject to withholding.

    Estimación objetiva (modelo 131) is explicitly out of scope per
    the ADR, so the engine only models the direct-estimation branch.
    """
    return not profile.professional_income_withholding_ge_70pct


def _applies_303(profile: AutonomoProfile) -> bool:
    """Modelo 303 - IVA autoliquidación.

    Applies iff the profile's IVA regime is one of ``GENERAL`` or
    ``SIMPLIFICADO``. Profiles in ``RECARGO_EQUIVALENCIA`` (the
    supplier remits the IVA on their behalf) and ``EXENTO`` (no IVA
    activity) do not file 303.

    Cite: ``BOE-Orden-IVA-autoliquidacion``; Manual práctico IVA
    cap. 303.
    """
    return profile.iva_regime in {IVARegime.GENERAL, IVARegime.SIMPLIFICADO}


def _applies_390(profile: AutonomoProfile) -> bool:
    """Modelo 390 - IVA resumen anual.

    Applies whenever Modelo 303 applies.

    Cite: ``BOE-Orden-IVA-resumen-anual``; Manual práctico IVA cap.
    resumen anual.
    """
    return _applies_303(profile)


def _applies_100(profile: AutonomoProfile) -> bool:
    """Modelo 100 - IRPF declaración anual.

    Applies to every autónomo with sufficient income; the v1 engine
    treats this as universally applicable to the profile set.

    Cite: ``BOE-Orden-IRPF-declaracion-anual``.
    """
    del profile
    return True


def _applies_111(profile: AutonomoProfile) -> bool:
    """Modelo 111 - Retenciones IRPF rendimientos del trabajo y profesionales.

    Applies iff the profile pays salaries or professional fees with
    retención.

    Cite: ``BOE-Orden-Retenciones-IRPF-trabajo-profesionales``.
    """
    return _has_withholding_outflows(profile)


def _applies_190(profile: AutonomoProfile) -> bool:
    """Modelo 190 - Resumen anual de retenciones IRPF.

    Applies iff Modelo 111 applies.

    Cite: ``BOE-Orden-Retenciones-IRPF-resumen-anual``.
    """
    return _applies_111(profile)


def _applies_115(profile: AutonomoProfile) -> bool:
    """Modelo 115 - Retenciones IRPF arrendamientos de inmuebles urbanos.

    Applies iff the profile pays alquiler de local with retención.

    Cite: ``BOE-Orden-Retenciones-Alquiler-Inmuebles-Urbanos``.
    """
    return profile.pays_rent_with_retencion


def _applies_180(profile: AutonomoProfile) -> bool:
    """Modelo 180 - Resumen anual de retenciones por arrendamiento.

    Applies iff Modelo 115 applies.

    Cite: ``BOE-Orden-Retenciones-Alquiler-Resumen-Anual``.
    """
    return _applies_115(profile)


def _applies_349(profile: AutonomoProfile) -> bool:
    """Modelo 349 - Operaciones intracomunitarias.

    Applies iff the profile conducts intra-EU operations.

    Cite: ``BOE-Orden-Recapitulativa-Intracomunitaria``.
    """
    return profile.does_intracomunitario


def _applies_347(profile: AutonomoProfile) -> bool:
    """Modelo 347 - Operaciones con terceras personas.

    Applies iff the annual third-party threshold was exceeded.

    Cite: ``BOE-Orden-347-Operaciones-Terceros``.
    """
    return profile.third_party_transactions_above_347_threshold


def _applies_720(profile: AutonomoProfile) -> bool:
    """Modelo 720 - Bienes en el extranjero.

    Applies iff the profile holds bienes en el extranjero above the
    legal threshold.

    Cite: ``BOE-Orden-720-Bienes-Extranjero``.
    """
    return profile.bienes_extranjero_above_threshold


_RULES: dict[str, _Rule] = {
    "100": _Rule(predicate=_applies_100, explanation="Toda persona física obligada a declarar IRPF."),
    "111": _Rule(
        predicate=_applies_111,
        explanation="El autónomo paga retenciones a trabajadores o profesionales.",
    ),
    "115": _Rule(predicate=_applies_115, explanation="El autónomo paga alquiler con retención."),
    "130": _Rule(
        predicate=_applies_130,
        explanation=(
            "Autónomo en estimación directa salvo la exención del 70% de ingresos profesionales ya retenidos."
        ),
    ),
    "180": _Rule(predicate=_applies_180, explanation="Resumen anual del modelo 115."),
    "190": _Rule(predicate=_applies_190, explanation="Resumen anual del modelo 111."),
    "303": _Rule(
        predicate=_applies_303,
        explanation="Autónomo en régimen general o simplificado de IVA.",
    ),
    "347": _Rule(
        predicate=_applies_347,
        explanation="Operaciones con terceros por encima del umbral legal.",
    ),
    "349": _Rule(predicate=_applies_349, explanation="Autónomo con operaciones intracomunitarias."),
    "390": _Rule(predicate=_applies_390, explanation="Resumen anual del modelo 303."),
    "720": _Rule(
        predicate=_applies_720,
        explanation="Bienes en el extranjero por encima del umbral legal.",
    ),
}


def applies_to(profile: AutonomoProfile, modelo: str) -> bool:
    """Return ``True`` iff ``profile`` is obliged to file ``modelo``.

    Pure function. The decision is derived from the rule table built
    from each rule's BOE order and Manual práctico citations.

    Args:
        profile: The autónomo profile to evaluate.
        modelo: The modelo string identifier.

    Returns:
        ``True`` if the profile is obliged to file ``modelo``.

    Raises:
        ScheduleComputationError: If ``modelo`` has no rule
            registered in the supported autónomo set.
    """
    rule = _RULES.get(modelo)
    if rule is None:
        raise ScheduleComputationError(f"No applicability rule registered for modelo {modelo!r}")
    return rule.predicate(profile)


def explain(profile: AutonomoProfile, modelo: str) -> str:
    """Return the human-readable applies-because explanation.

    The string is suitable for the
    :attr:`aeat.domain.deadlines.FilingObligation.applies_because` field and
    for the ``aeat deadlines explain`` CLI subcommand.

    Args:
        profile: The autónomo profile to evaluate.
        modelo: The modelo string identifier.

    Returns:
        Human-readable explanation referencing the rule.

    Raises:
        ScheduleComputationError: If ``modelo`` has no rule registered.
    """
    rule = _RULES.get(modelo)
    if rule is None:
        raise ScheduleComputationError(f"No applicability rule registered for modelo {modelo!r}")
    decision = "aplica" if rule.predicate(profile) else "no aplica"
    return f"{rule.explanation} ({decision})"
