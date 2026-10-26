"""Inspect real encrypted repository state in owning fixtures."""

from __future__ import annotations

from .....persistence.storage.errors import SecureObjectRowIdentityError
from ..errors import SedeValidationError
from ..observation_store import FiledDeclaracionObservationStore
from ..schema import IvaCompensationWalletObservation


def list_iva_wallet_observations(
    self: FiledDeclaracionObservationStore,
) -> tuple[IvaCompensationWalletObservation, ...]:
    """Return :class:`IvaCompensationWalletObservation` records from the active encrypted backend.

    Rows are scanned from
    :data:`adapters.persistence.storage.secure_object_namespaces.AEAT_IVA_WALLET_OBSERVATIONS_NAMESPACE`.
    """
    with self._crypto_scope():
        try:
            observations = list(self._wallet_observations.iter_records())
        except SecureObjectRowIdentityError as exc:
            raise SedeValidationError(
                f"IVA wallet observation does not derive the row it is stored in; decrypted payload is filed under {exc.expected_identifier!r}"
            ) from exc
    return tuple(
        sorted(observations, key=lambda item: (item.target_year, item.target_period.registry_token, item.captured_at))
    )
