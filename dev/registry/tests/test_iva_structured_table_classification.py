"""S80 closure contract for IVA tables not migrated as rate facts."""

from __future__ import annotations

import json
import tomllib
from copy import deepcopy
from hashlib import sha256
from pathlib import Path

import pytest

from cadrumo.core.resources.bundled_data import bundled_path

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_ANALYSIS_PATH = Path("dev/registry/analysis/facts_iva_retirement.toml")
_EXPECTED = {
    "catalogues.toml": (21, "needs_typed_schema_and_fact_migration", "retain_until_lossless_replacement"),
    "place_of_supply.toml": (22, "needs_typed_schema_and_fact_migration", "retain_until_lossless_replacement"),
    "territories.toml": (3, "needs_typed_schema_and_fact_migration", "retain_until_lossless_replacement"),
    "territory_carve_outs.toml": (12, "needs_typed_schema_and_fact_migration", "retain_until_lossless_replacement"),
    "country_names.toml": (78, "technical_non_legal_canonical_vocabulary", "retain"),
}

_SOURCE_TABLES = {
    "catalogues.toml": ("regulations", 21, "91e957a85fba4f2315379dcf54a010f517dcf3b5c6a9564b9198a3ca0cb66fb4"),
    "place_of_supply.toml": (
        "place_of_supply_rules",
        22,
        "b09a32d7fd5148006a55ac48a23d3261b2efe2538876ad0ceec3a9253fd14a97",
    ),
    "territories.toml": ("territory", 3, "e14b1b8ede8fe338a3e24117b2b8d5f5822bd5384efcc6fe085db93d2ae5b399"),
    "territory_carve_outs.toml": (
        "carve_out",
        12,
        "ab309cc72d98862ce78abfca2d1a3ddfd2bde13b0cba2f942e6e64ac2d29e0c3",
    ),
    "country_names.toml": ("country", 78, "86908dfe2c46744b3293b6f0ee9fa154c1b5f4dbae1240578d3ba18981b7dae4"),
}


def _semantic_digest(rows: object) -> str:
    canonical = json.dumps(rows, default=str, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    return sha256(canonical.encode()).hexdigest()


def test_every_remaining_iva_table_has_a_safe_s80_disposition() -> None:
    analysis = tomllib.loads(_ANALYSIS_PATH.read_text(encoding="utf-8"))
    rows = analysis["remaining_structured_tables"]
    actual = {
        Path(row["data_path"]).name: (row["row_count"], row["classification"], row["decision"])
        for row in rows
    }
    bundled_iva = bundled_path("registry", "aeat", "iva")

    assert analysis["classification_step"] == "W04.P15.S80"
    assert actual == _EXPECTED
    assert {path.name for path in bundled_iva.glob("*.toml")} == set(_EXPECTED)
    assert all(row["safe_next_scope"].strip() for row in rows)

    for filename, (table_name, row_count, expected_digest) in _SOURCE_TABLES.items():
        payload = tomllib.loads((bundled_iva / filename).read_text(encoding="utf-8"))
        source_rows = payload[table_name]

        assert set(payload) == {table_name}
        assert isinstance(source_rows, list)
        assert len(source_rows) == row_count
        assert actual[filename][0] == len(source_rows)
        assert _semantic_digest(source_rows) == expected_digest


def test_s80_source_census_rejects_a_same_count_semantic_mutation() -> None:
    source = bundled_path("registry", "aeat", "iva", "catalogues.toml")
    rows = tomllib.loads(source.read_text(encoding="utf-8"))["regulations"]
    mutated = deepcopy(rows)
    mutated[0]["requires_reverse_charge"] = not mutated[0]["requires_reverse_charge"]

    assert len(mutated) == len(rows)
    assert _semantic_digest(mutated) != _SOURCE_TABLES["catalogues.toml"][2]
