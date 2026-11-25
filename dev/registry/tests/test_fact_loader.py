"""Strict parsing tests for governed-fact TOML fragments."""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

import pytest
from pydantic import BaseModel, ValidationError

from cadrumo.core.toml import freeze_toml, read_toml
from cadrumo.domain.calculations.registry.errors import RegistryLoadError
from cadrumo.domain.calculations.registry.facts.payloads import GovernedFactFamily
from cadrumo.domain.calculations.registry.facts.schema import GovernedFact

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


def test_a_copied_fact_file_is_validated_once_and_shared_immutably(tmp_path: Path) -> None:
    """Every staged candidate copies the facts tree, so one content answers every copy, and no copy can alter it."""
    text = _scalar_fact_toml("fact.shared")
    (tmp_path / "bundle").mkdir()
    (tmp_path / "candidate").mkdir()
    bundled = load_governed_fact_file(_write(tmp_path / "bundle" / "0001-shared.toml", text))
    candidate = _write(tmp_path / "candidate" / "0001-shared.toml", text)
    copied = load_governed_fact_file(candidate)

    assert copied is bundled, "identical bytes must answer from the one validated fact"
    with pytest.raises(ValidationError):
        _assign(copied, "fact_id", "fact.tampered")
    assert _mutable_containers(copied) == [], "a shared fact must be deep-immutable"
    fresh = GovernedFact.model_validate(freeze_toml(read_toml(candidate, error_factory=RegistryLoadError))["fact"])
    assert load_governed_fact_file(candidate) == fresh, "a hit must still equal a fresh validation of the bytes"
    assert fresh.fact_id == "fact.shared"


def _assign(model: BaseModel, name: str, value: object) -> None:
    setattr(model, name, value)


def _mutable_containers(value: object, where: str = "fact") -> list[str]:
    """Return where a list, dict, set or bytearray is reachable from ``value``."""
    if isinstance(value, BaseModel):
        return [
            found
            for name in type(value).model_fields
            for found in _mutable_containers(getattr(value, name), f"{where}.{name}")
        ]
    if isinstance(value, (list, dict, set, bytearray)):
        return [where]
    if isinstance(value, (tuple, frozenset)):
        return [found for item in value for found in _mutable_containers(item, where)]
    if isinstance(value, Mapping):
        return [found for item in value.values() for found in _mutable_containers(item, where)]
    return []


def test_a_stat_preserving_rewrite_of_a_fact_file_is_validated_afresh(tmp_path: Path) -> None:
    path = _write(tmp_path / "0001-iva-general-rate.toml", _scalar_fact_toml())
    original = load_governed_fact_file(path)
    before = path.stat()

    _write(path, _scalar_fact_toml().replace('value = "0.21"', 'value = "0.22"'))
    os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
    assert (path.stat().st_size, path.stat().st_mtime_ns) == (before.st_size, before.st_mtime_ns)

    revised = load_governed_fact_file(path)
    assert revised != original
    assert "0.22" in revised.model_dump_json()


def test_a_refused_copy_names_its_own_path(tmp_path: Path) -> None:
    text = _scalar_fact_toml().replace('unit = "ratio"', 'unit = "ratio"\nunexpected = true')
    for directory in ("first", "second"):
        (tmp_path / directory).mkdir()
        path = _write(tmp_path / directory / "0001-iva-rate.toml", text)
        with pytest.raises(RegistryLoadError, match=f"{directory}.+invalid governed fact"):
            load_governed_fact_file(path)
