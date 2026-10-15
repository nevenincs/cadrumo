"""Supply deterministic publisher build inputs to native tooling tests."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from dev.packaging.google_oauth import GOOGLE_OAUTH_ENV

from .google_identity import PUBLISHER_CLIENT_JSON


@pytest.fixture(scope="module", autouse=True)
def _synthetic_publisher_build_identity() -> Iterator[None]:
    """Keep contract generation independent of the operator's publisher credentials."""
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv(GOOGLE_OAUTH_ENV, PUBLISHER_CLIENT_JSON)
        yield
