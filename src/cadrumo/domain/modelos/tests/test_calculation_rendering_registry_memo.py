"""Repeated reads of identical saved registry bytes validate once and refuse the same tampering."""

from __future__ import annotations

import gc
import json
from collections.abc import Iterator

import pytest
from pydantic import ValidationError
from pydantic_core import SchemaSerializer

from ....core.identity.documents import TAX_ID_FORMAT_CONTEXT
from ...calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ...calculations.registry.facts.atoms import TAGGED_FACT_ATOM_CONTEXT
from ...calculations.registry.facts.resolution import GovernedFactQuery, ResolvedGovernedFact
from ...calculations.registry.governed_fact_scope import validating_governed_facts
from ...calculations.registry.schema_references import TemporalSupportEnvelope
from .. import calculation_revision_rendering as rendering
from ..calculation_revision_rendering import (
    CALCULATION_RENDERING_SERIALIZER_CONTEXT_KEY,
    CalculationRenderingSerializerScope,
    CalculationRenderingSnapshot,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.fixture(autouse=True)
def _fresh_memo(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rendering, "_VERIFIED_REGISTRY", rendering._VerifiedRegistryMemo(maxsize=8))


@pytest.fixture
def operation() -> Iterator[PinnedAuthorityOperation]:
    with bundled_indexed_authority().operation() as pinned, validating_governed_facts(pinned):
        yield pinned


def _saved(operation: PinnedAuthorityOperation) -> str:
    return CalculationRenderingSnapshot.capture(
        operation.snapshot("303", filing_year=2026, period="1T"),
        authority_generation=operation.pin().logical_generation,
    ).model_dump_json()


def _count_compilers(monkeypatch: pytest.MonkeyPatch) -> list[SchemaSerializer]:
    original = rendering._compile_registry_serializer
    compiled: list[SchemaSerializer] = []

    def compile_public_schema() -> SchemaSerializer:
        serializer = original()
        compiled.append(serializer)
        return serializer

    monkeypatch.setattr(rendering, "_compile_registry_serializer", compile_public_schema)
    return compiled


def _read(saved: str, **extra: object) -> CalculationRenderingSnapshot:
    return CalculationRenderingSnapshot.model_validate_json(
        saved, context={CALCULATION_RENDERING_SERIALIZER_CONTEXT_KEY: CalculationRenderingSerializerScope(), **extra}
    )


def test_a_repeated_read_reuses_the_validated_snapshot_and_its_digests(
    operation: PinnedAuthorityOperation, monkeypatch: pytest.MonkeyPatch
) -> None:
    saved = _saved(operation)
    compiled = _count_compilers(monkeypatch)

    first = _read(saved)
    second = _read(saved)

    assert first == second
    assert second.registry_snapshot is first.registry_snapshot
    # Only the cold read compiled the public schema to recompute the rendering digest.
    assert len(compiled) == 1
    assert second.model_dump_json() == saved


@pytest.mark.parametrize("tamper", ("concealed-field", "registry-digest", "rendering-digest", "directory"))
def test_a_warm_memo_refuses_the_same_tampering_as_a_cold_read(
    operation: PinnedAuthorityOperation, tamper: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    saved = _saved(operation)
    payload = json.loads(saved)
    if tamper == "concealed-field":
        payload["registry_snapshot"]["revision"]["localization_key"] += ".tampered"
    elif tamper == "registry-digest":
        payload["registry_digest"] = "0" * 64
    elif tamper == "rendering-digest":
        payload["rendering_digest"] = "0" * 64
    else:
        payload["revision_directory_ids"] = sorted((*payload["revision_directory_ids"], "1900"))
    tampered = json.dumps(payload)
    with pytest.raises(ValidationError) as cold:
        _read(tampered)
    monkeypatch.setattr(rendering, "_VERIFIED_REGISTRY", rendering._VerifiedRegistryMemo(maxsize=8))

    assert _read(saved) == _read(saved)
    with pytest.raises(ValidationError) as warm:
        _read(tampered)

    assert str(warm.value) == str(cold.value)


class _DistinctOwner:
    """A separate governed-fact owner that resolves through the same pinned authority."""

    def __init__(self, operation: PinnedAuthorityOperation) -> None:
        self._operation = operation

    def resolve_governed_fact(self, query: GovernedFactQuery) -> ResolvedGovernedFact:
        return self._operation.resolve_governed_fact(query)

    def supported_filing_years(self) -> TemporalSupportEnvelope:
        return self._operation.supported_filing_years()


def test_another_governed_fact_owner_validates_the_same_bytes_again(operation: PinnedAuthorityOperation) -> None:
    saved = _saved(operation)
    first = _read(saved)

    owner = _DistinctOwner(operation)
    with validating_governed_facts(owner):
        again = _read(saved)
        repeated = _read(saved)

    assert again == first
    assert again.registry_snapshot is not first.registry_snapshot
    assert repeated.registry_snapshot is again.registry_snapshot


def test_a_released_owner_leaves_nothing_a_later_owner_can_reuse(operation: PinnedAuthorityOperation) -> None:
    saved = _saved(operation)
    owner = _DistinctOwner(operation)
    with validating_governed_facts(owner):
        released = _read(saved).registry_snapshot
    del owner
    gc.collect()

    successor = _DistinctOwner(operation)
    with validating_governed_facts(successor):
        fresh = _read(saved).registry_snapshot

    assert fresh is not released
    assert fresh == released


@pytest.mark.parametrize("key", (TAX_ID_FORMAT_CONTEXT, TAGGED_FACT_ATOM_CONTEXT))
def test_a_read_with_caller_validation_context_is_validated_in_full(
    operation: PinnedAuthorityOperation, key: str
) -> None:
    saved = _saved(operation)
    first = _read(saved)
    value: object = True if key == TAGGED_FACT_ATOM_CONTEXT else None

    again = _read(saved, **{key: value})

    assert again == first
    assert again.registry_snapshot is not first.registry_snapshot
