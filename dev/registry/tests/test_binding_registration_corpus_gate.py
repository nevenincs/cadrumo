"""Corpus-wide gate: every authored binding satisfies its provider registration.

The focused registration tests prove the rules on constructed rows. This gate
proves the *corpus* obeys them: every authored binding in every modelo
directory is constructed as a real ``BindingDefinition`` and validated by the
real :func:`validate_binding_against_registration`, with zero diagnostics
admitted. It is the build-time equivalent of what the authority publish refuses,
run directly off the authoring tree so a regression is attributed to the row
that caused it rather than to a publish failure hundreds of rows later.

The gate carries its own teeth: a representative defect of each rule the gate
protects is shown to be detected, on rows built in memory, so the normal path
and the defect proof pass in the same run and the contributor's tree is never
mutated.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

import pytest

from cadrumo.core.aggregation import ROW_SET_GROUPING_FOR_BINDING_SOURCE, BindingAggregation, BindingAggregationOp
from cadrumo.domain.calculations.registry.binding_provider_registration import (
    validate_binding_against_registration,
)
from cadrumo.domain.calculations.registry.binding_terminal_origin import (
    TerminalOriginClass,
    TerminalOriginExpectation,
)
from cadrumo.domain.calculations.registry.schema import BindingDefinition
from cadrumo.domain.calculations.registry.withholding_bindings import WithholdingProvider

from ..convert_binding_provider_shape import REGISTRY_MODELOS_ROOT, _as_tuples

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _modelo_dirs() -> list[Path]:
    return sorted(p for p in REGISTRY_MODELOS_ROOT.iterdir() if p.is_dir() and (p / "revisions").is_dir())


def _authored_rows(modelo_dir: Path) -> list[tuple[Path, dict[str, Any]]]:
    """Return every authored binding row of one modelo with the file it came from."""
    rows: list[tuple[Path, dict[str, Any]]] = []
    for toml_path in sorted(modelo_dir.glob("revisions/*/bindings/*.toml")):
        document = tomllib.loads(toml_path.read_text(encoding="utf-8"))
        for table in (document.get("revisions") or {}).values():
            if not isinstance(table, dict):
                continue
            for row in table.get("bindings") or []:
                if isinstance(row, dict):
                    rows.append((toml_path, row))
    return rows


@pytest.mark.parametrize("modelo_dir", _modelo_dirs(), ids=lambda path: path.name)
def test_every_authored_binding_satisfies_its_provider_registration(modelo_dir: Path) -> None:
    """Zero registration diagnostics across the modelo's whole authored binding corpus."""
    failures: list[str] = []
    checked = 0
    for toml_path, row in _authored_rows(modelo_dir):
        location = f"{toml_path.relative_to(REGISTRY_MODELOS_ROOT)}::{row.get('id', '?')}"
        try:
            binding = BindingDefinition.model_validate(_as_tuples(row))
        except Exception as exc:
            failures.append(f"{location}: does not construct: {exc}")
            continue
        checked += 1
        failures.extend(f"{location}: {diagnostic}" for diagnostic in validate_binding_against_registration(binding))

    del checked  # a modelo may legitimately author no binding of its own and inherit instead
    assert failures == [], "\n".join(failures)


def test_the_corpus_gate_is_not_vacuous() -> None:
    """A gate that enumerated nothing would pass silently; prove it sees the corpus.

    The floors are deliberately loose. They exist to catch an enumeration that
    breaks (a moved root, a changed glob), not to freeze a corpus count -- a
    count asserted exactly would fail on every honest authoring change.
    """
    modelo_dirs = _modelo_dirs()
    total_rows = sum(len(_authored_rows(modelo_dir)) for modelo_dir in modelo_dirs)
    modelos_with_rows = sum(1 for modelo_dir in modelo_dirs if _authored_rows(modelo_dir))

    assert len(modelo_dirs) >= 50
    assert modelos_with_rows >= 20
    assert total_rows >= 1000


def _withholding_row(**value_overrides: object) -> dict[str, Any]:
    """Return a well-formed grouped row-family binding, before any override."""
    value: dict[str, object] = {"data_type": "text", "channel": "row_set", "row_grouping": "withholding"}
    value.update(value_overrides)
    return {
        "id": "gate.teeth",
        "provider": WithholdingProvider(
            fact="row_field",
            row_field="perceptor_tax_id",
            grouping="per_perceptor_clave",
            record="perceptor",
            data_type="text",
        ),
        "value": value,
        "aggregation": BindingAggregation(op=BindingAggregationOp.ROWS),
        "legal_refs": ("ley-35-2006:art-99",),
        "source_refs": ("aeat-modelo-190-procedure",),
    }


def test_the_gate_detects_a_grouped_family_missing_its_grouping() -> None:
    """Teeth: dropping the grouping of a grouped family is caught, not tolerated."""
    row = _withholding_row()
    del row["value"]["row_grouping"]  # type: ignore[index]

    diagnostics = validate_binding_against_registration(BindingDefinition.model_validate(row))

    assert any("must declare row grouping 'withholding'" in diagnostic for diagnostic in diagnostics)


def test_the_gate_detects_a_rows_operation_off_the_row_set_channel() -> None:
    """Teeth: the conflation this contract retired is caught if it reappears."""
    row = _withholding_row(channel="text", row_grouping=None)
    row["value"].pop("row_grouping")  # type: ignore[union-attr]

    diagnostics = validate_binding_against_registration(BindingDefinition.model_validate(row))

    assert any("requires the 'row_set' value channel" in diagnostic for diagnostic in diagnostics)


def test_the_gate_detects_a_row_set_resting_on_an_exactly_one_terminal_origin() -> None:
    """Teeth: an empty row family must stay distinguishable from a missing one."""
    row = _withholding_row()
    row["terminal_origins"] = (
        TerminalOriginExpectation(
            source_class=TerminalOriginClass.PERCEPTOR_OBSERVATION,
            role="primary",
            cardinality="exactly_one",
            fingerprint="optional",
        ),
    )

    with pytest.raises(Exception, match="cannot rest on an exactly_one terminal origin"):
        BindingDefinition.model_validate(row)


def test_every_grouped_corpus_row_declares_its_canonical_grouping() -> None:
    """Corpus-wide: a grouped family's rows all name the one grouping its assembler dispatches on."""
    mismatches: list[str] = []
    for modelo_dir in _modelo_dirs():
        for toml_path, row in _authored_rows(modelo_dir):
            value = row.get("value")
            if not isinstance(value, dict) or value.get("channel") != "row_set":
                continue
            binding = BindingDefinition.model_validate(_as_tuples(row))
            expected = ROW_SET_GROUPING_FOR_BINDING_SOURCE.get(binding.source)
            declared = binding.value.row_grouping
            if (expected.value if expected else None) != (declared.value if declared else None):
                mismatches.append(f"{toml_path.name}::{row.get('id')}: {declared} != {expected}")
    assert mismatches == []
