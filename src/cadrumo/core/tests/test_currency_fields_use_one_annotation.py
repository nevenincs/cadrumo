"""A field that carries a currency code uses the one annotation for it.

This gate exists because the manual search kept succeeding. Four consecutive
rounds of the consolidation campaign each found a currency declaration the
previous round had missed -- a length-only alias in the ledger models, a
length-only bound on the invoice record, a bare ``min_length=1`` on a filing
snapshot, a hand-rolled ``^[A-Z]{3}$`` pattern -- and each time the fix was the
same and the next one was still out there. Four policies were live at once and
they disagreed on ordinary input: ``"eur"`` normalised at one site, passed
through unchanged at another and was refused at a third; ``"12A"`` was accepted
by two; a filing snapshot accepted the single character ``"E"``.

The rule is therefore structural rather than a list of known sites. Any field
whose NAME says it carries a currency code must be annotated
:obj:`~core.parsing.IsoCurrencyCode`, which trims, uppercases and requires three
letters -- or be recorded below with the reason it does not.

The allowlist is where the judgement lives, so every entry states a reason and a
stale entry fails. It deliberately does not accept a bare "legacy" or "TODO":
the entries here are decisions, and a decision that cannot be written down in a
sentence is not one.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_SRC = Path(__file__).resolve().parent.parent.parent

#: The canonical annotation, and the spellings a field may use to name it.
_CANONICAL = {"IsoCurrencyCode", "IsoCurrencyCode | None"}

#: Field names that carry an ISO 4217 code. Deliberately narrow: a name like
#: ``local_recurrence_amount`` contains no currency code however it reads, and
#: ``financial_base_currency`` on a settings object is a configuration key.
_CURRENCY_FIELD_NAMES = {"currency", "currency_code", "invoice_currency", "source_currency", "target_currency"}

#: Fields that carry a currency code under a different annotation, each with the
#: reason. A reason naming a REVIEWED difference in behaviour is the only kind
#: that belongs here.
DECLARED_EXCEPTIONS: dict[str, str] = {
    "application/operations/financial_operand.py::currency": (
        "a registry-AUTHORED declaration rather than operator or bank input, so "
        "a sloppy code should fail the author at load; IsoCurrencyCode would "
        "normalise an authored 'eur' and repair it behind them"
    ),
    "adapters/inbound/financial/providers/csv.py::currency": (
        "a raw parsed cell, held exactly as the bank exported it so the adapter "
        "can name the offending value; normalisation happens once at the "
        "RawTransaction boundary this feeds, not twice"
    ),
    "adapters/inbound/financial/providers/_mapped_tabular.py::currency": (
        "the same raw parse struct as the CSV provider, for the same reason: it "
        "carries the source cell, and RawTransaction normalises it"
    ),
    "application/ledger/invoice_draft_payloads.py::currency": (
        "the draft payload of a document reading, beside taxable_base and "
        "iva_rate which are strings for the same reason: it shows the operator "
        "what was read, including when what was read is wrong"
    ),
    "application/ledger/structured_invoice_ports.py::currency": (
        "a structured e-invoice as the parser read it, beside the parsed "
        "country codes and tax ids; the grounding and confirmation steps judge "
        "it, so the port must be able to carry a malformed value to them"
    ),
    "application/ledger/workspace.py::currency": (
        "a review row projected for display beside date and amount strings; it "
        "repeats the stored transaction's already-normalised code and "
        "validates nothing itself"
    ),
    "entrypoints/tui/ledger/models.py::currency": (
        "workbench transport models: an entry carries what the operator typed, "
        "which the application writer alone judges, and a reader draft carries "
        "the document's text for display, including when it is wrong"
    ),
    "application/ledger/invoice_draft_records.py::currency": (
        "read off a document rather than declared, so it must hold whatever the "
        "invoice actually said -- a refusal that cannot quote the unreadable "
        "value tells the operator nothing about which document to fix"
    ),
    "adapters/outbound/llm/invoice_field_grounding.py::currency": (
        "an extraction result awaiting grounding; refusing a malformed code at "
        "the model boundary would discard the evidence the grounding check "
        "exists to evaluate"
    ),
    "domain/renta/ledger_expenses.py::currency": (
        "Literal['EUR'] is STRICTER than the canonical annotation, not looser: "
        "this expense projection is euro-only by construction and the literal "
        "states that in the type rather than in a comment"
    ),
    # The eight entries below share one structural cause, stated per site
    # because each also names the boundary that does own its ISO policy.
    # IsoCurrencyCode is a BeforeValidator, and a BeforeValidator carries
    # ``__get_pydantic_core_schema__``; ``_require_no_custom_core_schema_hook``
    # in application/operations/_model_contract.py refuses exactly that on a
    # registered operation's public schema, as the sibling rule refuses
    # before/plain/wrap validators. A public operation field therefore cannot
    # normalise at all -- it declares shape and nothing else -- so the canonical
    # policy stays at the boundary each field feeds or is projected from.
    "application/invoices/catalogue_add_contracts.py::currency": (
        "a registered operation's public request schema, which the operation "
        "model contract forbids from carrying a core-schema-customising "
        "annotation; build_catalogue_invoice constructs the domain Invoice, "
        "whose currency IS IsoCurrencyCode, so the canonical policy applies one "
        "step later rather than not at all"
    ),
    "application/invoices/catalogue_read_projection.py::currency": (
        "a public projection of the domain Invoice, under the same operation "
        "schema contract; it does not merely omit the policy -- its _bounds "
        "model validator REFUSES any value that normalise_iso_4217_currency "
        "would change, which an after-mode validator may do where the "
        "annotation may not"
    ),
    "application/ledger/ledger_add_contracts.py::currency": (
        "a public request schema under the same operation model contract; it "
        "feeds ManualLedgerTransactionCommand, whose currency is "
        "IsoCurrencyCode, so the canonical normalisation happens at that "
        "command boundary"
    ),
    "application/ledger/export_operation.py::currency": (
        "a public projection of LedgerExportRow.currency, which is already "
        "IsoCurrencyCode; the operation schema contract forbids restating that "
        "annotation here, and the row it copies cannot hold a value the "
        "canonical policy would reject"
    ),
    "application/ledger/transaction_projection.py::currency": (
        "a public projection of LedgerTransactionPayload.currency, which is "
        "already IsoCurrencyCode, under the same operation schema contract; "
        "from_payload revalidates that payload's own JSON, so the value is "
        "canonical before it arrives"
    ),
    "application/ledger/invoice_evidence_confirm_operation.py::currency": (
        "a public operator-confirmation request under the same contract. The "
        "optional spelling escapes the core-schema check only because that "
        "walk does not enter a union, which is a gap rather than a licence to "
        "carry a policy its non-optional siblings cannot; prepare_invoice_"
        "confirmation_from_evidence reaches the domain Invoice that owns it"
    ),
    "application/modelo/modelo_spreadsheet_observations.py::currency_code": (
        "the public wire mirror of Modelo720RowObservation.currency_code, "
        "which IS IsoCurrencyCode; the operation schema contract forbids the "
        "canonical annotation on this mirror, and the mirror projects an "
        "already-validated row"
    ),
    "application/modelo/aggregate_public.py::currency_code": (
        "a public projection of ForeignAssetIngestObservation.currency_code, "
        "which is IsoCurrencyCode, under the same operation schema contract; "
        "to_domain revalidates through that model and refuses a value its "
        "canonical round trip would change"
    ),
    "application/invoices/catalogue_intake_contracts.py::currency": (
        "a wizard request field held as raw transport text because "
        "create_invoice_via_wizard validates every field independently and "
        "ACCUMULATES the failures, so a malformed code is reported beside a "
        "malformed NIF and date; refusing it at the request boundary would "
        "mask the other two behind the first"
    ),
    "application/ledger/update_contracts.py::currency": (
        "a canonical-text patch whose sibling date and decimal fields REFUSE "
        "non-canonical text rather than normalising it, which _canonical_currency "
        "enforces here for the same reason: the operator is editing one stored "
        "row and is told which token is wrong, where a folding annotation would "
        "silently rewrite it"
    ),
    "application/ledger/own_account_operation.py::currency": (
        "the secure request and masked public result obey the registered operation "
        "contract, which forbids the canonical BeforeValidator's core-schema hook; "
        "OwnBankAccountDetails owns the canonical IsoCurrencyCode policy when "
        "the worker builds account details, and from_account projects that validated code"
    ),
    "application/ledger/invoice_evidence_operation_dtos.py::currency": (
        "the wire projection of invoice_draft_records, read off a document "
        "rather than declared, and exempt for that record's own reason: it "
        "carries what the invoice actually said so the confirmation step can "
        "quote an unreadable value back to the operator"
    ),
    "domain/transactions/raw_transaction.py::currency": (
        "carries the length bound as an annotation but normalises through "
        "normalise_iso_4217_currency in a mode='before' validator, so it "
        "already applies the canonical policy and raises its own "
        "TransactionValidationError rather than a generic one"
    ),
}


def _currency_fields() -> dict[str, set[str]]:
    """Map ``path::field`` -> the set of annotations declared under that name.

    A SET, not a single annotation. Five modules declare a currency field name
    more than once -- ``application/ledger/models.py`` does it four times -- and
    keying to a single value let the last declaration overwrite the rest, so the
    gate could see only one of four and reported nothing about the others. The
    sibling country gate had the identical flaw and a mutation probe exposed it
    there; this is the same fix applied before it could hide anything here.

    The key stays ``path::field`` rather than gaining a line number, because an
    exception keyed by line goes stale on the next edit above it.
    """
    found: dict[str, set[str]] = {}
    for path in sorted(_SRC.rglob("*.py")):
        parts = path.relative_to(_SRC).parts
        if "tests" in parts or path.name.startswith("test_"):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:  # a peer's mid-edit file is not this gate's finding
            continue
        relative = path.relative_to(_SRC).as_posix()
        # A field is an annotated name in a CLASS body; a function's annotated
        # local holding a value it is still reading is not a declaration.
        class_statements = (
            statement for owner in ast.walk(tree) if isinstance(owner, ast.ClassDef) for statement in owner.body
        )
        for node in class_statements:
            if not isinstance(node, ast.AnnAssign) or not isinstance(node.target, ast.Name):
                continue
            if node.target.id not in _CURRENCY_FIELD_NAMES:
                continue
            annotation = ast.unparse(node.annotation)
            # A settings CONSTANT is not a model field carrying a value.
            if annotation.startswith("Final["):
                continue
            found.setdefault(f"{relative}::{node.target.id}", set()).add(annotation)
    return found


def test_every_currency_field_uses_the_canonical_annotation() -> None:
    """A new currency field must adopt the one annotation or declare why not."""
    offenders = {
        site: sorted(annotations - _CANONICAL)
        for site, annotations in _currency_fields().items()
        if not annotations <= _CANONICAL and site not in DECLARED_EXCEPTIONS
    }

    assert not offenders, (
        "these fields carry an ISO 4217 code under their own annotation. Use "
        "core.parsing.IsoCurrencyCode, which trims, uppercases and requires "
        "three letters; if this field genuinely must differ, record it in "
        f"DECLARED_EXCEPTIONS with the reason: {offenders}"
    )


def test_declared_exceptions_still_exist() -> None:
    """An exception whose field moved or adopted the canonical loses its entry."""
    sites = _currency_fields()
    stale = sorted(site for site in DECLARED_EXCEPTIONS if site not in sites)

    assert not stale, (
        "these declared exceptions name a currency field that no longer exists "
        f"at that path: drop them from DECLARED_EXCEPTIONS: {stale}"
    )


def test_declared_exceptions_have_not_quietly_adopted_the_canonical() -> None:
    """An exception that now uses the canonical is a stale entry, not a permission."""
    sites = _currency_fields()
    redundant = sorted(site for site in DECLARED_EXCEPTIONS if site in sites and sites[site] <= _CANONICAL)

    assert not redundant, f"these fields now use the canonical annotation and need no exception: {redundant}"


def test_every_exception_states_a_reason() -> None:
    """The judgement lives in the reason, so a placeholder is not an entry."""
    unreasoned = sorted(
        site
        for site, reason in DECLARED_EXCEPTIONS.items()
        if len(reason.strip()) < 40 or reason.strip().lower().startswith(("todo", "legacy", "temporary"))
    )

    assert not unreasoned, f"these currency exceptions carry no usable reason: {unreasoned}"


def test_the_gate_finds_currency_fields_at_all() -> None:
    """Anti-vacuity: a rename of the field vocabulary must fail, not pass silently.

    Without this, narrowing ``_CURRENCY_FIELD_NAMES`` to nothing -- or a sweep
    that renames the fields -- would make every assertion above trivially true.
    """
    sites = _currency_fields()

    assert len(sites) >= 10, f"only {len(sites)} currency fields discovered; the checks above would prove little"
    assert any(annotations & _CANONICAL for annotations in sites.values()), (
        "no field uses the canonical annotation, so the gate is measuring the wrong thing"
    )
