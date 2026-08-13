"""Raw source models for the annual Orden extraction boundary."""

from __future__ import annotations

from collections import Counter
from decimal import Decimal
from typing import Literal

from pydantic import Field, model_validator

from ....core.identity import ContentDigest
from ....domain.iva import IaeEpigrafe
from ._errors import RegistryValidationError
from ._ids import SourceRefId
from ._m303_orden_constants import (
    EXPECTED_ACTIVITY_COUNT,
    EXPECTED_AGRICULTURAL_AXIS_COUNTS,
    EXPECTED_DIFFICULT_JUSTIFICATION_PCT,
    EXPECTED_MODULE_COUNT,
    EXPECTED_MODULE_DISTRIBUTION,
    EXPECTED_NON_AGRICULTURAL_INGRESO_A_CUENTA_COUNT,
    EXPECTED_SEASONAL_INDEXES,
)
from ._schema_base import RegistryModel


class M303AnnualOrdenRawModule(RegistryModel):
    """One directly parsed, position-preserving annual IVA quota module."""

    order: int = Field(ge=1, le=7)
    definition: str = Field(min_length=1)
    unit: str = Field(min_length=1)
    coefficient: Decimal = Field(ge=Decimal("0"))
    required_text: str = Field(min_length=1)


class M303AnnualOrdenRawActivity(RegistryModel):
    """One annual IVA quota table as stated by the pinned BOE HTML."""

    annex_heading: Literal["ANEXO II"]
    activity_name: str = Field(min_length=1)
    iae_epigrafe: IaeEpigrafe
    modules: tuple[M303AnnualOrdenRawModule, ...] = Field(min_length=1, max_length=7)
    cuota_minima_pct: Decimal = Field(ge=Decimal("0"), le=Decimal("100"))
    required_text: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _module_rows_are_complete_and_ordered(self) -> M303AnnualOrdenRawActivity:
        if tuple(module.order for module in self.modules) != tuple(range(1, len(self.modules) + 1)):
            raise RegistryValidationError("annual Orden module rows must be complete and ordered from one")
        return self


class M303AnnualOrdenRawAgriculturalIndex(RegistryModel):
    """One agricultural IVA quota-index row as printed in Annex I."""

    annex_heading: Literal["ANEXO I"]
    activity_name: str = Field(min_length=1)
    cuota_devengada_index: Decimal = Field(gt=Decimal("0"))
    required_text: tuple[str, ...] = Field(min_length=1)


class M303AnnualOrdenRawIngresoACuenta(RegistryModel):
    """One non-agricultural IAE ingreso-a-cuenta row as printed in Annex II."""

    iae_epigrafe: IaeEpigrafe
    activity_name: str = Field(min_length=1)
    percentage: Decimal = Field(ge=Decimal("0"), le=Decimal("100"))
    required_text: str = Field(min_length=1)


class M303AnnualOrdenRawAgriculturalIngresoACuenta(RegistryModel):
    """One agricultural ingreso-a-cuenta row as printed in Annex I."""

    annex_heading: Literal["ANEXO I"]
    activity_name: str = Field(min_length=1)
    percentage: Decimal = Field(ge=Decimal("0"), le=Decimal("100"))
    required_text: tuple[str, ...] = Field(min_length=1)


class M303AnnualOrdenRawSeasonalIndex(RegistryModel):
    """One annual seasonal-day coefficient interval."""

    minimum_days: int = Field(ge=1, le=180)
    maximum_days: int = Field(ge=1, le=180)
    coefficient: Decimal = Field(gt=Decimal("0"))
    required_text: str = Field(min_length=1)

    @model_validator(mode="after")
    def _has_an_ordered_range(self) -> M303AnnualOrdenRawSeasonalIndex:
        if self.minimum_days > self.maximum_days:
            raise RegistryValidationError("annual Orden seasonal index range must be ordered")
        return self


class M303AnnualOrdenRawDifficultJustification(RegistryModel):
    """The matching Annex-I and Annex-II difficult-justification clauses."""

    percentage: Decimal = Field(ge=Decimal("0"), le=Decimal("100"))
    agricultural_required_text: str = Field(min_length=1)
    non_agricultural_required_text: str = Field(min_length=1)


class M303AnnualOrdenSourceCensus(RegistryModel):
    """Complete, digest-bound extraction of one official annual Orden source."""

    ejercicio: int = Field(ge=2000, le=2099)
    source_ref: SourceRefId
    source_content_digest: ContentDigest
    extractor_version: str = Field(min_length=1)
    activities: tuple[M303AnnualOrdenRawActivity, ...] = Field(min_length=EXPECTED_ACTIVITY_COUNT)
    agricultural_indexes: tuple[M303AnnualOrdenRawAgriculturalIndex, ...] = Field(min_length=1)
    non_agricultural_ingresos_a_cuenta: tuple[M303AnnualOrdenRawIngresoACuenta, ...] = Field(min_length=1)
    agricultural_ingresos_a_cuenta: tuple[M303AnnualOrdenRawAgriculturalIngresoACuenta, ...] = Field(min_length=1)
    seasonal_indexes: tuple[M303AnnualOrdenRawSeasonalIndex, ...] = Field(min_length=1)
    difficult_justification: M303AnnualOrdenRawDifficultJustification

    @model_validator(mode="after")
    def _has_the_complete_official_annual_quota_catalogue(self) -> M303AnnualOrdenSourceCensus:
        if len(self.activities) != EXPECTED_ACTIVITY_COUNT:
            raise RegistryValidationError(
                f"annual Orden source must contain {EXPECTED_ACTIVITY_COUNT} annual IVA activity tables, "
                f"got {len(self.activities)}",
            )
        module_counts = Counter(len(activity.modules) for activity in self.activities)
        if module_counts != EXPECTED_MODULE_DISTRIBUTION:
            raise RegistryValidationError(
                "annual Orden source has an unexpected IVA module distribution: "
                f"{dict(sorted(module_counts.items()))!r}",
            )
        if sum(module_counts.values()) != EXPECTED_ACTIVITY_COUNT:
            raise RegistryValidationError("annual Orden source activity table count is internally inconsistent")
        total_modules = sum(module_count * occurrences for module_count, occurrences in module_counts.items())
        if total_modules != EXPECTED_MODULE_COUNT:
            raise RegistryValidationError(
                f"annual Orden source must contain {EXPECTED_MODULE_COUNT} IVA module rows",
            )
        expected_agricultural_count = EXPECTED_AGRICULTURAL_AXIS_COUNTS.get(self.ejercicio)
        if expected_agricultural_count is None:
            raise RegistryValidationError("annual Orden source has an unsupported agricultural axis exercise")
        if len(self.agricultural_indexes) != expected_agricultural_count:
            raise RegistryValidationError("annual Orden source has the wrong agricultural quota-index row count")
        if len(self.agricultural_ingresos_a_cuenta) != expected_agricultural_count:
            raise RegistryValidationError("annual Orden source has the wrong agricultural ingreso-a-cuenta row count")
        if len(self.non_agricultural_ingresos_a_cuenta) != EXPECTED_NON_AGRICULTURAL_INGRESO_A_CUENTA_COUNT:
            raise RegistryValidationError("annual Orden source has the wrong IAE ingreso-a-cuenta row count")
        seasonal_shape = tuple(
            (item.minimum_days, item.maximum_days, item.coefficient) for item in self.seasonal_indexes
        )
        if seasonal_shape != EXPECTED_SEASONAL_INDEXES:
            raise RegistryValidationError("annual Orden source has the wrong seasonal index bands")
        if self.difficult_justification.percentage != EXPECTED_DIFFICULT_JUSTIFICATION_PCT:
            raise RegistryValidationError("annual Orden source has the wrong difficult-justification percentage")
        return self
