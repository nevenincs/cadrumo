"""Pure application contracts for operator state-projection refusal messages."""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast

import pytest

from cadrumo.application.state_projection import (
    ModeloReadinessRequest,
    ModeloRegistryRefusalCause,
    _registry_readiness_refusal,
    _registry_readiness_revision_mismatch_refusal,
    _resolve_modelo_readiness_registry,
)
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_registry_readiness_refusals_have_no_authored_describe_command() -> None:
    request = ModeloReadinessRequest(modelo="303", revision_id="rev", filing_year=2025)
    quarter = "4T"
    first = _registry_readiness_refusal(request, period_token=quarter, exc=RuntimeError("missing"))
    second = _registry_readiness_revision_mismatch_refusal(
        request,
        period_token=quarter,
        resolved_revision_id="resolved",
    )
    for refusal in (first, second):
        assert "aeat app modelo describe" not in refusal
        assert "revision" in refusal


def test_unavailable_snapshot_carries_closed_cause_separate_from_refusal_prose() -> None:
    class UnavailableAuthority:
        def snapshot(self, *args: object, **kwargs: object) -> None:
            raise FileNotFoundError("private-authority-path")

    request = ModeloReadinessRequest(modelo="303", revision_id="wanted", filing_year=2025)
    resolution = _resolve_modelo_readiness_registry(
        request,
        period=Period.from_year_and_code(2025, "1T"),
        operation=cast(PinnedAuthorityOperation, UnavailableAuthority()),
    )
    assert resolution.snapshot is None
    assert resolution.cause is ModeloRegistryRefusalCause.SNAPSHOT_UNAVAILABLE
    assert resolution.refusal
    assert "private-authority-path" not in resolution.cause.value


def test_revision_mismatch_carries_distinct_closed_cause() -> None:
    class DifferentRevisionAuthority:
        def snapshot(self, *args: object, **kwargs: object) -> SimpleNamespace:
            return SimpleNamespace(revision=SimpleNamespace(id="actual"))

    request = ModeloReadinessRequest(modelo="303", revision_id="wanted", filing_year=2025)
    resolution = _resolve_modelo_readiness_registry(
        request,
        period=Period.from_year_and_code(2025, "1T"),
        operation=cast(PinnedAuthorityOperation, DifferentRevisionAuthority()),
    )
    assert resolution.snapshot is None
    assert resolution.cause is ModeloRegistryRefusalCause.REVISION_MISMATCH
    assert resolution.refusal
