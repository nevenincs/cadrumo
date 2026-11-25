import { useMemo, useState } from "react";
import type { CatalogueInvoiceSnapshot } from "../../../shell/ledgerInvoiceContract";
import { useNavigationGuard } from "../../../shell/navigation/hooks";
import { useStrings } from "../../../shell/strings";
import { useVocabulary } from "../suggestions/SuggestionsProvider";
import type { InvoiceEditorProps } from "./InvoiceEditor";
import { useInvoiceEditorDraft } from "./invoiceEditorDraft";
import {
  checkCorrection,
  checkDraft,
  correctionOf,
  correctionPreview,
  readDraft,
  type CorrectionDraft,
  type InvoiceDraft,
  type Problem,
} from "./invoiceModel";
import { useInvoicePreview } from "./invoicePreview";
import { problemText } from "./invoiceWords";
import { useInvoiceEditorWrites } from "./useInvoiceEditorWrites";

/** Draft validation, preview correlation and review-stage state for the invoice sheet. */
export function useInvoiceEditor({
  port,
  invoices,
  target,
  onClose,
  onWritten,
  say,
}: Pick<
  InvoiceEditorProps,
  "port" | "invoices" | "target" | "onClose" | "onWritten" | "say"
>) {
  const t = useStrings();
  const vocabulary = useVocabulary();
  const opened =
    target.kind === "open"
      ? (invoices.find((found) => found.invoice_id === target.invoiceId) ??
        null)
      : null;
  // The stored invoice as it was opened: a write closes the editor.
  const [stored] = useState<CatalogueInvoiceSnapshot | null>(opened);
  const draftState = useInvoiceEditorDraft(vocabulary.defaultClass);
  const { draft, setDraft } = draftState;
  const [correction, setCorrection] = useState<CorrectionDraft | null>(() =>
    opened ? correctionOf(opened) : null,
  );
  const [chosen, setStage] = useState<"edit" | "remove">("edit");
  // Review waits for the ledger's answer to the draft as it stands: asked
  // for here, it opens once that answer would accept.
  const [wantsReview, setWantsReview] = useState(false);
  const backToEdit = () => {
    setStage("edit");
    setWantsReview(false);
  };
  const [asking, setAsking] = useState(false);
  const [tried, setTried] = useState(false);
  const [touched, setTouched] = useState<ReadonlySet<string>>(new Set());
  const [duplicate, setDuplicate] = useState<string | null>(null);
  const writes = useInvoiceEditorWrites({
    port,
    stored,
    onClose,
    onWritten,
    say,
    backToEdit,
    setDuplicate,
  });
  const { sending, outcome, setOutcome } = writes;
  const isNew = target.kind === "new";
  const reading = useMemo(
    () => readDraft(draft, vocabulary.correctiveClass),
    [draft, vocabulary.correctiveClass],
  );
  const asked = useMemo(
    () =>
      isNew
        ? reading.preview
        : stored && correction
          ? correctionPreview(stored, correction, vocabulary.correctiveClass)
          : {},
    [isNew, reading, stored, correction, vocabulary.correctiveClass],
  );
  const preview = useInvoicePreview(port, asked);
  const answered = preview.current;
  const check = useMemo(
    () => checkDraft(draft, reading, answered),
    [draft, reading, answered],
  );
  const corrected = useMemo(
    () =>
      stored && correction
        ? checkCorrection(
            stored,
            correction,
            answered,
            vocabulary.correctiveClass,
          )
        : null,
    [stored, correction, answered, vocabulary.correctiveClass],
  );
  const ready = isNew ? check.request : (corrected?.request ?? null);
  const stage =
    chosen === "edit" && wantsReview && ready && duplicate === null
      ? "confirm"
      : chosen;
  const problems: Record<string, Problem> = isNew
    ? check.problems
    : (corrected?.problems ?? {});
  const unknown = outcome?.kind === "unknown";
  const dirty = isNew ? draftState.dirty : (corrected?.changed.length ?? 0) > 0;
  // The editor weighs its own work before a navigation takes the section
  // down, instead of holding the window as a sheet does.
  useNavigationGuard(
    "ledger/invoices",
    sending ? "busy" : dirty ? "dirty" : "clean",
    { discard: onClose },
  );

  const touch = (field: string) =>
    setTouched((held) => (held.has(field) ? held : new Set(held).add(field)));
  const shown = (field: string) => {
    const problem = problems[field];
    if (!problem) return null;
    if (
      tried ||
      (problem.kind === "finding" && !problem.quiet) ||
      (touched.has(field) &&
        (problem.kind === "grammar" || problem.kind === "finding"))
    )
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
    backToEdit();
  };
  const correct = <K extends keyof CorrectionDraft>(
    key: K,
    value: CorrectionDraft[K],
  ) => {
    setCorrection((held) => (held ? { ...held, [key]: value } : held));
    if (outcome?.kind !== "unknown") setOutcome(null);
    backToEdit();
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

  return {
    ...writes,
    stored,
    draft,
    correction,
    setStage,
    stage,
    asking,
    setAsking,
    tried,
    touched,
    duplicate,
    isNew,
    preview,
    check,
    corrected,
    unknown,
    shown,
    touch,
    edit,
    correct,
    close,
    setTried,
    setWantsReview,
  };
}

export type InvoiceEditorState = ReturnType<typeof useInvoiceEditor>;
