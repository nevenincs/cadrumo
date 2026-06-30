"""Shared real-CLI harness for ledger validation-path tests."""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from pathlib import Path

from click.testing import Result

from ....adapters.persistence.storage.sql.engine import dispose_engine
from ....application.user_profile._orchestration import profile_create_storage_span, set_active_fields
from ....application.user_profile._testing import register_minimal_profile
from ....application.workflow._persistence import workflow_state_repository
from ....core.config import override_settings
from ....domain.user_profile import UserProfileFact
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_profile_storage_root

_PROFILE_ID = "9e0f3a2b-5d1c-4a77-9b2d-27ed6d6c7f10"
_PROFILE_LABEL = "tester"


def _invoke(args: Sequence[str], *, env: Mapping[str, str] | None = None) -> Result:
    return invoke_cached_cli(args, env=env)


@contextmanager
def open_bucket_session(tmp_path: Path) -> Iterator[None]:
    dispose_engine()
    with (
        override_settings(aeat_local_storage_root=tmp_path, aeat_output_language="en"),
        isolated_profile_storage_root(tmp_path=tmp_path),
        profile_create_storage_span(_PROFILE_ID),
    ):
        workflow_state_repository().update(
            lambda state: register_minimal_profile(
                state,
                profile_id=_PROFILE_ID,
                display_name=_PROFILE_LABEL,
            ),
        )
        try:
            yield
        finally:
            dispose_engine()


def _create_profile_and_import(tmp_path: Path) -> str:
    statement = tmp_path / "statement.csv"
    statement.write_text(
        "Date,Payee,Payment reference,Amount (EUR),Currency,Transaction ID\n"
        "2026-04-15,Client SL,Invoice 1,-50.00,EUR,n26-001\n",
        encoding="utf-8",
    )
    imported = _invoke(["app", "ledger", "import", str(statement), "--provider", "csv"])
    assert imported.exit_code == 0, imported.output

    listed = _invoke(["--format", "json", "app", "ledger", "list"])
    assert listed.exit_code == 0, listed.output
    payload = json.loads(listed.output)
    rows = payload.get("result", payload).get("rows", [])
    assert rows, listed.output
    return rows[0]["transaction_id"]


def _set_profile_axis(key: str, value: str) -> None:
    workflow_state_repository().update(
        lambda state: set_active_fields(state, (UserProfileFact(path=key, value=value),)),
    )


def _add_eligible_mixed_expense() -> str:
    result = _invoke(
        [
            "--format",
            "json",
            "app",
            "ledger",
            "add",
            "--date",
            "2026-02-10",
            "--amount",
            "60.50",
            "--direction",
            "OUTGOING",
            "--description",
            "phone bill",
            "--taxable-base",
            "50.00",
            "--iva-rate",
            "0.21",
            "--iva-amount",
            "10.50",
        ],
        env={"AEAT_OUTPUT_LANGUAGE": "en"},
    )
    assert result.exit_code == 0, result.output
    return json.loads(result.output)["result"]["transaction_id"]


def _flatten_box(text: str) -> str:
    return " ".join(text.replace("│", " ").split())


def _assert_pipeline_managed_state_refusal(flat: str, output: str) -> None:
    assert "set automatically" in flat, output
    assert "cannot be assigned by hand" in flat, output
    assert "BUSINESS, PERSONAL, MIXED" in flat, output
