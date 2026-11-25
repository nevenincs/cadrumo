import { expect, test, type Page } from "@playwright/test";

// What the window tells the host about its own failures, through the real
// diagnostics relay against a recording invoke boundary. Each record says what
// happened, as a value-free template and the script it came from, and a
// refusal carries the backend's own code beside the relay's; no value the
// window held ever reaches the record.

type Report = {
  event: string;
  level: string;
  command: string | null;
  code: string | null;
  reason?: string;
  template?: string;
  module?: string;
  line?: number;
  column?: number;
};

/** A synthetic private value: a NIF-shaped canary. */
const CANARY = "12345678Z";

type Act =
  | "prop-warning"
  | "detail-less-error"
  | "thrown-error"
  | "unknown-failure"
  | "refusal";

async function relay(target: Page, act: Act): Promise<Report[]> {
  await target.goto("/scenarios.html?scenario=signed-out&bar=off");
  await target.waitForFunction(() => Boolean(window.__scenarioModules));
  return target.evaluate(
    async ({ act, canary }) => {
      const reports: Report[] = [];
      Object.assign(window, {
        __CADRUMO_SHELL__: { token: "f".repeat(64) },
        __TAURI_INTERNALS__: {
          async invoke(command: string, args: unknown) {
            if (command === "desktop_frontend_diagnostic") {
              reports.push((args as { report: Report }).report);
              return null;
            }
            if (act === "unknown-failure")
              throw {
                code: "unknown",
                reason: "ERROR_FINANCIAL_AGGREGATION_VALIDATION",
              };
            if (act === "refusal")
              throw {
                code: "refused",
                reason: "REFUSED_MODELO_CROSS_PERIOD_CLEAN_STATE",
              };
            return null;
          },
        },
      });
      const { hostCall } = await window.__scenarioModules!.hostCall();
      const call = hostCall("f".repeat(64) as never);
      const settle = () => new Promise((resolve) => setTimeout(resolve, 100));
      if (act === "prop-warning")
        console.error(
          "Warning: Failed %s type: Invalid prop `%s` of value `%s` supplied to `%s`.",
          "prop",
          "value",
          canary,
          "Progress",
        );
      if (act === "detail-less-error")
        window.dispatchEvent(new ErrorEvent("error"));
      if (act === "thrown-error")
        setTimeout(() => {
          throw new TypeError(`Cannot read the holder ${canary}`);
        });
      if (act === "unknown-failure" || act === "refusal")
        await call("modelo_submit" as never, {} as never).catch(() => null);
      await settle();
      return reports;
    },
    { act, canary: CANARY },
  );
}

const valueFree = (reports: Report[]) =>
  expect(JSON.stringify(reports)).not.toContain(CANARY);

test("a console error says what it was, with its values taken out", async ({
  page: target,
}) => {
  const reports = await relay(target, "prop-warning");
  const consoled = reports.filter((report) => report.event === "console");
  expect(consoled).toHaveLength(1);
  expect(consoled[0]).toMatchObject({ level: "ERROR", command: null });
  // The authored shape survives; the values are gone.
  expect(consoled[0]!.template).toContain("Invalid prop");
  expect(consoled[0]!.template).not.toContain("Progress");
  valueFree(reports);
});

test("an uncaught error with no detail is named as such, not left blank", async ({
  page: target,
}) => {
  const reports = await relay(target, "detail-less-error");
  const uncaught = reports.filter(
    (report) => report.event === "uncaught_error",
  );
  expect(uncaught).toHaveLength(1);
  expect(uncaught[0]!.level).toBe("ERROR");
  expect(uncaught[0]!.template).toBeTruthy();
});

test("a thrown error names its kind and keeps none of its values", async ({
  page: target,
}) => {
  const reports = await relay(target, "thrown-error");
  const uncaught = reports.filter(
    (report) => report.event === "uncaught_error",
  );
  expect(uncaught).toHaveLength(1);
  expect(uncaught[0]!.template).toContain("TypeError");
  expect(uncaught[0]!.template).toContain("Cannot read");
  valueFree(reports);
});

test("a failed command carries the backend's failure code beside the relay's", async ({
  page: target,
}) => {
  const reports = await relay(target, "unknown-failure");
  expect(
    reports.filter((report) => report.event === "command_rejected"),
  ).toMatchObject([
    {
      level: "ERROR",
      command: "modelo_submit",
      code: "unknown",
      reason: "ERROR_FINANCIAL_AGGREGATION_VALIDATION",
    },
  ]);
});

test("a refused command is recorded below an error, with the backend's refusal", async ({
  page: target,
}) => {
  const reports = await relay(target, "refusal");
  expect(
    reports.filter((report) => report.event === "command_rejected"),
  ).toMatchObject([
    {
      level: "WARNING",
      command: "modelo_submit",
      code: "refused",
      reason: "REFUSED_MODELO_CROSS_PERIOD_CLEAN_STATE",
    },
  ]);
});
