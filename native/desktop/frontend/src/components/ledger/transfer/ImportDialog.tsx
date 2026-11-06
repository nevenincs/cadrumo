import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/components/ui/cn";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Icon } from "@/components/ui/icon";
import { IconButton } from "@/components/ui/icon-button";
import { listed } from "../../../shell/compose";
import type {
  FilePick,
  FilePurpose,
  LedgerPort,
  LedgerProvider,
  LedgerTransaction,
  PickedFile,
} from "../../../shell/ledger";
import type { InvoiceKind } from "../../../shell/ledgerInvoiceOperations";
import { publicPeriod, type LedgerPeriod } from "../../../shell/ledgerGrammar";
import type { ShowImportBatch } from "../../../shell/ledgerImports";
import { useStrings } from "../../../shell/strings";
import { formatCount } from "../../../shared/numbers";
import { landingSettle, useWritePause, WriteHold } from "../WritePause";
import {
  ACCOUNT_PROBE_LIMIT,
  NO_ACCOUNT,
  accountFact,
  accountFor,
  applyBank,
  applyBook,
  applyDocuments,
  importLanding,
  previewBankFile,
  previewForAccount,
  readBatchSpan,
  readImported,
  readOwnAccounts,
  type AccountKey,
  type BankFilePreview,
  type BankOptions,
  type ImportKind,
  type OwnAccount,
} from "./importModel";
import {
  ImportBankPreview,
  ImportPlainPreview,
  type ReadPreview,
} from "./ImportPreview";
import { ImportResultStep, type ImportOutcome } from "./ImportResult";
import { ImportWhatStep } from "./ImportWhatStep";

const PURPOSE: Record<ImportKind, Exclude<FilePurpose, "export">> = {
  bank: "bank_statements",
  book: "invoice_books",
  documents: "documents",
};
const STEPS = ["what", "preview", "result"] as const;
type Step = (typeof STEPS)[number];
/** How many imported likely duplicates the result reads to list. */
const DUPLICATES_SHOWN = 20;

type Progress = {
  kind: "reading" | "applying";
  done: number;
  total: number;
} | null;

/** The result a file's preview shows for the account it imports with. */
const shownResult = (preview: ReadPreview, account: AccountKey | undefined) =>
  preview.byAccount[account ?? NO_ACCOUNT] ?? preview.byAccount[NO_ACCOUNT]!;

function StepList({ step }: { step: Step }) {
  const t = useStrings();
  const at = STEPS.indexOf(step);
  return (
    <ol
      aria-label={t("desktop.ledger.import.steps")}
      className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground"
    >
      {STEPS.map((name, index) => (
        <li
          key={name}
          aria-current={index === at ? "step" : undefined}
          className={cn(
            "flex items-center gap-1",
            index === at && "font-medium text-foreground",
          )}
        >
          {index < at ? (
            <Icon name="tick" size="xs" />
          ) : (
            <span aria-hidden="true" className="tabular-nums">
              {index + 1}
            </span>
          )}
          {t(`desktop.ledger.import.step.${name}`)}
          {index < STEPS.length - 1 && (
            <Icon name="forward" size="xs" aria-hidden="true" />
          )}
        </li>
      ))}
    </ol>
  );
}

/**
 * Imports bank statements, an invoice book or documents in three steps:
 * what, a preview that writes nothing, then the apply of exactly what was
 * previewed and its result. Files come from the host's own dialogs or a
 * drop on the window and are shown by name only.
 */
export function ImportDialog({
  port,
  locale,
  period: pagePeriod,
  years,
  fallbackYear,
  onClose,
  onWritten,
  onShowImported,
  onShowDocuments,
  onCloseAutoFocus,
}: {
  port: LedgerPort;
  locale: string;
  /** The page's period, which the import period starts from. */
  period: LedgerPeriod | null;
  years: readonly number[] | null;
  fallbackYear: number;
  onClose(): void;
  /** Something may have been written: the page reads the ledger again. */
  onWritten(): void;
  onShowImported: ShowImportBatch;
  onShowDocuments(): void;
  /** Where the focus goes once the dialog has gone. */
  onCloseAutoFocus?: (event: Event) => void;
}) {
  const t = useStrings();
  const count = (value: number) => formatCount(locale, value);
  const heading = useRef<HTMLHeadingElement>(null);
  const issued = useRef(new Set<string>());
  const generation = useRef(0);
  const pickingNow = useRef(false);
  const [step, setStep] = useState<Step>("what");
  const [kind, setKind] = useState<ImportKind>("bank");
  const [files, setFilesNow] = useState<PickedFile[]>([]);
  // The files as last set, for a pick or a drop that answers after another.
  const held = useRef<PickedFile[]>([]);
  const setFiles = (next: PickedFile[]) => {
    held.current = next;
    setFilesNow(next);
  };
  const [leftOut, setLeftOut] = useState(0);
  const [over, setOver] = useState(false);
  const [picking, setPicking] = useState(false);
  const [pickFailed, setPickFailed] = useState(false);
  const [provider, setProvider] = useState<LedgerProvider>("auto");
  const [onlyPeriod, setOnlyPeriod] = useState<LedgerPeriod | null>(null);
  const [verify, setVerify] = useState(true);
  const [bookKind, setBookKind] = useState<InvoiceKind | null>(null);
  const [country, setCountry] = useState("");
  const [direction, setDirection] = useState<InvoiceKind | null>(null);
  const [accounts, setAccounts] = useState<OwnAccount[] | null>(null);
  const [previews, setPreviews] = useState<BankFilePreview[]>([]);
  const [choices, setChoices] = useState<Record<string, AccountKey>>({});
  const [reading, setReading] = useState<Set<string>>(new Set());
  const [progress, setProgress] = useState<Progress>(null);
  const [outcome, setOutcome] = useState<ImportOutcome | null>(null);
  const [duplicates, setDuplicates] = useState<LedgerTransaction[]>([]);
  const [showing, setShowing] = useState<"idle" | "reading" | "failed">("idle");
  const kindName = useId();

  const options: BankOptions = {
    provider,
    period: onlyPeriod ? publicPeriod(onlyPeriod) : null,
    verify,
  };
  const forget = (tokens: string[]) => {
    if (tokens.length === 0) return;
    tokens.forEach((token) => issued.current.delete(token));
    void port.forgetFiles(tokens as PickedFile["token"][]).catch(() => {});
  };
  // Every token goes when the dialog does.
  useEffect(() => {
    const held = issued.current;
    return () => {
      generation.current += 1;
      if (held.size > 0)
        void port
          .forgetFiles([...held] as PickedFile["token"][])
          .catch(() => {});
    };
  }, [port]);
  useEffect(() => {
    heading.current?.focus();
  }, [step]);
  useEffect(() => {
    let active = true;
    void readOwnAccounts(port).then((read) => {
      if (active) setAccounts(read ?? []);
    });
    return () => {
      active = false;
    };
  }, [port]);

  const take = (picked: PickedFile[], refused: number) => {
    picked.forEach((file) => issued.current.add(file.token));
    setLeftOut(refused);
    const current = held.current;
    if (kind === "book") {
      forget([...current, ...picked.slice(1)].map((file) => file.token));
      setFiles(picked.slice(0, 1));
      return;
    }
    const known = new Set(current.map((file) => file.name));
    const fresh = picked.filter((file) => !known.has(file.name));
    forget(
      picked.filter((file) => known.has(file.name)).map((file) => file.token),
    );
    setFiles([...current, ...fresh]);
  };
  const latestTake = useRef(take);
  latestTake.current = take;

  // A drop on the window adds files while the first step is shown.
  useEffect(() => {
    if (step !== "what") return;
    let stop: (() => void) | null = null;
    let active = true;
    void port
      .observeDrops(PURPOSE[kind], (signal) => {
        if (!active) {
          if (signal.kind === "dropped")
            void port
              .forgetFiles(signal.files.map((file) => file.token))
              .catch(() => {});
          return;
        }
        if (signal.kind === "over") setOver(true);
        else if (signal.kind === "left") setOver(false);
        else {
          setOver(false);
          latestTake.current(signal.files, signal.refused);
        }
      })
      .then((unobserve) => {
        if (active) stop = unobserve;
        else unobserve();
      })
      .catch(() => {});
    return () => {
      active = false;
      stop?.();
    };
  }, [port, step, kind]);

  const pick = async (how: FilePick) => {
    if (pickingNow.current) return;
    pickingNow.current = true;
    const mine = generation.current;
    setPicking(true);
    setPickFailed(false);
    try {
      const picks = await port.pickFiles(
        PURPOSE[kind],
        how,
        t(`desktop.ledger.import.filter.${kind}`),
      );
      if (mine !== generation.current) {
        void port
          .forgetFiles(picks.files.map((file) => file.token))
          .catch(() => {});
        return;
      }
      take(picks.files, picks.refused);
    } catch {
      if (mine === generation.current) setPickFailed(true);
    } finally {
      pickingNow.current = false;
      if (mine === generation.current) setPicking(false);
    }
  };
  const chooseKind = (next: ImportKind) => {
    if (pickingNow.current) return;
    forget(files.map((file) => file.token));
    setFiles([]);
    setLeftOut(0);
    setKind(next);
  };

  const countryValid = country === "" || /^[A-Z]{2}$/.test(country);
  const ready =
    files.length > 0 &&
    (kind === "bank" ||
      (kind === "book" && bookKind !== null && countryValid) ||
      (kind === "documents" && direction !== null));

  const previewBank = async (toRead: PickedFile[]) => {
    const known = accounts ?? (await readOwnAccounts(port)) ?? [];
    if (accounts === null) setAccounts(known);
    const probe = toRead.length * known.length <= ACCOUNT_PROBE_LIMIT;
    const read: BankFilePreview[] = [];
    setProgress({ kind: "reading", done: 0, total: toRead.length });
    for (const file of toRead) {
      read.push(await previewBankFile(port, file, options, known, probe));
      setProgress({ kind: "reading", done: read.length, total: toRead.length });
    }
    setProgress(null);
    return read;
  };
  const startPreview = async () => {
    if (kind === "bank") {
      setStep("preview");
      setPreviews([]);
      setChoices({});
      setPreviews(await previewBank(files));
    } else setStep("preview");
  };

  const readPreviews = previews.filter(
    (preview): preview is ReadPreview => preview.kind === "read",
  );
  const accountFacts = new Map(
    readPreviews.map((preview) => [
      preview.file.token,
      accountFact(preview, accounts ?? []),
    ]),
  );
  const accountOf = (preview: ReadPreview) =>
    accountFor(
      accountFacts.get(preview.file.token)!,
      choices[preview.file.token],
    );
  const shown = (preview: ReadPreview) =>
    shownResult(preview, accountOf(preview));
  const sendable = readPreviews.filter(
    (preview) => preview.digest !== null && shown(preview).imported > 0,
  );
  const missingAccount = sendable.some(
    (preview) => accountOf(preview) === undefined,
  );
  const nothingNew =
    kind === "bank" && progress === null && readPreviews.length > 0
      ? sendable.length === 0
      : false;

  const chooseAccount = async (preview: ReadPreview, account: AccountKey) => {
    const token = preview.file.token;
    setChoices((held) => ({ ...held, [token]: account }));
    if (preview.byAccount[account]) return;
    setReading((held) => new Set(held).add(token));
    const read = await previewForAccount(port, preview.file, options, account);
    setReading((held) => {
      const next = new Set(held);
      next.delete(token);
      return next;
    });
    setPreviews((held) =>
      held.map((item) => {
        if (item.kind !== "read" || item.file.token !== token) return item;
        if (read.kind !== "read")
          return { kind: "failed", file: item.file, code: read.code };
        if (read.refusal || read.digest !== item.digest)
          return {
            kind: "refused",
            file: item.file,
            reason: read.refusal ?? "source_changed",
            setup: read.refusal ? read.setup : null,
          };
        return {
          ...item,
          byAccount: { ...item.byAccount, [account]: read.result },
        };
      }),
    );
  };

  const pause = useWritePause();
  /** The settle of an import no read tells, which the product makes the
   * same when sent again: it reads `register` to know the ledger answers. */
  const repeatable = (what: string, register: "invoices" | "evidence") =>
    landingSettle(t, what, async () => {
      const read =
        register === "invoices"
          ? await port.submit("ledger.invoice.list", {}).catch(() => null)
          : await port.submit("ledger.evidence.list", {}).catch(() => null);
      return read?.kind === "settled" ? "repeatable" : null;
    });
  const apply = async () => {
    if (pause.held !== null) return;
    if (kind === "bank") {
      const plan = sendable.map((preview) => ({
        file: preview.file,
        account: accountOf(preview)!,
        digest: preview.digest!,
      }));
      // What each file's preview said it brings in, for a re-read to tell
      // whether an import not seen to settle wrote it.
      const importing = new Map(
        sendable.map((preview) => [
          preview.file.token,
          shown(preview).imported_transaction_refs.map(
            (ref) => ref.transaction_id,
          ),
        ]),
      );
      setProgress({ kind: "applying", done: 0, total: plan.length });
      const applied = await applyBank(port, plan, options, (done) =>
        setProgress({ kind: "applying", done, total: plan.length }),
      );
      setProgress(null);
      setOutcome({ kind: "bank", applied });
      setStep("result");
      const unseen = applied.flatMap((item) =>
        item.kind === "unknown" ? [item] : [],
      );
      if (unseen.length) {
        const what = listed(
          t,
          unseen.map((item) => item.file.name),
        );
        pause.hold({
          what,
          outcome: unseen.every((item) => item.code === "saved_unread")
            ? "saved_unread"
            : "unknown",
          settle: landingSettle(t, what, async () => {
            // The import stops at the first file not seen to settle.
            const found = await Promise.all(
              unseen.map((item) =>
                importLanding(port, importing.get(item.file.token) ?? []),
              ),
            );
            if (found.some((landing) => landing === null)) return null;
            return found.every((landing) => landing === "not_saved")
              ? "not_saved"
              : found.every((landing) => landing === "saved")
                ? "saved"
                : "repeatable";
          }),
        });
      }
      if (applied.some((item) => item.kind !== "not_sent")) onWritten();
      const flagged = applied.flatMap((item) =>
        item.kind === "imported"
          ? item.result.likely_duplicate_transaction_refs.map(
              (ref) => ref.transaction_id,
            )
          : [],
      );
      const read: LedgerTransaction[] = [];
      for (const id of flagged.slice(0, DUPLICATES_SHOWN)) {
        const movement = await readImported(port, id);
        if (movement) read.push(movement);
      }
      setDuplicates(read);
    } else if (kind === "book") {
      const file = files[0]!;
      setProgress({ kind: "applying", done: 0, total: 1 });
      const answer = await applyBook(port, file, bookKind!, country || null);
      setProgress(null);
      setOutcome({ kind: "book", file, answer });
      setStep("result");
      if (
        answer.kind === "failed" &&
        (answer.code === "unknown" || answer.code === "saved_unread")
      )
        pause.hold({
          what: file.name,
          outcome: answer.code,
          // No read says which rows a book holds before it is imported; the
          // import skips an invoice already in the catalogue
          // (`skipped_duplicate`), so sent again it adds nothing twice.
          settle: repeatable(file.name, "invoices"),
        });
      if (answer.kind !== "refused") onWritten();
    } else {
      setProgress({ kind: "applying", done: 0, total: files.length });
      const applied = await applyDocuments(port, files, direction!, (done) =>
        setProgress({ kind: "applying", done, total: files.length }),
      );
      setProgress(null);
      setOutcome({ kind: "documents", applied });
      setStep("result");
      const unseen = applied.stopped?.code;
      if (unseen === "unknown" || unseen === "saved_unread") {
        const what = listed(
          t,
          applied.stopped!.files.map((file) => file.name),
        );
        pause.hold({
          what,
          outcome: unseen,
          // The documents' content addresses are known only once read; a
          // document already held is left as it is (`no_op`), so sent
          // again the part adds nothing twice.
          settle: repeatable(what, "evidence"),
        });
      }
      onWritten();
    }
  };

  /** Previews again the files a changed file or an unknown write left. */
  const previewAgain = async (again: PickedFile[]) => {
    setOutcome(null);
    setDuplicates([]);
    setStep("preview");
    setPreviews([]);
    setPreviews(await previewBank(again));
  };

  const batches =
    outcome?.kind === "bank"
      ? outcome.applied.flatMap((item) =>
          item.kind === "imported" &&
          item.result.imported > 0 &&
          item.result.import_batch_id
            ? [item.result.import_batch_id]
            : [],
        )
      : [];
  const showImported = async () => {
    setShowing("reading");
    const span = await readBatchSpan(port, batches);
    if (!span) {
      setShowing("failed");
      return;
    }
    onShowImported({ batches, span });
    onClose();
  };

  const busy = progress !== null || reading.size > 0;
  const progressText =
    progress &&
    t(
      progress.kind === "reading"
        ? "desktop.ledger.import.reading"
        : "desktop.ledger.import.applying",
      { done: count(progress.done), total: count(progress.total) },
    );

  let body: ReactNode;
  let footer: ReactNode;
  if (step === "what") {
    body = (
      <ImportWhatStep
        t={t}
        locale={locale}
        kind={kind}
        kindName={kindName}
        onKind={chooseKind}
        files={files}
        leftOut={leftOut}
        over={over}
        picking={picking}
        pickFailed={pickFailed}
        onPick={pick}
        onRemove={(file) => {
          forget([file.token]);
          setFiles(files.filter((kept) => kept.token !== file.token));
        }}
        provider={provider}
        onProvider={setProvider}
        onlyPeriod={onlyPeriod}
        onOnlyPeriod={setOnlyPeriod}
        pagePeriod={pagePeriod}
        years={years}
        fallbackYear={fallbackYear}
        verify={verify}
        onVerify={setVerify}
        bookKind={bookKind}
        onBookKind={setBookKind}
        country={country}
        countryValid={countryValid}
        onCountry={setCountry}
        direction={direction}
        onDirection={setDirection}
      />
    );
    footer = (
      <>
        <Button variant="ghost" onClick={onClose}>
          {t("desktop.ledger.import.cancel")}
        </Button>
        <Button
          disabled={!ready || picking}
          onClick={() => !pickingNow.current && void startPreview()}
        >
          {t("desktop.ledger.import.preview")}
        </Button>
      </>
    );
  } else if (step === "preview") {
    body =
      kind === "bank" ? (
        <ImportBankPreview
          t={t}
          count={count}
          previews={previews}
          progressText={progressText}
          accounts={accounts ?? []}
          accountFacts={accountFacts}
          choices={choices}
          reading={reading}
          onChoose={(preview, account) => void chooseAccount(preview, account)}
          shown={shown}
          nothingNew={nothingNew}
        />
      ) : (
        <ImportPlainPreview
          t={t}
          locale={locale}
          kind={kind}
          files={files}
          bookKind={bookKind}
          country={country}
          direction={direction}
        />
      );
    const label =
      kind === "bank"
        ? nothingNew
          ? t("desktop.ledger.import.nothing_new")
          : t("desktop.ledger.import.apply_files", {
              count: sendable.length,
            })
        : kind === "book"
          ? t("desktop.ledger.import.apply_book")
          : t("desktop.ledger.import.apply_documents", {
              count: files.length,
            });
    footer = (
      <>
        <Button variant="ghost" disabled={busy} onClick={() => setStep("what")}>
          {t("desktop.ledger.import.back")}
        </Button>
        {missingAccount && (
          <span className="flex-1 text-sm text-muted-foreground">
            {t("desktop.ledger.import.choose_accounts")}
          </span>
        )}
        <WriteHold>
          <Button
            pending={progress?.kind === "applying"}
            disabled={
              kind === "bank" &&
              (previews.length === 0 || sendable.length === 0 || missingAccount)
            }
            onClick={() => void apply()}
          >
            {label}
          </Button>
        </WriteHold>
      </>
    );
  } else {
    const changed =
      outcome?.kind === "bank"
        ? outcome.applied.filter(
            (item) => item.kind === "changed" || item.kind === "not_sent",
          )
        : [];
    body = outcome && (
      <ImportResultStep
        t={t}
        locale={locale}
        count={count}
        port={port}
        outcome={outcome}
        duplicates={duplicates}
        progressText={progressText}
        showFailed={showing === "failed"}
      />
    );
    footer = (
      <>
        {batches.length > 0 && (
          <Button
            variant="outline"
            pending={showing === "reading"}
            onClick={() => void showImported()}
          >
            {t("desktop.ledger.import.show_imported")}
          </Button>
        )}
        {changed.length > 0 &&
          !(
            outcome?.kind === "bank" &&
            outcome.applied.some((item) => item.kind === "unknown")
          ) && (
            <Button
              variant="outline"
              onClick={() =>
                void previewAgain(changed.map((item) => item.file))
              }
            >
              {t("desktop.ledger.import.preview_again")}
            </Button>
          )}
        {outcome?.kind === "documents" &&
          outcome.applied.items.some(
            (item) =>
              item.status === "ingested" || item.status === "pending_review",
          ) && (
            <Button
              variant="outline"
              onClick={() => {
                onShowDocuments();
                onClose();
              }}
            >
              {t("desktop.ledger.import.show_documents")}
            </Button>
          )}
        <Button onClick={onClose}>{t("desktop.ledger.import.done")}</Button>
      </>
    );
  }

  return (
    <Dialog open onOpenChange={(open) => !open && !busy && onClose()}>
      <DialogContent
        placement="top"
        closeLabel={t("desktop.ledger.import.close")}
        className="ledger-import w-dialog-lg overflow-y-auto"
        onOpenAutoFocus={(event) => {
          event.preventDefault();
          heading.current?.focus();
        }}
        onCloseAutoFocus={onCloseAutoFocus}
      >
        <DialogHeader>
          <DialogTitle>{t("desktop.ledger.import.title")}</DialogTitle>
          <DialogDescription>
            {t("desktop.ledger.import.description")}
          </DialogDescription>
        </DialogHeader>
        <StepList step={step} />
        <div className="flex items-center gap-1">
          <h3
            ref={heading}
            tabIndex={-1}
            className="ledger-import-step font-medium text-foreground"
          >
            {t(`desktop.ledger.import.heading.${step}`)}
          </h3>
          {step === "preview" && kind === "bank" && (
            <IconButton
              label={t("desktop.ledger.import.bound_note")}
              size="xs"
              className="ledger-import-bound size-control-xs"
            >
              <Icon name="info" size="xs" />
            </IconButton>
          )}
        </div>
        <div className="grid gap-3">{body}</div>
        <DialogFooter sticky>{footer}</DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
