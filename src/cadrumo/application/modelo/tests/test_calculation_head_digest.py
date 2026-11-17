"""Full current-head CAS bytes survive saved-registry composition unchanged."""

from __future__ import annotations

import sys
import time
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from statistics import median
from types import FrameType

import pytest
from pydantic import SerializerFunctionWrapHandler, ValidationError, model_serializer

from ....core.hashing import (
    CanonicalJsonValue,
    canonical_json_bytes,
    canonical_json_bytes_with_member,
    content_hash_hex,
    sha256_hex,
)
from ....core.period import Period
from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ....domain.calculations.registry.schema import RegistrySnapshot
from ....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionCatalogue,
    CalculationRevisionState,
    derive_calculation_revision_id,
    derive_calculation_revision_id_from_revision,
)
from ....domain.modelos.calculation_revision_rendering import CalculationRenderingSnapshot, registry_payload
from ....domain.modelos.work_unit import WorkUnit, WorkUnitCatalogue, derive_work_unit_id
from ...operations.contract_manifest import load_operation_contract_manifest
from ..edit_admission import admit_modelo_edit_baseline
from ..edit_models import ModeloEditAdmittedV1, ModeloEditStaleBaselineRefusalV1
from ..edit_services import calculation_head_digest, reconfirm_modelo_edit_baseline

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.fixture(autouse=True)
def _governed_fact_scope() -> Iterator[None]:
    with bundled_indexed_authority().operation() as operation, validating_governed_facts(operation):
        yield


class _CustomHead(CalculationRevision):
    @model_serializer(mode="plain")
    def custom_wire(self) -> dict[str, str]:
        return {"custom": self.calculation_revision_id}


class _CustomRendering(CalculationRenderingSnapshot):
    @model_serializer(mode="wrap")
    def custom_wire(self, handler: SerializerFunctionWrapHandler) -> dict[str, object]:
        return {"custom": handler(self)}


def test_custom_serializers_use_original_full_dump(saved_head: CalculationRevision) -> None:
    custom = _CustomHead.model_validate(dict(saved_head))
    assert calculation_head_digest(custom) == sha256_hex(_original_bytes(custom))
    rendering = saved_head.rendering_snapshot
    assert rendering is not None
    custom_rendering = _CustomRendering.model_validate(dict(rendering))
    changed = saved_head.model_copy(update={"rendering_snapshot": custom_rendering})
    assert calculation_head_digest(changed) == sha256_hex(_original_bytes(changed))


@pytest.fixture(scope="module")
def saved_head() -> CalculationRevision:
    with bundled_indexed_authority().operation() as operation:
        year = operation.supported_filing_years().horizon
        snapshot = operation.reading_snapshot("100", filing_year=year, period="0A")
        rendering = CalculationRenderingSnapshot.capture(
            snapshot, authority_generation=operation.pin().logical_generation
        )
    created = datetime(year, 1, 1, tzinfo=UTC)
    revision_id = derive_calculation_revision_id(
        work_unit_id="b" * 64,
        input_values_by_casilla_id={},
        binding_overrides={},
        casilla_values={},
        source_provenance=(),
        filing_instance_evidence=None,
        rendering_snapshot=rendering,
    )
    return CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id="b" * 64,
        registry_snapshot_ref=snapshot.snapshot_ref,
        state=CalculationRevisionState.BORRADOR,
        rendering_snapshot=rendering,
        source_provenance=(),
        filing_instance_evidence=None,
        created_at=created,
        updated_at=created,
    )


def _original_bytes(head: CalculationRevision | None) -> bytes:
    return canonical_json_bytes({"calculation_head": None if head is None else head.model_dump(mode="json")})


def _assert_parity(head: CalculationRevision | None) -> None:
    expected = _original_bytes(head)
    assert calculation_head_digest(head) == sha256_hex(expected)
    if head is not None and head.rendering_snapshot is not None:
        value = CanonicalJsonValue(registry_payload(head.rendering_snapshot.registry_snapshot))
        payload = head.model_dump(mode="json", exclude={"rendering_snapshot": {"registry_snapshot"}})
        assert (
            canonical_json_bytes_with_member(
                {"calculation_head": payload},
                object_path=("calculation_head", "rendering_snapshot"),
                member="registry_snapshot",
                value=value,
            )
            == expected
        )


@pytest.mark.parametrize("state", tuple(CalculationRevisionState))
def test_current_head_bytes_across_valid_lifecycle_states(
    saved_head: CalculationRevision, state: CalculationRevisionState
) -> None:
    update: dict[str, object] = {"state": state, "updated_at": saved_head.created_at + timedelta(seconds=3)}
    if state in (
        CalculationRevisionState.VERIFICADO_COMPLETO,
        CalculationRevisionState.PRESENTADO,
        CalculationRevisionState.PRESENTADO_SUPERSEDIDO,
    ):
        update.update(verified_at=saved_head.created_at + timedelta(seconds=1), verified_by="Prueba ñ")
    if state in (CalculationRevisionState.PRESENTADO, CalculationRevisionState.PRESENTADO_SUPERSEDIDO):
        update.update(filed_at=saved_head.created_at + timedelta(seconds=2), filed_by="Prueba ñ")
    if state is CalculationRevisionState.PRESENTADO_SUPERSEDIDO:
        update["superseded_at"] = saved_head.created_at + timedelta(seconds=3)
    if state is CalculationRevisionState.DESCARTADO:
        update.update(
            discarded_at=saved_head.created_at + timedelta(seconds=3), discarded_by="Prueba ñ", discard_reason="Prueba"
        )
    copied = saved_head.model_copy(update=update)
    validated = CalculationRevision.model_validate_json(copied.model_dump_json())
    assert validated.calculation_revision_id == saved_head.calculation_revision_id
    _assert_parity(validated)
    assert calculation_head_digest(validated) != calculation_head_digest(saved_head)


def test_absent_head_and_legacy_absent_rendering(saved_head: CalculationRevision) -> None:
    _assert_parity(None)
    _assert_parity(saved_head.model_copy(update={"rendering_snapshot": None}))


@pytest.mark.parametrize("filed", (False, True), ids=("verified", "filed"))
def test_reconfirm_refuses_same_id_lifecycle_drift(saved_head: CalculationRevision, filed: bool) -> None:
    rendering = saved_head.rendering_snapshot
    assert rendering is not None
    snapshot = rendering.registry_snapshot
    period = Period.from_year_and_code(snapshot.filing_year, snapshot.period)
    work_id = derive_work_unit_id(
        bucket_id="digest-test",
        modelo="100",
        filing_year=snapshot.filing_year,
        period=period,
        revision_id=snapshot.revision.id,
    )
    selected = saved_head.model_copy(update={"work_unit_id": work_id})
    head = CalculationRevision.model_validate(
        dict(
            selected.model_copy(
                update={
                    "calculation_revision_id": derive_calculation_revision_id_from_revision(selected),
                }
            )
        )
    )
    work = WorkUnit(
        work_unit_id=work_id,
        bucket_id="digest-test",
        modelo="100",
        filing_year=snapshot.filing_year,
        period=period,
        revision_id=snapshot.revision.id,
        name="Synthetic digest return",
        created_at=head.created_at,
        updated_at=head.updated_at,
        current_calculation_revision_id=head.calculation_revision_id,
    )
    works = WorkUnitCatalogue(work_units={work_id: work})
    calculations = CalculationRevisionCatalogue(revisions={head.calculation_revision_id: head})
    with bundled_indexed_authority().operation() as operation:
        admitted = admit_modelo_edit_baseline(
            work_unit_id=work_id,
            work_catalogue=works,
            calculation_catalogue=calculations,
            operation=operation,
            operation_contracts=load_operation_contract_manifest().contract_set,
        )
    assert isinstance(admitted, ModeloEditAdmittedV1)
    assert (
        reconfirm_modelo_edit_baseline(
            admitted.baseline,
            work_catalogue=works,
            calculation_catalogue=calculations,
        )
        is None
    )
    update: dict[str, object] = {
        "state": CalculationRevisionState.PRESENTADO if filed else CalculationRevisionState.VERIFICADO_COMPLETO,
        "verified_at": head.created_at + timedelta(seconds=1),
        "verified_by": "Synthetic verifier",
        "updated_at": head.created_at + timedelta(seconds=2),
    }
    if filed:
        update.update(filed_at=head.created_at + timedelta(seconds=2), filed_by="Synthetic filer")
    changed = CalculationRevision.model_validate(dict(head.model_copy(update=update)))
    assert changed.calculation_revision_id == head.calculation_revision_id
    current = CalculationRevisionCatalogue(revisions={changed.calculation_revision_id: changed})
    refusal = reconfirm_modelo_edit_baseline(admitted.baseline, work_catalogue=works, calculation_catalogue=current)
    assert isinstance(refusal, ModeloEditStaleBaselineRefusalV1)
    assert refusal.mismatching_coordinates == ("calculation_head_digest",)


def test_same_coordinate_copy_is_never_served_stale_bytes(saved_head: CalculationRevision) -> None:
    rendering = saved_head.rendering_snapshot
    assert rendering is not None
    snapshot = rendering.registry_snapshot
    changed = snapshot.model_copy(update={"revision": snapshot.revision.model_copy(update={"formulas": ()})})
    assert changed.snapshot_ref == snapshot.snapshot_ref
    copied = saved_head.model_copy(
        update={"rendering_snapshot": rendering.model_copy(update={"registry_snapshot": changed})}
    )
    _assert_parity(copied)
    assert calculation_head_digest(copied) != calculation_head_digest(saved_head)
    _assert_parity(saved_head)


def test_generation_labels_and_directory_are_fresh(saved_head: CalculationRevision) -> None:
    rendering = saved_head.rendering_snapshot
    assert rendering is not None and rendering.labels
    changes: tuple[dict[str, object], ...] = (
        {"authority_generation": "a" * 64},
        {"labels": (rendering.labels[0].model_copy(update={"text": 'Prueba ñ 😀 \\"\n'}), *rendering.labels[1:])},
        {"revision_directory_ids": None},
    )
    for update in changes:
        copied = saved_head.model_copy(update={"rendering_snapshot": rendering.model_copy(update=update)})
        _assert_parity(copied)
        assert calculation_head_digest(copied) != calculation_head_digest(saved_head)


def test_saved_schema_rebuild_preserves_complete_bytes(saved_head: CalculationRevision) -> None:
    expected = _original_bytes(saved_head)
    RegistrySnapshot.model_rebuild(force=True)
    _assert_parity(saved_head)
    assert _original_bytes(saved_head) == expected


def test_legacy_hydrated_rendering_keeps_omitted_directory(saved_head: CalculationRevision) -> None:
    rendering = saved_head.rendering_snapshot
    assert rendering is not None
    payload = rendering.model_dump(mode="json")
    del payload["revision_directory_ids"]
    payload["rendering_digest"] = content_hash_hex(
        {"registry": payload["registry_snapshot"], "labels": payload["labels"]}
    )
    loaded = CalculationRenderingSnapshot.model_validate_json(canonical_json_bytes(payload))
    assert loaded.revision_directory_ids is None
    _assert_parity(saved_head.model_copy(update={"rendering_snapshot": loaded}))


def test_tampered_saved_rendering_still_refused_before_hashing(saved_head: CalculationRevision) -> None:
    rendering = saved_head.rendering_snapshot
    assert rendering is not None
    payload = rendering.model_dump(mode="json")
    payload["registry_digest"] = "0" * 64
    with pytest.raises(ValidationError):
        CalculationRenderingSnapshot.model_validate_json(canonical_json_bytes(payload))


def _sample(action: Callable[[], str]) -> tuple[str, float, float]:
    wall, cpu = time.perf_counter(), time.process_time()
    result = action()
    return result, time.perf_counter() - wall, time.process_time() - cpu


def _fresh_snapshot_head(head: CalculationRevision) -> CalculationRevision:
    """``head`` under another live object holding an equal registry snapshot."""
    rendering = head.rendering_snapshot
    assert rendering is not None
    copied = rendering.registry_snapshot.model_copy(deep=True)
    assert copied is not rendering.registry_snapshot
    return head.model_copy(update={"rendering_snapshot": rendering.model_copy(update={"registry_snapshot": copied})})


def test_the_registry_fragment_is_encoded_once_per_live_snapshot(saved_head: CalculationRevision) -> None:
    # Observe real calls without replacing the serializers or payload owner.
    head = _fresh_snapshot_head(saved_head)
    other = _fresh_snapshot_head(saved_head)
    encodings = {CanonicalJsonValue.__init__.__code__: 0}

    def observe(frame: FrameType, event: str, arg: object) -> None:
        if event == "call" and frame.f_code in encodings:
            encodings[frame.f_code] += 1

    previous = sys.getprofile()
    sys.setprofile(observe)
    try:
        first = calculation_head_digest(head)
        second = calculation_head_digest(head)
        after_one = encodings[CanonicalJsonValue.__init__.__code__]
        third = calculation_head_digest(other)
    finally:
        sys.setprofile(previous)
    assert after_one == 1
    assert encodings[CanonicalJsonValue.__init__.__code__] == 2
    assert first == second == third == sha256_hex(_original_bytes(head))


def test_cold_digest_including_fragment_preparation_reduces_full_head_cost(saved_head: CalculationRevision) -> None:
    # Every candidate invocation constructs its token afresh. Alternating order
    # and medians avoid assigning all warmup or collection pauses to one route.
    baseline: list[tuple[str, float, float]] = []
    composed: list[tuple[str, float, float]] = []
    for trial in range(5):
        actions = (
            (baseline, lambda: sha256_hex(_original_bytes(saved_head))),
            (composed, lambda: calculation_head_digest(saved_head)),
        )
        for samples, action in actions if trial % 2 == 0 else reversed(actions):
            samples.append(_sample(action))
    assert {sample[0] for sample in (*baseline, *composed)} == {calculation_head_digest(saved_head)}
    old_wall, new_wall = median(sample[1] for sample in baseline), median(sample[1] for sample in composed)
    old_cpu, new_cpu = median(sample[2] for sample in baseline), median(sample[2] for sample in composed)
    print(f"cold head digest wall {old_wall:.3f}->{new_wall:.3f}s CPU {old_cpu:.3f}->{new_cpu:.3f}s")
    assert new_cpu < old_cpu * 0.85
