"""CLI regression for the catalogue-invoice ``view`` and ``remove`` verbs.

The reconciliation catalogue gained ``create`` and ``list`` operator verbs but
no single-record read or delete. Without ``view`` an operator cannot confirm
the long content-addressed ``invoice_id`` that ``link --invoice-id`` resolves;
without ``remove`` a mistaken ``create`` is permanent. These tests exercise the
now-working verbs through the live Typer tree, an enrolled exact-profile
worker, and the real encrypted catalogue, and pin the refusals:

* ``view`` resolves a full id and an unambiguous prefix, and refuses an unknown
  id with the localized not-found message;
* ``remove`` requires ``--yes``, deletes an unlinked invoice, and refuses an
  invoice that still carries linked transactions (the bidirectional link must
  never be silently orphaned).
"""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path
from typing import cast

import pytest
from click.testing import Result

from ....application.invoices.catalogue_add_operation import (
    INVOICE_ADD_OPERATION_DEFINITION_ID,
    INVOICE_ADD_VALIDATION_REFUSAL_CODE,
)
from ....application.invoices.catalogue_read_operation import INVOICE_VIEW_OPERATION_DEFINITION_ID
from ....application.invoices.catalogue_remove_operation import INVOICE_REMOVE_OPERATION_DEFINITION_ID
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....tests.cli_envelope import require_error_document
from ._cli_text_output_support import _line_value
from ._isolated_profile_storage_fixtures import active_profile_isolated_backend
from .cli_runner import invoke_cached_cli
from .native_api_cli_support import NativeApiCliSession
from .test_runtime_invoice_add import catalogue_after_password_login, native_invoice_runtime_session

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.usefixtures("authority_operation"),
]
__all__ = ["active_profile_isolated_backend"]

_RECEIVED_COUNTERPARTY_CIF = "A58818501"
_RUNTIME_OPERATIONS = frozenset(
    {
        INVOICE_ADD_OPERATION_DEFINITION_ID,
        INVOICE_VIEW_OPERATION_DEFINITION_ID,
        INVOICE_REMOVE_OPERATION_DEFINITION_ID,
    }
)


def _create_catalogue_invoice(session: NativeApiCliSession[None], *, invoice_number: str = "2026-0142") -> str:
    result = session.invoke_password(
        "app", "ledger", "invoice", "add",
        "--kind", "received",
        "--counterparty-nif", _RECEIVED_COUNTERPARTY_CIF,
        "--counterparty-name", "Papeleria Sol SL",
        "--invoice-number", invoice_number,
        "--invoice-date", "2026-03-10",
        "--country-code", "ES",
        "--taxable-base", "100.00", "--iva-rate", "21",
        output_format="text",
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    invoice_id = _line_value(result.output, "invoice_id")
    assert len(invoice_id) == 64, invoice_id
    return invoice_id


def _invoke_open_profile(session: NativeApiCliSession[None], *command: str) -> Result:
    """Run a later command in the already-open profile without new auth input."""
    return invoke_cached_cli(("--format", "text", "--profile", session.profile_label, *command))


@pytest.mark.windows_only
@pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers")
def test_catalogue_create_records_a_retention_amount(
    authority_operation: PinnedAuthorityOperation, tmp_path: Path
) -> None:
    """``catalogue create`` (#66) persists a declared RIRPF art. 95 retención.

    Neither catalogue-invoice creation path could set ``retention_rate`` /
    ``retention_amount`` before this wiring, so a received invoice's
    withholding could never be recorded through the CLI at all.
    """
    with native_invoice_runtime_session(tmp_path, operation_ids=_RUNTIME_OPERATIONS) as session:
        result = session.invoke_password(
            "app", "ledger", "invoice", "add",
            "--kind", "received",
            "--counterparty-nif", _RECEIVED_COUNTERPARTY_CIF,
            "--counterparty-name", "Asesoria Profesional SL",
            "--invoice-number", "2026-RETENCION-001",
            "--invoice-date", "2026-03-10",
            "--country-code", "ES",
            "--taxable-base", "1000.00", "--iva-rate", "21",
            "--retention-rate", "0.15", "--retention-amount", "150.00",
            output_format="text",
        )  # fmt: skip
        assert result.exit_code == 0, result.output
        invoice_id = _line_value(result.output, "invoice_id")

        stored = catalogue_after_password_login(session.profile_id, authority_operation).invoices.get(invoice_id)
        assert stored is not None
        assert stored.retention_rate == Decimal("0.15")
        assert stored.retention_amount == Decimal("150.00")


@pytest.mark.windows_only
@pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers")
def test_catalogue_create_refuses_a_retention_rate_without_an_amount(
    authority_operation: PinnedAuthorityOperation, tmp_path: Path
) -> None:
    """A rate alone gets a structured refusal without changing the catalogue."""
    with native_invoice_runtime_session(tmp_path, operation_ids=_RUNTIME_OPERATIONS) as session:
        before = catalogue_after_password_login(session.profile_id, authority_operation)
        result = session.invoke_password(
            "app", "ledger", "invoice", "add",
            "--kind", "received",
            "--counterparty-nif", _RECEIVED_COUNTERPARTY_CIF,
            "--counterparty-name", "Asesoria Profesional SL",
            "--invoice-number", "2026-RETENCION-002",
            "--invoice-date", "2026-03-10",
            "--country-code", "ES",
            "--taxable-base", "1000.00", "--iva-rate", "21",
            "--retention-rate", "0.15",
        )  # fmt: skip
        assert result.exit_code == 2, result.output
        error = require_error_document(result.output)["error"]
        context = cast(dict[str, object], error["context"])
        assert error["code"] == "REFUSED_CLI_BOUNDARY"
        assert context["refusal_code"] == INVOICE_ADD_VALIDATION_REFUSAL_CODE
        assert context["terminal_condition"] == "refused"
        assert context["effect"] == "none"
        assert isinstance(context["operation_id"], str) and len(context["operation_id"]) == 64

        after = catalogue_after_password_login(session.profile_id, authority_operation)
        assert after == before


@pytest.mark.windows_only
@pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers")
def test_catalogue_view_resolves_full_id_and_prefix(tmp_path: Path) -> None:
    """``view`` shows one catalogue invoice by full id and by unambiguous prefix."""
    with native_invoice_runtime_session(tmp_path, operation_ids=_RUNTIME_OPERATIONS) as session:
        invoice_id = _create_catalogue_invoice(session)

        by_full = session.invoke_password("app", "ledger", "invoice", "view", invoice_id, output_format="text")
        assert by_full.exit_code == 0, by_full.output
        assert _line_value(by_full.output, "invoice_id") == invoice_id

        by_prefix = session.invoke_password("app", "ledger", "invoice", "view", invoice_id[:8], output_format="text")
        assert by_prefix.exit_code == 0, by_prefix.output
        assert _line_value(by_prefix.output, "invoice_id") == invoice_id


@pytest.mark.windows_only
@pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers")
def test_catalogue_view_refuses_unknown_id(tmp_path: Path) -> None:
    """An id matching no invoice is refused, naming the id — never a silent miss."""
    with native_invoice_runtime_session(tmp_path, operation_ids=_RUNTIME_OPERATIONS) as session:
        _create_catalogue_invoice(session)
        result = session.invoke_password("app", "ledger", "invoice", "view", "deadbeefdeadbeef", output_format="text")
        assert result.exit_code != 0, result.output
        assert "deadbeefdeadbeef" in result.output, result.output


@pytest.mark.windows_only
@pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers")
def test_catalogue_remove_requires_confirmation(authority_operation: PinnedAuthorityOperation, tmp_path: Path) -> None:
    """``remove`` without ``--yes`` is refused and leaves the record intact."""
    with native_invoice_runtime_session(tmp_path, operation_ids=_RUNTIME_OPERATIONS) as session:
        invoice_id = _create_catalogue_invoice(session)

        result = session.invoke_password("app", "ledger", "invoice", "remove", invoice_id, output_format="text")
        assert result.exit_code != 0, result.output

        # The unconfirmed refusal deleted nothing.
        assert (
            catalogue_after_password_login(session.profile_id, authority_operation).invoices.get(invoice_id) is not None
        )


@pytest.mark.windows_only
@pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers")
def test_catalogue_remove_deletes_unlinked_invoice(
    authority_operation: PinnedAuthorityOperation, tmp_path: Path
) -> None:
    """``remove --yes`` deletes an unlinked invoice and the deletion persists."""
    with native_invoice_runtime_session(tmp_path, operation_ids=_RUNTIME_OPERATIONS) as session:
        invoice_id = _create_catalogue_invoice(session)

        result = session.invoke_password(
            "app", "ledger", "invoice", "remove", invoice_id[:8], "--yes", output_format="text"
        )
        assert result.exit_code == 0, result.output
        assert _line_value(result.output, "invoice_id") == invoice_id

        assert catalogue_after_password_login(session.profile_id, authority_operation).invoices.get(invoice_id) is None


@pytest.mark.windows_only
@pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers")
def test_catalogue_remove_refuses_linked_invoice(authority_operation: PinnedAuthorityOperation, tmp_path: Path) -> None:
    """``remove`` refuses an invoice still linked to a transaction.

    Deleting it from the catalogue alone would leave the transaction side citing
    a vanished invoice; the verb refuses and the record stays put. The full
    create -> link -> remove chain is exercised through the CLI.
    """
    with native_invoice_runtime_session(tmp_path, operation_ids=_RUNTIME_OPERATIONS) as session:
        add = session.invoke_password(
            "app", "ledger", "add",
            "--date", "2026-03-10", "--amount", "121.00",
            "--direction", "OUTGOING", "--description", f"Supplier {_RECEIVED_COUNTERPARTY_CIF}",
            output_format="text",
        )  # fmt: skip
        assert add.exit_code == 0, add.output
        transaction_id = _line_value(add.output, "ID")

        invoice_id = _create_catalogue_invoice(session)
        linked = _invoke_open_profile(session, "app", "ledger", "link", transaction_id, "--invoice-id", invoice_id)
        assert linked.exit_code == 0, linked.output

        removed = session.invoke_password(
            "app", "ledger", "invoice", "remove", invoice_id, "--yes", output_format="text"
        )
        assert removed.exit_code != 0, removed.output
        assert transaction_id in removed.output, removed.output

        # The linked invoice was not deleted and still cites the transaction.
        stored = catalogue_after_password_login(session.profile_id, authority_operation).invoices.get(invoice_id)
        assert stored is not None
        assert stored.linked_transaction_ids == (transaction_id,), stored.linked_transaction_ids


@pytest.mark.windows_only
@pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers")
def test_catalogue_create_refuses_an_omitted_country_code(tmp_path: Path) -> None:
    """``--country-code`` is mandatory, because it routes both informativas.

    Both canonical entry verbs used to default it to ``ES``. The slim verb they
    replace defaults it to nothing and either derives the country from the EU
    IVA-ID prefix or raises, so repointing the operator's bare verbs onto the
    canonical aggregate would have converted a derive-or-raise into a silent
    domestic assumption.

    A silent ``ES`` is not a cosmetic default on this axis. The M347 projection
    filters on the counterparty country being ``ES``, so a foreign invoice
    stamped domestic is pulled INTO M347 and can carry a party over the
    declaration floor, while M349 declares the wrong member state. The
    canonical record has no EU IVA-ID field to derive a country from -- by
    design, since the tax id already IS the NIF-IVA for a non-ES country -- so
    the honest remedy is to require the operator to state it.
    """
    with native_invoice_runtime_session(tmp_path, operation_ids=_RUNTIME_OPERATIONS) as session:
        result = session.invoke_password(
            "app", "ledger", "invoice", "add",
            "--kind", "received",
            "--counterparty-nif", _RECEIVED_COUNTERPARTY_CIF,
            "--counterparty-name", "Papeleria Sol SL",
            "--invoice-number", "2026-NOCOUNTRY-001",
            "--invoice-date", "2026-03-10",
            "--taxable-base", "100.00", "--iva-rate", "21",
            output_format="text",
        )  # fmt: skip

    assert result.exit_code != 0, result.output
    # Names the missing option rather than failing generically, so the operator
    # is told what to supply instead of being left to guess.
    assert "--country-code" in result.output


@pytest.mark.windows_only
@pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers")
def test_catalogue_create_still_accepts_an_explicit_domestic_country_code(tmp_path: Path) -> None:
    """Positive control for the refusal above.

    A gate that refuses everything passes its own negative test and is worse
    than no gate, so the domestic case an operator previously got by omission
    must still succeed when it is stated explicitly.
    """
    with native_invoice_runtime_session(tmp_path, operation_ids=_RUNTIME_OPERATIONS) as session:
        result = session.invoke_password(
            "app", "ledger", "invoice", "add",
            "--kind", "received",
            "--counterparty-nif", _RECEIVED_COUNTERPARTY_CIF,
            "--counterparty-name", "Papeleria Sol SL",
            "--invoice-number", "2026-WITHCOUNTRY-001",
            "--invoice-date", "2026-03-10",
            "--country-code", "ES",
            "--taxable-base", "100.00", "--iva-rate", "21",
            output_format="text",
        )  # fmt: skip

        assert result.exit_code == 0, result.output
        assert len(_line_value(result.output, "invoice_id")) == 64


@pytest.mark.windows_only
@pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers")
def test_catalogue_create_accepts_every_regime_option_and_holds_the_totals_identity(tmp_path: Path) -> None:
    """All four regime axes are expressible from the CLI, and the identity holds.

    Before these options existed every canonically-written invoice was
    ORDINARIA with no series and no recargo by construction, and a
    rectificativa could not be entered at all -- so an operator could not
    express a regime the aggregate had always modelled.

    The identity asserted here is the invoice-total decomposition rule:
    grand_total equals base plus cuota plus recargo, with the retención
    OUTSIDE it. A recargo is charged on top of the cuota and is collected from
    the customer; a retención is withheld from the payment. Putting the
    retención inside the total would overstate what the customer owes, and
    putting the recargo outside it would understate the invoice.
    """
    with native_invoice_runtime_session(tmp_path, operation_ids=_RUNTIME_OPERATIONS) as session:
        result = session.invoke_password(
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
            output_format="text",
        )  # fmt: skip

        assert result.exit_code == 0, result.output
        assert _line_value(result.output, "invoice_class") == "RECTIFICATIVA"
        assert _line_value(result.output, "series") == "R"
        assert _line_value(result.output, "recargo_amount") == "52.00"
        # 1000 base + 210 cuota + 52 recargo, the recargo INSIDE the total.
        assert _line_value(result.output, "grand_total") == "1262.00"


@pytest.mark.windows_only
@pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers")
def test_catalogue_create_refuses_an_unknown_invoice_class_naming_the_accepted_set(tmp_path: Path) -> None:
    """A closed axis must instruct on parse failure, never fail bare.

    The option is typed on the enum so click renders the accepted set rather
    than leaving the operator to guess, which is the CLI boundary's job for
    every closed value set.
    """
    with native_invoice_runtime_session(tmp_path, operation_ids=_RUNTIME_OPERATIONS) as session:
        result = session.invoke_password(
            "app", "ledger", "invoice", "add",
            "--kind", "issued",
            "--counterparty-nif", "B12345674",
            "--counterparty-name", "Cliente SL",
            "--invoice-number", "2026-REG-002",
            "--invoice-date", "2026-05-04",
            "--country-code", "ES",
            "--taxable-base", "1000.00", "--iva-rate", "21",
            "--invoice-class", "no-such-class",
            output_format="text",
        )  # fmt: skip

    assert result.exit_code != 0
    assert "RECTIFICATIVA" in result.output
