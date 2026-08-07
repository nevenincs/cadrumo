"""CLI regression for the catalogue-invoice ``view`` and ``remove`` verbs.

The reconciliation catalogue gained ``create`` and ``list`` operator verbs but
no single-record read or delete. Without ``view`` an operator cannot confirm
the long content-addressed ``invoice_id`` that ``link --invoice-id`` resolves;
without ``remove`` a mistaken ``create`` is permanent. These tests exercise the
now-working verbs through the live Typer tree against a real encrypted bucket
session — no mocks, stubs, or monkeypatch — and pin the refusals:

* ``view`` resolves a full id and an unambiguous prefix, and refuses an unknown
  id with the localized not-found message;
* ``remove`` requires ``--yes``, deletes an unlinked invoice, and refuses an
  invoice that still carries linked transactions (the bidirectional link must
  never be silently orphaned).
"""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ....application.user_profile import profile_create_storage_span
from ....application.workflow import workflow_state_repository
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_profile_storage_root
from ....tests.user_profile import register_minimal_profile

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_RECEIVED_COUNTERPARTY_CIF = "A58818501"


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path) -> Iterator[None]:
    with (
        isolated_profile_storage_root(tmp_path=tmp_path),
        profile_create_storage_span("11111111-1111-4111-8111-111111111111"),
    ):
        workflow_state_repository().update(
            lambda state: register_minimal_profile(state, profile_id="11111111-1111-4111-8111-111111111111"),
        )
        yield


def _line_value(output: str, key: str) -> str:
    for line in output.splitlines():
        head, sep, tail = line.partition("\t")
        if sep and head.strip() == key:
            return tail.strip()
    raise AssertionError(f"no {key!r} line in CLI output:\n{output}")


def _create_catalogue_invoice(*, invoice_number: str = "2026-0142") -> str:
    result = invoke_cached_cli(
        [
            "app", "ledger", "invoice", "add",
            "--kind", "received",
            "--counterparty-nif", _RECEIVED_COUNTERPARTY_CIF,
            "--counterparty-name", "Papeleria Sol SL",
            "--invoice-number", invoice_number,
            "--invoice-date", "2026-03-10",
            "--country-code", "ES",
            "--taxable-base", "100.00", "--iva-rate", "21",
        ],
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    invoice_id = _line_value(result.output, "invoice_id")
    assert len(invoice_id) == 64, invoice_id
    return invoice_id


def test_catalogue_create_records_a_retention_amount() -> None:
    """``catalogue create`` (#66) persists a declared RIRPF art. 95 retención.

    Neither catalogue-invoice creation path could set ``retention_rate`` /
    ``retention_amount`` before this wiring, so a received invoice's
    withholding could never be recorded through the CLI at all.
    """
    result = invoke_cached_cli(
        [
            "app", "ledger", "invoice", "add",
            "--kind", "received",
            "--counterparty-nif", _RECEIVED_COUNTERPARTY_CIF,
            "--counterparty-name", "Asesoria Profesional SL",
            "--invoice-number", "2026-RETENCION-001",
            "--invoice-date", "2026-03-10",
            "--country-code", "ES",
            "--taxable-base", "1000.00", "--iva-rate", "21",
            "--retention-rate", "0.15", "--retention-amount", "150.00",
        ],
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    invoice_id = _line_value(result.output, "invoice_id")

    stored = InvoiceCatalogueRepository().load().get(invoice_id)
    assert stored is not None
    assert stored.retention_rate == Decimal("0.15")
    assert stored.retention_amount == Decimal("150.00")


def test_catalogue_create_refuses_a_retention_rate_without_an_amount() -> None:
    """A rate alone is refused at the CLI boundary, not silently dropped."""
    result = invoke_cached_cli(
        [
            "app", "ledger", "invoice", "add",
            "--kind", "received",
            "--counterparty-nif", _RECEIVED_COUNTERPARTY_CIF,
            "--counterparty-name", "Asesoria Profesional SL",
            "--invoice-number", "2026-RETENCION-002",
            "--invoice-date", "2026-03-10",
            "--country-code", "ES",
            "--taxable-base", "1000.00", "--iva-rate", "21",
            "--retention-rate", "0.15",
        ],
    )  # fmt: skip
    assert result.exit_code != 0, result.output
    assert "retention_rate" in result.output
    assert "retention_amount" in result.output


def test_catalogue_view_resolves_full_id_and_prefix() -> None:
    """``view`` shows one catalogue invoice by full id and by unambiguous prefix."""
    invoice_id = _create_catalogue_invoice()

    by_full = invoke_cached_cli(["app", "ledger", "invoice", "view", invoice_id])
    assert by_full.exit_code == 0, by_full.output
    assert _line_value(by_full.output, "invoice_id") == invoice_id

    by_prefix = invoke_cached_cli(["app", "ledger", "invoice", "view", invoice_id[:8]])
    assert by_prefix.exit_code == 0, by_prefix.output
    assert _line_value(by_prefix.output, "invoice_id") == invoice_id


def test_catalogue_view_refuses_unknown_id() -> None:
    """An id matching no invoice is refused, naming the id — never a silent miss."""
    _create_catalogue_invoice()
    result = invoke_cached_cli(
        ["app", "ledger", "invoice", "view", "deadbeefdeadbeef"],
    )
    assert result.exit_code != 0, result.output
    assert "deadbeefdeadbeef" in result.output, result.output


def test_catalogue_remove_requires_confirmation() -> None:
    """``remove`` without ``--yes`` is refused and leaves the record intact."""
    invoice_id = _create_catalogue_invoice()

    result = invoke_cached_cli(["app", "ledger", "invoice", "remove", invoice_id])
    assert result.exit_code != 0, result.output

    # The unconfirmed refusal deleted nothing.
    assert InvoiceCatalogueRepository().load().get(invoice_id) is not None


def test_catalogue_remove_deletes_unlinked_invoice() -> None:
    """``remove --yes`` deletes an unlinked invoice and the deletion persists."""
    invoice_id = _create_catalogue_invoice()

    result = invoke_cached_cli(
        ["app", "ledger", "invoice", "remove", invoice_id[:8], "--yes"],
    )
    assert result.exit_code == 0, result.output
    assert _line_value(result.output, "invoice_id") == invoice_id

    assert InvoiceCatalogueRepository().load().get(invoice_id) is None


def test_catalogue_remove_refuses_linked_invoice() -> None:
    """``remove`` refuses an invoice still linked to a transaction.

    Deleting it from the catalogue alone would leave the transaction side citing
    a vanished invoice; the verb refuses and the record stays put. The full
    create -> link -> remove chain is exercised through the CLI.
    """
    add = invoke_cached_cli(
        [
            "app", "ledger", "add",
            "--date", "2026-03-10", "--amount", "121.00",
            "--direction", "OUTGOING", "--description", f"Supplier {_RECEIVED_COUNTERPARTY_CIF}",
        ],
    )  # fmt: skip
    assert add.exit_code == 0, add.output
    transaction_id = _line_value(add.output, "ID")

    invoice_id = _create_catalogue_invoice()
    linked = invoke_cached_cli(
        ["app", "ledger", "link", transaction_id, "--invoice-id", invoice_id],
    )
    assert linked.exit_code == 0, linked.output

    removed = invoke_cached_cli(
        ["app", "ledger", "invoice", "remove", invoice_id, "--yes"],
    )
    assert removed.exit_code != 0, removed.output
    assert transaction_id in removed.output, removed.output

    # The linked invoice was not deleted and still cites the transaction.
    stored = InvoiceCatalogueRepository().load().get(invoice_id)
    assert stored is not None
    assert stored.linked_transaction_ids == (transaction_id,), stored.linked_transaction_ids


def test_catalogue_create_refuses_an_omitted_country_code() -> None:
    """``--country-code`` is mandatory, because it routes both informativas.

    Both canonical entry verbs used to default it to ``ES``. The slim verb they
    replace defaults it to nothing and either derives the country from the EU
    VAT-ID prefix or raises, so repointing the operator's bare verbs onto the
    canonical aggregate would have converted a derive-or-raise into a silent
    domestic assumption.

    A silent ``ES`` is not a cosmetic default on this axis. The M347 projection
    filters on the counterparty country being ``ES``, so a foreign invoice
    stamped domestic is pulled INTO M347 and can carry a party over the
    declaration floor, while M349 declares the wrong member state. The
    canonical record has no EU VAT-ID field to derive a country from -- by
    design, since the tax id already IS the NIF-IVA for a non-ES country -- so
    the honest remedy is to require the operator to state it.
    """
    result = invoke_cached_cli(
        [
            "app", "ledger", "invoice", "add",
            "--kind", "received",
            "--counterparty-nif", _RECEIVED_COUNTERPARTY_CIF,
            "--counterparty-name", "Papeleria Sol SL",
            "--invoice-number", "2026-NOCOUNTRY-001",
            "--invoice-date", "2026-03-10",
            "--taxable-base", "100.00", "--iva-rate", "21",
        ],
    )  # fmt: skip

    assert result.exit_code != 0, result.output
    # Names the missing option rather than failing generically, so the operator
    # is told what to supply instead of being left to guess.
    assert "--country-code" in result.output


def test_catalogue_create_still_accepts_an_explicit_domestic_country_code() -> None:
    """Positive control for the refusal above.

    A gate that refuses everything passes its own negative test and is worse
    than no gate, so the domestic case an operator previously got by omission
    must still succeed when it is stated explicitly.
    """
    result = invoke_cached_cli(
        [
            "app", "ledger", "invoice", "add",
            "--kind", "received",
            "--counterparty-nif", _RECEIVED_COUNTERPARTY_CIF,
            "--counterparty-name", "Papeleria Sol SL",
            "--invoice-number", "2026-WITHCOUNTRY-001",
            "--invoice-date", "2026-03-10",
            "--country-code", "ES",
            "--taxable-base", "100.00", "--iva-rate", "21",
        ],
    )  # fmt: skip

    assert result.exit_code == 0, result.output
    assert len(_line_value(result.output, "invoice_id")) == 64


def test_catalogue_create_accepts_every_regime_option_and_holds_the_totals_identity() -> None:
    """All four regime axes are expressible from the CLI, and the identity holds.

    Before these options existed every canonically-written invoice was
    ORDINARIA with no series and no recargo by construction, and a
    rectificativa could not be entered at all -- so an operator could not
    express a regime the aggregate had always modelled.

    The identity asserted here is the one the decomposition ADR pins:
    grand_total equals base plus cuota plus recargo, with the retención
    OUTSIDE it. A recargo is charged on top of the cuota and is collected from
    the customer; a retención is withheld from the payment. Putting the
    retención inside the total would overstate what the customer owes, and
    putting the recargo outside it would understate the invoice.
    """
    result = invoke_cached_cli(
        [
            "app", "ledger", "invoice", "add",
            "--kind", "issued",
            "--counterparty-nif", "B12345674",
            "--counterparty-name", "Minorista Recargo SL",
            "--invoice-number", "2026-REG-001",
            "--invoice-date", "2026-05-04",
            "--country-code", "ES",
            "--taxable-base", "1000.00", "--iva-rate", "21",
            "--invoice-class", "RECTIFICATIVA",
            "--series", "R",
            "--rectifies-invoice-number", "2026-0044",
            "--recargo", "52.00",
            "--iva-category", "domestic_general",
        ],
    )  # fmt: skip

    assert result.exit_code == 0, result.output
    assert _line_value(result.output, "invoice_class") == "RECTIFICATIVA"
    assert _line_value(result.output, "series") == "R"
    assert _line_value(result.output, "recargo_amount") == "52.00"
    # 1000 base + 210 cuota + 52 recargo, the recargo INSIDE the total.
    assert _line_value(result.output, "grand_total") == "1262.00"


def test_catalogue_create_refuses_an_unknown_invoice_class_naming_the_accepted_set() -> None:
    """A closed axis must instruct on parse failure, never fail bare.

    The option is typed on the enum so click renders the accepted set rather
    than leaving the operator to guess, which is the CLI boundary's job for
    every closed value set.
    """
    result = invoke_cached_cli(
        [
            "app", "ledger", "invoice", "add",
            "--kind", "issued",
            "--counterparty-nif", "B12345674",
            "--counterparty-name", "Cliente SL",
            "--invoice-number", "2026-REG-002",
            "--invoice-date", "2026-05-04",
            "--country-code", "ES",
            "--taxable-base", "1000.00", "--iva-rate", "21",
            "--invoice-class", "no-such-class",
        ],
    )  # fmt: skip

    assert result.exit_code != 0
    assert "RECTIFICATIVA" in result.output
