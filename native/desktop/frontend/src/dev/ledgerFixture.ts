// The scenario host's ledger: the ledger port answered from the synthetic
// ledger in ./fixtures/ledger.ts, held in this page's memory. It follows the
// registered contracts the page relies on: the list's order of filter, group
// selection, sort, group partition and page; a bulk classification that needs
// a classification on every row; a new id when a movement's amount,
// description, date or own account changes; refusals for rows a finalized
// revision cites; idempotency keys on add; and a model review answered only
// with the digest of the review the page read. What it answers is design and
// test evidence only. Its call lines name a definition, never a value.

import { answerInvoiceDuplicate } from "./ledgerDuplicateFixture";
import { answerRuleTrial } from "./ledgerRuleTrialFixture";
import { answerInvoiceMatch } from "./ledgerInvoiceMatchFixture";
import { answerSplitCheck } from "./ledgerSplitCheckFixture";
import {
  type FilePicks,
  type FilePurpose,
  type FileToken,
  isLedgerDefinition,
  type JsonObject,
  type JsonValue,
  type LedgerDefinitionId,
  type LedgerDropSignal,
  type LedgerErrorDetail,
  type LedgerOutcome,
  type LedgerPort,
  type LedgerResult,
  type LedgerReview,
} from "../shell/ledger";
import type {
  CatalogueInvoice,
  LedgerInvoiceDuplicateRequest,
  LedgerInvoiceMatchRequest,
} from "../shell/ledgerInvoiceOperations";
import type {
  LedgerSplitCheckRequest,
  LedgerStagedCheckRequest,
} from "../shell/ledgerMovementOperations";
import { RELAY_PAYLOAD_LIMIT, RELAY_REQUEST_LIMIT } from "../shell/relayBounds";
import { answerStagedCheck } from "./ledgerStagedCheckFixture";
import {
  cents,
  emptyLedger,
  type FixtureAccount,
  fixtureLedger,
  hex64,
  largeLedger,
  LEDGER_FIXTURE_PROFILE_ID,
  LEDGER_FIXTURE_TODAY,
  ledgerOfRows,
  money,
} from "./fixtures/ledger";
import { ledgerClassOf } from "./ledgerClassesFixture";
import { evidenceOperations } from "./ledgerEvidenceFixture";
import {
  invoiceOperations,
  InvoiceRequestInvalid,
  InvoiceStopped,
  InvoiceUnsettled,
} from "./ledgerInvoiceFixture";
import {
  MovementActionInvalid,
  movementActionOperations,
  MovementActionStopped,
} from "./ledgerMovementActionFixture";
import { setupOperations } from "./ledgerSetupFixture";
import {
  SetupKeptInPart,
  SetupRequestInvalid,
  SetupRequestUnrecorded,
  SetupStopped,
} from "./ledgerSetupSupport";
import {
  inPeriod,
  issues,
  knownValues,
  list,
  OWNED_PURCHASES,
  resolve,
  reviewStatus,
  row,
  Stopped,
} from "./ledgerQueryFixture";
import { PICKABLE, PURPOSE_KINDS } from "./ledgerFileFixture";
import {
  IBAN_THE_BACKEND_REFUSES,
  invalid,
  OWN_ACCOUNT_SECRETS,
  reject,
  text,
  unrecorded,
} from "./ledgerRequestFixture";
import { entryOperations } from "./ledgerEntryFixture";
import { importOperations } from "./ledgerImportFixture";
import { fixtureInstant } from "@/dev/fixtureDates";

/** The longest reply, in bytes of compact JSON, the host takes from the
 * relay; one longer is lost. */
const REPLY_LIMIT = 16 * 1024 * 1024;
/** What the host puts around a payload on the request line, with the room of
 * the request id it adds. */
const LINE_FRAME = {
  action: "operation_submit",
  subject_ref: "profile:00000000-0000-4000-8000-000000000000",
};
const REQUEST_ID_ROOM = 14 + 36 + 1 + 1;
const encoder = new TextEncoder();
/** A movement's id as the registered review request takes it. */
const CANONICAL_ID = /^[0-9a-f]{64}$/;

/** Whether the host refuses the request before sending it: the payload's
 * bytes of compact JSON, or the whole request's. */
export function tooLarge(definition: string, request: JsonObject): boolean {
  if (encoder.encode(JSON.stringify(request)).length > RELAY_PAYLOAD_LIMIT)
    return true;
  const line = JSON.stringify({
    action: LINE_FRAME.action,
    definition_id: definition,
    subject_ref: LINE_FRAME.subject_ref,
    payload: request,
  });
  return encoder.encode(line).length + REQUEST_ID_ROOM > RELAY_REQUEST_LIMIT;
}

/** Whether a reply is over the host's bound. */
export function replyTooLarge(result: JsonValue): boolean {
  const text = JSON.stringify(result);
  // Three bytes bound a character here, so only a long text is counted.
  return (
    text.length * 3 > REPLY_LIMIT && encoder.encode(text).length > REPLY_LIMIT
  );
}

/** How the scenario's ledger answers. */
export const LEDGER_SHAPES = [
  "fixture",
  "empty",
  "refused",
  "unknown",
  "unavailable",
  "slow",
  "large",
  "documents",
  // The `documents` ledger on a computer whose local AI is not set up.
  "reader_missing",
] as const;
export type LedgerShape = (typeof LEDGER_SHAPES)[number];

/** Delay added to every answer of the `slow` shape. */
const SLOW_MS = 4000;
/** How long a cancelled review takes to settle, as a worker that notices
 * the cancel at its next step would. */
const CANCEL_SETTLE_MS = 40;

declare global {
  interface Window {
    /** The active synthetic ledger port, for controlled transport delays. */
    __fixtureLedger?: LedgerPort;
    /** File transport hooks also reached through copied host methods. */
    __fixtureLedgerFiles?: {
      picked?: (picks: FilePicks) => Promise<FilePicks>;
      forgotten?: (tokens: FileToken[]) => void;
    };
    /** Controls for what the scenario's ledger cannot get from a person. */
    __scenarioLedger?: {
      /** Drops files with these names on the window. */
      drop(names: string[]): void;
      /** Changes every pending review, as a model reading again would. */
      changeReviews(): void;
      /** Changes a file's bytes, as editing it on disk between a preview
       * and an import would. */
      changeFile(name: string): void;
      /** Answers the next writes so, one each: `unknown` lands the write
       * and leaves its settlement unobserved, `lost` leaves it unknown
       * without its ever running, `saved_unread` lands it and loses its
       * answer, `refused` refuses it whole and writes nothing. */
      nextWrites(
        outcomes: ("unknown" | "lost" | "saved_unread" | "refused")[],
      ): void;
      /** Answers the next `count` reads of `definition` as unavailable,
       * as a runtime that did not answer them; with `where`, only reads
       * whose request carries each of its values. */
      nextReads(definition: string, count: number, where?: JsonObject): void;
      holdTracks(): void;
      releaseTracks(): void;
      pendingTracks(): number;
      /** Changes a stored movement's field, as another window saving it
       * would. */
      editElsewhere(id: string, field: string, value: string | null): void;
      /** The model reviews still waiting, by definition and movement,
       * cancelling ones included until they settle. */
      waitingReviews(): { definition: string; transaction: string }[];
      /** Asks the model about a movement from another window, which keeps
       * the review waiting there. */
      reviewElsewhere(id: string): void;
    };
  }
}

/** How often each made-up file was changed since the page loaded: the
 * made-up computer's, shared by every ledger the page makes. */
const edits = new Map<string, number>();
type Controls = NonNullable<Window["__scenarioLedger"]>;
/** Every ledger the page made. The development entry may make more than one
 * for one run, and the controls reach the one the page uses among them. */
const ledgers = new Set<Omit<Controls, "changeFile">>();

type Options = {
  say: (call: string) => void;
  wait: () => Promise<void>;
  signedIn: () => boolean;
  shape: LedgerShape;
  /** The language the backend words a refusal in; English when not given. */
  language?: string;
};

export function ledgerFixture(options: Options): LedgerPort {
  const { say, signedIn, shape } = options;
  // `ledgerRows` in the page's address sets how many movements the fourth
  // quarter of 2026 holds, for measuring the grid at any size.
  const rows = Math.trunc(
    Number(new URLSearchParams(window.location.search).get("ledgerRows")),
  );
  const ledger =
    shape === "empty"
      ? emptyLedger()
      : rows > 0
        ? ledgerOfRows(rows)
        : shape === "large"
          ? largeLedger()
          : fixtureLedger();
  let clock = 0;
  const now = () => {
    clock += 1;
    return `${LEDGER_FIXTURE_TODAY}T12:${String(Math.floor(clock / 60) % 60).padStart(2, "0")}:${String(clock % 60).padStart(2, "0")}Z`;
  };
  let operations = 0;
  const outcomes = new Map<string, LedgerOutcome>();
  type Pending = {
    definition: LedgerDefinitionId;
    request: JsonObject;
    transaction: string;
    /** What its lease holds: one waiting review per subject and
     * definition. */
    subject: string;
    version: number;
    shown: string | null;
    /** Cancelled, and not yet settled: it still holds its subject. */
    cancelling: boolean;
  };
  // A classification review is held per movement and can be cancelled
  // while it waits; a split review still holds the whole profile and
  // cannot be.
  const subjectOf = (definition: LedgerDefinitionId, transaction: string) =>
    definition === "ledger.classify.review"
      ? `transaction:${transaction}`
      : `profile:${LEDGER_FIXTURE_PROFILE_ID}`;
  const cancellableReview = (definition: LedgerDefinitionId) =>
    definition === "ledger.classify.review";
  const reviews = new Map<string, Pending>();
  // How the next writes are answered, where a scenario asked.
  const queued: ("unknown" | "lost" | "saved_unread" | "refused")[] = [];
  // How many of the next reads of a definition answer nothing.
  const failingReads = new Map<string, number>();
  let tracksHeld: Promise<void> | null = null;
  let releaseTracks = () => {};
  let pendingTracks = 0;
  // Reads that fail only where their request carries these values.
  const failingWhere: {
    definition: string;
    where: JsonObject;
    count: number;
  }[] = [];
  const files = new Map<FileToken, { name: string; purpose: FilePurpose }>();
  // The save tokens an export has written a file to.
  const written = new Set<FileToken>();
  const bytesOf = (name: string) =>
    hex64(`bytes:${name}:${edits.get(name) ?? 0}`);
  const drops = new Set<(signal: LedgerDropSignal) => void>();
  let dropPurpose: Exclude<FilePurpose, "export"> = "bank_statements";

  const answer = async () => {
    await options.wait();
    if (shape === "slow")
      await new Promise((done) => window.setTimeout(done, SLOW_MS));
    if (shape === "unavailable") reject("unavailable");
    if (!signedIn()) reject("not_signed_in");
  };
  const nextOperation = () => {
    operations += 1;
    return hex64(`operation:${operations}`);
  };
  const settle = (operation: string, result: JsonValue): LedgerOutcome => {
    const outcome: LedgerOutcome = {
      kind: "settled",
      operation_id: operation,
      revision: 3,
      result: result as JsonObject,
    };
    outcomes.set(operation, outcome);
    return outcome;
  };
  const events = () => [hex64(`event:${now()}`)];

  const issue = (name: string, purpose: FilePurpose): FileToken => {
    const token =
      `file-${hex64(`file:${files.size}:${name}`).slice(0, 32)}` as FileToken;
    files.set(token, { name, purpose });
    return token;
  };
  const take = (names: string[], purpose: FilePurpose): FilePicks => {
    const picks: FilePicks = { files: [], refused: 0 };
    for (const name of names) {
      const kind = name.split(".").pop()?.toLowerCase() ?? "";
      if (PURPOSE_KINDS[purpose].includes(kind))
        picks.files.push({
          token: issue(name, purpose),
          name,
          bytes: 2048 + name.length * 97,
        });
      else picks.refused += 1;
    }
    return picks;
  };
  const fileOf = (token: JsonValue | undefined, purpose: FilePurpose) => {
    if (typeof token !== "string") return invalid();
    const found = files.get(token as FileToken);
    if (!found) return reject("file_unavailable");
    if (found.purpose !== purpose) return invalid();
    return found;
  };

  ledgers.add({
    drop(names) {
      if (drops.size === 0) return;
      const picks = take(names, dropPurpose);
      drops.forEach((listener) => {
        listener({ kind: "over" });
        listener({ kind: "dropped", ...picks });
      });
    },
    changeReviews() {
      reviews.forEach((pending) => {
        pending.version += 1;
      });
    },
    nextWrites(next) {
      queued.push(...next);
    },
    nextReads(definition, count, where) {
      if (where) failingWhere.push({ definition, where, count });
      else
        failingReads.set(
          definition,
          (failingReads.get(definition) ?? 0) + count,
        );
    },
    holdTracks() {
      tracksHeld ??= new Promise<void>((resolve) => {
        releaseTracks = () => {
          tracksHeld = null;
          resolve();
        };
      });
    },
    releaseTracks: () => releaseTracks(),
    pendingTracks: () => pendingTracks,
    editElsewhere(id, field, value) {
      const movement = transactionOf(id);
      if (!movement) return;
      (movement.transaction as unknown as Record<string, string | null>)[
        field
      ] = field === "notes" || field === "counterparty" ? (value ?? "") : value;
      movement.transaction.modified_at = now();
    },
    waitingReviews: () =>
      [...reviews.values()].map((pending) => ({
        definition: pending.definition,
        transaction: pending.transaction,
      })),
    reviewElsewhere(id) {
      reviews.set(nextOperation(), {
        definition: "ledger.classify.review",
        request: {
          transaction_id: id,
          mode: "classification",
          origin: "classify_llm_apply",
        },
        transaction: id,
        subject: subjectOf("ledger.classify.review", id),
        version: 0,
        shown: null,
        cancelling: false,
      });
    },
  });
  window.__scenarioLedger = {
    drop: (names) => ledgers.forEach((made) => made.drop(names)),
    changeReviews: () => ledgers.forEach((made) => made.changeReviews()),
    nextWrites: (next) => ledgers.forEach((made) => made.nextWrites(next)),
    nextReads: (definition, count, where) =>
      ledgers.forEach((made) => made.nextReads(definition, count, where)),
    holdTracks: () => ledgers.forEach((made) => made.holdTracks()),
    releaseTracks: () => ledgers.forEach((made) => made.releaseTracks()),
    pendingTracks: () =>
      [...ledgers].reduce((total, made) => total + made.pendingTracks(), 0),
    editElsewhere: (id, field, value) =>
      ledgers.forEach((made) => made.editElsewhere(id, field, value)),
    waitingReviews: () => [...ledgers].flatMap((made) => made.waitingReviews()),
    reviewElsewhere: (id) =>
      ledgers.forEach((made) => made.reviewElsewhere(id)),
    changeFile(name) {
      edits.set(name, (edits.get(name) ?? 0) + 1);
    },
  };

  const {
    transactionOf,
    update,
    classifyRow,
    classify,
    bulk,
    add,
    status,
    preflight,
  } = entryOperations(ledger, {
    now,
    events,
    staleFilings: (period) => setupWork.staleFilings(period),
  });
  const { importStatement, importInvoiceBook, addDocuments } = importOperations(
    ledger,
    {
      now,
      events,
      bytesOf,
      fileOf,
      transactionOf,
      readerMissing: shape === "reader_missing",
    },
  );

  function exportLedger(request: JsonObject): JsonObject {
    const target = fileOf(request.output_path, "export");
    const format = (request.export_format as string | undefined) ?? "csv";
    if (target.name.split(".").pop() !== format) return invalid();
    written.add(request.output_path as FileToken);
    const rows = ledger.movements.filter(
      (movement) =>
        (request.include_inactive === true ||
          movement.transaction.lifecycle_state === "ACTIVE") &&
        inPeriod(movement, request.period),
    );
    return {
      profile_id: LEDGER_FIXTURE_PROFILE_ID,
      bucket_id: LEDGER_FIXTURE_PROFILE_ID,
      export_id: hex64(`export:${now()}`),
      export_format: format,
      media_type:
        format === "csv"
          ? "text/csv"
          : format === "jsonl"
            ? "application/x-ndjson"
            : "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      filename_extension: format,
      row_count: rows.length,
      byte_size: rows.length * 312,
      sha256: hex64(`export-bytes:${rows.length}`),
      fieldnames: [
        "transaction_id",
        "booked_date",
        "amount",
        "direction",
        "description",
      ],
      rows: [],
      bucket_event_ids: events(),
      output_path: target.name,
    };
  }

  /** Adds an own account or changes its details; the window sees it
   * masked, as the product publishes it. */
  function changeAccount(request: JsonObject): JsonObject {
    const action = request.action;
    const iban = text(request.iban);
    const id =
      action === "add"
        ? `acc-${String(ledger.accounts.length + 1).padStart(2, "0")}`
        : text(request.own_account_id);
    const existing = ledger.accounts.find(
      (account) => account.own_account_id === id,
    );
    if (action === "add" && (!iban || !text(request.label))) return invalid();
    if (iban === IBAN_THE_BACKEND_REFUSES)
      throw new Stopped("REFUSED_LEDGER_OWN_ACCOUNT_REGISTER_VALIDATION");
    if (action === "update" && !existing)
      throw new Stopped("ERROR_TRANSACTION_VALIDATION");
    const masked = iban
      ? `${iban.slice(0, 2).toUpperCase()}**${iban.slice(-4)}`
      : (existing?.masked_iban ?? "");
    const holding = text(request.holding) ?? existing?.holding ?? "titular";
    const account: FixtureAccount = {
      own_account_id: id!,
      label: text(request.label) ?? existing?.label ?? "",
      holding: holding === "cotitular" ? "cotitular" : "titular",
      masked_iban: masked,
      country_code: masked.slice(0, 2),
      sepa_marca: "1",
      has_swift_bic:
        Boolean(text(request.swift_bic)) || (existing?.has_swift_bic ?? false),
      has_bank_block:
        Boolean(text(request.bank_name)) || (existing?.has_bank_block ?? false),
      currency: text(request.currency) ?? existing?.currency ?? "EUR",
      opened_on: text(request.opened_on) ?? existing?.opened_on ?? null,
      closed_on: existing?.closed_on ?? null,
    };
    if (existing) Object.assign(existing, account);
    else ledger.accounts.push(account);
    return {
      profile_id: LEDGER_FIXTURE_PROFILE_ID,
      action: action as string,
      own_account_id: id,
      accounts: [account as unknown as JsonValue],
      designations: [],
      changed: true,
    };
  }
  function ownAccount(request: JsonObject): JsonObject {
    const action = text(request.action);
    const id = text(request.own_account_id);
    const accounts = ledger.accounts;
    if (action === "add" || action === "update") return changeAccount(request);
    if (action === "list")
      return {
        profile_id: LEDGER_FIXTURE_PROFILE_ID,
        action,
        own_account_id: null,
        accounts: accounts as unknown as JsonValue,
        designations: [...setupWork.designations()],
        changed: false,
      };
    if (action === "show") {
      const found = accounts.find((account) => account.own_account_id === id);
      if (!found) throw new Stopped("ERROR_TRANSACTION_VALIDATION");
      return {
        profile_id: LEDGER_FIXTURE_PROFILE_ID,
        action,
        own_account_id: id,
        accounts: [found as unknown as JsonValue],
        designations: [],
        changed: false,
      };
    }
    return setupWork.ownAccount(request);
  }

  const setupWork = setupOperations(ledger, {
    profileId: LEDGER_FIXTURE_PROFILE_ID,
    today: LEDGER_FIXTURE_TODAY,
    now,
    events,
    hex64,
    fileOf: (token) => fileOf(token, "documents"),
    language: options.language ?? "en",
  });
  const movementWork = movementActionOperations(ledger, {
    profileId: LEDGER_FIXTURE_PROFILE_ID,
    now,
    events,
    hex64,
  });
  const invoiceWork = invoiceOperations(ledger, {
    profileId: LEDGER_FIXTURE_PROFILE_ID,
    events,
    hex64,
  });
  const evidenceWork = evidenceOperations(ledger, {
    profileId: LEDGER_FIXTURE_PROFILE_ID,
    events,
    hex64,
    now,
    fileOf: (token) => fileOf(token, "documents"),
    issuesFor: (period) => issues(ledger, period),
    seed: shape === "documents" || shape === "reader_missing",
    readerMissing: shape === "reader_missing",
    language: options.language ?? "en",
  });
  const reads: Partial<
    Record<LedgerDefinitionId, (request: JsonObject) => JsonObject>
  > = {
    ...invoiceWork.reads,
    ...evidenceWork.reads,
    ...movementWork.reads,
    ...setupWork.reads,
    "ledger.known-values": (request) => knownValues(ledger, request),
    "ledger.rule.trial": (request) => {
      const answer = answerRuleTrial(
        request.description_pattern as string,
        request.transaction_ids as string[],
        (id) =>
          ledger.movements.find(
            (each) => each.transaction.transaction_id === id,
          )?.transaction,
        LEDGER_FIXTURE_PROFILE_ID,
      );
      if (!answer) throw new Error("unrecorded rule trial");
      return answer as unknown as JsonObject;
    },
    "ledger.invoice.duplicate": (request) =>
      answerInvoiceDuplicate(
        request as unknown as LedgerInvoiceDuplicateRequest,
        ledger.invoices,
        LEDGER_FIXTURE_PROFILE_ID,
      ) as unknown as JsonObject,
    "ledger.invoice.match": (request) =>
      answerInvoiceMatch(
        request as unknown as LedgerInvoiceMatchRequest,
        ledger.movements,
        ledger.invoices,
        LEDGER_FIXTURE_PROFILE_ID,
      ) as unknown as JsonObject,
    "ledger.split.check": (request) => {
      const movement = ledger.movements.find(
        (each) => each.transaction.transaction_id === request.transaction_id,
      );
      if (!movement) throw new Error("no such movement to split");
      return answerSplitCheck(
        movement.transaction.amount,
        request.parts as LedgerSplitCheckRequest["parts"],
        LEDGER_FIXTURE_PROFILE_ID,
      ) as unknown as JsonObject;
    },
    "ledger.staged.check": (request) => {
      const answer = answerStagedCheck(
        request as unknown as LedgerStagedCheckRequest,
        (id) => {
          const movement = ledger.movements.find(
            (each) => each.transaction.transaction_id === id,
          );
          return movement ? row(movement) : undefined;
        },
        LEDGER_FIXTURE_PROFILE_ID,
      );
      if (!answer) throw new Error("unrecorded staged check");
      return answer as unknown as JsonObject;
    },
    "ledger.list": (request) => list(ledger, request),
    "ledger.view": (request) => {
      const owned = OWNED_PURCHASES[request.transaction_prefix as string];
      const movement = owned
        ? {
            ...ledger.movements[0]!,
            transaction: {
              ...ledger.movements[0]!.transaction,
              description: owned,
            },
          }
        : resolve(ledger, request.transaction_prefix);
      return {
        profile_id: LEDGER_FIXTURE_PROFILE_ID,
        transaction_prefix: request.transaction_prefix as string,
        transaction: { ...movement.transaction } as unknown as JsonValue,
        review_status: reviewStatus(
          movement.transaction.business_classification,
        ),
        latest_llm_rejection: movement.llm_rejected
          ? {
              occurred_at: fixtureInstant(10, 2, "09:30:00Z"),
              operator_reason: "La propuesta no reconoce el proveedor.",
            }
          : null,
      };
    },
    "ledger.invoice.list": (request) => ({
      profile_id: LEDGER_FIXTURE_PROFILE_ID,
      kind: (request.kind as string | null | undefined) ?? null,
      invoices: ledger.invoices.filter((invoice: CatalogueInvoice) =>
        request.kind ? invoice.kind === request.kind : true,
      ) as unknown as JsonValue,
    }),
    "ledger.status": status,
    "ledger.preflight": preflight,
    "ledger.rule.list": () => ({
      profile_id: LEDGER_FIXTURE_PROFILE_ID,
      rules: ledger.rules as unknown as JsonValue,
    }),
  };
  const writes: Partial<
    Record<LedgerDefinitionId, (request: JsonObject) => JsonObject>
  > = {
    "ledger.update": update,
    "ledger.classify.single": classify,
    "ledger.classify.bulk": bulk,
    "ledger.add": add,
    "ledger.import": importStatement,
    "ledger.export": exportLedger,
    "ledger.invoice.import": importInvoiceBook,
    "ledger.evidence.batch": addDocuments,
    ...invoiceWork.writes,
    ...evidenceWork.writes,
    ...movementWork.writes,
    ...setupWork.writes,
    "ledger.remove": movementWork.remove,
  };

  function suggestion(pending: Pending, operation: string) {
    const movement = transactionOf(pending.transaction);
    const t = movement?.transaction;
    const mode = text(pending.request.mode) ?? "classification";
    // A household supply is proposed as Mixed, with the share the person
    // asked with or none; anything else as an office expense.
    const mixed =
      t !== undefined &&
      (t.business_classification === "MIXED" ||
        /FIBRA|LUZ|ELECTRICA/.test(t.description));
    const share = text(pending.request.business_pct);
    const gross = t ? cents(t.amount) : 0;
    const base = Math.round(gross / 1.21);
    const saturated = mode === "saturated";
    const halves = [Math.floor(gross / 2), gross - Math.floor(gross / 2)];
    return {
      projection_version: 1,
      profile_id: LEDGER_FIXTURE_PROFILE_ID,
      reviewed_proposal_digest: hex64(
        `proposal:${operation}:${pending.version}`,
      ),
      suggestion: {
        kind:
          mode === "split" || mode === "auto_split"
            ? "split"
            : saturated
              ? "saturated"
              : "classification",
        transaction_id: pending.transaction,
        provenance: "llm:local-medium",
        reason:
          pending.version === 0
            ? "The counterparty and the description match an office supplier."
            : "Read again: the description matches an office supplier.",
        evidence_id: t?.purchase_invoice_evidence_id ?? null,
        classification: mixed ? "MIXED" : "BUSINESS",
        category: mixed ? (t?.category_id ?? null) : "material_oficina",
        confidence: pending.version === 0 ? "0.82" : "0.79",
        multiple_components: mode === "split" || mode === "auto_split",
        business_pct: mixed ? share : null,
        iva_category: "domestic_general",
        iva_rate: saturated ? "0.21" : null,
        taxable_base: saturated ? money(base) : null,
        iva_amount: saturated ? money(gross - base) : null,
        rate_derivable: saturated,
        derivation_note: saturated ? "Registry rate for domestic_general." : "",
        evidence_advisory: "",
        parent_amount: mode === "split" && t ? t.amount : null,
        children:
          mode === "split" && t
            ? halves.map((part, at) => ({
                proportion: "0.5",
                amount: money(part),
                description: `${t.description} · ${at + 1}`,
                category: "material_oficina",
                iva_category: "domestic_general",
                iva_rate: null,
                taxable_base: null,
                iva_amount: null,
                rate_derivable: false,
                derivation_note: "",
                evidence_citation: "",
              }))
            : [],
      },
    };
  }

  /** Whether settling `definition` may change records: the host's class of
   * the definition alone decides it, whatever the request names. */
  const changes = (definition: LedgerDefinitionId) =>
    ledgerClassOf(definition) !== "read";

  async function run(
    definition: string,
    payload: unknown,
  ): Promise<LedgerOutcome> {
    say(`ledger ${definition}`);
    await answer();
    if (definition === "ledger.track" && tracksHeld) {
      pendingTracks++;
      try {
        await tracksHeld;
      } finally {
        pendingTracks--;
      }
    }
    if (!isLedgerDefinition(definition)) return reject("not_admitted");
    if (
      typeof payload !== "object" ||
      payload === null ||
      Array.isArray(payload)
    )
      return reject("invalid");
    const request = payload as JsonObject;
    if ("profile_id" in request || "source_directory" in request)
      return reject("invalid");
    if (
      definition === "ledger.own_account" &&
      OWN_ACCOUNT_SECRETS.some((field) => field in request)
    )
      return reject("invalid");
    // A review names its movement by the full id the registered request
    // decodes; a short handle or another spelling is refused there.
    if (
      ledgerClassOf(definition) === "review" &&
      !(
        typeof request.transaction_id === "string" &&
        CANONICAL_ID.test(request.transaction_id)
      )
    )
      return reject("invalid");
    if (tooLarge(definition, request)) return reject("too_large");
    const mutation = changes(definition);
    if (mutation && shape === "refused")
      return reject("refused", { reason: "operation_unavailable" });
    const narrowed = mutation
      ? undefined
      : failingWhere.find(
          (found) =>
            found.definition === definition &&
            found.count > 0 &&
            Object.entries(found.where).every(
              ([key, value]) =>
                JSON.stringify(request[key]) === JSON.stringify(value),
            ),
        );
    if (narrowed) {
      narrowed.count -= 1;
      return reject("unavailable");
    }
    const failing = mutation ? 0 : (failingReads.get(definition) ?? 0);
    if (failing > 0) {
      failingReads.set(definition, failing - 1);
      return reject("unavailable");
    }
    // A second review of a subject one already holds is refused before it
    // is submitted, as the runtime's lease refuses it.
    if (ledgerClassOf(definition) === "review") {
      const asked = ledger.movements.find(
        (movement) =>
          movement.transaction.transaction_id === request.transaction_id,
      );
      const subject =
        asked &&
        subjectOf(
          definition as LedgerDefinitionId,
          asked.transaction.transaction_id,
        );
      if (
        subject &&
        [...reviews.values()].some(
          (pending) =>
            pending.definition === definition && pending.subject === subject,
        )
      )
        return reject("refused", { reason: "subject_busy" });
    }
    const operation = nextOperation();
    try {
      if (ledgerClassOf(definition) === "review") {
        const movement = resolve(ledger, request.transaction_id);
        const reviewed = definition as LedgerDefinitionId;
        reviews.set(operation, {
          definition: reviewed,
          request,
          transaction: movement.transaction.transaction_id,
          subject: subjectOf(reviewed, movement.transaction.transaction_id),
          version: 0,
          shown: null,
          cancelling: false,
        });
        const paused: LedgerOutcome = {
          kind: "review",
          operation_id: operation,
          revision: 2,
          cancellable: cancellableReview(reviewed),
        };
        outcomes.set(operation, paused);
        return paused;
      }
      const handle =
        definition === "ledger.own_account"
          ? ownAccount
          : (writes[definition] ?? reads[definition]);
      if (!handle) return reject("unavailable");
      const asked = mutation ? queued.shift() : undefined;
      if (asked === "refused") {
        // Refused whole, as a revision-guarded save that found the ledger
        // changed: nothing was written.
        const refused: LedgerOutcome = {
          kind: "refused",
          operation_id: operation,
          revision: 3,
          reason: "precondition_failed",
          detail: null,
        };
        outcomes.set(operation, refused);
        return refused;
      }
      // Sent, and never run: nothing was written, and nothing can be
      // observed of it.
      if (asked === "lost")
        return reject("unknown", { operation_id: operation });
      const result = handle(request);
      // The write landed; its settlement was not observed, but it can be:
      // observing the operation answers what it settled.
      if (mutation && (shape === "unknown" || asked === "unknown")) {
        settle(operation, result);
        return reject("unknown", { operation_id: operation });
      }
      // The write landed and its answer was lost after it settled.
      if (mutation && asked === "saved_unread") {
        settle(operation, result);
        return reject("saved_unread", { operation_id: operation });
      }
      // A reply over the bound is lost: a write may have landed, a read
      // answered nothing.
      if (replyTooLarge(result)) {
        if (!mutation) return reject("unavailable");
        settle(operation, result);
        return reject("unknown", { operation_id: operation });
      }
      return settle(operation, result);
    } catch (error) {
      if (
        error instanceof InvoiceRequestInvalid ||
        error instanceof MovementActionInvalid
      )
        return invalid();
      if (error instanceof SetupRequestInvalid) return invalid();
      if (error instanceof SetupRequestUnrecorded) return unrecorded();
      if (error instanceof SetupKeptInPart) {
        // The refusal settled with a partial effect, which the host reports
        // as a write that stopped, not as a refusal that wrote nothing.
        return reject("unknown", {
          operation_id: operation,
          terminal_failure: {
            operation_id: operation,
            definition_id: definition,
            effect: "partial",
            refusal_words: null,
          },
        });
      }
      if (error instanceof SetupStopped) {
        const refused: LedgerOutcome = {
          kind: "refused",
          operation_id: operation,
          revision: 3,
          reason: error.reason,
          detail: error.detail as unknown as LedgerErrorDetail | null,
        };
        outcomes.set(operation, refused);
        return refused;
      }
      if (error instanceof MovementActionStopped) {
        const refused: LedgerOutcome = {
          kind: "refused",
          operation_id: operation,
          revision: 3,
          reason: error.reason,
          detail: null,
        };
        outcomes.set(operation, refused);
        return refused;
      }
      if (error instanceof InvoiceUnsettled)
        return reject("unknown", { operation_id: operation });
      if (error instanceof InvoiceStopped) {
        const refused: LedgerOutcome = {
          kind: "refused",
          operation_id: operation,
          revision: 3,
          reason: error.reason,
          detail: error.detail as unknown as LedgerErrorDetail,
        };
        outcomes.set(operation, refused);
        return refused;
      }
      if (!(error instanceof Stopped)) throw error;
      const stopped: LedgerOutcome = {
        kind: "refused",
        operation_id: operation,
        revision: 3,
        reason: error.reason,
        detail: null,
      };
      outcomes.set(operation, stopped);
      return stopped;
    }
  }

  const port: LedgerPort = {
    async submit(definition, payload) {
      window.__fixtureLedger = port;
      const outcome = await run(definition, payload);
      return outcome as LedgerOutcome<LedgerResult<typeof definition>>;
    },
    async observe(operation) {
      say("ledger observe");
      await answer();
      return outcomes.get(operation) ?? reject("not_admitted");
    },
    async review<Review>(operation: string) {
      say("ledger review");
      await answer();
      const pending = reviews.get(operation);
      if (!outcomes.has(operation)) return reject("not_admitted");
      if (!pending || pending.cancelling)
        return reject("review_changed", { reason: "not_pending" });
      const review = suggestion(pending, operation);
      pending.shown = hex64(JSON.stringify(review));
      const shown: LedgerReview<Review> = {
        operation_id: operation,
        revision: 2 + pending.version,
        review_digest: pending.shown,
        expires_at: null,
        review: review as Review,
      };
      return shown;
    },
    async answer(operation, reviewDigest, decision) {
      say(`ledger answer ${decision}`);
      await answer();
      const pending = reviews.get(operation);
      if (!pending || pending.cancelling)
        return reject("review_changed", { reason: "not_pending" });
      if (pending.shown !== reviewDigest) return reject("review_changed");
      // The review may have changed since the page read it.
      if (
        hex64(JSON.stringify(suggestion(pending, operation))) !== reviewDigest
      )
        return reject("review_changed", { reason: "review_changed" });
      if (shape === "refused")
        return reject("refused", { reason: "operation_unavailable" });
      const movement = transactionOf(pending.transaction);
      const proposal = suggestion(pending, operation).suggestion;
      const refuse = (reason: string): LedgerOutcome => {
        reviews.delete(operation);
        const refused: LedgerOutcome = {
          kind: "refused",
          operation_id: operation,
          revision: 3,
          reason,
          detail: null,
        };
        outcomes.set(operation, refused);
        return refused;
      };
      // An explicit rejection cannot apply; a Mixed proposal applies only
      // with a share.
      if (
        decision === "apply" &&
        (pending.request.origin === "classify_llm_reject" ||
          (proposal.classification === "MIXED" &&
            proposal.business_pct === null))
      )
        return refuse("ERROR_TRANSACTION_VALIDATION");
      if (
        movement &&
        (movement.sealed || movement.transaction.lifecycle_state !== "ACTIVE")
      )
        return refuse("ERROR_TRANSACTION_VALIDATION");
      reviews.delete(operation);
      if (decision === "apply" && movement) {
        if (proposal.kind === "split")
          movementWork.writes["ledger.split.manual"]!({
            transaction_id: pending.transaction,
            children: proposal.children.map((child) => ({
              amount: child.amount,
              description: child.description,
            })),
          });
        else
          classifyRow(
            movement,
            {
              classification: proposal.classification,
              category_id: proposal.category,
              business_pct: proposal.business_pct,
              iva_category: proposal.iva_category,
              ...(proposal.rate_derivable
                ? {
                    iva_rate: proposal.iva_rate,
                    taxable_base: proposal.taxable_base,
                    iva_amount: proposal.iva_amount,
                  }
                : {}),
            },
            "llm:local-medium",
          );
      }
      if (decision === "reject" && movement) movement.llm_rejected = true;
      movementWork.noteReview(
        pending.transaction,
        decision,
        text(pending.request.reason) ?? "",
      );
      if (shape === "unknown")
        return reject("unknown", { operation_id: operation });
      return settle(operation, {
        identity: {
          operation_id: operation,
          definition_id: pending.definition,
          subject_ref: `profile:${LEDGER_FIXTURE_PROFILE_ID}`,
        },
        request: { ...pending.request, profile_id: LEDGER_FIXTURE_PROFILE_ID },
        response: decision,
        result: {
          profile_id: LEDGER_FIXTURE_PROFILE_ID,
          reviewed_proposal_digest: suggestion(pending, operation)
            .reviewed_proposal_digest,
          outcome: decision === "apply" ? "classified" : "rejected",
          transaction_id: pending.transaction,
          provenance: proposal.provenance,
          operator_reason: text(pending.request.reason) ?? "",
        },
      });
    },
    async cancel(operation, revision) {
      say("ledger cancel");
      await answer();
      const observed = outcomes.get(operation);
      if (!observed) return reject("not_admitted");
      const pending = reviews.get(operation);
      const refuse = (reason: string) =>
        reject("refused", { operation_id: operation, reason });
      if (!pending) return refuse("operation_terminal");
      if (!cancellableReview(pending.definition))
        return refuse("cancellation_unsupported");
      if (pending.cancelling) return observed;
      if (observed.revision !== revision)
        return refuse("stale_operation_revision");
      // It has written nothing: cancelled, it settles with no effect and
      // lets its subject go once its worker notices.
      pending.cancelling = true;
      const settling: LedgerOutcome = {
        kind: "running",
        operation_id: operation,
        revision: revision + 1,
        cancellable: false,
      };
      outcomes.set(operation, settling);
      window.setTimeout(() => {
        reviews.delete(operation);
        outcomes.set(operation, {
          kind: "refused",
          operation_id: operation,
          revision: revision + 2,
          reason: null,
          detail: null,
        });
      }, CANCEL_SETTLE_MS);
      return settling;
    },
    async pickFiles(purpose, pick) {
      say(`ledger pickFiles ${purpose} ${pick}`);
      await answer();
      const offered = PICKABLE[purpose];
      const picks = take(
        pick === "file" ? offered.slice(0, 1) : offered,
        purpose,
      );
      return window.__fixtureLedgerFiles?.picked?.(picks) ?? picks;
    },
    async saveFile(format, _filterLabel, suggestedName) {
      say(`ledger saveFile ${format}`);
      await answer();
      const name = suggestedName ?? `movimientos-2026.${format}`;
      const picks =
        name.split(".").pop() === format
          ? take([name], "export")
          : { files: [], refused: 1 };
      return window.__fixtureLedgerFiles?.picked?.(picks) ?? picks;
    },
    async revealFile(token) {
      say("ledger revealFile");
      await answer();
      const file = files.get(token);
      if (!file) return reject("file_unavailable");
      if (file.purpose !== "export") return reject("invalid");
      if (!written.has(token)) return reject("file_unavailable");
    },
    async forgetFiles(tokens) {
      say("ledger forgetFiles");
      window.__fixtureLedgerFiles?.forgotten?.(tokens);
      tokens.forEach((token) => {
        files.delete(token);
        written.delete(token);
      });
    },
    async observeDrops(purpose, listener) {
      say(`ledger observeDrops ${purpose}`);
      dropPurpose = purpose;
      drops.add(listener);
      return () => {
        drops.delete(listener);
      };
    },
    async changeOwnAccount(change) {
      say("ledger changeOwnAccount");
      try {
        await answer();
        let request: JsonObject;
        try {
          request = JSON.parse(new TextDecoder().decode(change)) as JsonObject;
        } catch {
          return reject("invalid");
        }
        if (request.action !== "add" && request.action !== "update")
          return reject("invalid");
        if (shape === "refused")
          return reject("refused", { reason: "operation_unavailable" });
        const operation = nextOperation();
        try {
          const result = changeAccount(request);
          if (shape === "unknown")
            return reject("unknown", { operation_id: operation });
          return settle(operation, result);
        } catch (error) {
          if (!(error instanceof Stopped)) throw error;
          return {
            kind: "refused",
            operation_id: operation,
            revision: 3,
            reason: error.reason,
            detail: null,
          };
        }
      } finally {
        change.fill(0);
      }
    },
  };
  return port;
}
