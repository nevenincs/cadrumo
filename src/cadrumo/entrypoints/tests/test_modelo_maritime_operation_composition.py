"""Canonical maritime service over synthetic encrypted profile storage."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from ...adapters.persistence.profile.tests.profile_registration import register_minimal_profile
from ...adapters.persistence.storage.tests.profile_capsule_runtime import open_test_profile_session
from ...adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from ...application.user_profile.access_contracts import AccessDenialCode
from ...application.user_profile.access_errors import ProfileAccessRefusedError
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ..modelo_maritime_operation_composition import build_modelo_maritime_preview_ports

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]
_PROFILE = UUID("70707070-7070-4507-8507-070707070707")


@pytest.mark.parametrize("registered", [False, True], ids=["ordinary-rebeca", "retmar-warning-retry"])
def test_existing_profile_service_uses_retained_pin_and_preserves_retmar_requirement(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
    monkeypatch: pytest.MonkeyPatch,
    registered: bool,
) -> None:
    from ...application.modelo import maritime_preview

    # A retained operation must prevent the service's fallback authority door.
    def fallback() -> None:
        pytest.fail("maritime service must retain the worker's publication pin")

    monkeypatch.setattr(maritime_preview, "bundled_indexed_authority", fallback)
    with isolated_profile_storage_root(tmp_path=tmp_path), open_test_profile_session(str(_PROFILE)):
        register_minimal_profile(
            profile_id=str(_PROFILE),
            overrides={
                "maritime_worker.worker_class": "trabajador_del_mar",
                "maritime_worker.vessel_registry": "REBECA",
                "maritime_worker.retmar_registered": "true" if registered else "false",
            },
        )
        ports = build_modelo_maritime_preview_ports(profile_id=_PROFILE, operation=authority_operation)
        assert ports.operation is authority_operation and ports.profile_id == _PROFILE
        preview = ports.preview(annual_salary=None, qualifying_days=None, gross_navigation_income=Decimal("30000"))
        assert preview.facts.worker_class == "trabajador_del_mar" and preview.facts.vessel_registry == "REBECA"
        assert preview.retmar_mandatory_filing is registered
        assert (preview.retmar_warning_error is not None) is registered
        assert preview.result.retmar_mandatory_filing is False
        assert preview.result.observations[0].legal_refs == ("ley-19-1994:art-75",)
        assert preview.result.observations[0].source_refs
        with pytest.raises(ProfileAccessRefusedError) as refused:
            build_modelo_maritime_preview_ports(profile_id=uuid4(), operation=authority_operation)
        assert refused.value.reason is AccessDenialCode.PROFILE_MISMATCH
