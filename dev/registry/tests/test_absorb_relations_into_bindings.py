"""Join behaviour and refusals of the relation-absorption migration.

Every case builds an isolated temporary registry tree, so the contributor's
working tree is never mutated and the detector teeth (each refusal) are proven
against real files rather than a patched module. The normal path and the
defect proofs pass in the same suite, per ``aeat-quality-gates``.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

import pytest

from dev.registry.absorb_relations_into_bindings import AbsorptionReport, absorb_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_REVISION = "2024"
_MODELO = "999"

_MANIFEST = """\
id = "999"
title_key = "modelo.999.title"
legal_refs = ["ley-27-2014:art-40"]
source_refs = ["aeat-modelo-202-instructions"]
"""

_BINDING = """\
[[revisions."2024".bindings]]
id = "fold-slot"
provider = {{ kind = "relation_prefill", source_modelo = "{source_modelo}", source_casilla_id = "{casilla}" }}
value = {{ data_type = "money", channel = "decimal" }}
aggregation = {{ op = "{op}" }}
legal_refs = ["ley-27-2014:art-40"]
source_refs = ["aeat-modelo-202-instructions"]
"""

_RELATION = """\
[[revisions."2024".relations]]
id = "{relation_id}"
kind = "cross_model_output"
dependency_role = "direct_calculation"
source_modelo = "{source_modelo}"
source_revision_selector = {{ {selector} }}
source_casilla_id = "{casilla}"
target_binding = "{target_binding}"
period_alignment = {{ source_periods = "quarters", target_period = "0A" }}
source_periods = {source_periods}
target_periods = {target_periods}
aggregation = {{ op = "{op}" }}
legal_refs = ["ley-27-2014:art-40"]
source_refs = ["aeat-modelo-202-instructions"]
"""


def _seed(
    root: Path,
    *,
    relations: list[str],
    binding_source_modelo: str = "200",
    binding_casilla: str = "34",
    binding_op: str = "sum",
) -> Path:
    revision_dir = root / _MODELO / "revisions" / _REVISION
    (revision_dir / "bindings").mkdir(parents=True)
    (revision_dir / "relations").mkdir(parents=True)
    (root / _MODELO / "manifest.toml").write_text(_MANIFEST, encoding="utf-8")
    (revision_dir / "bindings" / "0001-bindings.toml").write_text(
        _BINDING.format(source_modelo=binding_source_modelo, casilla=binding_casilla, op=binding_op),
        encoding="utf-8",
    )
    (revision_dir / "relations" / "0001-relations.toml").write_text("\n".join(relations), encoding="utf-8")
    return revision_dir


def _relation(
    *,
    relation_id: str = "rel-one",
    source_modelo: str = "200",
    casilla: str = "34",
    target_binding: str = "fold-slot",
    selector: str = "filing_year_delta = -1",
    source_periods: str = '["0A"]',
    target_periods: str = '["0A"]',
    op: str = "sum",
) -> str:
    return _RELATION.format(
        relation_id=relation_id,
        source_modelo=source_modelo,
        casilla=casilla,
        target_binding=target_binding,
        selector=selector,
        source_periods=source_periods,
        target_periods=target_periods,
        op=op,
    )


def _run(root: Path, *, apply: bool = True) -> AbsorptionReport:
    report = AbsorptionReport()
    absorb_modelo(_MODELO, report, apply=apply, modelos_root=root)
    return report


def _provider(revision_dir: Path) -> dict[str, Any]:
    data = tomllib.loads((revision_dir / "bindings" / "0001-bindings.toml").read_text(encoding="utf-8"))
    return dict(data["revisions"][_REVISION]["bindings"][0]["provider"])


def test_a_single_relation_folds_into_its_target_binding_provider(tmp_path: Path) -> None:
    revision_dir = _seed(tmp_path, relations=[_relation()])

    report = _run(tmp_path)

    assert report.refusals == []
    provider = _provider(revision_dir)
    assert provider["relation_kind"] == "cross_model_output"
    assert provider["dependency_role"] == "direct_calculation"
    assert provider["temporal"] == {"kind": "filing_year_offset", "years": -1, "source_periods": ["0A"]}
    assert not (revision_dir / "relations").exists()
    assert report.join_table == {"rel-one": "fold-slot"}


def test_the_relations_target_periods_move_onto_the_bindings_applicability(tmp_path: Path) -> None:
    revision_dir = _seed(tmp_path, relations=[_relation(target_periods='["2P", "3P"]')])

    _run(tmp_path)

    data = tomllib.loads((revision_dir / "bindings" / "0001-bindings.toml").read_text(encoding="utf-8"))
    applicability = data["revisions"][_REVISION]["bindings"][0]["applicability"]
    assert applicability == {"kind": "target_periods", "periods": ["2P", "3P"]}


def test_a_relation_naming_no_declared_binding_is_refused(tmp_path: Path) -> None:
    revision_dir = _seed(tmp_path, relations=[_relation(target_binding="not-declared")])
    before = (revision_dir / "bindings" / "0001-bindings.toml").read_text(encoding="utf-8")

    report = _run(tmp_path)

    assert [item["reason"] for item in report.refusals] == [
        "relation names a target_binding this revision does not declare",
    ]
    assert (revision_dir / "bindings" / "0001-bindings.toml").read_text(encoding="utf-8") == before
    assert (revision_dir / "relations").exists()


def test_two_relations_disagreeing_on_an_unmergeable_axis_are_refused(tmp_path: Path) -> None:
    """Different source casillas cannot become one provider coordinate."""
    revision_dir = _seed(
        tmp_path,
        relations=[
            _relation(relation_id="rel-one"),
            _relation(relation_id="rel-two", casilla="35"),
        ],
    )
    before = (revision_dir / "bindings" / "0001-bindings.toml").read_text(encoding="utf-8")

    report = _run(tmp_path)

    assert report.refusals
    assert "disagree on 'source_casilla_id'" in report.refusals[0]["reason"]
    assert (revision_dir / "bindings" / "0001-bindings.toml").read_text(encoding="utf-8") == before


def test_two_relations_differing_only_in_source_periods_merge_to_one_window(tmp_path: Path) -> None:
    revision_dir = _seed(
        tmp_path,
        relations=[
            _relation(relation_id="rel-quarters", selector="filing_year_delta = 0", source_periods='["1T", "2T"]'),
            _relation(relation_id="rel-months", selector="filing_year_delta = 0", source_periods='["01", "02"]'),
        ],
    )

    report = _run(tmp_path)

    assert report.refusals == []
    assert _provider(revision_dir)["temporal"] == {
        "kind": "same_filing_year_periods",
        "source_periods": ["1T", "2T", "01", "02"],
    }
    assert report.merge_shape_counts["period_union"] == 1


def test_two_relations_differing_in_year_delta_per_target_period_become_one_offsets_map(tmp_path: Path) -> None:
    revision_dir = _seed(
        tmp_path,
        relations=[
            _relation(
                relation_id="rel-1p",
                selector="filing_year_delta = -2",
                target_periods='["1P"]',
                op="copy",
            ),
            _relation(
                relation_id="rel-2p-3p",
                selector="filing_year_delta = -1",
                target_periods='["2P", "3P"]',
                op="copy",
            ),
        ],
        binding_op="copy",
    )

    report = _run(tmp_path)

    assert report.refusals == []
    assert _provider(revision_dir)["temporal"] == {
        "kind": "filing_year_offset_by_target_period",
        "offsets": {"1P": -2, "2P": -1, "3P": -1},
        "source_periods": ["0A"],
    }
    assert report.merge_shape_counts["offset_by_target_period"] == 1


def test_an_absolute_source_year_that_is_not_the_revisions_own_year_is_refused(tmp_path: Path) -> None:
    revision_dir = _seed(tmp_path, relations=[_relation(selector="year = 2019")])
    before = (revision_dir / "bindings" / "0001-bindings.toml").read_text(encoding="utf-8")

    report = _run(tmp_path)

    assert report.refusals
    assert "selects absolute source year 2019" in report.refusals[0]["reason"]
    assert (revision_dir / "bindings" / "0001-bindings.toml").read_text(encoding="utf-8") == before


def test_an_absolute_source_year_equal_to_the_revision_year_maps_to_delta_zero(tmp_path: Path) -> None:
    revision_dir = _seed(tmp_path, relations=[_relation(selector=f"year = {_REVISION}")])

    report = _run(tmp_path)

    assert report.refusals == []
    assert _provider(revision_dir)["temporal"] == {
        "kind": "same_filing_year_periods",
        "source_periods": ["0A"],
    }


def test_an_aggregation_disagreement_between_relation_and_binding_is_refused(tmp_path: Path) -> None:
    revision_dir = _seed(tmp_path, relations=[_relation(op="copy")], binding_op="sum")
    before = (revision_dir / "bindings" / "0001-bindings.toml").read_text(encoding="utf-8")

    report = _run(tmp_path)

    assert report.refusals
    assert "aggregation" in report.refusals[0]["reason"]
    assert (revision_dir / "bindings" / "0001-bindings.toml").read_text(encoding="utf-8") == before


def test_a_source_modelo_disagreement_is_refused(tmp_path: Path) -> None:
    revision_dir = _seed(tmp_path, relations=[_relation(source_modelo="111")], binding_source_modelo="200")
    before = (revision_dir / "bindings" / "0001-bindings.toml").read_text(encoding="utf-8")

    report = _run(tmp_path)

    assert report.refusals
    assert "source_modelo" in report.refusals[0]["reason"]
    assert (revision_dir / "bindings" / "0001-bindings.toml").read_text(encoding="utf-8") == before


def test_a_dry_run_writes_nothing_but_reports_the_same_plan(tmp_path: Path) -> None:
    revision_dir = _seed(tmp_path, relations=[_relation()])
    before = (revision_dir / "bindings" / "0001-bindings.toml").read_text(encoding="utf-8")

    report = _run(tmp_path, apply=False)

    assert report.refusals == []
    assert report.relations_absorbed_by_modelo[_MODELO] == 1
    assert (revision_dir / "bindings" / "0001-bindings.toml").read_text(encoding="utf-8") == before
    assert (revision_dir / "relations" / "0001-relations.toml").exists()
