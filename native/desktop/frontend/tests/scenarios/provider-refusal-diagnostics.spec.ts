import { expect, test, type Page } from "@playwright/test";

// A provider settings command rejects with either the host's application
// error, which names its operation, or its service's own refusal: a closed
// code with the served cause and log reference beside it, and no operation.
// The diagnostics relay admits only its own closed codes, so the window
// records a service refusal as the relay's `refused` with the refusal's code
// as the reason, as the host records it, rather than a code the relay drops.
// A native build recorded a busy sign-in start with no code at all.

type Report = {
  event: string;
  level: string;
  command: string | null;
  code: string | null;
  reason?: string;
};

async function rejected(target: Page, failure: object): Promise<Report[]> {
  await target.goto("/scenarios.html?scenario=signed-out&bar=off");
  await target.waitForFunction(() => Boolean(window.__scenarioModules));
  return target.evaluate(async (failure) => {
    const reports: Report[] = [];
    Object.assign(window, {
      __CADRUMO_SHELL__: { token: "f".repeat(64) },
      __TAURI_INTERNALS__: {
        async invoke(command: string, args: unknown) {
          if (command === "desktop_frontend_diagnostic") {
            reports.push((args as { report: Report }).report);
            return null;
          }
          if (command === "provider_sign_in_start") throw failure;
          return null;
        },
      },
    });
    const { tauriHost } = await window.__scenarioModules!.tauriHost();
    await tauriHost()
      .providerSettings!.signIn!.start({
        provider: "example",
        revision: "0".repeat(64),
        method: "browser",
      })
      .catch(() => null);
    await new Promise((resolve) => setTimeout(resolve, 100));
    return reports.filter((report) => report.event === "command_rejected");
  }, failure);
}

test("a busy sign-in start is recorded as refused, with its code as the reason", async ({
  page: target,
}) => {
  const reports = await rejected(target, {
    code: "busy",
    cause: "sign_in_in_progress",
    log_ref: "9eb9ca70-7425-40d5-b3a8-1ee20b8d52ac",
  });
  expect(reports).toMatchObject([
    {
      level: "WARNING",
      command: "provider_sign_in_start",
      code: "refused",
      reason: "busy",
    },
  ]);
  expect(JSON.stringify(reports)).not.toContain("9eb9ca70");
});

test("a host application error keeps its own code and reason", async ({
  page: target,
}) => {
  const reports = await rejected(target, {
    code: "read_failed",
    operation: "cli",
    message: "The command output could not be read.",
    reason: "agent_admin_unavailable",
  });
  expect(reports).toMatchObject([
    {
      level: "ERROR",
      command: "provider_sign_in_start",
      code: "read_failed",
      reason: "agent_admin_unavailable",
    },
  ]);
});
