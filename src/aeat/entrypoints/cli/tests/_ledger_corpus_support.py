"""Shared helpers for ledger-corpus CLI journey tests."""

from __future__ import annotations

import json
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Any

import pytest
from click.testing import Result

from ....adapters.persistence.storage.sql.engine import dispose_engine
from ....application.user_profile._orchestration import profile_create_storage_span
from ....application.user_profile._testing import register_minimal_profile
from ....application.workflow._persistence import workflow_state_repository
from ....core.config import override_settings
from ....domain.calculations.registry import CasillaId, validated_casilla_id
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_profile_storage_root

_CORPUS = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "financial" / "ledger-corpus"
_FILES = (
    "bbva-business-eur.csv",
    "caixabank-personal.csv",
    "revolut-multi.csv",
    "n26-savings.csv",
)
_FIN_FIXTURES = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "financial"


def _invoke(args: Sequence[str]) -> Result:
    return invoke_cached_cli(args)


def _casilla_id(value: object) -> CasillaId:
    try:
        return validated_casilla_id(value, surface="test casilla id")
    except ValueError as exc:
        raise AssertionError(f"ledger corpus journey fixture casilla key {value!r} is not a CasillaId") from exc


_REVISION_CASILLA: CasillaId = _casilla_id("01")


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path) -> Iterator[None]:
    dispose_engine()
    with (
        override_settings(aeat_local_storage_root=tmp_path, aeat_output_language="en"),
        isolated_profile_storage_root(tmp_path=tmp_path),
        profile_create_storage_span("00000000-0000-4000-8000-000000000000"),
    ):
        try:
            workflow_state_repository().update(
                lambda state: register_minimal_profile(state, profile_id="00000000-0000-4000-8000-000000000000")
            )
            yield
        finally:
            dispose_engine()


def _oracle_rules() -> list[dict[str, Any]]:
    manifest = json.loads((_CORPUS / "ground-truth.manifest.json").read_text(encoding="utf-8"))
    return manifest["rules"]


def _match(description: str, rules: list[dict[str, Any]]) -> dict[str, Any] | None:
    for rule in rules:
        if rule["match"] in description:
            return rule
    return None


def _import_corpus() -> int:
    total = 0
    for name in _FILES:
        result = _invoke(["app", "ledger", "import", str(_CORPUS / name), "--provider", "csv"])
        assert result.exit_code == 0, f"{name}: {result.output}"
        total += 1
    return total


def _import_bbva() -> None:
    """Lighter import (single business account) for row-targeted journeys."""
    result = _invoke(
        ["app", "ledger", "import", str(_CORPUS / "bbva-business-eur.csv"), "--provider", "csv"],
    )
    assert result.exit_code == 0, result.output


def _list_rows() -> list[dict[str, Any]]:
    listed = _invoke(["--format", "json", "app", "ledger", "list"])
    assert listed.exit_code == 0, listed.output
    payload = json.loads(listed.output)
    return payload.get("result", payload).get("rows", [])


def _list_payload(*args: str) -> dict[str, Any]:
    listed = _invoke(["--format", "json", "app", "ledger", "list", *args])
    assert listed.exit_code == 0, listed.output
    payload = json.loads(listed.output)
    return payload.get("result", payload)


def _find(rows: list[dict[str, Any]], needle: str) -> dict[str, Any]:
    return next(r for r in rows if needle in r["description"])


def _set_group(tx_id: str, label: str) -> None:
    result = _invoke(["app", "ledger", "update", tx_id, "--group", label])
    assert result.exit_code == 0, result.output


def _active_repo() -> Any:
    from ....core import resolve_active_bucket_id
    from ....domain.transactions import TransactionCatalogueRepository

    bucket_id = resolve_active_bucket_id()
    assert bucket_id is not None
    return TransactionCatalogueRepository(bucket_id=bucket_id)


def _xlsx_mirror_of_csv(csv_path: Path, out: Path) -> None:
    """Write a faithful XLSX mirror of a ';'-delimited bank CSV.

    Every cell is the verbatim CSV string so the XLSX provider (which shares the
    CSV bank-layout catalogue and Spanish ',' decimal parsing) parses each row
    identically to the CSV provider, yielding identical content-addressed ids.
    """
    from openpyxl import Workbook

    workbook = Workbook()
    sheet = workbook.active
    assert sheet is not None
    for line in csv_path.read_text(encoding="utf-8").splitlines():
        sheet.append(line.split(";"))
    workbook.save(out)
