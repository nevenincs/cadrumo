"""A layout-authority citation grounds a formula only where the formula restates the printed sum it quotes.

The fixture dictionary prints two comunidad rows that sum other boxes. The checks run
through the formula-citation validator the compiler applies to every formula.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date
from pathlib import Path

import pytest

from cadrumo.core.hashing import sha256_hex
from cadrumo.domain.calculations.registry.schema import FormulaDefinition
from cadrumo.domain.calculations.registry.schema_base import RegistrySourceKind
from cadrumo.domain.calculations.registry.schema_references import SourceReference
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope

from .. import validate_evidence
from ..validate_design_sum import formula_citation_failures

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_SOURCE = "fixture-dictionary"
_BINDING = "renta-profile-tax-residence-ccaa"
_ROW_A = (
    "SUMA=[/R/DeduccionAutonomicaRes/ARes/SUMA][P102][0564][(suma de las casillas [0001] a [0002] - [0003] ? [0004])]"
)
_ROW_B = "SUMB=[/R/DeduccionAutonomicaRes/BRes/SUMB][P102][0564][(suma de las casillas [0005] + [0006])]"
_NUMERIC = frozenset({"0001", "0002", "0003", "0004", "0005", "0006"})

type Operands = Sequence[tuple[int, str]]


@pytest.fixture
def evidence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> validate_evidence.EvidenceValidator:
    monkeypatch.setattr(validate_evidence, "corpus_text_cache_dir", lambda: tmp_path / "cache")
    body = f"{_ROW_A}\n{_ROW_B}\n".encode("cp1252")
    corpus_path = "corpus/aeat_official/dictionary.properties"
    path = tmp_path / corpus_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    source = SourceReference(
        id=_SOURCE,
        evidence_tier="layout_authority",
        authority="aeat",
        kind=RegistrySourceKind.DICTIONARY,
        corpus_path=corpus_path,
        sha256=sha256_hex(body),
        bytes=len(body),
        retrieved_at=date(filing_year_envelope().horizon, 11, 2),
        source_url="https://sede.agenciatributaria.gob.es/dictionary.properties",
        review_status="pending_review",
    )
    return validate_evidence.EvidenceValidator(legal_refs={}, source_refs={_SOURCE: source}, source_root=tmp_path)


def _leaf(sign: int, box: str) -> dict[str, object]:
    leaf: dict[str, object] = {"casilla_id": box}
    return leaf if sign > 0 else {"op": "negate", "args": [leaf]}


def _refusal(reason: str) -> dict[str, object]:
    return {"op": "unresolved_outcome", "args": [{"text_literal": reason}]}


def _zero_test(args: Sequence[Mapping[str, object]]) -> dict[str, object]:
    return {"op": "equal", "args": [{"op": "sum", "args": list(args)}, {"literal": "0"}]}


def _term(selector: str, operands: Operands, guards: Sequence[str] = ()) -> dict[str, object]:
    summed = {"op": "sum", "args": [_leaf(sign, box) for sign, box in operands]}
    magnitudes = [{"op": "max", "args": [_leaf(1, box), _leaf(-1, box)]} for box in guards]
    selected = (
        {"op": "if_then_else", "args": [_zero_test(magnitudes), summed, _refusal("autonomic-deduction-unsummed-box")]}
        if guards
        else summed
    )
    other = [_zero_test(summed["args"]), {"literal": "0"}, _refusal("autonomic-deduction-other-comunidad")]
    predicate = {"op": "text_equal", "args": [{"binding": _BINDING}, {"text_literal": selector}]}
    return {"op": "if_then_else", "args": [predicate, selected, {"op": "if_then_else", "args": other}]}


def _formula(expression: Mapping[str, object], quotes: Sequence[str]) -> FormulaDefinition:
    return FormulaDefinition.model_validate(
        {
            "id": "fixture-design-sum",
            "target_casilla_id": "0564",
            "expression": expression,
            "rounding": "money-2",
            "legal_refs": ("ley-35-2006:art-77",),
            "source_refs": (_SOURCE,),
            "source_citations": tuple({"source_ref": _SOURCE, "required_text": (quote,)} for quote in quotes),
        }
    )


def _failures(evidence: validate_evidence.EvidenceValidator, formula: FormulaDefinition) -> list[str]:
    return formula_citation_failures("fixture", formula, numeric_casillas=_NUMERIC, evidence=evidence)


_A = [(1, "0001"), (1, "0002"), (-1, "0003")]
_B = [(1, "0005"), (1, "0006")]


def _design_sum(a: Operands = _A, a_guards: Sequence[str] = ("0004",)) -> dict[str, object]:
    return {"op": "sum", "args": [_term("a", a, a_guards), _term("b", _B)]}


def test_a_design_sum_cited_by_its_printed_rows_is_grounded(evidence: validate_evidence.EvidenceValidator) -> None:
    assert _failures(evidence, _formula(_design_sum(), (_ROW_A, _ROW_B))) == []


def test_an_ordinary_formula_citing_only_a_layout_row_is_refused(
    evidence: validate_evidence.EvidenceValidator,
) -> None:
    ordinary = {"op": "sum", "args": [_leaf(1, "0005"), _leaf(1, "0006")]}

    failures = _failures(evidence, _formula(ordinary, (_ROW_B,)))

    assert len(failures) == 1
    assert "does not restate a printed design sum" in failures[0]


@pytest.mark.parametrize(
    ("operands", "guards"),
    [
        ([*_A, (1, "0007")], ("0004",)),
        ([*_A, (1, "0004")], ()),
        ([(1, "0001"), (1, "0002"), (1, "0003")], ("0004",)),
        (_A, ()),
    ],
    ids=["unprinted-box", "unreadable-sign-summed", "printed-sign-flipped", "numeric-box-dropped"],
)
def test_a_design_sum_that_departs_from_its_row_is_refused(
    evidence: validate_evidence.EvidenceValidator, operands: Operands, guards: Sequence[str]
) -> None:
    failures = _failures(evidence, _formula(_design_sum(operands, guards), (_ROW_A, _ROW_B)))

    assert any("term 'a' restates 0 cited rows" in failure for failure in failures)


def test_a_design_sum_missing_the_citation_of_one_row_is_refused(
    evidence: validate_evidence.EvidenceValidator,
) -> None:
    failures = _failures(evidence, _formula(_design_sum(), (_ROW_A,)))

    assert any("term 'b' restates 0 cited rows" in failure for failure in failures)


def test_a_layout_citation_quoting_part_of_a_row_is_refused(evidence: validate_evidence.EvidenceValidator) -> None:
    partial = _ROW_B.removesuffix(")]")

    failures = _failures(evidence, _formula(_design_sum(), (_ROW_A, partial)))

    assert len(failures) == 1
    assert "quotes 0 whole rows, not one" in failures[0]
