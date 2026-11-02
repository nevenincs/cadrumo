"""The annual prorrata regularisation provider and its landing casillas."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from enum import StrEnum
from types import MappingProxyType
from typing import TYPE_CHECKING, Annotated, Literal, Protocol

from pydantic import AfterValidator, BaseModel, field_validator

from ....core.aggregation import BindingSourceKind
from ....core.casilla_id import CasillaId
from ....core.errors.hierarchy import pydantic_validation_boundary
from ....core.models import STRICT_FROZEN_CONFIG
from .binding_selector_utils import computed_money_binding_failures
from .errors import RegistryValidationError
from .form_codes import form_role_validator

if TYPE_CHECKING:
    from .schema import BindingDefinition

__all__ = [
    "PRORRATA_SOURCE_CASILLA_BY_ROLE",
    "ProrrataRegularizacionOutput",
    "ProrrataRegularizacionOutputValue",
    "ProrrataRegularizacionProvider",
    "ProrrataSourcePeriodSelection",
    "ProrrataSourceRole",
    "prorrata_definitive_percentage_source_casilla_id",
    "prorrata_source_casilla_id",
    "validate_prorrata_regularizacion_binding",
]


class _BindingWithProvider(Protocol):
    @property
    def provider(self) -> object:
        """Return the binding's typed provider declaration."""
        ...


class ProrrataRegularizacionOutput(StrEnum):
    """Which casilla a prorrata regularizacion lands in."""

    MODELO_303_CASILLA_44 = "modelo_303_casilla_44"
    MODELO_390_REGULARIZACION_ANUAL = "modelo_390_regularizacion_anual"


ProrrataRegularizacionOutputValue = Literal[
    ProrrataRegularizacionOutput.MODELO_303_CASILLA_44,
    ProrrataRegularizacionOutput.MODELO_390_REGULARIZACION_ANUAL,
]
"""The same vocabulary for a strict model field."""


class ProrrataSourceRole(StrEnum):
    """What a declared prorrata source casilla means to the regularisation."""

    VOLUMEN_CON_DERECHO = "volumen_con_derecho"
    VOLUMEN_TOTAL = "volumen_total"
    PORCENTAJE_DEFINITIVO = "porcentaje_definitivo"


PRORRATA_SOURCE_CASILLA_BY_ROLE: Mapping[ProrrataSourceRole, CasillaId] = MappingProxyType(
    {
        ProrrataSourceRole.VOLUMEN_CON_DERECHO: "iva.prorrata-volumen-con-derecho",
        ProrrataSourceRole.VOLUMEN_TOTAL: "iva.prorrata-volumen-total",
        ProrrataSourceRole.PORCENTAJE_DEFINITIVO: "iva.prorrata-porcentaje",
    }
)


def prorrata_source_casilla_id(
    bindings: Iterable[_BindingWithProvider],
    role: ProrrataSourceRole,
) -> CasillaId | None:
    """Return the casilla a typed prorrata provider declares for ``role``, or ``None`` without one.

    Provider validation guarantees each role's casilla is declared exactly once,
    so the lookup is by meaning and never by position in the declared list.
    """
    for binding in bindings:
        if isinstance(binding.provider, ProrrataRegularizacionProvider):
            return PRORRATA_SOURCE_CASILLA_BY_ROLE[role]
    return None


class ProrrataSourcePeriodSelection(StrEnum):
    """How a prorrata regularisation selects the source liquidation periods.

    ``FILER_LIQUIDATION_CADENCE`` reads the liquidation periods of the cadence
    the filer actually files under -- calendar quarters or, for a monthly filer,
    calendar months (RD 1624/1992 art. 71.3) -- from the period selectors of the
    revisions declaring the source modelo for the regularised year, so one
    declaration serves every past and future year without naming a period.
    """

    FILER_LIQUIDATION_CADENCE = "filer_liquidation_cadence"


def prorrata_definitive_percentage_source_casilla_id(
    bindings: Iterable[_BindingWithProvider],
) -> CasillaId | None:
    """Return the definitive-percentage source named by a typed provider."""
    return prorrata_source_casilla_id(bindings, ProrrataSourceRole.PORCENTAJE_DEFINITIVO)


class ProrrataRegularizacionProvider(BaseModel):
    """Selector for annual prorrata regularisation filing targets."""

    model_config = STRICT_FROZEN_CONFIG

    kind: Literal[BindingSourceKind.PRORRATA_REGULARIZACION] = BindingSourceKind.PRORRATA_REGULARIZACION

    source_modelo: Annotated[str, AfterValidator(form_role_validator("iva.periodic"))]
    source_casilla_ids: tuple[CasillaId, ...]
    source_period_selection: Literal[ProrrataSourcePeriodSelection.FILER_LIQUIDATION_CADENCE]
    regularizacion_output: ProrrataRegularizacionOutputValue

    @field_validator("source_casilla_ids")
    @classmethod
    @pydantic_validation_boundary
    def _source_casilla_ids_match_prorrata_inputs(cls, value: tuple[CasillaId, ...]) -> tuple[CasillaId, ...]:
        if len(value) != len(set(value)) or set(value) != set(PRORRATA_SOURCE_CASILLA_BY_ROLE.values()):
            raise RegistryValidationError(
                "prorrata_regularizacion selector must declare each of the annual prorrata volume "
                "(with right and total) and definitive-percentage casilla ids exactly once",
            )
        return value


def validate_prorrata_regularizacion_binding(binding: BindingDefinition) -> list[str]:
    """Return the build-time diagnostics for one prorrata regularisation binding.

    The provider model pins the source casillas, the cadence-derived source
    period selection and the landing output; what remains is the value
    contract, which must be the monetary regularisation the resolver computes.
    """
    return computed_money_binding_failures(binding, "prorrata-regularizacion")
