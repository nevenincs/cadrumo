"""The v1 provider catalog DTO, projected from normalized records."""

from pydantic import BaseModel

from ...providers.provider_catalog import ProviderRecord

class ProviderCatalogResponse(BaseModel):
    @classmethod
    def from_records(cls, records: tuple[ProviderRecord, ...]) -> ProviderCatalogResponse: ...
