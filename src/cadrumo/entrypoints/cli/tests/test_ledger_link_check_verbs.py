"""CLI surface tests for ``aeat app ledger link`` and ``aeat app ledger check``."""

from __future__ import annotations

import json
from collections.abc import Iterator, Sequence
from pathlib import Path

import pytest
from click.testing import Result

from ....core import Period
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_profile_storage_root
from ....tests.user_profile import register_minimal_profile

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _invoke(args: Sequence[str]) -> Result:
    return invoke_cached_cli(args)


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path) -> Iterator[None]:
    from ....application.user_profile import profile_create_storage_span
    from ....application.workflow import workflow_state_repository

    with (
        isolated_profile_storage_root(tmp_path=tmp_path),
        profile_create_storage_span("11111111-1111-4111-8111-111111111111"),
    ):
        workflow_state_repository().update(
            lambda state: register_minimal_profile(state, profile_id="11111111-1111-4111-8111-111111111111"),
        )
        yield


def test_link_requires_invoice_id() -> None:
    """`link` is invoice-only: --invoice-id is required, so a bare call refuses."""

    result = _invoke(["app", "ledger", "link", "0" * 64])
    assert result.exit_code != 0, result.output


def test_link_rejects_removed_evidence_id_grammar() -> None:
    """The retired `--evidence-id` option must be gone: evidence assignment is
    reserved for `aeat app ledger attach`. Passing it is an unknown-option error."""

    result = _invoke(["app", "ledger", "link", "0" * 64, "--invoice-id", "inv-1", "--evidence-id", "ev-123"])
    assert result.exit_code != 0, result.output
    assert "--evidence-id" in result.output or "No such option" in result.output


def test_link_refuses_unknown_transaction_id() -> None:
    """A transaction id absent from the active bucket's catalogue is
    refused before either repository write is attempted."""

    result = _invoke(
        ["app", "ledger", "link", "0" * 64, "--invoice-id", "inv-123"],
    )
    assert result.exit_code != 0, result.output


def test_link_help_advertises_local_only() -> None:
    """Help text must signal `local-only` so the operator cannot mistake
    the verb for an AEAT-contacting call."""

    result = _invoke(["app", "ledger", "link", "--help"])
    assert result.exit_code == 0, result.output
    assert any(token in result.output.lower() for token in ("local-only", "local;", "nunca", "csak helyi")), (
        result.output
    )


def test_link_help_names_catalogue_create_for_invoice_id() -> None:
    """``--invoice-id`` help must name the command that mints linkable ids."""

    result = invoke_cached_cli(["app", "ledger", "link", "--help"], env={"COLUMNS": "240"})

    assert result.exit_code == 0, result.output
    # Whitespace-normalized: Click's plain help formatter wraps prose to the
    # real terminal width, so a multi-word phrase can legitimately span a
    # line break at a word boundary.
    flat = " ".join(result.output.split())
    assert "aeat app ledger invoice catalogue create" in flat
    assert "aeat app ledger invoice add" in flat


def test_check_empty_catalogue_is_ready() -> None:
    """An active bucket with no transactions reports ready=true via the
    no-period audit branch and emits zero issues."""

    result = _invoke(["app", "ledger", "check"])
    assert result.exit_code == 0, result.output
    assert "checked\t0" in result.output
    assert "issues\t0" in result.output
    assert "ready\ttrue" in result.output


def _add_business_expense(*, booked_date: str, idempotency_key: str) -> None:
    result = _invoke(
        [
            "app",
            "ledger",
            "add",
            "--date",
            booked_date,
            "--amount",
            "121.00",
            "--direction",
            "OUTGOING",
            "--description",
            f"business expense {booked_date}",
            "--classification",
            "BUSINESS",
            "--idempotency-key",
            idempotency_key,
        ],
    )
    assert result.exit_code == 0, result.output


def test_check_accepts_period_year_filter_like_status() -> None:
    """`ledger check --period --year` scopes readiness checks to that period."""

    _add_business_expense(booked_date="2026-02-10", idempotency_key="check-q1")
    _add_business_expense(booked_date="2026-05-10", idempotency_key="check-q2")

    period = Period.from_year_and_code(2026, "1T")
    filtered = _invoke(["app", "ledger", "check", "--period", "1T", "--year", "2026"])
    filtered_json = _invoke(
        ["--format", "json", "app", "ledger", "check", "--period", "1T", "--year", "2026"],
    )

    assert filtered.exit_code == 0, filtered.output
    assert filtered_json.exit_code == 0, filtered_json.output
    assert f"periods\t{period}" in filtered.output
    assert "1T 2026" not in filtered.output
    assert "checked\t1" in filtered.output
    assert "ready\tfalse" in filtered.output
    assert json.loads(filtered_json.output)["result"]["periods"] == [str(period)]

    unfiltered = _invoke(["app", "ledger", "check"])
    assert unfiltered.exit_code == 0, unfiltered.output
    assert "periods\t2026" in unfiltered.output
    assert "checked\t2" in unfiltered.output


def test_check_period_without_year_refuses_like_status() -> None:
    """`ledger check --period 1T` refuses with the same --year guidance."""

    result = _invoke(["app", "ledger", "check", "--period", "1T"])

    assert result.exit_code != 0, result.output
    assert "--year" in result.output


def test_check_help_advertises_local_only() -> None:
    """Help text must signal `local-only`."""

    result = _invoke(["app", "ledger", "check", "--help"])
    assert result.exit_code == 0, result.output
    assert any(token in result.output.lower() for token in ("local-only", "local;", "nunca", "csak helyi")), (
        result.output
    )
    assert "--period" in result.output
    assert "--year" in result.output
    assert "1T" in result.output


def test_check_refuses_foreign_bucket_id_without_unlocked_session() -> None:
    """`--bucket-id` must not bypass the active profile storage session."""

    result = _invoke(
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


def test_link_refuses_operator_invoice_add_id_instructively() -> None:
    """`link --invoice-id` must refuse an id minted by ``invoice add``.

    The slim operator-CRUD ``BusinessOperationInvoice`` store (filled by
    ``invoice add``) and the rich reconciliation ``InvoiceCatalogue`` that
    ``link --invoice-id`` targets are intentionally distinct: only the rich
    ``Invoice`` carries ``linked_transaction_ids``. An ``invoice add`` id is
    therefore not a valid ``--invoice-id`` target. This is a documented sharp
    edge, deliberate so the two stores are never unified by mistake, and it is
    the runtime fact the ledger-evidence how-to must reflect.

    The refusal must be the instructive typed message that names the ``invoice
    add`` provenance and points at the evidence/attach path — never a silent
    accept, a raw traceback, or a bare "value invalid".
    """
    added = _invoke(
        [
            "app", "ledger", "add",
            "--date", "2026-03-10", "--amount", "121.00",
            "--direction", "OUTGOING", "--description", "Supplier payment B12345678",
        ],
    )  # fmt: skip
    assert added.exit_code == 0, added.output
    transaction_id = _line_value(added.output, "ID")

    invoice = _invoke(
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

    linked = _invoke(
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
    assert "invoice catalogue create" in lowered, linked.output
    assert "evidenc" in lowered, linked.output
    assert "traceback" not in lowered, linked.output


def test_check_reports_zero_link_inconsistencies_on_a_consistent_bucket() -> None:
    """A bucket whose invoice links agree reports the channel as empty.

    The link-integrity channel is period-independent, so it appears on the
    no-period audit branch alongside the readiness issues.
    """

    result = _invoke(["--format", "json", "app", "ledger", "check"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["result"]["link_inconsistencies"] == []
    assert payload["result"]["ready"] is True
    assert payload["notices"] == []


def test_check_reports_a_one_sided_invoice_link(tmp_path: Path) -> None:
    """A half-written link is surfaced as a row, a warning notice, and ready=false.

    The link writer commits both catalogues together, so this state is no
    longer reachable through the CLI; it is reproduced here at the repository
    boundary to prove the operator can discover the drift if it ever arises
    (from an interrupted pre-atomic write, or an out-of-band edit).
    """
    from ....adapters.persistence.profile.invoices import InvoiceCatalogueRepository
    from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
    from ....domain.transactions import TransactionCatalogue

    added = _invoke(
        [
            "app", "ledger", "add",
            "--date", "2026-03-10", "--amount", "121.00",
            "--direction", "OUTGOING", "--description", "Supplier payment B12345674",
            "--idempotency-key", "check-link-drift",
        ],
    )  # fmt: skip
    assert added.exit_code == 0, added.output
    transaction_id = _line_value(added.output, "ID")

    created = _invoke(
        [
            "app", "ledger", "invoice", "catalogue", "create",
            "--kind", "received",
            "--counterparty-nif", "B12345674",
            "--counterparty-name", "Proveedor SL",
            "--invoice-number", "2026-0143",
            "--invoice-date", "2026-03-10",
            "--taxable-base", "100.00", "--iva-rate", "21",
        ],
    )  # fmt: skip
    assert created.exit_code == 0, created.output
    invoice_id = _line_value(created.output, "invoice_id")

    linked = _invoke(["app", "ledger", "link", transaction_id, "--invoice-id", invoice_id])
    assert linked.exit_code == 0, linked.output

    # Drop the transaction side of the link, leaving the invoice citing it.
    bucket_id = "11111111-1111-4111-8111-111111111111"
    transactions_repo = TransactionCatalogueRepository(bucket_id=bucket_id)
    catalogue = transactions_repo.load()
    linked_transaction = catalogue.get(transaction_id)
    assert linked_transaction is not None
    unlinked = linked_transaction.model_copy(update={"invoice_id": None})
    transactions_repo.save(TransactionCatalogue.from_transactions([unlinked]))
    invoice = InvoiceCatalogueRepository(bucket_id=bucket_id).load().get(invoice_id)
    assert invoice is not None
    assert invoice.linked_transaction_ids == (transaction_id,)

    result = _invoke(["--format", "json", "app", "ledger", "check"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    rows = payload["result"]["link_inconsistencies"]
    assert rows == [
        {"invoice_id": invoice_id, "transaction_id": transaction_id, "direction": "invoice-only"},
    ]
    assert payload["result"]["ready"] is False
    codes = [notice["code"] for notice in payload["notices"]]
    assert "ledger.check.link_inconsistency" in codes
    notice = next(item for item in payload["notices"] if item["code"] == "ledger.check.link_inconsistency")
    assert notice["severity"] == "warning"
    assert notice["suggestion"] == "aeat app ledger link"
    assert notice["context"] == {"link_inconsistency_count": "1"}
