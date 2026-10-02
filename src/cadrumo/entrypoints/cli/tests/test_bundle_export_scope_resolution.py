"""A scoped export resolves its bound profile despite another ambient selection."""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.tests.profile_registration import register_cli_profile

from ....adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from ....application.user_profile.bundle_export import prepare_profile_export, reconcile_prepared_exports
from ....application.user_profile.bundle_export_contracts import (
    ProfileBundleExportPurpose,
    ProfileBundleExportRequest,
    ProfileBundleExportTransport,
)
from ....application.user_profile.bundle_export_operation import ProfileBundleExportJournalRepository
from ....application.user_profile.profile_pointer import active_profile_pointer_transaction
from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.user_profile.errors import ProfileExportError

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _request(destination: Path, *, name: str | None = None) -> ProfileBundleExportRequest:
    return ProfileBundleExportRequest(
        profile_name=name,
        destination=destination,
        purpose=ProfileBundleExportPurpose.PORTABLE_TRANSFER,
        transport=ProfileBundleExportTransport.CLEARTEXT_LOCAL,
    )


def test_scoped_export_ignores_ambient_profile_and_refuses_conflicting_name(tmp_path: Path) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path):
        alpha = register_cli_profile(label="Scope alpha", log_in=False)
        beta = register_cli_profile(label="Scope beta", log_in=False)
        repository = ProfileBundleExportJournalRepository()
        with active_profile_pointer_transaction() as pointer:
            assert pointer.select(alpha).bucket_id == alpha

        with bundled_indexed_authority().operation() as authority:
            decode = authority.profile_decode_context()
            prepared = prepare_profile_export(
                _request(tmp_path / "beta-bundle.json"),
                journal=repository,
                profile_decode_context=decode,
                authorized_profile_id=beta,
            )
            assert prepared.operation.profile_id == beta
            assert prepared.pointer.bucket_id == beta
            assert str(prepared.bundle.profile.profile_id) == beta
            assert Path(prepared.staged_path).is_file()

            with pytest.raises(ProfileExportError) as refusal:
                prepare_profile_export(
                    _request(tmp_path / "wrong-bundle.json", name="Scope alpha"),
                    journal=repository,
                    profile_decode_context=decode,
                    authorized_profile_id=beta,
                )
            assert refusal.value.context == {"profile_matches": False}
            assert tuple(item.operation_id for item in repository.scan().operations) == (
                prepared.operation.operation_id,
            )
            assert not (tmp_path / "wrong-bundle.json").exists()

            recovered = reconcile_prepared_exports(
                journal=repository,
                profile_decode_context=decode,
                authorized_profile_id=beta,
            )
            assert tuple(item.operation_id for item in recovered.reconciled) == (prepared.operation.operation_id,)
            assert not Path(prepared.staged_path).exists()
