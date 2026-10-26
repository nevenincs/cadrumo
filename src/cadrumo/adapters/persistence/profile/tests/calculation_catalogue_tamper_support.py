"""Plant a calculation-revision catalogue beneath the repository's write guard.

The repository refuses to save a revision whose registry coordinate disagrees
with its parent WorkUnit, so a test proving that a consumer also refuses such a
row has to put it in storage the way tampering would: by rewriting the
encrypted payload of the real row under its unchanged binding.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select

from .....domain.modelos.calculation_revision import CalculationRevision, CalculationRevisionCatalogue
from ...storage.secure_object_namespaces import MODELO_CALCULATION_REVISION_CATALOGUE_NAMESPACE
from ...storage.sql.engine import get_engine
from ...storage.sql.orm import SecureObjectRow
from ...storage.tests.secure_sql import mutate_encrypted_secure_object_json


def plant_calculation_revision_unchecked(
    catalogue: CalculationRevisionCatalogue,
    revision: CalculationRevision,
) -> None:
    """Replace ``revision`` inside the active bucket's persisted catalogue row."""
    namespace = MODELO_CALCULATION_REVISION_CATALOGUE_NAMESPACE
    statement = select(SecureObjectRow).where(
        SecureObjectRow.namespace == namespace.namespace,
        SecureObjectRow.object_key == namespace.require_default_object_key(),
    )
    # Spliced as JSON: a tampered revision is exactly what the catalogue model
    # refuses to hold, so it cannot be built through that model first.
    serialization_context = {"secure_calculation_revision": True}
    planted = catalogue.model_dump(mode="json", context=serialization_context)
    planted["revisions"][revision.calculation_revision_id] = revision.model_dump(
        mode="json",
        context=serialization_context,
    )

    def replace_payload(document: dict[str, Any]) -> None:
        document["payload"] = planted

    mutate_encrypted_secure_object_json(get_engine(), row_statement=statement, mutate=replace_payload)


__all__ = ["plant_calculation_revision_unchecked"]
