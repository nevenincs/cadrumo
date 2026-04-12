"""Pure-function applicability rules for autónomo modelos.

Each rule answers the question "must this profile file this modelo?".
The decisions are derived from the BOE / Manual práctico citations
recorded in the research note
``[[2026-04-12-deadline-engine-research]]`` - they are not invented.

Adding a new modelo means: (a) cite the BOE order in the research
note, (b) add an entry to :data:`_RULES`, (c) add the canonical window
to :mod:`aeat.deadlines._calendar`, (d) add a truth-table case to
``test_applies.py``.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from aeat.deadlines._errors import ScheduleComputationError
from aeat.deadlines._models import AutonomoProfile, IVARegime


@dataclass(frozen=True, slots=True)
class _Rule:
    """Internal applicability rule. Not exported."""

    predicate: Callable[[AutonomoProfile], bool]
    explanation: str


def _applies_130(profile: AutonomoProfile) -> bool:
    """Modelo 130 - IRPF pagos fraccionados (estimación directa).

    Always applies for the v1 autónomo set: the project assumes the
    autónomo is in estimación directa. Estimación objetiva (modelo
    131) is explicitly out of scope per the ADR.

    Cite: ``BOE-Orden-IRPF-pagos-fraccionados``; Manual práctico IRPF
    cap. pagos fraccionados.
    """
    del profile
    return True


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
    retención. The v1 engine collapses both into the
    ``has_employees`` flag - if you withhold IRPF for any reason, you
    file 111.

    Cite: ``BOE-Orden-Retenciones-IRPF-trabajo-profesionales``.
    """
    return profile.has_employees


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


def _applies_720(profile: AutonomoProfile) -> bool:
    """Modelo 720 - Bienes en el extranjero.

    Applies iff the profile holds bienes en el extranjero above the
    legal threshold.

    Cite: ``BOE-Orden-720-Bienes-Extranjero``.
    """
    return profile.bienes_extranjero_above_threshold


_RULES: dict[str, _Rule] = {
    "100": _Rule(_applies_100, "Toda persona física obligada a declarar IRPF."),
    "111": _Rule(_applies_111, "El autónomo paga retenciones a trabajadores o profesionales."),
    "115": _Rule(_applies_115, "El autónomo paga alquiler con retención."),
    "130": _Rule(
        _applies_130,
        "Autónomo en estimación directa: pagos fraccionados IRPF trimestrales.",
    ),
    "180": _Rule(_applies_180, "Resumen anual del modelo 115."),
    "190": _Rule(_applies_190, "Resumen anual del modelo 111."),
    "303": _Rule(
        _applies_303,
        "Autónomo en régimen general o simplificado de IVA.",
    ),
    "349": _Rule(_applies_349, "Autónomo con operaciones intracomunitarias."),
    "390": _Rule(_applies_390, "Resumen anual del modelo 303."),
    "720": _Rule(
        _applies_720,
        "Bienes en el extranjero por encima del umbral legal.",
    ),
}


def applies_to(profile: AutonomoProfile, modelo: str) -> bool:
    """Return ``True`` iff ``profile`` is obliged to file ``modelo``.

    Pure function. The decision is derived from the rule table built
    from the research note's BOE / Manual práctico citations.

    Args:
        profile: The autónomo profile to evaluate.
        modelo: The modelo string identifier.

    Returns:
        ``True`` if the profile is obliged to file ``modelo``.

    Raises:
        ScheduleComputationError: If ``modelo`` has no rule registered
            in the v1 autónomo set.
    """
    rule = _RULES.get(modelo)
    if rule is None:
        raise ScheduleComputationError(f"No applicability rule registered for modelo {modelo!r}")
    return rule.predicate(profile)


def explain(profile: AutonomoProfile, modelo: str) -> str:
    """Return the human-readable applies-because explanation.

    The string is suitable for the
    :attr:`aeat.deadlines.FilingObligation.applies_because` field and
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
