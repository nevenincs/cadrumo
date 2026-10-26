"""Behavioral proof that candidate fact 0102 owns compiler-time NIF validation."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

from cadrumo.core.identity.documents import TAX_ID_FORMAT_CONTEXT
from cadrumo.domain.calculations.registry.schema_scalars import NifString
from cadrumo.domain.calculations.registry.tax_id_format import tax_id_format_from_catalogue
from dev.registry.compiler.fact_providers import compile_authored_fact_catalogue

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_ALTERED_FORMAT_FACT = """
[fact]
fact_id = "spanish-tax-identifier-format"
family = "mapping"

[[fact.variants]]
variant_id = "spanish-tax-identifier-format:altered"
date_axis = "filing_period"
valid_from = 2025-01-01
legal_refs = ["fixture-law:tax-id"]
review_status = "agent_reviewed"
ownership = "authored"

[fact.variants.payload]
kind = "mapping"
entries = [
  { key = "tax_id.width", value = "7" },
  { key = "tax_id.country_prefix", value = "ZZ" },
  { key = "tax_id.country_prefixed_width", value = "9" },
  { key = "tax_id.country_prefix_strip_width", value = "2" },
  { key = "tax_id.leaders.prefixed_nif", value = "P" },
  { key = "tax_id.leaders.nie", value = "Q" },
  { key = "tax_id.leaders.cif", value = "TU" },
  { key = "tax_id.check.nif_letters", value = "EKCLHVQSZJNBXDPFYMGAWRT" },
  { key = "tax_id.check.nie_prefix.Q", value = "5" },
  { key = "tax_id.check.cif_digit_only_kinds", value = "T" },
  { key = "tax_id.check.cif_letter_only_kinds", value = "U" },
  { key = "tax_id.check.cif_letter_table", value = "ABCDEFGHIJ" },
]
"""


def test_candidate_fact_0102_governs_nif_validation_without_installed_authority(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Altered candidate values, not the installed artifact, decide acceptance."""
    facts_dir = tmp_path / "facts"
    facts_dir.mkdir()
    (facts_dir / "0102-spanish-tax-identifier-format.toml").write_text(
        _ALTERED_FORMAT_FACT,
        encoding="utf-8",
    )
    candidate_facts = compile_authored_fact_catalogue(tmp_path)
    candidate_format = tax_id_format_from_catalogue(candidate_facts)

    from cadrumo.domain.calculations.registry import authority

    # The installed artifact is reached through ``bundled_indexed_authority``;
    # patching a name the module no longer carries raised AttributeError, which
    # failed the test without ever arming the guard it exists to arm.
    monkeypatch.setattr(
        authority,
        "bundled_indexed_authority",
        lambda: (_ for _ in ()).throw(AssertionError("candidate validation consulted the installed artifact")),
    )
    adapter: TypeAdapter[str] = TypeAdapter(NifString)
    context = {TAX_ID_FORMAT_CONTEXT: candidate_format}

    assert adapter.validate_python("ZZ000000E", context=context) == "000000E"
    with pytest.raises(ValidationError):
        adapter.validate_python("00000000T", context=context)


@pytest.mark.parametrize(
    ("old", "new", "message"),
    (
        pytest.param(
            'value = "EKCLHVQSZJNBXDPFYMGAWRT"',
            'value = "EKCLHVQSZJNBXDPFYMGAWRE"',
            "23 unique",
            id="duplicate-nif-table-entry",
        ),
        pytest.param(
            'key = "tax_id.check.nie_prefix.Q", value = "5"',
            'key = "tax_id.check.nie_prefix.Q", value = "\N{ARABIC-INDIC DIGIT FIVE}"',
            "single decimal digits",
            id="unicode-nie-substitution",
        ),
        pytest.param(
            'key = "tax_id.check.cif_digit_only_kinds", value = "T"',
            'key = "tax_id.check.cif_digit_only_kinds", value = "TT"',
            "must not repeat",
            id="duplicate-cif-partition-leader",
        ),
        pytest.param(
            'key = "tax_id.check.cif_letter_table", value = "ABCDEFGHIJ"',
            'key = "tax_id.check.cif_letter_table", value = "ABCDEFGHIA"',
            "ten unique",
            id="duplicate-cif-table-entry",
        ),
    ),
)
def test_candidate_fact_refuses_malformed_checksum_declarations(
    tmp_path: Path, old: str, new: str, message: str
) -> None:
    malformed_fact = _ALTERED_FORMAT_FACT.replace(old, new)
    assert malformed_fact != _ALTERED_FORMAT_FACT
    facts_dir = tmp_path / "facts"
    facts_dir.mkdir()
    (facts_dir / "0102-spanish-tax-identifier-format.toml").write_text(malformed_fact, encoding="utf-8")

    candidate_facts = compile_authored_fact_catalogue(tmp_path)
    with pytest.raises(ValueError, match=message):
        tax_id_format_from_catalogue(candidate_facts)
