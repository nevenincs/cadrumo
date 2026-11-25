"""Registry-definition binding proof for ``FiledDeclaracionObservationStore``.

The store persists three secure-object row families — filed-declaration
artefacts, filed-declaration observations, and IVA-compensation-wallet
observations. Each family's ``classification`` and envelope ``schema_version``
MUST be single-sourced from its
:class:`~adapters.persistence.storage.SecureObjectNamespaceDefinition`
(``AEAT_FILED_DECLARATION_ARTEFACTS_NAMESPACE``,
``AEAT_FILED_DECLARATION_OBSERVATIONS_NAMESPACE``,
``AEAT_IVA_WALLET_OBSERVATIONS_NAMESPACE``) rather than restated as literals in
the store module.

This is a write-path proof, not a constant-equality assertion: it persists one
row of each family through the store and reads the raw the ``secure_objects`` row back
from the encrypted SQL backend, asserting the persisted ``classification`` and
``schema_version`` equal exactly what the registry definition declares. If the
store ever re-hardcoded a divergent sensitivity or version, the persisted row
would disagree with the registry authority and this gate would fail.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import select

from ......core.config import Settings
from ......core.period import Period
from ......domain.calculations.registry.tests.authored_editions import filing_year_envelope, newest_authored_edition
from .....persistence.storage.secure_object_namespaces import (
    AEAT_FILED_DECLARATION_ARTEFACTS_NAMESPACE,
    AEAT_FILED_DECLARATION_OBSERVATIONS_NAMESPACE,
    AEAT_IVA_WALLET_OBSERVATIONS_NAMESPACE,
)
from .....persistence.storage.sql.session import session_scope
from .....persistence.storage.sql.tables import secure_objects_table
from .....persistence.storage.tests.secure_sql import isolated_runtime_profile
from ..observation_store import FiledDeclaracionObservationStore
from .observation_store_support import (
    declaration_pdf_artefact,
    filed_declaration_observation,
    pending_wallet_observation,
)

pytestmark = [pytest.mark.usefixtures("authority_operation"), pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_EJERCICIO = newest_authored_edition("100")
_BUCKET_ID = "7303a2b7-83c8-4937-99f7-8259455fafe4"  # was 'sede-namespace-binding'
_AEAT = Settings.external_constants().aeat
_COTEJO_DOCUMENT_URL = f"{_AEAT.domains.www6}{_AEAT.sede_paths.cotejo_document}"


def test_persisted_rows_carry_registry_declared_classification_and_version(
    tmp_path: Path,
) -> None:
    """Every store row family persists the classification/version its registry def declares."""

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        store = FiledDeclaracionObservationStore(tmp_path / "sede-cache")

        body = b"%PDF-1.7 sede declaration body for namespace-binding proof"
        artefact = store.persist_artefact(
            ("100", _EJERCICIO, Period.from_year_and_code(_EJERCICIO, "0A"), "202310013522456T"),
            declaration_pdf_artefact(body),
            body,
        )
        store.persist_observation(filed_declaration_observation(artefact))
        store.persist_iva_wallet_observation(
            pending_wallet_observation(datetime(filing_year_envelope().horizon, 5, 19, 12, 0, 0, tzinfo=UTC))
        )

        expected_by_namespace = {
            AEAT_FILED_DECLARATION_ARTEFACTS_NAMESPACE.namespace: AEAT_FILED_DECLARATION_ARTEFACTS_NAMESPACE,
            AEAT_FILED_DECLARATION_OBSERVATIONS_NAMESPACE.namespace: AEAT_FILED_DECLARATION_OBSERVATIONS_NAMESPACE,
            AEAT_IVA_WALLET_OBSERVATIONS_NAMESPACE.namespace: AEAT_IVA_WALLET_OBSERVATIONS_NAMESPACE,
        }

        with session_scope(profile.repository._engine) as session:
            rows = session.execute(select(secure_objects_table)).all()
            observed = {row.namespace for row in rows}
            assert expected_by_namespace.keys() <= observed, (
                f"expected all three sede namespaces persisted, saw {sorted(observed)}"
            )
            for row in rows:
                definition = expected_by_namespace.get(row.namespace)
                if definition is None:
                    continue
                assert row.classification == definition.sensitivity.value, (
                    f"{row.namespace} row classification {row.classification!r} "
                    f"diverges from registry def {definition.sensitivity.value!r}"
                )
                assert row.schema_version == definition.schema_version, (
                    f"{row.namespace} row schema_version {row.schema_version} "
                    f"diverges from registry def {definition.schema_version}"
                )
