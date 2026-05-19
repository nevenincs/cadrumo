"""Anti-tautology roundtrip proof for the fincas-register SQL boundary.

Persists a populated Finca (every defaultable optional field set to a
non-default value) through the real SQL repository, mutates the
on-disk row to violate a strict pydantic invariant, reloads, and
asserts the corruption surfaces either as ValidationError or as
strict inequality. If this test ever passes silently with a corrupted
row, every fincas-register roundtrip in the suite is tautological.
"""

from __future__ import annotations

import secrets
from collections.abc import Iterator
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from aeat.adapters.persistence.storage import (
    EphemeralMasterKeyProvider,
    create_engine_from_settings,
    session_scope,
)
from aeat.adapters.persistence.storage.crypto._crypto import KEY_SIZE
from aeat.adapters.persistence.storage.sql._orm import Base, FincaRow
from aeat.core.config import Settings
from aeat.domain.fincas import (
    Finca,
    FincaRepository,
    UseType,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_persistence]


@pytest.fixture(autouse=True)
def _patch_master_key() -> Iterator[None]:
    with EphemeralMasterKeyProvider(key=secrets.token_bytes(KEY_SIZE)):
        yield


def _populated_finca() -> Finca:
    """Populate every defaultable optional field with a non-default value."""
    return Finca(
        identifier="calle-mayor-12-3a",
        address="Calle Mayor 12, 3.º A, 28013 Madrid",
        valor_catastral_total=Decimal("180000.00"),
        valor_catastral_construccion=Decimal("120000.00"),
        valor_catastral_revision_year=2018,
        coste_adquisicion=Decimal("210000.00"),
        coste_adquisicion_construccion=Decimal("140000.00"),
        acquisition_date=date(2015, 6, 1),
        disposal_date=date(2024, 12, 31),
        use_type=UseType.VIVIENDA_ARRENDADA,
        is_stressed_area=True,
        schema_version="1",
    )


def test_finca_roundtrip_strict_equality(tmp_path: Path) -> None:
    """A populated Finca round-trips through real SQLite with strict equality."""

    db_path = tmp_path / "fincas-roundtrip.db"
    settings = Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}")
    engine = create_engine_from_settings(settings)
    Base.metadata.create_all(engine)
    try:
        original = _populated_finca()
        with session_scope(engine) as session:
            repo = FincaRepository(session)
            saved = repo.upsert(original)
            assert saved.id is not None

        with session_scope(engine) as session:
            repo = FincaRepository(session)
            loaded = repo.get(saved.id)

        # Strict equality across the boundary; populated-field comparison.
        assert loaded.identifier == original.identifier
        assert loaded.address == original.address
        assert loaded.valor_catastral_total == original.valor_catastral_total
        assert loaded.valor_catastral_construccion == original.valor_catastral_construccion
        assert loaded.valor_catastral_revision_year == original.valor_catastral_revision_year
        assert loaded.coste_adquisicion == original.coste_adquisicion
        assert loaded.coste_adquisicion_construccion == original.coste_adquisicion_construccion
        assert loaded.acquisition_date == original.acquisition_date
        assert loaded.disposal_date == original.disposal_date
        assert loaded.use_type is original.use_type
        assert loaded.is_stressed_area == original.is_stressed_area
        assert loaded.schema_version == original.schema_version
    finally:
        engine.dispose()


def test_finca_invariant_violation_surfaces_on_reload(tmp_path: Path) -> None:
    """Anti-tautology: mutating the on-disk row to violate an invariant must surface.

    The Finca model_validator enforces
    ``valor_catastral_construccion <= valor_catastral_total``. We save
    a row with construccion=120k / total=180k, surgically flip the
    on-disk row so construccion exceeds total, reload, and assert the
    invariant trip surfaces either as ValidationError or as the loaded
    record diverging from the original.

    If this test passes silently with corrupted state, every
    fincas-register roundtrip in the suite is suspect.
    """

    db_path = tmp_path / "fincas-anti-tautology.db"
    settings = Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}")
    engine = create_engine_from_settings(settings)
    Base.metadata.create_all(engine)
    try:
        original = _populated_finca()
        with session_scope(engine) as session:
            saved = FincaRepository(session).upsert(original)
            assert saved.id is not None

        # Surgical mutation: set construccion > total to violate the invariant.
        with session_scope(engine) as session:
            row = session.get(FincaRow, saved.id)
            assert row is not None
            row.valor_catastral_construccion = Decimal("999999.99")

        regression_caught = False
        try:
            with session_scope(engine) as session:
                FincaRepository(session).get(saved.id)
        except Exception:  # noqa: BLE001 - boundary may raise different types
            regression_caught = True

        assert regression_caught, (
            "anti-tautology proof failed: corrupting valor_catastral_construccion "
            "to exceed valor_catastral_total did NOT surface on reload. The "
            "fincas-register boundary is tautological and every roundtrip in "
            "the suite is suspect."
        )
    finally:
        engine.dispose()
