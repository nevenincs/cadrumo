"""Modelo 131 DPA decimal selectors match the pinned official fixed-width design."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.binding_selector_utils import (
    BindingFixedExportSelector,
    binding_export_selector,
)
from dev.registry.compiler.loader import load_modelo_directory
from dev.registry.pipeline.semantic_map import load_semantic_map

from .authored_edition_support import authored_revisions, revision_covering, source_first_exercise, source_with_sha256

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_SOURCE_SHA256 = "83e40d7d4d64c3b2da570d5e70a650685de036277df3ce077b0569a2235aa06f"
_WORKBOOK_NAME = "06-131-ejercicios-2024-actualizado-13-12-24-180-kb-xlsx.xlsx"
_MAPPING_ROOT = Path(__file__).resolve().parents[1] / "mappings" / "modelo_131"
# The design epochs, oldest first, pair by position with the authored revisions; the
# late-quarters branch of the newest exercise is the last.
_DESIGN_EPOCHS = tuple(sorted(path.name for path in _MAPPING_ROOT.iterdir() if path.is_dir()))
_DECIMAL_COUNTS = (0, 26, 23, 23, 23)


def _source_decimal_positions() -> set[tuple[int, int]]:
    root = bundled_path("corpus", "aeat_official", "disenos_registro", "modelo_131", "files")
    workbook = root / _WORKBOOK_NAME
    assert hashlib.sha256(workbook.read_bytes()).hexdigest() == _SOURCE_SHA256
    text = (root / f"{_WORKBOOK_NAME}.extracted.md").read_text(encoding="utf-8")
    dpa = text.split("# DPA\n", 1)[1].split("# DID\n", 1)[0]
    return {
        (int(match.group(1)), int(match.group(2)))
        for line in dpa.splitlines()
        if "2 decimales" in line
        if (match := re.match(r"\d+ \| (\d+) \| (\d+) \| Num \|", line)) is not None
    }


def test_exact_official_decimal_rows_are_decimal_binding_selectors() -> None:
    positions = _source_decimal_positions()
    assert len(positions) == 26
    assert {(18, 4), (43, 4), (136, 10), (146, 17)} <= positions

    modelo = load_modelo_directory(bundled_path("registry", "aeat", "modelos", "131"))
    revision = modelo.revisions[
        str(revision_covering("131", source_first_exercise(source_with_sha256(_SOURCE_SHA256))).id)
    ]
    selected = []
    for binding in revision.bindings:
        selector = binding_export_selector(binding, revision=revision)
        if not isinstance(selector, BindingFixedExportSelector) or selector.record != "DPA":
            continue
        if (selector.offset, selector.length) not in positions:
            continue
        selected.append(binding)
        assert str(selector.data_type) == "decimal"
        assert selector.decimals == 2
        assert selector.signed is False
        assert str(binding.value.data_type) == "decimal"
        assert str(binding.value.channel) == "decimal"
    assert len(selected) == 26


def test_descendants_keep_decimal_shape_and_source_cited_construct_closure() -> None:
    modelo = load_modelo_directory(bundled_path("registry", "aeat", "modelos", "131"))
    for metadata, epoch, decimal_count in zip(authored_revisions("131"), _DESIGN_EPOCHS, _DECIMAL_COUNTS, strict=True):
        revision = modelo.revisions[str(metadata.id)]
        actual_decimal = sum(
            1
            for binding in revision.bindings
            if isinstance((selector := binding_export_selector(binding, revision=revision)), BindingFixedExportSelector)
            and selector.record == "DPA"
            and str(selector.data_type) == "decimal"
            and selector.decimals == 2
        )
        assert actual_decimal == decimal_count
        construct = next(
            item for item in revision.constructs if str(item.id) == "modelo-131-objective-estimation-instalment"
        )
        cited = {str(ref) for entry in load_semantic_map(_MAPPING_ROOT / epoch).entries for ref in entry.legal_refs}
        assert cited <= {str(ref) for ref in construct.legal_refs}
