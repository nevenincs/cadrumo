import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty";
import {
  Field,
  FieldDescription,
  FieldError,
  FieldLabel,
} from "@/components/ui/field";
import { Icon, type IconName } from "@/components/ui/icon";
import { IconButton } from "@/components/ui/icon-button";
import { NativeSelect } from "@/components/ui/native-select";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import type {
  LedgerPort,
  LedgerRequest,
  LedgerResult,
} from "../../../shell/ledger";
import type {
  InventoryBook,
  InventoryBookRow,
  InventoryInspectResult,
  InventoryListResult,
  InventoryMovement,
  InventoryRefusal,
  InventoryValuationResult,
} from "../../../shell/ledgerSetup";
import { useStrings, type Translate } from "../../../shell/strings";
import { amountText, dateText } from "../movements/movementWords";
import {
  CallLine,
  ChoiceField,
  FormGrid,
  Panel,
  readLanding,
  rankDecimal,
  Reading,
  SetupTable,
  TextField,
  useSetupDraft,
  useSetupWrite,
  type Column,
} from "../setup/SetupParts";
import type { SetupProps } from "../setup/setupProps";
import { setupCall, type SetupCall } from "../setup/setupModel";
import { grammarText, tokenText } from "../setup/setupWords";
import { useWritePause, WriteHold } from "../WritePause";
import {
  blankExtra,
  blankMovement,
  BOOK_FIELDS,
  bookListed,
  bookName,
  bookRequest,
  bookTouched,
  changeLanded,
  CORRECT_FIELDS,
  correctRequest,
  COST_FIELDS,
  COST_KIND_KEYS,
  COST_KINDS,
  CORRECTION_REASON_KEYS,
  CORRECTION_REASONS,
  DESCRIBE_FIELDS,
  describeRequest,
  EMPTY_BOOK,
  EMPTY_CORRECTION,
  EXTRA_FIELDS,
  fingerprintOf,
  HISTORY_KIND_KEYS,
  historyRows,
  KINDS,
  METHODS,
  MOVEMENT_FIELDS,
  movementCorrectionRequest,
  movementCounted,
  movementRequest,
  movementTouched,
  PRICE_FIELDS,
  PROOF_FILE_LIMIT,
  PROOF_KIND_KEYS,
  PROOF_KINDS,
  PROOF_SLOTS,
  REASON_FIELD,
  restoreRequest,
  RETIREMENT_REASON_KEYS,
  RETIREMENT_REASONS,
  retireRequest,
  reverseRequest,
  TOTAL_FIELDS,
  type BookDraft,
  type Built,
  type CorrectDraft,
  type DescribeDraft,
  type HistoryFact,
  type MovementDraft,
  type Problems,
  type ProofDraft,
  type ProofSlot,
  type StockField,
} from "./stockModel";
import { YearStepper } from "./YearStepper";

const NO_BOOKS: readonly InventoryBookRow[] = [];

/** A reference the window mints for something it sends and never shows. */
const mint = () => crypto.randomUUID();

const FILL_IN = "desktop.ledger.assets.write.fill_in";

/** The book a task acts on. */
type BookKey = { actividad_id: string; year: number };
const keyOf = (book: BookKey) => `${book.actividad_id}|${book.year}`;

// ---- Reading the books -------------------------------------------------------------

/** Reads the stock books while the pane shows, again after a `reload` or the
 * page's re-read, and drops what it read with the profile. The last answer
 * stays while the next is read. */
function useBookList(port: LedgerPort, reader: string | null, round: number) {
  const [list, setList] = useState<SetupCall<InventoryListResult> | null>(null);
  const { round: reread } = useWritePause();
  useEffect(() => {
    setList(null);
  }, [port, reader]);
  useEffect(() => {
    if (reader === null) return;
    let active = true;
    void (async () => {
      const answer = await setupCall(port, "ledger.inventory.list", {}, false);
      if (active) setList(answer);
    })();
    return () => {
      active = false;
    };
  }, [port, reader, round, reread]);
  return list;
}

/** Reads the chosen book with its movements and history, again after a
 * reload; what it read is the chosen book's alone. */
function useBookDetail(
  port: LedgerPort,
  reader: string | null,
  book: BookKey | null,
  round: number,
) {
  const [detail, setDetail] = useState<{
    key: string;
    call: SetupCall<InventoryInspectResult>;
  } | null>(null);
  const { round: reread } = useWritePause();
  const name = book?.actividad_id ?? null;
  const year = book?.year ?? null;
  const key =
    name === null || year === null ? null : keyOf({ actividad_id: name, year });
  useEffect(() => {
    setDetail(null);
  }, [port, reader]);
  useEffect(() => {
    if (reader === null || name === null || year === null || key === null)
      return;
    let active = true;
    void (async () => {
      const call = await setupCall(
        port,
        "ledger.inventory.inspect",
        { actividad_id: name, year },
        false,
      );
      if (active) setDetail({ key, call });
    })();
    return () => {
      active = false;
    };
  }, [port, reader, name, year, key, round, reread]);
  return detail && detail.key === key ? detail.call : null;
}

/** The refusal a call carries, wherever the call put it. */
function refusalOf(call: SetupCall<unknown> | null): InventoryRefusal | null {
  if (call?.kind === "refused")
    return (
      (call.detail as { refusal?: InventoryRefusal | null } | null)?.refusal ??
      null
    );
  if (call?.kind === "done")
    return (
      (call.result as { refusal?: InventoryRefusal | null } | null)?.refusal ??
      null
    );
  return null;
}

/** Words for a refused call: the stock book's own reason where the chrome has
 * one, else a plain refusal. Never the reason's token, a code or an
 * identifier. */
function refusalWords(
  t: Translate,
  call: SetupCall<unknown> | null,
  book: { name: string; year: number },
) {
  return (): string | null => {
    const found = refusalOf(call);
    if (call?.kind !== "refused" && found === null) return null;
    if (found === null) return t("desktop.ledger.stock.refused");
    const stated = Object.fromEntries(
      (found.reason_facts ?? []).map((fact) => [fact.key, fact.value]),
    );
    const said = t(`desktop.ledger.inventory.refusal.${found.reason}`, {
      ...stated,
      name: book.name,
      year: found.year ?? book.year,
    });
    return said.startsWith("desktop.") || /\{\w+\}/.test(said)
      ? t("desktop.ledger.stock.refused")
      : said;
  };
}

// ---- Parts shared by the forms -------------------------------------------------------

/** A status as a glyph and a count; the words sit in its tooltip and its
 * accessible name. */
function Pill({
  icon,
  count,
  label,
}: {
  icon: IconName;
  count: number;
  label: string;
}) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span
          role="img"
          aria-label={label}
          className="ledger-stock-pill inline-flex items-center gap-1 rounded-full bg-secondary px-2 py-0.5 text-xs font-medium tabular-nums text-secondary-foreground"
        >
          <Icon name={icon} size="xs" />
          <span aria-hidden="true">{count}</span>
        </span>
      </TooltipTrigger>
      <TooltipContent>{label}</TooltipContent>
    </Tooltip>
  );
}

/** The actions on one row. Each is an icon button; another action is one more
 * child. */
function RowActions({ children }: { children: ReactNode }) {
  return (
    <span className="ledger-stock-actions flex justify-end gap-0.5">
      {children}
    </span>
  );
}

type Choices = Readonly<
  Record<string, readonly { value: string; label: string }[]>
>;

/** The fields of a form, each drawn by its control. A refused value shows its
 * reason; one still to give shows so once the person has tried to send. */
function StockFields({
  fields,
  valueOf,
  onValue,
  choices,
  problems,
  missing,
  tried,
  at = (field) => field.key,
  autoFocus = false,
}: {
  fields: readonly StockField[];
  valueOf(field: StockField): string;
  onValue(field: StockField, value: string): void;
  choices: Choices;
  problems: Problems;
  missing: ReadonlySet<string>;
  tried: boolean;
  /** Where a field's problem is kept. */
  at?: (field: StockField) => string;
  autoFocus?: boolean;
}) {
  const t = useStrings();
  return (
    <FormGrid>
      {fields.map((field, index) => {
        const key = at(field);
        const problem = problems[key];
        const fillIn = tried && missing.has(key);
        const error = problem
          ? grammarText(t, problem)
          : fillIn
            ? t(FILL_IN)
            : null;
        return (
          <div key={field.key} data-field={field.key} className="contents">
            {field.control === "choice" ? (
              <ChoiceField
                label={t(field.label)}
                value={valueOf(field)}
                onValue={(value) => onValue(field, value)}
                placeholder={
                  field.required ? t("desktop.ledger.form.choose") : undefined
                }
                hint={error ?? (field.hint ? t(field.hint) : undefined)}
                options={choices[field.key] ?? []}
              />
            ) : (
              <TextField
                label={t(field.label)}
                name={field.key}
                value={valueOf(field)}
                onValue={(value) => onValue(field, value)}
                hint={field.hint ? t(field.hint) : undefined}
                error={error}
                required={field.required}
                inputMode={field.numeric ? "decimal" : "text"}
                maxLength={
                  field.control === "text"
                    ? field.key === "description"
                      ? 1024
                      : 120
                    : 40
                }
                autoFocus={autoFocus && index === 0}
              />
            )}
          </div>
        );
      })}
    </FormGrid>
  );
}

/** The reasons a person can give for a correction or a retirement, in the
 * words the backend's catalogue has for each. */
function reasonChoices(
  t: Translate,
  tokens: readonly string[],
  keys: Readonly<Record<string, string>>,
) {
  return {
    reason: tokens.map((value) => ({
      value,
      label: t(keys[value] ?? "desktop.ledger.stock.refused"),
    })),
  };
}

/** A file a purchase rests on. The window keeps a mark of the file's bytes
 * and not the file; a reference it minted names the proof, and neither is
 * drawn. */
function ProofPicker({
  label,
  hint,
  kinds,
  proof,
  fileName,
  onProof,
  fillIn,
}: {
  label: string;
  hint?: string;
  kinds: readonly string[];
  proof: ProofDraft;
  fileName: string | undefined;
  onProof(
    reference: string,
    change: (current: ProofDraft) => ProofDraft,
    fileName?: string,
  ): void;
  fillIn: boolean;
}) {
  const t = useStrings();
  const picker = useRef<HTMLInputElement>(null);
  const [failed, setFailed] = useState<string | null>(null);
  const read = async (file: File | undefined) => {
    if (!file) return;
    if (file.size > PROOF_FILE_LIMIT) {
      setFailed(t("desktop.ledger.stock.proof.file_too_large"));
      return;
    }
    try {
      const mark = await fingerprintOf(await file.arrayBuffer());
      onProof(
        proof.reference,
        (current) => ({ ...current, digest: mark }),
        file.name,
      );
      setFailed(null);
    } catch {
      setFailed(t("desktop.ledger.stock.proof.file_unread"));
    }
  };
  const shown = failed ?? (fillIn ? t(FILL_IN) : null);
  const choose = t(
    proof.digest === ""
      ? "desktop.ledger.stock.proof.choose_file"
      : "desktop.ledger.stock.proof.change_file",
  );
  return (
    <Field data-invalid={shown ? true : undefined}>
      <FieldLabel>{label}</FieldLabel>
      <div className="flex flex-wrap items-center gap-2">
        {kinds.length > 1 && (
          <NativeSelect
            controlSize="sm"
            aria-label={t("desktop.ledger.stock.proof.kind")}
            value={proof.kind}
            onChange={(event) =>
              onProof(proof.reference, (current) => ({
                ...current,
                kind: event.target.value,
              }))
            }
          >
            <option value="" disabled>
              {t("desktop.ledger.form.choose")}
            </option>
            {kinds.map((kind) => (
              <option key={kind} value={kind}>
                {t(PROOF_KIND_KEYS[kind as keyof typeof PROOF_KIND_KEYS])}
              </option>
            ))}
          </NativeSelect>
        )}
        <Button
          type="button"
          size="sm"
          variant="outline"
          aria-label={`${label}: ${choose}`}
          onClick={() => picker.current?.click()}
        >
          <Icon name="attach" size="sm" />
          {choose}
        </Button>
        {proof.digest !== "" && fileName && (
          <span className="flex items-center gap-1 text-sm text-muted-foreground">
            <Icon name="check" size="sm" />
            {fileName}
          </span>
        )}
        <input
          ref={picker}
          type="file"
          hidden
          tabIndex={-1}
          aria-hidden="true"
          onChange={(event) => {
            const input = event.currentTarget;
            void read(input.files?.[0]).finally(() => {
              input.value = "";
            });
          }}
        />
      </div>
      {hint && <FieldDescription>{hint}</FieldDescription>}
      <FieldError>{shown}</FieldError>
    </Field>
  );
}

function FormButtons({
  busy,
  ready,
  submit,
  onClose,
}: {
  busy: boolean;
  ready: boolean;
  submit: string;
  onClose(): void;
}) {
  const t = useStrings();
  return (
    <div className="flex flex-wrap gap-2">
      <Button
        type="button"
        size="sm"
        variant="ghost"
        aria-disabled={busy || undefined}
        onClick={() => {
          if (!busy) onClose();
        }}
      >
        {t("desktop.ledger.form.cancel")}
      </Button>
      <WriteHold>
        <Button
          type="submit"
          size="sm"
          className="ledger-stock-submit"
          aria-disabled={!ready || busy || undefined}
        >
          {busy ? t("desktop.ledger.form.saving") : submit}
        </Button>
      </WriteHold>
    </div>
  );
}

/** A group of fields under a heading, inside a form. */
function Section({
  heading,
  children,
  actions,
}: {
  heading: string;
  children: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <section className="flex flex-col gap-3">
      <div className="flex items-center gap-2">
        <h4 className="font-medium">{heading}</h4>
        <span className="flex-1" />
        {actions}
      </div>
      {children}
    </section>
  );
}

// ---- A new book --------------------------------------------------------------------

function BookForm({
  port,
  year,
  onClose,
  onWritten,
}: {
  port: LedgerPort;
  year: number;
  onClose(): void;
  onWritten(): void;
}) {
  const t = useStrings();
  const write = useSetupWrite(t("desktop.ledger.stock.title"));
  const [draft, setDraft] = useState<BookDraft>(EMPTY_BOOK);
  const [tried, setTried] = useState(false);
  useSetupDraft(bookTouched(draft));
  const built = bookRequest(year, draft);
  const choices = {
    method: METHODS.map((value) => ({
      value,
      label: tokenText(t, "inventory.method", value),
    })),
  };

  const send = async () => {
    if (write.busy) return;
    const request = built.request;
    if (request === null) {
      setTried(true);
      return;
    }
    const done = await write.run(
      () => setupCall(port, "ledger.inventory.create", request, true),
      readLanding(port, "ledger.inventory.list", {}, (listed) =>
        bookListed(listed.rows, request.actividad_id, year),
      ),
    );
    if (done.kind === "done" && refusalOf(done) === null) onWritten();
  };

  return (
    <Panel
      title={t("desktop.ledger.stock.form.book", { year })}
      className="ledger-stock-form ledger-stock-form-book"
    >
      <form
        noValidate
        className="flex flex-col gap-3"
        onSubmit={(event) => {
          event.preventDefault();
          void send();
        }}
      >
        <StockFields
          fields={BOOK_FIELDS}
          valueOf={(field) => draft[field.key as keyof BookDraft]}
          onValue={(field, value) =>
            setDraft((current) => ({ ...current, [field.key]: value }))
          }
          choices={choices}
          problems={built.problems}
          missing={built.missing}
          tried={tried}
          autoFocus
        />
        <FormButtons
          busy={write.busy}
          ready={built.request !== null}
          submit={t("desktop.ledger.stock.submit.book")}
          onClose={onClose}
        />
        <CallLine
          call={write.last}
          refusal={refusalWords(t, write.last, {
            name: t("desktop.ledger.stock.title"),
            year,
          })}
        />
      </form>
    </Panel>
  );
}

// ---- Changing a book -----------------------------------------------------------------

type ChangeId =
  | "ledger.inventory.describe"
  | "ledger.inventory.correct"
  | "ledger.inventory.movement.correct"
  | "ledger.inventory.movement.reverse"
  | "ledger.inventory.retire"
  | "ledger.inventory.restore";

/**
 * The form of a change to a book. The change carries the reference its form
 * minted when it opened, so a change sent again is the same change. A write
 * not seen to settle holds the page's writes and is judged on the history of
 * the book read again, never sent a second time.
 */
function ChangeForm<D extends ChangeId>({
  port,
  definition,
  book,
  name,
  correction,
  request,
  touched,
  title,
  submit,
  className,
  onTry,
  onClose,
  onWritten,
  children,
}: {
  port: LedgerPort;
  definition: D;
  book: BookKey;
  name: string;
  correction: string;
  request: LedgerRequest<D> | null;
  touched: boolean;
  title: string;
  submit: string;
  className: string;
  onTry(): void;
  onClose(): void;
  onWritten(): void;
  children: ReactNode;
}) {
  const t = useStrings();
  const write = useSetupWrite(title);
  useSetupDraft(touched);
  const send = async () => {
    if (write.busy) return;
    if (request === null) {
      onTry();
      return;
    }
    const done = await write.run(
      () =>
        setupCall(port, definition, request, true) as Promise<
          SetupCall<LedgerResult<D>>
        >,
      readLanding(
        port,
        "ledger.inventory.inspect",
        { actividad_id: book.actividad_id, year: book.year },
        (read) => changeLanded(read.ledger, correction),
      ),
    );
    if (done.kind === "done" && refusalOf(done) === null) onWritten();
  };
  return (
    <Panel title={title} className={`ledger-stock-form ${className}`}>
      <form
        noValidate
        className="flex flex-col gap-3"
        onSubmit={(event) => {
          event.preventDefault();
          void send();
        }}
      >
        {children}
        <FormButtons
          busy={write.busy}
          ready={request !== null}
          submit={submit}
          onClose={onClose}
        />
        <CallLine
          call={write.last}
          refusal={refusalWords(t, write.last, { name, year: book.year })}
        />
      </form>
    </Panel>
  );
}

function DescribeForm({
  port,
  book,
  ledger,
  onClose,
  onWritten,
}: {
  port: LedgerPort;
  book: InventoryBookRow;
  ledger: InventoryBook;
  onClose(): void;
  onWritten(): void;
}) {
  const t = useStrings();
  const start: DescribeDraft = {
    label: ledger.descriptor?.label ?? bookName(book),
    description: ledger.descriptor?.description ?? "",
  };
  const [draft, setDraft] = useState<DescribeDraft>(start);
  const [correction] = useState(mint);
  const [tried, setTried] = useState(false);
  const built = describeRequest(book, correction, draft);
  return (
    <ChangeForm
      port={port}
      definition="ledger.inventory.describe"
      book={book}
      name={bookName(book)}
      correction={correction}
      request={built.request}
      touched={
        draft.label !== start.label || draft.description !== start.description
      }
      title={t("desktop.ledger.stock.form.describe", {
        name: bookName(book),
        year: book.year,
      })}
      submit={t("desktop.ledger.stock.submit.describe")}
      className="ledger-stock-form-describe"
      onTry={() => setTried(true)}
      onClose={onClose}
      onWritten={onWritten}
    >
      <StockFields
        fields={DESCRIBE_FIELDS}
        valueOf={(field) => draft[field.key as keyof DescribeDraft]}
        onValue={(field, value) =>
          setDraft((current) => ({ ...current, [field.key]: value }))
        }
        choices={{}}
        problems={built.problems}
        missing={built.missing}
        tried={tried}
        autoFocus
      />
    </ChangeForm>
  );
}

function CorrectForm({
  port,
  book,
  onClose,
  onWritten,
}: {
  port: LedgerPort;
  book: InventoryBookRow;
  onClose(): void;
  onWritten(): void;
}) {
  const t = useStrings();
  const [draft, setDraft] = useState<CorrectDraft>(EMPTY_CORRECTION);
  const [correction] = useState(mint);
  const [tried, setTried] = useState(false);
  const built = correctRequest(book, correction, draft);
  const choices = {
    ...reasonChoices(t, CORRECTION_REASONS, CORRECTION_REASON_KEYS),
    method: [
      { value: "", label: t("desktop.ledger.stock.field.keep") },
      ...METHODS.map((value) => ({
        value,
        label: tokenText(t, "inventory.method", value),
      })),
    ],
  };
  return (
    <ChangeForm
      port={port}
      definition="ledger.inventory.correct"
      book={book}
      name={bookName(book)}
      correction={correction}
      request={built.request}
      touched={Object.values(draft).some((text) => text.trim() !== "")}
      title={t("desktop.ledger.stock.form.correct", {
        name: bookName(book),
        year: book.year,
      })}
      submit={t("desktop.ledger.stock.submit.correct")}
      className="ledger-stock-form-correct"
      onTry={() => setTried(true)}
      onClose={onClose}
      onWritten={onWritten}
    >
      <StockFields
        fields={CORRECT_FIELDS}
        valueOf={(field) => draft[field.key as keyof CorrectDraft]}
        onValue={(field, value) =>
          setDraft((current) => ({ ...current, [field.key]: value }))
        }
        choices={choices}
        problems={built.problems}
        missing={built.missing}
        tried={tried}
        autoFocus
      />
    </ChangeForm>
  );
}

/** The movement a form acts on, in a line. */
function movementLine(
  t: Translate,
  locale: string,
  movement: InventoryMovement,
) {
  return t("desktop.ledger.stock.fact.movement", {
    date: dateText(locale, movement.movement_date, true),
    kind: tokenText(t, "inventory.kind", movement.kind),
    quantity: movement.quantity.decimal,
  });
}

function ReverseForm({
  port,
  book,
  target,
  locale,
  onClose,
  onWritten,
}: {
  port: LedgerPort;
  book: InventoryBookRow;
  target: InventoryMovement;
  locale: string;
  onClose(): void;
  onWritten(): void;
}) {
  const t = useStrings();
  const [reason, setReason] = useState("");
  const [correction] = useState(mint);
  const [tried, setTried] = useState(false);
  const built = reverseRequest(book, correction, target.movement_id, reason);
  return (
    <ChangeForm
      port={port}
      definition="ledger.inventory.movement.reverse"
      book={book}
      name={bookName(book)}
      correction={correction}
      request={built.request}
      touched={reason !== ""}
      title={t("desktop.ledger.stock.form.reverse", {
        name: bookName(book),
        year: book.year,
      })}
      submit={t("desktop.ledger.stock.submit.reverse")}
      className="ledger-stock-form-reverse"
      onTry={() => setTried(true)}
      onClose={onClose}
      onWritten={onWritten}
    >
      <p className="text-sm">{movementLine(t, locale, target)}</p>
      <p className="text-sm text-muted-foreground">
        {t("desktop.ledger.stock.reverse_note")}
      </p>
      <StockFields
        fields={[REASON_FIELD]}
        valueOf={() => reason}
        onValue={(_, value) => setReason(value)}
        choices={reasonChoices(t, CORRECTION_REASONS, CORRECTION_REASON_KEYS)}
        problems={built.problems}
        missing={built.missing}
        tried={tried}
        autoFocus
      />
    </ChangeForm>
  );
}

function RetireForm({
  port,
  book,
  onClose,
  onWritten,
}: {
  port: LedgerPort;
  book: InventoryBookRow;
  onClose(): void;
  onWritten(): void;
}) {
  const t = useStrings();
  const [reason, setReason] = useState("");
  const [correction] = useState(mint);
  const [tried, setTried] = useState(false);
  const built = retireRequest(book, correction, reason);
  return (
    <ChangeForm
      port={port}
      definition="ledger.inventory.retire"
      book={book}
      name={bookName(book)}
      correction={correction}
      request={built.request}
      touched={reason !== ""}
      title={t("desktop.ledger.stock.form.retire", {
        name: bookName(book),
        year: book.year,
      })}
      submit={t("desktop.ledger.stock.submit.retire")}
      className="ledger-stock-form-retire"
      onTry={() => setTried(true)}
      onClose={onClose}
      onWritten={onWritten}
    >
      <Alert icon={<Icon name="info" />}>
        {t("desktop.ledger.stock.retire_note")}
      </Alert>
      <StockFields
        fields={[REASON_FIELD]}
        valueOf={() => reason}
        onValue={(_, value) => setReason(value)}
        choices={reasonChoices(t, RETIREMENT_REASONS, RETIREMENT_REASON_KEYS)}
        problems={built.problems}
        missing={built.missing}
        tried={tried}
        autoFocus
      />
    </ChangeForm>
  );
}

function RestoreForm({
  port,
  book,
  onClose,
  onWritten,
}: {
  port: LedgerPort;
  book: InventoryBookRow;
  onClose(): void;
  onWritten(): void;
}) {
  const t = useStrings();
  const [correction] = useState(mint);
  return (
    <ChangeForm
      port={port}
      definition="ledger.inventory.restore"
      book={book}
      name={bookName(book)}
      correction={correction}
      request={restoreRequest(book, correction)}
      touched={false}
      title={t("desktop.ledger.stock.form.restore", {
        name: bookName(book),
        year: book.year,
      })}
      submit={t("desktop.ledger.stock.submit.restore")}
      className="ledger-stock-form-restore"
      onTry={() => undefined}
      onClose={onClose}
      onWritten={onWritten}
    >
      <p className="text-sm text-muted-foreground">
        {t("desktop.ledger.stock.restore_note")}
      </p>
    </ChangeForm>
  );
}

// ---- A movement ---------------------------------------------------------------------

/** What a movement form holds: what is typed, the extra costs, the files, and
 * the names of the files attached. */
function useMovementDraft(initial: Readonly<Record<string, string>>) {
  const [draft, setDraft] = useState<MovementDraft>(() => ({
    ...blankMovement(mint),
    values: initial,
  }));
  const [names, setNames] = useState<Readonly<Record<string, string>>>({});
  const setValue = (field: StockField, value: string) =>
    setDraft((current) => ({
      ...current,
      values: { ...current.values, [field.key]: value },
    }));
  const setExtra = (key: string, field: string, value: string) =>
    setDraft((current) => ({
      ...current,
      extras: current.extras.map((extra) =>
        extra.key === key ? { ...extra, [field]: value } : extra,
      ),
    }));
  /** Changes one proof, found by the reference minted for it. */
  const setProof = (
    reference: string,
    change: (current: ProofDraft) => ProofDraft,
    fileName?: string,
  ) => {
    const swap = (proof: ProofDraft) =>
      proof.reference === reference ? change(proof) : proof;
    setDraft((current) => ({
      ...current,
      proofs: {
        price: swap(current.proofs.price),
        cost_check: swap(current.proofs.cost_check),
        iva_check: swap(current.proofs.iva_check),
      },
      extras: current.extras.map((extra) => ({
        ...extra,
        proof: swap(extra.proof),
      })),
    }));
    if (fileName !== undefined)
      setNames((current) => ({ ...current, [reference]: fileName }));
  };
  return { draft, setDraft, names, setValue, setExtra, setProof };
}

type MovementDraftState = ReturnType<typeof useMovementDraft>;

/** The fields of a movement: its date, kind and units, then what its kind
 * states about its cost. A purchase states its price, its extra costs, its
 * totals and the files that show them. */
function MovementFields({
  state,
  built,
  tried,
}: {
  state: MovementDraftState;
  built: Built<unknown>;
  tried: boolean;
}) {
  const t = useStrings();
  const { draft, names, setValue, setExtra, setProof, setDraft } = state;
  const kind = draft.values.kind ?? "";
  const choices = {
    kind: KINDS.map((value) => ({
      value,
      label: tokenText(t, "inventory.kind", value),
    })),
  };
  const extraChoices = {
    kind: COST_KINDS.map((value) => ({
      value,
      label: t(COST_KIND_KEYS[value]),
    })),
  };
  const common = {
    problems: built.problems,
    missing: built.missing,
    tried,
  };
  const slotFill = (slot: ProofSlot) =>
    tried &&
    (built.missing.has(`${slot.key}:file`) ||
      built.missing.has(`${slot.key}:kind`));
  return (
    <>
      <StockFields
        fields={MOVEMENT_FIELDS}
        valueOf={(field) => draft.values[field.key] ?? ""}
        onValue={setValue}
        choices={choices}
        {...common}
      />
      {kind !== "" && kind !== "purchase" && (
        <StockFields
          fields={COST_FIELDS}
          valueOf={(field) => draft.values[field.key] ?? ""}
          onValue={setValue}
          choices={{}}
          {...common}
        />
      )}
      {kind === "purchase" && (
        <>
          <Section heading={t("desktop.ledger.stock.purchase.price")}>
            <StockFields
              fields={PRICE_FIELDS}
              valueOf={(field) => draft.values[field.key] ?? ""}
              onValue={setValue}
              choices={{}}
              {...common}
            />
          </Section>
          <Section
            heading={t("desktop.ledger.stock.purchase.extras")}
            actions={
              <IconButton
                label={t("desktop.ledger.stock.extra.add")}
                onClick={() =>
                  setDraft((current) => ({
                    ...current,
                    extras: [...current.extras, blankExtra(mint)],
                  }))
                }
              >
                <Icon name="plus" />
              </IconButton>
            }
          >
            {draft.extras.length === 0 && (
              <p className="text-sm text-muted-foreground">
                {t("desktop.ledger.stock.extra.none")}
              </p>
            )}
            {draft.extras.map((extra) => {
              const field = (name: string) => `extra:${extra.key}:${name}`;
              return (
                <div
                  key={extra.key}
                  className="ledger-stock-extra flex flex-col gap-3 rounded-md bg-card p-3"
                >
                  <div className="flex justify-end">
                    <IconButton
                      label={t("desktop.ledger.stock.extra.remove")}
                      onClick={() =>
                        setDraft((current) => ({
                          ...current,
                          extras: current.extras.filter(
                            (found) => found.key !== extra.key,
                          ),
                        }))
                      }
                    >
                      <Icon name="trash" />
                    </IconButton>
                  </div>
                  <StockFields
                    fields={EXTRA_FIELDS}
                    valueOf={(entry) =>
                      extra[entry.key as "kind" | "price" | "iva" | "share"]
                    }
                    onValue={(entry, value) =>
                      setExtra(extra.key, entry.key, value)
                    }
                    choices={extraChoices}
                    at={(entry) => field(entry.key)}
                    {...common}
                  />
                  <ProofPicker
                    label={t("desktop.ledger.stock.proof.extra")}
                    kinds={PROOF_KINDS}
                    proof={extra.proof}
                    fileName={names[extra.proof.reference]}
                    onProof={setProof}
                    fillIn={
                      tried &&
                      (built.missing.has(field("proof:file")) ||
                        built.missing.has(field("proof:kind")))
                    }
                  />
                </div>
              );
            })}
          </Section>
          <Section heading={t("desktop.ledger.stock.purchase.totals")}>
            <p className="text-sm text-muted-foreground">
              {t("desktop.ledger.stock.purchase.totals_hint")}
            </p>
            <StockFields
              fields={TOTAL_FIELDS}
              valueOf={(field) => draft.values[field.key] ?? ""}
              onValue={setValue}
              choices={{}}
              {...common}
            />
          </Section>
          <Section heading={t("desktop.ledger.stock.purchase.proofs")}>
            <p className="text-sm text-muted-foreground">
              {t("desktop.ledger.stock.purchase.proofs_hint")}
            </p>
            {PROOF_SLOTS.map((slot) => (
              <ProofPicker
                key={slot.key}
                label={t(slot.label)}
                hint={slot.hint ? t(slot.hint) : undefined}
                kinds={slot.kinds}
                proof={draft.proofs[slot.key]}
                fileName={names[draft.proofs[slot.key].reference]}
                onProof={setProof}
                fillIn={slotFill(slot)}
              />
            ))}
          </Section>
        </>
      )}
    </>
  );
}

function MovementForm({
  port,
  book,
  onClose,
  onWritten,
}: {
  port: LedgerPort;
  book: InventoryBookRow;
  onClose(): void;
  onWritten(): void;
}) {
  const t = useStrings();
  const write = useSetupWrite(t("desktop.ledger.stock.title"));
  // The movement's reference is minted once, when the form opens, and never
  // shown or typed. A movement sent again under it is refused.
  const [reference] = useState(mint);
  const state = useMovementDraft({});
  const [tried, setTried] = useState(false);
  useSetupDraft(movementTouched(state.draft));
  const built = movementRequest(book, reference, state.draft);

  const send = async () => {
    if (write.busy) return;
    const request = built.request;
    if (request === null) {
      setTried(true);
      return;
    }
    // A movement adds one to its book's count, so the count before the write
    // tells whether it landed.
    const before = book.movement_count;
    const done = await write.run(
      () => setupCall(port, "ledger.inventory.movement.add", request, true),
      readLanding(port, "ledger.inventory.list", {}, (listed) =>
        movementCounted(listed.rows, book, before),
      ),
    );
    if (done.kind === "done" && refusalOf(done) === null) onWritten();
  };

  return (
    <Panel
      title={t("desktop.ledger.stock.form.movement", {
        name: bookName(book),
        year: book.year,
      })}
      className="ledger-stock-form ledger-stock-form-movement"
    >
      <form
        noValidate
        className="flex flex-col gap-4"
        onSubmit={(event) => {
          event.preventDefault();
          void send();
        }}
      >
        <MovementFields state={state} built={built} tried={tried} />
        <FormButtons
          busy={write.busy}
          ready={built.request !== null}
          submit={t("desktop.ledger.stock.submit.movement")}
          onClose={onClose}
        />
        <CallLine
          call={write.last}
          refusal={refusalWords(t, write.last, {
            name: bookName(book),
            year: book.year,
          })}
        />
      </form>
    </Panel>
  );
}

/** The values a correction of a movement starts from: what the movement
 * states, so the person changes only what was wrong. A purchase's cost and
 * files are not served back, so they are stated again. */
function startOf(movement: InventoryMovement): Record<string, string> {
  return {
    date: movement.movement_date,
    kind: movement.kind,
    quantity: movement.quantity.decimal,
    ...(movement.kind !== "purchase" && movement.unit_cost
      ? { unit_cost: movement.unit_cost.decimal }
      : {}),
    ...(movement.kind !== "purchase" && movement.taxable_base
      ? { total_cost: movement.taxable_base.decimal }
      : {}),
  };
}

function MovementCorrectForm({
  port,
  book,
  target,
  onClose,
  onWritten,
}: {
  port: LedgerPort;
  book: InventoryBookRow;
  target: InventoryMovement;
  onClose(): void;
  onWritten(): void;
}) {
  const t = useStrings();
  // Both references are minted once, when the form opens, and never shown.
  const [ids] = useState(() => ({ correction: mint(), movement: mint() }));
  const [initial] = useState(() => startOf(target));
  const state = useMovementDraft(initial);
  const [reason, setReason] = useState("");
  const [tried, setTried] = useState(false);
  const built = movementCorrectionRequest(
    book,
    ids,
    target.movement_id,
    reason,
    state.draft,
  );
  const changed =
    reason !== "" ||
    movementTouched({
      ...state.draft,
      values: Object.fromEntries(
        Object.entries(state.draft.values).filter(
          ([key, text]) => initial[key] !== text,
        ),
      ),
    });
  return (
    <ChangeForm
      port={port}
      definition="ledger.inventory.movement.correct"
      book={book}
      name={bookName(book)}
      correction={ids.correction}
      request={built.request}
      touched={changed}
      title={t("desktop.ledger.stock.form.movement_correct", {
        name: bookName(book),
        year: book.year,
      })}
      submit={t("desktop.ledger.stock.submit.movement_correct")}
      className="ledger-stock-form-movement-correct"
      onTry={() => setTried(true)}
      onClose={onClose}
      onWritten={onWritten}
    >
      <p className="text-sm text-muted-foreground">
        {t("desktop.ledger.stock.movement_correct_note")}
      </p>
      <StockFields
        fields={[REASON_FIELD]}
        valueOf={() => reason}
        onValue={(_, value) => setReason(value)}
        choices={reasonChoices(t, CORRECTION_REASONS, CORRECTION_REASON_KEYS)}
        problems={built.problems}
        missing={built.missing}
        tried={tried}
        autoFocus
      />
      <MovementFields state={state} built={built} tried={tried} />
    </ChangeForm>
  );
}

// ---- What a book holds ------------------------------------------------------------------

/** A fact of the history, in words. */
function factText(t: Translate, locale: string, fact: HistoryFact): string {
  switch (fact.kind) {
    case "opening":
      return t("desktop.ledger.stock.fact.opening", {
        value: amountText(locale, fact.value),
      });
    case "method":
      return t("desktop.ledger.stock.fact.method", {
        value: tokenText(t, "inventory.method", fact.value),
      });
    case "label":
      return t("desktop.ledger.stock.fact.label", { value: fact.value });
    case "description":
      return fact.value
        ? t("desktop.ledger.stock.fact.description", { value: fact.value })
        : t("desktop.ledger.stock.fact.no_description");
    case "movement":
      return movementLine(t, locale, fact.value);
    case "removed":
      return t("desktop.ledger.stock.fact.removed");
  }
}

function FactList({
  facts: list,
  locale,
}: {
  facts: readonly HistoryFact[];
  locale: string;
}) {
  const t = useStrings();
  if (list.length === 0) return <span aria-hidden="true">—</span>;
  return (
    <>
      {list.map((fact, at) => (
        <span key={at} className="block">
          {factText(t, locale, fact)}
        </span>
      ))}
    </>
  );
}

/** The changes of a book, newest first: when, what, why, and what each
 * displaced and left in its place. */
function History({
  ledger,
  locale,
  name,
}: {
  ledger: InventoryBook;
  locale: string;
  name: string;
}) {
  const t = useStrings();
  const rows = useMemo(() => historyRows(ledger), [ledger]);
  if (rows.length === 0)
    return (
      <p className="ledger-stock-history-note text-sm text-muted-foreground">
        {t("desktop.ledger.stock.history_none")}
      </p>
    );
  return (
    <SetupTable
      label={t("desktop.ledger.stock.history_of", { name })}
      rows={rows}
      rowKey={(row) => String(row.position)}
      className="ledger-stock-history"
      columns={[
        {
          key: "when",
          label: t("desktop.ledger.stock.history.when"),
          sort: (row) => row.position,
          cell: (row) => dateText(locale, row.day, true),
        },
        {
          key: "what",
          label: t("desktop.ledger.stock.history.what"),
          cell: (row) => t(HISTORY_KIND_KEYS[row.kind]),
        },
        {
          key: "reason",
          label: t("desktop.ledger.stock.history.reason"),
          cell: (row) =>
            row.reason === null
              ? "—"
              : row.reason.family === "correction"
                ? t(CORRECTION_REASON_KEYS[row.reason.token])
                : t(RETIREMENT_REASON_KEYS[row.reason.token]),
        },
        {
          key: "before",
          label: t("desktop.ledger.stock.history.before"),
          cell: (row) => <FactList facts={row.before} locale={locale} />,
        },
        {
          key: "after",
          label: t("desktop.ledger.stock.history.after"),
          cell: (row) => <FactList facts={row.after} locale={locale} />,
        },
      ]}
    />
  );
}

// ---- The pane -------------------------------------------------------------------------

type Task =
  | { kind: "book" }
  | {
      kind: "movement" | "describe" | "correct" | "retire" | "restore";
      book: BookKey;
    }
  | {
      kind: "movement_correct" | "movement_reverse";
      book: BookKey;
      target: InventoryMovement;
    };

/**
 * Assets › Stock (existencias): the stock books for a year, one per activity,
 * the movements and history of the chosen one, a valuation preview that saves
 * nothing, and the forms to add a book or a movement and to change them. A
 * list not yet loaded, one that could not be loaded, one that was refused, an
 * account that withholds it and a year with no book are each said apart. A
 * retired book stays listed, marked with its reason; its stock cannot change
 * until it is restored.
 */
export function StockPane({
  port,
  reader,
  locale,
  years,
  fallbackYear,
}: SetupProps) {
  const t = useStrings();
  const [chosenYear, setYear] = useState<number | null>(null);
  const [chosen, setChosen] = useState<string | null>(null);
  const [task, setTask] = useState<Task | null>(null);
  const [preview, setPreview] = useState<{
    key: string;
    call: SetupCall<InventoryValuationResult>;
  } | null>(null);

  const year = chosenYear ?? fallbackYear;
  const [round, setRound] = useState(0);
  const reload = () => setRound((count) => count + 1);
  const list = useBookList(port, reader, round);
  const listed = list?.kind === "done" ? list.result.rows : NO_BOOKS;
  const offered = useMemo(
    () => [...(years ?? []), ...listed.map((row) => row.year), fallbackYear],
    [years, listed, fallbackYear],
  );
  const books = listed.filter((row) => row.year === year);
  const book = books.find((row) => row.actividad_id === chosen) ?? books[0];
  const retired = books.filter((row) => row.retired === true).length;
  const bookKey: BookKey | null = book
    ? { actividad_id: book.actividad_id, year: book.year }
    : null;
  const detail = useBookDetail(port, reader, bookKey, round);

  const choose = (row: BookKey) => setChosen(row.actividad_id);
  const open = (next: Task) => {
    if (next.kind !== "book") choose(next.book);
    setTask(next);
  };
  const written = () => {
    setPreview(null);
    setTask(null);
    reload();
  };
  const runPreview = async (row: InventoryBookRow) => {
    choose(row);
    setPreview({
      key: keyOf(row),
      call: await setupCall(
        port,
        "ledger.inventory.valuation.preview",
        { actividad_id: row.actividad_id, year: row.year },
        false,
      ),
    });
  };

  const ledger =
    detail?.kind === "done" && detail.result.outcome === "found"
      ? detail.result.ledger
      : null;

  const columns: Column<InventoryBookRow>[] = [
    {
      key: "name",
      label: t("desktop.ledger.stock.column.name"),
      sort: (row) => bookName(row),
      cell: (row) => (
        <span className="flex flex-wrap items-center gap-1.5">
          <Button
            variant="link"
            size="xs"
            className="ledger-stock-choose"
            aria-current={book?.actividad_id === row.actividad_id || undefined}
            onClick={() => choose(row)}
          >
            {bookName(row)}
          </Button>
          {row.retired === true && (
            <span className="ledger-stock-retired inline-flex items-center gap-1 text-xs text-muted-foreground">
              <Icon name="archive" size="xs" />
              {row.retirement_reason
                ? t("desktop.ledger.stock.retired_because", {
                    reason: t(RETIREMENT_REASON_KEYS[row.retirement_reason]),
                  })
                : t("desktop.ledger.stock.retired")}
            </span>
          )}
          {(row.correction_count ?? 0) > 0 && (
            <Pill
              icon="edit"
              count={row.correction_count ?? 0}
              label={t("desktop.ledger.stock.count.corrections", {
                count: row.correction_count ?? 0,
              })}
            />
          )}
        </span>
      ),
    },
    {
      key: "method",
      label: t("desktop.ledger.inventory.column.method"),
      sort: (row) => tokenText(t, "inventory.method", row.valuation_method),
      cell: (row) => tokenText(t, "inventory.method", row.valuation_method),
    },
    {
      key: "opening",
      label: t("desktop.ledger.inventory.column.opening"),
      numeric: true,
      sort: (row) => rankDecimal(row.opening_stock.decimal),
      cell: (row) => amountText(locale, row.opening_stock.decimal),
    },
    {
      key: "movements",
      label: t("desktop.ledger.inventory.column.movements"),
      numeric: true,
      sort: (row) => row.movement_count,
      cell: (row) => row.movement_count,
    },
    {
      key: "actions",
      label: t("desktop.ledger.form.actions"),
      hidden: true,
      resizable: false,
      cell: (row) => {
        // A retired book's stock cannot change; the tooltip says why.
        const stopped = row.retired === true;
        const why = stopped
          ? t("desktop.ledger.stock.retired_hint")
          : undefined;
        const key = { actividad_id: row.actividad_id, year: row.year };
        return (
          <RowActions>
            <WriteHold>
              <IconButton
                label={t("desktop.ledger.stock.action.add_movement")}
                hint={why}
                aria-disabled={stopped || undefined}
                className="ledger-stock-add-movement"
                onClick={() =>
                  !stopped && open({ kind: "movement", book: key })
                }
              >
                <Icon name="plus" />
              </IconButton>
            </WriteHold>
            <IconButton
              label={t("desktop.ledger.stock.action.preview")}
              className="ledger-stock-preview"
              onClick={() => void runPreview(row)}
            >
              <Icon name="eye" />
            </IconButton>
            <WriteHold>
              <IconButton
                label={t("desktop.ledger.stock.action.describe")}
                className="ledger-stock-describe"
                onClick={() => open({ kind: "describe", book: key })}
              >
                <Icon name="edit" />
              </IconButton>
            </WriteHold>
            <WriteHold>
              <IconButton
                label={t("desktop.ledger.stock.action.correct")}
                hint={why}
                aria-disabled={stopped || undefined}
                className="ledger-stock-correct"
                onClick={() => !stopped && open({ kind: "correct", book: key })}
              >
                <Icon name="reset" />
              </IconButton>
            </WriteHold>
            <WriteHold>
              {stopped ? (
                <IconButton
                  label={t("desktop.ledger.stock.action.restore")}
                  className="ledger-stock-restore"
                  onClick={() => open({ kind: "restore", book: key })}
                >
                  <Icon name="unarchive" />
                </IconButton>
              ) : (
                <IconButton
                  label={t("desktop.ledger.stock.action.retire")}
                  className="ledger-stock-retire"
                  onClick={() => open({ kind: "retire", book: key })}
                >
                  <Icon name="archive" />
                </IconButton>
              )}
            </WriteHold>
          </RowActions>
        );
      },
    },
  ];

  const body = () => {
    if (reader === null)
      return (
        <EmptyState
          icon="lock"
          heading={t("desktop.ledger.stock.unavailable")}
          className="ledger-stock-unavailable"
        />
      );
    if (list === null)
      return (
        <EmptyState
          busy
          heading={t("desktop.ledger.stock.loading")}
          className="ledger-stock-loading"
        />
      );
    if (list.kind === "refused")
      return (
        <Alert
          tone="danger"
          role="alert"
          icon={<Icon name="refused" />}
          className="ledger-stock-refused"
        >
          {t("desktop.ledger.stock.load_refused")}
        </Alert>
      );
    if (list.kind !== "done")
      return (
        <Alert
          tone="warning"
          role="alert"
          icon={<Icon name="alert" />}
          className="ledger-stock-failed"
        >
          <span>
            {t("desktop.ledger.stock.load_failed")}{" "}
            <Button variant="link" size="xs" onClick={reload}>
              {t("desktop.ledger.form.reread")}
            </Button>
          </span>
        </Alert>
      );
    if (books.length === 0)
      return (
        <EmptyState
          icon="book"
          heading={t("desktop.ledger.stock.empty", { year })}
          className="ledger-stock-empty"
        />
      );
    return (
      <SetupTable
        label={t("desktop.ledger.stock.books", { year })}
        rows={books}
        rowKey={(row) => row.actividad_id}
        selected={book?.actividad_id ?? null}
        columns={columns}
        className="ledger-stock-table"
      />
    );
  };

  const form = () => {
    if (task === null || reader === null) return null;
    const close = () => setTask(null);
    if (task.kind === "book")
      return (
        <BookForm
          key={`book|${year}`}
          port={port}
          year={year}
          onClose={close}
          onWritten={written}
        />
      );
    const row = listed.find(
      (found) =>
        found.actividad_id === task.book.actividad_id &&
        found.year === task.book.year,
    );
    if (!row) return null;
    const common = { port, book: row, onClose: close, onWritten: written };
    const key = `${task.kind}|${keyOf(row)}`;
    switch (task.kind) {
      case "movement":
        return <MovementForm key={key} {...common} />;
      case "describe":
        return ledger && keyOf(ledger) === keyOf(row) ? (
          <DescribeForm key={key} {...common} ledger={ledger} />
        ) : (
          <Reading label={t("desktop.ledger.stock.detail_loading")} />
        );
      case "correct":
        return <CorrectForm key={key} {...common} />;
      case "retire":
        return <RetireForm key={key} {...common} />;
      case "restore":
        return <RestoreForm key={key} {...common} />;
      case "movement_correct":
        return (
          <MovementCorrectForm
            key={`${key}|${task.target.movement_id}`}
            {...common}
            target={task.target}
          />
        );
      case "movement_reverse":
        return (
          <ReverseForm
            key={`${key}|${task.target.movement_id}`}
            {...common}
            target={task.target}
            locale={locale}
          />
        );
    }
  };

  const valued =
    preview &&
    book &&
    preview.key === keyOf(book) &&
    preview.call.kind === "done"
      ? preview.call.result.preview
      : null;

  const movementsBody = () => {
    if (!book) return null;
    if (detail === null)
      return <Reading label={t("desktop.ledger.stock.detail_loading")} />;
    if (detail.kind !== "done" || detail.result.outcome !== "found" || !ledger)
      return (
        <Alert
          tone={detail.kind === "refused" ? "danger" : "warning"}
          role="alert"
          icon={<Icon name={detail.kind === "refused" ? "refused" : "alert"} />}
          className="ledger-stock-detail-failed"
        >
          {detail.kind === "refused" ||
          (detail.kind === "done" && detail.result.outcome === "refused")
            ? t("desktop.ledger.stock.detail_refused")
            : t("desktop.ledger.stock.detail_failed")}
        </Alert>
      );
    const stopped = book.retired === true;
    const why = stopped ? t("desktop.ledger.stock.retired_hint") : undefined;
    const bookKey: BookKey = {
      actividad_id: book.actividad_id,
      year: book.year,
    };
    return (
      <>
        {ledger.period_movements.length === 0 ? (
          <p className="ledger-stock-movements-note text-sm text-muted-foreground">
            {t("desktop.ledger.stock.movements_none")}
          </p>
        ) : (
          <SetupTable<InventoryMovement>
            label={t("desktop.ledger.stock.movements_of", {
              name: bookName(book),
            })}
            rows={ledger.period_movements}
            rowKey={(movement) => movement.movement_id}
            className="ledger-stock-movements"
            columns={[
              {
                key: "date",
                label: t("desktop.ledger.inventory.column.date"),
                sort: (movement) => movement.movement_date,
                cell: (movement) =>
                  dateText(locale, movement.movement_date, true),
              },
              {
                key: "kind",
                label: t("desktop.ledger.inventory.column.kind"),
                sort: (movement) =>
                  tokenText(t, "inventory.kind", movement.kind),
                cell: (movement) =>
                  tokenText(t, "inventory.kind", movement.kind),
              },
              {
                key: "quantity",
                label: t("desktop.ledger.inventory.column.quantity"),
                numeric: true,
                sort: (movement) => rankDecimal(movement.quantity.decimal),
                cell: (movement) => movement.quantity.decimal,
              },
              {
                key: "unit",
                label: t("desktop.ledger.inventory.column.unit_cost"),
                numeric: true,
                sort: (movement) => rankDecimal(movement.unit_cost?.decimal),
                cell: (movement) => movement.unit_cost?.decimal ?? "—",
              },
              {
                key: "cost",
                label: t("desktop.ledger.stock.column.cost"),
                numeric: true,
                sort: (movement) =>
                  rankDecimal(
                    movement.acquisition_cost?.total_acquisition_cost.decimal ??
                      movement.taxable_base?.decimal,
                  ),
                cell: (movement) => {
                  const cost =
                    movement.acquisition_cost?.total_acquisition_cost.decimal ??
                    movement.taxable_base?.decimal;
                  return cost === undefined ? "—" : amountText(locale, cost);
                },
              },
              {
                key: "actions",
                label: t("desktop.ledger.form.actions"),
                hidden: true,
                resizable: false,
                cell: (movement) => (
                  <RowActions>
                    <WriteHold>
                      <IconButton
                        label={t(
                          "desktop.ledger.stock.action.movement_correct",
                        )}
                        hint={why}
                        aria-disabled={stopped || undefined}
                        className="ledger-stock-movement-correct"
                        onClick={() =>
                          !stopped &&
                          open({
                            kind: "movement_correct",
                            book: bookKey,
                            target: movement,
                          })
                        }
                      >
                        <Icon name="edit" />
                      </IconButton>
                    </WriteHold>
                    <WriteHold>
                      <IconButton
                        label={t(
                          "desktop.ledger.stock.action.movement_reverse",
                        )}
                        hint={why}
                        aria-disabled={stopped || undefined}
                        className="ledger-stock-movement-reverse"
                        onClick={() =>
                          !stopped &&
                          open({
                            kind: "movement_reverse",
                            book: bookKey,
                            target: movement,
                          })
                        }
                      >
                        <Icon name="erase" />
                      </IconButton>
                    </WriteHold>
                  </RowActions>
                ),
              },
            ]}
          />
        )}
        <h4 className="font-medium">
          {t("desktop.ledger.stock.history_of", { name: bookName(book) })}
        </h4>
        <History ledger={ledger} locale={locale} name={bookName(book)} />
      </>
    );
  };

  return (
    <div className="ledger-stock flex min-h-0 flex-1 flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <WriteHold>
          <IconButton
            label={t("desktop.ledger.stock.action.add_book")}
            className="ledger-stock-add-book"
            disabled={reader === null}
            onClick={() => open({ kind: "book" })}
          >
            <Icon name="plus" />
          </IconButton>
        </WriteHold>
        <YearStepper
          value={year}
          years={offered}
          onChange={(next) => {
            setYear(next);
            setChosen(null);
            setPreview(null);
            setTask(null);
          }}
        />
        <span className="flex-1" />
        {list?.kind === "done" && (
          <span
            role="group"
            aria-label={t("desktop.ledger.stock.summary")}
            className="flex flex-wrap items-center gap-1"
          >
            <Pill
              icon="book"
              count={books.length}
              label={t("desktop.ledger.stock.count.books", {
                count: books.length,
              })}
            />
            {retired > 0 && (
              <Pill
                icon="archive"
                count={retired}
                label={t("desktop.ledger.stock.count.retired", {
                  count: retired,
                })}
              />
            )}
          </span>
        )}
      </div>
      {form()}
      {body()}
      {valued && book && (
        <Alert icon={<Icon name="info" />} className="ledger-stock-valuation">
          <span className="font-medium tabular-nums">
            {t("desktop.ledger.inventory.valuation", {
              name: bookName(book),
              closing: amountText(locale, valued.derived_closing_value.decimal),
              cogs: amountText(locale, valued.cogs.decimal),
              method: tokenText(t, "inventory.method", valued.valuation_method),
            })}
          </span>
          <span className="text-sm">
            {t("desktop.ledger.inventory.preview_note")}
          </span>
        </Alert>
      )}
      {preview && preview.call.kind !== "done" && book && (
        <CallLine
          call={preview.call}
          refusal={refusalWords(t, preview.call, {
            name: bookName(book),
            year: book.year,
          })}
        />
      )}
      {preview?.call.kind === "done" && refusalOf(preview.call) !== null && (
        <Alert
          tone="danger"
          role="alert"
          icon={<Icon name="refused" />}
          className="ledger-stock-refused"
        >
          {refusalWords(t, preview.call, {
            name: book ? bookName(book) : "",
            year,
          })()}
        </Alert>
      )}
      {list?.kind === "done" && movementsBody()}
    </div>
  );
}
