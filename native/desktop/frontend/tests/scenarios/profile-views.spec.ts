import { expect, test } from "@playwright/test";
import type {
  FilingCalendar,
  NotificationsSummary,
  ProfileViews,
} from "../../src/shell/views";

test("profile reads hide previous snapshots on the first commit and ignore late replies", async ({
  page,
}) => {
  await page.goto("/scenarios.html?scenario=signed-out&bar=off");
  await page.waitForFunction(() => Boolean(window.__scenarioModules));
  const result = await page.evaluate(async () => {
    const { react, dom, client, calendar, messages } =
      await window.__scenarioModules!.profileViews();
    const calendarRequests: {
      resolve(value: FilingCalendar): void;
      reject(error: Error): void;
    }[] = [];
    const messageRequests: {
      resolve(value: NotificationsSummary): void;
      reject(error: Error): void;
    }[] = [];
    const views: ProfileViews = {
      filingCalendar: () =>
        new Promise((resolve, reject) => {
          calendarRequests.push({ resolve, reject });
        }),
      notifications: () =>
        new Promise((resolve, reject) => {
          messageRequests.push({ resolve, reject });
        }),
    };
    const snapshot: FilingCalendar = {
      range: { from_date: "2026-01-01", to_date: "2026-12-31" },
      entries: [],
      events: [],
      warnings: [],
      generated_at: "profile-a",
      coverage: {
        surfaced: [],
        confidently_excluded: [],
        advised: [],
        out_of_scope: [],
      },
      suppressed_entries: [],
    };
    let refusals = 0;
    const refused = () => refusals++;
    const commits: {
      reader: string | null;
      calendar: string;
      messages: string;
    }[] = [];
    let refresh = () => {};
    function Probe({ reader }: { reader: string | null }) {
      const filing = calendar.useFilingCalendar(views, reader, true, refused);
      const summary = messages.useMessages(views, reader, refused);
      react.useLayoutEffect(() => {
        refresh = filing.refresh;
        commits.push({
          reader,
          calendar: filing.state.kind,
          messages: summary.kind,
        });
      });
      return null;
    }
    const container = document.createElement("div");
    document.body.append(container);
    const root = client.createRoot(container);
    const render = (reader: string | null) =>
      dom.flushSync(() => root.render(react.createElement(Probe, { reader })));
    const settle = () =>
      new Promise((resolve) => window.setTimeout(resolve, 30));
    try {
      render("a");
      calendarRequests[0]!.resolve(snapshot);
      messageRequests[0]!.resolve({
        captured_at: "profile-a",
        row_count: 9,
        unread: 9,
      });
      await settle();
      const ready = commits.at(-1);
      const beforeSwitch = commits.length;
      render("b");
      const firstB = commits[beforeSwitch];
      render(null);
      const beforeRefresh = calendarRequests.length;
      refresh();
      const afterRefresh = calendarRequests.length;
      calendarRequests[1]!.reject(new Error("late old profile"));
      messageRequests[1]!.reject(new Error("late old profile"));
      await settle();
      const withheld = commits.at(-1);
      render("c");
      dom.flushSync(() => root.unmount());
      calendarRequests[2]!.reject(new Error("after unmount"));
      messageRequests[2]!.reject(new Error("after unmount"));
      await settle();
      return { ready, firstB, withheld, beforeRefresh, afterRefresh, refusals };
    } finally {
      container.remove();
    }
  });
  expect(result.ready).toEqual({
    reader: "a",
    calendar: "ready",
    messages: "ready",
  });
  expect(result.firstB).toEqual({
    reader: "b",
    calendar: "loading",
    messages: "unknown",
  });
  expect(result.withheld).toEqual({
    reader: null,
    calendar: "withheld",
    messages: "unknown",
  });
  expect(result.afterRefresh).toBe(result.beforeRefresh);
  expect(result.refusals).toBe(0);
});
