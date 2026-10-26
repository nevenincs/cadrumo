"""Canonical locale fixture for operator-surface contract tests."""

from collections.abc import Iterator

import pytest

from ....core.config import override_settings


@pytest.fixture(autouse=True)
def pin_english_locale() -> Iterator[None]:
    """Pin rendered operator-surface assertions to canonical English strings.

    This remains module-imported rather than a package ``conftest`` fixture, so
    sibling operator-surface tests retain their own locale behaviour.
    """

    with override_settings(cadrumo_output_language="en"):
        yield


__all__ = ["pin_english_locale"]
