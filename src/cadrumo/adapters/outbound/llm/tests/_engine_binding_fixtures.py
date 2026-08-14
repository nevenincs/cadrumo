"""Canonical secure-object engine rendezvous for the LLM key-binding tests.

Both key-binding test modules tamper with rows through the raw SQLAlchemy
engine backing the per-test encrypted profile, reached out-of-band from the
fixture through this module-level holder rather than threaded as a parameter
through every helper.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING

import pytest

from .....tests.secure_sql import TestRuntimeProfile

if TYPE_CHECKING:
    from sqlalchemy import Engine

_ENGINE_HOLDER: list[Engine] = []


@pytest.fixture(autouse=True)
def _bind_engine(secure_object_test_profile: TestRuntimeProfile) -> Iterator[None]:
    _ENGINE_HOLDER.clear()
    _ENGINE_HOLDER.append(secure_object_test_profile.repository._engine)
    yield
    _ENGINE_HOLDER.clear()


__all__ = ["_ENGINE_HOLDER", "_bind_engine"]
