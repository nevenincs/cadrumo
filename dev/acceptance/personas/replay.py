"""Replay a persona's profile, household, withholding, ledger, documents and inventory through the CLI."""

from __future__ import annotations

import json

from cadrumo.entrypoints.tests.persona_materialisation import (
    bank_statement,
    document_path,
    inventory_statement,
    patch_answers,
)
from cadrumo.tests.personas import (
    LedgerRow,
)

from . import commands
from .journey import (
    ACTOR,
    Journey,
    found_text,
)

LIST_LIMIT = "1000"
"""The page size the ledger listing is read with."""


# -- profile ---------------------------------------------------------------------------------------------------------


def create_profile(journey: Journey) -> bool:
    """Create the persona's profile with its credential on stdin; whether it now exists."""
    secret = journey.cli.passphrase
    payload = json.dumps({"passphrase": secret, "passphrase_confirmation": secret}, separators=(",", ":"))
    args = ("config", "profile", "create", f"persona-{journey.persona.id}", "--quiet", "--secrets-stdin")
    return journey.run("profile.create", args, authenticated=False, stdin_payload=payload).ok


def replay_profile(journey: Journey) -> None:
    """Submit the wizard answers and elections, the fields, and the activity rows."""
    persona = journey.persona
    args, missing = commands.profile_edit_arguments(patch_answers(persona, journey.envelope), persona.fields)
    journey.missing(missing)
    journey.run("profile.answers", args)
    for item in persona.fields:
        routed = commands.field_arguments(item)
        if isinstance(routed, commands.MissingRoute):
            journey.gap(routed.step, routed.missing)
        elif routed is not None:
            journey.run(f"fields.{item.path}", routed)
    for index, activity in enumerate(persona.activities):
        journey.run(f"activities.{index}", commands.activity_arguments(activity.values))


def replay_household(journey: Journey) -> None:
    """Submit the household families the persona states."""
    rendered, missing = commands.household_arguments(journey.persona, journey.envelope)
    journey.missing(missing)
    for args in rendered:
        journey.run("household.descendants", args)


def replay_withholding(journey: Journey) -> None:
    """Record each certificate the taxpayer declares; a payer certificate's bytes are not held."""
    persona = journey.persona
    for certificate in persona.withholding_certificates:
        step = f"withholding_certificates.{certificate.payer}"
        if certificate.origin != "operator_declaration":
            journey.note(f"{step}: a payer certificate needs its bytes and the persona references none; not loaded")
            continue
        journey.run(step, commands.withholding_arguments(persona, certificate, journey.envelope))
    if any(item.cotizaciones_seguridad_social is not None for item in persona.withholding_certificates):
        journey.note(
            "withholding_certificates.cotizaciones_seguridad_social: no operation records an employee's Seguridad "
            "Social contributions; not loaded"
        )


# -- ledger ----------------------------------------------------------------------------------------------------------


def import_ledger(journey: Journey) -> None:
    """Import the bank statement, then find each row's transaction in the ledger listing."""
    persona = journey.persona
    if not persona.ledger:
        return
    statement = journey.workdir / f"{persona.id}-statement.csv"
    statement.write_text(bank_statement(persona.ledger, journey.envelope), encoding="utf-8", newline="\n")
    imported = journey.run("ledger.import", ("app", "ledger", "import", "--file", str(statement), "--provider", "csv"))
    if not imported.ok:
        return
    listed = journey.run("ledger.list", ("app", "ledger", "list", "--limit", LIST_LIMIT))
    rows = listed.result.get("rows")
    if not listed.ok or not isinstance(rows, list):
        return
    if listed.result.get("truncated"):
        journey.note(f"ledger.list: the listing was truncated at {LIST_LIMIT} rows")
    mapped, unmatched = commands.correlate_rows(persona.ledger, rows, journey.envelope)
    journey.transactions.update(mapped)
    journey.note(
        "ledger.correlate: ledger list exposes no statement reference (provider transaction id), so each row's "
        "transaction is found by date, amount, direction and concept"
    )
    if unmatched:
        journey.gap(
            "ledger.correlate",
            f"no listed transaction matches these rows uniquely and no command exposes the statement reference: "
            f"{', '.join(unmatched)}",
        )


def _transaction(journey: Journey, step: str, ref: str) -> str | None:
    found_id = journey.transactions.get(ref)
    if found_id is None:
        journey.skip(step, f"no transaction was found for {ref}")
    return found_id


def classify_rows(journey: Journey) -> None:
    """Classify every row as the in-process replay does."""
    persona = journey.persona
    unmapped = commands.unmapped_classify_fields(persona)
    if unmapped:
        journey.gap("ledger.classify", f"`ledger classify` takes no option for {', '.join(sorted(unmapped))}")
    for row in persona.ledger:
        step = f"ledger.classify.{row.ref}"
        transaction_id = _transaction(journey, step, row.ref)
        if transaction_id is not None:
            journey.run(step, commands.classify_arguments(persona, row, transaction_id, ACTOR))


def _record_invoice(journey: Journey, row: LedgerRow) -> None:
    args = commands.invoice_arguments(journey.persona, row, journey.envelope)
    if args is None:
        return
    added = journey.run(f"ledger.invoice.{row.ref}", args)
    invoice_id = found_text(added.result, "invoice_id")
    if invoice_id is None:
        return
    journey.invoices[row.ref] = invoice_id
    step = f"ledger.link.{row.ref}"
    transaction_id = _transaction(journey, step, row.ref)
    if transaction_id is not None:
        journey.run(step, ("app", "ledger", "link", transaction_id, "--invoice-id", invoice_id, "--by", ACTOR))


def record_invoices(journey: Journey) -> None:
    """Record the invoice behind each row and link it to the row's transaction."""
    for row in journey.persona.ledger:
        _record_invoice(journey, row)


def add_documents(journey: Journey) -> None:
    """Keep each document as evidence and attach it to the rows it evidences."""
    persona = journey.persona
    for document in persona.documents:
        source = document_path(persona, document, envelope=journey.envelope, workdir=journey.workdir)
        args = (
            "app",
            "ledger",
            "evidence",
            "add",
            str(source),
            "--notes",
            f"persona {persona.id} document {document.id} ({document.relation})",
            "--idempotency-key",
            f"persona-{persona.id}-{document.id}",
        )
        added = journey.run(f"documents.{document.id}", args)
        evidence_id = found_text(added.result, "evidence_id")
        for ref in document.attach_to:
            step = f"documents.{document.id}.attach.{ref}"
            transaction_id = _transaction(journey, step, ref)
            if transaction_id is None or evidence_id is None:
                continue
            attach = ("app", "ledger", "attach", transaction_id, "--purchase-invoice-evidence-id", evidence_id)
            journey.run(step, (*attach, "--actor", ACTOR))


def open_inventory(journey: Journey) -> None:
    """Open each existencias book and record its closing on its movements, evidenced by the statement."""
    persona = journey.persona
    for book in persona.inventory:
        year = book.year.resolve(journey.envelope)
        step = f"inventory.{book.activity}.{year}"
        if not journey.run(f"{step}.create", commands.inventory_create_arguments(book, year)).ok:
            continue
        source = inventory_statement(persona, book, envelope=journey.envelope, workdir=journey.workdir)
        stored = journey.run(f"{step}.evidence", ("app", "ledger", "inventory", "evidence-add", str(source)))
        reference = found_text(stored.result, "reference")
        digest = found_text(stored.result, "content_digest")
        if reference is None or digest is None:
            journey.skip(f"{step}.closing", "the statement was not kept")
            continue
        facts = commands.inventory_closing_facts(book, year, reference=reference, content_digest=digest)
        path = journey.workdir / "inventory" / f"{book.activity}-{year}-closing.json"
        path.write_text(json.dumps(facts, indent=2), encoding="utf-8", newline="\n")
        closing = ("app", "ledger", "inventory", "closing-value-record", book.activity, "--year", str(year))
        journey.run(f"{step}.closing", (*closing, "--file", str(path)))


def complete_setup(journey: Journey) -> None:
    """Declare the profile's setup complete, as the setup flow ends."""
    journey.setup_complete = journey.run("setup.complete", ("config", "profile", "complete-setup")).ok
