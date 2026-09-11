"""Registry-backed loaders for RIRPF/LIRPF retención rate parameters.

Two independent rate families live here, one per module. RD 439/2007 (RIRPF)
art. 95 fixes rates for rendimientos de actividades económicas — 15 % general
and 7 % inicio-de-actividades for actividades profesionales (apartado 1), plus
the sectoral 2 % agrícola/ganadera plus its 1 % engorde de porcino y avicultura
carve-out (apartado 4), 2 % forestal (apartado 5) and 1 % estimación objetiva
(apartado 6.1.º). LIRPF art. 101.2, developed by RIRPF art. 80.1.3.º, fixes the
administrador/consejero rate: 35 % general, dropping to 19 % when the paying
entity's importe neto de la cifra de negocios is below 100.000 euros. Both are
regulatory values, so they live in the registry catalogue —
``registry/aeat/legal/irpf-retencion-actividades.toml`` under
``[parameters."rirpf-art-95:*"]``, and
``registry/aeat/legal/irpf-retencion-administradores.toml`` under
``[parameters."lirpf-art-101:*"]`` — with their BOE citation and review
metadata, and Python consumers read them from here rather than from a bare
``Decimal(...)`` literal, where neither the figure nor its legal basis was
auditable.

The loaders resolve typed scalar facts through ``ValidatedRegistryAuthority``
at an explicit filing-period coordinate, then project only the values needed
by their frozen pydantic records. The authority owns validation, fingerprinting
and lifecycle identity; this module keeps neither a legal-parameter parser nor
a local value cache.

What the art. 95 rates are *for*: :attr:`RirpfArt95RetencionRates.general_rate`
is the upper bound on a **bounded inference**, not a rate the system ever
applies. A retención is declared by the operator or inferred as invoice gross
minus cash and then capped; no path may invert a rate to reconstruct a base
from cash, because selecting the applicable rate for a row is a per-row legal
fact the system cannot determine. The administrador rates, by contrast, ARE
applied directly: an administrador/consejero row's withheld amount is compared
against ``base * general_rate`` and ``base * reduced_rate`` to confirm it
matches one of the two statutory figures.

See Also:
    :mod:`domain.iva.components`
        Declares, per IVA category, whether a retención is expected at all.
    :mod:`domain.iva.recargo_equivalencia`
        The loader idiom this module follows.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, Final

from pydantic import BaseModel, Field

from ...core.models import STRICT_FROZEN_CONFIG
from .errors import TransactionValidationError

if TYPE_CHECKING:
    from ..calculations.registry.authority import ValidatedRegistryAuthority
    from ..calculations.registry.facts.resolution import ResolvedScalarFact


class RirpfArt95RetencionRates(BaseModel):
    """Frozen record of the RIRPF art. 95 retención rates.

    Attributes:
        general_rate: 15 % applied to the ingresos íntegros satisfechos when
            the rendimiento is the contraprestación of an actividad
            profesional (RIRPF art. 95.1, first paragraph).
        inicio_actividad_rate: 7 % applied in the período impositivo of inicio
            de actividades profesionales and the two following, provided no
            professional activity was carried on in the preceding year
            (RIRPF art. 95.1, second paragraph).
        agricola_ganadera_rate: 2 % applied to rendimientos of an actividad
            agrícola o ganadera in the general case (RIRPF art. 95.4.2.º).
        ganadera_engorde_rate: 1 % applied to actividades ganaderas de engorde
            de porcino y avicultura — an express carve-out from the 2 % above,
            not a separate regime (RIRPF art. 95.4.1.º).
        forestal_rate: 2 % applied to rendimientos of an actividad forestal
            (RIRPF art. 95.5). Equal in value to
            :attr:`agricola_ganadera_rate` but fixed by a different apartado,
            so it is carried as its own field rather than aliased.
        estimacion_objetiva_rate: 1 % applied when the rendimiento neto is
            determined under estimación objetiva for one of the IAE
            groups/epígrafes listed in art. 95.6.2.º (RIRPF art. 95.6.1.º).
    """

    model_config = STRICT_FROZEN_CONFIG

    general_rate: Decimal = Field(gt=Decimal("0"), lt=Decimal("1"))
    inicio_actividad_rate: Decimal = Field(gt=Decimal("0"), lt=Decimal("1"))
    agricola_ganadera_rate: Decimal = Field(gt=Decimal("0"), lt=Decimal("1"))
    ganadera_engorde_rate: Decimal = Field(gt=Decimal("0"), lt=Decimal("1"))
    forestal_rate: Decimal = Field(gt=Decimal("0"), lt=Decimal("1"))
    estimacion_objetiva_rate: Decimal = Field(gt=Decimal("0"), lt=Decimal("1"))


_GENERAL_PARAM_ID: Final[str] = "rirpf-art-95:retencion-actividades-profesionales-general"
_INICIO_PARAM_ID: Final[str] = "rirpf-art-95:retencion-actividades-profesionales-inicio"
_AGRICOLA_GANADERA_PARAM_ID: Final[str] = "rirpf-art-95:retencion-actividades-agricolas-ganaderas-general"
_GANADERA_ENGORDE_PARAM_ID: Final[str] = "rirpf-art-95:retencion-actividades-ganaderas-engorde-porcino-avicultura"
_FORESTAL_PARAM_ID: Final[str] = "rirpf-art-95:retencion-actividades-forestales"
_ESTIMACION_OBJETIVA_PARAM_ID: Final[str] = "rirpf-art-95:retencion-actividades-estimacion-objetiva"

#: Every art. 95 parameter this module resolves, in apartado order.
#:
#: Declared once so the rate loader and the grounding lookup below cannot drift:
#: a parameter added to one and not the other would produce a rate set whose
#: refs do not cover it.
_ART95_PARAMETER_IDS: Final[tuple[str, ...]] = (
    _GENERAL_PARAM_ID,
    _INICIO_PARAM_ID,
    _AGRICOLA_GANADERA_PARAM_ID,
    _GANADERA_ENGORDE_PARAM_ID,
    _FORESTAL_PARAM_ID,
    _ESTIMACION_OBJETIVA_PARAM_ID,
)


def retencion_effective_date(*, value_date: date | None, booked_date: date | None) -> date:
    """Return the settlement date that selects a transaction's withholding facts.

    A bank's value date records when the payment became effective and therefore
    takes precedence.  Some providers do not supply it; their booked date is
    the recorded settlement coordinate.  No wall-clock fallback is lawful here:
    a row with neither dated payment fact is unsupported and must not select a
    rate from a different legal period.
    """
    if value_date is not None:
        return value_date
    if booked_date is not None:
        return booked_date
    raise TransactionValidationError("retención fact resolution requires a transaction value or booked date")


def _resolved_scalar_parameter(
    parameter_id: str,
    *,
    effective_date: date,
    expected_unit: str,
    authority: ValidatedRegistryAuthority | None = None,
) -> ResolvedScalarFact:
    """Resolve one rate fact with the authority evidence required by its consumer."""
    from ..calculations.registry.errors import RegistryError
    from ..calculations.registry.facts.resolution import ResolvedScalarFact, ScalarFactQuery
    from ..calculations.registry.schema_base import DateAxis

    if authority is None:
        from ..calculations.registry.authority import bundled_authority

        authority = bundled_authority()
    try:
        resolved = authority.resolve_governed_fact(
            ScalarFactQuery(
                fact_id=parameter_id,
                date_axis=DateAxis.FILING_PERIOD,
                effective_date=effective_date,
            )
        )
    except RegistryError as exc:
        raise TransactionValidationError(
            f"failed to resolve retención fact {parameter_id!r}: {exc}",
        ) from exc
    if not isinstance(resolved, ResolvedScalarFact):
        raise TransactionValidationError(f"retención fact {parameter_id!r} did not resolve to a scalar")
    if resolved.payload.unit != expected_unit:
        raise TransactionValidationError(
            f"retención fact {parameter_id!r} carries unit {resolved.payload.unit!r}, expected {expected_unit!r}",
        )
    if not resolved.legal_refs:
        raise TransactionValidationError(f"retención fact {parameter_id!r} has no legal references")
    return resolved


def _legal_refs_of(
    parameter_id: str,
    *,
    effective_date: date,
    authority: ValidatedRegistryAuthority | None = None,
) -> tuple[str, ...]:
    """Return one resolved fact's legal references, refusing an ungrounded result."""
    return tuple(
        _resolved_scalar_parameter(
            parameter_id,
            effective_date=effective_date,
            expected_unit="fraction" if parameter_id != _ADMINISTRADOR_INCN_UMBRAL_PARAM_ID else "EUR",
            authority=authority,
        ).legal_refs
    )


def load_retencion_actividades_rates(
    *,
    effective_date: date,
    authority: ValidatedRegistryAuthority | None = None,
) -> RirpfArt95RetencionRates:
    """Return the RIRPF art. 95 retención rates from the registry catalogue.

    Returns:
        A :class:`RirpfArt95RetencionRates` record with every rate value.

    Raises:
        TransactionValidationError: If any expected parameter id is absent,
            carries no string value, or does not parse as a ``Decimal``, or if
            the registry parameter catalogue cannot be loaded.
    """
    coordinate = effective_date
    return RirpfArt95RetencionRates(
        general_rate=_decimal_fact(_GENERAL_PARAM_ID, coordinate, authority),
        inicio_actividad_rate=_decimal_fact(_INICIO_PARAM_ID, coordinate, authority),
        agricola_ganadera_rate=_decimal_fact(_AGRICOLA_GANADERA_PARAM_ID, coordinate, authority),
        ganadera_engorde_rate=_decimal_fact(_GANADERA_ENGORDE_PARAM_ID, coordinate, authority),
        forestal_rate=_decimal_fact(_FORESTAL_PARAM_ID, coordinate, authority),
        estimacion_objetiva_rate=_decimal_fact(_ESTIMACION_OBJETIVA_PARAM_ID, coordinate, authority),
    )


def rirpf_art95_retencion_legal_refs(
    *,
    effective_date: date,
    authority: ValidatedRegistryAuthority | None = None,
) -> tuple[str, ...]:
    """Return the registry legal references grounding the art. 95 rate set.

    Read off the parameters this module already resolves rather than restated
    here, which is the whole point: an advisory that names an article from a
    Python literal asserts law the registry cannot confirm it still says, while
    one carrying the parameter's own refs moves with the registry.

    Returns:
        The distinct reference ids, in first-seen order so the sequence is
        stable for an operator comparing two runs.
    """
    seen: list[str] = []
    for parameter_id in _ART95_PARAMETER_IDS:
        for reference in _legal_refs_of(parameter_id, effective_date=effective_date, authority=authority):
            if reference not in seen:
                seen.append(reference)
    return tuple(seen)


def statutory_activity_retencion_rates(*, effective_date: date) -> frozenset[Decimal]:
    """Return every distinct retención rate RIRPF art. 95 fixes.

    The DISTINCT values, not one per apartado: art. 95.4.2.º and art. 95.5 both
    fix 2 %, and art. 95.4.1.º and art. 95.6.1.º both fix 1 %, so the six
    declared parameters collapse to four figures. Callers that ask "is this
    amount a statutory rate product?" want the value set; callers that need to
    know WHICH apartado applies to a given row must read the named field
    instead, because that is a per-row legal determination this set discards.

    Returns:
        The distinct art. 95 rates, currently 15 %, 7 %, 2 % and 1 %.
    """
    rates = load_retencion_actividades_rates(effective_date=effective_date)
    return frozenset(
        {
            rates.general_rate,
            rates.inicio_actividad_rate,
            rates.agricola_ganadera_rate,
            rates.ganadera_engorde_rate,
            rates.forestal_rate,
            rates.estimacion_objetiva_rate,
        },
    )


def professional_activity_retencion_rates(*, effective_date: date) -> frozenset[Decimal]:
    """Return the art. 95.1 rates, those an actividad PROFESIONAL retains at.

    Split out from the sectoral figures because a match on one of these is a
    materially stronger claim than a match on 1 % or 2 %: 15 % and 7 % are large
    enough that a fee or rounding gap does not land on them by accident, while
    the sectoral rates are small enough that one routinely does.

    Returns:
        The art. 95.1 general and inicio-de-actividades rates.
    """
    rates = load_retencion_actividades_rates(effective_date=effective_date)
    return frozenset({rates.general_rate, rates.inicio_actividad_rate})


def maximum_supported_activity_retencion_rate(*, effective_date: date) -> Decimal:
    """Return the upper bound the withheld-amount inference is capped at.

    The bound is the RIRPF art. 95.1 general rate: an inferred retención above
    15 % of the taxable base is evidence that the recorded cash figure is the
    invoice base without IVA rather than a net-of-retención payment, so the
    inference is refused instead of persisting a fabricated withholding.

    Returns:
        The maximum retención rate the activity inference will accept.
    """
    return load_retencion_actividades_rates(effective_date=effective_date).general_rate


class AdministradorRetencionRates(BaseModel):
    """Frozen record of the LIRPF art. 101.2 administrador/consejero rates.

    Attributes:
        general_rate: 35 % fixed rate on rendimientos del trabajo perceived by
            administradores y miembros de consejos de administración, de las
            juntas que hagan sus veces, y demás miembros de otros órganos
            representativos (LIRPF art. 101.2 primer inciso; RIRPF art.
            80.1.3.º primer párrafo).
        reduced_rate: 19 % rate that replaces :attr:`general_rate` when the
            paying entity's importe neto de la cifra de negocios is below
            :attr:`reduced_incn_threshold_eur` (LIRPF art. 101.2 segundo
            inciso; RIRPF art. 80.1.3.º segundo párrafo).
        reduced_incn_threshold_eur: The INCN ceiling, in euros, strictly below
            which :attr:`reduced_rate` applies instead of :attr:`general_rate`.
    """

    model_config = STRICT_FROZEN_CONFIG

    general_rate: Decimal = Field(gt=Decimal("0"), lt=Decimal("1"))
    reduced_rate: Decimal = Field(gt=Decimal("0"), lt=Decimal("1"))
    reduced_incn_threshold_eur: Decimal = Field(gt=Decimal("0"))


_ADMINISTRADOR_GENERAL_PARAM_ID: Final[str] = "lirpf-art-101:retencion-administrador-general"
_ADMINISTRADOR_REDUCIDA_PARAM_ID: Final[str] = "lirpf-art-101:retencion-administrador-reducida"
_ADMINISTRADOR_INCN_UMBRAL_PARAM_ID: Final[str] = "lirpf-art-101:retencion-administrador-incn-umbral-eur"

#: Every administrador parameter this module resolves. Declared once so the
#: rate loader and the grounding lookup below cannot drift, for the same
#: reason :data:`_ART95_PARAMETER_IDS` is declared once.
_ADMINISTRADOR_PARAMETER_IDS: Final[tuple[str, ...]] = (
    _ADMINISTRADOR_GENERAL_PARAM_ID,
    _ADMINISTRADOR_REDUCIDA_PARAM_ID,
    _ADMINISTRADOR_INCN_UMBRAL_PARAM_ID,
)


def load_administrador_retencion_rates(
    *,
    effective_date: date,
    authority: ValidatedRegistryAuthority | None = None,
) -> AdministradorRetencionRates:
    """Return the LIRPF art. 101.2 administrador retención rates from the registry.

    Returns:
        An :class:`AdministradorRetencionRates` record with every rate value.

    Raises:
        TransactionValidationError: If any expected parameter id is absent,
            carries no string value, or does not parse as a ``Decimal``, or if
            the registry parameter catalogue cannot be loaded.
    """
    coordinate = effective_date
    return AdministradorRetencionRates(
        general_rate=_decimal_fact(_ADMINISTRADOR_GENERAL_PARAM_ID, coordinate, authority),
        reduced_rate=_decimal_fact(_ADMINISTRADOR_REDUCIDA_PARAM_ID, coordinate, authority),
        reduced_incn_threshold_eur=_decimal_fact(
            _ADMINISTRADOR_INCN_UMBRAL_PARAM_ID,
            coordinate,
            authority,
            expected_unit="EUR",
        ),
    )


def administrador_retencion_legal_refs(
    *,
    effective_date: date,
    authority: ValidatedRegistryAuthority | None = None,
) -> tuple[str, ...]:
    """Return the registry legal references grounding the administrador rate set.

    Read off the parameters this module already resolves rather than restated
    here, for the same reason :func:`rirpf_art95_retencion_legal_refs` states:
    an advisory that names an article from a Python literal asserts law the
    registry cannot confirm it still says, while one carrying the parameter's
    own refs moves with the registry.

    Returns:
        The distinct reference ids, in first-seen order so the sequence is
        stable for an operator comparing two runs.
    """
    seen: list[str] = []
    for parameter_id in _ADMINISTRADOR_PARAMETER_IDS:
        for reference in _legal_refs_of(parameter_id, effective_date=effective_date, authority=authority):
            if reference not in seen:
                seen.append(reference)
    return tuple(seen)


def _decimal_fact(
    parameter_id: str,
    effective_date: date,
    authority: ValidatedRegistryAuthority | None,
    *,
    expected_unit: str = "fraction",
) -> Decimal:
    """Return a Decimal only from a resolved scalar fact with the expected unit."""
    value = _resolved_scalar_parameter(
        parameter_id,
        effective_date=effective_date,
        expected_unit=expected_unit,
        authority=authority,
    ).payload.value
    if not isinstance(value, Decimal):
        raise TransactionValidationError(f"retención fact {parameter_id!r} has non-Decimal value {value!r}")
    return value


__all__ = [
    "AdministradorRetencionRates",
    "RirpfArt95RetencionRates",
    "administrador_retencion_legal_refs",
    "load_administrador_retencion_rates",
    "load_retencion_actividades_rates",
    "maximum_supported_activity_retencion_rate",
    "professional_activity_retencion_rates",
    "retencion_effective_date",
    "rirpf_art95_retencion_legal_refs",
    "statutory_activity_retencion_rates",
]
