"""CLI regression for the guided manual-entry invoice wizard.

``aeat app ledger invoice catalogue wizard`` (#254 slice 4b) is the guided,
non-interactive fallback for when extraction (evidence extract / vision OCR)
is unavailable or insufficient: every invoice field is supplied up front as a
CLI option, each field is validated independently (a malformed NIF and a
malformed date are BOTH reported in one refusal), the write delegates to
:func:`~application.invoices.create_catalogue_invoice` (the sole
sanctioned writer), and a retry with identical fields is a guarded idempotent
no-op rather than a duplicate error.

Real behaviour only: a real encrypted bucket session, the live Typer tree,
and real invoice records. No mocks, stubs, or monkeypatch. Runs against an
isolated in-process CliRunner, so "non-blocking" is proven directly: the
runner supplies no stdin, and a command that tried to prompt would hang or
raise -- these tests completing at all is the non-interactivity proof.

See Also:
    :func:`~application.invoices.create_invoice_via_wizard`
        Application facade that validates every manual-entry field.
    :class:`~domain.invoices.Invoice`
        Domain invoice record persisted by the wizard path.
    :class:`~adapters.persistence.profile.invoices.InvoiceCatalogueRepository`
        Bucket-scoped encrypted repository used for the real round trip.
    :func:`~entrypoints.cli._ledger_business_invoice_cli.catalogue_wizard`
        CLI command handler covered by these integration tests.

The wizard is the manual fallback that complements the extraction (OCR)
path: whichever is unavailable or insufficient, the operator-facing
``invoice --kind`` surface stays consistent either way.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from ....adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ....application.user_profile import profile_create_storage_span
from ....application.workflow import workflow_state_repository
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_profile_storage_root
from ....tests.user_profile import register_minimal_profile
from .envelope_helpers import require_schema_envelope as _json_result

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

# A valid Spanish CIF (control digit verified) reused across the catalogue
# invoice test surface.
_RECEIVED_COUNTERPARTY_CIF = "A58818501"

_BASE_ARGS = [
    "app", "ledger", "invoice", "catalogue", "wizard",
    "--kind", "received",
    "--counterparty-nif", _RECEIVED_COUNTERPARTY_CIF,
    "--counterparty-name", "Papeleria Sol SL",
    "--invoice-number", "2026-0900",
    "--invoice-date", "2026-03-10",
    "--taxable-base", "100.00",
    "--iva-rate", "21",
]  # fmt: skip


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


def test_wizard_creates_invoice_from_provided_fields() -> None:
    """Every field supplied up front creates a valid catalogue invoice."""
    result = invoke_cached_cli(["--format", "json", *_BASE_ARGS])
    assert result.exit_code == 0, result.output
    payload = _json_result(result.output)
    assert payload["already_existed"] is False
    assert payload["counterparty_tax_id"] == _RECEIVED_COUNTERPARTY_CIF
    assert payload["invoice_number"] == "2026-0900"
    assert payload["grand_total"] == "121.00"

    stored = InvoiceCatalogueRepository().load().get(str(payload["invoice_id"]))
    assert stored is not None
    assert stored.counterparty_name == "Papeleria Sol SL"
    assert stored.base_total == stored.grand_total - stored.iva_total


def test_wizard_created_invoice_roundtrips_through_encrypted_boundary() -> None:
    """The wizard-created record survives a fresh reload from encrypted storage.

    A second, independently constructed :class:`InvoiceCatalogueRepository`
    instance loads the SAME encrypted bucket store (no in-process cache reuse),
    proving the invoice created via the wizard persists faithfully across the
    :class:`~adapters.persistence.storage.SecureObjectRepository` boundary.
    Strict pydantic equality is asserted against the invoice retained from the
    original wizard call.
    """
    result = invoke_cached_cli(["--format", "json", *_BASE_ARGS])
    assert result.exit_code == 0, result.output
    payload = _json_result(result.output)
    invoice_id = str(payload["invoice_id"])

    first_read = InvoiceCatalogueRepository().load().get(invoice_id)
    assert first_read is not None

    # A freshly constructed repository forces a real reload from the
    # encrypted backend rather than reusing any in-process object identity.
    second_read = InvoiceCatalogueRepository().load().get(invoice_id)
    assert second_read is not None
    assert second_read == first_read
    assert second_read.model_dump(mode="json") == first_read.model_dump(mode="json")


def test_wizard_refuses_malformed_nif() -> None:
    """A malformed NIF is refused with an actionable, field-naming error."""
    args = list(_BASE_ARGS)
    nif_index = args.index("--counterparty-nif") + 1
    args[nif_index] = "NOTANIF"

    result = invoke_cached_cli(args)
    assert result.exit_code != 0, result.output
    assert "counterparty_nif" in result.output, result.output


def test_wizard_refuses_malformed_date() -> None:
    """A non-ISO invoice date is refused, naming the failing field."""
    args = list(_BASE_ARGS)
    date_index = args.index("--invoice-date") + 1
    args[date_index] = "10/03/2026"

    result = invoke_cached_cli(args)
    assert result.exit_code != 0, result.output
    assert "invoice_date" in result.output, result.output


def test_wizard_refuses_negative_taxable_base() -> None:
    """A negative taxable base is refused, naming the failing field."""
    args = list(_BASE_ARGS)
    base_index = args.index("--taxable-base") + 1
    args[base_index] = "-50.00"

    result = invoke_cached_cli(args)
    assert result.exit_code != 0, result.output
    assert "taxable_base" in result.output, result.output


def test_wizard_refuses_unsupported_iva_rate() -> None:
    """An IVA percentage outside the recognised slot set is refused."""
    args = list(_BASE_ARGS)
    rate_index = args.index("--iva-rate") + 1
    args[rate_index] = "13"

    result = invoke_cached_cli(args)
    assert result.exit_code != 0, result.output
    assert "iva_rate" in result.output, result.output


def test_wizard_reports_multiple_field_errors_in_one_refusal() -> None:
    """Several malformed fields are ALL named in one refusal, not just the first.

    Guards against the fail-fast-on-first-field regression: a bad NIF and a
    bad date submitted together must both surface, never silently masking the
    second failure behind the first (no-silent-under-declaration).
    """
    args = list(_BASE_ARGS)
    args[args.index("--counterparty-nif") + 1] = "NOTANIF"
    args[args.index("--invoice-date") + 1] = "10/03/2026"

    result = invoke_cached_cli(args)
    assert result.exit_code != 0, result.output
    assert "counterparty_nif" in result.output, result.output
    assert "invoice_date" in result.output, result.output


def test_wizard_retry_with_identical_fields_is_idempotent_noop() -> None:
    """A retry with the exact same fields resolves to a guarded no-op.

    The content-derived identity is unchanged, so the second call must not
    raise a duplicate error and must not create a second record; it reports
    ``already_existed`` and the identical ``invoice_id``.
    """
    first = invoke_cached_cli(["--format", "json", *_BASE_ARGS])
    assert first.exit_code == 0, first.output
    first_payload = _json_result(first.output)
    assert first_payload["already_existed"] is False

    second = invoke_cached_cli(["--format", "json", *_BASE_ARGS])
    assert second.exit_code == 0, second.output
    second_payload = _json_result(second.output)
    assert second_payload["already_existed"] is True
    assert second_payload["invoice_id"] == first_payload["invoice_id"]

    # No duplicate was written: exactly one invoice exists for this identity.
    catalogue = InvoiceCatalogueRepository().load()
    matches = [inv for inv in catalogue.values() if inv.invoice_number == "2026-0900"]
    assert len(matches) == 1, matches


def test_wizard_is_non_interactive() -> None:
    """The wizard command never blocks on stdin.

    The command completes synchronously against a runner that supplies no stdin
    content; a blocking prompt would hang or raise ``EOFError`` here instead.
    """
    result = invoke_cached_cli(_BASE_ARGS, input="")
    assert result.exit_code == 0, result.output
