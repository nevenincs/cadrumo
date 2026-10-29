"""Registry-wide values every snapshot and governed-fact resolution reads.

Resolving any governed fact gates on the support envelope, so these models stay
apart from the full registry schema: reading the envelope must not import every
binding, formula and revision model.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Annotated

from pydantic import Field

from ....core.frozen_mapping import FROZEN_MAPPING
from ....core.modelo import Modelo
from .convenio import ConvenioAuthority
from .m303_orden_projection_models import M303AnnualOrdenAuthority
from .schema_base import RegistryModel
from .schema_references import TemporalSupportEnvelope

if TYPE_CHECKING:
    from .schema_catalogues import RegistryCatalogues


class SupportedFilingYearsCatalogue(TemporalSupportEnvelope):
    """The registry's sole declaration of the filing years the product supports.

    Authored as bounds rather than an enumeration, because the two ends of the
    span do not carry the same force. ``floor`` is a hard gate: nothing resolves
    below it. ``horizon`` is the last globally authored coordinate, not a gate;
    when ``hard_ceiling`` is absent the supported range remains open above it.
    Missing modelo editions inside that range are projected from an eligible
    authored anchor.

    The span is contiguous by construction. A product that supports 2022 and
    2024 but not 2023 is not a state the law produces; the enumerated form could
    express it only by accident, and nothing ever did.

    :attr:`TemporalSupportEnvelope.years` still enumerates the span, derived
    now rather than authored,
    so a consumer asking which years are supported keeps asking the same way. It
    is a plain property rather than a computed field on purpose: the published
    artifact is re-validated against this model on every read, and a serialised
    derivation would be refused there as an unexpected member.
    """

    def admits_filing_year(self, filing_year: int) -> bool:
        """Return whether a filing year is inside the product's hard gates."""
        return self.projection_coordinate(filing_year) is not None


class SnapshotGlobalCatalogues(RegistryModel):
    """Small registry-wide values required while assembling a point snapshot."""

    convenio: ConvenioAuthority = Field(default_factory=ConvenioAuthority.empty)
    supplementary_ordenes: Annotated[Mapping[Modelo, M303AnnualOrdenAuthority], FROZEN_MAPPING] = Field(
        default_factory=dict[Modelo, M303AnnualOrdenAuthority],
        validate_default=True,
    )
    supported_filing_years: SupportedFilingYearsCatalogue

    @classmethod
    def from_catalogues(cls, catalogues: RegistryCatalogues) -> SnapshotGlobalCatalogues:
        """Project only globals consumed by snapshot construction and fact resolution."""
        return cls(
            convenio=catalogues.convenio,
            supplementary_ordenes=catalogues.supplementary_ordenes,
            supported_filing_years=catalogues.require_supported_filing_years(),
        )


__all__ = ["SnapshotGlobalCatalogues", "SupportedFilingYearsCatalogue"]
