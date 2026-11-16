import { useLayoutEffect } from "react";
import type { OutputLanguage } from "../../../shell/modeloContract/modelo";
import type {
  ModeloWriteHolds,
  ModeloWriteOwner,
} from "../../../shell/modeloWriteHolds";
import type { ModeloWorkbenchFormProjectionV1 } from "../../../shell/modeloContract/modeloWorkForm";
import type { useHistoryRead } from "./historyRead";

/** The last form read of the open declaration, and the History view's
 * answers, kept by the caller while the workspace is put away, in memory
 * only. */
export type KeptWorkspaceRead = Parameters<
  typeof useHistoryRead
>[0]["memory"] & {
  form?: {
    workUnitId: string;
    language: OutputLanguage;
    envelope: ModeloWorkbenchFormProjectionV1;
  };
};

/** The read to draw at once: the kept one of the same declaration in the
 * same language, or none yet. */
export function keptRead(
  kept: KeptWorkspaceRead | undefined,
  workUnitId: string,
  language: OutputLanguage,
):
  | { phase: "ready"; envelope: ModeloWorkbenchFormProjectionV1 }
  | { phase: "reading" } {
  const form = kept?.form;
  return form && form.workUnitId === workUnitId && form.language === language
    ? { phase: "ready", envelope: form.envelope }
    : { phase: "reading" };
}

/** The kept read is the last one, not the declaration as it stands: while a
 * fresh read is made it is held as a read the window still has to make, the
 * hold every write leaves behind, so the same switches that refuse a write
 * and say the window is reading answer for it. Where a hold already stands,
 * it holds. Answers what to call when the workspace is put away or the read
 * is to be made again: the hold goes if the fresh read has not landed. */
function holdKeptRead(
  holds: ModeloWriteHolds,
  target: string,
  owner: ModeloWriteOwner,
): () => void {
  const lease = holds.begin(target, owner);
  if (!lease) return () => undefined;
  holds.needsRead(lease);
  return () => {
    const held = holds.get(target);
    if (held?.id === lease.id) holds.readCompleted(held);
  };
}

/** Who a declaration's holds are said to belong to. */
export function ownerOf(
  workUnitId: string,
  envelope: ModeloWorkbenchFormProjectionV1,
): ModeloWriteOwner {
  const form = envelope.form.form;
  return {
    workUnitId,
    label: [
      form.modelo,
      form.modelo_name ?? form.modelo_title,
      form.period_words,
    ]
      .filter(Boolean)
      .join(" · "),
    filingYear: form.filing_year,
    readsIvaWallet: form.offers_iva_wallet,
  };
}

/** Before it is painted, a kept read is held until the fresh read lands. */
export function useKeptReadHold(
  kept: KeptWorkspaceRead | undefined,
  workUnitId: string,
  language: OutputLanguage,
  holds: ModeloWriteHolds,
  target: string,
) {
  useLayoutEffect(() => {
    const first = keptRead(kept, workUnitId, language);
    return first.phase === "ready"
      ? holdKeptRead(holds, target, ownerOf(workUnitId, first.envelope))
      : undefined;
  }, [kept, workUnitId, language, holds, target]);
}
