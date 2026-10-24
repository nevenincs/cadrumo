import { useId, useMemo, useState } from "react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty";
import {
  Field,
  FieldDescription,
  FieldError,
  FieldLabel,
} from "@/components/ui/field";
import { Icon } from "@/components/ui/icon";
import { Input } from "@/components/ui/input";
import {
  SegmentedControl,
  SegmentedControlItem,
} from "@/components/ui/segmented-control";
import { Spinner } from "@/components/ui/spinner";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import type {
  CatalogueInvoice,
  ConfirmationBlocker,
  EvidenceConfirmResult,
  EvidenceDraft,
  EvidenceRecord,
  InvoiceKind,
  LedgerPort,
  LedgerRow,
} from "../../../shell/ledger";
import type { StageEvent, StageState } from "../../../shell/ledgerStage";
import { readAnswer } from "../../../shell/ledgerWindow";
import { useNavigationGuard } from "../../../shell/navigation/hooks";
import { provisionActionOf } from "../../../shell/provisioningRecovery";
import { useStrings, type Translate } from "../../../shell/strings";
import { SetupOffer } from "../../setup/SetupOffer";
import { seriesAndNumber } from "../invoices/invoiceModel";
import { figureText, kindChoice, problemText } from "../invoices/invoiceWords";
import { write } from "../invoices/invoiceWrites";
import { failureCode } from "../ledgerWords";
import { useWritePause, WriteHold } from "../WritePause";
import { reconcile, stageLink, stagedLinks } from "../matching/matchingModel";
import { invoiceLine } from "../matching/matchingWords";
import { dayText } from "../transfer/transferWords";
import {
  confirmation,
  countryAdmitted,
  duplicateOf,
  provenanceOf,
  readCorrection,
  readValue,
  readingFieldOf,
  readingRows,
  referenceFields,
  resolutionOf,
  sameAsRead,
  sameReading,
  type CorrectionField,
  type Corrections,
  type DocumentReference,
  type FindingAnswer,
  type ReadingBinding,
  type ReadingField,
} from "./documentsModel";
import {
  doubtful,
  fieldLabel,
  holdText,
  provenanceText,
  reasonLabel,
} from "./documentWords";
import { OffHostDialog } from "./OffHostDialog";
import { useLedgerRead } from "./useLedgerRead";

const KINDS: readonly InvoiceKind[] = ["received", "issued"];

/** A value as the reading table shows it: rates as percentages. */
function shownValue(locale: string, field: ReadingField, value: string | null) {
  if (value === null) return null;
  if (field === "iva_rate" || field === "retencion_rate") return `${value}%`;
  if (
    field === "taxable_base" ||
    field === "iva_amount" ||
    field === "recargo_amount" ||
    field === "retencion_amount" ||
    field === "grand_total"
  )
    return figureText(locale, value);
  return value;
}

/**
 * Where a value came from, as a glyph: its words are the tooltip and what a
 * screen reader hears, so the column stays one glyph wide.
 */
function Provenance({
  t,
  draft,
  field,
  edited,
}: {
  t: Translate;
  draft: EvidenceDraft;
  field: ReadingField;
  edited: boolean;
}) {
  const found = edited ? null : provenanceOf(draft, field);
  const [glyph, words] = edited
    ? [
        <Icon key="edited" name="edit" size="xs" />,
        t("desktop.ledger.documents.entered_by_you"),
      ]
    : found
      ? [
          doubtful(found) ? (
            <Icon key="doubt" name="alert" size="xs" className="text-warning" />
          ) : (
            <Icon
              key="read"
              name="tick"
              size="xs"
              className="text-muted-foreground"
            />
          ),
          provenanceText(t, found),
        ]
      : readValue(draft, field) === null
        ? [
            <Icon
              key="unread"
              name="pending"
              size="xs"
              className="text-muted-foreground"
            />,
            t("desktop.ledger.documents.not_read"),
          ]
        : [
            <Icon
              key="unknown"
              name="info"
              size="xs"
              className="text-muted-foreground"
            />,
            t("desktop.ledger.documents.no_provenance"),
          ];
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span className="ledger-provenance inline-flex size-icon-sm items-center justify-center text-sm text-muted-foreground">
          {glyph}
          <span className="sr-only">{words}</span>
        </span>
      </TooltipTrigger>
      <TooltipContent>{words}</TooltipContent>
    </Tooltip>
  );
}

function Finding({
  t,
  blocker,
  answer,
  onAnswer,
}: {
  t: Translate;
  blocker: ConfirmationBlocker;
  answer: FindingAnswer | undefined;
  onAnswer(answer: FindingAnswer): void;
}) {
  const group = useId();
  const answered = resolutionOf(blocker, answer) !== null;
  const candidates = blocker.candidates ?? [];
  const current = answer ?? { action: "attest", value: "", note: "" };
  return (
    <li
      className="ledger-finding grid gap-2 rounded-md bg-muted p-3"
      data-answered={answered || undefined}
    >
      <div className="flex flex-wrap items-center gap-2">
        <Icon
          name={answered ? "check" : "alert"}
          size="sm"
          className={answered ? "text-success" : "text-warning"}
        />
        <span className="font-medium">{reasonLabel(t, blocker.reason)}</span>
        {blocker.field && <Badge>{fieldLabel(t, blocker.field)}</Badge>}
      </div>
      {blocker.detail && <p className="text-sm">{blocker.detail}</p>}
      <SegmentedControl
        aria-label={t("desktop.ledger.documents.answer")}
        value={answer?.action ?? ""}
        onValueChange={(action) =>
          onAnswer({
            action: action as FindingAnswer["action"],
            value: "",
            note: current.note,
          })
        }
        className="ledger-finding-action w-fit"
      >
        <SegmentedControlItem
          value="choose_candidate"
          disabled={candidates.length === 0}
          className="text-sm"
        >
          {t("desktop.ledger.documents.action.choose_candidate")}
        </SegmentedControlItem>
        <SegmentedControlItem value="supply_value" className="text-sm">
          {t("desktop.ledger.documents.action.supply_value")}
        </SegmentedControlItem>
        <SegmentedControlItem value="attest" className="text-sm">
          {t("desktop.ledger.documents.action.attest")}
        </SegmentedControlItem>
      </SegmentedControl>
      {answer?.action === "choose_candidate" && (
        <fieldset className="grid gap-1">
          <legend className="sr-only">
            {t("desktop.ledger.documents.readings")}
          </legend>
          {candidates.map((candidate) => (
            <label
              key={candidate.value}
              className="flex cursor-pointer items-center gap-2 text-sm"
            >
              <input
                type="radio"
                name={group}
                className="size-icon-sm shrink-0 accent-primary"
                checked={answer.value === candidate.value}
                onChange={() => onAnswer({ ...answer, value: candidate.value })}
              />
              <span className="font-mono">{candidate.value}</span>
              {candidate.note && (
                <span className="text-muted-foreground">{candidate.note}</span>
              )}
            </label>
          ))}
        </fieldset>
      )}
      {answer?.action === "supply_value" && (
        <Input
          controlSize="sm"
          className="ledger-finding-value"
          aria-label={t("desktop.ledger.documents.the_value")}
          maxLength={1024}
          value={answer.value}
          onChange={(event) =>
            onAnswer({ ...answer, value: event.target.value })
          }
        />
      )}
      {answer?.action === "attest" && (
        <Input
          controlSize="sm"
          className="ledger-finding-note"
          aria-label={t("desktop.ledger.documents.why_right")}
          placeholder={t("desktop.ledger.documents.why_right")}
          maxLength={2048}
          value={answer.note}
          onChange={(event) =>
            onAnswer({ ...answer, note: event.target.value })
          }
        />
      )}
    </li>
  );
}

type Notice =
  | { kind: "changed" }
  /** `recovery` is the setup action the refusal names, if any. */
  | { kind: "refused"; code: string; recovery: string | null }
  | { kind: "unknown" }
  | { kind: "failed"; code: string }
  | { kind: "checked"; saved: boolean };

/**
 * One reading waiting for review: what was read and where from, the
 * findings to answer, and the confirmation as a catalogue invoice. The
 * confirmation is bound to the source and to the reading shown: the page
 * reads the document again just before, and a reading that changed is
 * shown for review again instead of being confirmed.
 */
export function DraftReview({
  port,
  reader,
  locale,
  evidenceReference,
  reference,
  record,
  fileName,
  invoices,
  rows,
  stage,
  onStage,
  onWritten,
  onConfirmed,
  say,
}: {
  port: LedgerPort;
  reader: string | null;
  locale: string;
  evidenceReference: string;
  reference: DocumentReference;
  record: EvidenceRecord | null;
  fileName: string;
  invoices: CatalogueInvoice[] | null;
  rows: LedgerRow[] | null;
  stage: StageState;
  onStage(event: StageEvent): void;
  /** Something may have been written: the section reads its lists again. */
  onWritten(): void;
  /** The reading was confirmed: it leaves the queue. */
  onConfirmed(reference: string): void;
  say(text: string): void;
}) {
  const t = useStrings();
  const pause = useWritePause();
  const { read, reread } = useLedgerRead(
    port,
    reader,
    true,
    "ledger.evidence.review.view",
    { evidence_reference: evidenceReference },
    evidenceReference,
  );
  const [binding, setBinding] = useState<
    (ReadingBinding & { draft: EvidenceDraft }) | null
  >(null);
  const [kind, setKind] = useState<InvoiceKind | null>(null);
  const [country, setCountry] = useState("");
  const [corrections, setCorrections] = useState<Corrections>({});
  const [answers, setAnswers] = useState<Record<string, FindingAnswer>>({});
  const [anyway, setAnyway] = useState(false);
  const [busy, setBusy] = useState<
    "reading" | "confirming" | "checking" | null
  >(null);
  const [notice, setNotice] = useState<Notice | null>(null);
  const [confirmed, setConfirmed] = useState<EvidenceConfirmResult | null>(
    null,
  );
  const [offHost, setOffHost] = useState(false);
  // Corrections and answers not yet confirmed are asked about before a
  // navigation takes the section down; a read or confirmation in flight
  // holds it.
  useNavigationGuard(
    "ledger/documents",
    busy !== null
      ? "busy"
      : Object.keys(corrections).length > 0 || Object.keys(answers).length > 0
        ? "dirty"
        : "clean",
  );
  const countryId = useId();
  const currencyId = useId();

  const view = read.value;
  const draft = view?.draft ?? null;
  const blockers = view?.blockers ?? [];
  const actions = stage.content.actions;
  const duplicate = useMemo(
    () => (draft ? duplicateOf(draft, kind, corrections, invoices) : null),
    [draft, kind, corrections, invoices],
  );

  /** Reads the document again, here or off this computer, and binds the
   * confirmation to that reading. A reading that differs from the one
   * shown is shown instead, to be reviewed again. */
  async function readAgain(offHostProvider: "AGENT" | null) {
    if (!draft) return null;
    setBusy("reading");
    setNotice(null);
    const sent = await write(port, "ledger.evidence.extract", {
      ...referenceFields(reference),
      ...(offHostProvider
        ? { off_host_provider: offHostProvider, acknowledge_off_host: true }
        : {}),
    });
    setBusy(null);
    if (sent.kind !== "done") {
      setNotice(
        sent.kind === "unknown"
          ? { kind: "unknown" }
          : sent.kind === "refused"
            ? {
                kind: "refused",
                code: sent.reason ?? "refused",
                recovery: provisionActionOf(sent.detail),
              }
            : { kind: "failed", code: sent.code },
      );
      if (sent.kind === "unknown") {
        pause.hold({
          what: t("desktop.ledger.section.documents"),
          outcome: sent.saved ? "saved_unread" : "unknown",
        });
        onWritten();
      }
      return null;
    }
    const result = sent.result;
    const fresh = {
      sourceSha256: result.source_sha256,
      draftReviewSha256: result.draft_review_sha256,
      draft: result.draft,
    };
    setBinding(fresh);
    if (!sameReading(result.draft, draft)) {
      setNotice({ kind: "changed" });
      reread();
      return null;
    }
    return fresh;
  }

  const plan =
    draft && binding
      ? confirmation({
          reference,
          binding,
          draft,
          blockers,
          answers,
          kind,
          country,
          corrections,
          duplicate,
          confirmAnyway: anyway,
        })
      : draft
        ? confirmation({
            reference,
            binding: { sourceSha256: "", draftReviewSha256: "" },
            draft,
            blockers,
            answers,
            kind,
            country,
            corrections,
            duplicate,
            confirmAnyway: anyway,
          })
        : null;
  const holds = plan?.kind === "held" ? plan.holds : [];

  async function confirm() {
    if (!draft || holds.length) return;
    const bound =
      binding && sameReading(binding.draft, draft)
        ? binding
        : await readAgain(null);
    if (!bound) return;
    const ready = confirmation({
      reference,
      binding: bound,
      draft,
      blockers,
      answers,
      kind,
      country,
      corrections,
      duplicate,
      confirmAnyway: anyway,
    });
    if (ready.kind !== "ready") return;
    setBusy("confirming");
    const sent = await write(port, "ledger.evidence.confirm", ready.request);
    setBusy(null);
    if (sent.kind === "done") {
      setConfirmed(sent.result);
      onConfirmed(evidenceReference);
      say(
        t("desktop.ledger.documents.confirmed_toast", {
          number: seriesAndNumber(sent.result.confirmation.invoice),
        }),
      );
      onWritten();
      return;
    }
    if (sent.kind === "unknown") {
      setNotice({ kind: "unknown" });
      pause.hold({
        what: t("desktop.ledger.section.documents"),
        outcome: sent.saved ? "saved_unread" : "unknown",
      });
      return;
    }
    // A refused confirmation wrote nothing; the reading may have changed.
    setNotice(
      sent.kind === "refused"
        ? {
            kind: "refused",
            code: sent.reason ?? "refused",
            recovery: provisionActionOf(sent.detail),
          }
        : { kind: "failed", code: sent.code },
    );
    setBinding(null);
  }

  /** Learns what an unseen outcome came to: a confirmed reading leaves the
   * queue. */
  async function check() {
    setBusy("checking");
    try {
      const answer = readAnswer(
        await port.submit("ledger.evidence.review.list", {}),
      );
      if (answer.kind === "answer") {
        const waiting = (answer.result.rows ?? []).some(
          (row) => row.evidence_reference === evidenceReference,
        );
        setNotice({ kind: "checked", saved: !waiting });
        onWritten();
      }
    } catch {
      // The outcome stays unknown.
    } finally {
      setBusy(null);
    }
  }

  if (confirmed) {
    const invoice = confirmed.confirmation.invoice;
    const staged = stagedLinks(actions);
    const offer =
      rows && invoice.linked_transaction_ids.length === 0
        ? (reconcile(rows, [invoice], actions).list[0] ?? null)
        : null;
    const linkStaged = staged.invoices.get(invoice.invoice_id);
    return (
      <div className="ledger-draft-confirmed grid gap-3 p-3">
        <Alert tone="success" icon={<Icon name="check" />}>
          <AlertTitle>
            {confirmed.confirmation.created
              ? t("desktop.ledger.documents.confirmed", {
                  number: seriesAndNumber(invoice),
                })
              : t("desktop.ledger.documents.already_confirmed", {
                  number: seriesAndNumber(invoice),
                })}
          </AlertTitle>
          <AlertDescription>{invoiceLine(t, locale, invoice)}</AlertDescription>
        </Alert>
        {confirmed.confirmation.total_discrepancy && (
          <Alert tone="warning" icon={<Icon name="alert" />}>
            {t("desktop.ledger.documents.printed_differs", {
              printed: figureText(
                locale,
                confirmed.confirmation.total_discrepancy.printed_total.decimal,
              ),
              recorded: figureText(
                locale,
                confirmed.confirmation.total_discrepancy.recorded_total.decimal,
              ),
            })}
          </Alert>
        )}
        {linkStaged ? (
          <Alert
            icon={<Icon name="lock" />}
            className="ledger-draft-link-staged"
          >
            {t("desktop.ledger.matching.staged_toast")}
          </Alert>
        ) : (
          offer && (
            <Alert
              icon={<Icon name="link" />}
              className="ledger-draft-link-offer"
            >
              <AlertTitle>
                {t("desktop.ledger.documents.link_offer")}
              </AlertTitle>
              <AlertDescription className="grid gap-2">
                <span>
                  {t("desktop.ledger.documents.link_offer_note", {
                    description: offer.row.transaction.description,
                    date: dayText(locale, offer.row.transaction.date),
                    amount: figureText(locale, offer.row.transaction.amount),
                  })}
                </span>
                <span>
                  <Button
                    size="xs"
                    variant="outline"
                    className="ledger-match-link"
                    onClick={() => {
                      onStage(
                        stageLink(
                          offer.row.transaction.transaction_id,
                          invoice.invoice_id,
                        ),
                      );
                      say(t("desktop.ledger.matching.staged_toast"));
                    }}
                  >
                    <Icon name="lock" size="xs" />
                    {t("desktop.ledger.matching.link")}
                  </Button>
                </span>
              </AlertDescription>
            </Alert>
          )
        )}
      </div>
    );
  }

  if (read.phase === "failed")
    return (
      <EmptyState
        className="ledger-draft-failed"
        icon="alert"
        description={
          <span role="alert">
            {t("desktop.ledger.documents.read_failed")}{" "}
            <code className="font-mono text-xs">
              {failureCode(read.failure)}
            </code>
          </span>
        }
      >
        <Button variant="outline" onClick={reread}>
          {t("desktop.ledger.retry")}
        </Button>
      </EmptyState>
    );
  if (!view || !draft)
    return (
      <EmptyState
        className="ledger-draft-loading"
        role="status"
        busy
        description={t("desktop.ledger.loading")}
      />
    );

  const correctable = (field: CorrectionField) => {
    const readField = readingFieldOf(field, kind ?? "received");
    const typed = corrections[field];
    const read = readValue(draft, readField);
    const parsed = typed === undefined ? null : readCorrection(field, typed);
    const edited =
      parsed !== null &&
      !(parsed.kind === "value" && sameAsRead(field, parsed.value, read)) &&
      !(parsed.kind === "empty" && read === null);
    return { readField, typed, read, parsed, edited };
  };
  const suggested = draft.suggested_kind ?? null;
  const readCountry =
    kind === "issued"
      ? (draft.customer_country_code ?? null)
      : kind === "received"
        ? (draft.supplier_country_code ?? null)
        : null;
  const currencyRead = readValue(draft, "currency");
  const attachTarget =
    duplicate && record && reference.kind === "evidence"
      ? (duplicate.linked_transaction_ids[0] ?? null)
      : null;
  const attachId = attachTarget
    ? `attach:${attachTarget}:${reference.id}`
    : null;
  const attachStaged = actions.some((action) => action.id === attachId);
  const open = blockers.filter(
    (blocker) => resolutionOf(blocker, answers[blocker.blocker_id]) === null,
  ).length;

  return (
    <div className="ledger-draft grid gap-4 p-3">
      <div className="flex flex-wrap items-start gap-2">
        <div className="grid min-w-0 flex-1 gap-0.5">
          <h3 className="text-md font-semibold [overflow-wrap:anywhere]">
            {fileName}
          </h3>
          {/* The extractor is an identifier, not words: it is named only on
              hover, beside the day it read the file. */}
          <Tooltip>
            <TooltipTrigger asChild>
              <span className="justify-self-start text-sm text-muted-foreground">
                {dayText(locale, view.drafted_at.slice(0, 10))}
              </span>
            </TooltipTrigger>
            <TooltipContent>
              {t("desktop.ledger.documents.read_by", {
                extractor: view.extractor,
                date: dayText(locale, view.drafted_at.slice(0, 10)),
              })}
            </TooltipContent>
          </Tooltip>
        </div>
        <WriteHold>
          <Button
            size="sm"
            variant="outline"
            className="ledger-draft-reread"
            disabled={busy !== null}
            aria-busy={busy === "reading" || undefined}
            onClick={() => void readAgain(null)}
          >
            {busy === "reading" ? <Spinner /> : <Icon name="sync" />}
            {t("desktop.ledger.documents.read_again")}
          </Button>
        </WriteHold>
        {reference.kind === "evidence" && (
          <Button
            size="sm"
            variant="ghost"
            className="ledger-draft-off-host"
            disabled={busy !== null}
            onClick={() => setOffHost(true)}
          >
            {t("desktop.ledger.documents.read_off_host")}
          </Button>
        )}
      </div>

      {notice?.kind === "changed" && (
        <Alert tone="warning" role="alert" icon={<Icon name="alert" />}>
          {t("desktop.ledger.documents.reading_changed")}
        </Alert>
      )}
      {(notice?.kind === "refused" || notice?.kind === "failed") && (
        <Alert tone="danger" role="alert" icon={<Icon name="refused" />}>
          <AlertTitle>{t("desktop.ledger.documents.not_done")}</AlertTitle>
          <AlertDescription className="flex flex-wrap items-center gap-2">
            <code className="font-mono text-xs">{notice.code}</code>
            {notice.kind === "refused" && (
              <SetupOffer action={notice.recovery} />
            )}
          </AlertDescription>
        </Alert>
      )}
      {notice?.kind === "unknown" && (
        <Alert tone="warning" role="alert" icon={<Icon name="unknown" />}>
          <AlertTitle>{t("desktop.ledger.documents.unknown")}</AlertTitle>
          <AlertDescription className="flex flex-wrap items-center gap-2">
            {t("desktop.ledger.documents.unknown_note")}
            <Button
              size="xs"
              variant="outline"
              className="ledger-draft-check"
              disabled={busy !== null}
              onClick={() => {
                void check();
                if (!pause.rereading) pause.reread();
              }}
            >
              {t("desktop.ledger.documents.check")}
            </Button>
          </AlertDescription>
        </Alert>
      )}
      {notice?.kind === "checked" && (
        <Alert icon={<Icon name="info" />} className="ledger-draft-checked">
          {notice.saved
            ? t("desktop.ledger.documents.checked_saved")
            : t("desktop.ledger.documents.checked_not_saved")}
        </Alert>
      )}
      {view.label_reading_fallback && (
        <Alert
          tone="warning"
          icon={<Icon name="pause" />}
          className="ledger-draft-unread"
        >
          <AlertTitle>{t("desktop.ledger.documents.unread")}</AlertTitle>
          <AlertDescription className="grid gap-2">
            <span>
              {view.label_reading_fallback.unread_fields
                .map((field) => fieldLabel(t, field))
                .join(" · ")}
            </span>
            <SetupOffer
              action={provisionActionOf(view.label_reading_fallback)}
              className="justify-self-start"
            />
          </AlertDescription>
        </Alert>
      )}

      <section aria-labelledby={`${countryId}-read`} className="grid gap-2">
        <h4 id={`${countryId}-read`} className="text-sm font-semibold">
          {t("desktop.ledger.documents.what_was_read")}
        </h4>
        <table className="ledger-draft-fields w-full text-sm">
          <thead className="sr-only">
            <tr>
              <th scope="col">{t("desktop.ledger.documents.column.field")}</th>
              <th scope="col">{t("desktop.ledger.documents.column.source")}</th>
              <th scope="col">{t("desktop.ledger.documents.column.value")}</th>
            </tr>
          </thead>
          <tbody>
            {readingRows(kind).map((row) => {
              if (row.kind === "read") {
                const value = readValue(draft, row.field);
                return (
                  <tr key={row.field} data-field={row.field}>
                    <th
                      scope="row"
                      className="w-1/4 py-1 pr-2 text-left font-normal text-muted-foreground"
                    >
                      {fieldLabel(t, row.field)}
                    </th>
                    <td className="w-6 py-1 pr-2 text-center">
                      <Provenance
                        t={t}
                        draft={draft}
                        field={row.field}
                        edited={false}
                      />
                    </td>
                    <td className="py-1 pr-2 tabular-nums">
                      {shownValue(locale, row.field, value) ?? "—"}
                    </td>
                  </tr>
                );
              }
              const facts = correctable(row.field);
              const refused =
                facts.parsed?.kind === "refused" ? facts.parsed.refusal : null;
              return (
                <tr key={row.field} data-field={row.field}>
                  <th
                    scope="row"
                    className="w-1/4 py-1 pr-2 text-left font-normal text-muted-foreground"
                  >
                    {fieldLabel(t, row.field)}
                  </th>
                  <td className="w-6 py-1 pr-2 text-center">
                    <Provenance
                      t={t}
                      draft={draft}
                      field={facts.readField}
                      edited={facts.edited}
                    />
                  </td>
                  <td className="py-1 pr-2">
                    <Input
                      controlSize="sm"
                      className="ledger-draft-input tabular-nums"
                      aria-label={fieldLabel(t, row.field)}
                      aria-invalid={refused ? true : undefined}
                      maxLength={1024}
                      value={facts.typed ?? facts.read ?? ""}
                      onChange={(event) =>
                        setCorrections((held) => ({
                          ...held,
                          [row.field]: event.target.value,
                        }))
                      }
                    />
                    {refused && (
                      <FieldError>
                        {problemText(t, { kind: "grammar", refusal: refused })}
                      </FieldError>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </section>

      {blockers.length > 0 && (
        <section
          aria-labelledby={`${countryId}-findings`}
          className="grid gap-2"
        >
          <h4
            id={`${countryId}-findings`}
            className="flex items-center gap-2 text-sm font-semibold"
          >
            {t("desktop.ledger.documents.findings")}
            <Badge
              variant={open ? "warning" : "success"}
              aria-label={t("desktop.ledger.documents.findings_open", {
                count: open,
              })}
            >
              {open}
            </Badge>
          </h4>
          <ul className="grid gap-2">
            {blockers.map((blocker) => (
              <Finding
                key={blocker.blocker_id}
                t={t}
                blocker={blocker}
                answer={answers[blocker.blocker_id]}
                onAnswer={(answer) =>
                  setAnswers((held) => ({
                    ...held,
                    [blocker.blocker_id]: answer,
                  }))
                }
              />
            ))}
          </ul>
        </section>
      )}

      <section aria-labelledby={`${countryId}-confirm`} className="grid gap-3">
        <h4 id={`${countryId}-confirm`} className="text-sm font-semibold">
          {t("desktop.ledger.documents.confirm_heading")}
        </h4>
        <Field>
          <FieldLabel id={`${countryId}-kind`}>
            {t("desktop.ledger.documents.this_is")}
          </FieldLabel>
          <SegmentedControl
            aria-labelledby={`${countryId}-kind`}
            value={kind ?? ""}
            onValueChange={(value) => setKind(value as InvoiceKind)}
            className="ledger-draft-kind w-fit"
          >
            {KINDS.map((choice) => (
              <SegmentedControlItem
                key={choice}
                value={choice}
                className="text-sm"
              >
                {kindChoice(t, choice)}
              </SegmentedControlItem>
            ))}
          </SegmentedControl>
          <FieldDescription>
            {suggested
              ? t("desktop.ledger.documents.reads_as", {
                  kind: kindChoice(t, suggested),
                })
              : t("desktop.ledger.documents.no_default")}
          </FieldDescription>
        </Field>
        <div className="flex flex-wrap gap-3">
          <Field className="w-40">
            <FieldLabel htmlFor={countryId}>
              {t("desktop.ledger.documents.country")}
            </FieldLabel>
            <Input
              id={countryId}
              controlSize="sm"
              className="ledger-draft-country uppercase"
              maxLength={2}
              aria-invalid={
                country !== "" && !countryAdmitted(country) ? true : undefined
              }
              value={country}
              onChange={(event) => setCountry(event.target.value.toUpperCase())}
            />
            {readCountry && country !== readCountry && (
              <Button
                size="xs"
                variant="link"
                className="ledger-draft-country-read w-fit"
                onClick={() => setCountry(readCountry)}
              >
                {t("desktop.ledger.documents.as_read", { value: readCountry })}
              </Button>
            )}
          </Field>
          {currencyRead === null && (
            <Field className="w-40">
              <FieldLabel htmlFor={currencyId}>
                {t("desktop.ledger.documents.field.currency")}
              </FieldLabel>
              <Input
                id={currencyId}
                controlSize="sm"
                className="uppercase"
                maxLength={3}
                value={corrections.currency ?? ""}
                onChange={(event) =>
                  setCorrections((held) => ({
                    ...held,
                    currency: event.target.value.toUpperCase(),
                  }))
                }
              />
              <FieldDescription>
                {t("desktop.ledger.documents.currency_not_read")}
              </FieldDescription>
            </Field>
          )}
        </div>
        {duplicate && (
          <Alert
            tone="warning"
            icon={<Icon name="alert" />}
            className="ledger-draft-duplicate"
          >
            <AlertTitle>
              {t("desktop.ledger.documents.duplicate", {
                number: seriesAndNumber(duplicate),
              })}
            </AlertTitle>
            <AlertDescription className="grid gap-2">
              <span>{invoiceLine(t, locale, duplicate)}</span>
              <span className="flex flex-wrap items-center gap-2">
                {attachTarget && record && !attachStaged && (
                  <Button
                    size="xs"
                    className="ledger-draft-attach"
                    onClick={() => {
                      onStage({
                        type: "stage_action",
                        action: {
                          id: attachId!,
                          kind: "attach",
                          transactionId: attachTarget,
                          evidenceId: record.evidence_id,
                          attachmentIds: [record.attachment_id],
                        },
                      });
                      say(t("desktop.ledger.documents.attach_staged"));
                    }}
                  >
                    {t("desktop.ledger.documents.attach_to", {
                      number: seriesAndNumber(duplicate),
                    })}
                  </Button>
                )}
                {attachStaged && (
                  <span className="text-sm">
                    {t("desktop.ledger.documents.attach_staged")}
                  </span>
                )}
                {!attachTarget && (
                  <span className="text-sm">
                    {t("desktop.ledger.documents.no_movement_to_attach")}
                  </span>
                )}
                <Button
                  size="xs"
                  variant="outline"
                  className="ledger-draft-anyway"
                  aria-pressed={anyway}
                  onClick={() => setAnyway(!anyway)}
                >
                  {t("desktop.ledger.documents.confirm_anyway")}
                </Button>
              </span>
            </AlertDescription>
          </Alert>
        )}
        <p className="text-sm text-muted-foreground">
          {t("desktop.ledger.documents.confirm_note")}
        </p>
        <div className="flex flex-wrap items-center gap-2">
          <WriteHold>
            <Button
              className="ledger-draft-confirm"
              aria-disabled={holds.length > 0 || busy !== null || undefined}
              aria-busy={busy === "confirming" || undefined}
              aria-describedby={holds.length ? `${countryId}-holds` : undefined}
              onClick={() => void confirm()}
            >
              {busy === "confirming" && <Spinner />}
              {t("desktop.ledger.documents.confirm")}
            </Button>
          </WriteHold>
          {holds.length > 0 && (
            <span
              id={`${countryId}-holds`}
              className="ledger-draft-holds text-sm text-muted-foreground"
            >
              {holds.map((hold) => holdText(t, hold)).join(" · ")}
            </span>
          )}
        </div>
        <details className="text-xs text-muted-foreground">
          <summary className="cursor-pointer">
            {t("desktop.ledger.documents.technical")}
          </summary>
          <dl className="mt-1 grid grid-cols-[auto_1fr] gap-x-3 font-mono [overflow-wrap:anywhere]">
            <dt>{t("desktop.ledger.documents.source_digest")}</dt>
            <dd>{binding?.sourceSha256 ?? record?.source_sha256 ?? "—"}</dd>
            <dt>{t("desktop.ledger.documents.reading_digest")}</dt>
            <dd>{binding?.draftReviewSha256 ?? "—"}</dd>
          </dl>
        </details>
      </section>
      {offHost && (
        <OffHostDialog
          fileName={fileName}
          onClose={() => setOffHost(false)}
          onSend={() => {
            setOffHost(false);
            void readAgain("AGENT");
          }}
        />
      )}
    </div>
  );
}
