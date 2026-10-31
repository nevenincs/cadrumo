"""Per-modelo scope memoisation never answers a changed modelo, and refusals are kept per receipt.

Registry-scope checks fold one pure per-modelo projection over a tree, and the
projection of an unchanged modelo object is reused. These tests prove the reuse
is keyed to the object itself: a modelo whose content changes is necessarily a
new frozen object, and it is projected afresh through the real checks. They
also prove a registry compile refusal is replayed only for the identical
compilation receipt.
"""

from __future__ import annotations

import gc
from collections.abc import Callable
from datetime import date
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.schema import ModeloDefinition, ModeloRevision
from cadrumo.domain.calculations.registry.schema_references import PeriodSelector
from cadrumo.domain.calculations.registry.schema_surfaces import CasillaDefinition

from ..authority_state import authoring_root_pair, cached_compilation
from ..registry_scope import validate_registry_scope
from ..validate_cross_revision import (
    cross_revision_casilla_consistency_failures,
    strict_cross_revision_casilla_continuity_failures,
)
from ..validation_memoization import ModeloIdentityMemo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _casilla(*, data_type: str) -> CasillaDefinition:
    return CasillaDefinition.model_validate(
        {
            "id": "0001",
            "number": "0001",
            "localization_keys": ("test.registry.casilla.label",),
            "section": ("test",),
            "data_type": data_type,
            "semantic_role": "test_value",
            "legal_refs": ("ley-58-2003:art-29",),
            "source_refs": ("aeat-manual",),
            "continuidad_id": "test-value",
        },
    )


def _revision(revision_id: str, *, valid_from: date, valid_to: date | None, data_type: str) -> ModeloRevision:
    return ModeloRevision.model_validate(
        {
            "id": revision_id,
            "localization_key": f"test.registry.revision.{revision_id}.label",
            "valid_from": valid_from,
            "valid_to": valid_to,
            "period_selector": PeriodSelector(years=(2025,), periods=("alta",)),
            "legal_refs": ("ley-58-2003:art-29",),
            "source_refs": ("aeat-manual",),
            "casillas": (_casilla(data_type=data_type),),
            "continuidad_validation": "strict",
        },
    )


def _overlapping_modelo(*, right_data_type: str) -> ModeloDefinition:
    left = _revision("variant-a", valid_from=date(2025, 1, 1), valid_to=date(2025, 12, 31), data_type="money")
    right = _revision("variant-b", valid_from=date(2025, 2, 3), valid_to=None, data_type=right_data_type)
    return ModeloDefinition.model_validate(
        {
            "id": "036",
            "title_localization_key": "test.registry.modelo.title",
            "official_name_localization_key": "test.registry.modelo.official_name",
            "tax_domain": "censo",
            "cadence": "event",
            "jurisdiction": "ES-AEAT",
            "legal_refs": ("ley-58-2003:art-29",),
            "source_refs": ("aeat-manual",),
            "revisions": {left.id: left, right.id: right},
        },
    )


def _with_right_data_type(modelo: ModeloDefinition, data_type: str) -> ModeloDefinition:
    """Change one casilla the only way a frozen registry model changes: a new copy."""
    right = modelo.revisions["variant-b"]
    changed = right.model_copy(update={"casillas": (_casilla(data_type=data_type),)})
    return modelo.model_copy(update={"revisions": {**modelo.revisions, "variant-b": changed}})


def test_memo_reuses_one_object_and_recomputes_a_changed_copy() -> None:
    memo: ModeloIdentityMemo[str] = ModeloIdentityMemo()
    computed: list[str] = []

    def project(modelo: ModeloDefinition) -> str:
        value = str(modelo.revisions["variant-b"].casillas[0].data_type)
        computed.append(value)
        return value

    original = _overlapping_modelo(right_data_type="money")
    assert memo.get_or_compute(original, project) == "money"
    assert memo.get_or_compute(original, project) == "money"
    assert computed == ["money"]

    changed = _with_right_data_type(original, "decimal")
    assert changed == _with_right_data_type(original, "decimal")
    assert memo.get_or_compute(changed, project) == "decimal"
    assert computed == ["money", "decimal"]


def test_memo_never_keeps_a_modelo_alive() -> None:
    memo: ModeloIdentityMemo[int] = ModeloIdentityMemo()
    modelo = _overlapping_modelo(right_data_type="money")
    memo.get_or_compute(modelo, lambda _modelo: 1)
    assert len(memo) == 1

    del modelo
    gc.collect()

    assert len(memo) == 0


def test_real_checks_see_a_drift_introduced_after_the_clean_modelo_was_memoised() -> None:
    """The staleness proof: a mutated input reaches the real checks, never the stale verdict."""
    clean = _overlapping_modelo(right_data_type="money")
    assert cross_revision_casilla_consistency_failures((clean,)) == ()
    assert strict_cross_revision_casilla_continuity_failures((clean,)) == ()
    clean_scope = validate_registry_scope((clean,))

    drifted = _with_right_data_type(clean, "decimal")
    consistency = cross_revision_casilla_consistency_failures((drifted,))
    assert len(consistency) == 1
    assert "data_type" in consistency[0]
    assert validate_registry_scope((drifted,)) != clean_scope

    # The clean object still answers clean; its memoised verdict did not absorb the drift.
    assert cross_revision_casilla_consistency_failures((clean,)) == ()
    assert validate_registry_scope((clean,)) == clean_scope


def test_a_fold_over_a_repeated_modelo_groups_exactly_like_one_pass() -> None:
    """Replaying memoised per-modelo divergences keeps the tree-wide grouping of one pass.

    One pass appends both occurrences' divergences under the same grouping key,
    so a repeated modelo yields one failure, not two.
    """
    drifted = _overlapping_modelo(right_data_type="decimal")
    single = cross_revision_casilla_consistency_failures((drifted,))
    assert len(single) == 1

    twice = cross_revision_casilla_consistency_failures((drifted, drifted.model_copy()))
    # modelo_by_id keeps the last object for a repeated id, exactly as before.
    assert twice == single


def test_a_compile_refusal_is_replayed_only_for_its_identical_receipt(tmp_path: Path) -> None:
    registry_root = tmp_path / "registry"
    source_root = tmp_path / "sources"
    registry_root.mkdir()
    source_root.mkdir()
    pair = authoring_root_pair(registry_root, source_root)
    builds: list[str] = []

    def refuse(reason: str) -> Callable[[], ValidatedRegistryAuthority]:
        def build() -> ValidatedRegistryAuthority:
            builds.append(reason)
            raise RegistryValidationError(f"refused: {reason}")

        return build

    receipt = {"source_receipt": "s", "compiler_source_tree_digest": "c"}
    with pytest.raises(RegistryValidationError, match="refused: first") as first:
        cached_compilation(pair, registry_identity_digest="a", **receipt, build=refuse("first"))
    with pytest.raises(RegistryValidationError, match="refused: first") as replayed:
        cached_compilation(pair, registry_identity_digest="a", **receipt, build=refuse("unused"))
    assert replayed.value is first.value
    assert builds == ["first"]

    with pytest.raises(RegistryValidationError, match="refused: changed"):
        cached_compilation(pair, registry_identity_digest="b", **receipt, build=refuse("changed"))
    assert builds == ["first", "changed"]


def test_a_non_registry_failure_is_never_replayed(tmp_path: Path) -> None:
    registry_root = tmp_path / "registry"
    source_root = tmp_path / "sources"
    registry_root.mkdir()
    source_root.mkdir()
    pair = authoring_root_pair(registry_root, source_root)
    calls: list[int] = []

    def transient() -> ValidatedRegistryAuthority:
        calls.append(1)
        raise OSError("transient")

    for _attempt in range(2):
        with pytest.raises(OSError, match="transient"):
            cached_compilation(
                pair,
                registry_identity_digest="a",
                source_receipt="s",
                compiler_source_tree_digest="c",
                build=transient,
            )
    assert len(calls) == 2
