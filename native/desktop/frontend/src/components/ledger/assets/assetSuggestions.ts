// What the element forms offer as text is typed in, and what the descriptor
// form starts from when the element's purchase has an invoice. Both are draft
// text the person sees and the register still judges. A pick fills only the
// fields beside it that are empty, and nothing here is a tax fact.

import { useEffect, useRef } from "react";
import type { SuggestionProps } from "@/components/editors/editorProps";
import type { Suggestion } from "@/components/ui/suggestions";
import type { AcquisitionCandidate } from "../../../shell/ledgerSetup";
import { emptyFills } from "../suggestions/ledgerSuggestions";
import {
  useFieldSuggestions,
  useHeldInvoices,
} from "../suggestions/SuggestionsProvider";
import type { FieldKind, FormDraft, FormField } from "./assetFields";
import { purchaseInvoiceFacts } from "./assetWrites";

/** The sibling fields a supplier pick can fill, by what the pick offers. */
const SUPPLIER_SIBLINGS = {
  name: "supplier_name",
  tax_id: "supplier_tax_id",
} as const;

const DESCRIPTOR_FACTS = [
  "supplier_name",
  "supplier_tax_id",
  "document_number",
] as const;

/**
 * The fields with what each offers: suppliers, tax ids, document numbers and
 * acquisition references from the invoices the page holds, and a new
 * element's name from the purchase it names. A fill goes only to a field
 * still empty.
 */
export function useAssetSuggestions({
  kind,
  fields,
  draft,
  set,
  purchase,
}: {
  kind: FieldKind;
  fields: readonly FormField[];
  draft: FormDraft;
  set(changes: FormDraft): void;
  /** The purchase a new element names as its acquisition. */
  purchase: AcquisitionCandidate | undefined;
}): FormField[] {
  const names = useFieldSuggestions("supplier");
  const taxIds = useFieldSuggestions("supplier_tax_id");
  const numbers = useFieldSuggestions("invoice_number", {
    invoiceKind: "received",
    party: draft.supplier_name ?? "",
  });
  const references = useFieldSuggestions("invoice_number", {
    invoiceKind: "received",
  });
  const fillBeside = (picked: Suggestion) => {
    const entries = emptyFills(picked.fills, draft, SUPPLIER_SIBLINGS);
    if (entries.length > 0) set(Object.fromEntries(entries));
  };
  const described = purchase?.description.trim() ?? "";
  const offers: Partial<Record<string, SuggestionProps>> = {
    supplier_name: { ...names, onPick: fillBeside },
    supplier_tax_id: { ...taxIds, onPick: fillBeside },
    document_number: { ...numbers, onPick: fillBeside },
    acquisition_reference: references,
    ...(kind === "element" && described !== ""
      ? {
          name: {
            suggestions: [{ value: described, label: described }],
            opensEmpty: true,
          },
        }
      : {}),
  };
  return fields.map((field) => {
    const found = offers[field.key];
    return found === undefined ? field : { ...field, offers: found };
  });
}

/**
 * Starts the descriptor of an element bought with a ledger movement from the
 * one received invoice linked to that movement: its supplier, tax id and
 * number. It does so once, when the descriptor states none of them and none
 * has been typed, and the person sees the text as a draft.
 */
export function usePurchasePrefill({
  active,
  purchase,
  stated,
  draft,
  set,
}: {
  active: boolean;
  /** The movement the element's revision names as its acquisition. */
  purchase: string | null;
  /** What the descriptor states now; null while it is unread. */
  stated: Readonly<Record<string, string | null>> | null;
  draft: FormDraft;
  set(changes: FormDraft): void;
}) {
  const invoices = useHeldInvoices(active && purchase !== null);
  const done = useRef(false);
  useEffect(() => {
    if (done.current || !active || purchase === null) return;
    if (invoices === null || stated === null) return;
    done.current = true;
    const blank = DESCRIPTOR_FACTS.every(
      (key) => (stated[key] ?? "") === "" && (draft[key] ?? "") === "",
    );
    if (!blank) return;
    const facts = purchaseInvoiceFacts(invoices, purchase);
    if (Object.keys(facts).length > 0) set(facts);
  }, [active, purchase, invoices, stated, draft, set]);
}
