import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { cn } from "@/components/ui/cn";
import { Icon } from "@/components/ui/icon";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import {
  SegmentedControl,
  SegmentedControlItem,
} from "@/components/ui/segmented-control";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import type {
  CatalogueInvoice,
  InvoiceAddRequest,
  InvoiceAddResult,
  InvoiceKind,
  InvoiceUpdateField,
  InvoiceUpdateRequest,
  LedgerPort,
  PaymentStatus,
} from "../../../shell/ledger";
import { IVA_CATEGORIES, isIvaCategory } from "../../../shell/ledgerVocabulary";
import { useStrings, type Translate } from "../../../shell/strings";
import { localDay } from "../../../shared/dates";
import { amountText, dayText } from "../transfer/transferWords";
import { useWritePause, WriteHold } from "../WritePause";
import {
  EditorSection,
  FixedField,
  FormField,
  type ControlProps,
} from "./InvoiceFields";
import { DraftLines, StoredLines } from "./InvoiceLines";
import {
  CREATION_INVARIANTS,
  INVOICE_CLASSES,
  OPERATION_TYPES,
  PAYMENT_STATUSES,
  PREMISES_SITUATIONS,
  RETENTION_PRESETS,
  checkCorrection,
  checkDraft,
  correctionOf,
  emptyDraft,
  emptyLine,
  lessDecimal,
  seriesAndNumber,
  shownRetentionAmount,
  suggestNumber,
  type CorrectionDraft,
  type InvoiceDraft,
  type Problem,
} from "./invoiceModel";
import {
  classLabel,
  figureText,
  kindChoice,
  kindLabel,
  paymentLabel,
  problemText,
} from "./invoiceWords";
import {
  addLanded,
  removeLanded,
  updateLanded,
  write,
  type Landed,
} from "./invoiceWrites";

/** Which invoice the editor shows: a new one, or one in the catalogue. */
export type EditorTarget =
  { kind: "new" } | { kind: "open"; invoiceId: string };

/** A write the editor sent and did not see settle. */
type Pending =
  | { what: "add"; request: InvoiceAddRequest }
  | { what: "update"; request: InvoiceUpdateRequest }
  | { what: "remove"; invoiceId: string };

type Outcome =
  | { kind: "refused"; text: string }
  | { kind: "failed"; code: string }
  | { kind: "unknown"; pending: Pending; checked: boolean }
  | { kind: "not_saved" };

const ivaCategoryLabel = (t: Translate, id: string) =>
  isIvaCategory(id) ? t(`desktop.ledger.iva_category.${id}`) : id;

let lineKeys = 0;
const nextLineKey = () => {
  lineKeys += 1;
  return `line-${lineKeys}`;
};

/**
 * The invoice editor, a modal sheet. A new invoice starts with nothing
 * assumed: the person says whether they issued or received it, and names
 * its country and currency. Its four requirements are named at the top and
 * ticked as they are met. A stored invoice shows its identity and lines as
 * fixed, with why, and lets the person correct only what the ledger lets
 * them correct. Every write is reviewed first and sent once; an outcome
 * that was not seen is said to be unknown, and nothing more is written
 * until the person checks.
 */
export function InvoiceEditor({
  port,
  locale,
  invoices,
  target,
  onClose,
  onWritten,
  onOpenInvoice,
  say,
}: {
  port: LedgerPort;
  locale: string;
  /** The catalogue as read, for the next number and the stored invoice. */
  invoices: readonly CatalogueInvoice[];
  target: EditorTarget;
  onClose(): void;
  /** An invoice the ledger stored, or null with the id of one it removed. */
  onWritten(invoice: CatalogueInvoice | null, removed?: string): void;
  onOpenInvoice(invoiceId: string): void;
  /** Confirms a write in a toast. */
  say(text: string): void;
}) {
  const t = useStrings();
  const opened =
    target.kind === "open"
      ? (invoices.find((found) => found.invoice_id === target.invoiceId) ??
        null)
      : null;
  // The stored invoice as it was opened: a write closes the editor.
  const [stored] = useState<CatalogueInvoice | null>(opened);
  const [draft, setDraft] = useState<InvoiceDraft>(() =>
    emptyDraft(nextLineKey()),
  );
  const initialDraft = useRef(JSON.stringify(draft));
  const [correction, setCorrection] = useState<CorrectionDraft | null>(() =>
    opened ? correctionOf(opened) : null,
  );
  const [stage, setStage] = useState<"edit" | "confirm" | "remove">("edit");
  const [asking, setAsking] = useState(false);
  const [sending, setSending] = useState(false);
  const [outcome, setOutcome] = useState<Outcome | null>(null);
  const [tried, setTried] = useState(false);
  const [touched, setTouched] = useState<ReadonlySet<string>>(new Set());
  const [duplicate, setDuplicate] = useState<string | null>(null);
  const pause = useWritePause();
  // A write the page settles after this editor closed says nothing here.
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  const isNew = target.kind === "new";
  const check = useMemo(() => checkDraft(draft), [draft]);
  const corrected = useMemo(
    () => (stored && correction ? checkCorrection(stored, correction) : null),
    [stored, correction],
  );
  const problems: Record<string, Problem> = isNew
    ? check.problems
    : (corrected?.problems ?? {});
  const unknown = outcome?.kind === "unknown";
  const dirty = isNew
    ? JSON.stringify(draft) !== initialDraft.current
    : (corrected?.changed.length ?? 0) > 0;

  const touch = (field: string) =>
    setTouched((held) => (held.has(field) ? held : new Set(held).add(field)));
  const shown = (field: string) => {
    const problem = problems[field];
    if (!problem) return null;
    if (tried || (touched.has(field) && problem.kind === "grammar"))
      return problemText(t, problem);
    return null;
  };
  const edit = <K extends keyof InvoiceDraft>(
    key: K,
    value: InvoiceDraft[K],
  ) => {
    setDraft((held) => ({ ...held, [key]: value }));
    if (key === "number") setDuplicate(null);
    if (outcome?.kind !== "unknown") setOutcome(null);
    setStage("edit");
  };
  const correct = <K extends keyof CorrectionDraft>(
    key: K,
    value: CorrectionDraft[K],
  ) => {
    setCorrection((held) => (held ? { ...held, [key]: value } : held));
    if (outcome?.kind !== "unknown") setOutcome(null);
    setStage("edit");
  };

  const close = () => {
    if (sending) return;
    if (asking) {
      setAsking(false);
      return;
    }
    if (dirty) setAsking(true);
    else onClose();
  };

  // ---- Writes ----------------------------------------------------------------

  const settled = (landed: Landed, pending: Pending) => {
    if (landed.kind === "unreadable") {
      setOutcome({ kind: "unknown", pending, checked: true });
      return;
    }
    if (landed.kind === "not_saved") {
      setOutcome({ kind: "not_saved" });
      setStage("edit");
      return;
    }
    if (pending.what === "remove") {
      say(t("desktop.ledger.invoices.removed", { number: numberOf(stored) }));
      onWritten(null, pending.invoiceId);
    } else {
      const invoice = landed.invoice;
      say(
        t(
          pending.what === "add"
            ? "desktop.ledger.invoices.added"
            : "desktop.ledger.invoices.saved",
          { number: invoice ? seriesAndNumber(invoice) : numberOf(stored) },
        ),
      );
      onWritten(invoice);
    }
    onClose();
  };

  /** Reads whether `pending` landed. */
  const landedOf = (pending: Pending): Promise<Landed> =>
    pending.what === "add"
      ? addLanded(port, pending.request)
      : pending.what === "update"
        ? updateLanded(port, pending.request)
        : removeLanded(port, pending.invoiceId);

  /** A write not seen to settle: the editor says so, and every write on
   * the page waits until the page's re-read reads whether it landed. */
  const undetermined = (pending: Pending, saved: boolean) => {
    setOutcome({ kind: "unknown", pending, checked: false });
    const what = t("desktop.ledger.invoices.title", {
      number:
        pending.what === "add"
          ? pending.request.invoice_number
          : numberOf(stored),
    });
    pause.hold({
      what,
      outcome: saved ? "saved_unread" : "unknown",
      settle: async () => {
        const landed = await landedOf(pending);
        if (mounted.current) settled(landed, pending);
        if (landed.kind === "unreadable") return null;
        return [
          t(
            landed.kind === "saved"
              ? "desktop.ledger.paused.found_saved"
              : "desktop.ledger.paused.unsaved",
            { movement: what },
          ),
        ];
      },
    });
  };

  const refusedText = (reason: string | null) =>
    t("desktop.ledger.invoices.refused", { code: reason ?? "refused" });

  const add = async (request: InvoiceAddRequest) => {
    setSending(true);
    const answer = await write(port, "ledger.invoice.add", request);
    setSending(false);
    if (answer.kind === "done") {
      const result = answer.result;
      if (result.outcome === "created" && result.invoice) {
        say(
          result.euro_value_pending
            ? t("desktop.ledger.invoices.added_no_rate", {
                number: seriesAndNumber(result.invoice),
              })
            : t("desktop.ledger.invoices.added", {
                number: seriesAndNumber(result.invoice),
              }),
        );
        onWritten(result.invoice);
        onClose();
        return;
      }
      refuseAdd(result);
      return;
    }
    if (answer.kind === "refused") {
      const detail = answer.detail as Partial<InvoiceAddResult> | null;
      if (detail && detail.outcome === "validation_error")
        refuseAdd(detail as InvoiceAddResult);
      else setOutcome({ kind: "refused", text: refusedText(answer.reason) });
      setStage("edit");
      return;
    }
    if (answer.kind === "unknown")
      undetermined({ what: "add", request }, answer.saved);
    else setOutcome({ kind: "failed", code: answer.code });
  };
  const refuseAdd = (
    result: Pick<InvoiceAddResult, "validation_code" | "invoice_id">,
  ) => {
    setStage("edit");
    if (result.validation_code === "duplicate_invoice") {
      setDuplicate(result.invoice_id ?? "");
      setOutcome(null);
    } else
      setOutcome({
        kind: "refused",
        text: t("desktop.ledger.invoices.invalid"),
      });
  };

  const update = async (request: InvoiceUpdateRequest) => {
    setSending(true);
    const answer = await write(port, "ledger.invoice.update", request);
    setSending(false);
    if (answer.kind === "done") {
      say(
        t("desktop.ledger.invoices.saved", {
          number: seriesAndNumber(answer.result.invoice),
        }),
      );
      onWritten(answer.result.invoice);
      onClose();
    } else if (answer.kind === "refused") {
      setOutcome({ kind: "refused", text: refusedText(answer.reason) });
      setStage("edit");
    } else if (answer.kind === "unknown")
      undetermined({ what: "update", request }, answer.saved);
    else setOutcome({ kind: "failed", code: answer.code });
  };

  const remove = async (invoiceId: string) => {
    setSending(true);
    const answer = await write(port, "ledger.invoice.remove", {
      invoice_id: invoiceId,
    });
    setSending(false);
    if (answer.kind === "done") {
      say(t("desktop.ledger.invoices.removed", { number: numberOf(stored) }));
      onWritten(null, invoiceId);
      onClose();
    } else if (answer.kind === "refused") {
      setOutcome({ kind: "refused", text: refusedText(answer.reason) });
      setStage("edit");
    } else if (answer.kind === "unknown")
      undetermined({ what: "remove", invoiceId }, answer.saved);
    else setOutcome({ kind: "failed", code: answer.code });
  };

  // Checking is the page's one re-read: it settles this write and every
  // other one the page holds.
  const checkPending = () => {
    if (!pause.rereading) pause.reread();
  };

  // ---- What the editor shows ---------------------------------------------------

  const title = isNew
    ? t("desktop.ledger.invoices.new")
    : stored
      ? t("desktop.ledger.invoices.title", { number: seriesAndNumber(stored) })
      : t("desktop.ledger.invoices.gone_title");

  let body: ReactNode;
  if (!isNew && (!stored || !correction))
    body = (
      <Alert tone="warning" icon={<Icon name="alert" />}>
        {t("desktop.ledger.invoices.gone")}
      </Alert>
    );
  else if (isNew)
    body = (
      <NewInvoice
        draft={draft}
        check={check}
        invoices={invoices}
        locale={locale}
        shown={shown}
        touch={touch}
        tried={tried}
        touched={touched}
        edit={edit}
        duplicate={duplicate}
        onOpenInvoice={onOpenInvoice}
      />
    );
  else
    body = (
      <StoredInvoice
        invoice={stored!}
        correction={correction!}
        locale={locale}
        shown={shown}
        touch={touch}
        correct={correct}
      />
    );

  const changed = corrected?.changed ?? [];
  const primary = (): ReactNode => {
    if (unknown) return null;
    if (isNew) {
      if (stage === "confirm" && check.request)
        return (
          <WriteHold>
            <Button
              size="sm"
              pending={sending}
              onClick={() => void add(check.request!)}
            >
              {t("desktop.ledger.invoices.add")}
            </Button>
          </WriteHold>
        );
      return (
        <Button
          size="sm"
          onClick={() => {
            setTried(true);
            if (check.request && duplicate === null) setStage("confirm");
          }}
        >
          {t("desktop.ledger.invoices.review")}
        </Button>
      );
    }
    if (!stored || !corrected) return null;
    if (stage === "confirm" && corrected.request)
      return (
        <WriteHold>
          <Button
            size="sm"
            pending={sending}
            onClick={() => void update(corrected.request!)}
          >
            {t("desktop.ledger.invoices.save")}
          </Button>
        </WriteHold>
      );
    if (stage === "remove") return null;
    return (
      <Button
        size="sm"
        aria-disabled={changed.length === 0 ? true : undefined}
        onClick={() => {
          if (changed.length === 0) return;
          setTried(true);
          if (corrected.request) setStage("confirm");
        }}
      >
        {t("desktop.ledger.invoices.review_changes", { count: changed.length })}
      </Button>
    );
  };

  return (
    <Sheet open onOpenChange={(open) => !open && close()}>
      <SheetContent
        closeLabel={t("desktop.ledger.invoices.close")}
        className="ledger-invoice-editor gap-5"
        aria-describedby={undefined}
        // Escape is the sheet's own dismissal, which asks before edits go.
        onEscapeKeyDown={(event) => event.preventDefault()}
        onInteractOutside={(event) => {
          if (sending) event.preventDefault();
        }}
      >
        <SheetHeader>
          <SheetTitle>{title}</SheetTitle>
          <SheetDescription>
            {isNew
              ? t("desktop.ledger.invoices.new_note")
              : stored
                ? t("desktop.ledger.invoices.stored_note", {
                    kind: kindLabel(t, stored.kind),
                    payment: paymentLabel(t, stored.payment_status),
                    count: stored.linked_transaction_ids.length,
                  })
                : null}
          </SheetDescription>
        </SheetHeader>

        {asking && (
          <Alert
            tone="warning"
            role="alertdialog"
            aria-labelledby="ledger-invoice-discard"
            icon={<Icon name="alert" />}
            className="ledger-invoice-discard"
          >
            <AlertTitle id="ledger-invoice-discard">
              {t(
                isNew
                  ? "desktop.ledger.invoices.discard_new"
                  : "desktop.ledger.invoices.discard_changes",
              )}
            </AlertTitle>
            <AlertDescription>
              {t("desktop.ledger.invoices.discard_note")}
            </AlertDescription>
            <div className="mt-1 flex gap-2">
              <Button size="xs" autoFocus onClick={() => setAsking(false)}>
                {t("desktop.ledger.invoices.keep_editing")}
              </Button>
              <Button size="xs" variant="destructive" onClick={onClose}>
                {t("desktop.ledger.invoices.discard")}
              </Button>
            </div>
          </Alert>
        )}

        <OutcomeAlert
          outcome={outcome}
          sending={sending || pause.rereading}
          onCheck={checkPending}
        />

        <div className="flex flex-col gap-6">{body}</div>

        {stage === "confirm" && (
          <Confirmation
            isNew={isNew}
            draftRequest={check.request}
            totals={check.totals}
            stored={stored}
            correction={correction}
            changed={changed}
            locale={locale}
          />
        )}
        {stage === "remove" && stored && (
          <RemoveConfirmation invoice={stored} />
        )}

        <SheetFooter className="border-t border-border pt-3">
          {!isNew && stored && stage !== "remove" && !unknown && (
            <Button
              size="sm"
              variant="ghost"
              className="mr-auto"
              onClick={() => setStage("remove")}
            >
              <Icon name="trash" />
              {t("desktop.ledger.invoices.remove")}
            </Button>
          )}
          {stage === "remove" && stored && (
            <>
              <Button
                size="sm"
                variant="ghost"
                className="mr-auto"
                autoFocus
                onClick={() => setStage("edit")}
              >
                {t("desktop.ledger.invoices.keep_it")}
              </Button>
              {stored.linked_transaction_ids.length === 0 && !unknown && (
                <WriteHold>
                  <Button
                    size="sm"
                    variant="destructive"
                    pending={sending}
                    onClick={() => void remove(stored.invoice_id)}
                  >
                    {t("desktop.ledger.invoices.remove_confirm")}
                  </Button>
                </WriteHold>
              )}
            </>
          )}
          {stage === "confirm" && (
            <Button size="sm" variant="ghost" onClick={() => setStage("edit")}>
              {t("desktop.ledger.invoices.back")}
            </Button>
          )}
          {stage !== "remove" && (
            <Button size="sm" variant="ghost" onClick={close}>
              {t(
                isNew
                  ? "desktop.ledger.invoices.cancel"
                  : "desktop.ledger.invoices.close",
              )}
            </Button>
          )}
          {primary()}
        </SheetFooter>
      </SheetContent>
    </Sheet>
  );
}

const numberOf = (invoice: CatalogueInvoice | null) =>
  invoice ? seriesAndNumber(invoice) : "";

function OutcomeAlert({
  outcome,
  sending,
  onCheck,
}: {
  outcome: Outcome | null;
  sending: boolean;
  onCheck(): void;
}) {
  const t = useStrings();
  if (!outcome) return null;
  if (outcome.kind === "unknown")
    return (
      <Alert
        tone="danger"
        role="alert"
        icon={<Icon name="unknown" />}
        className="ledger-invoice-unknown"
      >
        <AlertTitle>{t("desktop.ledger.invoices.unknown")}</AlertTitle>
        <AlertDescription>
          {t(
            outcome.checked
              ? "desktop.ledger.invoices.unknown_unread"
              : "desktop.ledger.invoices.unknown_note",
          )}
        </AlertDescription>
        <div className="mt-1">
          <Button
            size="xs"
            variant="outline"
            pending={sending}
            onClick={onCheck}
          >
            {t("desktop.ledger.invoices.check")}
          </Button>
        </div>
      </Alert>
    );
  if (outcome.kind === "not_saved")
    return (
      <Alert
        tone="warning"
        icon={<Icon name="alert" />}
        className="ledger-invoice-not-saved"
      >
        {t("desktop.ledger.invoices.not_saved")}
      </Alert>
    );
  return (
    <Alert
      tone="danger"
      role="alert"
      icon={<Icon name="refused" />}
      className="ledger-invoice-refused"
    >
      {outcome.kind === "refused"
        ? outcome.text
        : t("desktop.ledger.invoices.failed", { code: outcome.code })}
    </Alert>
  );
}

// ---- A new invoice -----------------------------------------------------------------

function NewInvoice({
  draft,
  check,
  invoices,
  locale,
  shown,
  touch,
  tried,
  touched,
  edit,
  duplicate,
  onOpenInvoice,
}: {
  draft: InvoiceDraft;
  check: ReturnType<typeof checkDraft>;
  invoices: readonly CatalogueInvoice[];
  locale: string;
  shown(field: string): string | null;
  touch(field: string): void;
  tried: boolean;
  touched: ReadonlySet<string>;
  edit<K extends keyof InvoiceDraft>(key: K, value: InvoiceDraft[K]): void;
  duplicate: string | null;
  onOpenInvoice(invoiceId: string): void;
}) {
  const t = useStrings();
  const text =
    (
      key: keyof InvoiceDraft,
      field: string,
      transform?: (value: string) => string,
    ) =>
    (control: ControlProps) => (
      <Input
        {...control}
        value={draft[key] as string}
        onChange={(event) =>
          edit(
            key,
            (transform
              ? transform(event.target.value)
              : event.target.value) as never,
          )
        }
        onBlur={() => touch(field)}
      />
    );
  const issued = draft.kind === "issued";
  const year = /^\d{4}-\d{2}-\d{2}$/.test(draft.issuedAt.trim())
    ? Number(draft.issuedAt.trim().slice(0, 4))
    : Number(localDay().slice(0, 4));
  const suggestion = suggestNumber(invoices, {
    kind: draft.kind,
    invoiceClass: draft.invoiceClass,
    series: draft.series,
    year,
  });
  const rectificativa = draft.invoiceClass === "RECTIFICATIVA";
  const numberHint =
    suggestion && draft.number.trim() !== suggestion.number ? (
      <span className="flex flex-wrap items-center gap-2">
        {t("desktop.ledger.invoices.next_number", {
          series: suggestion.series,
          number: suggestion.number,
        })}
        <Button
          variant="link"
          size="xs"
          aria-label={t("desktop.ledger.invoices.use_number", {
            number: suggestion.number,
          })}
          onClick={() => {
            edit("number", suggestion.number);
            if (!draft.series.trim()) edit("series", suggestion.series);
          }}
        >
          {t("desktop.ledger.invoices.use")}
        </Button>
      </span>
    ) : issued && rectificativa && !draft.series.trim() ? (
      t("desktop.ledger.invoices.next_number_series")
    ) : undefined;
  const numberError =
    duplicate !== null
      ? t("desktop.ledger.invoices.duplicate")
      : shown("invoice_number");
  const base = check.totals.base;
  const retentionAmount = shownRetentionAmount(draft, base);
  const lineShown = (key: string, field: string) =>
    tried ||
    (touched.has(`line:${key}:${field}`) &&
      check.problems[`line:${key}:${field}`]?.kind === "grammar");

  return (
    <>
      <div
        role="group"
        aria-labelledby="ledger-invoice-kind"
        className="flex flex-col gap-1.5"
      >
        <span
          id="ledger-invoice-kind"
          className="text-sm font-medium text-muted-foreground"
        >
          {t("desktop.ledger.invoices.this_is")}
        </span>
        <SegmentedControl
          aria-labelledby="ledger-invoice-kind"
          aria-required
          aria-invalid={shown("kind") ? true : undefined}
          aria-describedby={
            shown("kind") ? "ledger-invoice-kind-error" : undefined
          }
          value={draft.kind ?? ""}
          onValueChange={(value) => edit("kind", value as InvoiceKind)}
          className="ledger-invoice-kind max-w-md"
        >
          {(["issued", "received"] as const).map((kind) => (
            <SegmentedControlItem key={kind} value={kind}>
              {kindChoice(t, kind)}
            </SegmentedControlItem>
          ))}
        </SegmentedControl>
        {shown("kind") && (
          <p
            id="ledger-invoice-kind-error"
            role="alert"
            className="flex items-start gap-1.5 text-sm text-destructive"
          >
            <Icon name="alert" size="xs" className="mt-0.5" />
            {shown("kind")}
          </p>
        )}
      </div>

      <Invariants held={check.invariants} />

      <EditorSection title={t("desktop.ledger.invoices.party")}>
        <div className="grid grid-cols-2 gap-3">
          <FormField
            label={t("desktop.ledger.invoices.field.counterparty_name")}
            required
            error={shown("counterparty_name")}
            className="col-span-2"
          >
            {text("counterpartyName", "counterparty_name")}
          </FormField>
          <FormField
            label={t("desktop.ledger.invoices.field.counterparty_tax_id")}
            hint={
              issued && draft.invoiceClass === "SIMPLIFICADA"
                ? t("desktop.ledger.invoices.hint.tax_id_optional")
                : undefined
            }
            error={shown("counterparty_tax_id")}
          >
            {(control) => (
              <Input
                {...control}
                className="font-mono"
                value={draft.taxId}
                onChange={(event) => edit("taxId", event.target.value)}
                onBlur={() => touch("counterparty_tax_id")}
              />
            )}
          </FormField>
          <FormField
            label={t("desktop.ledger.invoices.field.counterparty_country")}
            hint={t("desktop.ledger.invoices.hint.country")}
            required
            error={shown("counterparty_country")}
          >
            {text("country", "counterparty_country", (value) =>
              value.toUpperCase(),
            )}
          </FormField>
        </div>
      </EditorSection>

      <EditorSection title={t("desktop.ledger.invoices.document")}>
        <div className="grid grid-cols-2 gap-3">
          <FormField label={t("desktop.ledger.invoices.field.invoice_class")}>
            {(control) => (
              <NativeSelect
                {...control}
                value={draft.invoiceClass}
                onChange={(event) =>
                  edit(
                    "invoiceClass",
                    event.target.value as InvoiceDraft["invoiceClass"],
                  )
                }
              >
                {INVOICE_CLASSES.map((token) => (
                  <option key={token} value={token}>
                    {classLabel(t, token)}
                  </option>
                ))}
              </NativeSelect>
            )}
          </FormField>
          <FormField
            label={t("desktop.ledger.invoices.field.series")}
            required={rectificativa}
            error={shown("series")}
          >
            {text("series", "series")}
          </FormField>
          <FormField
            label={t("desktop.ledger.invoices.field.invoice_number")}
            required
            hint={numberHint}
            error={numberError}
          >
            {text("number", "invoice_number")}
          </FormField>
          <FormField
            label={t("desktop.ledger.invoices.field.issued_at")}
            hint={t("desktop.ledger.invoices.hint.date")}
            required
            error={shown("issued_at")}
          >
            {text("issuedAt", "issued_at")}
          </FormField>
          <FormField
            label={t("desktop.ledger.invoices.field.operation_date")}
            hint={t("desktop.ledger.invoices.hint.operation_date")}
            error={shown("operation_date")}
          >
            {text("operationDate", "operation_date")}
          </FormField>
          <FormField
            label={t("desktop.ledger.invoices.field.currency")}
            hint={t("desktop.ledger.invoices.hint.currency")}
            required
            error={shown("currency")}
          >
            {text("currency", "currency", (value) => value.toUpperCase())}
          </FormField>
          {rectificativa && (
            <FormField
              label={t(
                "desktop.ledger.invoices.field.rectifies_invoice_number",
              )}
              required
              error={shown("rectifies_invoice_number")}
            >
              {text("rectifies", "rectifies_invoice_number")}
            </FormField>
          )}
          <IvaCategoryField
            value={draft.ivaCategory}
            onChange={(value) => edit("ivaCategory", value)}
            unset={t("desktop.ledger.invoices.from_lines")}
          />
          <OperationTypeField
            value={draft.operationType}
            onChange={(value) => edit("operationType", value)}
          />
        </div>
        {duplicate && (
          <div>
            <Button
              variant="link"
              size="xs"
              onClick={() => onOpenInvoice(duplicate)}
            >
              {t("desktop.ledger.invoices.open_duplicate")}
            </Button>
          </div>
        )}
      </EditorSection>

      <EditorSection title={t("desktop.ledger.invoices.lines")}>
        {shown("lines") && (
          <p
            role="alert"
            className="flex items-start gap-1.5 text-sm text-destructive"
          >
            <Icon name="alert" size="xs" className="mt-0.5" />
            {shown("lines")}
          </p>
        )}
        <DraftLines
          lines={draft.lines}
          figures={check.lines}
          kind={draft.kind}
          locale={locale}
          problems={check.problems}
          shown={lineShown}
          onChange={(key, field, value) => {
            edit(
              "lines",
              draft.lines.map((line) =>
                line.key === key ? { ...line, [field]: value } : line,
              ),
            );
          }}
          onAdd={() =>
            edit("lines", [...draft.lines, emptyLine(nextLineKey())])
          }
          onRemove={(key) =>
            edit(
              "lines",
              draft.lines.filter((line) => line.key !== key),
            )
          }
        />
        <p className="text-xs text-muted-foreground">
          {t("desktop.ledger.invoices.lines_note")}
        </p>
      </EditorSection>

      <EditorSection title={t("desktop.ledger.invoices.totals")}>
        <div className="grid grid-cols-2 gap-3">
          <div className="flex flex-col gap-3 rounded-lg bg-accent p-3">
            <TotalsList
              locale={locale}
              currency={draft.currency.trim().toUpperCase()}
              base={check.totals.base}
              iva={check.totals.iva}
              total={check.totals.total}
              recargo={
                <FormField
                  label={t("desktop.ledger.invoices.field.recargo")}
                  error={shown("recargo")}
                >
                  {(control) => (
                    <Input
                      {...control}
                      controlSize="sm"
                      inputMode="decimal"
                      className="text-end tabular-nums"
                      value={draft.recargo}
                      onChange={(event) => edit("recargo", event.target.value)}
                      onBlur={() => touch("recargo")}
                    />
                  )}
                </FormField>
              }
            />
            <FormField
              label={t("desktop.ledger.invoices.field.printed_total")}
              hint={t("desktop.ledger.invoices.hint.printed_total")}
              error={shown("printed")}
            >
              {(control) => (
                <Input
                  {...control}
                  controlSize="sm"
                  inputMode="decimal"
                  className="text-end tabular-nums"
                  value={draft.printedTotal}
                  onChange={(event) => edit("printedTotal", event.target.value)}
                  onBlur={() => touch("printed")}
                />
              )}
            </FormField>
          </div>
          <Retention
            locale={locale}
            rate={draft.retentionRate}
            amount={retentionAmount}
            total={check.totals.total}
            rateError={shown("retention_rate")}
            amountError={shown("retention_amount")}
            onRate={(value) => {
              edit("retentionRate", value);
              edit("retentionTouched", false);
            }}
            onAmount={(value) => {
              edit("retentionAmount", value);
              edit("retentionTouched", true);
            }}
            onBlur={touch}
          />
        </div>
      </EditorSection>

      {issued && (
        <EditorSection title={t("desktop.ledger.invoices.lease")}>
          <label className="flex items-center gap-2 text-base">
            <Checkbox
              checked={draft.lease}
              onChange={(event) => edit("lease", event.target.checked)}
            />
            {t("desktop.ledger.invoices.field.lease")}
          </label>
          {draft.lease && (
            <div className="grid grid-cols-2 gap-3">
              <FormField label={t("desktop.ledger.invoices.field.situacion")}>
                {(control) => (
                  <NativeSelect
                    {...control}
                    value={draft.situacion}
                    onChange={(event) => edit("situacion", event.target.value)}
                  >
                    <option value="">
                      {t("desktop.ledger.invoices.not_stated")}
                    </option>
                    {PREMISES_SITUATIONS.map((code) => (
                      <option key={code} value={code}>
                        {t(`desktop.ledger.invoices.situacion.s${code}`)}
                      </option>
                    ))}
                  </NativeSelect>
                )}
              </FormField>
              <FormField
                label={t("desktop.ledger.invoices.field.referencia")}
                error={shown("referencia")}
              >
                {(control) => (
                  <Input
                    {...control}
                    className="font-mono"
                    maxLength={25}
                    value={draft.referencia}
                    onChange={(event) => edit("referencia", event.target.value)}
                    onBlur={() => touch("referencia")}
                  />
                )}
              </FormField>
            </div>
          )}
        </EditorSection>
      )}

      <NotesField
        value={draft.notes}
        onChange={(value) => edit("notes", value)}
      />
    </>
  );
}

/** The four requirements of every new invoice, each ticked once met. */
function Invariants({ held }: { held: Record<string, boolean> }) {
  const t = useStrings();
  return (
    <ul
      className="ledger-invoice-invariants flex flex-wrap gap-x-4 gap-y-1 text-sm"
      aria-label={t("desktop.ledger.invoices.needs")}
    >
      {CREATION_INVARIANTS.map((invariant) => {
        const met = held[invariant] === true;
        return (
          <li
            key={invariant}
            data-invariant={invariant}
            data-met={met || undefined}
            className={cn(
              "flex items-center gap-1.5",
              met ? "text-foreground" : "text-muted-foreground",
            )}
          >
            <Icon
              name={met ? "tick" : "pending"}
              size="xs"
              className={met ? "text-success" : undefined}
            />
            {t(`desktop.ledger.invoices.invariant.${invariant}`)}
            <span className="sr-only">
              {t(
                met
                  ? "desktop.ledger.invoices.met"
                  : "desktop.ledger.invoices.not_met",
              )}
            </span>
          </li>
        );
      })}
    </ul>
  );
}

function TotalsList({
  locale,
  currency,
  base,
  iva,
  total,
  recargo,
}: {
  locale: string;
  currency: string;
  base: string;
  iva: string;
  total: string;
  recargo: ReactNode;
}) {
  const t = useStrings();
  const row = "flex items-baseline justify-between gap-3";
  return (
    <div className="ledger-invoice-totals flex flex-col gap-2 text-base">
      <dl className="flex flex-col gap-2">
        <div className={row}>
          <dt className="text-muted-foreground">
            {t("desktop.ledger.invoices.base")}
          </dt>
          <dd className="tabular-nums">{figureText(locale, base)}</dd>
        </div>
        <div className={row}>
          <dt className="text-muted-foreground">
            {t("desktop.ledger.invoices.iva")}
          </dt>
          <dd className="tabular-nums">{figureText(locale, iva)}</dd>
        </div>
      </dl>
      {recargo}
      <dl>
        <div className={cn(row, "border-t border-border pt-2 font-medium")}>
          <dt>{t("desktop.ledger.invoices.total")}</dt>
          <dd className="ledger-invoice-total tabular-nums">
            {figureText(locale, total)} {currency}
          </dd>
        </div>
      </dl>
    </div>
  );
}

/** Retención, outside the total: worked out from its rate and editable,
 * with what is left to be paid. */
function Retention({
  locale,
  rate,
  amount,
  total,
  rateError,
  amountError,
  onRate,
  onAmount,
  onBlur,
}: {
  locale: string;
  rate: string;
  amount: string;
  total: string;
  rateError: string | null;
  amountError: string | null;
  onRate(value: string): void;
  onAmount(value: string): void;
  onBlur(field: string): void;
}) {
  const t = useStrings();
  const withheld = /^\d+(\.\d+)?$/.test(amount.trim()) ? amount.trim() : null;
  const left = withheld === null ? total : lessDecimal(total, withheld);
  return (
    <div className="ledger-invoice-retention flex flex-col gap-3 rounded-lg bg-accent p-3">
      <span className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
        {t("desktop.ledger.invoices.retention")}
      </span>
      <div
        role="group"
        aria-label={t("desktop.ledger.invoices.retention_presets")}
        className="flex flex-wrap gap-1"
      >
        {RETENTION_PRESETS.map((preset) => (
          <Button
            key={preset}
            variant="pill"
            size="xs"
            aria-pressed={rate.trim() === preset}
            onClick={() => onRate(preset)}
          >
            {`${preset}%`}
          </Button>
        ))}
      </div>
      <div className="grid grid-cols-2 gap-2">
        <FormField
          label={t("desktop.ledger.invoices.field.retention_rate")}
          hint={t("desktop.ledger.invoices.hint.percent")}
          error={rateError}
        >
          {(control) => (
            <Input
              {...control}
              controlSize="sm"
              inputMode="decimal"
              value={rate}
              onChange={(event) => onRate(event.target.value)}
              onBlur={() => onBlur("retention_rate")}
            />
          )}
        </FormField>
        <FormField
          label={t("desktop.ledger.invoices.field.retention_amount")}
          error={amountError}
        >
          {(control) => (
            <Input
              {...control}
              controlSize="sm"
              inputMode="decimal"
              className="text-end tabular-nums"
              value={amount}
              onChange={(event) => onAmount(event.target.value)}
              onBlur={() => onBlur("retention_amount")}
            />
          )}
        </FormField>
      </div>
      <p className="ledger-invoice-to-pay text-sm tabular-nums">
        {withheld !== null && left !== null
          ? t("desktop.ledger.invoices.to_pay_withheld", {
              amount: figureText(locale, left),
              retention: figureText(locale, withheld),
            })
          : t("desktop.ledger.invoices.to_pay", {
              amount: figureText(locale, total),
            })}
      </p>
    </div>
  );
}

function IvaCategoryField({
  value,
  onChange,
  unset,
}: {
  value: string;
  onChange(value: string): void;
  unset: string;
}) {
  const t = useStrings();
  return (
    <FormField label={t("desktop.ledger.invoices.field.iva_category")}>
      {(control) => (
        <NativeSelect
          {...control}
          value={value}
          onChange={(event) => onChange(event.target.value)}
        >
          <option value="">{unset}</option>
          {IVA_CATEGORIES.map((category) => (
            <option key={category} value={category}>
              {ivaCategoryLabel(t, category)}
            </option>
          ))}
        </NativeSelect>
      )}
    </FormField>
  );
}

function OperationTypeField({
  value,
  onChange,
}: {
  value: string;
  onChange(value: string): void;
}) {
  const t = useStrings();
  return (
    <FormField label={t("desktop.ledger.invoices.field.operation_type")}>
      {(control) => (
        <NativeSelect
          {...control}
          value={value}
          onChange={(event) => onChange(event.target.value)}
        >
          <option value="">{t("desktop.ledger.invoices.none")}</option>
          {OPERATION_TYPES.map((key) => (
            <option key={key} value={key}>
              {t("desktop.ledger.invoices.operation_key", { key })}
            </option>
          ))}
        </NativeSelect>
      )}
    </FormField>
  );
}

function NotesField({
  value,
  onChange,
}: {
  value: string;
  onChange(value: string): void;
}) {
  const t = useStrings();
  return (
    <FormField label={t("desktop.ledger.invoices.field.notes")}>
      {(control) => (
        <textarea
          {...control}
          rows={3}
          className="w-full min-w-0 rounded-md border border-input bg-card px-2.5 py-1.5 text-base text-foreground transition-colors"
          value={value}
          onChange={(event) => onChange(event.target.value)}
        />
      )}
    </FormField>
  );
}

// ---- A stored invoice --------------------------------------------------------------

function StoredInvoice({
  invoice,
  correction,
  locale,
  shown,
  touch,
  correct,
}: {
  invoice: CatalogueInvoice;
  correction: CorrectionDraft;
  locale: string;
  shown(field: string): string | null;
  touch(field: string): void;
  correct<K extends keyof CorrectionDraft>(
    key: K,
    value: CorrectionDraft[K],
  ): void;
}) {
  const t = useStrings();
  const fixed = t("desktop.ledger.invoices.fixed");
  const text =
    (
      key: keyof CorrectionDraft,
      field: string,
      transform?: (value: string) => string,
    ) =>
    (control: ControlProps) => (
      <Input
        {...control}
        value={correction[key] as string}
        onChange={(event) =>
          correct(
            key,
            (transform
              ? transform(event.target.value)
              : event.target.value) as never,
          )
        }
        onBlur={() => touch(field)}
      />
    );
  const rectificativa = correction.invoiceClass === "RECTIFICATIVA";
  const amount = shownRetentionAmount(correction, invoice.base_total.decimal);
  return (
    <>
      <Alert icon={<Icon name="lock" />} className="ledger-invoice-identity">
        {t("desktop.ledger.invoices.identity_fixed")}
      </Alert>

      <EditorSection title={t("desktop.ledger.invoices.party")}>
        <div className="grid grid-cols-2 gap-3">
          <FixedField
            label={t("desktop.ledger.invoices.field.kind")}
            value={kindChoice(t, invoice.kind)}
            reason={fixed}
          />
          <FormField
            label={t("desktop.ledger.invoices.field.counterparty_name")}
            required
            error={shown("counterparty_name")}
          >
            {text("counterpartyName", "counterparty_name")}
          </FormField>
          <FixedField
            label={t("desktop.ledger.invoices.field.counterparty_tax_id")}
            value={
              invoice.counterparty_tax_id ?? t("desktop.ledger.invoices.none")
            }
            reason={fixed}
            mono
          />
          <FormField
            label={t("desktop.ledger.invoices.field.counterparty_country")}
            hint={t("desktop.ledger.invoices.hint.country")}
            required
            error={shown("counterparty_country")}
          >
            {text("country", "counterparty_country", (value) =>
              value.toUpperCase(),
            )}
          </FormField>
        </div>
      </EditorSection>

      <EditorSection title={t("desktop.ledger.invoices.document")}>
        <div className="grid grid-cols-2 gap-3">
          <FormField label={t("desktop.ledger.invoices.field.invoice_class")}>
            {(control) => (
              <NativeSelect
                {...control}
                value={correction.invoiceClass}
                onChange={(event) =>
                  correct("invoiceClass", event.target.value)
                }
              >
                {INVOICE_CLASSES.map((token) => (
                  <option key={token} value={token}>
                    {classLabel(t, token)}
                  </option>
                ))}
              </NativeSelect>
            )}
          </FormField>
          <FormField
            label={t("desktop.ledger.invoices.field.series")}
            required={rectificativa}
            error={shown("series")}
          >
            {text("series", "series")}
          </FormField>
          <FixedField
            label={t("desktop.ledger.invoices.field.invoice_number")}
            value={invoice.invoice_number}
            reason={fixed}
          />
          <FixedField
            label={t("desktop.ledger.invoices.field.issued_at")}
            value={dayText(locale, invoice.issued_at)}
            reason={fixed}
          />
          {invoice.operation_date === null ? (
            <FixedField
              label={t("desktop.ledger.invoices.field.operation_date")}
              value={t("desktop.ledger.invoices.none")}
              reason={t("desktop.ledger.invoices.operation_date_fixed")}
            />
          ) : (
            <FormField
              label={t("desktop.ledger.invoices.field.operation_date")}
              hint={t("desktop.ledger.invoices.hint.date")}
              error={shown("operation_date")}
            >
              {text("operationDate", "operation_date")}
            </FormField>
          )}
          <FixedField
            label={t("desktop.ledger.invoices.field.currency")}
            value={invoice.currency}
            reason={fixed}
          />
          {rectificativa && (
            <FormField
              label={t(
                "desktop.ledger.invoices.field.rectifies_invoice_number",
              )}
              required
              error={shown("rectifies_invoice_number")}
            >
              {text("rectifies", "rectifies_invoice_number")}
            </FormField>
          )}
          <IvaCategoryField
            value={correction.ivaCategory}
            onChange={(value) => correct("ivaCategory", value)}
            unset={t("desktop.ledger.invoices.none")}
          />
          <OperationTypeField
            value={correction.operationType}
            onChange={(value) => correct("operationType", value)}
          />
        </div>
      </EditorSection>

      <EditorSection
        title={t("desktop.ledger.invoices.lines")}
        aside={
          <span className="flex items-center gap-1 text-xs text-muted-foreground">
            <Icon name="lock" size="xs" />
            {t("desktop.ledger.invoices.lines_fixed")}
          </span>
        }
      >
        <StoredLines
          lines={invoice.lines}
          kind={invoice.kind}
          locale={locale}
        />
      </EditorSection>

      <EditorSection title={t("desktop.ledger.invoices.totals")}>
        <div className="grid grid-cols-2 gap-3">
          <div className="rounded-lg bg-accent p-3">
            <TotalsList
              locale={locale}
              currency={invoice.currency}
              base={invoice.base_total.decimal}
              iva={invoice.iva_total.decimal}
              total={invoice.grand_total.decimal}
              recargo={
                invoice.recargo_amount ? (
                  <div className="flex items-baseline justify-between gap-3">
                    <span className="text-muted-foreground">
                      {t("desktop.ledger.invoices.field.recargo")}
                    </span>
                    <span className="tabular-nums">
                      {figureText(locale, invoice.recargo_amount.decimal)}
                    </span>
                  </div>
                ) : null
              }
            />
          </div>
          <Retention
            locale={locale}
            rate={correction.retentionRate}
            amount={amount}
            total={invoice.grand_total.decimal}
            rateError={shown("retention_rate")}
            amountError={shown("retention_amount")}
            onRate={(value) => {
              correct("retentionRate", value);
              correct("retentionTouched", false);
            }}
            onAmount={(value) => {
              correct("retentionAmount", value);
              correct("retentionTouched", true);
            }}
            onBlur={touch}
          />
        </div>
      </EditorSection>

      <EditorSection title={t("desktop.ledger.invoices.payment_section")}>
        <div className="grid grid-cols-2 gap-3">
          <FormField label={t("desktop.ledger.invoices.field.payment_status")}>
            {(control) => (
              <NativeSelect
                {...control}
                value={correction.paymentStatus}
                onChange={(event) =>
                  correct("paymentStatus", event.target.value as PaymentStatus)
                }
              >
                {PAYMENT_STATUSES.map((status) => (
                  <option key={status} value={status}>
                    {paymentLabel(t, status)}
                  </option>
                ))}
              </NativeSelect>
            )}
          </FormField>
          <FormField
            label={t("desktop.ledger.invoices.field.payment_id")}
            hint={t("desktop.ledger.invoices.hint.payment_id")}
            error={shown("payment_id")}
          >
            {(control) => (
              <Input
                {...control}
                className="font-mono"
                value={correction.paymentId}
                onChange={(event) => correct("paymentId", event.target.value)}
                onBlur={() => touch("payment_id")}
              />
            )}
          </FormField>
        </div>
      </EditorSection>

      <NotesField
        value={correction.notes}
        onChange={(value) => correct("notes", value)}
      />

      <EditorSection title={t("desktop.ledger.invoices.linked")}>
        <p className="flex items-center gap-1.5 text-base">
          <Icon name="link" size="xs" />
          {t("desktop.ledger.invoices.linked_count", {
            count: invoice.linked_transaction_ids.length,
          })}
        </p>
        <p className="text-xs text-muted-foreground">
          {t("desktop.ledger.invoices.links_permanent")}
        </p>
      </EditorSection>
    </>
  );
}

// ---- Confirmations ----------------------------------------------------------------

const FIELD_LABELS: Record<InvoiceUpdateField, string> = {
  counterparty_name: "counterparty_name",
  counterparty_country: "counterparty_country",
  notes: "notes",
  payment_status: "payment_status",
  iva_category: "iva_category",
  operation_type: "operation_type",
  operation_date: "operation_date",
  retention_rate: "retention_rate",
  retention_amount: "retention_amount",
  series: "series",
  invoice_class: "invoice_class",
  rectifies_invoice_number: "rectifies_invoice_number",
  payment_id: "payment_id",
};

function Confirmation({
  isNew,
  draftRequest,
  totals,
  stored,
  correction,
  changed,
  locale,
}: {
  isNew: boolean;
  draftRequest: InvoiceAddRequest | null;
  totals: { total: string };
  stored: CatalogueInvoice | null;
  correction: CorrectionDraft | null;
  changed: readonly InvoiceUpdateField[];
  locale: string;
}) {
  const t = useStrings();
  if (isNew && draftRequest)
    return (
      <Alert icon={<Icon name="info" />} className="ledger-invoice-confirm">
        <AlertTitle>
          {[
            kindLabel(t, draftRequest.kind),
            draftRequest.invoice_number,
            dayText(locale, draftRequest.issued_at),
            draftRequest.counterparty_name,
            amountText(locale, totals.total, draftRequest.currency),
          ].join(" · ")}
        </AlertTitle>
        <AlertDescription>
          {t("desktop.ledger.invoices.confirm_new")}
        </AlertDescription>
      </Alert>
    );
  if (!stored || !correction) return null;
  const before = correctionOf(stored);
  const value = (draft: CorrectionDraft, field: InvoiceUpdateField): string => {
    switch (field) {
      case "counterparty_name":
        return draft.counterpartyName;
      case "counterparty_country":
        return draft.country.toUpperCase();
      case "notes":
        return draft.notes;
      case "payment_status":
        return paymentLabel(t, draft.paymentStatus);
      case "iva_category":
        return draft.ivaCategory ? ivaCategoryLabel(t, draft.ivaCategory) : "";
      case "operation_type":
        return draft.operationType;
      case "operation_date":
        return draft.operationDate ? dayText(locale, draft.operationDate) : "";
      case "retention_rate":
        return draft.retentionRate ? `${draft.retentionRate}%` : "";
      case "retention_amount":
        return shownRetentionAmount(draft, stored.base_total.decimal);
      case "series":
        return draft.series;
      case "invoice_class":
        return classLabel(t, draft.invoiceClass);
      case "rectifies_invoice_number":
        return draft.invoiceClass === "RECTIFICATIVA" ? draft.rectifies : "";
      case "payment_id":
        return draft.paymentId;
    }
  };
  const blank = t("desktop.ledger.invoices.none");
  return (
    <Alert icon={<Icon name="info" />} className="ledger-invoice-confirm">
      <AlertTitle>
        {t("desktop.ledger.invoices.confirm_changes", {
          count: changed.length,
        })}
      </AlertTitle>
      <ul className="flex flex-col gap-0.5 text-sm">
        {changed.map((field) => (
          <li key={field} data-field={field}>
            <span className="font-medium">
              {t(`desktop.ledger.invoices.field.${FIELD_LABELS[field]}`)}
            </span>
            {": "}
            {field === "payment_id" ? null : (
              <>
                <span className="text-muted-foreground">
                  {value(before, field) || blank}
                </span>
                {" → "}
              </>
            )}
            <span>{value(correction, field) || blank}</span>
          </li>
        ))}
      </ul>
    </Alert>
  );
}

function RemoveConfirmation({ invoice }: { invoice: CatalogueInvoice }) {
  const t = useStrings();
  const linked = invoice.linked_transaction_ids.length;
  return linked > 0 ? (
    <Alert
      tone="danger"
      role="alert"
      icon={<Icon name="lock" />}
      className="ledger-invoice-remove"
    >
      <AlertTitle>{t("desktop.ledger.invoices.remove_linked")}</AlertTitle>
      <AlertDescription>
        {t("desktop.ledger.invoices.remove_linked_note", { count: linked })}
      </AlertDescription>
    </Alert>
  ) : (
    <Alert
      tone="warning"
      icon={<Icon name="trash" />}
      className="ledger-invoice-remove"
    >
      <AlertTitle>{t("desktop.ledger.invoices.remove_question")}</AlertTitle>
      <AlertDescription>
        {t("desktop.ledger.invoices.remove_note")}
      </AlertDescription>
    </Alert>
  );
}
