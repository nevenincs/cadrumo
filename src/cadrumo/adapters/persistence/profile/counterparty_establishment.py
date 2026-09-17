"""Encrypted profile adapter for counterparty-establishment facts.

Core types:
:class:`~cadrumo.core.classification.policies.SensitivityClass`.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import ClassVar, override

from pydantic import BaseModel

from ....application.ledger.counterparty_establishment import ConfirmedCounterpartyFacts
from ....application.ledger.counterparty_establishment_ports import (
    CounterpartyEstablishmentPersistenceError,
    CounterpartyEstablishmentRepositoryProtocol,
)
from ....core.classification.policies import SensitivityClass
from ..storage.envelope.secure_bound_repository import SecureBoundRepository
from ..storage.secure_object_namespaces import LEDGER_CONFIRMED_COUNTERPARTY_FACTS_NAMESPACE


def _translate_storage[T](operation: str, action: Callable[[], T]) -> T:
    """Expose only the application persistence error at this boundary."""
    try:
        return action()
    except CounterpartyEstablishmentPersistenceError:
        raise
    except Exception as exc:
        raise CounterpartyEstablishmentPersistenceError(operation) from exc


class CounterpartyEstablishmentRepository(
    SecureBoundRepository[ConfirmedCounterpartyFacts],
    CounterpartyEstablishmentRepositoryProtocol,
):
    """Bind confirmed counterparty facts to the encrypted profile store."""

    namespace: ClassVar[str] = LEDGER_CONFIRMED_COUNTERPARTY_FACTS_NAMESPACE.namespace
    sensitivity: ClassVar[SensitivityClass] = LEDGER_CONFIRMED_COUNTERPARTY_FACTS_NAMESPACE.sensitivity
    schema_version: ClassVar[int] = LEDGER_CONFIRMED_COUNTERPARTY_FACTS_NAMESPACE.schema_version
    payload_type: ClassVar[type[BaseModel]] = ConfirmedCounterpartyFacts

    @override
    def extract_identifier(self, payload: ConfirmedCounterpartyFacts) -> str:
        return payload.counterparty_key

    @override
    def load(self, identifier: str) -> ConfirmedCounterpartyFacts | None:
        """Load a fact while translating secure-object failures."""
        return _translate_storage(
            "load",
            lambda: super(CounterpartyEstablishmentRepository, self).load(identifier),
        )

    @override
    def save(self, payload: ConfirmedCounterpartyFacts) -> None:
        """Persist a fact while translating secure-object failures."""
        _translate_storage(
            "save",
            lambda: super(CounterpartyEstablishmentRepository, self).save(payload),
        )

    @override
    def delete(self, identifier: str) -> bool:
        """Delete a fact while translating secure-object failures."""
        return _translate_storage(
            "delete",
            lambda: super(CounterpartyEstablishmentRepository, self).delete(identifier),
        )


def build_counterparty_establishment_repository(
    *,
    bucket_id: str,
) -> CounterpartyEstablishmentRepositoryProtocol:
    """Bind the encrypted counterparty-facts store to one profile bucket."""
    return CounterpartyEstablishmentRepository(bucket_id=bucket_id)


__all__ = [
    "CounterpartyEstablishmentRepository",
    "build_counterparty_establishment_repository",
]
