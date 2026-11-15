import { useCallback, type MutableRefObject } from "react";
import type { ModeloPort } from "../../../shell/modelo";
import type { OutputLanguage } from "../../../shell/modeloContract/modelo";
import type { ModeloWorkbenchFormProjectionV1 } from "../../../shell/modeloContract/modeloWorkForm";
import type { ModeloWriteHolds } from "../../../shell/modeloWriteHolds";
import { runOperation } from "../dialogs/operationRun";
import { answersFor, withFilingState } from "./filingStateRead";
import type { KeptWorkspaceRead } from "./keptRead";

/** What the workspace's own reads share: the newest read begun, so an older
 * one yields to it, and the declaration shown now. */
export type WorkspaceReads = {
  latest: MutableRefObject<number>;
  newest: MutableRefObject<{
    ticket: number;
    result: Promise<boolean>;
  } | null>;
  shownEnvelope: MutableRefObject<ModeloWorkbenchFormProjectionV1 | null>;
};

/**
 * After an export, a filing or a receipt the Export and record view reads
 * only the filing state, which serves the filed header, the journey and the
 * next step as well as the filing; a read that does not settle, or answers
 * for another declaration, falls back to the whole read.
 */
export function useRereadFiling({
  port,
  workUnitId,
  language,
  holds,
  target,
  kept,
  reads: { latest, newest, shownEnvelope },
  reread,
  show,
}: {
  port: ModeloPort;
  workUnitId: string;
  language: OutputLanguage;
  holds: ModeloWriteHolds;
  target: string;
  kept: KeptWorkspaceRead | undefined;
  reads: WorkspaceReads;
  reread: () => Promise<boolean>;
  show: (envelope: ModeloWorkbenchFormProjectionV1) => void;
}) {
  return useCallback(async () => {
    const base = shownEnvelope.current;
    if (!base) return reread();
    const ticket = ++latest.current;
    const before = holds.get(target);
    const marked = before ? holds.readBegan(before) : false;
    const overtaken = () =>
      newest.current !== null && newest.current.ticket > ticket
        ? newest.current.result
        : false;
    const result = (async () => {
      try {
        const run = await runOperation(
          port,
          () =>
            port.submit("modelo.work.filing_state", {
              work_unit_id: workUnitId,
              output_language: language,
            }),
          () => ticket === latest.current,
        );
        if (ticket !== latest.current) return overtaken();
        if (run.kind !== "settled" || !answersFor(base, run.result))
          return await reread();
        const next = withFilingState(base, run.result);
        shownEnvelope.current = next;
        if (kept) kept.form = { workUnitId, language, envelope: next };
        show(next);
        if (before) holds.readCompleted(before);
        return true;
      } finally {
        if (marked && before) holds.readEnded(before);
      }
    })();
    newest.current = { ticket, result };
    return result;
  }, [
    port,
    workUnitId,
    language,
    holds,
    target,
    kept,
    latest,
    newest,
    shownEnvelope,
    reread,
    show,
  ]);
}
