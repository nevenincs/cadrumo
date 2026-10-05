"""Encrypted roundtrip and guarded mutation of the Modelo 720 foreign-asset register.

Persists :class:`ForeignAssetRegister` under
``cadrumo.persistence.profile.foreign_assets`` at ``SensitivityClass.FINANCIAL``.

Anti-tautology: the fixture fills every optional field (a subclave, a declaration
for condition 8 with its tipo de titularidad, a partial participation). A probe
rewrites a persisted participation and checks the reload differs, and another
deletes a required field and checks the load refuses rather than re-defaulting.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pydantic
import pytest
from sqlalchemy import select

from .....core.foreign_asset_obligation import M720AssetClassCode
from .....domain.foreign_assets.register import (
    ForeignAssetDeclarationEntry,
    ForeignAssetRegister,
    ForeignAssetRegisterEntry,
    M720AssetIdentifier,
    M720DeclarantCondition,
    M720IdentifierScheme,
)
from ...storage.secure_object_namespaces import PROFILE_FOREIGN_ASSET_REGISTER_NAMESPACE
from ...storage.sql.engine import get_engine
from ...storage.sql.orm import SecureObjectRow
from ...storage.tests.secure_sql import isolated_runtime_profile, mutate_encrypted_secure_object_json
from ..foreign_assets import ForeignAssetRegisterRepository
from .foreign_asset_authoring import declare_foreign_asset, register_asset

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_ACCOUNT_REF = "m720a_" + "a" * 32
_REAL_ESTATE_REF = "m720a_" + "b" * 32


def _account() -> ForeignAssetRegisterEntry:
    return ForeignAssetRegisterEntry(
        asset_ref=_ACCOUNT_REF,
        asset_class=M720AssetClassCode.CUENTA,
        subclave=3,
        country_code="DE",
        identifier=M720AssetIdentifier(scheme=M720IdentifierScheme.IBAN, value="DE89370400440532013000"),
        description="synthetic savings account",
        held_since=date(2015, 1, 1),
    )


def _real_estate() -> ForeignAssetRegisterEntry:
    return ForeignAssetRegisterEntry(
        asset_ref=_REAL_ESTATE_REF,
        asset_class=M720AssetClassCode.BIEN_INMUEBLE,
        subclave=2,
        country_code="PT",
        identifier=M720AssetIdentifier(scheme=M720IdentifierScheme.NONE),
        description="synthetic flat",
        held_since=date(2015, 1, 1),
    )


def _declarations() -> tuple[ForeignAssetDeclarationEntry, ...]:
    return (
        ForeignAssetDeclarationEntry(
            asset_ref=_ACCOUNT_REF,
            condition=M720DeclarantCondition.TITULAR,
            participation_pct=Decimal("50.00"),
        ),
        ForeignAssetDeclarationEntry(
            asset_ref=_REAL_ESTATE_REF,
            condition=M720DeclarantCondition.OTRAS_TITULARIDAD_REAL,
            titularidad_detail="nuda propiedad",
            participation_pct=Decimal("100.00"),
        ),
    )


def _populate(repository: ForeignAssetRegisterRepository) -> ForeignAssetRegister:
    register_asset(repository, _account())
    register_asset(repository, _real_estate())
    current = repository.load()
    for declaration in _declarations():
        current = declare_foreign_asset(repository, declaration)
    return current


def _register_row():
    return select(SecureObjectRow).where(
        SecureObjectRow.namespace == PROFILE_FOREIGN_ASSET_REGISTER_NAMESPACE.namespace,
        SecureObjectRow.object_key == PROFILE_FOREIGN_ASSET_REGISTER_NAMESPACE.require_default_object_key(),
    )


def test_an_absent_register_loads_empty(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="5b1c9f0e-3a2d-4c7e-9f10-7208a1b2c3d4"):
        assert ForeignAssetRegisterRepository().load() == ForeignAssetRegister()


def test_the_register_survives_encrypted_storage_field_for_field(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="6c2d0a1f-4b3e-4d8f-8a21-7208b2c3d4e5"):
        repository = ForeignAssetRegisterRepository()
        written = _populate(repository)

        loaded = ForeignAssetRegisterRepository().load()

        assert loaded == written
        assert loaded == ForeignAssetRegister(assets=(_account(), _real_estate()), declarations=_declarations())


def test_registering_the_same_official_identifier_twice_is_refused(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="7d3e1b2a-5c4f-4e90-9b32-7208c3d4e5f6"):
        repository = ForeignAssetRegisterRepository()
        register_asset(repository, _account())
        duplicate = _account().model_copy(update={"asset_ref": "m720a_" + "c" * 32})

        with pytest.raises(ValueError, match="same official identifier"):
            register_asset(repository, duplicate)
        assert repository.load().assets == (_account(),)


def test_declaring_an_unregistered_asset_is_refused(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="8e4f2c3b-6d50-4fa1-8c43-7208d4e5f607"):
        repository = ForeignAssetRegisterRepository()

        with pytest.raises(ValueError, match="unregistered assets"):
            declare_foreign_asset(repository, _declarations()[0])
        assert repository.load() == ForeignAssetRegister()


def test_a_rewritten_participation_surfaces_on_reload(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="9f5a3d4c-7e61-4ab2-9d54-7208e5f60718") as profile:
        repository = ForeignAssetRegisterRepository()
        written = _populate(repository)

        def mutate(document):
            assert document["declarations"][0]["participation_pct"] == "50.00"
            document["declarations"][0]["participation_pct"] = "25.00"

        mutate_encrypted_secure_object_json(get_engine(profile.settings), row_statement=_register_row(), mutate=mutate)

        reloaded = repository.load()
        assert reloaded != written
        assert reloaded.declarations[0].participation_pct == Decimal("25.00")


def test_a_deleted_required_field_refuses_the_load(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="a06b4e5d-8f72-4bc3-8e65-7208f6071829") as profile:
        repository = ForeignAssetRegisterRepository()
        _populate(repository)

        def mutate(document):
            del document["assets"][0]["country_code"]

        mutate_encrypted_secure_object_json(get_engine(profile.settings), row_statement=_register_row(), mutate=mutate)

        with pytest.raises(pydantic.ValidationError, match="country_code"):
            repository.load()
