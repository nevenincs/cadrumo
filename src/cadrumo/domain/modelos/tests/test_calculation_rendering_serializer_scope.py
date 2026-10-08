"""Catalogue-local public serializer reuse preserves every saved rendering value."""

from __future__ import annotations

import json
from collections.abc import Iterator

import pytest
from pydantic import BaseModel, Field, TypeAdapter, ValidationError
from pydantic_core import SchemaSerializer

from ....core.hashing import content_hash_hex
from ....core.models import STRICT_FROZEN_CONFIG
from ...calculations.registry.authority import bundled_indexed_authority
from ...calculations.registry.governed_fact_scope import validating_governed_facts
from ...calculations.registry.schema import MODELO_REVISION_IDS_CONTEXT, RegistrySnapshot
from .. import calculation_revision_rendering as rendering
from ..calculation_revision_rendering import (
    CALCULATION_RENDERING_SERIALIZER_CONTEXT_KEY,
    CalculationRenderingSerializerScope,
    CalculationRenderingSnapshot,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.fixture(autouse=True)
def _governed_fact_scope() -> Iterator[None]:
    with bundled_indexed_authority().operation() as operation, validating_governed_facts(operation):
        yield


class _RenderingBatch(BaseModel):
    model_config = STRICT_FROZEN_CONFIG

    snapshots: tuple[CalculationRenderingSnapshot, ...] = ()


@pytest.fixture(scope="module")
def rendering_batch() -> _RenderingBatch:
    with bundled_indexed_authority().operation() as operation:
        return _RenderingBatch(
            snapshots=tuple(
                CalculationRenderingSnapshot.capture(
                    operation.snapshot("303", filing_year=2025, period=period),
                    authority_generation=operation.pin().logical_generation,
                )
                for period in ("1T", "2T")
            )
        )


def _count_compilers(monkeypatch: pytest.MonkeyPatch) -> list[SchemaSerializer]:
    original = rendering._compile_registry_serializer
    compiled: list[SchemaSerializer] = []

    def compile_public_schema() -> SchemaSerializer:
        serializer = original()
        compiled.append(serializer)
        return serializer

    monkeypatch.setattr(rendering, "_compile_registry_serializer", compile_public_schema)
    return compiled


def _context() -> dict[str, object]:
    return {CALCULATION_RENDERING_SERIALIZER_CONTEXT_KEY: CalculationRenderingSerializerScope()}


def test_one_read_compiles_once_and_preserves_distinct_snapshot_values(
    rendering_batch: _RenderingBatch, monkeypatch: pytest.MonkeyPatch
) -> None:
    saved = rendering_batch.model_dump_json()
    compiled = _count_compilers(monkeypatch)
    context = _context()

    loaded = _RenderingBatch.model_validate_json(saved, context=context)

    assert len(compiled) == 1
    assert loaded == rendering_batch
    assert tuple(value.registry_snapshot.period for value in loaded.snapshots) == ("1T", "2T")
    assert loaded.snapshots[0].registry_snapshot is not loaded.snapshots[1].registry_snapshot
    assert loaded.snapshots[0].rendering_digest != loaded.snapshots[1].rendering_digest
    assert tuple(context) == (CALCULATION_RENDERING_SERIALIZER_CONTEXT_KEY,)


def test_one_write_compiles_once_and_keeps_independent_complete_bytes(
    rendering_batch: _RenderingBatch, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The retained Python traversal is independent of the compiled JSON path.
    complete = rendering_batch.model_dump(mode="python")
    expected = TypeAdapter(dict[str, object]).dump_json(complete)
    compiled = _count_compilers(monkeypatch)

    saved = rendering_batch.model_dump_json(context=_context()).encode()

    assert len(compiled) == 1
    assert saved == expected
    payload = json.loads(saved)
    for value in payload["snapshots"]:
        assert "localization_key" in value["registry_snapshot"]["revision"]
        assert value["rendering_digest"] == content_hash_hex(
            {
                "registry": value["registry_snapshot"],
                "labels": value["labels"],
                "revision_directory_ids": value["revision_directory_ids"],
            }
        )


def test_independent_reads_and_writes_each_compile_a_fresh_schema(
    rendering_batch: _RenderingBatch, monkeypatch: pytest.MonkeyPatch
) -> None:
    saved = rendering_batch.model_dump_json()
    compiled = _count_compilers(monkeypatch)

    for _ in range(2):
        loaded = _RenderingBatch.model_validate_json(saved, context=_context())
        assert loaded.model_dump_json(context=_context()) == saved

    assert len(compiled) == 4
    assert len({id(serializer) for serializer in compiled}) == 4


def test_a_new_scope_uses_the_current_public_schema(
    rendering_batch: _RenderingBatch, monkeypatch: pytest.MonkeyPatch
) -> None:
    snapshot = rendering_batch.snapshots[0].registry_snapshot
    compiled = _count_compilers(monkeypatch)
    before = rendering._registry_payload(snapshot, context=_context())

    class ExtendedSnapshot(RegistrySnapshot):
        additional_public_field: str = Field(default="new declaration", exclude=True)

    extended = ExtendedSnapshot.model_validate(
        {name: getattr(snapshot, name) for name in RegistrySnapshot.model_fields}
    )
    monkeypatch.setattr(rendering, "RegistrySnapshot", ExtendedSnapshot)
    after = rendering._registry_payload(extended, context=_context())

    assert len(compiled) == 2
    assert compiled[0] is not compiled[1]
    assert after.pop("additional_public_field") == "new declaration"
    assert after == before


@pytest.mark.parametrize("tamper", ("concealed-field", "registry-digest", "nested-map-identity", "directory"))
def test_scoped_read_retains_the_same_tamper_refusals(
    rendering_batch: _RenderingBatch, tamper: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    valid = rendering_batch.model_dump_json()
    payload = json.loads(valid)
    second = payload["snapshots"][1]
    if tamper == "concealed-field":
        second["registry_snapshot"]["revision"]["localization_key"] += ".tampered"
    elif tamper == "registry-digest":
        second["registry_digest"] = "0" * 64
    elif tamper == "nested-map-identity":
        sources = second["registry_snapshot"]["sources"]
        sources[next(iter(sources))]["id"] = "different-source-identity"
    else:
        second["revision_directory_ids"] = sorted((*second["revision_directory_ids"], "1900"))
    saved = json.dumps(payload)
    with pytest.raises(ValidationError) as unscoped:
        _RenderingBatch.model_validate_json(saved)
    compiled = _count_compilers(monkeypatch)

    with pytest.raises(ValidationError) as scoped:
        _RenderingBatch.model_validate_json(saved, context=_context())

    assert str(scoped.value) == str(unscoped.value)
    assert len(compiled) == 1
    # A failed call cannot leave its compiler in the next call's context.
    loaded = _RenderingBatch.model_validate_json(valid, context=_context())
    assert loaded == rendering_batch
    assert len(compiled) == 2
    assert compiled[0] is not compiled[1]


def test_sibling_directory_context_stays_local_to_each_snapshot(
    rendering_batch: _RenderingBatch, monkeypatch: pytest.MonkeyPatch
) -> None:
    with bundled_indexed_authority().operation() as operation:
        other = CalculationRenderingSnapshot.capture(
            operation.snapshot("720", filing_year=2026, period="0A"),
            authority_generation=operation.pin().logical_generation,
        )
    original = _RenderingBatch(snapshots=(rendering_batch.snapshots[0], other))
    saved = original.model_dump_json()
    compiled = _count_compilers(monkeypatch)
    context = _context()
    context[MODELO_REVISION_IDS_CONTEXT] = frozenset({"caller-only"})

    loaded = _RenderingBatch.model_validate_json(saved, context=context)

    assert len(compiled) == 1
    assert loaded == original
    assert loaded.snapshots[0].revision_directory_ids != loaded.snapshots[1].revision_directory_ids
    assert context[MODELO_REVISION_IDS_CONTEXT] == frozenset({"caller-only"})
    assert len(context) == 2


def test_empty_calls_leave_the_serializer_lazy(monkeypatch: pytest.MonkeyPatch) -> None:
    compiled = _count_compilers(monkeypatch)
    empty = _RenderingBatch.model_validate_json('{"snapshots":[]}', context=_context())

    assert empty.model_dump_json(context=_context()) == '{"snapshots":[]}'
    assert compiled == []


def test_scoped_read_keeps_valid_historical_omitted_directory_bytes() -> None:
    with bundled_indexed_authority().operation() as operation:
        original = CalculationRenderingSnapshot.capture(
            operation.snapshot("720", filing_year=2026, period="0A"),
            authority_generation=operation.pin().logical_generation,
        )
    payload = json.loads(original.model_dump_json())
    del payload["revision_directory_ids"]
    payload["rendering_digest"] = content_hash_hex(
        {"registry": payload["registry_snapshot"], "labels": payload["labels"]}
    )
    saved = json.dumps(payload)

    unscoped = CalculationRenderingSnapshot.model_validate_json(saved)
    scoped = CalculationRenderingSnapshot.model_validate_json(saved, context=_context())

    assert scoped == unscoped
    assert scoped.revision_directory_ids is None
    assert scoped.model_dump_json(context=_context()) == unscoped.model_dump_json()
