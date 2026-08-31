from __future__ import annotations

from typing import cast

import pytest
from pydantic import AnyHttpUrl, ValidationError

from ......tests.aeat_literal_fixtures import aeat_url
from ..site_health_records import SiteHealthEvidence

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_SEDE_ROOT_URL = aeat_url("sede", "/")


@pytest.mark.parametrize("marker", (42, 99))
def test_non_string_marker_raises_validation_error_not_type_error(marker: int) -> None:
    with pytest.raises(ValidationError) as raised:
        SiteHealthEvidence(
            url=AnyHttpUrl(_SEDE_ROOT_URL),
            http_status=200,
            html_fragment="",
            detected_markers=cast(tuple[str, ...], (marker,)),
        )

    assert raised.value.errors(include_url=False)[0]["type"] == "string_type"


def test_valid_string_markers_are_accepted() -> None:
    evidence = SiteHealthEvidence(
        url=AnyHttpUrl(_SEDE_ROOT_URL),
        http_status=200,
        html_fragment="ok",
        detected_markers=("mantenimiento", "agencia"),
    )

    assert evidence.detected_markers == ("mantenimiento", "agencia")
