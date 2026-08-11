"""Shared real-CLI harness for ledger validation-path tests."""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from pathlib import Path

from click.testing import Result

from ....adapters.persistence.storage.sql.engine import dispose_engine
from ....application.user_profile import profile_create_storage_span, set_active_fields
from ....application.workflow import workflow_state_repository
from ....core.config import override_settings
from ....domain.user_profile import UserProfileFact
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_profile_storage_root
from ....tests.user_profile import register_minimal_profile

_PROFILE_ID = "9e0f3a2b-5d1c-4a77-9b2d-27ed6d6c7f10"
_PROFILE_LABEL = "tester"


def _invoke(args: Sequence[str], *, env: Mapping[str, str] | None = None) -> Result:
    return invoke_cached_cli(args, env=env)


@contextmanager
def open_bucket_session(tmp_path: Path) -> Iterator[None]:
    dispose_engine()
    with (
        override_settings(cadrumo_local_storage_root=tmp_path, cadrumo_output_language="en"),
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
        newline="\n",
    )
    imported = _invoke(["app", "ledger", "import", "--file", str(statement), "--provider", "csv"])
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


#: The IVA axes the deadlines profile demands before it will answer for a
#: taxpayer, with the values of an ordinary general-regime filer.
#:
#: The composition is the one axis with no defensible default -- an undeclared
#: composition is not a general one -- and the four booleans are opt-in special
#: regimes this taxpayer is not in. They are declared together because the
#: profile refuses on the whole set: satisfying one surfaces the next, which
#: reads as a sequence of unrelated failures rather than one incomplete
#: profile.
_GENERAL_REGIME_IVA_AXES: tuple[tuple[str, str | bool], ...] = (
    ("iva.m303_regime_composition", "general"),
    ("iva.redeme_enrolled", False),
    ("iva.cash_accounting_regime_enrolled", False),
    ("iva.voluntary_sii_enrolled", False),
    ("iva.hydrocarbon_deposit_advance_payment_deduction_entitled", False),
)


def _declare_general_regime_iva_profile() -> None:
    """Complete the minimal profile's IVA block for a general-regime filer.

    ``register_minimal_profile`` deliberately registers the smallest profile
    that can hold a bucket, which does not include the IVA axes. Any CLI path
    that resolves an IVA treatment -- notably ``evidence confirm`` -- then
    refuses with an incomplete-profile error before reaching the behaviour
    under test, so a suite exercising that path must declare them.

    Written in ONE update rather than one per axis, so the profile is never
    observed half-declared by anything reading between writes.
    """
    workflow_state_repository().update(
        lambda state: set_active_fields(
            state,
            tuple(UserProfileFact(path=path, value=value) for path, value in _GENERAL_REGIME_IVA_AXES),
        ),
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
        env={"CADRUMO_OUTPUT_LANGUAGE": "en"},
    )
    assert result.exit_code == 0, result.output
    return json.loads(result.output)["result"]["transaction_id"]


def _flatten_box(text: str) -> str:
    return " ".join(text.replace("│", " ").split())


def _assert_pipeline_managed_state_refusal(flat: str, output: str) -> None:
    assert "set automatically" in flat, output
    assert "cannot be assigned by hand" in flat, output
    assert "BUSINESS, PERSONAL, MIXED" in flat, output
