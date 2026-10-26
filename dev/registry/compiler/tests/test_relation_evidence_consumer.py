"""A factual-evidence relation binding is a typed consumer only where a declared period reads it.

From its 2025 edition Modelo 193 sums its declarant totals from the type 2
perceptor records (aeat-dr-193-2025, positions 145-189), and the two Modelo 123
relations stay declared as a reconciliation cross-check: relation prefill
resolves them for the annual period and carries them as evidence, but no casilla,
formula or export reads them. The census must count that read, and must not
count a relation whose role puts it in the arithmetic or whose applicability no
declared period admits.

Every case runs the real loader over an isolated copy of the live modelo, or an
in-memory copy of its compiled revision; nothing in the working tree changes.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from cadrumo.domain.calculations.registry.binding_targets import BindingConsumerKind, binding_consumers
from cadrumo.domain.calculations.registry.binding_temporal import TargetPeriods

from ..loader import load_modelo_directory
from ..validate_bindings import unreferenced_binding_advisories

if TYPE_CHECKING:
    from cadrumo.domain.calculations.registry.schema import ModeloRevision

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_MODELOS_ROOT = Path(__file__).resolve().parents[4] / "src" / "cadrumo" / "_data" / "registry" / "aeat" / "modelos"
_REVISION = "2025-y-siguientes"
_EVIDENCE_BINDINGS = ("modelo-193-123-base-anual", "modelo-193-123-retenciones-anual")
_BASE_OVERRIDE = (
    'selector = {revision = "2024", id = "modelo-193-123-base-anual"}\n'
    "# A reconciliation cross-check against the quarterly modelo 123, no longer the\n"
    "# source of decl.base-total.\n"
    'fields = {provider = {relation_kind = "cross_model_output", dependency_role = "factual_evidence"}}\n'
)


def _revision(tmp_path: Path, *, base_override: str | None = None) -> ModeloRevision:
    tree = tmp_path / "193"
    shutil.copytree(_MODELOS_ROOT / "193", tree)
    if base_override is not None:
        path = tree / "revisions" / _REVISION / "revision.toml"
        text = path.read_text(encoding="utf-8")
        assert text.count(_BASE_OVERRIDE) == 1
        path.write_text(text.replace(_BASE_OVERRIDE, base_override), encoding="utf-8")
    return load_modelo_directory(tree).revisions[_REVISION]


def _evidence_kinds(revision: ModeloRevision, binding_id: str) -> list[BindingConsumerKind]:
    return [
        ref.kind for ref in binding_consumers(revision)[binding_id] if ref.kind is BindingConsumerKind.RELATION_EVIDENCE
    ]


def _advised(revision: ModeloRevision) -> str:
    return "\n".join(unreferenced_binding_advisories(prefix="modelo 193", revision=revision))


def test_the_annual_cross_check_relations_are_counted_as_evidence_consumers(tmp_path: Path) -> None:
    revision = _revision(tmp_path)
    consumers = binding_consumers(revision)

    for binding_id in _EVIDENCE_BINDINGS:
        evidence = [ref for ref in consumers[binding_id] if ref.kind is BindingConsumerKind.RELATION_EVIDENCE]
        assert [ref.owner for ref in evidence] == ["modelo-193-dep-123"], consumers[binding_id]
        assert binding_id not in _advised(revision)


def test_a_relation_that_enters_the_arithmetic_is_not_evidence(tmp_path: Path) -> None:
    """TEETH: the same binding declared as a direct calculation input, with no casilla reading it, stays an orphan."""
    revision = _revision(
        tmp_path,
        base_override=_BASE_OVERRIDE.replace(
            'dependency_role = "factual_evidence"', 'dependency_role = "direct_calculation"'
        ),
    )

    assert _evidence_kinds(revision, "modelo-193-123-base-anual") == []
    assert "modelo-193-123-base-anual" in _advised(revision)
    assert _evidence_kinds(revision, "modelo-193-123-retenciones-anual") == [BindingConsumerKind.RELATION_EVIDENCE]


def test_evidence_no_declared_period_selects_is_never_read(tmp_path: Path) -> None:
    """TEETH: applicability outside every declared period means relation prefill never resolves it."""
    revision = _revision(tmp_path)
    assert "1T" not in revision.period_selector.declared_periods
    unread = revision.model_copy(
        update={
            "bindings": tuple(
                binding.model_copy(update={"applicability": TargetPeriods(periods=("1T",))})
                if binding.id == "modelo-193-123-base-anual"
                else binding
                for binding in revision.bindings
            ),
        },
    )

    assert _evidence_kinds(unread, "modelo-193-123-base-anual") == []
    assert "modelo-193-123-base-anual" in _advised(unread)
