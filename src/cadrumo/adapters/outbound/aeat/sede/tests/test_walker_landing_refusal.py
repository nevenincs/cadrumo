"""Active browser readers refuse landings without a readable origin."""

from __future__ import annotations

import pytest

from ......core.config import Settings
from ......tests.aeat_literal_fixtures import (
    configured_path,
)
from .._adapter_utils import assert_landed_url_readable
from ..errors import SedeNavigationError

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_AEAT = Settings.external_constants().aeat
_RESUMEN_PATH = configured_path("sede_paths", "expedientes_resumen")


class TestUnreadableLandingIsRefused:
    """A navigation that produced no readable URL is refused, not skipped."""

    def test_a_readable_landing_is_returned_unchanged(self) -> None:
        landed = f"{_AEAT.domains.www6}{_RESUMEN_PATH}"
        assert assert_landed_url_readable(landed, requested_url=landed) == landed

    @pytest.mark.parametrize("landed", ["", "about:blank", _RESUMEN_PATH])
    def test_a_landing_with_no_usable_origin_is_refused(self, landed: str) -> None:
        with pytest.raises(SedeNavigationError):
            assert_landed_url_readable(landed, requested_url=f"{_AEAT.domains.www6}{_RESUMEN_PATH}")

    def test_the_refusal_names_the_requested_url(self) -> None:
        requested = f"{_AEAT.domains.www6}{_RESUMEN_PATH}"
        with pytest.raises(SedeNavigationError) as excinfo:
            assert_landed_url_readable("", requested_url=requested)
        context = excinfo.value.context
        assert context is not None
        assert context["requested_url"] == requested
