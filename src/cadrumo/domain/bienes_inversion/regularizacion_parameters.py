"""Registry-resolved LIVA art-107/109 figures for the capital-goods regularización.

A registry parameter is hosted on a REVISION, and only the filing context names
one. This domain package holds no filing context and performs no revision
selection -- no domain package in the tree does -- so it cannot read these
figures for itself. The accepted placement decision resolves them at the
application boundary, which already holds the compiled revision it selected, and
passes the result in as :class:`BienesInversionRegularizacionParameters`.

The bundle carries no defaults and has one legitimate constructor,
:func:`resolve_bienes_inversion_regularizacion_parameters`, which reads the
validated authority. A calculator therefore cannot be called without resolved
values, and a missing parameter leaves the bundle unconstructable rather than
silently zero or silently equal to yesterday's law.

:class:`BienesInversionParameterProvenance` travels with the values into every
result. Without it, handing the same bundle to a producer and to its oracle
would make a WRONG bundle self-consistent and cost the oracle its independence;
with it, a replay can refuse a result whose provenance disagrees with the bundle
it was handed.

See Also:
    :mod:`domain.bienes_inversion.register`
        The art-109 and art-110 computations that consume the bundle.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field, model_validator

from ...core.errors.hierarchy import CadrumoError as _CadrumoError
from ...core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN_CONFIG
from ..calculations.registry.formula_runtime_ops import resolve_dated_value
from ..calculations.registry.schema import ModeloRevision
from ..calculations.registry.schema_base import ThresholdComparison
from ..calculations.registry.schema_formula import DatedValue


class BienesInversionParameterResolutionError(_CadrumoError):
    """Raised when a revision cannot supply the whole art-107/109 figure set.

    Refusing here rather than substituting a default is the point: an incomplete
    set means the revision does not govern this arithmetic, and a partial bundle
    would regularise a capital good on figures nothing grounded.
    """


#: Parameter id stem shared by every figure in the family, per modelo.
_ID_STEM = "bien-inversion-"

#: Slug of each figure, in the bundle's own field order.
_VENTANA_MUEBLE = "ventana-anos-mueble"
_VENTANA_INMUEBLE = "ventana-anos-inmueble"
_DIVISOR_MUEBLE = "divisor-mueble"
_DIVISOR_INMUEBLE = "divisor-inmueble"
_UMBRAL_PUNTOS = "regularizacion-umbral-puntos"

_REQUIRED_SLUGS = (
    _VENTANA_MUEBLE,
    _VENTANA_INMUEBLE,
    _DIVISOR_MUEBLE,
    _DIVISOR_INMUEBLE,
    _UMBRAL_PUNTOS,
)


class BienesInversionParameterProvenance(BaseModel):
    """Which registry declaration produced a bundle's values.

    Attributes:
        modelo_id: Modelo whose revision hosts the parameters.
        revision_id: The hosting revision's canonical id.
        parameter_ids: Every parameter read, in bundle field order.
        resolved_on: The filing-period date the values were selected for.
    """

    model_config = _STRICT_FROZEN_CONFIG

    modelo_id: str = Field(min_length=1, max_length=16)
    revision_id: str = Field(min_length=1, max_length=64)
    parameter_ids: tuple[str, ...] = Field(min_length=len(_REQUIRED_SLUGS), max_length=len(_REQUIRED_SLUGS))
    resolved_on: date

    @model_validator(mode="after")
    def _names_the_whole_family(self) -> BienesInversionParameterProvenance:
        """Refuse provenance that does not describe the bundle it travels with.

        A bundle resolves five figures, so provenance naming fewer is not a
        record of where those values came from -- it is a partial claim that
        would still satisfy an oracle comparing provenance by equality. Pinning
        the count and the distinctness here means a hand-built bundle cannot
        carry a provenance that describes something else.
        """
        if len(set(self.parameter_ids)) != len(self.parameter_ids):
            raise ValueError("parameter_ids must not repeat an id")
        return self


class BienesInversionRegularizacionParameters(BaseModel):
    """The LIVA art-107/109 figures one revision declares, resolved.

    Every field is required. There is no default anywhere in this model, so an
    instance can only exist because a validated revision supplied every value.

    Attributes:
        ventana_anos_mueble: Art. 107.Uno window for a non-real-property good.
        ventana_anos_inmueble: Art. 107.Tres window for terrenos o edificaciones.
        divisor_mueble: Art. 109.3a divisor for a non-real-property good.
        divisor_inmueble: Art. 109.3a divisor for terrenos o edificaciones.
        umbral_puntos: Art. 107.Uno de-minimis difference in percentage points.
        umbral_comparison: Whether the de-minimis is exceeded strictly or not.
            Registry data rather than a fixed operator, because a redaction
            changing "superior a" to "igual o superior a" would change the
            arithmetic without changing the number.
        provenance: The declaration these values came from.
    """

    model_config = _STRICT_FROZEN_CONFIG

    ventana_anos_mueble: int = Field(gt=0)
    ventana_anos_inmueble: int = Field(gt=0)
    divisor_mueble: Decimal = Field(gt=Decimal(0))
    divisor_inmueble: Decimal = Field(gt=Decimal(0))
    umbral_puntos: Decimal = Field(ge=Decimal(0))
    umbral_comparison: ThresholdComparison
    provenance: BienesInversionParameterProvenance

    def regularizacion_applies(self, diferencia_puntos: Decimal) -> bool:
        """Whether the art-107.Uno de-minimis gate admits a regularisation.

        The comparison direction is registry data rather than a hardcoded
        operator, so the day a redaction changes it the change lands in the
        declaration and not in this file.
        """
        if self.umbral_comparison is ThresholdComparison.INCLUSIVE:
            return diferencia_puntos >= self.umbral_puntos
        return diferencia_puntos > self.umbral_puntos


def resolve_bienes_inversion_regularizacion_parameters(
    revision: ModeloRevision,
    *,
    modelo_id: str,
    filing_period_date: date,
) -> BienesInversionRegularizacionParameters:
    """Build the bundle from one compiled revision's declared parameters.

    Args:
        revision: The compiled revision the application layer selected.
        modelo_id: Modelo the revision belongs to, recorded in provenance.
        filing_period_date: Date on the ``filing_period`` axis to select values for.

    Returns:
        The fully resolved :class:`BienesInversionRegularizacionParameters`.

    Raises:
        BienesInversionParameterResolutionError: When the revision declares none
            of the family, only part of it, or a value that does not resolve for
            ``filing_period_date``.
    """
    declared = {
        parameter.id.split(_ID_STEM, 1)[1]: parameter for parameter in revision.parameters if _ID_STEM in parameter.id
    }
    missing = tuple(slug for slug in _REQUIRED_SLUGS if slug not in declared)
    if missing:
        raise BienesInversionParameterResolutionError(
            f"modelo {modelo_id} revision {revision.id} declares no capital-goods "
            f"regularisation figure for {', '.join(missing)}; the LIVA art-107/109 "
            "arithmetic has no grounded source for this filing context",
        )

    date_context: Mapping[str, date] = {"filing_period": filing_period_date}
    resolved: dict[str, DatedValue] = {}
    for slug in _REQUIRED_SLUGS:
        parameter = declared[slug]
        try:
            resolved[slug] = resolve_dated_value(parameter, date_context)
        except Exception as exc:
            raise BienesInversionParameterResolutionError(
                f"modelo {modelo_id} revision {revision.id} parameter {parameter.id} "
                f"does not resolve for filing-period date {filing_period_date.isoformat()}: {exc}",
            ) from exc

    return BienesInversionRegularizacionParameters(
        ventana_anos_mueble=int(resolved[_VENTANA_MUEBLE].value),
        ventana_anos_inmueble=int(resolved[_VENTANA_INMUEBLE].value),
        divisor_mueble=Decimal(resolved[_DIVISOR_MUEBLE].value),
        divisor_inmueble=Decimal(resolved[_DIVISOR_INMUEBLE].value),
        umbral_puntos=Decimal(resolved[_UMBRAL_PUNTOS].value),
        umbral_comparison=resolved[_UMBRAL_PUNTOS].comparison,
        provenance=BienesInversionParameterProvenance(
            modelo_id=modelo_id,
            revision_id=revision.id,
            parameter_ids=tuple(declared[slug].id for slug in _REQUIRED_SLUGS),
            resolved_on=filing_period_date,
        ),
    )
