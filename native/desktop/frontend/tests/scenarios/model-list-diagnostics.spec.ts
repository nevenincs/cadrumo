import { expect, test, type Page } from "@playwright/test";

// Reading the models a person can use answers where their setup stands: the
// service still starting, signed out, the agent's catalogue not there yet.
// Each view that lists models shows that state with the step that moves it
// on, so its refusal is noted at INFO and never reported as a warning or an
// error. A refusal that is a fault, such as an answer the host cannot read,
// is still an error.

type Report = {
  event: string;
  level: string;
  command: string | null;
  code: string | null;
};

type Read = "localModels" | "localEngine" | "providerCatalog";

async function rejected(
  target: Page,
  read: Read,
  failure: object,
): Promise<Report[]> {
  await target.goto("/scenarios.html?scenario=signed-out&bar=off");
  await target.waitForFunction(() => Boolean(window.__scenarioModules));
  return target.evaluate(
    async ({ read, failure }) => {
      const reports: Report[] = [];
      Object.assign(window, {
        __CADRUMO_SHELL__: { token: "f".repeat(64) },
        __TAURI_INTERNALS__: {
          async invoke(command: string, args: unknown) {
            if (command === "desktop_frontend_diagnostic") {
              reports.push((args as { report: Report }).report);
              return null;
            }
            if (command.startsWith("agent_")) throw failure;
            return null;
          },
        },
      });
      const { tauriHost } = await window.__scenarioModules!.tauriHost();
      const session = tauriHost().agentSession!;
      await (
        read === "providerCatalog"
          ? session.providerCatalog!()
          : session[read]!()
      ).catch(() => null);
      await new Promise((resolve) => setTimeout(resolve, 100));
      return reports.filter((report) => report.event === "command_rejected");
    },
    { read, failure },
  );
}

const command: Record<Read, string> = {
  localModels: "agent_local_models",
  localEngine: "agent_local_engine",
  providerCatalog: "agent_provider_catalog",
};

for (const read of ["localModels", "localEngine", "providerCatalog"] as const)
  for (const code of [
    "agent_signed_out",
    "agent_service_busy",
    "agent_service_not_ready",
    "agent_reconnecting",
    "agent_catalog_unavailable",
  ])
    test(`${command[read]} answering ${code} is noted at INFO`, async ({
      page: target,
    }) => {
      expect(await rejected(target, read, { code })).toMatchObject([
        { level: "INFO", command: command[read], code },
      ]);
    });

test("a model list the host cannot read is still an error", async ({
  page: target,
}) => {
  expect(
    await rejected(target, "localModels", {
      code: "agent_service_failed",
      operation: "cli",
      message: "The child output could not be read",
      reason: "admin_local_models_contract",
    }),
  ).toMatchObject([
    {
      level: "ERROR",
      command: "agent_local_models",
      code: "agent_service_failed",
    },
  ]);
});
