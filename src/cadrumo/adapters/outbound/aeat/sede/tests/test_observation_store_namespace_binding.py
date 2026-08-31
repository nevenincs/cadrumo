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
row of each family through the store and reads the raw ``SecureObjectRow`` back
from the encrypted SQL backend, asserting the persisted ``classification`` and
``schema_version`` equal exactly what the registry definition declares. If the
store ever re-hardcoded a divergent sensitivity or version, the persisted row
would disagree with the registry authority and this gate would fail.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import AnyHttpUrl
from sqlalchemy import select

from ......core.config import Settings
from ......core.period import Period
from ......tests.secure_sql import isolated_runtime_profile
from .....persistence.storage._secure_object_namespaces import (
    AEAT_FILED_DECLARATION_ARTEFACTS_NAMESPACE,
    AEAT_FILED_DECLARATION_OBSERVATIONS_NAMESPACE,
    AEAT_IVA_WALLET_OBSERVATIONS_NAMESPACE,
)
from .....persistence.storage.sql import SecureObjectRow
from .....persistence.storage.sql.session import session_scope
from ..iva_compensation_wallet import IVA_COMPENSATION_WALLET_URL
from ..observation_store import FiledDeclaracionObservationStore
from ..schema import (
    FiledDeclaracionArtefact,
    FiledDeclaracionObservation,
    IvaCompensationWalletObservation,
    IvaCompensationWalletRow,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_BUCKET_ID = "7303a2b7-83c8-4937-99f7-8259455fafe4"  # was 'sede-namespace-binding'
_AEAT = Settings.external_constants().aeat
_COTEJO_DOCUMENT_URL = f"{_AEAT.domains.www6}{_AEAT.sede_paths.cotejo_document}"


def _artefact(body: bytes) -> FiledDeclaracionArtefact:
    return FiledDeclaracionArtefact(
        kind="declaration_pdf",
        source_url=AnyHttpUrl(f"{_COTEJO_DOCUMENT_URL}?CSV=TUD4V9XAUV7QJ8QV"),
        content_type="application/pdf",
        byte_count=len(body),
        sha256=hashlib.sha256(body).hexdigest(),
        captured_at=datetime(2024, 7, 1, 9, 0, 0, tzinfo=UTC),
    )


def _observation(artefact: FiledDeclaracionArtefact) -> FiledDeclaracionObservation:
    return FiledDeclaracionObservation(
        modelo="100",
        ejercicio=2023,
        period=Period.from_year_and_code(2023, "0A"),
        expediente_id="202310013522456T",
        status="PRESENTADA",
        presented_at=datetime(2024, 6, 30, 12, 34, 56, tzinfo=UTC),
        authenticated_identity="12345678Z",
        artefacts=(artefact,),
    )


def _iva_wallet_observation() -> IvaCompensationWalletObservation:
    return IvaCompensationWalletObservation(
        taxpayer_nif="12345678Z",
        authenticated_identity="12345678Z",
        target_year=2026,
        target_period=Period.from_year_and_code(2026, "2T"),
        rows=(
            IvaCompensationWalletRow(
                generation_year=2026,
                generation_period=Period.from_year_and_code(2026, "1T"),
                generated_amount=Decimal("1200"),
                applied_amount=Decimal("0"),
                pending_amount=Decimal("1200"),
                raw_label="2026 | 1T | 1200 | 0 | 1200",
            ),
        ),
        total_pending=Decimal("1200"),
        source_url=AnyHttpUrl(IVA_COMPENSATION_WALLET_URL),
        captured_at=datetime(2026, 5, 19, 12, 0, 0, tzinfo=UTC),
        raw_sha256="b" * 64,
    )


def test_persisted_rows_carry_registry_declared_classification_and_version(
    tmp_path: Path,
) -> None:
    """Every store row family persists the classification/version its registry def declares."""

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        store = FiledDeclaracionObservationStore(tmp_path / "sede-cache")

        body = b"%PDF-1.7 sede declaration body for namespace-binding proof"
        artefact = store.persist_artefact(
            ("100", 2023, Period.from_year_and_code(2023, "0A"), "202310013522456T"),
            _artefact(body),
            body,
        )
        store.persist_observation(_observation(artefact))
        store.persist_iva_wallet_observation(_iva_wallet_observation())

        expected_by_namespace = {
            AEAT_FILED_DECLARATION_ARTEFACTS_NAMESPACE.namespace: AEAT_FILED_DECLARATION_ARTEFACTS_NAMESPACE,
            AEAT_FILED_DECLARATION_OBSERVATIONS_NAMESPACE.namespace: AEAT_FILED_DECLARATION_OBSERVATIONS_NAMESPACE,
            AEAT_IVA_WALLET_OBSERVATIONS_NAMESPACE.namespace: AEAT_IVA_WALLET_OBSERVATIONS_NAMESPACE,
        }

        with session_scope(profile.repository._engine) as session:
            rows = session.execute(select(SecureObjectRow)).scalars().all()
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
