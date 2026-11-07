// The scenario ledger's imports: the statements, invoice books and
// documents it reads from the made-up computer's files, and what each
// import adds. Everything it answers is synthetic.

import type {
  FilePurpose,
  JsonObject,
  JsonValue,
  PublicPeriod,
} from "../shell/ledger";
import {
  type FixtureLedger,
  type FixtureMovement,
  hex64,
  LEDGER_FIXTURE_PROFILE_ID,
  money,
  movementId,
} from "./fixtures/ledger";
import {
  BOOK_REFUSALS,
  fixtureTemplate,
  STATEMENT,
  STATEMENTS,
} from "./ledgerFileFixture";
import { compare, periodSpan, Stopped } from "./ledgerQueryFixture";
import { invalid, text } from "./ledgerRequestFixture";
import { fixtureDay, fixtureYear } from "@/dev/fixtureDates";

/** The scenario ledger's import answers over its movements. */
export function importOperations(
  ledger: FixtureLedger,
  tools: {
    now: () => string;
    events: () => string[];
    bytesOf: (name: string) => string;
    fileOf: (
      token: JsonValue | undefined,
      purpose: FilePurpose,
    ) => { name: string };
    transactionOf: (id: string) => FixtureMovement | undefined;
    /** The local AI's program is not set up. */
    readerMissing: boolean;
  },
) {
  const { now, events, bytesOf, fileOf, transactionOf, readerMissing } = tools;
  /** The movements already in the ledger that a statement's first rows fall
   * on the day and amount of, chosen once from October 2026. */
  let duplicateTargets: FixtureMovement[] | null = null;
  const targets = () =>
    (duplicateTargets ??= ledger.movements
      .filter(
        (movement) =>
          movement.transaction.date.startsWith(`${fixtureYear}-10-`) &&
          movement.transaction.lifecycle_state === "ACTIVE",
      )
      .sort((left, right) =>
        compare(left.transaction.date, right.transaction.date),
      )
      .slice(0, 4));

  /** One statement's rows as the product reads them, each bound to `bound`. */
  function statementRows(name: string, bound: string | null) {
    const spec = STATEMENTS[name] ?? STATEMENT;
    const stem = name.replace(/\.[a-z0-9]+$/i, "").toUpperCase();
    return Array.from({ length: spec.rows }, (_, at) => {
      const target = at < spec.duplicates ? targets()[at] : undefined;
      const dayOfMonth = spec.gap && at > 3 ? 18 + (at % 9) : 1 + (at % 9);
      const date = target
        ? target.transaction.date
        : fixtureDay(10, dayOfMonth);
      const amount = target
        ? target.transaction.amount
        : money(1500 + at * 731 + stem.length * 13);
      const description = `${target ? "CARGO" : "MOVIMIENTO"} ${stem.slice(0, 18)} ${String(at + 1).padStart(2, "0")}`;
      const direction = target
        ? target.transaction.direction
        : at % 4 === 0
          ? "INCOMING"
          : "OUTGOING";
      return {
        id: movementId({
          date,
          amount,
          description,
          own_account_id: bound,
          salt: name,
        }),
        date,
        amount,
        description,
        direction,
      };
    });
  }

  /** A bank statement import, as the product's public result tells it: a
   * row already in the ledger is skipped, a row on the day and amount of
   * another is imported and listed as a likely duplicate, and each file
   * read names its digest by its place in the request. */
  function importStatement(request: JsonObject): JsonObject {
    const tokens = request.files;
    if (!Array.isArray(tokens) || tokens.length === 0) return invalid();
    const chosen = tokens.map((token) => fileOf(token, "bank_statements"));
    const expected = request.expected_source_sha256 ?? null;
    if (
      expected !== null &&
      (!Array.isArray(expected) || expected.length !== chosen.length)
    )
      return invalid();
    const account = text(request.own_account_id);
    if (
      account !== null &&
      !ledger.accounts.some((known) => known.own_account_id === account)
    )
      throw new Stopped("ERROR_TRANSACTION_VALIDATION");
    const period = (request.period ?? null) as PublicPeriod | null;
    const span = period ? periodSpan(period.filing_year, period.code) : null;
    if (period && !span) return invalid();
    const dryRun = request.dry_run === true;
    const verify = request.verify === true;
    const profile = LEDGER_FIXTURE_PROFILE_ID;
    const ref = (id: string): JsonObject => ({
      bucket_id: profile,
      transaction_id: id,
    });
    const refused: JsonObject[] = [];
    const digests: JsonObject[] = [];
    const imported: JsonObject[] = [];
    const skipped: JsonObject[] = [];
    const duplicates: JsonObject[] = [];
    const diagnostics: JsonObject[] = [];
    const validations: JsonObject[] = [];
    const batches: string[] = [];
    let rows = 0;
    chosen.forEach((file, index) => {
      const spec = STATEMENTS[file.name] ?? STATEMENT;
      const sha = bytesOf(file.name);
      // Apply takes exactly the files the preview read, unchanged since.
      if (Array.isArray(expected) && expected[index] !== sha) {
        refused.push({ file_name: file.name, reason_code: "source_changed" });
        return;
      }
      // Where the local AI is not set up, a PDF statement, which only the
      // local AI reads, is refused for it.
      if (readerMissing && file.name.endsWith(".pdf")) {
        refused.push({
          file_name: file.name,
          reason_code: "reader_unavailable",
        });
        return;
      }
      if (!spec.readable) {
        refused.push({
          file_name: file.name,
          reason_code: "transaction_validation",
        });
        return;
      }
      // A chosen account that the file's own rows contradict refuses it.
      if (account !== null && spec.names !== null && spec.names !== account) {
        refused.push({
          file_name: file.name,
          reason_code: "own_account_mismatch",
        });
        return;
      }
      const named = ledger.accounts.some(
        (known) => known.own_account_id === spec.names,
      )
        ? spec.names
        : null;
      const bound = account ?? named;
      const read = statementRows(file.name, bound).filter(
        (row) => !span || (row.date >= span[0] && row.date <= span[1]),
      );
      digests.push({ file_index: index, sha256: sha });
      validations.push({ valid: true, warning_count: 0, encoding: "utf-8" });
      rows += read.length;
      const days = new Set<string>();
      const fresh: string[] = [];
      for (const row of read) {
        const day = `${row.date}:${row.amount}`;
        if (transactionOf(row.id)) {
          skipped.push(ref(row.id));
          if (verify)
            diagnostics.push({
              kind: "duplicate",
              severity: "info",
              message: "transactions.import.message_082074",
              affected_transaction_ids: [row.id],
            });
          continue;
        }
        const likely =
          days.has(day) ||
          ledger.movements.some(
            (movement) =>
              `${movement.transaction.date}:${movement.transaction.amount}` ===
              day,
          );
        days.add(day);
        imported.push(ref(row.id));
        fresh.push(row.id);
        if (likely) duplicates.push(ref(row.id));
        if (dryRun) continue;
        const created = now();
        ledger.movements.push({
          transaction: {
            ...fixtureTemplate(),
            transaction_id: row.id,
            date: row.date,
            booked_date: row.date,
            value_date: row.date,
            amount: row.amount,
            direction: row.direction,
            description: row.description,
            created_at: created,
            modified_at: created,
          },
          group_label: null,
          own_account_id: bound,
          import_batch_id: null,
          issue: likely ? "duplicate" : null,
          sealed: false,
          llm_rejected: false,
          idempotency_key: null,
        });
      }
      if (verify && spec.gap && read.length > 0)
        diagnostics.push({
          kind: "gap",
          severity: "warning",
          message: "transactions.import.message_829073",
          affected_transaction_ids: [],
        });
      if (!dryRun && fresh.length > 0) {
        const batch = hex64(`batch:${fresh.join(",")}`);
        batches.push(batch);
        for (const id of fresh) transactionOf(id)!.import_batch_id = batch;
      }
    });
    return {
      profile_id: profile,
      rows,
      imported: imported.length,
      skipped: skipped.length,
      likely_duplicates: duplicates.length,
      dry_run: dryRun,
      verify,
      period: period as unknown as JsonValue,
      bucket_id: profile,
      // Files that each import have no single batch between them.
      import_batch_id: batches.length === 1 ? batches[0]! : null,
      bucket_event_ids: dryRun || imported.length === 0 ? [] : events(),
      imported_transaction_refs: imported,
      skipped_transaction_refs: skipped,
      likely_duplicate_transaction_refs: duplicates,
      validations,
      sources: chosen.map(() => ({ requested: false, sha256: null })),
      diagnostics,
      refused_files: refused,
      source_digests: digests,
    };
  }

  /** An invoice book, row by row: no dry run, a refused row leaves the
   * others, and a row the catalogue already holds is skipped. */
  function importInvoiceBook(request: JsonObject): JsonObject {
    const file = fileOf(request.source_path, "invoice_books");
    const kind = request.kind;
    if (kind !== "issued" && kind !== "received") return invalid();
    const country = text(request.country);
    if (country !== null && !/^[A-Z]{2}$/.test(country)) return invalid();
    const sha = bytesOf(file.name);
    const expected = text(request.source_sha256);
    if (expected !== null && expected !== sha)
      throw new Stopped("ERROR_INVOICE_IMPORT_SOURCE_CHANGED");
    const refusals = BOOK_REFUSALS[file.name] ?? [];
    const rows = 6;
    const created: string[] = [];
    let skippedDuplicate = 0;
    const template = ledger.invoices.find((invoice) => invoice.kind === kind);
    for (let row = 2; row < rows + 2; row += 1) {
      if (refusals.some((refusal) => refusal.row_number === row)) continue;
      // The book's first row repeats an invoice the catalogue holds.
      const id =
        row === 2 && template
          ? template.invoice_id
          : hex64(`book:${file.name}:${kind}:${row}`);
      if (ledger.invoices.some((invoice) => invoice.invoice_id === id)) {
        skippedDuplicate += 1;
        continue;
      }
      const baseCents = 4000 + row * 1250;
      const ivaCents = Math.round(baseCents * 0.21);
      const issued = `${fixtureYear}-${String(1 + (row % 9)).padStart(2, "0")}-1${row % 9}`;
      ledger.invoices.push({
        ...(template ?? ledger.invoices[0]!),
        invoice_id: id,
        kind,
        invoice_number: `LIB-${fixtureYear}-${String(row).padStart(3, "0")}`,
        issued_at: issued,
        operation_date: issued,
        counterparty_name: `Proveedor del libro ${row}, S.L.`,
        counterparty_tax_id: `B0000${String(row).padStart(4, "0")}`,
        counterparty_country: country ?? "ES",
        base_total: { decimal: money(baseCents) },
        iva_total: { decimal: money(ivaCents) },
        grand_total: { decimal: money(baseCents + ivaCents) },
        payment_status: "PENDING",
        linked_transaction_ids: [],
        source_filename: file.name,
        source_sha256: sha,
        source_row_index: row,
        lines: [],
      });
      created.push(id);
    }
    return {
      profile_id: LEDGER_FIXTURE_PROFILE_ID,
      source_sha256: sha,
      rows,
      created: created.length,
      skipped_duplicate: skippedDuplicate,
      refused: refusals as unknown as JsonValue,
      created_invoice_ids: created,
      unmapped_column_headers: ["Observaciones"],
      mapping_reasons: [],
    };
  }

  /** Documents added as evidence: a PDF or an XML is read at once, an image
   * waits for its reading, and a document already held is left as it is.
   * Where the local AI is not set up, an image cannot be read: it is paused,
   * and the run's pause names the local AI's setup. */
  function addDocuments(request: JsonObject): JsonObject {
    const sources = request.sources;
    const direction = request.direction;
    if (!Array.isArray(sources) || sources.length === 0) return invalid();
    if (direction !== "issued" && direction !== "received") return invalid();
    const items: JsonObject[] = [];
    let writes = 0;
    let paused = false;
    for (const token of sources) {
      const file = fileOf(token, "documents");
      const address = hex64(`document:${bytesOf(file.name)}`);
      const kind = file.name.split(".").pop()?.toLowerCase() ?? "";
      const image = kind !== "pdf" && kind !== "xml";
      const held = ledger.evidence.some(
        (record) => record.source_sha256 === address,
      );
      if (image && !held && readerMissing) {
        paused = true;
        items.push({
          content_address: address,
          identity: `${address}:${direction}`,
          direction,
          source_name: file.name,
          status: "paused",
          refusal_code: null,
          refusal_verdict: null,
          needed_inference: true,
          label_reading_fallback: null,
        });
        continue;
      }
      if (!held) {
        writes += 1;
        const at = now();
        ledger.evidence.push({
          evidence_id: hex64(`evidence:${address}`),
          bucket_id: LEDGER_FIXTURE_PROFILE_ID,
          source_sha256: address,
          attachment_id: address,
          media_kind: image ? "image" : "pdf",
          supplier: null,
          invoice_number: null,
          invoice_date: null,
          taxable_base: null,
          iva_rate: null,
          iva_amount: null,
          notes: "",
          created_at: at,
          updated_at: at,
          source_path: file.name,
        });
      }
      items.push({
        content_address: address,
        identity: `${address}:${direction}`,
        direction,
        source_name: file.name,
        status: held ? "no_op" : image ? "pending_review" : "ingested",
        refusal_code: null,
        refusal_verdict: null,
        needed_inference: image,
        label_reading_fallback: null,
      });
    }
    return {
      profile_id: LEDGER_FIXTURE_PROFILE_ID,
      write_count: writes,
      effect: writes > 0 ? "updated" : "none",
      direction,
      run: {
        items,
        unresolved: [],
        inference_pause: paused ? readerPause() : null,
      },
    };
  }

  /** The pause a batch reports when the local AI's program is not set up. */
  function readerPause(): JsonObject {
    return { facts: [{ name: "local_ai_state", value: "absent" }] };
  }

  return { importStatement, importInvoiceBook, addDocuments };
}
