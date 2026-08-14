"""Canonical pytest fixtures for LLM encrypted-runtime isolation."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from .secure_sql import TestRuntimeProfile, isolated_runtime_profile

_BUCKET_ID = "llm-test-runtime"


@pytest.fixture(autouse=True)
def _secure_object_test_backend(
    secure_object_test_profile: TestRuntimeProfile,
) -> Iterator[None]:
    """Route LLM cache and usage persistence through a per-test encrypted DB."""

    _ = secure_object_test_profile
    yield


@pytest.fixture
def secure_object_test_profile(tmp_path: Path) -> Iterator[TestRuntimeProfile]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        yield profile
