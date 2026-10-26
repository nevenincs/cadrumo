"""The capital-goods regularisation provider and the casillas it can land in.

The output vocabulary is closed and modelo-specific: a regularisation computed
for Modelo 303 casilla 43 is not the same legal quantity as the Modelo 390
annual box, so one is never a spelling of the other.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel

from ....core.aggregation import BindingSourceKind
from ....core.models import STRICT_FROZEN_CONFIG

__all__ = [
    "BienesInversionRegularizacionOutput",
    "BienesInversionRegularizacionOutputValue",
    "BienesInversionRegularizacionProvider",
]


class BienesInversionRegularizacionOutput(StrEnum):
    """Which casilla a bienes-de-inversion regularizacion lands in.

    Distinct from the prorrata regularizacion outputs even though both name a 303 and a
    390 destination: these are different casillas for a different adjustment, and one
    set is not a spelling of the other.
    """

    MODELO_303_CASILLA_43 = "modelo_303_casilla_43"
    MODELO_390_CASILLA_63 = "modelo_390_casilla_63"


BienesInversionRegularizacionOutputValue = Literal[
    BienesInversionRegularizacionOutput.MODELO_303_CASILLA_43,
    BienesInversionRegularizacionOutput.MODELO_390_CASILLA_63,
]
"""The same vocabulary for a strict model field."""


class BienesInversionRegularizacionProvider(BaseModel):
    """Selector for capital-goods regularisation filing targets."""

    model_config = STRICT_FROZEN_CONFIG

    kind: Literal[BindingSourceKind.BIENES_INVERSION_REGULARIZACION] = BindingSourceKind.BIENES_INVERSION_REGULARIZACION

    source_modelo: Literal["303"]
    regularizacion_output: BienesInversionRegularizacionOutputValue
