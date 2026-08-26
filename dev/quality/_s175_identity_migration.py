"""One-shot migration of reviewed line citations to exact stable identities."""

from __future__ import annotations

import json

from dev.quality.registry_facade_family_census import MATRIX_PATH, generated_rows


document = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
generated = {row["old_path"]: row for row in generated_rows()}
for row in document["rows"]:
    current = generated[row["old_path"]]["current_symbol_locators"]
    row["semantic_evidence"]["owner_definition_locators"] = sorted(
        locator for locators in current.values() for locator in locators
    )
    result = row["rag_result"]
    identity = f"{result['path']}::{result['symbol']}"
    if current.get(result["symbol"], []).count(identity) != 1:
        raise RuntimeError(
            f"stored RAG result does not resolve uniquely: {identity}; "
            f"current={current.get(result['symbol'], [])}"
        )
    old_location = f"{result['path']}:{result['line_start']}"
    evidence = row["alternative_owner_evidence"]
    if old_location not in evidence:
        raise RuntimeError(f"review prose lost its RAG citation: {row['row_id']}")
    row["alternative_owner_evidence"] = evidence.replace(old_location, identity)

MATRIX_PATH.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
