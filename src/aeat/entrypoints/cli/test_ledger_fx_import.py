"""CLI import wires the ECB normalizer so foreign rows convert (ledger-fx-conversion).

Regression for the persona-surfaced HIGH defect: the CLI import path previously
persisted GBP/USD rows with value_in_eur=None, which then gated as
UNSUPPORTED_CURRENCY at aggregation. After wiring the ECB euro reference-rate
normalizer at the composition root, imported foreign rows carry fx_rate and
value_in_eur; EUR rows remain unconverted (native).
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ...adapters.persistence.storage.sql.engine import dispose_engine
from ...application.user_profile._orchestration import profile_create_storage_span
from ...application.user_profile._testing import register_minimal_profile
from ...application.workflow._models import resolve_active_bucket_id
from ...application.workflow._persistence import workflow_state_repository
from ...core.config import override_settings
from ...domain.transactions import TransactionCatalogueRepository
from ...tests.secure_sql import isolated_profile_storage_root
from . import app

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]

_RUNNER = CliRunner()
_CORPUS = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "financial" / "ledger-corpus"


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path) -> Iterator[None]:
    dispose_engine()
    with (
        override_settings(aeat_local_storage_root=tmp_path, aeat_output_language="en"),
        isolated_profile_storage_root(tmp_path=tmp_path),
        profile_create_storage_span("default"),
    ):
        try:
            workflow_state_repository().update(
                lambda state: register_minimal_profile(state, profile_id="default")
            )
            yield
        finally:
            dispose_engine()


def test_cli_import_converts_foreign_rows_to_eur() -> None:
    result = _RUNNER.invoke(
        app, ["app", "ledger", "import", str(_CORPUS / "revolut-multi.csv"), "--provider", "csv"]
    )
    assert result.exit_code == 0, result.output

    bucket_id = resolve_active_bucket_id()
    assert bucket_id is not None
    catalogue = TransactionCatalogueRepository(bucket_id=bucket_id).load()
    transactions = list(catalogue.values())

    foreign = [t for t in transactions if t.raw.currency in {"GBP", "USD"}]
    eur = [t for t in transactions if t.raw.currency == "EUR"]
    assert foreign, "revolut corpus must contain GBP/USD rows"

    for t in foreign:
        assert t.fx_rate is not None, f"{t.raw.description}: fx_rate not set"
        assert t.value_in_eur is not None, f"{t.raw.description}: value_in_eur not set"
        assert t.value_in_eur > 0
    # EUR rows are native: no conversion applied.
    for t in eur:
        assert t.fx_rate is None
        assert t.value_in_eur is None


def test_list_surfaces_eur_value_and_fx_rate_for_foreign_rows() -> None:
    import json

    result = _RUNNER.invoke(
        app, ["app", "ledger", "import", str(_CORPUS / "revolut-multi.csv"), "--provider", "csv"]
    )
    assert result.exit_code == 0, result.output
    listed = _RUNNER.invoke(app, ["--format", "json", "app", "ledger", "list"])
    assert listed.exit_code == 0, listed.output
    rows = json.loads(listed.output)["result"]["rows"]
    foreign = [r for r in rows if r.get("currency") in {"GBP", "USD"}]
    eur = [r for r in rows if r.get("currency") == "EUR"]
    assert foreign
    # Finding #2: the EUR-equivalent and FX rate are now visible on the read
    # surface, not only computed silently at aggregation.
    for r in foreign:
        assert r.get("value_in_eur") is not None, r
        assert r.get("fx_rate") is not None, r
    for r in eur:
        assert r.get("value_in_eur") is None
        assert r.get("fx_rate") is None
