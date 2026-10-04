"""Encrypted SQL persistence for the modelo 360 solicitud register.

The :class:`application.filing.producer_snapshot_m360.Modelo360SolicitudRegister` document
is stored as a ``FINANCIAL`` secure object through the profile secure-object kernel, in the
singleton namespace
:data:`adapters.persistence.storage.secure_object_namespaces.PROFILE_MODELO_360_SOLICITUD_NAMESPACE`.

The register is authoritative primary state: the operator declares each solicitud's header,
parties and account choice (a reference to one of the solicitante's own accounts, or the
representante's account embedded here), and no other store can answer them. It therefore has a strict
save/load roundtrip and revision-guarded mutation.

See Also:
    :mod:`adapters.persistence.profile.foreign_assets`
        Sibling register adapter on the same storage kernel.
"""

from __future__ import annotations

from ....application.filing.producer_snapshot_m360 import Modelo360SolicitudEntry, Modelo360SolicitudRegister
from ..storage.secure_object_namespaces import PROFILE_MODELO_360_SOLICITUD_NAMESPACE
from ..storage.sql.secure_objects import SecureObjectRepository
from ._secure_model_document import (
    ProfileBareModelSecurePersistence,
    resolve_profile_secure_object_repository,
)


class Modelo360SolicitudRepository:
    """Governed repository for the encrypted modelo 360 solicitud register singleton."""

    def __init__(
        self,
        *,
        bucket_id: str | None = None,
        objects: SecureObjectRepository | None = None,
    ) -> None:
        """Bind the repository to one bucket, or to an explicit secure-object store (tests)."""
        self._storage = ProfileBareModelSecurePersistence(
            objects=resolve_profile_secure_object_repository(objects=objects, bucket_id=bucket_id),
            definition=PROFILE_MODELO_360_SOLICITUD_NAMESPACE,
            model_type=Modelo360SolicitudRegister,
            empty_document=Modelo360SolicitudRegister,
        )

    def load(self) -> Modelo360SolicitudRegister:
        """Load the register, returning an empty document when none was ever written."""
        return self._storage.load()

    def declare(self, entry: Modelo360SolicitudEntry) -> Modelo360SolicitudRegister:
        """Atomically declare one solicitud, replacing any earlier entry for its period."""
        # A singleton row: the change rewrites the whole document, so it runs through
        # the revision-guarded unit of work and is re-applied on a concurrent write.
        return self._storage.mutate(lambda current: current.with_entry(entry))


__all__ = ["Modelo360SolicitudRepository"]
