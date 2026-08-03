"""The manager session's page after an edit is what storage holds.

:func:`cadrumo.entrypoints.cli._config._manager_frontend._active_profile_manager_storage`
is the door the live manager runs on, and it projects the post-edit page
from the record the write path committed rather than re-reading it. That
retires a full aggregate decrypt of data the process had just encrypted and
stored, but only if the projected page is genuinely indistinguishable from
the one a fresh read produces -- otherwise the manager would be showing the
operator something subtly other than stored state.

These tests pin that equivalence at the production door. The repository-level
proof (``test_saved_record_is_byte_equivalent_to_a_fresh_load``) covers the
record; this covers the page the operator actually sees.
"""

from __future__ import annotations

import pytest

from .....application.user_profile import (
    ProfileRepository,
    build_profile_overview,
    register_profile_with_credentials,
)
from .....core import require_active_bucket_id
from .....tests.secure_sql import isolated_profile_storage_root
from .._manager_frontend import _active_profile_manager_storage

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
]

_PASSWORD = "manager-session-storage-operator-secret"  # noqa: S105 - synthetic test fixture
_LABEL = "Session Storage Subject"


def _page_from_storage() -> object:
    """Build the page from an independent full read of the encrypted record."""
    aggregate = ProfileRepository().load(require_active_bucket_id())
    return build_profile_overview(aggregate.record, label=_LABEL)


def test_the_post_edit_page_equals_one_built_from_a_fresh_read(tmp_path) -> None:
    """Projecting from the committed record is indistinguishable from re-reading it.

    This is the whole justification for dropping the second decrypt: if the
    two pages could differ, the read would be load-bearing rather than
    redundant and the manager would be rendering a different object.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path):
        register_profile_with_credentials(label=_LABEL, passphrase=_PASSWORD)
        opening, persist = _active_profile_manager_storage(label=_LABEL)

        page = persist("identity.name", "Committed Name")

        assert page != opening, "the edit is not reflected in the returned page"
        assert page == _page_from_storage()


def test_a_cleared_field_also_matches_a_fresh_read(tmp_path) -> None:
    """A blank submission clears the fact, and the page must follow storage.

    Clearing takes the other branch of the write path (a ``None`` value and
    a different bucket event), so the equivalence is pinned on both.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path):
        register_profile_with_credentials(label=_LABEL, passphrase=_PASSWORD)
        _opening, persist = _active_profile_manager_storage(label=_LABEL)
        persist("identity.name", "Committed Name")

        cleared = persist("identity.name", "   ")

        assert cleared == _page_from_storage()


def test_the_equivalence_check_can_actually_fail(tmp_path) -> None:
    """Anti-tautology: the comparison above is not vacuously true.

    If ``build_profile_overview`` returned a value that compared equal
    regardless of its record, both tests would pass against a broken door.
    Two genuinely different records must produce unequal pages.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path):
        register_profile_with_credentials(label=_LABEL, passphrase=_PASSWORD)
        _opening, persist = _active_profile_manager_storage(label=_LABEL)

        first = persist("identity.name", "First Name")
        second = persist("identity.name", "Second Name")

        assert first != second
