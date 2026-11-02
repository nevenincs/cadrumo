"""The capital-goods regularisation provider and the casillas it can land in.

The output vocabulary is closed and modelo-specific: a regularisation computed
for Modelo 303 casilla 43 is not the same legal quantity as the Modelo 390
annual box, so one is never a spelling of the other.
"""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING, Annotated, Literal

from pydantic import AfterValidator, BaseModel

from ....core.aggregation import BindingSourceKind
from ....core.models import STRICT_FROZEN_CONFIG
from .binding_selector_utils import computed_money_binding_failures
from .form_codes import form_role_validator

if TYPE_CHECKING:
    from .schema import BindingDefinition

__all__ = [
    "BienesInversionRegularizacionOutput",
    "BienesInversionRegularizacionOutputValue",
    "BienesInversionRegularizacionProvider",
    "validate_bienes_inversion_regularizacion_binding",
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

    source_modelo: Annotated[str, AfterValidator(form_role_validator("iva.periodic"))]
    regularizacion_output: BienesInversionRegularizacionOutputValue


def validate_bienes_inversion_regularizacion_binding(binding: BindingDefinition) -> list[str]:
    """Return the build-time diagnostics for one capital-goods regularisation binding.

    The provider model pins the source modelo and the landing output; what
    remains is the value contract, which must be the monetary regularisation the
    resolver computes.
    """
    return computed_money_binding_failures(binding, "bienes-inversion-regularizacion")
