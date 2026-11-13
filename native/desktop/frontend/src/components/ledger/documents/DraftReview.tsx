import {
  useCallback,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { CountryEditor } from "@/components/editors/CountryEditor";
import { useInvoiceDuplicate } from "../../../shell/ledgerInvoiceDuplicate";
import { useInvoiceMatches } from "../../../shell/ledgerInvoiceMatch";
import { CurrencyEditor } from "@/components/editors/CurrencyEditor";
import { TypedField } from "@/components/editors/TypedField";
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
import {
  SegmentedControl,
  SegmentedControlItem,
} from "@/components/ui/segmented-control";
import { Spinner } from "@/components/ui/spinner";
import type { Suggestion } from "@/components/ui/suggestions";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { facts } from "../../../shell/compose";
import {
  servedNextStep,
  servedRefusalWords,
  type LedgerPort,
  type LedgerRow,
} from "../../../shell/ledger";
import type { EvidenceConfirmResult } from "../../../shell/ledgerDocumentOperations";
import type { InvoiceDraftProjectionV1 } from "../../../shell/ledgerDocumentReviewContract";
import type { LedgerEvidenceRecordProjection } from "../../../shell/ledgerDocumentContract";
import type {
  CatalogueInvoiceSnapshot,
  InvoiceKind,
} from "../../../shell/ledgerInvoiceContract";
import type { StageEvent, StageState } from "../../../shell/ledgerStage";
import { readAnswer } from "../../../shell/ledgerWindow";
import { useNavigationGuard } from "../../../shell/navigation/hooks";
import { provisionActionOf } from "../../../shell/provisioningRecovery";
import { useStrings } from "../../../shell/strings";
import { localDay } from "../../../shared/dates";
import { formatDay } from "../../../shared/dateFormats";
import { seriesAndNumber } from "../invoices/invoiceModel";
import { kindChoice, problemText } from "../invoices/invoiceWords";
import { write } from "../invoices/invoiceWrites";
import { landingSettle, useWritePause, WriteHold } from "../WritePause";
import { useFieldSuggestions } from "../suggestions/SuggestionsProvider";
import {
  emptyFills,
  invoiceNumberOptions,
  partySeriesOptions,
  partyNameOptions,
  partyTaxIdOptions,
} from "../suggestions/ledgerSuggestions";
import { stagedLinks } from "../matching/matchingModel";
import {
  CORRECTION_SHAPES,
  DERIVED_FIELDS,
  confirmation,
  countryAdmitted,
  duplicateQuestion,
  entrySpec,
  fieldWidth,
  readCorrection,
  readValue,
  readingFieldOf,
  readingRows,
  referenceFields,
  resolutionOf,
  seeded,
  sameAsRead,
  sameReading,
  type CorrectionField,
  type Corrections,
  type DocumentReference,
  type FindingAnswer,
  type ReadingBinding,
  type ReadingField,
} from "./documentsModel";
import { fieldLabel, holdText } from "./documentWords";
import { confirmationLanding, extractionLanding } from "./documentLanding";
import { DocumentViewer } from "./DocumentViewer";
import { OffHostDialog } from "./OffHostDialog";
import { useLedgerRead } from "./useLedgerRead";
import { ConfirmedReading } from "./ConfirmedReading";
import { DuplicateNotice } from "./DuplicateNotice";
import { Provenance, type Question } from "./ReadingProvenance";
import { ReadingTable, shownReadingValue } from "./ReadingTable";
import { ReviewColumns } from "./ReviewColumns";
import { Finding } from "./ReviewFinding";
import { ReviewNotices, type ReviewNotice } from "./ReviewNotices";

const KINDS: readonly InvoiceKind[] = ["received", "issued"];

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
  onLinkStaged,
  viewerShare,
  onViewerShare,
  say,
}: {
  port: LedgerPort;
  reader: string | null;
  locale: string;
  evidenceReference: string;
  reference: DocumentReference;
  record: LedgerEvidenceRecordProjection | null;
  fileName: string;
  invoices: CatalogueInvoiceSnapshot[] | null;
  rows: LedgerRow[] | null;
  stage: StageState;
  onStage(event: StageEvent): void;
  /** Something may have been written: the section reads its lists again. */
  onWritten(): void;
  /** The reading was confirmed: it leaves the queue. */
  onConfirmed(reference: string): void;
  /** The confirmed invoice's link was staged: the flow moves on to the
   * next document. */
  onLinkStaged(): void;
  /** The viewer's share of the width, in percent. */
  viewerShare: number;
  onViewerShare(share: number): void;
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
    (ReadingBinding & { draft: InvoiceDraftProjectionV1 }) | null
  >(null);
  const [kind, setKind] = useState<InvoiceKind | null>(null);
  const [country, setCountry] = useState("");
  const [corrections, setCorrections] = useState<Corrections>({});
  const [answers, setAnswers] = useState<Record<string, FindingAnswer>>({});
  const [anyway, setAnyway] = useState(false);
  const [busy, setBusy] = useState<
    "reading" | "confirming" | "checking" | null
  >(null);
  const [notice, setNotice] = useState<ReviewNotice | null>(null);
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
  const countries = useFieldSuggestions("country");
  const currencies = useFieldSuggestions("currency");
  const root = useRef<HTMLDivElement>(null);
  const confirmedLink = useCallback((button: HTMLButtonElement | null) => {
    // A match may arrive after confirmation. Follow it only while the
    // person remains at this result; a late read must not take focus back.
    if (button && document.activeElement === root.current) button.focus();
  }, []);
  // After a confirmation the next step is its link, when one is offered;
  // otherwise the confirmation itself, so the focus is never left behind
  // on the button that went away.
  useEffect(() => {
    if (!confirmed) return;
    const at = root.current;
    (at?.querySelector<HTMLElement>(".ledger-match-link") ?? at)?.focus();
  }, [confirmed]);

  // Keyed by the document, so another document's page is never kept. It
  // stays beside the confirmation, read only, to check what was confirmed.
  const viewer = (
    <DocumentViewer
      key={`${reference.kind}:${reference.id}`}
      port={port}
      reader={reader}
      reference={reference}
      fileName={fileName}
    />
  );
  const columns = (className: string, body: ReactNode) => (
    <ReviewColumns
      viewer={viewer}
      share={viewerShare}
      onShare={onViewerShare}
      className={className}
    >
      {body}
    </ReviewColumns>
  );

  const view = read.value;
  const draft = view?.draft ?? null;
  const blockers = view?.blockers ?? [];
  const actions = stage.content.actions;
  const duplicateAsked = useMemo(
    () => (draft ? duplicateQuestion(draft, kind, corrections) : null),
    [draft, kind, corrections],
  );
  const duplicateCheck = useInvoiceDuplicate(port, duplicateAsked, invoices);
  const duplicateId =
    duplicateCheck.kind === "answer" ? duplicateCheck.result.invoice_id : null;
  const duplicate =
    invoices?.find((invoice) => invoice.invoice_id === duplicateId) ?? null;
  // What the ledger would link the confirmed invoice to, asked once it has one
  // that no movement is linked to.
  const confirmedInvoice = confirmed?.confirmation.invoice ?? null;
  const linkAsked = useMemo(
    () =>
      confirmedInvoice && confirmedInvoice.linked_transaction_ids.length === 0
        ? {
            staged: [...stagedLinks(actions).rows].map(
              ([transaction_id, invoice_id]) => ({
                transaction_id,
                invoice_id,
              }),
            ),
            invoice_id: confirmedInvoice.invoice_id,
          }
        : null,
    [confirmedInvoice, actions],
  );
  const linkMatches = useInvoiceMatches(port, linkAsked, rows);
  // The answer names an invoice the list has yet to bring, or has not come.
  const duplicateUnread =
    duplicateAsked !== null &&
    (duplicateCheck.kind !== "answer" ||
      (duplicateId !== null && duplicate === null));

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
                words: servedRefusalWords(sent.detail),
                step: servedNextStep(sent.detail),
              }
            : { kind: "failed", code: sent.code },
      );
      if (sent.kind === "unknown") {
        const what = t("desktop.ledger.section.documents");
        pause.hold({
          what,
          outcome: sent.saved ? "saved_unread" : "unknown",
          settle: landingSettle(
            t,
            what,
            extractionLanding(
              port,
              evidenceReference,
              view?.drafted_at ?? null,
            ),
          ),
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
          duplicateUnread,
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
            duplicateUnread,
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
      duplicateUnread,
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
      const what = t("desktop.ledger.section.documents");
      pause.hold({
        what,
        outcome: sent.saved ? "saved_unread" : "unknown",
        settle: landingSettle(
          t,
          what,
          confirmationLanding(port, evidenceReference, {
            kind: ready.request.kind,
            number:
              ready.request.invoice_number ??
              readValue(draft, "invoice_number"),
          }),
        ),
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
            words: servedRefusalWords(sent.detail),
            step: servedNextStep(sent.detail),
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

  if (confirmed)
    return columns(
      "",
      <ConfirmedReading
        rootRef={root}
        linkRef={confirmedLink}
        confirmed={confirmed}
        rows={rows}
        linkMatches={linkMatches}
        actions={actions}
        locale={locale}
        onStage={onStage}
        onLinkStaged={onLinkStaged}
        say={say}
      />,
    );

  if (read.phase === "failed")
    return columns(
      "flex",
      <EmptyState
        className="ledger-draft-failed"
        icon="alert"
        description={
          <span role="alert">{t("desktop.ledger.documents.read_failed")}</span>
        }
      >
        <Button variant="outline" onClick={reread}>
          {t("desktop.ledger.retry")}
        </Button>
      </EmptyState>,
    );
  if (!view || !draft)
    return columns(
      "flex",
      <EmptyState
        className="ledger-draft-loading"
        role="status"
        busy
        description={t("desktop.ledger.loading")}
      />,
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
  /** What a correctable row offers: the catalogue's parties, series and
   * numbers, this party's first. A party picked fills the other of name and
   * tax id only while the person has not touched it and the reading left it
   * empty; the person sees it and confirms as before. */
  const offers = (field: CorrectionField) => {
    const party = correctable("counterparty_name");
    const partyName = party.typed ?? party.read ?? "";
    const fillSibling =
      (sibling: CorrectionField, key: "name" | "tax_id") =>
      (picked: Suggestion) => {
        const { typed, read } = correctable(sibling);
        const filled =
          typed === undefined
            ? emptyFills<CorrectionField>(
                picked.fills,
                { [sibling]: read },
                { [key]: sibling },
              )
            : [];
        if (filled.length === 0) return;
        setCorrections((held) => ({
          ...held,
          ...Object.fromEntries(
            filled.filter(([to]) => held[to] === undefined),
          ),
        }));
        say(t("desktop.ledger.suggestions.filled"));
      };
    switch (field) {
      case "counterparty_name":
        return {
          suggestions: invoices && partyNameOptions(invoices, { kind }),
          onPick: fillSibling("counterparty_tax_id", "tax_id"),
        };
      case "counterparty_tax_id":
        return {
          suggestions: invoices && partyTaxIdOptions(invoices, { kind }),
          onPick: fillSibling("counterparty_name", "name"),
        };
      case "series":
        return {
          suggestions:
            invoices &&
            partySeriesOptions(invoices, { kind, party: partyName }),
          opensEmpty: true,
        };
      case "invoice_number":
        return {
          suggestions:
            invoices &&
            invoiceNumberOptions(invoices, { kind, party: partyName }, locale),
        };
      case "currency":
        return currencies;
      default:
        return {};
    }
  };
  const suggested = draft.suggested_kind ?? null;
  const readCountry =
    kind === "issued"
      ? (draft.customer_country_code ?? null)
      : kind === "received"
        ? (draft.supplier_country_code ?? null)
        : null;
  const currencyRead = readValue(draft, "currency");
  const open = blockers.filter(
    (blocker) => resolutionOf(blocker, answers[blocker.blocker_id]) === null,
  ).length;
  const findingId = (at: number) => `${countryId}-finding-${at}`;
  /** The first finding that asks about `field`, as the way to it. */
  const questionOf = (field: ReadingField): Question | null => {
    const at = blockers.findIndex((blocker) => blocker.field === field);
    if (at < 0) return null;
    return {
      words: blockers[at]!.reason_words ?? null,
      go: () => {
        const finding = document.getElementById(findingId(at));
        finding?.scrollIntoView({ block: "nearest" });
        finding?.focus({ preventScroll: true });
      },
    };
  };

  return columns(
    "",
    <div ref={root} className="ledger-draft-reading grid gap-4 p-3">
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
                {formatDay(locale, localDay(new Date(view.drafted_at)))}
              </span>
            </TooltipTrigger>
            <TooltipContent>
              {t("desktop.ledger.documents.read_by", {
                extractor: view.extractor,
                date: formatDay(locale, localDay(new Date(view.drafted_at))),
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
        {/* Offered only where the backend says this profile may be asked;
            each read still asks for its own acknowledgement. */}
        {reference.kind === "evidence" &&
          view.off_host_read_offered === true && (
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

      <ReviewNotices
        notice={notice}
        busy={busy !== null}
        fallback={view.label_reading_fallback}
        onCheck={() => {
          void check();
          if (!pause.rereading) pause.reread();
        }}
      />

      <section aria-labelledby={`${countryId}-read`} className="grid gap-2">
        <h4 id={`${countryId}-read`} className="text-sm font-semibold">
          {t("desktop.ledger.documents.what_was_read")}
        </h4>
        <ReadingTable
          rows={readingRows(kind)}
          renderRow={(row) => {
            if (row.kind === "read") {
              const value = readValue(draft, row.field);
              return (
                <tr data-field={row.field}>
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
                      question={questionOf(row.field)}
                    />
                  </td>
                  <td className="py-1 pr-2 tabular-nums">
                    {shownReadingValue(locale, row.field, value) ?? "—"}
                  </td>
                </tr>
              );
            }
            const facts = correctable(row.field);
            const refused =
              facts.parsed?.kind === "refused" ? facts.parsed.refusal : null;
            return (
              <tr data-field={row.field}>
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
                    question={questionOf(facts.readField)}
                  />
                </td>
                <td className="py-1 pr-2">
                  <div
                    className={`ledger-draft-input ${fieldWidth(
                      CORRECTION_SHAPES[row.field],
                      row.field === "counterparty_name",
                    )}`}
                  >
                    <TypedField
                      field={entrySpec(CORRECTION_SHAPES[row.field], row.field)}
                      controlSize="sm"
                      aria-label={fieldLabel(t, row.field)}
                      invalid={refused ? true : undefined}
                      describedBy={
                        refused ? `${countryId}-${row.field}-error` : undefined
                      }
                      value={
                        facts.typed ??
                        seeded(CORRECTION_SHAPES[row.field], facts.read ?? "")
                      }
                      {...offers(row.field)}
                      onChange={(value) =>
                        setCorrections((held) => ({
                          ...held,
                          [row.field]: value,
                        }))
                      }
                    />
                  </div>
                  {refused && (
                    <FieldError id={`${countryId}-${row.field}-error`}>
                      {problemText(t, { kind: "grammar", refusal: refused })}
                    </FieldError>
                  )}
                </td>
              </tr>
            );
          }}
        />
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
            {blockers.map((blocker, at) => (
              <Finding
                key={blocker.blocker_id}
                id={findingId(at)}
                t={t}
                blocker={blocker}
                answer={answers[blocker.blocker_id]}
                printed={
                  blocker.field &&
                  DERIVED_FIELDS.has(blocker.field as ReadingField)
                    ? shownReadingValue(
                        locale,
                        blocker.field as ReadingField,
                        readValue(draft, blocker.field as ReadingField),
                      )
                    : null
                }
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
            <CountryEditor
              id={countryId}
              controlSize="sm"
              className="ledger-draft-country"
              maxLength={2}
              invalid={
                country !== "" && !countryAdmitted(country) ? true : undefined
              }
              value={country}
              onChange={setCountry}
              {...countries}
            />
            {readCountry && country !== readCountry && (
              <Button
                size="xs"
                variant="link"
                className="ledger-draft-country-read w-fit"
                onClick={() => {
                  setCountry(readCountry);
                  // The country was the last thing asked: confirming is next.
                  root.current
                    ?.querySelector<HTMLElement>(".ledger-draft-confirm")
                    ?.focus();
                }}
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
              <CurrencyEditor
                id={currencyId}
                controlSize="sm"
                value={corrections.currency ?? ""}
                onChange={(currency) =>
                  setCorrections((held) => ({ ...held, currency }))
                }
                {...currencies}
              />
              <FieldDescription>
                {t("desktop.ledger.documents.currency_not_read")}
              </FieldDescription>
            </Field>
          )}
        </div>
        <DuplicateNotice
          duplicateCheck={duplicateCheck}
          asked={duplicateAsked !== null}
          duplicate={duplicate}
          record={record}
          reference={reference}
          actions={actions}
          anyway={anyway}
          onAnyway={setAnyway}
          locale={locale}
          onStage={onStage}
          say={say}
        />
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
              {facts(
                t,
                holds.map((hold) => holdText(t, hold)),
              )}
            </span>
          )}
        </div>
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
    </div>,
  );
}
