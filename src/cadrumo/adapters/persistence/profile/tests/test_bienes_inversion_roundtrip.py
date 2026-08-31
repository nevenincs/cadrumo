"""Strict roundtrip across the capital-goods IVA regularización register repo.

Persists :class:`BienesInversionIvaRegister` under
``cadrumo.persistence.profile.bienes_inversion`` at ``SensitivityClass.FINANCIAL``.

Anti-tautology: the fixture populates every defaultable field on
:class:`BienInversionIvaRecord` with non-default values (a non-default
``art108_elegible`` False on the second record, a populated
``asset_record_ref``, and a populated :class:`BienInversionDisposal`). The
save-drops-field / load-re-defaults-field regression is caught by two probes:
one corrupts a persisted value and asserts the strict-equality witness surfaces
the drift, one deletes a required field and asserts the load path raises.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pydantic
import pytest

from .....domain.bienes_inversion.register import (
    BienesInversionIvaRegister,
    BienInversionDisposal,
    BienInversionDisposalRegime,
    BienInversionIvaRecord,
    BienInversionKind,
)
from .....tests.secure_sql import isolated_runtime_profile, mutate_encrypted_secure_object_json
from ....persistence.storage.sql.engine import get_engine
from ..bienes_inversion import BienesInversionIvaRegisterRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


def _populated_register() -> BienesInversionIvaRegister:
    movable = BienInversionIvaRecord(
        identifier="bi-2022-furgoneta",
        description="Furgoneta de reparto afecta a la actividad",
        acquisition_year=2022,
        cuota_soportada=Decimal("4200.00"),
        prorrata_inicial_pct=Decimal("80"),
        kind=BienInversionKind.MUEBLE,
        art108_elegible=True,
        asset_record_ref="asset-2022-furgoneta",
        acquisition_ledger_id="ledger-2022-furgoneta",
        disposal=BienInversionDisposal(year=2024, regime=BienInversionDisposalRegime.SUJETA_NO_EXENTA),
    )
    real_estate = BienInversionIvaRecord(
        identifier="bi-2021-local",
        description="Local comercial afecto",
        acquisition_year=2021,
        cuota_soportada=Decimal("31500.00"),
        prorrata_inicial_pct=Decimal("65"),
        kind=BienInversionKind.INMUEBLE,
        art108_elegible=False,
        asset_record_ref="asset-2021-local",
        acquisition_ledger_id="ledger-2021-local",
    )
    return BienesInversionIvaRegister(records=(movable, real_estate))


def test_register_survives_encrypted_storage_roundtrip(tmp_path: Path) -> None:
    """BienesInversionIvaRegister roundtrips through encrypted SQL, field-for-field."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="d63bdf53-db2f-43f7-a735-458cc56ccb9a"):
        repo = BienesInversionIvaRegisterRepository()
        original = _populated_register()
        repo.save(original)
        loaded = repo.load()

        assert loaded == original
        movable = loaded.records[0]
        assert movable.cuota_soportada == Decimal("4200.00")
        assert movable.prorrata_inicial_pct == Decimal("80")
        assert movable.kind is BienInversionKind.MUEBLE
        assert movable.art108_elegible is True
        assert movable.asset_record_ref == "asset-2022-furgoneta"
        assert movable.disposal is not None
        assert movable.disposal.year == 2024
        assert movable.disposal.regime is BienInversionDisposalRegime.SUJETA_NO_EXENTA
        real_estate = loaded.records[1]
        assert real_estate.kind is BienInversionKind.INMUEBLE
        assert real_estate.art108_elegible is False


def test_register_add_refuses_duplicate_identifier(tmp_path: Path) -> None:
    """The atomic add path refuses a second record with an existing identifier."""
    from ..bienes_inversion import BienInversionRecordError, declare_bien_inversion

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="573d2a96-ff7a-48c2-9128-0a8e395f4928"):
        record = _populated_register().records[0]
        declare_bien_inversion(record)
        with pytest.raises(BienInversionRecordError, match="already exists"):
            declare_bien_inversion(record)


def test_register_corrupted_prorrata_surfaces_at_load(tmp_path: Path) -> None:
    """Anti-tautology: corrupting a persisted percentage must surface at load.

    Persists a populated register, reaches into the encrypted SecureObjectRow,
    rewrites the first record's ``prorrata_inicial_pct`` to a different value,
    and asserts the strict-equality witness flags the drift after reload. If this
    ever passes silently, the register boundary is tautological.
    """
    from sqlalchemy import select

    from ...storage.secure_object_namespaces import PROFILE_BIENES_INVERSION_IVA_REGISTER_NAMESPACE
    from ...storage.sql import SecureObjectRow

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="95f73d79-f5cb-4bb7-984d-0991c85c698d") as profile:
        engine = get_engine(profile.settings)
        repo = BienesInversionIvaRegisterRepository()
        original = _populated_register()
        repo.save(original)

        stmt = select(SecureObjectRow).where(
            SecureObjectRow.namespace == PROFILE_BIENES_INVERSION_IVA_REGISTER_NAMESPACE.namespace,
            SecureObjectRow.object_key == PROFILE_BIENES_INVERSION_IVA_REGISTER_NAMESPACE.require_default_object_key(),
        )

        def mutate(document):
            assert document["records"][0]["prorrata_inicial_pct"] == "80"
            document["records"][0]["prorrata_inicial_pct"] = "55"

        mutate_encrypted_secure_object_json(engine, row_statement=stmt, mutate=mutate)

        reloaded = repo.load()
        assert reloaded != original
        assert reloaded.records[0].prorrata_inicial_pct == Decimal("55")


def test_register_missing_cuota_surfaces_at_load(tmp_path: Path) -> None:
    """Anti-tautology: a *deleted* required field must raise at load.

    A save-drops-field / load-re-defaults-field regression is invisible to a
    mutation probe — only an absent-field probe catches it. ``cuota_soportada`` is
    required, so its deletion must raise ``ValidationError``, never silently
    rehydrate a record with no cuota.
    """
    from sqlalchemy import select

    from ...storage.secure_object_namespaces import PROFILE_BIENES_INVERSION_IVA_REGISTER_NAMESPACE
    from ...storage.sql import SecureObjectRow

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="736f0917-5f82-4fad-9731-22994886baf9") as profile:
        engine = get_engine(profile.settings)
        repo = BienesInversionIvaRegisterRepository()
        repo.save(_populated_register())

        stmt = select(SecureObjectRow).where(
            SecureObjectRow.namespace == PROFILE_BIENES_INVERSION_IVA_REGISTER_NAMESPACE.namespace,
            SecureObjectRow.object_key == PROFILE_BIENES_INVERSION_IVA_REGISTER_NAMESPACE.require_default_object_key(),
        )

        def mutate(document):
            assert "cuota_soportada" in document["records"][0]
            del document["records"][0]["cuota_soportada"]

        mutate_encrypted_secure_object_json(engine, row_statement=stmt, mutate=mutate)

        with pytest.raises(pydantic.ValidationError, match="cuota_soportada"):
            repo.load()
