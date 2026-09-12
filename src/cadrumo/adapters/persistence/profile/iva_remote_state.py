"""Encrypted persistence adapter for live IVA acquisition manifests."""

from __future__ import annotations

from typing import ClassVar, override

from pydantic import BaseModel

from ....application.live.remote_state_models import IvaRemoteStateAcquisitionManifest
from ..storage.envelope.secure_bound_repository import SecureBoundRepository
from ..storage.runtime_repository import secure_object_repository_for_active_bucket
from ..storage.secure_object_namespaces import LIVE_IVA_REMOTE_STATE_ACQUISITIONS_NAMESPACE


class IvaRemoteStateAcquisitionManifestRepository(SecureBoundRepository[IvaRemoteStateAcquisitionManifest]):
    """Persist redacted live IVA acquisition manifests in the active bucket."""

    namespace: ClassVar[str] = LIVE_IVA_REMOTE_STATE_ACQUISITIONS_NAMESPACE.namespace
    sensitivity: ClassVar = LIVE_IVA_REMOTE_STATE_ACQUISITIONS_NAMESPACE.sensitivity
    schema_version: ClassVar[int] = LIVE_IVA_REMOTE_STATE_ACQUISITIONS_NAMESPACE.schema_version
    payload_type: ClassVar[type[BaseModel]] = IvaRemoteStateAcquisitionManifest

    def __init__(self) -> None:
        super().__init__(objects=secure_object_repository_for_active_bucket())

    @override
    def extract_identifier(self, payload: IvaRemoteStateAcquisitionManifest) -> str:
        return payload.acquisition_id


__all__ = ["IvaRemoteStateAcquisitionManifestRepository"]
