import { expect, test, type Page } from "@playwright/test";
import { agentColumn, scenarioOnly, send, settled } from "../support/agent";
import { label } from "../support/strings";

// Setup an assistant started waits on the person in the agent column, beside
// the agent's other approvals. The scenario host stands in for the runtime's
// setup reviews: a test raises one through `window.__scenarioSetupReviews`, as
// the agent's setup tool would, and the column finds it when a reply ends.
// The person sees the plan in plain words and answers with one press;
// nothing that identifies the request reaches the screen, and Settings has
// no setup review of its own.

const SIZE = "180 MB";

/** Words and shapes that identify a request rather than describe it. */
const INTERNAL = [
  /\b[0-9a-f]{64}\b/,
  /operation/i,
  /digest/i,
  /interaction/i,
  /revision/i,
  /playwright-browsers/,
  /expires/i,
];

type Controls = {
  raise(): void;
  change(): void;
  loseNextAnswer(): void;
  answers: ("apply" | "reject")[];
};

test.beforeEach(async ({ page: target }) => {
  scenarioOnly("the setup reviews are the scenario host's");
  await target.addInitScript(() => {
    if (sessionStorage.getItem("layout-cleared")) return;
    localStorage.clear();
    sessionStorage.setItem("layout-cleared", "1");
  });
  await target.goto(
    "/scenarios.html?scenario=signed-in&latency=0&bar=off&setupReviews=on",
  );
});

const control = <Name extends Exclude<keyof Controls, "answers">>(
  target: Page,
  name: Name,
) =>
  target.evaluate((called) => {
    const reviews = (window as unknown as { __scenarioSetupReviews?: Controls })
      .__scenarioSetupReviews;
    if (!reviews) throw new Error("no setup review controls");
    reviews[called]();
  }, name);

const answers = (target: Page) =>
  target.evaluate(
    () =>
      (window as unknown as { __scenarioSetupReviews?: Controls })
        .__scenarioSetupReviews?.answers ?? [],
  );

const setupApproval = (target: Page) =>
  agentColumn(target).getByRole("region", {
    name: label("desktop.setup_review.title"),
  });

const approve = (target: Page) =>
  setupApproval(target).getByRole("button", {
    name: label("desktop.setup.approve_size", { size: SIZE }),
    exact: true,
  });

const reject = (target: Page) =>
  setupApproval(target).getByRole("button", {
    name: label("desktop.setup_review.reject"),
    exact: true,
  });

/** The assistant starts setup and its reply ends with setup waiting. */
async function setupWaits(target: Page, message: string) {
  await control(target, "raise");
  await send(target, message);
  await settled(target);
  await expect(setupApproval(target)).toBeVisible();
}

async function noInternalWords(target: Page) {
  const text = await agentColumn(target).innerText();
  for (const word of INTERNAL) expect(text).not.toMatch(word);
}

test("an assistant's setup waits in the agent column with its plan in plain words", async ({
  page: target,
}) => {
  await expect(setupApproval(target)).toHaveCount(0);
  await setupWaits(target, "Configura el navegador.");
  const shown = setupApproval(target);
  await expect(shown).toContainText(label("desktop.setup_review.lead"));
  await expect(shown).toContainText(
    label("desktop.setup.plan_size", { size: SIZE }),
  );
  await expect(shown).toContainText(
    label("desktop.setup.plan_from", { hosts: "cdn.playwright.dev" }),
  );
  await expect(shown).toContainText(
    label("desktop.setup.plan_destination", {
      folder: label("desktop.setup_review.destination_browser"),
    }),
  );
  await noInternalWords(target);
  // The review is the agent column's alone: Settings shows none of it.
  await target.locator("[data-rail=settings]").click();
  const settings = target.getByRole("dialog", {
    name: label("desktop.settings.title"),
  });
  await expect(settings).toBeVisible();
  await expect(settings).not.toContainText(label("desktop.setup_review.title"));
  for (const word of INTERNAL)
    expect(await settings.innerText()).not.toMatch(word);
});

test("approving answers the setup once and the approval goes away", async ({
  page: target,
}) => {
  await setupWaits(target, "Configura el navegador.");
  await approve(target).click();
  await expect(setupApproval(target)).toHaveCount(0);
  expect(await answers(target)).toEqual(["apply"]);
  // A later reply finds nothing waiting and answers nothing again.
  await send(target, "¿Ya está?");
  await settled(target);
  await expect(setupApproval(target)).toHaveCount(0);
  expect(await answers(target)).toEqual(["apply"]);
});

test("rejecting answers the setup and the approval goes away", async ({
  page: target,
}) => {
  await setupWaits(target, "Configura el navegador.");
  await reject(target).click();
  await expect(setupApproval(target)).toHaveCount(0);
  expect(await answers(target)).toEqual(["reject"]);
});

test("a plan that changed before the press is not answered and is shown again", async ({
  page: target,
}) => {
  await setupWaits(target, "Configura el navegador.");
  await control(target, "change");
  await approve(target).click();
  await expect(
    agentColumn(target).getByText(label("desktop.setup_review.changed")),
  ).toBeVisible();
  expect(await answers(target)).toEqual([]);
  // The changed plan is offered again, to be read before it is answered.
  await expect(setupApproval(target)).toBeVisible();
  await noInternalWords(target);
});

test("an answer whose reply is lost is never sent again and says setup may have started", async ({
  page: target,
}) => {
  await setupWaits(target, "Configura el navegador.");
  await control(target, "loseNextAnswer");
  await approve(target).click();
  await expect(
    agentColumn(target).getByText(label("desktop.setup_review.uncertain")),
  ).toBeVisible();
  await expect(setupApproval(target)).toHaveCount(0);
  await expect(
    agentColumn(target).getByRole("button", {
      name: label("desktop.setup_review.check_setup"),
    }),
  ).toBeVisible();
  expect(await answers(target)).toEqual(["apply"]);
  await noInternalWords(target);
});
