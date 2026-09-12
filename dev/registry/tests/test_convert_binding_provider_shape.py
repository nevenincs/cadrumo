"""Behaviour of the authored-binding provider-shape converter.

Every case builds an isolated temporary registry tree seeded from one small
authored modelo, so the contributor's working tree is never mutated and the
detector teeth (a refused row, a dry run) are proven on real files rather than
on a patched module.
"""

from __future__ import annotations

import shutil
import tomllib
from pathlib import Path
from typing import Any

import pytest

from cadrumo.domain.calculations.registry.binding_value_contract import (
    CHANNEL_FOR_BINDING_DATA_TYPE,
    BindingDataType,
    BindingValueContract,
)
from cadrumo.domain.calculations.registry.schema import BindingDefinition
from cadrumo.domain.calculations.registry.schema_base import CasillaDataType

from ..convert_binding_provider_shape import (
    BINDING_DATA_TYPE_FOR_CASILLA_DATA_TYPE,
    REGISTRY_MODELOS_ROOT,
    CasillaTypeEvidence,
    ConsumerIndex,
    ConversionRefusalError,
    ConversionReport,
    _as_tuples,
    convert_modelo,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


SEED_MODELO = "151"
REVISION = "2025-y-siguientes"


def _seed_tree(tmp_path: Path) -> Path:
    """Copy one small authored modelo into an isolated registry root."""
    modelos_root = tmp_path / "modelos"
    modelos_root.mkdir()
    shutil.copytree(REGISTRY_MODELOS_ROOT / SEED_MODELO, modelos_root / SEED_MODELO)
    return modelos_root


def _bindings_file(modelos_root: Path) -> Path:
    directory = modelos_root / SEED_MODELO / "revisions" / REVISION / "bindings"
    return next(iter(sorted(directory.glob("*.toml"))))


def _casillas_file(modelos_root: Path) -> Path:
    directory = modelos_root / SEED_MODELO / "revisions" / REVISION / "casillas"
    return next(iter(sorted(directory.glob("*.toml"))))


def _write_rows(path: Path, rows: str) -> None:
    """Replace a fragment's binding rows, keeping the revision table header."""
    path.write_text(rows, encoding="utf-8")


def _run(modelos_root: Path, *, apply: bool = True) -> ConversionReport:
    report = ConversionReport()
    convert_modelo(
        SEED_MODELO,
        report,
        {
            "100": {"1391": CasillaTypeEvidence(declared=frozenset({"money"}), casilla_ids=frozenset({"1391"}))},
            SEED_MODELO: {},
        },
        apply=apply,
        modelos_root=modelos_root,
    )
    return report


def _converted_rows(path: Path) -> list[dict[str, Any]]:
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    return list(data["revisions"][REVISION]["bindings"])


def _first_provider(path: Path) -> dict[str, Any]:
    provider = _converted_rows(path)[0]["provider"]
    assert isinstance(provider, dict)
    return provider


def _row(fields: str) -> str:
    return f'[[revisions."{REVISION}".bindings]]\n{fields}\n'


SEEDED_CONSUMED_BINDING = "modelo-151-impatriado-base-liquidable-general"
"""The binding id the seeded revision's casilla already names, declared ``money``."""

BASE_TAIL = 'legal_refs = ["ley-35-2006:art-93"]\nsource_refs = ["aeat-modelo-151-procedure"]\n'


def _legacy_row() -> str:
    """Return one legacy-shaped row the seeded revision's casilla already consumes."""
    return _row(
        f'id = "{SEEDED_CONSUMED_BINDING}"\n'
        'source = "ledger_impatriado_income_aggregation"\n'
        'selector = { modelo = "151", target_casilla_id = "impatriado.base-liquidable-general", '
        'fact = "ingresos_integros_sum" }\n'
        'aggregation = { op = "sum" }\n' + BASE_TAIL
    )


def test_previous_filing_legacy_year_delta_folds_into_a_temporal_member(tmp_path: Path) -> None:
    """The six loose previous-filing period fields become one temporal member."""
    modelos_root = _seed_tree(tmp_path)
    path = _bindings_file(modelos_root)
    _write_rows(
        path,
        _row(
            'id = "m151-prev"\n'
            'source = "previous_filing"\n'
            'selector = { source_modelo = "100", source_casilla_id = "1391", '
            'filing_year_delta = -1, source_periods = ["0A"] }\n'
            'aggregation = { op = "copy" }\n' + BASE_TAIL
        ),
    )

    report = _run(modelos_root)

    assert report.refusals == []
    assert report.value_rule_counts["consumer_source_casilla"] == 1
    provider = _first_provider(path)
    assert provider["kind"] == "previous_filing"
    assert provider["temporal"] == {"kind": "filing_year_offset", "years": -1, "source_periods": ["0A"]}
    assert "filing_year_delta" not in provider
    assert "source_periods" not in provider


def test_inventory_absolute_filing_year_becomes_same_target_context(tmp_path: Path) -> None:
    """The inventory selector's absolute year is replaced by a relative member."""
    modelos_root = _seed_tree(tmp_path)
    path = _bindings_file(modelos_root)
    _write_rows(
        path,
        _row(
            f'id = "{SEEDED_CONSUMED_BINDING}"\n'
            'source = "inventory"\n'
            'selector = { modelo = "100", filing_year = 2025, projection_grain = "taxpayer_year_activity", '
            'fact = "row_field", record = "inventory_activity", grouping = "per_inventory_activity", '
            'row_field = "closing_minus_opening_positive", target_casilla_id = "0177" }\n' + BASE_TAIL
        ),
    )

    report = _run(modelos_root)

    assert report.refusals == []
    provider = _first_provider(path)
    assert provider["temporal"] == {"kind": "same_target_context"}
    assert "filing_year" not in provider


def test_rows_aggregation_carries_the_element_type_on_the_row_set_channel(tmp_path: Path) -> None:
    """A rows-op row converts to the row_set channel keeping its per-row element type."""
    modelos_root = _seed_tree(tmp_path)
    path = _bindings_file(modelos_root)
    _write_rows(
        path,
        _row(
            'id = "m151-rows"\n'
            'source = "withholding"\n'
            'selector = { fact = "row_field", row_field = "perceptor_tax_id", '
            'grouping = "per_perceptor_clave", record = "perceptor", data_type = "text" }\n'
            'aggregation = { op = "rows" }\n' + BASE_TAIL
        ),
    )

    report = _run(modelos_root)

    assert report.refusals == []
    assert report.value_rule_counts["rows_aggregation:selector_data_type"] == 1
    value = _converted_rows(path)[0]["value"]
    assert value == {"data_type": "text", "channel": "row_set", "row_grouping": "withholding"}


def test_a_provider_native_rows_row_converts_without_a_grouping(tmp_path: Path) -> None:
    """A row-producing source outside the grouped row-assembly axis declares no grouping, never an invented one."""
    modelos_root = _seed_tree(tmp_path)
    path = _bindings_file(modelos_root)
    _write_rows(
        path,
        _row(
            'id = "m151-invoice-rows"\n'
            'source = "payable_invoice"\n'
            'selector = { fact = "row_field", row_field = "party_tax_id" }\n'
            'aggregation = { op = "rows" }\n' + BASE_TAIL
        ),
    )

    report = _run(modelos_root)

    assert report.refusals == []
    assert _converted_rows(path)[0]["value"] == {"data_type": "text", "channel": "row_set"}


def test_typed_enum_row_moves_into_the_value_contract(tmp_path: Path) -> None:
    """A top-level typed_enum becomes the value contract's enum bridge and leaves the row."""
    modelos_root = _seed_tree(tmp_path)
    path = _bindings_file(modelos_root)
    _write_rows(
        path,
        _row(
            'id = "m151-enum"\n'
            'source = "profile"\n'
            'selector = { profile_key = "taxpayer.ccaa" }\n'
            'typed_enum = "CCAA"\n' + BASE_TAIL
        ),
    )

    report = _run(modelos_root)

    assert report.refusals == []
    converted = _converted_rows(path)[0]
    assert converted["value"] == {"data_type": "enum", "channel": "enum", "typed_enum": "CCAA"}
    assert "typed_enum" not in converted


def test_a_row_with_no_derivable_value_is_refused_and_its_file_untouched(tmp_path: Path) -> None:
    """An undecidable value contract refuses the row and leaves the whole fragment legacy-shaped."""
    modelos_root = _seed_tree(tmp_path)
    path = _bindings_file(modelos_root)
    _casillas_file(modelos_root).write_text("", encoding="utf-8")
    original = (
        _row(
            'id = "m151-undecidable"\n'
            'source = "ledger_irnr_income_aggregation"\n'
            'selector = { modelo = "151", target_casilla_id = "nowhere", fact = "gross_income_sum" }\n'
            'aggregation = { op = "sum" }\n' + BASE_TAIL
        )
        + "\n"
        + _row(
            'id = "m151-decidable"\n'
            'source = "manual_input"\n'
            'selector = { record = "type_1", field = "x", offset = 1, length = 2, data_type = "money" }\n' + BASE_TAIL
        )
    )
    _write_rows(path, original)

    report = _run(modelos_root)

    assert [refusal["binding_id"] for refusal in report.refusals] == ["m151-undecidable"]
    assert path.read_text(encoding="utf-8") == original
    assert str(path) in report.files_skipped
    assert str(path) not in report.files_rewritten


def test_dry_run_writes_nothing(tmp_path: Path) -> None:
    """A dry run reports the conversion it would make and leaves every file byte-identical."""
    modelos_root = _seed_tree(tmp_path)
    _write_rows(_bindings_file(modelos_root), _legacy_row())
    before = {path: path.read_bytes() for path in modelos_root.rglob("*.toml")}

    report = _run(modelos_root, apply=False)

    assert report.rows_converted > 0
    assert report.refusals == []
    assert {path: path.read_bytes() for path in modelos_root.rglob("*.toml")} == before


def test_every_converted_row_validates_as_a_binding_definition(tmp_path: Path) -> None:
    """A converted row round-trips through the schema the loader enforces."""
    modelos_root = _seed_tree(tmp_path)
    _write_rows(_bindings_file(modelos_root), _legacy_row())

    report = _run(modelos_root)

    assert report.rows_converted >= 1

    for path in (modelos_root / SEED_MODELO).rglob("bindings/*.toml"):
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        for revision_table in data["revisions"].values():
            for row in revision_table.get("bindings", []):
                assert "source" not in row
                assert "selector" not in row
                BindingDefinition.model_validate(_as_tuples(row))


def test_consumers_that_disagree_on_a_data_type_refuse_the_row() -> None:
    """Two consuming casillas naming different data types are a contradiction, not a choice."""
    evidence = CasillaTypeEvidence(
        declared=frozenset({"money", "integer"}),
        casilla_ids=frozenset({"01", "02"}),
    )
    index = ConsumerIndex(revision_casilla={"m151-contested": evidence})

    with pytest.raises(ConversionRefusalError) as refused:
        index.lookup("m151-contested")

    assert refused.value.binding_id == "m151-contested"
    assert "disagree" in refused.value.reason
    assert "integer" in refused.value.reason
    assert "money" in refused.value.reason
    assert "01" in refused.value.reason


def test_a_consumer_that_omits_its_data_type_refuses_the_row() -> None:
    """An omitted casilla data type is unknown, never money by default."""
    index = ConsumerIndex(
        revision_casilla={
            "m151-untyped": CasillaTypeEvidence(omitted_by=frozenset({"07"}), casilla_ids=frozenset({"07"})),
        },
    )

    with pytest.raises(ConversionRefusalError) as refused:
        index.lookup("m151-untyped")

    assert refused.value.reason == "consuming casilla 07 declares no data_type"


def test_one_agreeing_consumer_resolves_its_declared_data_type() -> None:
    """Consumers that agree still resolve to the single type they declare."""
    index = ConsumerIndex(
        modelo_casilla={
            "m151-agreed": CasillaTypeEvidence(declared=frozenset({"text"}), casilla_ids=frozenset({"03", "04"})),
        },
    )

    assert index.lookup("m151-agreed") == ("consumer_modelo_casilla", "text")
    assert index.lookup("m151-absent") is None


def test_a_decimal_casilla_maps_to_the_non_monetary_decimal_data_type() -> None:
    """A casilla that declares a non-monetary decimal is not carried as money."""
    mapped = BINDING_DATA_TYPE_FOR_CASILLA_DATA_TYPE[CasillaDataType.DECIMAL.value]

    assert mapped is BindingDataType.DECIMAL
    assert mapped is not BindingDataType.MONEY


def test_every_mapped_binding_data_type_builds_a_legal_value_contract() -> None:
    """The converter can only emit pairings the schema accepts."""
    for casilla_data_type, binding_data_type in BINDING_DATA_TYPE_FOR_CASILLA_DATA_TYPE.items():
        assert casilla_data_type in {member.value for member in CasillaDataType}
        contract = BindingValueContract(
            data_type=binding_data_type,
            channel=CHANNEL_FOR_BINDING_DATA_TYPE[binding_data_type],
        )
        assert contract.data_type is binding_data_type
