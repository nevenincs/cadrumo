"""Calculation-history scans refuse rows filed under a foreign key.

``CalculationObservationRepository.iter_modelo`` and
``IvaWalletDecisionRepository.list_decisions`` both filter on the DECRYPTED
payload's own coordinates, which trusts a record to describe the key it is
stored under. A genuine 303/2026/1T observation written under the canonical
``303:2025:1T`` key entered the 2025 window through ``iter_modelo`` and fed
carry-forward and aggregation readers; a wallet decision written under another
taxpayer/period hash sorted into ``list_decisions`` as that subject's latest
decision and entered reconciliation.

Both now scan through the repository base's verifying counterpart, which
recomputes each natural key from the payload and refuses a mismatch rather
than yielding it. The tests write through the real encrypted SQLite substrate
at the wrong key — no double stands between the assertion and the storage
behaviour it claims to check.

Anti-tautology: each case pairs the wrong-key refusal with a same-key scan
that must still yield the record, so a scan broken into refusing everything
fails the second assertion rather than passing the first.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.storage import Envelope, SecureObjectRowIdentityError
from ....core.period import Period
from ....core.external_constants import UTF_8_ENCODING
from ....domain.calculations.registry.bindings import CasillaObservation, RegistryModeloObservation
from ....tests.secure_sql import isolated_runtime_profile
from ..observations_repository import (
    CalculationObservationRepository,
    ObservationEnvelopePayload,
    observation_key,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_CAPTURED_AT = datetime(2026, 5, 28, 11, 35, tzinfo=UTC)
_FOREIGN_REVISION_ID = "revision-from-the-other-period"


def _observation(filing_year: int) -> RegistryModeloObservation:
    return RegistryModeloObservation(
        modelo="303",
        filing_year=filing_year,
        period="1T",
        observations=(
            CasillaObservation(
                casilla_id="iva.cuota-devengada-total",
                value=Decimal("20000.00"),
                legal_refs=("ley-37-1992:art-21",),
                source_refs=("aeat-iva-2026",),
            ),
        ),
    )


def _write_under_key(
    repository: CalculationObservationRepository,
    observation: RegistryModeloObservation,
    *,
    object_key: str,
) -> None:
    """Persist ``observation`` under an arbitrary key, bypassing the writer."""
    payload = ObservationEnvelopePayload(
        observation=observation,
        captured_at=_CAPTURED_AT,
        source_kind="aeat_sede_justificante",
        stamped_revision_id=_FOREIGN_REVISION_ID,
    )
    envelope = Envelope[ObservationEnvelopePayload](
        schema_version=repository.schema_version,
        written_at=_CAPTURED_AT,
        classification=repository.sensitivity,
        payload=payload,
    )
    repository.secure_object_repository.save(
        namespace=repository.namespace,
        object_key=object_key,
        classification=repository.sensitivity,
        schema_version=repository.schema_version,
        written_at=envelope.written_at,
        payload=envelope.model_dump_json().encode(UTF_8_ENCODING),
    )


def test_iter_modelo_refuses_an_observation_filed_under_a_foreign_period_key(
    tmp_path: Path,
) -> None:
    """A 2026 observation stored under the 2025 key must not enter the scan."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        repository = CalculationObservationRepository()
        _write_under_key(
            repository,
            _observation(2026),
            object_key=observation_key("303", Period.from_year_and_code(2025, "1T")),
        )

        with pytest.raises(SecureObjectRowIdentityError):
            tuple(repository.iter_modelo("303"))


def test_iter_modelo_yields_an_observation_filed_under_its_own_key(
    tmp_path: Path,
) -> None:
    """Anti-vacuity: a correctly filed row still reaches the scan."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        repository = CalculationObservationRepository()
        repository.save(
            repository.prepare_observation_envelope(
                _observation(2025),
                source_kind="aeat_sede_justificante",
                captured_at=_CAPTURED_AT,
            )
        )

        scanned = tuple(repository.iter_modelo("303"))

        assert [payload.observation.filing_year for payload in scanned] == [2025]
