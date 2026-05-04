"""Runtime schema-provider registry gate."""

from __future__ import annotations

import pytest

from ...domain.filing import FilingBuilderError
from .runtime import build_runtime_schema_provider

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


def test_runtime_schema_provider_requires_registry_snapshot() -> None:
    with pytest.raises(FilingBuilderError, match="validated registry snapshots"):
        build_runtime_schema_provider()
