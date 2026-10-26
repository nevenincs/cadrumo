import { expect, test } from "@playwright/test";
import { agentColumn, messageField, personTurns } from "../support/agent";
import { label } from "../support/strings";

test("the first activity report preserves a controlled draft and its submission", async ({
  page,
}) => {
  await page.goto("/scenarios.html?scenario=signed-in&latency=0&bar=off");
  await expect(page.locator(".titlebar .profile-name")).toBeVisible();
  const field = messageField(page);
  await field.fill("Keep this first message.");
  // The scenario host records activity in React state. Its rerender must
  // happen after the field has taken the input, even on the first report.
  await expect(field).toHaveValue("Keep this first message.");
  await expect
    .poll(() =>
      page.evaluate(
        () =>
          (window.__scenarioHostCalls ?? []).filter(
            (call) => call === "noteActivity",
          ).length,
      ),
    )
    .toBe(1);
  await expect(
    agentColumn(page).getByRole("button", {
      name: label("desktop.agent.send"),
      exact: true,
    }),
  ).not.toHaveAttribute("aria-disabled", "true");
  await field.press("Enter");
  await expect(personTurns(page)).toHaveCount(1);
  await expect(personTurns(page)).toContainText("Keep this first message.");
});

test("person input renews once; polling and synthetic events never renew", async ({
  page,
}) => {
  await page.goto("/scenarios.html?scenario=signed-in&latency=0&bar=off");
  await expect(page.locator(".titlebar .profile-name")).toBeVisible();
  const count = () =>
    page.evaluate(
      () =>
        (window.__scenarioHostCalls ?? []).filter(
          (call) => call === "noteActivity",
        ).length,
    );
  expect(await count()).toBe(0);
  await page.evaluate(() =>
    window.dispatchEvent(new KeyboardEvent("keydown", { key: "a" })),
  );
  expect(await count()).toBe(0);
  await page.keyboard.press("Shift");
  await expect.poll(count).toBe(1);
  await page.keyboard.press("Shift");
  expect(await count()).toBe(1);
});

test("mouse movement counts as input and remains throttled", async ({
  page,
}) => {
  await page.goto("/scenarios.html?scenario=signed-in&latency=0&bar=off");
  await expect(page.locator(".titlebar .profile-name")).toBeVisible();
  const count = () =>
    page.evaluate(
      () =>
        (window.__scenarioHostCalls ?? []).filter(
          (call) => call === "noteActivity",
        ).length,
    );
  await page.evaluate(() =>
    window.dispatchEvent(new PointerEvent("pointermove")),
  );
  expect(await count()).toBe(0);
  await page.mouse.move(100, 100);
  await expect.poll(count).toBe(1);
  await page.mouse.move(150, 150);
  expect(await count()).toBe(1);
});
