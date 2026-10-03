"""Encrypted SQL persistence for the Modelo 720 foreign-asset register.

The :class:`domain.foreign_assets.register.ForeignAssetRegister` document is stored
as a ``FINANCIAL`` secure object through the profile secure-object kernel, in the
singleton namespace
:data:`adapters.persistence.storage.secure_object_namespaces.PROFILE_FOREIGN_ASSET_REGISTER_NAMESPACE`.

The register is authoritative primary state: the operator registers each foreign
asset once and declares the per-asset facts the type 2 record needs, so it has a
strict save/load roundtrip and revision-guarded mutation.

See Also:
    :mod:`domain.foreign_assets.register`
        Typed register payload and its invariants.
    :mod:`adapters.persistence.profile.bienes_inversion`
        Sibling register adapter on the same storage kernel.
"""

from __future__ import annotations

from collections.abc import Callable

from ....core.errors.hierarchy import CadrumoError
from ....core.logging import get_logger
from ....domain.foreign_assets.register import (
    ForeignAssetDeclarationEntry,
    ForeignAssetRegister,
    ForeignAssetRegisterEntry,
    ForeignAssetRegisterError,
)
from ..storage.secure_object_namespaces import PROFILE_FOREIGN_ASSET_REGISTER_NAMESPACE
from ..storage.sql.secure_objects import SecureObjectRepository
from ._secure_model_document import (
    ProfileBareModelSecurePersistence,
    resolve_profile_secure_object_repository,
)

_log = get_logger(__name__)


class ForeignAssetRegisterRepository:
    """Governed repository for the encrypted foreign-asset register singleton."""

    def __init__(
        self,
        *,
        bucket_id: str | None = None,
        objects: SecureObjectRepository | None = None,
    ) -> None:
        """Bind the repository to one bucket, or to an explicit secure-object store (tests)."""
        self._storage = ProfileBareModelSecurePersistence(
            objects=resolve_profile_secure_object_repository(objects=objects, bucket_id=bucket_id),
            definition=PROFILE_FOREIGN_ASSET_REGISTER_NAMESPACE,
            model_type=ForeignAssetRegister,
            empty_document=ForeignAssetRegister,
        )

    def load(self) -> ForeignAssetRegister:
        """Load the register, returning an empty document when absent.

        Raises:
            ForeignAssetRegisterError: When the stored envelope cannot be loaded or decrypted.
        """
        try:
            return self._storage.load()
        except (OSError, CadrumoError) as exc:
            _log.debug(
                "foreign asset register load failed",
                extra={
                    "namespace": self._storage.namespace,
                    "object_key": self._storage.object_key,
                    "error_type": type(exc).__name__,
                },
            )
            raise ForeignAssetRegisterError(
                f"unable to load foreign asset register: {self._storage.object_key}",
                context={"namespace": self._storage.namespace, "object_key": self._storage.object_key},
                translated_message="adapters.persistence.profile.foreign_assets.errors.load_register_failed",
            ) from exc

    def register_asset(self, entry: ForeignAssetRegisterEntry) -> ForeignAssetRegister:
        """Atomically add one asset; the document refuses a repeated ref or official identifier."""
        return self._mutate(lambda current: current.with_asset(entry))

    def declare(self, entry: ForeignAssetDeclarationEntry) -> ForeignAssetRegister:
        """Atomically add one declaration; an unknown asset or a repeated key is refused."""
        return self._mutate(lambda current: current.with_declaration(entry))

    def _mutate(self, change: Callable[[ForeignAssetRegister], ForeignAssetRegister]) -> ForeignAssetRegister:
        # The register is a singleton row: every change rewrites the document,
        # so it runs through the revision-guarded unit of work and is re-applied
        # to the newly current document on a concurrent write.
        return self._storage.mutate(change)


__all__ = ["ForeignAssetRegisterRepository"]
