import type { LedgerOutcome } from "../../../shell/ledger";
import {
  MODELO_ACTOR,
  calculateWorkRequest,
  type ModeloPort,
  type ModeloResult,
} from "../../../shell/modelo";
import type { ModeloWorkM303AttestationPublicResultV2 } from "../../../shell/modeloContract/modeloWork";
import type { ModeloWorkbenchFormProjectionV1 } from "../../../shell/modeloContract/modeloWorkForm";
import type { ModeloWriteHolds } from "../../../shell/modeloWriteHolds";
import type { OperationRun } from "../dialogs/operationRun";

export type CalculationEvidenceAnswer = {
  jointReturn: boolean;
  observedAt: string | null;
};
type Receipt = ModeloWorkM303AttestationPublicResultV2;
type Memory = { receipt?: Receipt; blocked: boolean };
// Session-owned custody receipts survive closing and reopening a declaration.
// No operator answer is retained here. An unread receipt must be recovered,
// never replaced by silently authoring another attestation.
const memories = new WeakMap<ModeloWriteHolds, Map<string, Memory>>();
export function calculationEvidenceMemory(
  holds: ModeloWriteHolds,
  profile: string,
  work: string,
): Memory {
  let session = memories.get(holds);
  if (!session) memories.set(holds, (session = new Map()));
  const key = JSON.stringify([profile, work]);
  let memory = session.get(key);
  if (!memory) session.set(key, (memory = { blocked: false }));
  return memory;
}
type CalculateResult = ModeloResult<"modelo.work.calculate">;
type EvidenceRun =
  OperationRun<CalculateResult> | { kind: "evidence_unavailable" } | null;
export type EvidenceWriter = <Result>(
  send: () => Promise<LedgerOutcome<Result>>,
  current: () => boolean,
) => Promise<OperationRun<Result> | null>;

/** The admitted form alone decides whether to ask. Each write uses the same
 * declaration hold; a successful attestation is read before calculation. */
export async function calculateWithEvidence({
  envelope,
  answer,
  memory,
  port,
  write,
  reread,
  current,
}: {
  envelope: ModeloWorkbenchFormProjectionV1;
  answer: CalculationEvidenceAnswer | null;
  memory: Memory;
  port: ModeloPort;
  write: EvidenceWriter;
  reread(): Promise<boolean>;
  current(): boolean;
}): Promise<EvidenceRun> {
  if (!current()) return null;
  if (!envelope.asks_m303_evidence)
    return write(
      () =>
        port.submit(
          "modelo.work.calculate",
          calculateWorkRequest(envelope.work_unit_id),
        ),
      current,
    );
  if (!answer) return null;
  let receipt = memory.receipt;
  if (envelope.asks_modelo_390) {
    if (memory.blocked) return { kind: "evidence_unavailable" };
    if (!receipt) {
      const observedAt = answer.observedAt;
      if (!observedAt) return null;
      const admitted = await write(() => {
        // Mark only after shared write admission, before sending: a lost
        // response cannot turn a later Calculate into a mutation retry.
        memory.blocked = true;
        return port.submit("modelo.work.m303_attestation", {
          work_unit_id: envelope.work_unit_id,
          observed_at: observedAt,
          actor: MODELO_ACTOR,
        });
      }, current);
      if (!admitted) return null;
      if (admitted.kind !== "settled") {
        if (admitted.kind === "refused" || admitted.kind === "not_sent")
          memory.blocked = false;
        return admitted;
      }
      receipt = admitted.result;
      if (
        receipt.profile_id !== envelope.profile_id ||
        receipt.work_unit_id !== envelope.work_unit_id
      )
        return { kind: "evidence_unavailable" };
      memory.receipt = receipt;
      memory.blocked = false;
      if (!(await reread()) || !current()) return null;
    }
    if (
      receipt.profile_id !== envelope.profile_id ||
      receipt.work_unit_id !== envelope.work_unit_id
    )
      return { kind: "evidence_unavailable" };
  }
  if (!current()) return null;
  return write(
    () =>
      port.submit("modelo.work.calculate", {
        work_unit_id: envelope.work_unit_id,
        actor: MODELO_ACTOR,
        ordinary_m303_filing_evidence: {
          joint_return_elected: answer.jointReturn,
          ...(envelope.asks_modelo_390 && receipt
            ? {
                m303_exonerado_390_attachment_id: receipt.attachment_id,
                m303_exonerado_390_sha256: receipt.sha256,
              }
            : {}),
        },
      }),
    current,
  );
}
