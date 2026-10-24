// How the Import dialog previews and applies. A bank statement is read once
// per file in a dry run that writes nothing, and once more for each own
// account where the person has any: the account a file's rows name binds
// them the same way as choosing it, so a file whose rows come out the same
// either way names that account. The apply then sends each file alone with
// the account chosen for it and the digest its preview read, so a file that
// changed since is refused rather than imported. Invoice books have no dry
// run; documents are added in parts the host can carry. Nothing here keeps
// a value beyond the dialog's memory, and no write is ever sent twice.

import {
  ledgerFailure,
  type EvidenceBatchResult,
  type InvoiceImportResult,
  type InvoiceKind,
  type JsonObject,
  type LedgerDefinitionId,
  type LedgerImportRefusalCode,
  type LedgerImportResult,
  type LedgerPort,
  type LedgerProvider,
  type LedgerRequest,
  type LedgerResult,
  type LedgerTransaction,
  type PickedFile,
  type PublicPeriod,
} from "../../../shell/ledger";
import {
  sameDecimal,
  periodFilters,
  periodOf,
} from "../../../shell/ledgerGrammar";
import { importBatchFilters } from "../../../shell/ledgerImports";
import { readPage } from "../../../shell/ledgerWindow";

export const IMPORT_KINDS = ["bank", "book", "documents"] as const;
export type ImportKind = (typeof IMPORT_KINDS)[number];

export const LEDGER_PROVIDERS: readonly LedgerProvider[] = [
  "auto",
  "csv",
  "ofx",
  "qfx",
  "xlsx",
  "xls",
  "pdf",
];

/** The most own accounts a preview reads each file against, all files
 * together. Beyond it the person chooses every file's account. */
export const ACCOUNT_PROBE_LIMIT = 48;
/** The most documents one request adds; more are sent as further parts. */
export const DOCUMENTS_PER_PART = 16;

/** No own account: the rows stay unbound unless they name one. */
export const NO_ACCOUNT = "none";
/** An own account's id, or `NO_ACCOUNT`. */
export type AccountKey = string;

/** An own account as a choice: its label and masked number. */
export type OwnAccount = { id: string; label: string; masked: string };

/** What one call answered. A write that did not settle where the page
 * could see it is `unknown`: it may have been saved and is never sent
 * again. */
export type Attempt<Result> =
  | { kind: "settled"; result: Result }
  | { kind: "refused"; reason: string | null }
  | { kind: "failed"; code: string; reason: string | null };

async function attempt<D extends LedgerDefinitionId>(
  port: LedgerPort,
  definition: D,
  payload: LedgerRequest<D>,
  write: boolean,
): Promise<Attempt<LedgerResult<D>>> {
  try {
    const outcome = await port.submit(definition, payload);
    if (outcome.kind === "settled")
      return { kind: "settled", result: outcome.result };
    if (outcome.kind === "refused")
      return { kind: "refused", reason: outcome.reason };
    // Still running or waiting where the page stopped looking.
    return {
      kind: "failed",
      code: write ? "unknown" : "unavailable",
      reason: null,
    };
  } catch (error) {
    const failure = ledgerFailure(error);
    return {
      kind: "failed",
      code: failure.code,
      reason: failure.reason ?? null,
    };
  }
}

/** The registered own accounts, or null where they could not be read. */
export async function readOwnAccounts(
  port: LedgerPort,
): Promise<OwnAccount[] | null> {
  const read = await attempt(
    port,
    "ledger.own_account",
    { action: "list" },
    false,
  );
  if (read.kind !== "settled") return null;
  const accounts = (read.result as JsonObject).accounts;
  if (!Array.isArray(accounts)) return null;
  return accounts.flatMap((account) => {
    const found = account as JsonObject;
    return typeof found.own_account_id === "string"
      ? [
          {
            id: found.own_account_id,
            label: typeof found.label === "string" ? found.label : "",
            masked:
              typeof found.masked_iban === "string" ? found.masked_iban : "",
          },
        ]
      : [];
  });
}

export type BankOptions = {
  provider: LedgerProvider;
  period: PublicPeriod | null;
  /** Reports gaps, duplicates and parser notes as well. */
  verify: boolean;
};

/** One statement file as its preview read it. */
export type BankFilePreview =
  | {
      kind: "read";
      file: PickedFile;
      /** The digest of the bytes the preview read; null where it read no
       * rows, which leaves nothing to import. */
      digest: string | null;
      /** The dry run for each account read so far, and with no account. */
      byAccount: Partial<Record<AccountKey, LedgerImportResult>>;
      /** Accounts whose choice the file's own rows refuse. */
      mismatched: string[];
      /** The account the file's rows name, where they name a registered
       * one. */
      detected: string | null;
      /** Whether every registered account was read against it. */
      probed: boolean;
    }
  | { kind: "refused"; file: PickedFile; reason: LedgerImportRefusalCode }
  | { kind: "failed"; file: PickedFile; code: string };

const dryRun = (
  file: PickedFile,
  account: AccountKey,
  options: BankOptions,
): LedgerRequest<"ledger.import"> => ({
  files: [file.token],
  provider: options.provider,
  dry_run: true,
  verify: options.verify,
  period: options.period,
  own_account_id: account === NO_ACCOUNT ? null : account,
});

/** The movements a dry run would write or skip, as one sorted list. */
const rowIds = (result: LedgerImportResult) =>
  [...result.imported_transaction_refs, ...result.skipped_transaction_refs]
    .map((ref) => ref.transaction_id)
    .sort()
    .join(",");

/** The file's own refusal or digest in one dry run's answer. */
function readOf(result: LedgerImportResult) {
  const refusal = result.refused_files[0]?.reason_code ?? null;
  return { refusal, digest: result.source_digests[0]?.sha256 ?? null };
}

/** Previews one statement file: with no account, then against each own
 * account where `probe` allows. */
export async function previewBankFile(
  port: LedgerPort,
  file: PickedFile,
  options: BankOptions,
  accounts: readonly OwnAccount[],
  probe: boolean,
): Promise<BankFilePreview> {
  const base = await attempt(
    port,
    "ledger.import",
    dryRun(file, NO_ACCOUNT, options),
    false,
  );
  if (base.kind === "failed")
    return { kind: "failed", file, code: base.reason ?? base.code };
  if (base.kind === "refused")
    return { kind: "failed", file, code: base.reason ?? "refused" };
  const { refusal, digest } = readOf(base.result);
  if (refusal) return { kind: "refused", file, reason: refusal };
  const preview: Extract<BankFilePreview, { kind: "read" }> = {
    kind: "read",
    file,
    digest,
    byAccount: { [NO_ACCOUNT]: base.result },
    mismatched: [],
    detected: null,
    probed: false,
  };
  if (!probe || accounts.length === 0) return preview;
  for (const account of accounts) {
    const read = await previewForAccount(port, file, options, account.id);
    if (read.kind !== "read") return preview;
    if (read.refusal === "own_account_mismatch") {
      preview.mismatched.push(account.id);
      continue;
    }
    // The bytes changed between two reads of the same preview.
    if (read.refusal === "source_changed" || read.digest !== digest)
      return { kind: "refused", file, reason: "source_changed" };
    if (read.refusal) return { kind: "refused", file, reason: read.refusal };
    preview.byAccount[account.id] = read.result;
    if (
      preview.detected === null &&
      base.result.rows > 0 &&
      rowIds(read.result) === rowIds(base.result)
    )
      preview.detected = account.id;
  }
  preview.probed = true;
  return preview;
}

/** One dry run of `file` bound to `account`. */
export async function previewForAccount(
  port: LedgerPort,
  file: PickedFile,
  options: BankOptions,
  account: AccountKey,
): Promise<
  | {
      kind: "read";
      result: LedgerImportResult;
      refusal: LedgerImportRefusalCode | null;
      digest: string | null;
    }
  | { kind: "failed"; code: string }
> {
  const read = await attempt(
    port,
    "ledger.import",
    dryRun(file, account, options),
    false,
  );
  if (read.kind !== "settled")
    return {
      kind: "failed",
      code:
        read.kind === "failed"
          ? (read.reason ?? read.code)
          : (read.reason ?? "refused"),
    };
  return { kind: "read", result: read.result, ...readOf(read.result) };
}

/** Whose the rows of a previewed file are, where the file or the register
 * settles it, so the person is not asked. */
export type AccountFact =
  | { kind: "detected"; account: string }
  /** The rows name an account that is not registered: only no account
   * takes them. */
  | { kind: "unregistered" }
  | { kind: "no_accounts" }
  | { kind: "choose" };
export function accountFact(
  preview: Extract<BankFilePreview, { kind: "read" }>,
  accounts: readonly OwnAccount[],
): AccountFact {
  if (preview.detected) return { kind: "detected", account: preview.detected };
  if (accounts.length === 0) return { kind: "no_accounts" };
  if (preview.probed && preview.mismatched.length === accounts.length)
    return { kind: "unregistered" };
  return { kind: "choose" };
}

/** The account a file imports with: the one its rows name, the only one
 * possible, or the person's choice, which may still be missing. */
export function accountFor(
  fact: AccountFact,
  choice: AccountKey | undefined,
): AccountKey | undefined {
  if (fact.kind === "detected") return fact.account;
  if (fact.kind === "choose") return choice;
  return NO_ACCOUNT;
}

/** One file's apply, in the order they were sent. */
export type BankApplied =
  | { kind: "imported"; file: PickedFile; result: LedgerImportResult }
  | {
      kind: "refused";
      file: PickedFile;
      reason: LedgerImportRefusalCode | string;
    }
  /** Its bytes are not those the preview read: preview it again. */
  | { kind: "changed"; file: PickedFile }
  /** Sent, and not seen to settle: it may have been imported. */
  | { kind: "unknown"; file: PickedFile; code: string }
  /** Left unsent after a write whose outcome is not known. */
  | { kind: "not_sent"; file: PickedFile };

/** Failures that stop the files after them: the outcome is not known, or
 * no further write can be sent now. */
const STOPPING = new Set([
  "unknown",
  "saved_unread",
  "not_signed_in",
  "unavailable",
]);

export type BankApplyFile = {
  file: PickedFile;
  account: AccountKey;
  digest: string;
};

/** Imports each file alone, exactly as previewed, one after another. */
export async function applyBank(
  port: LedgerPort,
  files: readonly BankApplyFile[],
  options: BankOptions,
  progress: (done: number) => void,
): Promise<BankApplied[]> {
  const applied: BankApplied[] = [];
  let stopped = false;
  for (const { file, account, digest } of files) {
    if (stopped) {
      applied.push({ kind: "not_sent", file });
      continue;
    }
    const sent = await attempt(
      port,
      "ledger.import",
      {
        files: [file.token],
        provider: options.provider,
        dry_run: false,
        verify: options.verify,
        period: options.period,
        own_account_id: account === NO_ACCOUNT ? null : account,
        expected_source_sha256: [digest],
      },
      true,
    );
    if (sent.kind === "settled") {
      const refusal = sent.result.refused_files[0]?.reason_code;
      applied.push(
        refusal === "source_changed"
          ? { kind: "changed", file }
          : refusal
            ? { kind: "refused", file, reason: refusal }
            : { kind: "imported", file, result: sent.result },
      );
    } else if (sent.kind === "refused") {
      applied.push({ kind: "refused", file, reason: sent.reason ?? "refused" });
    } else if (sent.code === "unknown" || sent.code === "saved_unread") {
      applied.push({ kind: "unknown", file, code: sent.code });
      stopped = true;
    } else {
      applied.push({ kind: "refused", file, reason: sent.reason ?? sent.code });
      stopped = STOPPING.has(sent.code);
    }
    progress(applied.length);
  }
  return applied;
}

/** Imports an invoice book. It has no dry run: its rows are checked as
 * they are created. */
export function applyBook(
  port: LedgerPort,
  file: PickedFile,
  kind: InvoiceKind,
  country: string | null,
): Promise<Attempt<InvoiceImportResult>> {
  return attempt(
    port,
    "ledger.invoice.import",
    { kind, source_path: file.token, country },
    true,
  );
}

/** What adding documents came to, over every part sent. */
export type DocumentsApplied = {
  items: EvidenceBatchResult["run"]["items"];
  unresolved: EvidenceBatchResult["run"]["unresolved"];
  /** The part that did not settle, if one did not, and why. */
  stopped: { code: string; files: PickedFile[] } | null;
  /** Files of later parts, left unsent. */
  notSent: PickedFile[];
};

/** Adds documents as evidence in parts, stopping at a part that does not
 * settle. */
export async function applyDocuments(
  port: LedgerPort,
  files: readonly PickedFile[],
  direction: InvoiceKind,
  progress: (done: number) => void,
): Promise<DocumentsApplied> {
  const done: DocumentsApplied = {
    items: [],
    unresolved: [],
    stopped: null,
    notSent: [],
  };
  for (let at = 0; at < files.length; at += DOCUMENTS_PER_PART) {
    const part = files.slice(at, at + DOCUMENTS_PER_PART);
    if (done.stopped) {
      done.notSent.push(...part);
      continue;
    }
    const sent = await attempt(
      port,
      "ledger.evidence.batch",
      { sources: part.map((file) => file.token), direction },
      true,
    );
    if (sent.kind === "settled") {
      done.items.push(...sent.result.run.items);
      done.unresolved.push(...sent.result.run.unresolved);
    } else
      done.stopped = {
        code:
          sent.kind === "refused"
            ? (sent.reason ?? "refused")
            : sent.code === "unknown" || sent.code === "saved_unread"
              ? "unknown"
              : (sent.reason ?? sent.code),
        files: part,
      };
    progress(Math.min(files.length, at + part.length));
  }
  return done;
}

/** The first and last day of the movements of `batches`, read from the
 * ledger, or null where they could not be read. */
export async function readBatchSpan(
  port: LedgerPort,
  batches: readonly string[],
): Promise<{ from: string; to: string } | null> {
  let from: string | null = null;
  let to: string | null = null;
  for (const batch of batches) {
    for (const order of ["asc", "desc"] as const) {
      const read = await readPage(port, {
        filters: importBatchFilters(batch),
        sort_by: "date",
        sort_order: order,
        offset: 0,
        limit: 1,
      });
      if (read.kind !== "answer") return null;
      const day = read.result.rows[0]?.transaction.date;
      if (!day) continue;
      if (from === null || day < from) from = day;
      if (to === null || day > to) to = day;
    }
  }
  return from && to ? { from, to } : null;
}

/** A likely duplicate as imported, and the movements already in the
 * ledger on its day with its amount. */
export type DuplicatePair = {
  imported: LedgerTransaction;
  existing: LedgerTransaction[];
};

/** Reads an imported likely duplicate. */
export async function readImported(
  port: LedgerPort,
  id: string,
): Promise<LedgerTransaction | null> {
  const read = await attempt(
    port,
    "ledger.view",
    { transaction_prefix: id },
    false,
  );
  return read.kind === "settled" ? read.result.transaction : null;
}

/** The movements already in the ledger that `imported` was flagged
 * against: those on its day with its amount, other than itself. */
export async function readExisting(
  port: LedgerPort,
  imported: LedgerTransaction,
): Promise<LedgerTransaction[] | null> {
  const month = periodOf(imported.date, "month");
  if (!month) return null;
  const found: LedgerTransaction[] = [];
  for (let offset = 0; ;) {
    const read = await readPage(port, {
      filters: periodFilters(month),
      sort_by: "date",
      sort_order: "asc",
      offset,
      limit: 250,
    });
    if (read.kind !== "answer") return null;
    for (const row of read.result.rows)
      if (
        row.transaction.transaction_id !== imported.transaction_id &&
        row.transaction.date === imported.date &&
        sameDecimal(row.transaction.amount, imported.amount)
      )
        found.push(row.transaction);
    offset += read.result.rows.length;
    if (read.result.rows.length === 0 || offset >= read.result.total)
      return found;
  }
}
