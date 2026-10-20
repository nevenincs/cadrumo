"""Byte-bounded profile pages preserve the largest fitting ordered prefix."""

from uuid import uuid4

import pytest

from cadrumo.domain.user_profile.values import ProfileSetupState

from ..view_operation import (
    PROFILE_VIEW_MAX_RESULT_BYTES,
    ProfileViewFactItem,
    ProfileViewOperationRequest,
    ProfileViewOperationResult,
    ProfileViewPageKind,
    ProfileViewRefusalCode,
)
from ..view_reader import _paginate_source, _ProfileViewCommon

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.mark.parametrize("size,count", [(1, 0), (1, 128), (400, 128), (21_000, 1), (9_000, 3)])
def test_page_is_maximal_within_the_byte_ceiling(size: int, count: int) -> None:
    request = ProfileViewOperationRequest(profile_id=uuid4(), page_kind=ProfileViewPageKind.FACTS)
    common: _ProfileViewCommon = {
        "profile_id": request.profile_id,
        "page_kind": request.page_kind,
        "record_revision": 1,
        "content_digest": "a" * 64,
        "setup_state": ProfileSetupState.INCOMPLETE,
        "schema_version": 1,
        "valid": True,
        "cursor": 0,
    }
    source = tuple(ProfileViewFactItem(path=f"example.field_{i}", value="ñ" * size) for i in range(count))
    page = _paginate_source(request, common, source)
    if size > 20_000:
        assert page.refusal_code is ProfileViewRefusalCode.ITEM_TOO_LARGE
        return
    assert page.items == source[: len(page.items)]
    assert len(page.model_dump_json().encode("utf-8")) <= PROFILE_VIEW_MAX_RESULT_BYTES
    if page.next_cursor is not None:
        larger_count = len(page.items) + 1
        larger = ProfileViewOperationResult(
            **common,
            outcome="page",
            total_items=count,
            items=source[:larger_count],
            next_cursor=larger_count if larger_count < count else None,
        )
        assert len(larger.model_dump_json().encode("utf-8")) > PROFILE_VIEW_MAX_RESULT_BYTES
