"""The shared result-size refusal trips strictly above its parameterised byte bound."""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from cadrumo_client.contracts.access_refusals import AccessDenialCode

from ....core.hashing import canonical_json_bytes
from ...user_profile.access_errors import ProfileAccessRefusedError
from ..result_size import refuse_oversized_result

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


class _Document(BaseModel):
    text: str


def _document_of_size(size: int) -> _Document:
    document = _Document(text="")
    overhead = len(canonical_json_bytes(document.model_dump(mode="json")))
    sized = _Document(text="x" * (size - overhead))
    assert len(canonical_json_bytes(sized.model_dump(mode="json"))) == size
    return sized


@pytest.mark.parametrize("limit", [64, 4_096])
def test_a_result_at_the_limit_is_accepted(limit: int) -> None:
    refuse_oversized_result(_document_of_size(limit), limit)


@pytest.mark.parametrize("limit", [64, 4_096])
def test_a_result_one_byte_over_the_limit_is_refused_as_operation_denied(limit: int) -> None:
    with pytest.raises(ProfileAccessRefusedError) as refused:
        refuse_oversized_result(_document_of_size(limit + 1), limit)

    assert refused.value.reason is AccessDenialCode.OPERATION_DENIED
