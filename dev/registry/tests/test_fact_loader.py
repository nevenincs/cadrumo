"""Strict parsing tests for governed-fact TOML fragments."""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.errors import RegistryLoadError
from cadrumo.domain.calculations.registry.facts.schema import GovernedFactFamily

from ..compiler.fact_loader import load_governed_fact_file, load_governed_facts

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _scalar_fact_toml(fact_id: str = "iva.general.rate") -> str:
    return f'''[fact]
fact_id = "{fact_id}"
family = "scalar"

[[fact.variants]]
variant_id = "{fact_id}.2025"
date_axis = "transaction_date"
valid_from = 2025-01-01
legal_refs = ["ley-37-1992-art-90"]
source_refs = ["aeat-iva-rates"]
review_status = "pending_review"
ownership = "authored"

[[fact.variants.source_citations]]
source_ref = "aeat-iva-rates"
required_text = ["Tipo general"]

[fact.variants.payload]
kind = "scalar"
value = "0.21"
unit = "ratio"
'''


def _write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def test_load_governed_fact_file_parses_one_strict_fact(tmp_path: Path) -> None:
    fact = load_governed_fact_file(_write(tmp_path / "0001-iva-general-rate.toml", _scalar_fact_toml()))

    assert fact.fact_id == "iva.general.rate"
    assert fact.family is GovernedFactFamily.SCALAR
    assert fact.variants[0].variant_id == "iva.general.rate.2025"


@pytest.mark.parametrize(
    ("filename", "text", "message"),
    [
        ("iva-rate.toml", _scalar_fact_toml(), "filename must match"),
        ("0001-iva-rate.toml", "not valid = [", "invalid TOML"),
        ("0001-iva-rate.toml", "[metadata]\nname = 'extra'\n", "exactly one \\[fact\\] table"),
        (
            "0001-iva-rate.toml",
            _scalar_fact_toml() + "\n[metadata]\nname = 'extra'\n",
            "exactly one \\[fact\\] table",
        ),
        (
            "0001-iva-rate.toml",
            _scalar_fact_toml().replace('unit = "ratio"', 'unit = "ratio"\nunexpected = true'),
            "invalid governed fact",
        ),
    ],
)
def test_load_governed_fact_file_fails_closed(
    tmp_path: Path,
    filename: str,
    text: str,
    message: str,
) -> None:
    path = _write(tmp_path / filename, text)

    with pytest.raises(RegistryLoadError, match=message):
        load_governed_fact_file(path)


def test_load_governed_facts_uses_filename_order_not_fact_identity(tmp_path: Path) -> None:
    _write(tmp_path / "0002-alpha.toml", _scalar_fact_toml("fact.alpha"))
    _write(tmp_path / "0001-zeta.toml", _scalar_fact_toml("fact.zeta"))

    facts = load_governed_facts(tmp_path)

    assert tuple(fact.fact_id for fact in facts) == ("fact.zeta", "fact.alpha")


def test_load_governed_facts_refuses_duplicate_semantic_identity(tmp_path: Path) -> None:
    _write(tmp_path / "0001-first.toml", _scalar_fact_toml())
    _write(tmp_path / "0002-second.toml", _scalar_fact_toml())

    with pytest.raises(RegistryLoadError, match="already declared"):
        load_governed_facts(tmp_path)


def test_load_governed_facts_allows_an_absent_directory(tmp_path: Path) -> None:
    assert load_governed_facts(tmp_path / "absent") == ()
