import { useEffect, useId, useMemo, useState, type ReactNode } from "react";
import { DateEditor } from "@/components/editors/DateEditor";
import { DecimalEditor } from "@/components/editors/DecimalEditor";
import { MoneyEditor } from "@/components/editors/MoneyEditor";
import { PercentEditor } from "@/components/editors/PercentEditor";
import { TextEditor } from "@/components/editors/TextEditor";
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
  InventoryAdvisory,
  InventoryInspectResult,
  InventoryListResult,
  InventoryMovement,
  InventoryOptionsResult,
  InventoryRefusal,
  InventoryValuationResult,
} from "../../../shell/ledgerSetup";
import { useStrings, type Translate } from "../../../shell/strings";
import { formatDay } from "../../../shared/dateFormats";
import { formatAmount, formatDecimal } from "../../../shared/numbers";
import {
  CallLine,
  ChoiceField,
  FormGrid,
  Panel,
  readLanding,
  rankDecimal,
  Reading,
  SetupTable,
  useSetupDraft,
  useSetupWrite,
  type Column,
} from "../setup/SetupParts";
import type { SetupProps } from "../setup/setupProps";
import { setupCall, type SetupCall } from "../setup/setupModel";
import { grammarText } from "../setup/setupWords";
import { useWritePause, WriteHold } from "../WritePause";
import {
  blankExtra,
  blankMovement,
  BOOK_FIELDS,
  bookListed,
  bookName,
  bookNameOptions,
  bookRequest,
  bookTouched,
  changeLanded,
  CLOSING_FIELDS,
  closingLanded,
  closingRequest,
  closingTouched,
  CORRECT_FIELDS,
  correctRequest,
  COST_FIELDS,
  COUNT_FIELDS,
  DESCRIBE_FIELDS,
  describeRequest,
  draftOfMovement,
  EMPTY_BOOK,
  EMPTY_CLOSING,
  EMPTY_CORRECTION,
  evidenceRequest,
  EXTRA_FIELDS,
  historyRows,
  MOVEMENT_FIELDS,
  movementCorrectionRequest,
  movementCounted,
  movementRequest,
  movementTouched,
  NO_OFFERS,
  offersOf,
  plays,
  proofFromKept,
  PRICE_FIELDS,
  PROOF_SLOTS,
  REASON_FIELD,
  restoreRequest,
  retireRequest,
  reverseRequest,
  blankProof,
  servedWord,
  slotKinds,
  vocabularyOf,
  wordFrom,
  wordOf,
  type BookDraft,
  type Built,
  type ClosingDraft,
  type CorrectDraft,
  type DescribeDraft,
  type HistoryFact,
  type MovementDraft,
  type Offers,
  type Problems,
  type ProofDraft,
  type ProofSlotKey,
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

/** The family every reason key the backend serves for a refused inventory
 * change belongs to. */
const INVENTORY_REASON_FAMILY = "application.inventory.service.errors.";

/** Words for a refused call: the sentence the backend's catalogue has for the
 * reason it gave, filled in with the facts it gave. A reason without a
 * sentence, or one a fact is missing from, is said plainly and never as its
 * key or a code. */
function refusalWords(t: Translate, call: SetupCall<unknown> | null) {
  return (): string | null => {
    const found = refusalOf(call);
    if (call?.kind !== "refused" && found === null) return null;
    const plain = t("desktop.ledger.stock.refused");
    const key = found?.reason_key ?? null;
    if (
      found === null ||
      key === null ||
      !key.startsWith(INVENTORY_REASON_FAMILY)
    )
      return plain;
    const said = t(
      key,
      Object.fromEntries(
        (found.reason_facts ?? []).map((fact) => [fact.key, fact.value]),
      ),
    );
    return said === key || /\{\w+\}/.test(said) ? plain : said;
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

/** One field of a form, on the editor its kind of value has. */
function StockEntry({
  field,
  value,
  onValue,
  error,
  autoFocus,
}: {
  field: StockField;
  value: string;
  onValue(value: string): void;
  error: string | null;
  autoFocus: boolean;
}) {
  const t = useStrings();
  const id = useId();
  const hint = field.hint ? t(field.hint) : undefined;
  const describedBy =
    [hint ? `${id}-hint` : null, error ? `${id}-error` : null]
      .filter(Boolean)
      .join(" ") || undefined;
  const editor = {
    id,
    name: field.key,
    value,
    onChange: onValue,
    invalid: error ? true : undefined,
    describedBy,
    required: field.required,
    autoFocus,
  };
  return (
    <Field data-invalid={error ? true : undefined}>
      <FieldLabel htmlFor={id}>{t(field.label)}</FieldLabel>
      {field.control === "date" ? (
        <DateEditor {...editor} />
      ) : field.control === "money" ? (
        <MoneyEditor {...editor} />
      ) : field.control === "quantity" ? (
        <DecimalEditor {...editor} />
      ) : field.control === "share" ? (
        <PercentEditor {...editor} unit="fraction" />
      ) : (
        <TextEditor
          {...editor}
          {...field.offers}
          maxLength={field.max ?? (field.key === "description" ? 1024 : 120)}
        />
      )}
      {hint && <FieldDescription id={`${id}-hint`}>{hint}</FieldDescription>}
      <FieldError id={`${id}-error`}>{error}</FieldError>
    </Field>
  );
}

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
                hint={field.hint ? t(field.hint) : undefined}
                error={error}
                options={choices[field.key] ?? []}
              />
            ) : (
              <StockEntry
                field={field}
                value={valueOf(field)}
                onValue={(value) => onValue(field, value)}
                error={error}
                autoFocus={autoFocus && index === 0}
              />
            )}
          </div>
        );
      })}
    </FormGrid>
  );
}

/** The choices the backend serves for one family, in the words it has for
 * each. */
function choicesOf(t: Translate, offers: Offers, family: string) {
  return (offers[family] ?? []).map((served) => ({
    value: served.value,
    label: servedWord(t, served),
  }));
}

/** Reads the closed choices the forms offer. They are the backend's to
 * serve, so a form offers none until they are read. */
function useOffers(port: LedgerPort, reader: string | null, round: number) {
  const [read, setRead] = useState<SetupCall<InventoryOptionsResult> | null>(
    null,
  );
  useEffect(() => {
    setRead(null);
  }, [port, reader]);
  useEffect(() => {
    if (reader === null) return;
    let active = true;
    void (async () => {
      const answer = await setupCall(
        port,
        "ledger.inventory.options",
        {},
        false,
      );
      if (active) setRead(answer);
    })();
    return () => {
      active = false;
    };
  }, [port, reader, round]);
  const offers = useMemo(
    () => (read?.kind === "done" ? offersOf(read.result) : NO_OFFERS),
    [read],
  );
  const vocabulary = useMemo(() => vocabularyOf(offers), [offers]);
  return { offers, vocabulary, state: read === null ? "loading" : read.kind };
}

type OfferState = ReturnType<typeof useOffers>;

/** What a form says while the choices it offers are not there. */
function OffersNote({ state }: { state: OfferState["state"] }) {
  const t = useStrings();
  if (state === "done") return null;
  return state === "loading" ? (
    <Reading label={t("desktop.ledger.stock.options_loading")} />
  ) : (
    <Alert tone="warning" role="alert" icon={<Icon name="alert" />}>
      {t("desktop.ledger.stock.options_failed")}
    </Alert>
  );
}

/** A document the person chooses with the system's file dialog. The backend
 * reads and keeps it, and answers what it keeps it as; the window holds
 * neither the file nor a mark of its own making, and shows the file's name. */
function ProofPicker({
  port,
  label,
  hint,
  kinds,
  proof,
  onProof,
  fillIn,
  disabled = false,
}: {
  port: LedgerPort;
  label: string;
  hint?: string;
  /** The kinds the document can be; one kind asks for no choice. */
  kinds: readonly { value: string; label: string }[];
  proof: ProofDraft;
  onProof(change: (current: ProofDraft) => ProofDraft): void;
  fillIn: boolean;
  disabled?: boolean;
}) {
  const t = useStrings();
  const [failed, setFailed] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const choose = async () => {
    if (busy) return;
    setBusy(true);
    setFailed(null);
    try {
      const picks = await port.pickFiles(
        "documents",
        "file",
        t("desktop.ledger.import.filter.documents"),
      );
      const file = picks.files[0];
      if (!file) return;
      const kept = await setupCall(
        port,
        "ledger.inventory.evidence.add",
        evidenceRequest(file.token),
        true,
      );
      await port.forgetFiles([file.token]).catch(() => undefined);
      const proofKept =
        kept.kind === "done" ? proofFromKept(kept.result, file.name) : null;
      if (proofKept !== null)
        onProof((current) => ({
          ...current,
          reference: proofKept.reference,
          digest: proofKept.digest,
          fileName: proofKept.fileName,
        }));
      // A file the book did not keep says why in the book's own sentence,
      // and what is held already stays.
      else
        setFailed(refusalWords(t, kept)() ?? t("desktop.ledger.stock.refused"));
    } catch {
      setFailed(t("desktop.ledger.stock.refused"));
    } finally {
      setBusy(false);
    }
  };
  const shown = failed ?? (fillIn ? t(FILL_IN) : null);
  const word =
    proof.digest === ""
      ? t("desktop.ledger.stock.proof.choose_file")
      : t("desktop.ledger.stock.proof.change_file");
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
              onProof((current) => ({
                ...current,
                kind: event.target.value,
              }))
            }
          >
            <option value="" disabled>
              {t("desktop.ledger.form.choose")}
            </option>
            {kinds.map((kind) => (
              <option key={kind.value} value={kind.value}>
                {kind.label}
              </option>
            ))}
          </NativeSelect>
        )}
        <Button
          type="button"
          size="sm"
          variant="outline"
          aria-label={`${label}: ${word}`}
          aria-disabled={busy || disabled || undefined}
          onClick={() => {
            if (!disabled) void choose();
          }}
        >
          <Icon name="attach" size="sm" />
          {busy ? t("desktop.ledger.stock.proof.keeping") : word}
        </Button>
        {proof.digest !== "" && (
          <span className="flex items-center gap-1 text-sm text-muted-foreground">
            <Icon name="check" size="sm" />
            {proof.fileName ?? t("desktop.ledger.stock.proof.kept")}
          </span>
        )}
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
      {!ready && !busy && (
        <span className="self-center text-xs text-muted-foreground">
          {t("desktop.ledger.form.fill_to_continue")}
        </span>
      )}
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
  books,
  catalogue,
  onClose,
  onWritten,
}: {
  port: LedgerPort;
  year: number;
  /** The books held, in every year; null while unread or where it failed. */
  books: readonly InventoryBookRow[] | null;
  catalogue: OfferState;
  onClose(): void;
  onWritten(): void;
}) {
  const t = useStrings();
  const write = useSetupWrite(t("desktop.ledger.stock.title"));
  const [draft, setDraft] = useState<BookDraft>(EMPTY_BOOK);
  const [tried, setTried] = useState(false);
  useSetupDraft(bookTouched(draft));
  const built = bookRequest(year, draft, catalogue.vocabulary);
  const choices = {
    method: choicesOf(t, catalogue.offers, "valuation_method"),
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
        <OffersNote state={catalogue.state} />
        <StockFields
          fields={BOOK_FIELDS.map((field) =>
            field.key === "name" && books !== null
              ? {
                  ...field,
                  offers: { suggestions: bookNameOptions(books, year) },
                }
              : field,
          )}
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
        <CallLine call={write.last} refusal={refusalWords(t, write.last)} />
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
        <CallLine call={write.last} refusal={refusalWords(t, write.last)} />
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
  catalogue,
  onClose,
  onWritten,
}: {
  port: LedgerPort;
  book: InventoryBookRow;
  catalogue: OfferState;
  onClose(): void;
  onWritten(): void;
}) {
  const t = useStrings();
  const [draft, setDraft] = useState<CorrectDraft>(EMPTY_CORRECTION);
  const [correction] = useState(mint);
  const [tried, setTried] = useState(false);
  const built = correctRequest(book, correction, draft, catalogue.vocabulary);
  const choices = {
    reason: choicesOf(t, catalogue.offers, "correction_reason"),
    method: [
      { value: "", label: t("desktop.ledger.stock.field.keep") },
      ...choicesOf(t, catalogue.offers, "valuation_method"),
    ],
  };
  return (
    <ChangeForm
      port={port}
      definition="ledger.inventory.correct"
      book={book}
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
      <OffersNote state={catalogue.state} />
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
    date: formatDay(locale, movement.movement_date),
    kind: wordOf(t, "movement_kind", movement.kind),
    quantity: formatDecimal(locale, movement.quantity.decimal),
  });
}

function ReverseForm({
  port,
  book,
  target,
  locale,
  catalogue,
  onClose,
  onWritten,
}: {
  port: LedgerPort;
  catalogue: OfferState;
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
  const built = reverseRequest(
    book,
    correction,
    target.movement_id,
    reason,
    catalogue.vocabulary,
  );
  return (
    <ChangeForm
      port={port}
      definition="ledger.inventory.movement.reverse"
      book={book}
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
      <OffersNote state={catalogue.state} />
      <StockFields
        fields={[REASON_FIELD]}
        valueOf={() => reason}
        onValue={(_, value) => setReason(value)}
        choices={{
          reason: choicesOf(t, catalogue.offers, "correction_reason"),
        }}
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
  catalogue,
  onClose,
  onWritten,
}: {
  port: LedgerPort;
  catalogue: OfferState;
  book: InventoryBookRow;
  onClose(): void;
  onWritten(): void;
}) {
  const t = useStrings();
  const [reason, setReason] = useState("");
  const [correction] = useState(mint);
  const [tried, setTried] = useState(false);
  const built = retireRequest(book, correction, reason, catalogue.vocabulary);
  return (
    <ChangeForm
      port={port}
      definition="ledger.inventory.retire"
      book={book}
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
      <OffersNote state={catalogue.state} />
      <StockFields
        fields={[REASON_FIELD]}
        valueOf={() => reason}
        onValue={(_, value) => setReason(value)}
        choices={{
          reason: choicesOf(t, catalogue.offers, "retirement_reason"),
        }}
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

/** The document a change of a proof is for: a slot of the purchase, or the
 * extra cost with the key it was minted. */
type ProofTarget = { slot: ProofSlotKey } | { extra: string };

/** What a movement form holds: what is typed, the extra costs and the files
 * kept. */
function useMovementDraft(initial: MovementDraft) {
  const [draft, setDraft] = useState<MovementDraft>(initial);
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
  const setProof = (
    target: ProofTarget,
    change: (current: ProofDraft) => ProofDraft,
  ) => {
    setDraft((current) =>
      "slot" in target
        ? {
            ...current,
            proofs: {
              ...current.proofs,
              [target.slot]: change(current.proofs[target.slot]),
            },
          }
        : {
            ...current,
            extras: current.extras.map((extra) =>
              extra.key === target.extra
                ? { ...extra, proof: change(extra.proof) }
                : extra,
            ),
          },
    );
  };
  return { draft, setDraft, setValue, setExtra, setProof };
}

type MovementDraftState = ReturnType<typeof useMovementDraft>;

/** The fields of a movement: its date, kind and units, then what its kind
 * states about its cost. A purchase states its price, its extra costs and
 * the files that show them; what it all comes to is the backend's to add up. */
function MovementFields({
  port,
  catalogue,
  state,
  built,
  tried,
}: {
  port: LedgerPort;
  catalogue: OfferState;
  state: MovementDraftState;
  built: Built<unknown>;
  tried: boolean;
}) {
  const t = useStrings();
  const { draft, setValue, setExtra, setProof, setDraft } = state;
  const kind = draft.values.kind ?? "";
  const purchase = plays(catalogue.vocabulary, "purchase", kind);
  const choices = { kind: choicesOf(t, catalogue.offers, "movement_kind") };
  const extraChoices = {
    kind: choicesOf(t, catalogue.offers, "attributable_cost_kind"),
  };
  const common = {
    problems: built.problems,
    missing: built.missing,
    tried,
  };
  const slotFill = (slot: ProofSlotKey) =>
    tried &&
    (built.missing.has(`${slot}:file`) || built.missing.has(`${slot}:kind`));
  const kindsOf = (slot: ProofSlotKey) => {
    const allowed = slotKinds(slot, catalogue.vocabulary);
    return (catalogue.offers.acquisition_evidence_kind ?? [])
      .filter((served) => allowed.includes(served.value))
      .map((served) => ({
        value: served.value,
        label: servedWord(t, served),
      }));
  };
  const ready = catalogue.state === "done";
  return (
    <>
      <OffersNote state={catalogue.state} />
      <StockFields
        fields={MOVEMENT_FIELDS}
        valueOf={(field) => draft.values[field.key] ?? ""}
        onValue={setValue}
        choices={choices}
        {...common}
      />
      {kind !== "" && !purchase && (
        <StockFields
          fields={COST_FIELDS}
          valueOf={(field) => draft.values[field.key] ?? ""}
          onValue={setValue}
          choices={{}}
          {...common}
        />
      )}
      {purchase && (
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
                    port={port}
                    label={t("desktop.ledger.stock.proof.extra")}
                    kinds={(catalogue.offers.acquisition_evidence_kind ?? [])
                      .filter((served) =>
                        slotKinds("price", catalogue.vocabulary).includes(
                          served.value,
                        ),
                      )
                      .map((served) => ({
                        value: served.value,
                        label: servedWord(t, served),
                      }))}
                    proof={extra.proof}
                    onProof={(change) => setProof({ extra: extra.key }, change)}
                    disabled={!ready}
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
          <Section heading={t("desktop.ledger.stock.purchase.proofs")}>
            <p className="text-sm text-muted-foreground">
              {t("desktop.ledger.stock.purchase.proofs_hint")}
            </p>
            {PROOF_SLOTS.map((slot) => (
              <ProofPicker
                key={slot.key}
                port={port}
                label={t(slot.label)}
                hint={slot.hint ? t(slot.hint) : undefined}
                kinds={kindsOf(slot.key)}
                proof={draft.proofs[slot.key]}
                onProof={(change) => setProof({ slot: slot.key }, change)}
                disabled={!ready}
                fillIn={slotFill(slot.key)}
              />
            ))}
          </Section>
          <p className="text-sm text-muted-foreground">
            {t("desktop.ledger.stock.purchase.totals_note")}
          </p>
        </>
      )}
    </>
  );
}

function MovementForm({
  port,
  book,
  catalogue,
  onClose,
  onWritten,
}: {
  port: LedgerPort;
  book: InventoryBookRow;
  catalogue: OfferState;
  onClose(): void;
  onWritten(): void;
}) {
  const t = useStrings();
  const write = useSetupWrite(t("desktop.ledger.stock.title"));
  // The movement's reference is minted once, when the form opens, and never
  // shown or typed. A movement sent again under it is refused.
  const [reference] = useState(mint);
  const state = useMovementDraft(blankMovement());
  const [tried, setTried] = useState(false);
  useSetupDraft(movementTouched(state.draft));
  const built = movementRequest(
    book,
    reference,
    state.draft,
    catalogue.vocabulary,
  );

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
        <MovementFields
          port={port}
          catalogue={catalogue}
          state={state}
          built={built}
          tried={tried}
        />
        <FormButtons
          busy={write.busy}
          ready={built.request !== null}
          submit={t("desktop.ledger.stock.submit.movement")}
          onClose={onClose}
        />
        <CallLine call={write.last} refusal={refusalWords(t, write.last)} />
      </form>
    </Panel>
  );
}

function MovementCorrectForm({
  port,
  book,
  target,
  catalogue,
  onClose,
  onWritten,
}: {
  port: LedgerPort;
  book: InventoryBookRow;
  target: InventoryMovement;
  catalogue: OfferState;
  onClose(): void;
  onWritten(): void;
}) {
  const t = useStrings();
  // Both references are minted once, when the form opens, and never shown.
  const [ids] = useState(() => ({ correction: mint(), movement: mint() }));
  const [initial] = useState(() =>
    draftOfMovement(target, catalogue.vocabulary),
  );
  const state = useMovementDraft(initial);
  const [reason, setReason] = useState("");
  const [tried, setTried] = useState(false);
  const built = movementCorrectionRequest(
    book,
    ids,
    target.movement_id,
    reason,
    state.draft,
    catalogue.vocabulary,
  );
  const changed =
    reason !== "" || JSON.stringify(state.draft) !== JSON.stringify(initial);
  return (
    <ChangeForm
      port={port}
      definition="ledger.inventory.movement.correct"
      book={book}
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
        choices={{
          reason: choicesOf(t, catalogue.offers, "correction_reason"),
        }}
        problems={built.problems}
        missing={built.missing}
        tried={tried}
        autoFocus
      />
      <MovementFields
        port={port}
        catalogue={catalogue}
        state={state}
        built={built}
        tried={tried}
      />
    </ChangeForm>
  );
}

// ---- A closing value -----------------------------------------------------------------

/** The closing value of a book from the facts the person knows: how it is
 * decided, why, the documents that show it, and the count when the count is
 * the value. Nothing is hashed or fingerprinted here. */
function ClosingForm({
  port,
  book,
  catalogue,
  onClose,
  onWritten,
}: {
  port: LedgerPort;
  book: InventoryBookRow;
  catalogue: OfferState;
  onClose(): void;
  onWritten(): void;
}) {
  const t = useStrings();
  const write = useSetupWrite(t("desktop.ledger.stock.title"));
  // Keep the decision reference stable when the form is submitted again.
  const [ids] = useState(() => ({
    decision: mint(),
  }));
  const [draft, setDraft] = useState<ClosingDraft>(EMPTY_CLOSING);
  const [tried, setTried] = useState(false);
  useSetupDraft(closingTouched(draft));
  const built = closingRequest(book, ids, draft, catalogue.vocabulary);
  const physical = plays(
    catalogue.vocabulary,
    "count_authority",
    draft.values.authority,
  );
  const ready = catalogue.state === "done";

  const setValue = (field: StockField, value: string) =>
    setDraft((current) => ({
      ...current,
      values: { ...current.values, [field.key]: value },
    }));
  const setRole = (
    group: "decision" | "count",
    role: string,
    change: (current: ProofDraft) => ProofDraft,
  ) => {
    setDraft((current) => ({
      ...current,
      [group]: {
        ...current[group],
        [role]: change(current[group][role] ?? blankProof(role)),
      },
    }));
  };
  const setPrior = (
    key: string,
    change: (current: ProofDraft) => ProofDraft,
  ) => {
    setDraft((current) => ({
      ...current,
      prior: current.prior.map((entry) =>
        entry.key === key ? { ...entry, proof: change(entry.proof) } : entry,
      ),
    }));
  };
  const filled = (key: string) => tried && built.missing.has(`${key}:file`);
  const roles = (family: string) => catalogue.offers[family] ?? [];

  const send = async () => {
    if (write.busy) return;
    const request = built.request;
    if (request === null) {
      setTried(true);
      return;
    }
    const done = await write.run(
      () =>
        setupCall(port, "ledger.inventory.closing-value.record", request, true),
      readLanding(
        port,
        "ledger.inventory.inspect",
        { actividad_id: book.actividad_id, year: book.year },
        (read) => closingLanded(read.ledger),
      ),
    );
    if (done.kind === "done" && refusalOf(done) === null) onWritten();
  };

  const documents = (
    group: "decision" | "count",
    family: string,
    heading: string,
  ) => (
    <Section heading={heading}>
      {roles(family).map((served) => (
        <ProofPicker
          key={served.value}
          port={port}
          label={servedWord(t, served)}
          kinds={[]}
          proof={draft[group][served.value] ?? blankProof(served.value)}
          onProof={(change) => setRole(group, served.value, change)}
          disabled={!ready}
          fillIn={filled(`${group}:${served.value}`)}
        />
      ))}
    </Section>
  );

  return (
    <Panel
      title={t("desktop.ledger.stock.form.closing", {
        name: bookName(book),
        year: book.year,
      })}
      className="ledger-stock-form ledger-stock-form-closing"
    >
      <form
        noValidate
        className="flex flex-col gap-4"
        onSubmit={(event) => {
          event.preventDefault();
          void send();
        }}
      >
        <p className="text-sm text-muted-foreground">
          {t("desktop.ledger.stock.closing.note")}
        </p>
        <OffersNote state={catalogue.state} />
        <StockFields
          fields={CLOSING_FIELDS}
          valueOf={(field) => draft.values[field.key] ?? ""}
          onValue={setValue}
          choices={{
            authority: choicesOf(t, catalogue.offers, "closing_authority"),
          }}
          problems={built.problems}
          missing={built.missing}
          tried={tried}
          autoFocus
        />
        {physical && (
          <Section heading={t("desktop.ledger.stock.closing.count")}>
            <StockFields
              fields={COUNT_FIELDS}
              valueOf={(field) => draft.values[field.key] ?? ""}
              onValue={setValue}
              choices={{
                basis: choicesOf(
                  t,
                  catalogue.offers,
                  "closing_valuation_basis",
                ),
              }}
              problems={built.problems}
              missing={built.missing}
              tried={tried}
            />
          </Section>
        )}
        {physical &&
          documents(
            "count",
            "physical_evidence_role",
            t("desktop.ledger.stock.closing.count_documents"),
          )}
        {documents(
          "decision",
          "decision_evidence_role",
          t("desktop.ledger.stock.closing.documents"),
        )}
        <Section
          heading={t("desktop.ledger.stock.closing.prior")}
          actions={
            <IconButton
              label={t("desktop.ledger.stock.closing.prior_add")}
              onClick={() =>
                setDraft((current) => ({
                  ...current,
                  prior: [
                    ...current.prior,
                    { key: mint(), proof: blankProof() },
                  ],
                }))
              }
            >
              <Icon name="plus" />
            </IconButton>
          }
        >
          <p className="text-sm text-muted-foreground">
            {t("desktop.ledger.stock.closing.prior_hint")}
          </p>
          {draft.prior.map((entry) => (
            <div key={entry.key} className="flex items-end gap-2">
              <ProofPicker
                port={port}
                label={t("desktop.ledger.stock.closing.prior_document")}
                kinds={[]}
                proof={entry.proof}
                onProof={(change) => setPrior(entry.key, change)}
                disabled={!ready}
                fillIn={filled(`prior:${entry.key}`)}
              />
              <IconButton
                label={t("desktop.ledger.stock.closing.prior_remove")}
                onClick={() =>
                  setDraft((current) => ({
                    ...current,
                    prior: current.prior.filter(
                      (found) => found.key !== entry.key,
                    ),
                  }))
                }
              >
                <Icon name="trash" />
              </IconButton>
            </div>
          ))}
        </Section>
        <FormButtons
          busy={write.busy}
          ready={built.request !== null}
          submit={t("desktop.ledger.stock.submit.closing")}
          onClose={onClose}
        />
        <CallLine call={write.last} refusal={refusalWords(t, write.last)} />
      </form>
    </Panel>
  );
}

// ---- What a book holds ------------------------------------------------------------------

/** A fact of the history, in words. */
function factText(t: Translate, locale: string, fact: HistoryFact): string {
  switch (fact.kind) {
    case "opening":
      return t("desktop.ledger.stock.fact.opening", {
        value: formatAmount(locale, fact.value),
      });
    case "method":
      return t("desktop.ledger.stock.fact.method", {
        value: wordOf(t, "valuation_method", fact.value),
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
  offers,
}: {
  offers: Offers;
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
          cell: (row) => formatDay(locale, row.day),
        },
        {
          key: "what",
          label: t("desktop.ledger.stock.history.what"),
          cell: (row) => wordFrom(t, offers, "history_kind", row.kind),
        },
        {
          key: "reason",
          label: t("desktop.ledger.stock.history.reason"),
          cell: (row) =>
            row.reason === null
              ? "—"
              : row.reason.family === "correction"
                ? wordFrom(t, offers, "correction_reason", row.reason.token)
                : wordFrom(t, offers, "retirement_reason", row.reason.token),
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

// ---- What a purchase came to -------------------------------------------------------

/** The family every sentence the backend serves as an advisory belongs to. */
const ADVISORY_FAMILY = "application.inventory.advisories.";

type FactLine = { key: string; label: string; value: string };

/** A purchase as the backend keeps it: the price, each extra cost, what the
 * backend added up, and the kinds of document it rests on. Every figure is
 * read from what the backend served; none is worked out here. */
function PurchaseFacts({
  movement,
  locale,
  onClose,
}: {
  movement: InventoryMovement;
  locale: string;
  onClose(): void;
}) {
  const t = useStrings();
  const cost = movement.acquisition_cost ?? null;
  const detail = movement.acquisition_detail ?? null;
  const money = (value: { decimal: string }) =>
    formatAmount(locale, value.decimal);
  const lines: FactLine[] = [];
  if (cost !== null) {
    lines.push({
      key: "price",
      label: t("desktop.ledger.stock.facts.price"),
      value: money(cost.consideration_excluding_iva),
    });
    if (detail !== null) {
      lines.push({
        key: "iva",
        label: t("desktop.ledger.stock.facts.iva"),
        value: money(detail.consideration_iva_amount),
      });
      for (const component of detail.components)
        lines.push({
          key: component.component_id,
          label: wordOf(t, "attributable_cost_kind", component.kind),
          value: money(component.taxable_base),
        });
    }
    lines.push(
      {
        key: "extra_total",
        label: t("desktop.ledger.stock.facts.extra_total"),
        value: money(cost.directly_attributable_cost_total),
      },
      {
        key: "recoverable",
        label: t("desktop.ledger.stock.facts.recoverable"),
        value: money(cost.recoverable_iva_excluded),
      },
      {
        key: "unrecoverable",
        label: t("desktop.ledger.stock.facts.unrecoverable"),
        value: money(cost.nonrecoverable_iva_included),
      },
      {
        key: "total",
        label: t("desktop.ledger.stock.facts.total"),
        value: money(cost.total_acquisition_cost),
      },
    );
  }
  return (
    <Panel
      title={t("desktop.ledger.stock.facts.title", {
        date: formatDay(locale, movement.movement_date),
      })}
      className="ledger-stock-form ledger-stock-purchase"
    >
      <div className="flex flex-col gap-3">
        {cost === null ? (
          <p className="text-sm text-muted-foreground">
            {t("desktop.ledger.stock.facts.unknown")}
          </p>
        ) : (
          <SetupTable
            label={t("desktop.ledger.stock.facts.table")}
            rows={lines}
            rowKey={(line) => line.key}
            className="ledger-stock-purchase-lines"
            columns={[
              {
                key: "what",
                label: t("desktop.ledger.stock.facts.what"),
                cell: (line) => line.label,
              },
              {
                key: "amount",
                label: t("desktop.ledger.stock.facts.amount"),
                numeric: true,
                cell: (line) => line.value,
              },
            ]}
          />
        )}
        <section className="flex flex-col gap-1">
          <h4 className="font-medium">
            {t("desktop.ledger.stock.facts.documents")}
          </h4>
          {detail === null || detail.documents.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              {t("desktop.ledger.stock.facts.documents_unknown")}
            </p>
          ) : (
            <ul className="ledger-stock-documents text-sm">
              {detail.documents.map((document) => (
                <li
                  key={`${document.reference}|${document.evidence_kind}`}
                  className="flex items-center gap-1"
                >
                  <Icon name="attach" size="sm" />
                  {t("desktop.ledger.stock.facts.document", {
                    kind: wordOf(
                      t,
                      "acquisition_evidence_kind",
                      document.evidence_kind,
                    ),
                    name:
                      document.file_name ??
                      t("desktop.ledger.stock.proof.kept"),
                  })}
                </li>
              ))}
            </ul>
          )}
        </section>
        <div className="flex">
          <Button type="button" size="sm" variant="ghost" onClick={onClose}>
            {t("desktop.ledger.form.close")}
          </Button>
        </div>
      </div>
    </Panel>
  );
}

/** What the backend says about a book that the person should know, said in
 * its own sentence with the year filled in. A sentence it has no words for
 * is left out rather than shown as a key. */
function Advisories({
  advisories,
  className,
}: {
  advisories: readonly InventoryAdvisory[] | undefined;
  className: string;
}) {
  const t = useStrings();
  const said = (advisories ?? []).flatMap((advisory) => {
    if (!advisory.key.startsWith(ADVISORY_FAMILY)) return [];
    const sentence = t(advisory.key, { year: advisory.year });
    return sentence === advisory.key ? [] : [{ advisory, sentence }];
  });
  if (said.length === 0) return null;
  return (
    <>
      {said.map(({ advisory, sentence }) => (
        <Alert
          key={`${advisory.code}|${advisory.year}`}
          tone="warning"
          icon={<Icon name="alert" />}
          className={className}
        >
          {sentence}
        </Alert>
      ))}
    </>
  );
}

// ---- The pane -------------------------------------------------------------------------

type Task =
  | { kind: "book" }
  | {
      kind:
        "movement" | "describe" | "correct" | "retire" | "restore" | "closing";
      book: BookKey;
    }
  | {
      kind: "movement_correct" | "movement_reverse" | "purchase_facts";
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
  const catalogue = useOffers(port, reader, round);

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
                    reason: wordOf(
                      t,
                      "retirement_reason",
                      row.retirement_reason,
                    ),
                  })
                : t("desktop.ledger.stock.retired")}
            </span>
          )}
          {(row.advisories ?? []).length > 0 && (
            <Pill
              icon="alert"
              count={(row.advisories ?? []).length}
              label={t("desktop.ledger.stock.count.advisories", {
                count: (row.advisories ?? []).length,
              })}
            />
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
      sort: (row) => wordOf(t, "valuation_method", row.valuation_method),
      cell: (row) => wordOf(t, "valuation_method", row.valuation_method),
    },
    {
      key: "opening",
      label: t("desktop.ledger.inventory.column.opening"),
      numeric: true,
      sort: (row) => rankDecimal(row.opening_stock.decimal),
      cell: (row) => formatAmount(locale, row.opening_stock.decimal),
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
                label={t("desktop.ledger.stock.action.closing")}
                hint={why}
                aria-disabled={stopped || undefined}
                className="ledger-stock-closing"
                onClick={() => !stopped && open({ kind: "closing", book: key })}
              >
                <Icon name="lock" />
              </IconButton>
            </WriteHold>
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
          books={list?.kind === "done" ? listed : null}
          catalogue={catalogue}
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
    const common = {
      port,
      book: row,
      catalogue,
      onClose: close,
      onWritten: written,
    };
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
      case "closing":
        return <ClosingForm key={key} {...common} />;
      case "purchase_facts":
        return (
          <PurchaseFacts
            key={`${key}|${task.target.movement_id}`}
            movement={task.target}
            locale={locale}
            onClose={close}
          />
        );
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
        <Advisories
          advisories={ledger.advisories ?? book.advisories}
          className="ledger-stock-advisory"
        />
        {ledger.closing_authority_fingerprints !== null && (
          <Alert
            icon={<Icon name="lock" />}
            className="ledger-stock-closing-recorded"
          >
            {t("desktop.ledger.stock.closing.recorded", { year: book.year })}
          </Alert>
        )}
        {ledger.period_movements.length === 0 ? (
          <p className="ledger-stock-movements-note text-sm text-muted-foreground">
            {t(
              stopped
                ? "desktop.ledger.stock.movements_none_retired"
                : "desktop.ledger.stock.movements_none",
            )}
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
                cell: (movement) => formatDay(locale, movement.movement_date),
              },
              {
                key: "kind",
                label: t("desktop.ledger.inventory.column.kind"),
                sort: (movement) => wordOf(t, "movement_kind", movement.kind),
                cell: (movement) => wordOf(t, "movement_kind", movement.kind),
              },
              {
                key: "quantity",
                label: t("desktop.ledger.inventory.column.quantity"),
                numeric: true,
                sort: (movement) => rankDecimal(movement.quantity.decimal),
                cell: (movement) =>
                  formatDecimal(locale, movement.quantity.decimal),
              },
              {
                key: "unit",
                label: t("desktop.ledger.inventory.column.unit_cost"),
                numeric: true,
                sort: (movement) => rankDecimal(movement.unit_cost?.decimal),
                cell: (movement) =>
                  movement.unit_cost
                    ? formatDecimal(locale, movement.unit_cost.decimal, {
                        minFraction: 0,
                        maxFraction: 6,
                      })
                    : "—",
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
                  return cost === undefined ? "—" : formatAmount(locale, cost);
                },
              },
              {
                key: "actions",
                label: t("desktop.ledger.form.actions"),
                hidden: true,
                resizable: false,
                cell: (movement) => (
                  <RowActions>
                    {plays(catalogue.vocabulary, "purchase", movement.kind) && (
                      <IconButton
                        label={t("desktop.ledger.stock.action.purchase_facts")}
                        className="ledger-stock-purchase-facts"
                        onClick={() =>
                          open({
                            kind: "purchase_facts",
                            book: bookKey,
                            target: movement,
                          })
                        }
                      >
                        <Icon name="eye" />
                      </IconButton>
                    )}
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
        <History
          ledger={ledger}
          locale={locale}
          name={bookName(book)}
          offers={catalogue.offers}
        />
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
              closing: formatAmount(
                locale,
                valued.derived_closing_value.decimal,
              ),
              cogs: formatAmount(locale, valued.cogs.decimal),
              method: wordOf(t, "valuation_method", valued.valuation_method),
            })}
          </span>
          <span className="text-sm">
            {t("desktop.ledger.inventory.preview_note")}
          </span>
        </Alert>
      )}
      {preview && preview.call.kind !== "done" && book && (
        <CallLine call={preview.call} refusal={refusalWords(t, preview.call)} />
      )}
      {preview?.call.kind === "done" && refusalOf(preview.call) !== null && (
        <Alert
          tone="danger"
          role="alert"
          icon={<Icon name="refused" />}
          className="ledger-stock-refused"
        >
          {refusalWords(t, preview.call)()}
        </Alert>
      )}
      {list?.kind === "done" && movementsBody()}
    </div>
  );
}
