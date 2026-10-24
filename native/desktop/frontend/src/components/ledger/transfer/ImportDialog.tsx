import {
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
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
import { Field, FieldDescription, FieldLabel } from "@/components/ui/field";
import { Icon, type IconName } from "@/components/ui/icon";
import { IconButton } from "@/components/ui/icon-button";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  SegmentedControl,
  SegmentedControlItem,
} from "@/components/ui/segmented-control";
import { Spinner } from "@/components/ui/spinner";
import { Switch } from "@/components/ui/switch";
import type {
  FilePick,
  FilePurpose,
  InvoiceImportResult,
  InvoiceKind,
  LedgerImportResult,
  LedgerPort,
  LedgerProvider,
  LedgerTransaction,
  PickedFile,
} from "../../../shell/ledger";
import {
  periodOf,
  publicPeriod,
  type LedgerPeriod,
} from "../../../shell/ledgerGrammar";
import type { ShowImportBatch } from "../../../shell/ledgerImports";
import { useStrings, type Translate } from "../../../shell/strings";
import { localDay } from "../../../shared/dates";
import { SetupOffer } from "../../setup/SetupOffer";
import { PeriodSelector } from "../PeriodSelector";
import { landingSettle, useWritePause, WriteHold } from "../WritePause";
import {
  ACCOUNT_PROBE_LIMIT,
  IMPORT_KINDS,
  LEDGER_PROVIDERS,
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
  readExisting,
  readImported,
  readOwnAccounts,
  type AccountKey,
  type Attempt,
  type BankApplied,
  type BankFilePreview,
  type BankOptions,
  type DocumentsApplied,
  type ImportKind,
  type OwnAccount,
} from "./importModel";
import {
  amountText,
  dayText,
  diagnosticText,
  importRefusal,
  providerName,
  sizeText,
} from "./transferWords";

const PURPOSE: Record<ImportKind, Exclude<FilePurpose, "export">> = {
  bank: "bank_statements",
  book: "invoice_books",
  documents: "documents",
};
const STEPS = ["what", "preview", "result"] as const;
type Step = (typeof STEPS)[number];
/** How many imported likely duplicates the result reads to list. */
const DUPLICATES_SHOWN = 20;

type ReadPreview = Extract<BankFilePreview, { kind: "read" }>;
type Progress = {
  kind: "reading" | "applying";
  done: number;
  total: number;
} | null;
type Outcome =
  | { kind: "bank"; applied: BankApplied[] }
  | { kind: "book"; file: PickedFile; answer: Attempt<InvoiceImportResult> }
  | { kind: "documents"; applied: DocumentsApplied };

const fileIcon = (name: string): IconName =>
  /\.(png|jpe?g|tiff?|webp|heic|heif)$/i.test(name)
    ? "image"
    : /\.(pdf|xml)$/i.test(name)
      ? "page"
      : "sheet";

/** The result a file's preview shows for the account it imports with. */
const shownResult = (preview: ReadPreview, account: AccountKey | undefined) =>
  preview.byAccount[account ?? NO_ACCOUNT] ?? preview.byAccount[NO_ACCOUNT]!;

function Counts({ items }: { items: [string, number][] }) {
  return (
    <dl className="ledger-import-counts flex flex-wrap gap-x-4 gap-y-1 text-sm">
      {items.map(([label, value]) => (
        <div key={label} className="flex gap-1.5">
          <dt className="text-muted-foreground">{label}</dt>
          <dd className="font-medium tabular-nums">{value}</dd>
        </div>
      ))}
    </dl>
  );
}

/** One file in a list: its kind's icon, its name and what is said of it. */
function FileRow({
  name,
  icon,
  children,
  refused = false,
  action,
}: {
  name: string;
  icon?: IconName;
  children?: ReactNode;
  refused?: boolean;
  action?: ReactNode;
}) {
  return (
    <li
      data-refused={refused || undefined}
      className="flex items-start gap-2 rounded-md border border-border px-2.5 py-2"
    >
      {/* A file that cannot be read is a refusal, not a danger: its glyph
          says so, in the ink of the rest. */}
      <Icon
        name={icon ?? (refused ? "refused" : fileIcon(name))}
        className={cn("mt-0.5", refused && "text-muted-foreground")}
      />
      <div className="grid min-w-0 flex-1 gap-1">
        <span className="font-medium [overflow-wrap:anywhere]">{name}</span>
        {children}
      </div>
      {action}
    </li>
  );
}

/** A likely duplicate as imported, beside what it was flagged against. */
function DuplicateCompare({
  port,
  locale,
  imported,
}: {
  port: LedgerPort;
  locale: string;
  imported: LedgerTransaction;
}) {
  const t = useStrings();
  const [open, setOpen] = useState(false);
  const [existing, setExisting] = useState<LedgerTransaction[] | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    if (!open || existing !== null || failed) return;
    let active = true;
    void readExisting(port, imported).then((found) => {
      if (!active) return;
      if (found === null) setFailed(true);
      else setExisting(found);
    });
    return () => {
      active = false;
    };
  }, [open, existing, failed, port, imported]);
  const facts = (movement: LedgerTransaction) => (
    <div className="grid gap-0.5 rounded-md bg-accent p-2 text-sm">
      <span className="font-medium [overflow-wrap:anywhere]">
        {movement.description}
      </span>
      {movement.counterparty && (
        <span className="text-muted-foreground">{movement.counterparty}</span>
      )}
      <span className="tabular-nums">
        {amountText(locale, movement.amount, movement.currency)} ·{" "}
        {t(
          `desktop.ledger.import.direction.${movement.direction.toLowerCase()}`,
        )}{" "}
        · {dayText(locale, movement.date)}
      </span>
    </div>
  );
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button variant="link" size="xs">
          {t("desktop.ledger.import.compare")}
        </Button>
      </PopoverTrigger>
      <PopoverContent
        align="start"
        aria-label={t("desktop.ledger.import.compare_title")}
        className="ledger-duplicate grid w-dialog gap-2"
      >
        <p className="font-medium">
          {t("desktop.ledger.import.compare_title")}
        </p>
        <div className="grid gap-1">
          <span className="text-xs text-muted-foreground">
            {t("desktop.ledger.import.compare_imported")}
          </span>
          {facts(imported)}
        </div>
        <div className="grid gap-1">
          <span className="text-xs text-muted-foreground">
            {t("desktop.ledger.import.compare_existing")}
          </span>
          {failed ? (
            <p role="alert" className="text-sm">
              {t("desktop.ledger.import.compare_failed")}
            </p>
          ) : existing === null ? (
            <Spinner label={t("desktop.ledger.import.compare_reading")} />
          ) : existing.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              {t("desktop.ledger.import.compare_none")}
            </p>
          ) : (
            existing.map((movement) => (
              <div key={movement.transaction_id}>{facts(movement)}</div>
            ))
          )}
        </div>
        <p className="text-xs text-muted-foreground">
          {t("desktop.ledger.import.compare_note")}
        </p>
      </PopoverContent>
    </Popover>
  );
}

/** A preview's likely duplicates as a glyph and a count, opening what
 * happens to them. The preview names no row of its own, so the comparison
 * with the movement already stored waits for the import. */
function DuplicatesChip({
  t,
  count,
  shown,
}: {
  t: Translate;
  count: number;
  shown: string;
}) {
  const name = t("desktop.ledger.import.duplicates_chip", { count: shown });
  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button
          variant="pill"
          size="xs"
          className="ledger-import-duplicates-chip w-fit tabular-nums"
          aria-label={name}
          data-count={count}
        >
          <Icon name="alert" size="xs" className="text-warning" />
          <span aria-hidden="true">{shown}</span>
        </Button>
      </PopoverTrigger>
      <PopoverContent
        align="start"
        aria-label={name}
        className="ledger-import-duplicates-note grid w-dialog gap-1"
      >
        <p className="font-medium">{name}</p>
        <p className="text-sm text-muted-foreground">
          {t("desktop.ledger.import.duplicates_note")}
        </p>
      </PopoverContent>
    </Popover>
  );
}

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
  const numbers = useMemo(() => new Intl.NumberFormat(locale), [locale]);
  const count = (value: number) => numbers.format(value);
  const heading = useRef<HTMLHeadingElement>(null);
  const issued = useRef(new Set<string>());
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
  const [outcome, setOutcome] = useState<Outcome | null>(null);
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
    setPicking(true);
    setPickFailed(false);
    try {
      const picks = await port.pickFiles(
        PURPOSE[kind],
        how,
        t(`desktop.ledger.import.filter.${kind}`),
      );
      take(picks.files, picks.refused);
    } catch {
      setPickFailed(true);
    } finally {
      setPicking(false);
    }
  };
  const chooseKind = (next: ImportKind) => {
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
  const facts = new Map(
    readPreviews.map((preview) => [
      preview.file.token,
      accountFact(preview, accounts ?? []),
    ]),
  );
  const accountOf = (preview: ReadPreview) =>
    accountFor(facts.get(preview.file.token)!, choices[preview.file.token]);
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
        const what = unseen.map((item) => item.file.name).join(", ");
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
      if (applied.stopped?.code === "unknown") {
        const what = applied.stopped.files.map((file) => file.name).join(", ");
        pause.hold({
          what,
          outcome: "unknown",
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
      <WhatStep
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
        <Button disabled={!ready} onClick={() => void startPreview()}>
          {t("desktop.ledger.import.preview")}
        </Button>
      </>
    );
  } else if (step === "preview") {
    body =
      kind === "bank" ? (
        <BankPreview
          t={t}
          count={count}
          previews={previews}
          progressText={progressText}
          accounts={accounts ?? []}
          facts={facts}
          choices={choices}
          reading={reading}
          onChoose={(preview, account) => void chooseAccount(preview, account)}
          shown={shown}
          nothingNew={nothingNew}
        />
      ) : (
        <PlainPreview
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
      <ResultStep
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

function WhatStep({
  t,
  locale,
  kind,
  kindName,
  onKind,
  files,
  leftOut,
  over,
  picking,
  pickFailed,
  onPick,
  onRemove,
  provider,
  onProvider,
  onlyPeriod,
  onOnlyPeriod,
  pagePeriod,
  years,
  fallbackYear,
  verify,
  onVerify,
  bookKind,
  onBookKind,
  country,
  countryValid,
  onCountry,
  direction,
  onDirection,
}: {
  t: Translate;
  locale: string;
  kind: ImportKind;
  kindName: string;
  onKind(kind: ImportKind): void;
  files: PickedFile[];
  leftOut: number;
  over: boolean;
  picking: boolean;
  pickFailed: boolean;
  onPick(how: FilePick): void;
  onRemove(file: PickedFile): void;
  provider: LedgerProvider;
  onProvider(provider: LedgerProvider): void;
  onlyPeriod: LedgerPeriod | null;
  onOnlyPeriod(period: LedgerPeriod | null): void;
  pagePeriod: LedgerPeriod | null;
  years: readonly number[] | null;
  fallbackYear: number;
  verify: boolean;
  onVerify(verify: boolean): void;
  bookKind: InvoiceKind | null;
  onBookKind(kind: InvoiceKind): void;
  country: string;
  countryValid: boolean;
  onCountry(country: string): void;
  direction: InvoiceKind | null;
  onDirection(direction: InvoiceKind): void;
}) {
  const ids = useId();
  const directionChoice = (
    value: InvoiceKind | null,
    onChange: (next: InvoiceKind) => void,
    label: string,
  ) => (
    <Field>
      <FieldLabel id={`${ids}-${label}`}>{t(label)}</FieldLabel>
      <SegmentedControl
        aria-labelledby={`${ids}-${label}`}
        value={value ?? ""}
        onValueChange={(next) => onChange(next as InvoiceKind)}
      >
        <SegmentedControlItem value="received">
          {t("desktop.ledger.import.kind_received")}
        </SegmentedControlItem>
        <SegmentedControlItem value="issued">
          {t("desktop.ledger.import.kind_issued")}
        </SegmentedControlItem>
      </SegmentedControl>
    </Field>
  );
  return (
    <>
      <Field>
        {/* The step's heading already says this on screen; the control
            keeps its name. */}
        <FieldLabel id={kindName} className="sr-only">
          {t("desktop.ledger.import.what")}
        </FieldLabel>
        <SegmentedControl
          aria-labelledby={kindName}
          value={kind}
          onValueChange={(next) => onKind(next as ImportKind)}
        >
          {IMPORT_KINDS.map((value) => (
            <SegmentedControlItem key={value} value={value}>
              {t(`desktop.ledger.import.kind.${value}`)}
            </SegmentedControlItem>
          ))}
        </SegmentedControl>
      </Field>
      <div
        data-over={over || undefined}
        className={cn(
          "ledger-import-drop grid justify-items-center gap-2 rounded-lg border-2 p-4 text-center",
          over
            ? "border-solid border-foreground"
            : "border-dashed border-border-strong",
        )}
      >
        <Icon name="upload" size="lg" className="text-muted-foreground" />
        <p>{t(`desktop.ledger.import.drop.${kind}`)}</p>
        <div className="flex flex-wrap justify-center gap-2">
          <Button
            variant="outline"
            size="sm"
            pending={picking}
            onClick={() => onPick(kind === "book" ? "file" : "files")}
          >
            {t(
              kind === "book"
                ? "desktop.ledger.import.choose_file"
                : "desktop.ledger.import.choose_files",
            )}
          </Button>
          {kind !== "book" && (
            <Button
              variant="ghost"
              size="sm"
              disabled={picking}
              onClick={() => onPick("folder")}
            >
              {t("desktop.ledger.import.choose_folder")}
            </Button>
          )}
        </div>
        <p className="text-xs text-muted-foreground">
          {t(`desktop.ledger.import.accepts.${kind}`)}
        </p>
      </div>
      {pickFailed && (
        <p role="alert" className="text-sm">
          {t("desktop.ledger.import.pick_failed")}
        </p>
      )}
      {leftOut > 0 && (
        <p role="status" className="text-sm text-muted-foreground">
          {t("desktop.ledger.import.left_out", { count: leftOut })}
        </p>
      )}
      {files.length > 0 && (
        <ul
          aria-label={t("desktop.ledger.import.chosen")}
          className="ledger-import-files grid gap-1"
        >
          {files.map((file) => (
            <FileRow
              key={file.token}
              name={file.name}
              action={
                <IconButton
                  label={t("desktop.ledger.import.remove", { name: file.name })}
                  onClick={() => onRemove(file)}
                >
                  <Icon name="close" />
                </IconButton>
              }
            >
              {file.bytes !== null && (
                <span className="text-xs text-muted-foreground">
                  {sizeText(locale, file.bytes)}
                </span>
              )}
            </FileRow>
          ))}
        </ul>
      )}
      {kind === "bank" && (
        <div className="grid gap-3">
          <Field>
            <FieldLabel htmlFor={`${ids}-provider`}>
              {t("desktop.ledger.import.provider_label")}
            </FieldLabel>
            <NativeSelect
              id={`${ids}-provider`}
              value={provider}
              onChange={(event) =>
                onProvider(event.target.value as LedgerProvider)
              }
            >
              {LEDGER_PROVIDERS.map((value) => (
                <option key={value} value={value}>
                  {providerName(t, value)}
                </option>
              ))}
            </NativeSelect>
          </Field>
          <div className="grid gap-1.5">
            <label className="flex items-center gap-2 text-sm">
              <Switch
                checked={onlyPeriod !== null}
                onCheckedChange={(on) =>
                  onOnlyPeriod(
                    on ? (pagePeriod ?? periodOf(localDay(), "quarter")) : null,
                  )
                }
              />
              {t("desktop.ledger.import.only_period")}
            </label>
            {onlyPeriod ? (
              <PeriodSelector
                value={onlyPeriod}
                onChange={(next) => next && onOnlyPeriod(next)}
                label={t("desktop.ledger.import.period")}
                years={years}
                locale={locale}
                fallbackYear={fallbackYear}
                allowAll={false}
                className="justify-self-start"
              />
            ) : (
              <p className="text-xs text-muted-foreground">
                {t("desktop.ledger.import.any_date")}
              </p>
            )}
          </div>
          <label className="flex items-center gap-2 text-sm">
            <Switch checked={verify} onCheckedChange={onVerify} />
            {t("desktop.ledger.import.verify")}
          </label>
          <p className="text-sm text-muted-foreground">
            {t("desktop.ledger.import.account_later")}
          </p>
        </div>
      )}
      {kind === "book" && (
        <div className="grid gap-3">
          {directionChoice(
            bookKind,
            onBookKind,
            "desktop.ledger.import.book_kind",
          )}
          <Field data-invalid={!countryValid || undefined}>
            <FieldLabel htmlFor={`${ids}-country`}>
              {t("desktop.ledger.import.country")}
            </FieldLabel>
            <Input
              id={`${ids}-country`}
              value={country}
              maxLength={2}
              autoComplete="off"
              aria-invalid={!countryValid || undefined}
              aria-describedby={`${ids}-country-hint`}
              className="w-control-lg uppercase"
              onChange={(event) =>
                onCountry(event.target.value.toUpperCase().trim())
              }
            />
            <FieldDescription id={`${ids}-country-hint`}>
              {countryValid
                ? t("desktop.ledger.import.country_hint")
                : t("desktop.ledger.import.country_invalid", {
                    value: country,
                  })}
            </FieldDescription>
          </Field>
        </div>
      )}
      {kind === "documents" &&
        directionChoice(
          direction,
          onDirection,
          "desktop.ledger.import.documents_kind",
        )}
    </>
  );
}

function BankPreview({
  t,
  count,
  previews,
  progressText,
  accounts,
  facts,
  choices,
  reading,
  onChoose,
  shown,
  nothingNew,
}: {
  t: Translate;
  count(value: number): string;
  previews: BankFilePreview[];
  progressText: string | null;
  accounts: OwnAccount[];
  facts: Map<string, ReturnType<typeof accountFact>>;
  choices: Record<string, AccountKey>;
  reading: Set<string>;
  onChoose(preview: ReadPreview, account: AccountKey): void;
  shown(preview: ReadPreview): LedgerImportResult;
  nothingNew: boolean;
}) {
  const ids = useId();
  if (previews.length === 0)
    return (
      <p role="status" className="flex items-center gap-2 text-sm">
        <Spinner />
        {progressText ?? t("desktop.ledger.import.reading_start")}
      </p>
    );
  const read = previews.filter(
    (preview): preview is ReadPreview => preview.kind === "read",
  );
  const total = (pick: (result: LedgerImportResult) => number) =>
    read.reduce((sum, preview) => sum + pick(shown(preview)), 0);
  const accountName = (id: string) => {
    const account = accounts.find((held) => held.id === id);
    return account ? `${account.label} · ${account.masked}` : id;
  };
  return (
    <>
      {nothingNew && (
        <Alert tone="success" icon={<Icon name="check" />}>
          <AlertTitle>{t("desktop.ledger.import.nothing_new")}</AlertTitle>
          <AlertDescription>
            {t("desktop.ledger.import.nothing_new_note")}
          </AlertDescription>
        </Alert>
      )}
      <Counts
        items={[
          [t("desktop.ledger.import.count.rows"), total((r) => r.rows)],
          [t("desktop.ledger.import.count.new"), total((r) => r.imported)],
          [t("desktop.ledger.import.count.skipped"), total((r) => r.skipped)],
          [
            t("desktop.ledger.import.count.duplicates"),
            total((r) => r.likely_duplicates),
          ],
          [
            t("desktop.ledger.import.count.refused"),
            previews.filter((preview) => preview.kind !== "read").length,
          ],
        ].map(([label, value]) => [label as string, value as number])}
      />
      <ul
        aria-label={t("desktop.ledger.import.files")}
        className="ledger-import-preview grid gap-1"
      >
        {previews.map((preview) => {
          if (preview.kind === "refused")
            return (
              <FileRow
                key={preview.file.token}
                name={preview.file.name}
                refused
              >
                <span className="text-sm">
                  {importRefusal(t, preview.reason)}
                </span>
              </FileRow>
            );
          if (preview.kind === "failed")
            return (
              <FileRow
                key={preview.file.token}
                name={preview.file.name}
                refused
              >
                <span className="text-sm">
                  {t("desktop.ledger.import.preview_failed")}{" "}
                  <code className="font-mono text-xs">{preview.code}</code>
                </span>
              </FileRow>
            );
          const result = shown(preview);
          const fact = facts.get(preview.file.token)!;
          const select = `${ids}-${preview.file.token}`;
          return (
            <FileRow key={preview.file.token} name={preview.file.name}>
              <span className="text-sm text-muted-foreground tabular-nums">
                {reading.has(preview.file.token)
                  ? t("desktop.ledger.import.reading_start")
                  : t("desktop.ledger.import.file_counts", {
                      rows: count(result.rows),
                      fresh: count(result.imported),
                      skipped: count(result.skipped),
                    })}
              </span>
              <div className="flex flex-wrap items-center gap-2 text-sm">
                <label htmlFor={select} className="text-muted-foreground">
                  {t("desktop.ledger.import.account")}
                </label>
                {fact.kind === "choose" || fact.kind === "detected" ? (
                  <NativeSelect
                    id={select}
                    controlSize="sm"
                    required
                    aria-describedby={
                      fact.kind === "detected" ? `${select}-hint` : undefined
                    }
                    aria-invalid={
                      (fact.kind === "choose" &&
                        choices[preview.file.token] === undefined &&
                        result.imported > 0) ||
                      undefined
                    }
                    // A detected account is the choice already made, and
                    // stays changeable.
                    value={
                      choices[preview.file.token] ??
                      (fact.kind === "detected" ? fact.account : "")
                    }
                    onChange={(event) => onChoose(preview, event.target.value)}
                  >
                    <option value="" disabled>
                      {t("desktop.ledger.import.account_choose")}
                    </option>
                    {accounts
                      .filter(
                        (account) => !preview.mismatched.includes(account.id),
                      )
                      .map((account) => (
                        <option key={account.id} value={account.id}>
                          {accountName(account.id)}
                        </option>
                      ))}
                    <option value={NO_ACCOUNT}>
                      {t("desktop.ledger.import.no_account")}
                    </option>
                  </NativeSelect>
                ) : (
                  <span id={select} className="font-medium">
                    {t("desktop.ledger.import.no_account")}
                    <span className="ml-2 text-xs font-normal text-muted-foreground">
                      {t(`desktop.ledger.import.account_${fact.kind}`)}
                    </span>
                  </span>
                )}
                {fact.kind === "detected" && (
                  <span
                    id={`${select}-hint`}
                    className="text-xs text-muted-foreground"
                  >
                    {t("desktop.ledger.import.account_detected")}
                  </span>
                )}
              </div>
              {result.likely_duplicates > 0 && (
                <DuplicatesChip
                  t={t}
                  count={result.likely_duplicates}
                  shown={count(result.likely_duplicates)}
                />
              )}
              {result.diagnostics.map((diagnostic, at) => (
                <span key={at} className="text-sm text-muted-foreground">
                  {diagnosticText(t, diagnostic.message)}
                </span>
              ))}
            </FileRow>
          );
        })}
      </ul>
      {progressText && (
        <p role="status" className="flex items-center gap-2 text-sm">
          <Spinner />
          {progressText}
        </p>
      )}
      <details className="text-xs text-muted-foreground">
        <summary className="cursor-pointer">
          {t("desktop.ledger.import.technical")}
        </summary>
        <ul className="mt-1 grid gap-0.5 font-mono">
          {read.map((preview) => (
            <li key={preview.file.token} className="[overflow-wrap:anywhere]">
              {preview.file.name} · sha256 {preview.digest ?? "-"}
            </li>
          ))}
        </ul>
      </details>
    </>
  );
}

function PlainPreview({
  t,
  locale,
  kind,
  files,
  bookKind,
  country,
  direction,
}: {
  t: Translate;
  locale: string;
  kind: ImportKind;
  files: PickedFile[];
  bookKind: InvoiceKind | null;
  country: string;
  direction: InvoiceKind | null;
}) {
  return (
    <>
      <ul
        aria-label={t("desktop.ledger.import.files")}
        className="ledger-import-preview grid gap-1"
      >
        {files.map((file) => (
          <FileRow key={file.token} name={file.name}>
            {file.bytes !== null && (
              <span className="text-xs text-muted-foreground">
                {sizeText(locale, file.bytes)}
              </span>
            )}
          </FileRow>
        ))}
      </ul>
      {kind === "book" ? (
        <Alert tone="warning" icon={<Icon name="alert" />}>
          <AlertTitle>{t("desktop.ledger.import.book_no_preview")}</AlertTitle>
          <AlertDescription>
            {t("desktop.ledger.import.book_no_preview_note", {
              kind: t(`desktop.ledger.import.kind_${bookKind}`),
              country: country || t("desktop.ledger.import.country_none"),
            })}
          </AlertDescription>
        </Alert>
      ) : (
        <p className="text-sm text-muted-foreground">
          {t("desktop.ledger.import.documents_note", {
            kind: t(`desktop.ledger.import.kind_${direction}`),
          })}
        </p>
      )}
    </>
  );
}

function ResultStep({
  t,
  locale,
  count,
  port,
  outcome,
  duplicates,
  progressText,
  showFailed,
}: {
  t: Translate;
  locale: string;
  count(value: number): string;
  port: LedgerPort;
  outcome: Outcome;
  duplicates: LedgerTransaction[];
  progressText: string | null;
  showFailed: boolean;
}) {
  const unknown = (names: string[]) => (
    <Alert tone="danger" role="alert" icon={<Icon name="unknown" />}>
      <AlertTitle>{t("desktop.ledger.import.unknown")}</AlertTitle>
      <AlertDescription>
        {t("desktop.ledger.import.unknown_note", {
          names: new Intl.ListFormat(locale).format(names),
        })}
      </AlertDescription>
    </Alert>
  );
  if (outcome.kind === "bank") {
    const imported = outcome.applied.filter(
      (item): item is Extract<BankApplied, { kind: "imported" }> =>
        item.kind === "imported",
    );
    const sum = (pick: (result: LedgerImportResult) => number) =>
      imported.reduce((total, item) => total + pick(item.result), 0);
    const flagged = sum((result) => result.likely_duplicates);
    const unknownFiles = outcome.applied.filter(
      (item) => item.kind === "unknown",
    );
    return (
      <>
        {imported.length > 0 && (
          <Alert tone="success" icon={<Icon name="check" />}>
            <AlertTitle>
              {t("desktop.ledger.import.imported", {
                count: sum((result) => result.imported),
              })}
            </AlertTitle>
            <AlertDescription>
              {t("desktop.ledger.import.imported_note", {
                skipped: sum((result) => result.skipped),
                flagged,
              })}
            </AlertDescription>
          </Alert>
        )}
        {unknownFiles.length > 0 &&
          unknown(unknownFiles.map((item) => item.file.name))}
        {showFailed && (
          <p role="alert" className="text-sm">
            {t("desktop.ledger.import.show_failed")}
          </p>
        )}
        <ul
          aria-label={t("desktop.ledger.import.files")}
          className="ledger-import-result grid gap-1"
        >
          {outcome.applied.map((item) => (
            <FileRow
              key={item.file.token}
              name={item.file.name}
              refused={item.kind === "refused" || item.kind === "changed"}
              icon={
                item.kind === "unknown"
                  ? "unknown"
                  : item.kind === "not_sent"
                    ? "pending"
                    : item.kind === "imported"
                      ? "check"
                      : undefined
              }
            >
              <span className="text-sm">
                {item.kind === "imported"
                  ? t("desktop.ledger.import.file_imported", {
                      fresh: count(item.result.imported),
                      skipped: count(item.result.skipped),
                    })
                  : item.kind === "changed"
                    ? importRefusal(t, "source_changed")
                    : item.kind === "refused"
                      ? importRefusal(t, item.reason)
                      : item.kind === "unknown"
                        ? t("desktop.ledger.import.file_unknown")
                        : t("desktop.ledger.import.file_not_sent")}
              </span>
            </FileRow>
          ))}
        </ul>
        {flagged > 0 && (
          <section
            aria-label={t("desktop.ledger.import.duplicates")}
            className="grid gap-1"
          >
            <h4 className="text-sm font-medium">
              {t("desktop.ledger.import.duplicates")}
            </h4>
            <ul className="ledger-import-duplicates grid gap-1">
              {duplicates.map((movement) => (
                <li
                  key={movement.transaction_id}
                  className="flex flex-wrap items-center gap-2 text-sm"
                >
                  <Icon name="alert" size="xs" className="text-warning" />
                  <span className="tabular-nums">
                    {dayText(locale, movement.date)} ·{" "}
                    {amountText(locale, movement.amount, movement.currency)}
                  </span>
                  <span className="min-w-0 [overflow-wrap:anywhere]">
                    {movement.description}
                  </span>
                  <DuplicateCompare
                    port={port}
                    locale={locale}
                    imported={movement}
                  />
                </li>
              ))}
            </ul>
            {flagged > duplicates.length && duplicates.length > 0 && (
              <p className="text-xs text-muted-foreground">
                {t("desktop.ledger.import.duplicates_more", {
                  count: flagged - duplicates.length,
                })}
              </p>
            )}
          </section>
        )}
        {progressText && (
          <p role="status" className="text-sm">
            {progressText}
          </p>
        )}
      </>
    );
  }
  if (outcome.kind === "book") {
    const { answer } = outcome;
    if (answer.kind === "failed" && answer.code === "unknown")
      return unknown([outcome.file.name]);
    if (answer.kind !== "settled")
      return (
        <Alert tone="danger" role="alert" icon={<Icon name="refused" />}>
          <AlertTitle>{t("desktop.ledger.import.book_refused")}</AlertTitle>
          <AlertDescription>
            <code className="font-mono text-xs">
              {answer.reason ?? (answer.kind === "failed" ? answer.code : "")}
            </code>
          </AlertDescription>
        </Alert>
      );
    const result = answer.result;
    return (
      <>
        <Alert tone="success" icon={<Icon name="check" />}>
          <AlertTitle>
            {t("desktop.ledger.import.book_created", { count: result.created })}
          </AlertTitle>
          <AlertDescription>
            {t("desktop.ledger.import.book_note", {
              rows: count(result.rows),
              skipped: count(result.skipped_duplicate),
              refused: count(result.refused.length),
            })}
          </AlertDescription>
        </Alert>
        {result.refused.length > 0 && (
          <table className="ledger-import-refused w-full text-sm">
            <caption className="text-left font-medium">
              {t("desktop.ledger.import.refused_rows")}
            </caption>
            <thead>
              <tr className="text-left text-muted-foreground">
                <th scope="col" className="py-1 pr-3 font-normal">
                  {t("desktop.ledger.import.row")}
                </th>
                <th scope="col" className="py-1 pr-3 font-normal">
                  {t("desktop.ledger.import.field")}
                </th>
                <th scope="col" className="py-1 font-normal">
                  {t("desktop.ledger.import.reason")}
                </th>
              </tr>
            </thead>
            <tbody>
              {result.refused.map((row) => (
                <tr
                  key={`${row.row_number}:${row.field}`}
                  className="border-t border-border align-top"
                >
                  <td className="py-1 pr-3 tabular-nums">
                    {count(row.row_number)}
                  </td>
                  <td className="py-1 pr-3 font-mono text-xs">{row.field}</td>
                  <td className="py-1 [overflow-wrap:anywhere]">
                    {row.reason}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {result.unmapped_column_headers.length > 0 && (
          <p className="text-sm text-muted-foreground">
            {t("desktop.ledger.import.unmapped", {
              columns: new Intl.ListFormat(locale).format(
                result.unmapped_column_headers,
              ),
            })}
          </p>
        )}
        <details className="text-xs text-muted-foreground">
          <summary className="cursor-pointer">
            {t("desktop.ledger.import.technical")}
          </summary>
          <p className="mt-1 font-mono [overflow-wrap:anywhere]">
            {outcome.file.name} · sha256 {result.source_sha256}
          </p>
        </details>
      </>
    );
  }
  const { applied } = outcome;
  const by = (status: string) =>
    applied.items.filter((item) => item.status === status).length;
  const refused = applied.items.filter((item) => item.status === "refused");
  return (
    <>
      {applied.items.length > 0 && (
        <Alert tone="success" icon={<Icon name="check" />}>
          <AlertTitle>
            {t("desktop.ledger.import.documents_added", {
              count: by("ingested") + by("pending_review"),
            })}
          </AlertTitle>
          <AlertDescription>
            {t("desktop.ledger.import.documents_result", {
              waiting: count(by("pending_review")),
              held: count(by("no_op")),
              paused: count(by("paused")),
            })}
          </AlertDescription>
        </Alert>
      )}
      {applied.stopped &&
        (applied.stopped.code === "unknown" ? (
          unknown(applied.stopped.files.map((file) => file.name))
        ) : (
          <Alert tone="danger" role="alert" icon={<Icon name="refused" />}>
            <AlertTitle>
              {t("desktop.ledger.import.documents_refused")}
            </AlertTitle>
            <AlertDescription>
              <code className="font-mono text-xs">{applied.stopped.code}</code>
            </AlertDescription>
          </Alert>
        ))}
      {applied.paused && (
        <Alert
          tone="warning"
          icon={<Icon name="pause" />}
          className="ledger-batch-paused"
        >
          <AlertDescription>
            {applied.paused.action !== null
              ? t("desktop.ledger.documents.paused_local_ai")
              : t("desktop.ledger.documents.paused_unavailable")}
            <SetupOffer action={applied.paused.action} className="mt-1" />
          </AlertDescription>
        </Alert>
      )}
      {(refused.length > 0 ||
        applied.unresolved.length > 0 ||
        applied.notSent.length > 0) && (
        <ul
          aria-label={t("desktop.ledger.import.files")}
          className="ledger-import-result grid gap-1"
        >
          {refused.map((item) => (
            <FileRow key={item.identity} name={item.source_name} refused>
              <span className="text-sm">
                {t("desktop.ledger.import.refusal.other", {
                  code: item.refusal_code ?? "refused",
                })}
              </span>
            </FileRow>
          ))}
          {applied.unresolved.map((item) => (
            <FileRow
              key={`${item.source_name}:${item.refusal_code}`}
              name={item.source_name}
              refused
            >
              <span className="text-sm">
                {t("desktop.ledger.import.refusal.other", {
                  code: item.refusal_code,
                })}
              </span>
            </FileRow>
          ))}
          {applied.notSent.map((file) => (
            <FileRow key={file.token} name={file.name} icon="pending">
              <span className="text-sm">
                {t("desktop.ledger.import.file_not_sent")}
              </span>
            </FileRow>
          ))}
        </ul>
      )}
    </>
  );
}
