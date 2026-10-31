"""Registry-wide source, legal, fact and annual manual coverage catalogues."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from enum import StrEnum
from typing import Annotated

from pydantic import BeforeValidator, Field, field_validator, model_validator

from ....core.errors.hierarchy import pydantic_validation_boundary
from ....core.frozen_mapping import FROZEN_MAPPING
from ....core.modelo import Modelo
from .convenio import ConvenioAuthority
from .errors import RegistryValidationError
from .facts.schema import GovernedFactCatalogue
from .ids import LegalRefId, SourceRefId
from .m303_orden_projection_models import M303AnnualOrdenAuthority
from .runtime_catalogues import RuntimeRegistryCatalogues
from .schema_base import RegistryModel, coerce_enum_member
from .schema_references import LegalReference, RegistryExternalLink, SourceReference
from .snapshot_globals import SupportedFilingYearsCatalogue


class SociedadesAnnualManualCoverageStatus(StrEnum):
    """The independently auditable availability state of one annual manual."""

    AVAILABLE = "available"
    UNACQUIRED = "unacquired"
    UNPUBLISHED = "unpublished"


SociedadesAnnualManualCoverageStatusField = Annotated[
    SociedadesAnnualManualCoverageStatus,
    BeforeValidator(coerce_enum_member(SociedadesAnnualManualCoverageStatus)),
]
"""Registry token hydrated into a Sociedades annual-manual coverage status."""


class SociedadesAnnualManualCoverageDisposition(RegistryModel):
    """One exact-year outcome for the annual Sociedades manual corpus.

    This is documentary availability only. It is intentionally separate from
    Modelo 200 revision selection and filing capability.
    """

    year: int = Field(ge=1900, le=9999)
    status: SociedadesAnnualManualCoverageStatusField
    source_ref: SourceRefId | None = None
    official_locator: RegistryExternalLink
    observed_at: date
    acquisition_condition_key: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_disposition(self) -> SociedadesAnnualManualCoverageDisposition:
        if self.status is SociedadesAnnualManualCoverageStatus.AVAILABLE:
            if self.source_ref is None:
                raise ValueError("available Sociedades manual coverage requires source_ref")
            if self.acquisition_condition_key is not None:
                raise ValueError(
                    "available Sociedades manual coverage must not declare acquisition_condition_key",
                )
        elif self.status is SociedadesAnnualManualCoverageStatus.UNACQUIRED:
            if self.source_ref is not None:
                raise ValueError("unacquired Sociedades manual coverage must not declare source_ref")
            if self.acquisition_condition_key is None:
                raise ValueError(
                    "unacquired Sociedades manual coverage requires acquisition_condition_key",
                )
        else:
            if self.source_ref is not None:
                raise ValueError("unpublished Sociedades manual coverage must not declare source_ref")
            if self.acquisition_condition_key is None:
                raise ValueError(
                    "unpublished Sociedades manual coverage requires acquisition_condition_key",
                )
        return self


class SociedadesAnnualManualCoverageCatalogue(RegistryModel):
    """One declarative coverage ledger for annual Sociedades manuals."""

    dispositions: tuple[SociedadesAnnualManualCoverageDisposition, ...] = Field(min_length=1)

    @field_validator("dispositions")
    @classmethod
    @pydantic_validation_boundary
    def _years_are_unique_and_ordered(
        cls,
        value: tuple[SociedadesAnnualManualCoverageDisposition, ...],
    ) -> tuple[SociedadesAnnualManualCoverageDisposition, ...]:
        years = tuple(disposition.year for disposition in value)
        if tuple(sorted(set(years))) != years:
            raise RegistryValidationError(
                "Sociedades annual manual coverage years must be unique and in ascending order",
            )
        return value


class RegistryCatalogues(RegistryModel):
    """Collect the registry-wide legal, source, fact, and support catalogues."""

    legal: Annotated[Mapping[LegalRefId, LegalReference], FROZEN_MAPPING]
    sources: Annotated[Mapping[SourceRefId, SourceReference], FROZEN_MAPPING]
    facts: GovernedFactCatalogue = Field(default_factory=GovernedFactCatalogue)
    convenio: ConvenioAuthority = Field(default_factory=ConvenioAuthority.empty)
    supplementary_ordenes: Annotated[Mapping[Modelo, M303AnnualOrdenAuthority], FROZEN_MAPPING] = Field(
        default_factory=dict[Modelo, M303AnnualOrdenAuthority],
        validate_default=True,
    )
    supported_filing_years: SupportedFilingYearsCatalogue | None = None
    sociedades_annual_manual_coverage: SociedadesAnnualManualCoverageCatalogue | None = None
    runtime: RuntimeRegistryCatalogues = Field(default_factory=RuntimeRegistryCatalogues)

    def require_supported_filing_years(self) -> SupportedFilingYearsCatalogue:
        """Return the registry's single support envelope, refusing a catalogue set without it."""
        if self.supported_filing_years is None:
            raise RegistryValidationError("registry catalogues declare no supported filing years")
        return self.supported_filing_years
