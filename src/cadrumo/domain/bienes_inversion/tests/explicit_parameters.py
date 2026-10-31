"""The explicit regularización parameter bundle the art-109/110 procedure tests supply."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from ...calculations.registry.schema_base import ThresholdComparison
from ..regularizacion_parameters import (
    BienesInversionParameterProvenance,
    BienesInversionRegularizacionParameters,
)

#: An explicit bundle, supplied rather than resolved: these are unit tests of the
#: art-109/110 PROCEDURE, and the procedure is what they prove. Whether the
#: figures below are the ones the law states is a separate question, answered
#: against the registry itself by the modelo 303 parameter gates. Supplying them
#: here as inputs keeps a legal value out of this file's assertions.
EXPLICIT_PARAMS = BienesInversionRegularizacionParameters(
    ventana_anos_mueble=4,
    ventana_anos_inmueble=9,
    divisor_mueble=Decimal("5"),
    divisor_inmueble=Decimal("10"),
    umbral_puntos=Decimal("10"),
    umbral_comparison=ThresholdComparison.EXCLUSIVE,
    provenance=BienesInversionParameterProvenance(
        modelo_id="303",
        revision_id="2025",
        parameter_ids=(
            "m303-bien-inversion-ventana-anos-mueble",
            "m303-bien-inversion-ventana-anos-inmueble",
            "m303-bien-inversion-divisor-mueble",
            "m303-bien-inversion-divisor-inmueble",
            "m303-bien-inversion-regularizacion-umbral-puntos",
        ),
        resolved_on=date(2025, 6, 1),
    ),
)


def params_for(year: int) -> BienesInversionRegularizacionParameters:
    """The bundle, resolved for ``year``.

    The projection now refuses a bundle resolved for a different filing year, so
    a fixture cannot carry one fixed year and be applied to another.
    """
    return EXPLICIT_PARAMS.model_copy(
        update={"provenance": EXPLICIT_PARAMS.provenance.model_copy(update={"resolved_on": date(year, 12, 31)})}
    )
