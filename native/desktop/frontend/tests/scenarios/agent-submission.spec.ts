import { expect, test, type Page } from "@playwright/test";
import {
  agentColumn,
  ask,
  conversation,
  messageField,
  personTurns,
  settled,
} from "../support/agent";
import { label } from "../support/strings";

declare global {
  interface Window {
    __submissionGate?: {
      entered: boolean;
      completed: boolean;
      release(): void;
      fail(): void;
    };
  }
}

type Delay = "start" | "observe" | "send" | "acknowledgement" | "history";

// Control the scenario transport, while the real column, composer, live
// conversation and transcript handle every intermediate state.
async function hold(page: Page, phase: Delay) {
  await page.evaluate((phase) => {
    const session = window.__fixtureAgentSession;
    const views = window.__fixtureAgentViews;
    if (!session || !views) throw new Error("No fixture agent");
    let release = () => {};
    let fail = () => {};
    const waiting = new Promise<void>((resolve, reject) => {
      release = resolve;
      fail = () => reject(new Error("agent_service_failed"));
    });
    const gate = {
      entered: false,
      completed: false,
      release,
      fail,
    };
    window.__submissionGate = gate;
    const wait = async () => {
      gate.entered = true;
      await waiting;
    };
    switch (phase) {
      case "start": {
        const original = session.startConversation;
        session.startConversation = async () => {
          session.startConversation = original;
          await wait();
          const answer = await original();
          gate.completed = true;
          return answer;
        };
        break;
      }
      case "observe": {
        const original = session.observe;
        session.observe = async (...args) => {
          session.observe = original;
          await wait();
          const answer = await original(...args);
          gate.completed = true;
          return answer;
        };
        break;
      }
      case "send":
      case "acknowledgement": {
        const original = session.send;
        session.send = async (request) => {
          session.send = original;
          if (phase === "send") await wait();
          const answer = await original(request);
          if (phase === "acknowledgement") await wait();
          gate.completed = true;
          return answer;
        };
        break;
      }
      case "history": {
        const original = views.history;
        views.history = async (id) => {
          views.history = original;
          const snapshot = await original(id);
          await wait();
          gate.completed = true;
          return snapshot;
        };
      }
    }
  }, phase);
}

const entered = (page: Page) =>
  expect
    .poll(() => page.evaluate(() => window.__submissionGate?.entered))
    .toBe(true);
const release = (page: Page) =>
  page.evaluate(() => window.__submissionGate?.release());

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => localStorage.clear());
  await page.goto("/scenarios.html?scenario=signed-in&latency=0&bar=off");
  await messageField(page).fill("Ready");
  await expect(
    agentColumn(page).getByRole("button", {
      name: label("desktop.agent.send"),
      exact: true,
    }),
  ).not.toHaveAttribute("aria-disabled", "true");
  await messageField(page).fill("");
});

for (const phase of ["start", "observe", "send"] as const) {
  test(`the message stays visible while ${phase} is pending`, async ({
    page,
  }) => {
    await hold(page, phase);
    await ask(page, "Review my invoices.");
    await entered(page);
    await expect(messageField(page)).toHaveValue("");
    await expect(personTurns(page)).toHaveCount(1);
    await expect(personTurns(page)).toContainText("Review my invoices.");
    await expect(personTurns(page).getByRole("status")).toHaveText(
      label("desktop.agent.sending"),
    );
    await expect(conversation(page)).not.toContainText(
      label("desktop.agent.transcript_empty"),
    );
    await release(page);
    await settled(page);
    await expect(personTurns(page)).toHaveCount(1);
    await expect(personTurns(page)).toContainText("Review my invoices.");
    await expect(personTurns(page).getByRole("status")).toHaveCount(0);
  });
}

test("a slow acknowledgement does not move or duplicate a message already in history", async ({
  page,
}) => {
  await hold(page, "acknowledgement");
  await ask(page, "Review my invoices.");
  await entered(page);
  await expect(personTurns(page)).toHaveCount(1);
  await expect(conversation(page).locator("ol > li").first()).toContainText(
    "Review my invoices.",
  );
  // Wait for settlement and its history read before acknowledging the send.
  await expect
    .poll(() =>
      page.evaluate(
        () =>
          (window.__scenarioHostCalls ?? []).filter((call) =>
            call.startsWith("agentHistory "),
          ).length,
      ),
    )
    .toBeGreaterThanOrEqual(2);
  await expect(conversation(page)).not.toContainText(
    label("desktop.agent.working"),
  );
  await release(page);
  await settled(page);
  await expect(personTurns(page)).toHaveCount(1);
});

test("an acknowledged message stays visible through a stale initial history read", async ({
  page,
}) => {
  await hold(page, "history");
  await ask(page, "Review my invoices.");
  await entered(page);
  await expect(personTurns(page)).toHaveCount(1);
  await expect(personTurns(page)).not.toContainText(
    label("desktop.agent.sending"),
  );
  await expect(conversation(page)).not.toContainText(
    label("desktop.agent.transcript_empty"),
  );
  await release(page);
  await settled(page);
  await expect(personTurns(page)).toHaveCount(1);
});

for (const phase of ["start", "observe", "send"] as const) {
  test(`a failed ${phase} restores the draft and clears the sending indicator`, async ({
    page,
  }) => {
    await hold(page, phase);
    await ask(page, "Keep my draft.");
    await entered(page);
    await expect(personTurns(page)).toContainText("Keep my draft.");
    await page.evaluate(() => window.__submissionGate?.fail());
    await expect(messageField(page)).toHaveValue("Keep my draft.");
    await expect(personTurns(page)).toHaveCount(0);
    await expect(agentColumn(page).getByRole("alert").first()).toBeVisible();
    await expect(agentColumn(page)).not.toContainText(
      label("desktop.agent.sending"),
    );
    await ask(page, "Keep my draft.");
    await settled(page);
    await expect(personTurns(page)).toHaveCount(1);
  });
}

test("an identical follow-up stays beside the earlier message while sending", async ({
  page,
}) => {
  await ask(page, "Review my invoices.");
  await settled(page);
  await hold(page, "send");
  await ask(page, "Review my invoices.");
  await entered(page);
  await expect(personTurns(page)).toHaveCount(2);
  await expect(personTurns(page).first().getByRole("status")).toHaveCount(0);
  await expect(personTurns(page).last().getByRole("status")).toHaveText(
    label("desktop.agent.sending"),
  );
  await release(page);
  await settled(page);
  await expect(personTurns(page)).toHaveCount(2);
});

test("a late send cannot add its message to a new conversation", async ({
  page,
}) => {
  await hold(page, "send");
  await ask(page, "The previous conversation.");
  await entered(page);
  await agentColumn(page)
    .getByRole("button", { name: label("desktop.agent.new_conversation") })
    .click();
  await release(page);
  await expect
    .poll(() => page.evaluate(() => window.__submissionGate?.completed))
    .toBe(true);
  await expect(agentColumn(page)).not.toContainText(
    "The previous conversation.",
  );
  await ask(page, "The new conversation.");
  await settled(page);
  await expect(personTurns(page)).toHaveCount(1);
  await expect(personTurns(page)).toContainText("The new conversation.");
});
