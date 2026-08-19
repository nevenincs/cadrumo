"""Canonical pytest fixtures for LLM encrypted-runtime isolation."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from ..adapters.persistence.tests.runtime_profile_fixture import bucket_scoped_runtime_profile_fixture
from .secure_sql import TestRuntimeProfile

_BUCKET_ID = "70316d3b-62cd-4735-b831-c6712f01a418"  # was 'llm-test-runtime'


@pytest.fixture(autouse=True)
def _secure_object_test_backend(
    secure_object_test_profile: TestRuntimeProfile,
) -> Iterator[None]:
    """Route LLM cache and usage persistence through a per-test encrypted DB."""

    _ = secure_object_test_profile
    yield


secure_object_test_profile = bucket_scoped_runtime_profile_fixture(
    _BUCKET_ID,
    autouse=False,
    name="secure_object_test_profile",
)
