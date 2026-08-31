"""Strict roundtrip across the encrypted justificante boundary.

:class:`JustificanteRepository` persists :class:`Justificante` records
through :class:`SecureObjectRepository` at ``SensitivityClass.AUDIT``.
This test asserts the save / load cycle preserves every typed field of
the record across the column-encryption boundary with byte-identical
fidelity.

Real active-profile runtime, real SQLite, no mocks. A regression in
the audit-class column-encryption hook, the
``Envelope[Justificante]`` schema, or the repository load path
surfaces as a strict pydantic inequality.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import AnyHttpUrl
from sqlalchemy import select

from .....core.period import Period
from .....domain.justificante import Justificante
from .....tests.aeat_literal_fixtures import justificante_wlpl_cotejo_url
from .....tests.secure_sql import isolated_runtime_profile, mutate_encrypted_secure_object_json
from ....persistence.storage.sql import SecureObjectRow
from ....persistence.storage.sql.engine import get_engine
from ...storage._secure_object_namespaces import JUSTIFICANTE_METADATA_NAMESPACE
from ...storage.errors import SecureObjectRowIdentityError
from ..justificante import JustificanteRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_PRESENTED_AT = datetime(2026, 5, 27, 11, 15, 0, tzinfo=UTC)
_FOREIGN_CSV = "ZXCV1234QWER5678"


def _populated_justificante() -> Justificante:
    """Build a Justificante with every typed field set to a non-default value."""

    return Justificante(
        csv="ABCD12345678EFGH",
        modelo="303",
        period=Period.from_year_and_code(2025, "1T"),
        ejercicio="2025",
        presentation_id="PRES-2025-001-XYZ",
        presented_at=_PRESENTED_AT,
        tax_id="12345678Z",
        total_a_ingresar=Decimal("12345.67"),
        total_a_devolver=Decimal("456.78"),
        verification_url=AnyHttpUrl(justificante_wlpl_cotejo_url("ABCD12345678EFGH")),
        source_pdf_path=Path("justificantes/303-2025-1T-ABCD.pdf"),
        source_pdf_sha256="a" * 64,
        parsed_at=_PRESENTED_AT,
    )


def test_justificante_survives_encrypted_storage_roundtrip(
    tmp_path: Path,
) -> None:
    """A Justificante persisted through JustificanteRepository loads back equal.

    Exercises the full encrypted-persistence boundary at AUDIT
    sensitivity:

        Justificante -> Envelope -> JSON bytes -> column encryption
            -> SQLite -> column decryption -> JSON bytes -> Envelope
                -> Justificante.

    Per-field witnesses pin the most fragile fields:

    * AnyHttpUrl: pydantic serializes Url objects as str; the
      reload must reconstitute the AnyHttpUrl wrapper.
    * Path: a pathlib.Path serializes as str on the wire; the load
      side must reconstitute the typed Path.
    * Decimal: both monetary Decimals must round-trip with exact magnitude;
      a float intermediate would surface here as inequality on a fractional
      value.
    """

    with isolated_runtime_profile(tmp_path=tmp_path):
        original = _populated_justificante()
        repo = JustificanteRepository()
        repo.save(original)
        loaded = repo.load(original.csv)

        assert loaded is not None
        assert loaded == original
        assert loaded.total_a_ingresar == Decimal("12345.67")
        assert loaded.total_a_devolver == Decimal("456.78")
        assert str(loaded.verification_url).endswith("/ABCD12345678EFGH")
        assert loaded.source_pdf_path == Path("justificantes/303-2025-1T-ABCD.pdf")
        assert loaded.presentation_id == "PRES-2025-001-XYZ"


def test_justificante_corrupted_persisted_csv_refuses_at_load(tmp_path: Path) -> None:
    """A shape-valid foreign CSV in the encrypted payload is refused on load.

    The real encrypted SQLite row stays filed under the original CSV. Rewriting
    only the envelope payload's CSV to another canonical form proves the
    production identity-binding refusal rather than merely Pydantic's shape
    validation: the row decrypts and the payload validates, but its natural key
    no longer agrees with the key used to load it.
    """
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        original = _populated_justificante()
        repo = JustificanteRepository()
        repo.save(original)

        stmt = select(SecureObjectRow).where(
            SecureObjectRow.namespace == JUSTIFICANTE_METADATA_NAMESPACE.namespace,
        )

        def mutate(document):
            assert document["payload"]["csv"] == original.csv
            document["payload"]["csv"] = _FOREIGN_CSV

        mutate_encrypted_secure_object_json(
            get_engine(profile.settings),
            row_statement=stmt,
            mutate=mutate,
        )

        with pytest.raises(SecureObjectRowIdentityError) as refusal:
            repo.load(original.csv)

    assert refusal.value.expected_identifier == original.csv
    assert refusal.value.payload_identifier == _FOREIGN_CSV
