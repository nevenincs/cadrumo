import { useEffect, useRef, useState } from "react";
import { emptyDraft, type InvoiceDraft } from "./invoiceModel";

let lineKeys = 0;
export const nextLineKey = () => {
  lineKeys += 1;
  return `line-${lineKeys}`;
};

/** Initializes a new draft, adopting a late served default without marking it dirty. */
export function useInvoiceEditorDraft(defaultClass: string | null) {
  const [draft, setDraft] = useState<InvoiceDraft>(() =>
    emptyDraft(nextLineKey(), defaultClass),
  );
  const initialDraft = useRef(JSON.stringify(draft));
  // The vocabulary can arrive after the draft opened: the served default
  // fills a class still unchosen, and the draft as opened takes it too, so
  // the fill is not an edit.
  useEffect(() => {
    if (draft.invoiceClass !== "" || defaultClass === null) return;
    const served = defaultClass;
    setDraft((held) =>
      held.invoiceClass === "" ? { ...held, invoiceClass: served } : held,
    );
    const asOpened: InvoiceDraft = JSON.parse(initialDraft.current);
    initialDraft.current = JSON.stringify({
      ...asOpened,
      invoiceClass: served,
    });
  }, [draft.invoiceClass, defaultClass]);

  return {
    draft,
    setDraft,
    dirty: JSON.stringify(draft) !== initialDraft.current,
  };
}
