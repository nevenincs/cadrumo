import { useCallback, useEffect, useState } from "react";
import type { ModeloPort } from "../../../shell/modelo";
import type { OutputLanguage } from "../../../shell/modeloContract/modelo";
import type { ModeloWorkMetadataSnapshot } from "../../../shell/modeloContract/modeloWork";
import type { ModeloWorkHistoryEntryV1 } from "../../../shell/modeloContract/modeloWorkHistory";
import type { ModeloWorkbenchFormProjectionV1 } from "../../../shell/modeloContract/modeloWorkForm";

// The declaration's record and its history, as the History view shows them.
// Both reads go through the host's one serial lane for the profile, so a read
// asked again for a declaration that has not changed delays every read behind
// it, the form's own included. They are asked once per revision of the
// declaration: showing the view again, or coming back to the page, reuses the
// answers while the form read says the same revision and no write was sent.

/** The answers asked for one revision of one declaration, answered or not. */
type HeldHistoryRead = {
  revision: string;
  unit: Promise<ModeloWorkMetadataSnapshot | null>;
  entries: Promise<ModeloWorkHistoryEntryV1[] | null>;
};

/** Where the answers are held while the page is away, with the count of the
 * writes sent on the declarations it holds: a write retires every answer read
 * before it, whatever the form read after it says. */
type HistoryMemory = {
  history?: HeldHistoryRead;
  written?: number;
};

/** The revision the answers stand for: the declaration, the language, the
 * writes sent, and what the form read says the record, calculation, check,
 * filing and receipt are at. */
export function historyRevision(
  envelope: ModeloWorkbenchFormProjectionV1,
  language: OutputLanguage,
  written: number,
): string {
  const baseline = envelope.admitted_baseline;
  return JSON.stringify([
    envelope.profile_id,
    envelope.work_unit_id,
    language,
    written,
    envelope.registry_revision_id,
    envelope.calculation_revision_id,
    envelope.verification_report_id,
    baseline?.work_unit_record_digest ?? null,
    baseline?.calculation_head_digest ?? null,
    envelope.form.form.edit_closure,
    envelope.header.file,
    envelope.receipt,
  ]);
}

async function readUnit(
  port: ModeloPort,
  workUnit: string,
): Promise<ModeloWorkMetadataSnapshot | null> {
  try {
    const outcome = await port.submit("modelo.work.metadata", {
      work_unit_id: workUnit,
    });
    return outcome.kind === "settled" ? outcome.result.unit : null;
  } catch {
    return null;
  }
}

async function readEntries(
  port: ModeloPort,
  workUnit: string,
  language: OutputLanguage,
): Promise<ModeloWorkHistoryEntryV1[] | null> {
  try {
    const outcome = await port.submit("modelo.work.history", {
      work_unit_id: workUnit,
      output_language: language,
    });
    return outcome.kind === "settled" ? outcome.result.entries : null;
  } catch {
    return null;
  }
}

/**
 * The record and history of the declaration `envelope` shows, read while
 * `wanted`. `ask` makes sure the answers for the form read now are asked,
 * and resolves once both have answered.
 */
export function useHistoryRead({
  port,
  envelope,
  language,
  wanted,
  memory,
}: {
  port: ModeloPort;
  envelope: ModeloWorkbenchFormProjectionV1;
  language: OutputLanguage;
  wanted: boolean;
  memory: HistoryMemory;
}) {
  const [unit, setUnit] = useState<ModeloWorkMetadataSnapshot | null>(null);
  const [entries, setEntries] = useState<ModeloWorkHistoryEntryV1[] | null>(
    null,
  );
  const held = useCallback(
    (shown: ModeloWorkbenchFormProjectionV1): HeldHistoryRead => {
      const revision = historyRevision(shown, language, memory.written ?? 0);
      const kept = memory.history;
      if (kept?.revision === revision) return kept;
      const workUnit = shown.work_unit_id;
      const asked: HeldHistoryRead = {
        revision,
        unit: readUnit(port, workUnit),
        entries: readEntries(port, workUnit, language),
      };
      memory.history = asked;
      // An answer that did not come is not held: the next showing asks again.
      void Promise.all([asked.unit, asked.entries]).then(([u, e]) => {
        if ((u === null || e === null) && memory.history === asked)
          memory.history = undefined;
      });
      return asked;
    },
    [port, language, memory],
  );
  useEffect(() => {
    if (!wanted) return;
    let current = true;
    const asked = held(envelope);
    void asked.unit.then((answer) => {
      if (current) setUnit(answer);
    });
    void asked.entries.then((answer) => {
      if (current) setEntries(answer);
    });
    return () => {
      current = false;
    };
  }, [wanted, envelope, held]);
  const ask = useCallback(
    async (shown: ModeloWorkbenchFormProjectionV1) => {
      const asked = held(shown);
      const [answeredUnit, answeredEntries] = await Promise.all([
        asked.unit,
        asked.entries,
      ]);
      setUnit(answeredUnit);
      setEntries(answeredEntries);
    },
    [held],
  );
  return { unit, entries, ask };
}
