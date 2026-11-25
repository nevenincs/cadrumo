"""The finding a cleared art. 23.2 tier raises: it asks for the leases and names the door that records them."""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.adapters.persistence.storage.custody.tests.profile_schema_legacy_support import (
    publish_legacy_capsule,
    record_session,
)
from cadrumo.application.user_profile.profile_schema_migration import (
    drain_migration_cleared_paths,
    migrate_profile_record_on_open,
)
from cadrumo.core.json_contract import ResolvedNoticeAction

from ....core.config import override_settings
from ....core.i18n.render import tr
from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.user_profile.schema_migration import RETIRED_RENTAL_TIER_PATH
from ....domain.user_profile.values import UserProfileFact
from ...payer_fact_migration_notices import (
    RENTAL_TIER_NOTICE_CODE,
    drain_payer_fact_migration_notices,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_LOCALES = ("en", "es", "ca", "hu")


@pytest.mark.parametrize("locale", _LOCALES)
def test_the_migration_delivers_the_lease_finding_once_in_the_operator_language(tmp_path: Path, locale: str) -> None:
    with bundled_indexed_authority().operation() as operation:
        create_context, decode_context = operation.profile_create_context(), operation.profile_decode_context()
    publish_legacy_capsule(
        tmp_path,
        version=8,
        facts=(
            UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
            UserProfileFact(path=RETIRED_RENTAL_TIER_PATH, value="tier-70"),
        ),
        create_context=create_context,
        decode_context=decode_context,
    )
    drain_migration_cleared_paths()
    session = record_session(decode_context)
    try:
        migrate_profile_record_on_open(session, root=tmp_path)
        with override_settings(cadrumo_output_language=locale):
            first = drain_payer_fact_migration_notices()
            second = drain_payer_fact_migration_notices()
            expected = tr("cli.config.profile.notices.rental_tier_cleared")
    finally:
        session.close()
        drain_migration_cleared_paths()

    (notice,) = first
    assert notice.code == RENTAL_TIER_NOTICE_CODE
    assert notice.message == expected
    assert "arrendamiento" in notice.message
    assert isinstance(notice.action, ResolvedNoticeAction)
    assert notice.action.action.target_command_key == "config.profile.arrendamiento.list"
    assert second == ()
