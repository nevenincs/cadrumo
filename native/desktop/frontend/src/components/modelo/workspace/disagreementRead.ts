import { useEffect, useRef, useState } from "react";
import {
  ledgerFailure,
  servedRefusalWords,
  type LedgerErrorDetail,
} from "../../../shell/ledger";
import type { ModeloPort } from "../../../shell/modelo";
import type { OutputLanguage } from "../../../shell/modeloContract/modelo";
import type { CreditResolutionRowProjection } from "../../../shell/modeloContract/modeloWork";
import type {
  ModeloFormIssueLine,
  ModeloWorkbenchFormProjectionV1,
} from "../../../shell/modeloContract/modeloWorkForm";

// The operator's answers to the source disagreements one calculation holds,
// as the application lists them. Which line offers to accept or to revoke,
// what each answer covers and why one was refused are all served; this keeps
// only what came back, for the calculation the form showed.

/** The answers held, from not read to answered. */
export type DisagreementsRead =
  | { phase: "idle" }
  | { phase: "reading" }
  | { phase: "ready"; rows: CreditResolutionRowProjection[] }
  /** The read did not answer; `code` is the host's closed reason. */
  | { phase: "failed"; code: string };

/** Whether the form states any disagreement an answer can address. */
export const statesDisagreement = (lines: readonly ModeloFormIssueLine[]) =>
  lines.some(
    (line) => line.finding_id !== null && line.finding_id !== undefined,
  );

/**
 * The answers the declaration holds for the calculation the form showed, in
 * `language`, read while `wanted` and only where the form states a
 * disagreement. A form read again reads them again.
 */
export function useDisagreements({
  port,
  envelope,
  language,
  wanted,
}: {
  port: ModeloPort;
  envelope: ModeloWorkbenchFormProjectionV1;
  language: OutputLanguage;
  wanted: boolean;
}): DisagreementsRead {
  const [read, setRead] = useState<DisagreementsRead>({ phase: "idle" });
  const latest = useRef(0);
  const revision = envelope.calculation_revision_id;
  const asks =
    wanted && revision !== null && statesDisagreement(envelope.issue_lines);
  useEffect(() => {
    const ticket = ++latest.current;
    if (!asks || revision === null) {
      setRead({ phase: "idle" });
      return;
    }
    setRead({ phase: "reading" });
    port
      .submit(
        "modelo.work.disagreements",
        { calculation_revision_id: revision, output_language: language },
        envelope.work_unit_id,
      )
      .then(
        (outcome) => {
          if (ticket !== latest.current) return;
          setRead(
            outcome.kind === "settled"
              ? { phase: "ready", rows: outcome.result.resolutions }
              : { phase: "failed", code: outcome.kind },
          );
        },
        (error: unknown) => {
          if (ticket === latest.current)
            setRead({ phase: "failed", code: ledgerFailure(error).code });
        },
      );
    return () => {
      latest.current += 1;
    };
  }, [asks, port, revision, language, envelope]);
  return read;
}

/** The stored acceptance a line's revocation is sent against: the active
 * answer to its disagreement, as the list served it; null where none was
 * read. */
export function activeAnswer(
  read: DisagreementsRead,
  findingId: string | null,
): CreditResolutionRowProjection | null {
  if (read.phase !== "ready" || findingId === null) return null;
  return (
    read.rows.find(
      (row) => row.finding_id === findingId && row.state === "active",
    ) ?? null
  );
}

/** The sentence the application served for an answer it refused, from the
 * refusal its result or its settled detail carries; null when it served
 * none. */
export function refusalWords(
  detail: LedgerErrorDetail | object | null | undefined,
): string | null {
  if (!detail) return null;
  const refusal = (detail as { refusal?: unknown }).refusal;
  return servedRefusalWords(refusal) ?? servedRefusalWords(detail);
}
