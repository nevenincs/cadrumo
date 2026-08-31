"""Registry-definition binding proof for the LLM secure-object write paths.

The LLM cache, usage sink, and run-telemetry sink each persist an encrypted
secure object. Their ``classification`` and envelope ``schema_version`` MUST be
single-sourced from the owning
:class:`~adapters.persistence.storage.SecureObjectNamespaceDefinition`
(``LLM_CACHE_NAMESPACE`` / ``LLM_USAGE_NAMESPACE`` /
``LLM_RUN_TELEMETRY_NAMESPACE``) rather than restated as ``SensitivityClass``
literals and integer versions in the adapter modules.

This is a write-path proof, not a bare constant-equality assertion: it drives
the exact production recorder each caller uses (``LLMCache.write``,
``UsageRecorder.record``, ``LLMRunTelemetryRecorder.record``), then reads the
raw :class:`SecureObjectRow` back from the encrypted SQL backend and asserts the
persisted classification and schema_version equal exactly what the registry def
declares. If any LLM consumer re-hardcoded a metadata value that diverged from
the def, the substrate write policy would refuse the save (surfacing here as an
error) or the persisted row would disagree with the authority.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import select

from .....llm.models import LLMProvider, LLMRequest, LLMResponse, UsageRecord
from .....tests.secure_sql import TestRuntimeProfile
from ....persistence.storage._secure_object_namespaces import (
    LLM_CACHE_NAMESPACE,
    LLM_RUN_TELEMETRY_NAMESPACE,
    LLM_USAGE_NAMESPACE,
)
from ....persistence.storage.sql import SecureObjectRow
from ....persistence.storage.sql.session import session_scope
from .._cache import LLMCache
from .._run_telemetry import LLMRunRecord, LLMRunTelemetryRecorder
from .._usage import UsageRecorder

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_WHEN = datetime(2026, 5, 28, 12, 40, 0, tzinfo=UTC)


def _rows_for(profile: TestRuntimeProfile, namespace: str) -> list[SecureObjectRow]:
    with session_scope(profile.repository._engine) as session:
        return [row for row in session.execute(select(SecureObjectRow)).scalars().all() if row.namespace == namespace]


def test_llm_cache_row_carries_registry_declared_metadata(
    tmp_path: Path,
    secure_object_test_profile: TestRuntimeProfile,
) -> None:
    """A cache entry written by ``LLMCache.write`` persists the def's metadata."""

    request = LLMRequest(
        prompt="Translate the following AEAT casilla guidance into English.",
        system="You are a faithful AEAT tax-domain translator.",
        max_tokens=512,
        temperature=0.2,
        language="en",
        provider_override=LLMProvider.ANTHROPIC,
        model_override="claude-opus-4-7",
    )
    response = LLMResponse(
        text="Casilla 03 records cumulative net revenue for the period.",
        provider=LLMProvider.ANTHROPIC,
        model="claude-opus-4-7",
        input_tokens=137,
        output_tokens=64,
        cost_estimate_usd=Decimal("0.0145"),
        cache_hit=False,
        created_at=_WHEN,
        request_id="a" * 64,
    )
    LLMCache(root_dir=tmp_path / "llm-cache").write(request, response)

    rows = _rows_for(secure_object_test_profile, LLM_CACHE_NAMESPACE.namespace)
    assert len(rows) == 1, f"expected one cache row, saw {len(rows)}"
    assert rows[0].classification == LLM_CACHE_NAMESPACE.sensitivity.value
    assert rows[0].schema_version == LLM_CACHE_NAMESPACE.schema_version


def test_llm_usage_row_carries_registry_declared_metadata(
    tmp_path: Path,
    secure_object_test_profile: TestRuntimeProfile,
) -> None:
    """A usage row written by ``UsageRecorder.record`` persists the def's metadata."""

    UsageRecorder(root_dir=tmp_path / "llm-usage").record(
        UsageRecord(
            prompt_id="casilla_extract_v1",
            caller="aeat.cli.modelo.calc",
            text="Casilla 03 records cumulative net revenue for the period.",
            provider=LLMProvider.ANTHROPIC,
            model="claude-opus-4-7",
            input_tokens=137,
            output_tokens=64,
            cost_estimate_usd=Decimal("0.0145"),
            cache_hit=False,
            created_at=_WHEN,
            request_id="b" * 64,
        ),
    )

    rows = _rows_for(secure_object_test_profile, LLM_USAGE_NAMESPACE.namespace)
    assert len(rows) == 1, f"expected one usage row, saw {len(rows)}"
    assert rows[0].classification == LLM_USAGE_NAMESPACE.sensitivity.value
    assert rows[0].schema_version == LLM_USAGE_NAMESPACE.schema_version


def test_llm_run_telemetry_row_carries_registry_declared_metadata(
    tmp_path: Path,
    secure_object_test_profile: TestRuntimeProfile,
) -> None:
    """A telemetry row written by ``LLMRunTelemetryRecorder.record`` persists the def's metadata."""

    LLMRunTelemetryRecorder(root_dir=tmp_path / "llm-run-telemetry").record(
        LLMRunRecord(
            run_id="run-binding-proof",
            caller="cadrumo.application.ledger.llm_classification",
            provider="claude",
            model="claude-opus-4-7",
            duration_ms=4200,
            succeeded=True,
            error_kind="",
            started_at=_WHEN,
        ),
    )

    rows = _rows_for(secure_object_test_profile, LLM_RUN_TELEMETRY_NAMESPACE.namespace)
    assert len(rows) == 1, f"expected one telemetry row, saw {len(rows)}"
    assert rows[0].classification == LLM_RUN_TELEMETRY_NAMESPACE.sensitivity.value
    assert rows[0].schema_version == LLM_RUN_TELEMETRY_NAMESPACE.schema_version
