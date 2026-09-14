"""Corpus-wide gate: every authored binding satisfies its provider registration.

The focused registration tests prove the rules on constructed rows. This gate
proves the *corpus* obeys them: every binding of every modelo directory is
validated by the real :func:`validate_binding_against_registration`, with zero
diagnostics admitted. It is the build-time equivalent of what the authority
publish refuses, run one modelo at a time so a regression is attributed to the
modelo that caused it rather than to a publish failure hundreds of rows later.

The bindings are read the way the registry itself types them: each modelo is
loaded through :func:`load_modelo_directory` and the gate walks the revisions'
``bindings``. That matters for grounding. An authored row is permitted to state
no ``source_refs`` of its own and take its edition's ``binding_source_refs``
default, so a row lifted straight out of the TOML is not yet a binding -- the
default fill happens during materialisation, before typed construction. Typing
raw rows here would refuse exactly the rows the registry accepts, and would
check a shape the registry never runs.

The gate carries its own teeth: a representative defect of each rule the gate
protects is shown to be detected, on rows built in memory, so the normal path
and the defect proof pass in the same run and the contributor's tree is never
mutated.
"""

from __future__ import annotations

from functools import cache
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
from cadrumo.domain.calculations.registry.binding_value_contract import BindingValueChannel
from cadrumo.domain.calculations.registry.manual_input_selector import ManualInputProvider
from cadrumo.domain.calculations.registry.schema import BindingDefinition
from cadrumo.domain.calculations.registry.schema_base import CasillaDataType
from cadrumo.domain.calculations.registry.withholding_bindings import WithholdingProvider

from ..compiler.loader import load_modelo_directory
from ..convert_binding_provider_shape import REGISTRY_MODELOS_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _modelo_dirs() -> list[Path]:
    return sorted(p for p in REGISTRY_MODELOS_ROOT.iterdir() if p.is_dir() and (p / "revisions").is_dir())


@cache
def _materialised_bindings(modelo_dir: Path) -> tuple[tuple[str, BindingDefinition], ...]:
    """Return every binding of one modelo, typed as the registry types it.

    The modelo is loaded through the real loader, so each binding arrives with
    its edition defaults already filled and its provider and value contracts
    already constructed. Each is paired with a ``modelo/revision::id`` locator
    so a diagnostic names the row it belongs to.
    """
    definition = load_modelo_directory(modelo_dir)
    return tuple(
        (f"{modelo_dir.name}/{revision_id}::{binding.id}", binding)
        for revision_id, revision in definition.revisions.items()
        for binding in revision.bindings
    )


@pytest.mark.parametrize("modelo_dir", _modelo_dirs(), ids=lambda path: path.name)
def test_every_authored_binding_satisfies_its_provider_registration(modelo_dir: Path) -> None:
    """Zero registration diagnostics across the modelo's whole binding corpus."""
    failures: list[str] = []
    for location, binding in _materialised_bindings(modelo_dir):
        failures.extend(f"{location}: {diagnostic}" for diagnostic in validate_binding_against_registration(binding))

    # a modelo may legitimately author no binding of its own and inherit instead
    assert failures == [], "\n".join(failures)


def test_the_corpus_gate_is_not_vacuous() -> None:
    """A gate that enumerated nothing would pass silently; prove it sees the corpus.

    The floors are deliberately loose. They exist to catch an enumeration that
    breaks (a moved root, a changed glob), not to freeze a corpus count -- a
    count asserted exactly would fail on every honest authoring change.
    """
    modelo_dirs = _modelo_dirs()
    total_rows = sum(len(_materialised_bindings(modelo_dir)) for modelo_dir in modelo_dirs)
    modelos_with_rows = sum(1 for modelo_dir in modelo_dirs if _materialised_bindings(modelo_dir))

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
            data_type=CasillaDataType.TEXT,
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


def test_the_gate_detects_a_row_set_channel_with_no_authored_aggregation() -> None:
    """Teeth: omitting the ``aggregation`` block is not a way out of the rows agreement.

    ``withholding`` is the sharpest case: it is the one row-capable family the
    default table deliberately excludes from the ``rows`` default, so a row set
    authored without an aggregation block takes ``sum`` and every row assembler
    passes it over -- the casilla resolves to no rows rather than to a refusal.
    """
    row = _withholding_row()
    del row["aggregation"]

    diagnostics = validate_binding_against_registration(BindingDefinition.model_validate(row))

    assert any(
        "the 'row_set' value channel requires the 'rows' aggregation operation, not 'sum'" in diagnostic
        for diagnostic in diagnostics
    )


def test_an_undeclared_aggregation_is_not_held_to_the_permitted_operation_set() -> None:
    """The family default is a rows marker, not an authored operation.

    ``manual_input`` permits ``copy`` alone while the default table answers
    ``sum`` for it, which is the shape most of the authored corpus carries.
    Reporting that would report the default table rather than the declaration,
    so the permitted-operation check stays on the authored block.
    """
    row = {
        "id": "gate.teeth.manual",
        "provider": ManualInputProvider(casilla_id="renta.0100", data_type=CasillaDataType.DECIMAL),
        "value": {"data_type": "money", "channel": "decimal"},
        "legal_refs": ("ley-35-2006:art-99",),
        "source_refs": ("aeat-modelo-190-procedure",),
    }

    assert validate_binding_against_registration(BindingDefinition.model_validate(row)) == ()


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
        for location, binding in _materialised_bindings(modelo_dir):
            if binding.value.channel != BindingValueChannel.ROW_SET:
                continue
            expected = ROW_SET_GROUPING_FOR_BINDING_SOURCE.get(binding.source)
            declared = binding.value.row_grouping
            if (expected.value if expected else None) != (declared.value if declared else None):
                mismatches.append(f"{location}: {declared} != {expected}")
    assert mismatches == []
