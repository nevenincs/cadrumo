"""Detector-teeth tests for the field existence census.

Each test plants a tree in a temporary registry root and proves the census
names what was planted; nothing here asserts a count over the live corpus.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ..edition_field_census import build_report, field_paths, signal_lines

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _edition(root: Path, modelo: str, edition: str, *, manifest: str, sections: dict[str, str]) -> None:
    edition_dir = root / "modelos" / modelo / "revisions" / edition
    edition_dir.mkdir(parents=True)
    (edition_dir / "revision.toml").write_text(f'[revisions."{edition}"]\n{manifest}\n', encoding="utf-8")
    for family, text in sections.items():
        (edition_dir / family).mkdir()
        (edition_dir / family / "0001.toml").write_text(text, encoding="utf-8")


def _family(report, name: str):
    return next(item for item in report.families if item.family == name)


class TestFieldPaths:
    def test_paths_are_capped_at_two_levels(self) -> None:
        member = {"id": "x", "expression": {"op": "sum", "args": [{"op": "add", "args": [{"casilla_id": "1"}]}]}}
        paths = field_paths(member)
        assert "expression" in paths
        assert "expression.op" in paths
        assert "expression.args" in paths
        assert not any(path.count(".") > 1 for path in paths)

    def test_a_discriminated_nest_records_its_kind(self) -> None:
        paths = field_paths({"id": "b", "provider": {"kind": "previous_filing", "source_modelo": "100"}})
        assert "provider" in paths
        assert "provider[kind=previous_filing]" in paths
        assert "provider[kind=previous_filing].source_modelo" in paths
        assert "provider.source_modelo" not in paths

    def test_an_array_of_tables_records_its_sub_fields(self) -> None:
        paths = field_paths({"id": "f", "source_citations": [{"source_ref": "a", "required_text": ["x"]}]})
        assert {"source_citations", "source_citations[]", "source_citations[].source_ref"} <= paths


class TestClassification:
    def test_an_unknown_key_is_classified_unknown_and_a_typed_key_typed(self, tmp_path: Path) -> None:
        _edition(
            tmp_path,
            "999",
            "2025",
            manifest="valid_from = 2025-01-01",
            sections={"casillas": '[[revisions."2025".casillas]]\nid = "01"\ninvented = 1\n'},
        )
        casillas = _family(build_report(tmp_path), "casillas")
        by_path = {item.path: item for item in casillas.fields}
        assert by_path["id"].klass == "typed"
        assert by_path["invented"].klass == "unknown"

    def test_the_authoring_only_key_is_classified_authoring(self, tmp_path: Path) -> None:
        _edition(
            tmp_path,
            "999",
            "2025",
            manifest="valid_from = 2025-01-01",
            sections={"casillas": '[[revisions."2025".casillas]]\nid = "01"\nadditional_source_refs = ["a"]\n'},
        )
        casillas = _family(build_report(tmp_path), "casillas")
        assert next(item for item in casillas.fields if item.path == "additional_source_refs").klass == "authoring"

    def test_a_typed_field_no_member_carries_is_unused(self, tmp_path: Path) -> None:
        _edition(
            tmp_path,
            "999",
            "2025",
            manifest="valid_from = 2025-01-01",
            sections={"casillas": '[[revisions."2025".casillas]]\nid = "01"\n'},
        )
        assert "formula" in _family(build_report(tmp_path), "casillas").unused


class TestDivergence:
    def test_a_field_present_in_one_edition_and_absent_in_the_next_is_divergent(self, tmp_path: Path) -> None:
        _edition(
            tmp_path,
            "999",
            "2024",
            manifest="valid_from = 2024-01-01",
            sections={"casillas": '[[revisions."2024".casillas]]\nid = "01"\nsegmento = "a"\n'},
        )
        _edition(
            tmp_path,
            "999",
            "2025",
            manifest="valid_from = 2025-01-01",
            sections={"casillas": '[[revisions."2025".casillas]]\nid = "01"\n'},
        )
        casillas = _family(build_report(tmp_path), "casillas")
        assert [(d.path, d.present, d.absent) for d in casillas.divergences] == [("segmento", ("2024",), ("2025",))]

    def test_a_field_carried_by_every_edition_is_not_divergent(self, tmp_path: Path) -> None:
        for edition in ("2024", "2025"):
            _edition(
                tmp_path,
                "999",
                edition,
                manifest=f"valid_from = {edition}-01-01",
                sections={"casillas": f'[[revisions."{edition}".casillas]]\nid = "01"\nsegmento = "a"\n'},
            )
        assert _family(build_report(tmp_path), "casillas").divergences == ()


class TestSignal:
    def test_the_signal_is_deterministic_and_names_the_planted_family(self, tmp_path: Path) -> None:
        _edition(
            tmp_path,
            "999",
            "2025",
            manifest="valid_from = 2025-01-01",
            sections={"bindings": '[[revisions."2025".bindings]]\nid = "b"\nprovider = { kind = "manual" }\n'},
        )
        first = signal_lines(build_report(tmp_path))
        second = signal_lines(build_report(tmp_path))
        assert first == second
        assert any(line.startswith("fields bindings members=1") for line in first)
        assert any(line.startswith("field bindings provider[kind=manual] ") for line in first)
        declared = {"#", "corpus", "fields", "field", "unused", "divergent", "limitation"}
        assert {line.split(" ", 1)[0] for line in first} <= declared
