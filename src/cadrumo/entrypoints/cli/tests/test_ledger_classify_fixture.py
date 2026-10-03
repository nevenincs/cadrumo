"""Derived classify --file fixture: drift guard + apply journey.

The committed ``classify/*.classify.csv`` fixtures pair each corpus row's
content-addressed id with the oracle classification. This module (1) regenerates
the expected rows from the corpus + oracle and asserts byte-equality with the
committed fixture (so corpus drift fails loudly), and (2) drives the fixture
through ``ledger classify --file`` and asserts every row is applied.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from ....adapters.inbound.financial.providers.csv import CsvProvider
from ....domain.transactions.models import derive_transaction_id
from ....tests.inventory import FIXTURES_DIR
from ._ledger_corpus_support import _match
from .ledger_ux_support import _invoke_exact_profile
from .runtime_profile_cli_fixture import native_cli_profile_scope

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_CORPUS = FIXTURES_DIR / "financial" / "ledger-corpus"
_ACCOUNT = "bbva-business-eur.csv"
_FIXTURE = _CORPUS / "classify" / "bbva-business-eur.classify.csv"


def _rules() -> list[dict[str, object]]:
    loaded = json.loads((_CORPUS / "ground-truth.manifest.json").read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    raw_rules = loaded.get("rules")
    assert isinstance(raw_rules, list)
    rules: list[dict[str, object]] = []
    for raw_rule in raw_rules:
        assert isinstance(raw_rule, dict)
        rules.append({str(key): value for key, value in raw_rule.items()})
    return rules


def _expected_csv_text() -> str:
    rules = _rules()
    lines = ["transaction_id,classification,category_id"]
    for parsed in CsvProvider().ingest(_CORPUS / _ACCOUNT):
        raw = parsed.raw
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


@pytest.mark.windows_only
@pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers")
@pytest.mark.usefixtures("authority_operation")
def test_classify_fixture_applies_through_bulk_classify(tmp_path: Path) -> None:
    with native_cli_profile_scope(tmp_path) as profile:
        profile.register(
            label="native-ledger-classify-fixture",
            facts={
                "taxpayer_type.entity_type": "natural_person",
                "identity.name": "Native",
                "identity.surnames": "Classify fixture",
                "activities.description": "design",
                "censo.activity_start_date": "2025-01-01",
                "tax_residence.jurisdiction_scope": "common_regime",
                "iva.regime": "GENERAL",
                "iva.m303_regime_composition": "general",
                "iva.redeme_enrolled": "false",
                "iva.cash_accounting_regime_enrolled": "false",
                "iva.voluntary_sii_enrolled": "false",
                "iva.hydrocarbon_deposit_advance_payment_deduction_entitled": "false",
            },
        )
        imported = _invoke_exact_profile(
            profile, ["app", "ledger", "import", "--file", str(_CORPUS / _ACCOUNT), "--provider", "csv"]
        )
        assert imported.exit_code == 0, imported.output
        result = _invoke_exact_profile(
            profile, ["--format", "json", "app", "ledger", "classify", "--file", str(_FIXTURE)]
        )
        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)["result"]
        expected_rows = len(_FIXTURE.read_text(encoding="utf-8").strip().splitlines()) - 1
        assert payload["applied"] == expected_rows, payload
        assert payload["failures"] == []
