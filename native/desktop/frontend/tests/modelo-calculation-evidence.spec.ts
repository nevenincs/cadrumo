import { expect, test } from "@playwright/test";
import { readFileSync } from "node:fs";
import {
  calculateWithEvidence,
  calculationEvidenceMemory,
  type EvidenceWriter,
  type CalculationEvidenceAnswer,
} from "../src/components/modelo/workspace/calculationEvidence";
import { runOperation } from "../src/components/modelo/dialogs/operationRun";
import {
  createModeloWriteHolds,
  declarationWriteKey,
} from "../src/shell/modeloWriteHolds";
import type { ModeloPort } from "../src/shell/modelo";
import type { ModeloWorkM303AttestationPublicResultV2 } from "../src/shell/modeloContract/modeloWork";
import type { ModeloWorkbenchFormProjectionV1 } from "../src/shell/modeloContract/modeloWorkForm";
import type { LedgerOutcome } from "../src/shell/ledger";
import { MODELO_FIXTURES } from "./support/windowFixtures";
import { fixtureInstant, fixtureYear } from "../src/dev/fixtureDates";

const envelope = (last = false) =>
  ({
    ...JSON.parse(
      readFileSync(new URL("modelo-303-1T-en.json", MODELO_FIXTURES), "utf8"),
    ),
    asks_m303_evidence: true,
    asks_modelo_390: last,
  }) as ModeloWorkbenchFormProjectionV1;
const answer: CalculationEvidenceAnswer = {
  jointReturn: false,
  observedAt: fixtureInstant(11, 3, "12:34:56.000Z"),
};
const settled = (result: unknown): LedgerOutcome => ({
  kind: "settled",
  operation_id: "op",
  revision: 2,
  result: result as Record<string, never>,
});
const refusal: LedgerOutcome = {
  kind: "refused",
  operation_id: "op",
  revision: 2,
  reason: "refused",
  detail: null,
};

function harness(last = false) {
  const form = envelope(last);
  const holds = createModeloWriteHolds();
  const target = declarationWriteKey(form.work_unit_id);
  const memory = calculationEvidenceMemory(
    holds,
    form.profile_id,
    form.work_unit_id,
  );
  const calls: { definition: string; payload: unknown }[] = [];
  const events: string[] = [];
  let current = true;
  let read = true;
  const receipt: ModeloWorkM303AttestationPublicResultV2 = {
    result_version: 2,
    profile_id: form.profile_id,
    work_unit_id: form.work_unit_id,
    filing_year: fixtureYear,
    period: { filing_year: fixtureYear, code: "4T" },
    attachment_id: "a".repeat(64),
    sha256: "a".repeat(64),
  };
  let attestation = () => Promise.resolve(settled(receipt));
  let calculation = () =>
    Promise.resolve(settled({ calculation_revision_id: "new" }));
  const port = {
    submit: async (definition: string, payload: unknown) => {
      calls.push({ definition, payload });
      events.push(definition);
      return definition === "modelo.work.m303_attestation"
        ? attestation()
        : calculation();
    },
    observe: async () => {
      throw new Error("unexpected observation");
    },
  } as unknown as ModeloPort;
  const write: EvidenceWriter = async (send, alive) => {
    if (!alive()) return null;
    const lease = holds.begin(target);
    if (!lease) return null;
    const outcome = await runOperation(port, send, alive);
    if (outcome.kind === "unknown") holds.unknown(lease, outcome.operationId);
    else if (outcome.kind === "settled" || outcome.kind === "saved_unread")
      holds.needsRead(lease, outcome.kind === "saved_unread");
    else holds.notWritten(lease);
    return alive() ? outcome : null;
  };
  const reread = async () => {
    events.push("read");
    const before = holds.get(target);
    if (read && before) holds.readCompleted(before);
    return read;
  };
  return {
    form,
    holds,
    target,
    memory,
    calls,
    events,
    receipt,
    reread,
    stale: () => {
      current = false;
    },
    failRead: () => {
      read = false;
    },
    attestation: (send: typeof attestation) => {
      attestation = send;
    },
    calculation: (send: typeof calculation) => {
      calculation = send;
    },
    run: (value: CalculationEvidenceAnswer | null = answer) =>
      calculateWithEvidence({
        envelope: form,
        answer: value,
        memory,
        port,
        write,
        reread,
        current: () => current,
      }),
  };
}

test("cancelling or leaving the election unanswered sends no mutation", async () => {
  const h = harness();
  expect(await h.run(null)).toBeNull();
  expect(h.calls).toEqual([]);
});
test("an explicit No is sent as false while preserving replay of existing operator inputs", async () => {
  const h = harness();
  await h.run();
  expect(h.calls).toEqual([
    {
      definition: "modelo.work.calculate",
      payload: {
        work_unit_id: h.form.work_unit_id,
        actor: "operator:desktop-modelo",
        ordinary_m303_filing_evidence: { joint_return_elected: false },
      },
    },
  ]);
});
test("a persisted head replays without asking or supplying new evidence", async () => {
  const h = harness(true);
  h.form.asks_m303_evidence = false;
  await h.run(null);
  expect(h.calls).toEqual([
    {
      definition: "modelo.work.calculate",
      payload: {
        work_unit_id: h.form.work_unit_id,
        actor: "operator:desktop-modelo",
      },
    },
  ]);
});
test("last-period consent is required before an attestation can be admitted", async () => {
  const h = harness(true);
  expect(await h.run({ jointReturn: false, observedAt: null })).toBeNull();
  expect(h.calls).toEqual([]);
});
test("last-period attestation is read before its returned custody pair is used", async () => {
  const h = harness(true);
  await h.run();
  expect(h.events).toEqual([
    "modelo.work.m303_attestation",
    "read",
    "modelo.work.calculate",
  ]);
  expect(h.calls[0]?.payload).toEqual({
    work_unit_id: h.form.work_unit_id,
    observed_at: answer.observedAt,
    actor: "operator:desktop-modelo",
  });
  expect(h.calls[1]?.payload).toMatchObject({
    ordinary_m303_filing_evidence: {
      joint_return_elected: false,
      m303_exonerado_390_attachment_id: h.receipt.attachment_id,
      m303_exonerado_390_sha256: h.receipt.sha256,
    },
  });
});
test("attestation refusal stops calculation and permits a deliberate new attempt", async () => {
  const h = harness(true);
  h.attestation(async () => refusal);
  expect((await h.run())?.kind).toBe("refused");
  expect(h.calls).toHaveLength(1);
  expect(h.memory.blocked).toBe(false);
});
for (const code of ["unknown", "saved_unread"])
  test(`${code} attestation remains held and is never repeated after a later read`, async () => {
    const h = harness(true);
    h.attestation(async () => {
      throw Object.assign(new Error(code), { code });
    });
    expect((await h.run())?.kind).toBe(code);
    expect(h.holds.get(h.target)).toBeDefined();
    await h.reread();
    expect((await h.run())?.kind).toBe("evidence_unavailable");
    expect(h.calls).toHaveLength(1);
  });
test("successful custody survives a subsequent calculation refusal and reopening", async () => {
  const h = harness(true);
  h.calculation(async () => refusal);
  await h.run();
  expect(
    calculationEvidenceMemory(h.holds, h.form.profile_id, h.form.work_unit_id),
  ).toBe(h.memory);
  await h.run();
  expect(h.calls.map((call) => call.definition)).toEqual([
    "modelo.work.m303_attestation",
    "modelo.work.calculate",
    "modelo.work.calculate",
  ]);
});
test("a receipt for another profile or work unit cannot be used", async () => {
  for (const change of [{ profile_id: "other" }, { work_unit_id: "other" }]) {
    const h = harness(true);
    h.attestation(async () => settled({ ...h.receipt, ...change }));
    expect((await h.run())?.kind).toBe("evidence_unavailable");
    expect(h.calls).toHaveLength(1);
    expect(h.memory.blocked).toBe(true);
  }
});
test("stale or unmounted work stops the chain after attestation admission", async () => {
  const h = harness(true);
  h.attestation(async () => {
    h.stale();
    return settled(h.receipt);
  });
  expect(await h.run()).toBeNull();
  expect(h.calls).toHaveLength(1);
  expect(h.holds.get(h.target)).toBeDefined();
  expect(h.memory.blocked).toBe(true);
});
test("a failed declaration refresh retains the receipt and blocks calculation", async () => {
  const h = harness(true);
  h.failRead();
  expect(await h.run()).toBeNull();
  expect(h.memory.receipt).toEqual(h.receipt);
  expect(h.calls).toHaveLength(1);
  expect(h.holds.get(h.target)).toBeDefined();
});
test("a competing declaration writer prevents attestation admission", async () => {
  const h = harness(true);
  h.holds.begin(h.target);
  expect(await h.run()).toBeNull();
  expect(h.calls).toEqual([]);
  expect(h.memory.blocked).toBe(false);
});
