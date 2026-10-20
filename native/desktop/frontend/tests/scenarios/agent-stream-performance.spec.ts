import { expect, test } from "@playwright/test";
import type { AgentStreamEvent } from "../../src/shell/agentSession";
import {
  agentColumn,
  agentTurns,
  ask,
  conversation,
  messageField,
  settled,
} from "../support/agent";
import { label } from "../support/strings";

declare global {
  interface Window {
    __performanceEmit?: (event: AgentStreamEvent) => void;
    __transcriptObservations?: number;
    __snapshotReads?: number;
  }
}

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.clear();
    const Observer = window.ResizeObserver;
    window.ResizeObserver = class extends Observer {
      observe(target: Element, options?: ResizeObserverOptions) {
        if (target.getAttribute("role") === "log")
          window.__transcriptObservations =
            (window.__transcriptObservations ?? 0) + 1;
        super.observe(target, options);
      }
    };
  });
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

test("a host snapshot serves the conversation without separate history and pending reads", async ({
  page,
}) => {
  await page.evaluate(() => {
    const views = window.__fixtureAgentViews!;
    const session = window.__fixtureAgentSession!;
    const history = views.history.bind(views);
    const pending = session.pending.bind(session);
    views.snapshot = async (id) => {
      window.__snapshotReads = (window.__snapshotReads ?? 0) + 1;
      return { history: await history(id), pending: await pending(id) };
    };
    views.history = () => {
      throw new Error("Separate history read");
    };
    session.pending = () => {
      throw new Error("Separate pending read");
    };
  });
  await ask(page, "Use the combined read.");
  await settled(page);
  await expect(agentTurns(page)).toContainText("Use the combined read.");
  expect(
    await page.evaluate(() => window.__snapshotReads),
  ).toBeGreaterThanOrEqual(2);
  await expect(agentColumn(page).getByRole("alert")).toHaveCount(0);
});

test("streaming keeps one scroll observer and respects a reader above the newest text", async ({
  page,
}) => {
  await page.evaluate(() => {
    const session = window.__fixtureAgentSession!;
    const observe = session.observe.bind(session);
    session.observe = (id, listener) => {
      window.__performanceEmit = listener;
      return observe(id, listener);
    };
  });
  await ask(page, "Begin.");
  await settled(page);
  const observations = await page.evaluate(
    () => window.__transcriptObservations,
  );
  await page.evaluate(() => {
    const emit = window.__performanceEmit!;
    emit({ type: "reply_started", reply_id: "stream-test" });
    for (let i = 1; i <= 200; i += 1)
      emit({
        type: "text",
        reply_id: "stream-test",
        message_id: "text",
        sequence: i,
        delta: `Line ${i}\n\n`,
      });
  });
  await expect(agentTurns(page).last()).toContainText("Line 200");
  const log = conversation(page);
  await expect
    .poll(() =>
      log.evaluate((el) => el.scrollHeight - el.scrollTop - el.clientHeight),
    )
    .toBeLessThanOrEqual(8);
  await log.evaluate((el) => {
    el.scrollTop = 0;
  });
  await expect.poll(() => log.evaluate((el) => el.scrollTop)).toBe(0);
  // Let the actual scroll event reach the component before more growth.
  await page.evaluate(
    () =>
      new Promise<void>((resolve) =>
        requestAnimationFrame(() => requestAnimationFrame(() => resolve())),
      ),
  );
  await page.evaluate(() => {
    window.__performanceEmit!({
      type: "text",
      reply_id: "stream-test",
      message_id: "text",
      sequence: 201,
      delta: "Reader stays here.\n\n",
    });
  });
  await expect(agentTurns(page).last()).toContainText("Reader stays here.");
  expect(await log.evaluate((el) => el.scrollTop)).toBe(0);
  expect(await page.evaluate(() => window.__transcriptObservations)).toBe(
    observations,
  );
  await log.evaluate((el) => {
    el.scrollTop = el.scrollHeight;
  });
  await page.evaluate(
    () =>
      new Promise<void>((resolve) =>
        requestAnimationFrame(() => requestAnimationFrame(() => resolve())),
      ),
  );
  await page.evaluate(() => {
    window.__performanceEmit!({
      type: "text",
      reply_id: "stream-test",
      message_id: "text",
      sequence: 202,
      delta: "Following again.\n\n",
    });
  });
  await expect(agentTurns(page).last()).toContainText("Following again.");
  await expect
    .poll(() =>
      log.evaluate((el) => el.scrollHeight - el.scrollTop - el.clientHeight),
    )
    .toBeLessThanOrEqual(8);
});
