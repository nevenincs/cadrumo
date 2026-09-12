"""Detector-teeth tests for the mechanically derived modelo embed scan."""

from __future__ import annotations

from pathlib import Path

import pytest

from ..validation.regulatory_embeds import EvidenceKind, census

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_MODELO_SPECIFIC_BODIES = {
    "module_name": '"""Modelo-named."""\nVALUE = 1\n',
    "modelo_reference": "from cadrumo.core import Modelo\nOWNER = Modelo('303')\n",
    "defined_symbol": "def evaluate_m210_resolve_something() -> int:\n    return 1\n",
}


@pytest.mark.parametrize("signal", sorted(_MODELO_SPECIFIC_BODIES))
def test_each_structural_signal_discovers_a_new_module(signal: str, tmp_path: Path) -> None:
    stem = "_m347_planted" if signal == "module_name" else "_planted_surface"
    (tmp_path / f"{stem}.py").write_text(_MODELO_SPECIFIC_BODIES[signal], encoding="utf-8")

    records = census(tmp_path)

    assert [Path(record.path).name for record in records] == [f"{stem}.py"]
    assert signal in {str(item) for item in records[0].signals}


@pytest.mark.parametrize(
    ("body", "kind"),
    [
        ("from decimal import Decimal\nRATE = Decimal('0.21')\n", EvidenceKind.DECIMAL_LITERAL),
        ("FIRST_YEAR = 2026\n", EvidenceKind.FILING_YEAR_LITERAL),
        (
            "RULE_REASON = 'La declaración deberá presentarse según la regulación vigente.'\n",
            EvidenceKind.REGULATORY_PROSE_LITERAL,
        ),
    ],
)
def test_each_regulatory_literal_shape_bites(body: str, kind: EvidenceKind, tmp_path: Path) -> None:
    (tmp_path / "_m303_planted.py").write_text(body, encoding="utf-8")

    records = census(tmp_path)

    assert kind in {item.kind for item in records[0].evidence}


def test_an_unparsable_module_is_announced_without_hiding_healthy_evidence(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    (tmp_path / "_healthy_m303.py").write_text("YEAR = 2026\n", encoding="utf-8")
    (tmp_path / "_broken_m210.py").write_text("def broken(:\n", encoding="utf-8")

    records = census(tmp_path)

    assert len(records) == 1
    assert records[0].evidence
    assert "_broken_m210.py" in capsys.readouterr().err


def test_a_parsable_tree_is_silent(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (tmp_path / "_healthy_m303.py").write_text("VALUE = 1\n", encoding="utf-8")

    census(tmp_path)

    assert capsys.readouterr().err == ""


@pytest.mark.parametrize(
    "body",
    [
        "from decimal import Decimal\ndef total(value: Decimal) -> Decimal:\n    return value + Decimal('0')\n",
        "from decimal import Decimal\ndef share(value: Decimal) -> Decimal:\n    return value / Decimal('100')\n",
        "class Observation:\n    filing_year: int = 2100\n",
        "from decimal import Decimal\nclass Observation:\n    percentage: Decimal = Decimal('100')\n",
        "import re\nPATTERN = re.compile(r'^número\\s+$')\n",
        "class Observation:\n    value: str\n    '''Descripción del campo que no es texto de operador.'''\n",
    ],
)
def test_non_policy_syntax_is_not_reported(body: str, tmp_path: Path) -> None:
    (tmp_path / "_m303_planted.py").write_text(body, encoding="utf-8")

    records = census(tmp_path)

    assert records[0].evidence == ()


def test_a_non_identity_decimal_in_a_validation_still_bites(tmp_path: Path) -> None:
    (tmp_path / "_m303_planted.py").write_text(
        "from decimal import Decimal\ndef validate(value: Decimal) -> bool:\n    return value == Decimal('0.20')\n",
        encoding="utf-8",
    )

    records = census(tmp_path)

    assert {item.kind for item in records[0].evidence} == {EvidenceKind.DECIMAL_LITERAL}
