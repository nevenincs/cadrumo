import { expect, test } from "@playwright/test";
import type { LedgerOutcome } from "../src/shell/ledger";
import type { ModeloPort } from "../src/shell/modelo";
import { runOperation } from "../src/components/modelo/dialogs/operationRun";

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
  const calls = { observe: 0 };
  const port = {
    observe: () => {
      const next = observed[calls.observe];
      calls.observe += 1;
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
  });
});
