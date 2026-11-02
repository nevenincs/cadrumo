import { heldDecimal } from "../../../shared/numbers";
import type { PublicDecimal } from "../../../shell/ledger";
import { canonicalDecimal } from "../../../shell/ledgerGrammar";
import type { InventoryMovement } from "../../../shell/ledgerSetup";
import type { ProofSlotKey } from "./stockVocabulary";
import { plays, type Vocabulary } from "./stockVocabulary";

// ---- What the person has typed -----------------------------------------------

/** A file a purchase or a closing value rests on: what the backend named it
 * by once it kept it, the kind of proof, and the mark it answered. Both are
 * empty until a file is kept, and neither is drawn. */
export type ProofDraft = {
  reference: string;
  kind: string;
  digest: string;
  /** The file's bare name, where it is known; only ever shown. */
  fileName?: string;
};

/** One extra cost of a purchase. Its key is the reference minted for it. */
export type ExtraDraft = {
  key: string;
  kind: string;
  price: string;
  iva: string;
  share: string;
  proof: ProofDraft;
};

export type BookDraft = { name: string; method: string; opening: string };

export type MovementDraft = {
  /** The text of each field, by its key. */
  values: Readonly<Record<string, string>>;
  extras: readonly ExtraDraft[];
  proofs: Readonly<Record<ProofSlotKey, ProofDraft>>;
};

export type DescribeDraft = { label: string; description: string };
export type CorrectDraft = { reason: string; opening: string; method: string };

/** A closing value: what is typed, and the files kept, by the role each
 * plays. A document that shows the prior year's closing is one more file. */
export type ClosingDraft = {
  values: Readonly<Record<string, string>>;
  decision: Readonly<Record<string, ProofDraft>>;
  count: Readonly<Record<string, ProofDraft>>;
  prior: readonly { key: string; proof: ProofDraft }[];
};

export const EMPTY_BOOK: BookDraft = { name: "", method: "", opening: "" };
export const EMPTY_CORRECTION: CorrectDraft = {
  reason: "",
  opening: "",
  method: "",
};
export const EMPTY_CLOSING: ClosingDraft = {
  values: {},
  decision: {},
  count: {},
  prior: [],
};

export const blankProof = (kind = ""): ProofDraft => ({
  reference: "",
  kind,
  digest: "",
});

export const blankExtra = (mint: () => string): ExtraDraft => ({
  key: mint(),
  kind: "",
  price: "",
  iva: "",
  share: "",
  proof: blankProof(),
});

/** A movement form's start: nothing typed, nothing kept. */
export function blankMovement(): MovementDraft {
  return {
    values: {},
    extras: [],
    proofs: {
      price: blankProof(),
      cost_check: blankProof(),
      iva_check: blankProof(),
    },
  };
}

export const proofKept = (proof: ProofDraft) => proof.digest !== "";

/** Whether anything is typed or chosen that is not yet written. */
export function movementTouched(draft: MovementDraft): boolean {
  return (
    Object.values(draft.values).some((text) => text.trim() !== "") ||
    draft.extras.length > 0 ||
    Object.values(draft.proofs).some(proofKept)
  );
}

export function closingTouched(draft: ClosingDraft): boolean {
  return (
    Object.values(draft.values).some((text) => text.trim() !== "") ||
    Object.values(draft.decision).some(proofKept) ||
    Object.values(draft.count).some(proofKept) ||
    draft.prior.length > 0
  );
}

export const bookTouched = (draft: BookDraft): boolean =>
  Object.values(draft).some((text) => text.trim() !== "");

/** The draft a correction starts from: what the book kept of the movement,
 * so the person changes only what was wrong. */
export function draftOfMovement(
  movement: InventoryMovement,
  vocabulary: Vocabulary,
): MovementDraft {
  const blank = blankMovement();
  const text = (value: { decimal: string } | null | undefined) =>
    value ? heldDecimal(value.decimal) : "";
  const detail = movement.acquisition_detail ?? null;
  const cost = movement.acquisition_cost ?? null;
  const base: Record<string, string> = {
    date: movement.movement_date,
    kind: movement.kind,
    quantity: heldDecimal(movement.quantity.decimal),
  };
  if (!plays(vocabulary, "purchase", movement.kind))
    return {
      ...blank,
      values: {
        ...base,
        ...(movement.unit_cost ? { unit_cost: text(movement.unit_cost) } : {}),
        ...(movement.taxable_base
          ? { total_cost: text(movement.taxable_base) }
          : {}),
      },
    };
  if (cost === null || detail === null) return { ...blank, values: base };
  const held = (reference: string): ProofDraft => {
    const found = detail.documents.find(
      (document) => document.reference === reference,
    );
    return found
      ? {
          reference: found.reference,
          kind: found.evidence_kind,
          digest: found.content_digest,
          ...(found.file_name ? { fileName: found.file_name } : {}),
        }
      : blankProof();
  };
  const share = (fraction: PublicDecimal) =>
    heldDecimal(canonicalDecimal(fraction.decimal) ?? fraction.decimal);
  return {
    values: {
      ...base,
      price: text(cost.consideration_excluding_iva),
      iva: text(detail.consideration_iva_amount),
      share: share(detail.consideration_deductible_iva_ratio),
    },
    extras: detail.components.map((component) => ({
      key: component.component_id,
      kind: component.kind,
      price: text(component.taxable_base),
      iva: text(component.iva_amount),
      share: share(component.deductible_iva_ratio),
      proof: held(component.evidence_references[0] ?? ""),
    })),
    proofs: {
      price: held(detail.consideration_evidence),
      cost_check: held(detail.attributable_cost_review_evidence),
      iva_check: held(detail.iva_recoverability_review_evidence),
    },
  };
}
