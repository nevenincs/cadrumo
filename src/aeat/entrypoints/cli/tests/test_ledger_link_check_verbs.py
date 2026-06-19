"""CLI surface tests for ``aeat app ledger link`` and ``aeat app ledger check``."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ....application.user_profile._orchestration import profile_create_storage_span
from ....application.user_profile._testing import register_minimal_profile
from ....application.workflow._persistence import workflow_state_repository
from ....tests.secure_sql import isolated_profile_storage_root
from .. import app

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path) -> Iterator[None]:
    with (
        isolated_profile_storage_root(tmp_path=tmp_path),
        profile_create_storage_span("operator"),
    ):
        workflow_state_repository().update(
            lambda state: register_minimal_profile(state, profile_id="operator"),
        )
        yield


def test_link_requires_at_least_one_target(cli_runner: CliRunner) -> None:
    """Neither --invoice-id nor --evidence-id supplied surfaces as
    BadParameter; the canonical call is meant to bind something."""

    result = cli_runner.invoke(app, ["app", "ledger", "link", "0" * 64])
    assert result.exit_code != 0, result.output


def test_link_refuses_unknown_transaction_id(cli_runner: CliRunner) -> None:
    """A transaction id absent from the active bucket's catalogue is
    refused before either repository write is attempted."""

    result = cli_runner.invoke(
        app,
        ["app", "ledger", "link", "0" * 64, "--evidence-id", "ev-123"],
    )
    assert result.exit_code != 0, result.output


def test_link_help_advertises_local_only(cli_runner: CliRunner) -> None:
    """Help text must signal `local-only` so the operator cannot mistake
    the verb for an AEAT-contacting call."""

    result = cli_runner.invoke(app, ["app", "ledger", "link", "--help"])
    assert result.exit_code == 0, result.output
    assert any(token in result.output.lower() for token in ("local-only", "local;", "nunca", "csak helyi")), (
        result.output
    )


def test_check_empty_catalogue_is_ready(cli_runner: CliRunner) -> None:
    """An active bucket with no transactions reports ready=true via the
    no-period audit branch and emits zero issues."""

    result = cli_runner.invoke(app, ["app", "ledger", "check"])
    assert result.exit_code == 0, result.output
    assert "checked\t0" in result.output
    assert "issues\t0" in result.output
    assert "ready\ttrue" in result.output


def test_check_help_advertises_local_only(cli_runner: CliRunner) -> None:
    """Help text must signal `local-only`."""

    result = cli_runner.invoke(app, ["app", "ledger", "check", "--help"])
    assert result.exit_code == 0, result.output
    assert any(token in result.output.lower() for token in ("local-only", "local;", "nunca", "csak helyi")), (
        result.output
    )


def test_check_refuses_foreign_bucket_id_without_unlocked_session(cli_runner: CliRunner) -> None:
    """`--bucket-id` must not bypass the active profile storage session."""

    result = cli_runner.invoke(
        app,
        ["app", "ledger", "check", "--bucket-id", "some-other-bucket"],
    )
    assert result.exit_code != 0, result.output
    assert "Storage runtime is not ready" in result.output


def _line_value(output: str, key: str) -> str:
    """Return the value of one ``key\\tvalue`` line in CLI text output."""
    for line in output.splitlines():
        head, sep, tail = line.partition("\t")
        if sep and head.strip() == key:
            return tail.strip()
    raise AssertionError(f"no {key!r} line in CLI output:\n{output}")


def test_link_refuses_operator_invoice_add_id_instructively(cli_runner: CliRunner) -> None:
    """`link --invoice-id` must refuse an id minted by ``invoice add``.

    Per the accepted ``2026-06-10-ledger-invoice-unification-adr`` the slim
    operator-CRUD ``BusinessOperationInvoice`` store (filled by ``invoice add``)
    and the rich reconciliation ``InvoiceCatalogue`` that ``link --invoice-id``
    targets are intentionally distinct: only the rich ``Invoice`` carries
    ``linked_transaction_ids``. An ``invoice add`` id is therefore not a valid
    ``--invoice-id`` target. This is the "documented sharp edge" the ADR fixes
    explicitly so a future agent does not unify the two stores by mistake, and
    it is the runtime fact the ledger-evidence how-to must reflect (audit M17).

    The refusal must be the instructive typed message that names the ``invoice
    add`` provenance and points at the evidence/attach path — never a silent
    accept, a raw traceback, or a bare "value invalid".
    """
    added = cli_runner.invoke(
        app,
        [
            "app", "ledger", "add",
            "--date", "2026-03-10", "--amount", "121.00",
            "--direction", "OUTGOING", "--description", "Supplier payment B12345678",
        ],
    )  # fmt: skip
    assert added.exit_code == 0, added.output
    transaction_id = _line_value(added.output, "ID")

    invoice = cli_runner.invoke(
        app,
        [
            "app", "ledger", "invoice", "add",
            "--kind", "received",
            "--counterparty-nif", "B12345678",
            "--invoice-number", "2026-0142",
            "--invoice-date", "2026-03-10",
            "--taxable-base", "100.00", "--iva-rate", "21",
            "--iva-amount", "21.00", "--total-amount", "121.00",
        ],
    )  # fmt: skip
    assert invoice.exit_code == 0, invoice.output
    invoice_add_id = _line_value(invoice.output, "invoice_id")

    linked = cli_runner.invoke(
        app,
        ["app", "ledger", "link", transaction_id, "--invoice-id", invoice_add_id],
    )

    # The documented `invoice add` -> `link --invoice-id` chain is refused.
    assert linked.exit_code != 0, linked.output
    lowered = linked.output.lower()
    # Instructive: the refusal names the `invoice add` provenance and routes the
    # operator to the evidence path — not a bare invalid or a Python traceback.
    # The shipped message is localized, so match the language-stable command
    # token plus the shared evidence/`evidencia` stem rather than English prose.
    assert "invoice add" in lowered, linked.output
    assert "evidenc" in lowered, linked.output
    assert "traceback" not in lowered, linked.output
