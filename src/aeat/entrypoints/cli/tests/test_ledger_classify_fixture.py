"""Derived classify --from-csv fixture: drift guard + apply journey.

The committed ``classify/*.classify.csv`` fixtures pair each corpus row's
content-addressed id with the oracle classification. This module (1) regenerates
the expected rows from the corpus + oracle and asserts byte-equality with the
committed fixture (so corpus drift fails loudly), and (2) drives the fixture
through ``ledger classify --from-csv`` and asserts every row is applied.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ....adapters.inbound.financial.providers._csv import CsvProvider
from ....adapters.persistence.storage.sql.engine import dispose_engine
from ....application.user_profile._orchestration import profile_create_storage_span
from ....application.user_profile._testing import register_minimal_profile
from ....application.workflow._persistence import workflow_state_repository
from ....core.config import override_settings
from ....domain.transactions import derive_transaction_id
from ....tests import FIXTURES_DIR
from ....tests.secure_sql import isolated_profile_storage_root
from .. import app

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_RUNNER = CliRunner()
_CORPUS = FIXTURES_DIR / "financial" / "ledger-corpus"
_ACCOUNT = "bbva-business-eur.csv"
_FIXTURE = _CORPUS / "classify" / "bbva-business-eur.classify.csv"


def _rules() -> list[dict[str, object]]:
    return json.loads((_CORPUS / "ground-truth.manifest.json").read_text(encoding="utf-8"))["rules"]


def _match(description: str, rules: list[dict[str, object]]) -> dict[str, object] | None:
    for rule in rules:
        match_val = rule.get("match")
        if isinstance(match_val, str) and match_val in description:
            return rule
    return None


def _expected_csv_text() -> str:
    rules = _rules()
    lines = ["transaction_id,classification,category_id"]
    for raw in CsvProvider().ingest(_CORPUS / _ACCOUNT):
        rule = _match(raw.description, rules)
        assert rule is not None, raw.description
        if rule["classification"] == "MIXED":
            continue
        cat = rule.get("category_id") or ""
        lines.append(f"{derive_transaction_id(raw)},{rule['classification']},{cat}")
    return "\n".join(lines) + "\n"


def test_classify_fixture_matches_oracle_derivation() -> None:
    # Drift guard: the committed fixture must equal the freshly-derived rows.
    assert _FIXTURE.read_text(encoding="utf-8") == _expected_csv_text()


@pytest.fixture
def _isolated_backend(tmp_path: Path) -> Iterator[None]:
    dispose_engine()
    with (
        override_settings(aeat_local_storage_root=tmp_path, aeat_output_language="en"),
        isolated_profile_storage_root(tmp_path=tmp_path),
        profile_create_storage_span("default"),
    ):
        try:
            workflow_state_repository().update(lambda state: register_minimal_profile(state, profile_id="default"))
            yield
        finally:
            dispose_engine()


def test_classify_fixture_applies_through_bulk_classify(_isolated_backend: None) -> None:
    imported = _RUNNER.invoke(app, ["app", "ledger", "import", str(_CORPUS / _ACCOUNT), "--provider", "csv"])
    assert imported.exit_code == 0, imported.output
    result = _RUNNER.invoke(app, ["--format", "json", "app", "ledger", "classify", "--from-csv", str(_FIXTURE)])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)["result"]
    expected_rows = len(_FIXTURE.read_text(encoding="utf-8").strip().splitlines()) - 1
    assert payload["applied"] == expected_rows, payload
    assert payload["failures"] == []
