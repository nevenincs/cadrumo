import type { ComboboxOption } from "@/components/ui/combobox";
import type { LedgerParticipation } from "../../../shell/ledger";
import type { OwnAccountChoice } from "../../../shell/ledgerMovementReads";
import {
  DIRECTIONS,
  IRPF_CATEGORIES,
  IVA_CATEGORIES,
  SPENDING_CATEGORY_FAMILIES,
} from "../../../shell/ledgerVocabulary";
import type { Translate } from "../../../shell/strings";
import {
  categoryOption,
  directionLabel,
  irpfCategoryLabel,
  ivaCategoryLabel,
} from "../movements/movementWords";
import type {
  InspectorSection,
  LifecycleAction,
  SkipReason,
} from "./inspectorModel";

// The inspector's words: every key named here in full, so the catalogue's
// checks find each one.

export const sectionNames = (
  t: Translate,
): Record<InspectorSection, string> => ({
  classify: t("desktop.ledger.inspector.section.classify"),
  documents: t("desktop.ledger.inspector.section.documents"),
  invoice: t("desktop.ledger.inspector.section.invoice"),
  details: t("desktop.ledger.inspector.section.details"),
  history: t("desktop.ledger.inspector.section.history"),
});

export function lifecycleName(t: Translate, kind: LifecycleAction): string {
  switch (kind) {
    case "archive":
      return t("desktop.ledger.inspector.action.archive");
    case "stash":
      return t("desktop.ledger.inspector.action.stash");
    case "restore":
      return t("desktop.ledger.inspector.action.restore");
    case "exclude":
      return t("desktop.ledger.inspector.action.exclude");
  }
}

export function skipName(t: Translate, reason: SkipReason): string {
  switch (reason) {
    case "not_active":
      return t("desktop.ledger.inspector.skip.not_active");
    case "sealed":
      return t("desktop.ledger.inspector.skip.sealed");
    case "sealed_unread":
      return t("desktop.ledger.inspector.skip.sealed_unread");
    case "transfer":
      return t("desktop.ledger.inspector.skip.transfer");
    case "personal":
      return t("desktop.ledger.inspector.skip.personal");
    case "unclassified":
      return t("desktop.ledger.inspector.skip.unclassified");
  }
}

/** The revision states that seal the movements a revision cites. */
const SEALING = ["verificado_completo", "presentado"];
export const seals = (participation: LedgerParticipation) =>
  SEALING.includes(participation.revision_state);

/** A declaration revision's state in its real words: a local filing is
 * not the AEAT's confirmation, a receipt is. */
export function revisionStateLabel(
  t: Translate,
  participation: Pick<
    LedgerParticipation,
    "revision_state" | "justificante_reference"
  >,
): string {
  switch (participation.revision_state) {
    case "verificado_completo":
      return t("desktop.ledger.inspector.used.verified");
    case "presentado":
      return participation.justificante_reference
        ? t("desktop.ledger.inspector.used.filed_confirmed")
        : t("desktop.ledger.inspector.used.filed_local");
    case "presentado_supersedido":
      return t("desktop.ledger.inspector.used.superseded");
    case "borrador":
      return t("desktop.ledger.inspector.used.draft");
    case "descartado":
      return t("desktop.ledger.inspector.used.discarded");
    default:
      return participation.revision_state;
  }
}

/** A declaration as one line: "Modelo 303 · 2026 1T". */
export const declarationName = (
  t: Translate,
  modelo: string,
  year: number,
  period: string,
) => t("desktop.ledger.inspector.used.name", { modelo, year, period });

const EVENT_KEYS: Record<string, string> = {
  "ledger.transaction.created": "desktop.ledger.inspector.event.created",
  "ledger.transaction.imported": "desktop.ledger.inspector.event.imported",
  "ledger.transaction.updated": "desktop.ledger.inspector.event.updated",
  "ledger.transaction.classified": "desktop.ledger.inspector.event.classified",
  "ledger.transaction.llm_suggestion.rejected":
    "desktop.ledger.inspector.event.model_rejected",
  "ledger.transaction.allocated": "desktop.ledger.inspector.event.allocated",
  "ledger.transaction.removed": "desktop.ledger.inspector.event.removed",
  "ledger.transaction.archived": "desktop.ledger.inspector.event.archived",
  "ledger.transaction.stashed": "desktop.ledger.inspector.event.stashed",
  "ledger.transaction.restored": "desktop.ledger.inspector.event.restored",
  "ledger.transaction.reviewed_excluded":
    "desktop.ledger.inspector.event.excluded",
  "ledger.transaction.exported": "desktop.ledger.inspector.event.exported",
  "ledger.transaction.split": "desktop.ledger.inspector.event.split",
  "ledger.transaction.merged": "desktop.ledger.inspector.event.merged",
  "ledger.transaction.invoice.linked": "desktop.ledger.inspector.event.linked",
  "ledger.transaction.correction.applied":
    "desktop.ledger.inspector.event.corrected",
  "purchase_invoice_evidence.attached":
    "desktop.ledger.inspector.event.evidence_attached",
  "purchase_invoice_evidence.replaced":
    "desktop.ledger.inspector.event.evidence_replaced",
  "purchase_invoice_evidence.detached":
    "desktop.ledger.inspector.event.evidence_detached",
  "attachment.linked": "desktop.ledger.inspector.event.attachment_linked",
  "attachment.removed": "desktop.ledger.inspector.event.attachment_removed",
};
/** What an event in a movement's history did. */
export const eventName = (t: Translate, type: string) =>
  t(EVENT_KEYS[type] ?? "desktop.ledger.inspector.event.other");

/** Who decided a classification: you, a rule, the model with your
 * approval, or the product working it out. */
export function decidedBy(t: Translate, source: string): string {
  if (source === "" || source === "none")
    return t("desktop.ledger.inspector.by.nobody");
  if (source.startsWith("llm:"))
    return t("desktop.ledger.inspector.by.model", { model: source });
  if (source.startsWith("rule:"))
    return t("desktop.ledger.inspector.by.rule", { rule: source.slice(5) });
  if (source.startsWith("derived:"))
    return t("desktop.ledger.inspector.by.derived");
  return t("desktop.ledger.inspector.by.you");
}

/** Why asking the model gave nothing to read, in words, and whether its
 * code says more than the words, for Technical details. `subject_busy` is
 * an earlier review of the same movement still waiting. */
export function modelFailureText(
  t: Translate,
  code: string,
): { text: string; technical: boolean } {
  switch (code) {
    case "subject_busy":
      return {
        text: t("desktop.ledger.inspector.model.busy"),
        technical: false,
      };
    case "no_review":
      return {
        text: t("desktop.ledger.inspector.model.no_review"),
        technical: false,
      };
    case "refused":
      return {
        text: t("desktop.ledger.inspector.model.refused"),
        technical: false,
      };
    default:
      return {
        text: t("desktop.ledger.inspector.model.unavailable"),
        technical: true,
      };
  }
}

// ---- Choices -------------------------------------------------------------------

export const categoryOptions = (t: Translate): ComboboxOption[] =>
  SPENDING_CATEGORY_FAMILIES.flatMap(([family, members]) =>
    members.map((member) => categoryOption(t, family, member)),
  );
export const ivaCategoryOptions = (t: Translate): ComboboxOption[] =>
  IVA_CATEGORIES.map((id) => ({ value: id, label: ivaCategoryLabel(t, id) }));
export const irpfCategoryOptions = (t: Translate): ComboboxOption[] =>
  IRPF_CATEGORIES.map((id) => ({ value: id, label: irpfCategoryLabel(t, id) }));
export const directionOptions = (t: Translate): ComboboxOption[] =>
  DIRECTIONS.map((id) => ({ value: id, label: directionLabel(t, id) }));
export const accountOptions = (
  accounts: readonly OwnAccountChoice[],
): ComboboxOption[] =>
  accounts.map((account) => ({ value: account.id, label: account.label }));
