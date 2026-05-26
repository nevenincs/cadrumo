"""Strict roundtrip across the encrypted justificante boundary.

:class:`JustificanteRepository` persists :class:`Justificante` records
through :class:`SecureObjectRepository` at ``SensitivityClass.AUDIT``.
This test asserts the save / load cycle preserves every typed field of
the record across the column-encryption boundary with byte-identical
fidelity.

Real :class:`EphemeralMasterKeyProvider` and real SQLite. A
regression in the audit-class column-encryption hook, the
``Envelope[Justificante]`` schema, or the repository load path
surfaces as a strict pydantic inequality.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import AnyHttpUrl

from ...adapters.persistence.storage import (
    EphemeralMasterKeyProvider,
)
from ...adapters.persistence.storage.sql import SecureObjectRepository
from ...adapters.persistence.storage.sql._orm import Base
from ...adapters.persistence.storage.sql.engine import create_engine_from_settings
from ...core.config import Settings
from ._repository import JustificanteRepository
from ._schema import Justificante

pytestmark = [pytest.mark.unit, pytest.mark.domain_persistence]


def _populated_justificante() -> Justificante:
    """Build a Justificante with every typed field set to a non-default value."""

    now = datetime.now(UTC).replace(microsecond=0)
    return Justificante(
        csv="ABCD12345678EFGH",
        modelo="303",
        period="1T",
        ejercicio="2025",
        presentation_id="PRES-2025-001-XYZ",
        presented_at=now,
        tax_id="12345678Z",
        total_a_ingresar=Decimal("12345.67"),
        total_a_devolver=None,
        verification_url=AnyHttpUrl(
            "https://sede.agenciatributaria.gob.es/wlpl/SCEJ-MANT/cotejo/CSV/ABCD12345678EFGH",
        ),
        source_pdf_path=Path("justificantes/303-2025-1T-ABCD.pdf"),
        source_pdf_sha256="a" * 64,
        parsed_at=now,
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
    * Decimal: the ``total_a_ingresar`` Decimal must round-trip
      with exact magnitude; a float intermediate would surface
      here as inequality on a fractional value.
    """

    provider = EphemeralMasterKeyProvider()
    with provider:
        db_path = tmp_path / "justificante-roundtrip.db"
        engine = create_engine_from_settings(
            Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"),
        )
        Base.metadata.create_all(engine)
        try:
            objects = SecureObjectRepository(engine=engine)

            original = _populated_justificante()
            repo = JustificanteRepository(objects=objects)
            repo.save(original)
            loaded = repo.load(original.csv)

            assert loaded is not None
            assert loaded == original
            assert loaded.total_a_ingresar == Decimal("12345.67")
            assert loaded.total_a_devolver is None
            assert str(loaded.verification_url).endswith("/ABCD12345678EFGH")
            assert loaded.source_pdf_path == Path("justificantes/303-2025-1T-ABCD.pdf")
            assert loaded.presentation_id == "PRES-2025-001-XYZ"
        finally:
            engine.dispose()
