"""A modelo row states whether local work is supported once, and refuses to state it two ways."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ..reference_catalogue_contracts import ModeloRowPayload, printed_local_work_status

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_GUIDANCE = "Modelo 600 is filed with the Comunidad Autonoma."


def _row(*, supported: bool, status: str, guidance: str | None) -> ModeloRowPayload:
    return ModeloRowPayload(
        code="600",
        title="Synthetic modelo",
        cadence="ad_hoc",
        tax_domain="itp",
        revision_count=1,
        local_work_supported=supported,
        local_work_status=status,
        local_work_guidance=guidance,
    )


def test_a_row_whose_status_and_guidance_follow_its_flag_is_built_either_way() -> None:
    supported = _row(supported=True, status="supported-model-level", guidance=None)
    unsupported = _row(supported=False, status="unsupported-local-work", guidance=_GUIDANCE)

    assert (supported.local_work_supported, supported.local_work_status) == (True, "supported-model-level")
    assert (unsupported.local_work_supported, unsupported.local_work_status) == (False, "unsupported-local-work")
    assert printed_local_work_status(supported=True) == supported.local_work_status
    assert printed_local_work_status(supported=False) == unsupported.local_work_status


@pytest.mark.parametrize(
    ("supported", "status", "guidance"),
    [
        pytest.param(False, "supported-model-level", _GUIDANCE, id="unsupported-printed-as-supported"),
        pytest.param(True, "unsupported-local-work", None, id="supported-printed-as-unsupported"),
        pytest.param(True, "supported-model-level", _GUIDANCE, id="supported-with-guidance"),
        pytest.param(False, "unsupported-local-work", None, id="unsupported-without-guidance"),
    ],
)
def test_a_row_that_states_its_local_work_support_two_ways_is_refused(
    supported: bool, status: str, guidance: str | None
) -> None:
    with pytest.raises(ValidationError, match="local-work"):
        _row(supported=supported, status=status, guidance=guidance)
