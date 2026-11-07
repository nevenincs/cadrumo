import { expect, test } from "@playwright/test";
import type { LedgerOutcome } from "../src/shell/ledger";
import type { ModeloPort } from "../src/shell/modelo";
import { runOperation } from "../src/components/modelo/dialogs/operationRun";
import { fixtureYear } from "../src/dev/fixtureDates";

// One modelo write as the review and the Export and record view send it:
// sent once, followed with observe while it runs, and unknown whenever its
// settlement was not seen. Nothing here is sent twice.

const settled = (id = "op-1"): LedgerOutcome => ({
  kind: "settled",
  operation_id: id,
  revision: 3,
  result: { ok: true },
});
const running = (id = "op-1"): LedgerOutcome => ({
  kind: "running",
  operation_id: id,
  revision: 1,
  cancellable: false,
});
const rejection = (code: string, operation_id: string | null = null) =>
  Object.assign(new Error(code), { code, operation_id });

/** A port whose observe answers `observed` in turn, counting its calls. */
function observing(observed: (() => LedgerOutcome)[]) {
  const calls = { observe: 0, operationIds: [] as string[] };
  const port = {
    observe: (operationId: string) => {
      const next = observed[calls.observe];
      calls.observe += 1;
      calls.operationIds.push(operationId);
      return Promise.resolve().then(() => {
        if (!next) throw rejection("unknown");
        return next();
      });
    },
  } as unknown as ModeloPort;
  return { port, calls };
}

test("a settled write answers its result without observing", async () => {
  const { port, calls } = observing([]);
  let sent = 0;
  const run = await runOperation(
    port,
    () => {
      sent += 1;
      return Promise.resolve(settled());
    },
    () => true,
  );
  expect(run).toEqual({ kind: "settled", result: { ok: true } });
  expect(sent).toBe(1);
  expect(calls.observe).toBe(0);
});

test("a running write is observed until it settles", async () => {
  const { port, calls } = observing([() => running(), () => settled()]);
  const run = await runOperation(
    port,
    () => Promise.resolve(running()),
    () => true,
  );
  expect(run.kind).toBe("settled");
  expect(calls.observe).toBe(2);
});

test("a running write whose observation fails is unknown, never resent", async () => {
  const { port } = observing([
    () => {
      throw rejection("unavailable");
    },
  ]);
  let sent = 0;
  const run = await runOperation(
    port,
    () => {
      sent += 1;
      return Promise.resolve(running("op-7"));
    },
    () => true,
  );
  expect(run).toEqual({ kind: "unknown", operationId: "op-7" });
  expect(sent).toBe(1);
});

test("a write whose page stops watching is unknown", async () => {
  const { port, calls } = observing([() => settled()]);
  const run = await runOperation(
    port,
    () => Promise.resolve(running("op-9")),
    () => false,
  );
  expect(run).toEqual({ kind: "unknown", operationId: "op-9" });
  expect(calls.observe).toBe(0);
});

test("a write that pauses for a review is not followed here", async () => {
  const { port } = observing([]);
  const run = await runOperation(
    port,
    () =>
      Promise.resolve({
        kind: "review",
        operation_id: "op-3",
        revision: 2,
        cancellable: true,
      } as LedgerOutcome),
    () => true,
  );
  expect(run).toEqual({ kind: "unknown", operationId: "op-3" });
});

test("rejections are told apart by what reached the runtime", async () => {
  const { port } = observing([]);
  const after = (error: Error) =>
    runOperation(
      port,
      () => Promise.reject(error),
      () => true,
    );
  expect(await after(rejection("unknown", "op-4"))).toEqual({
    kind: "unknown",
    operationId: "op-4",
  });
  expect(await after(rejection("saved_unread", "op-5"))).toEqual({
    kind: "saved_unread",
  });
  expect(await after(rejection("unavailable"))).toEqual({
    kind: "not_sent",
    code: "unavailable",
  });
  expect(await after(rejection("refused", "op-6"))).toEqual({
    kind: "refused",
    operationId: "op-6",
    reason: null,
    words: null,
    step: null,
    detail: null,
  });
  expect(await after(rejection("refused"))).toEqual({
    kind: "not_sent",
    code: "refused",
  });
  // Anything the host did not answer never reached it.
  expect(await after(new Error("network"))).toEqual({
    kind: "not_sent",
    code: "unavailable",
  });
});

test("a rejected submission reads its served refusal without sending again", async () => {
  const { port, calls } = observing([
    () => ({
      kind: "refused",
      operation_id: "op-refused",
      revision: 2,
      reason: "observed_reason",
      detail: {
        detail_version: 1,
        kind: "operation_error",
        error_code: null,
        message_key: null,
        context: [],
        context_entries_omitted: 0,
        precondition_verdict_json: null,
        refusal_words: "The backend served this explanation.",
      },
    }),
  ]);
  let sent = 0;
  const run = await runOperation(
    port,
    () => {
      sent += 1;
      return Promise.reject(
        Object.assign(rejection("refused", "op-refused"), {
          reason: "original_reason",
          detail: { refusal_words: "Untrusted rejection detail" },
        }),
      );
    },
    () => true,
  );
  expect(run).toEqual({
    kind: "refused",
    operationId: "op-refused",
    reason: "original_reason",
    words: "The backend served this explanation.",
    step: null,
    detail: null,
  });
  expect(sent).toBe(1);
  expect(calls.operationIds).toEqual(["op-refused"]);
});

test("an unreadable refusal keeps its original reason and no invented words", async () => {
  const { port, calls } = observing([
    () => {
      throw rejection("unavailable");
    },
  ]);
  let sent = 0;
  const run = await runOperation(
    port,
    () => {
      sent += 1;
      return Promise.reject(
        Object.assign(rejection("refused", "op-refused"), {
          reason: "original_reason",
          detail: { refusal_words: "Untrusted rejection detail" },
        }),
      );
    },
    () => true,
  );
  expect(run).toEqual({
    kind: "refused",
    operationId: "op-refused",
    reason: "original_reason",
    words: null,
    step: null,
    detail: null,
  });
  expect(sent).toBe(1);
  expect(calls.operationIds).toEqual(["op-refused"]);
});

test("an unexpected observed settlement does not turn a refusal into a saved write", async () => {
  const { port, calls } = observing([() => settled("op-refused")]);
  let sent = 0;
  const run = await runOperation(
    port,
    () => {
      sent += 1;
      return Promise.reject(rejection("refused", "op-refused"));
    },
    () => true,
  );
  expect(run).toEqual({
    kind: "refused",
    operationId: "op-refused",
    reason: null,
    words: null,
    step: null,
    detail: null,
  });
  expect(sent).toBe(1);
  expect(calls.operationIds).toEqual(["op-refused"]);
});

test("a refusal observed for a different operation cannot supply its words", async () => {
  const { port, calls } = observing([
    () => ({
      kind: "refused",
      operation_id: "op-other",
      revision: 2,
      reason: null,
      detail: {
        detail_version: 1,
        kind: "operation_error",
        error_code: null,
        message_key: null,
        context: [],
        context_entries_omitted: 0,
        precondition_verdict_json: null,
        refusal_words: "An unrelated explanation.",
      },
    }),
  ]);
  let sent = 0;
  const run = await runOperation(
    port,
    () => {
      sent += 1;
      return Promise.reject(rejection("refused", "op-refused"));
    },
    () => true,
  );
  expect(run).toEqual({
    kind: "refused",
    operationId: "op-refused",
    reason: null,
    words: null,
    step: null,
    detail: null,
  });
  expect(sent).toBe(1);
  expect(calls.operationIds).toEqual(["op-refused"]);
});

test("a settled refusal names its operation", async () => {
  const { port } = observing([]);
  const run = await runOperation(
    port,
    () =>
      Promise.resolve({
        kind: "refused",
        operation_id: "op-8",
        revision: 2,
        reason: "operation_denied",
        detail: null,
      } as LedgerOutcome),
    () => true,
  );
  expect(run).toEqual({
    kind: "refused",
    operationId: "op-8",
    reason: "operation_denied",
    words: null,
    step: null,
    detail: null,
  });
});

test("a settled refusal carries the step the backend named, and only one of a kind the window runs", async () => {
  const { port } = observing([]);
  const refusing = (next_step: unknown) =>
    runOperation(
      port,
      () =>
        Promise.resolve({
          kind: "refused",
          operation_id: "op-9",
          revision: 2,
          reason: "refused",
          detail: { refusal_words: "No quarter yet.", next_step },
        } as LedgerOutcome),
      () => true,
    );
  expect(
    await refusing({
      kind: "create_work",
      modelo: "130",
      filing_year: fixtureYear,
      period_code: "1T",
      words: "Create the first quarter",
    }),
  ).toMatchObject({
    kind: "refused",
    operationId: "op-9",
    reason: "refused",
    words: "No quarter yet.",
    step: {
      kind: "create_work",
      modelo: "130",
      filing_year: fixtureYear,
      period_code: "1T",
      words: "Create the first quarter",
    },
  });
  expect(
    await refusing({
      kind: "calculate_work",
      work_unit_id: "a".repeat(64),
      words: "Calculate it",
    }),
  ).toMatchObject({
    step: {
      kind: "calculate_work",
      work_unit_id: "a".repeat(64),
      words: "Calculate it",
    },
  });
  // A kind this window does not run, an address it cannot run and a step
  // without words are not offered.
  for (const unrunnable of [
    { kind: "file_work", work_unit_id: "a".repeat(64), words: "File it" },
    { kind: "calculate_work", words: "Calculate it" },
    { kind: "create_work", modelo: "130", words: "Create it" },
    { kind: "calculate_work", work_unit_id: "a".repeat(64), words: "" },
    "calculate_work",
  ])
    expect(await refusing(unrunnable)).toMatchObject({ step: null });
});

const failedTerminal = {
  operation_id: "a".repeat(64),
  definition_id: "modelo.work.calculate",
  effect: "unknown" as const,
  refusal_words: "Review the invoice evidence before continuing.",
};

test("a known failed calculation preserves served words and unknown effects without another submission", async () => {
  const { port, calls } = observing([]);
  let sent = 0;
  const run = await runOperation(
    port,
    async () => {
      sent++;
      throw Object.assign(rejection("unknown", failedTerminal.operation_id), {
        terminal_failure: failedTerminal,
        detail: { private_context: "canary" },
      });
    },
    () => true,
  );
  expect(run).toEqual({
    kind: "unknown",
    operationId: failedTerminal.operation_id,
    terminalFailure: failedTerminal,
  });
  expect(JSON.stringify(run)).not.toContain("canary");
  expect(sent).toBe(1);
  expect(calls.observe).toBe(0);
});

test("a terminal failure observed after running keeps its exact words and operation identity", async () => {
  const { port } = observing([
    () => {
      throw Object.assign(rejection("unknown", failedTerminal.operation_id), {
        terminal_failure: failedTerminal,
      });
    },
  ]);
  const run = await runOperation(
    port,
    () => Promise.resolve(running(failedTerminal.operation_id)),
    () => true,
  );
  expect(run).toEqual({
    kind: "unknown",
    operationId: failedTerminal.operation_id,
    terminalFailure: failedTerminal,
  });
});

test("a failure for another observed operation cannot authorize reviewing the pending calculation", async () => {
  const other = "b".repeat(64);
  const { port } = observing([
    () => {
      throw Object.assign(rejection("unknown", other), {
        terminal_failure: { ...failedTerminal, operation_id: other },
      });
    },
  ]);
  const run = await runOperation(
    port,
    () => Promise.resolve(running(failedTerminal.operation_id)),
    () => true,
  );
  expect(run).toEqual({
    kind: "unknown",
    operationId: failedTerminal.operation_id,
  });
});

test("malformed terminal evidence is discarded rather than treated as a stopped operation", async () => {
  const { port } = observing([]);
  for (const malformed of [
    { ...failedTerminal, operation_id: "b".repeat(64) },
    { ...failedTerminal, effect: "none" },
    { ...failedTerminal, effect: "in_flight" },
    { ...failedTerminal, definition_id: "private/invalid" },
    { ...failedTerminal, refusal_words: "x".repeat(2049) },
    { ...failedTerminal, refusal_words: { message: "canary" } },
  ]) {
    const run = await runOperation(
      port,
      async () => {
        throw Object.assign(rejection("unknown", failedTerminal.operation_id), {
          terminal_failure: malformed,
        });
      },
      () => true,
    );
    expect(run).toEqual({
      kind: "unknown",
      operationId: failedTerminal.operation_id,
    });
  }
});
