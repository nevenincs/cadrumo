import { expect, test, type Page } from "@playwright/test";
import { label } from "../support/strings";

// The agent's settings: the signed-in profile's model providers, each
// reached by its API or its command-line app, opened from the agent's own
// header and only for a profile signed in here. A key is written, saved and
// forgotten; it is never shown again, and never left behind in the page, its
// storage, its address or what the host was asked.

const FAKE_KEY = "FAKE-KEY-not-a-real-key-0000";

const open = (target: Page, scenario = "signed-in") =>
  target.goto(`/scenarios.html?scenario=${scenario}&latency=0&bar=off`);

const settings = (target: Page) =>
  target
    .locator(".pane-agent")
    .getByRole("region", { name: label("desktop.providers.title") });

const settingsButton = (target: Page) =>
  target
    .locator(".pane-agent")
    .getByRole("button", { name: label("desktop.agent.settings") });

/** A provider reached one way, by its name and that way's word. */
const row = (target: Page, name: string, transport: "api" | "cli") =>
  settings(target)
    .getByRole("listitem")
    .filter({
      has: target.getByRole("heading", {
        name: `${name} ${label(`desktop.providers.transport_${transport}`)}`,
        exact: true,
      }),
    });

async function openSettings(target: Page) {
  await settingsButton(target).click();
  await expect(settings(target)).toBeVisible();
}

/** Writes `secret` in a provider's key field and saves it. */
async function saveKey(
  target: Page,
  name: string,
  transport: "api" | "cli",
  secret: string,
  baseUrl?: string,
) {
  const provider = row(target, name, transport);
  await provider
    .getByRole("button", { name: /^(Add|Replace) (key|token)$/ })
    .click();
  await provider.getByLabel(new RegExp(`^${name} `)).fill(secret);
  if (baseUrl !== undefined)
    await provider
      .getByLabel(label("desktop.providers.base_url_label"))
      .fill(baseUrl);
  await provider
    .getByRole("button", { name: label("desktop.providers.save") })
    .click();
}

test.beforeEach(async ({ page: target }) => {
  await target.addInitScript(() => {
    if (sessionStorage.getItem("layout-cleared")) return;
    localStorage.clear();
    sessionStorage.setItem("layout-cleared", "1");
  });
});

test("a key is saved from the profile's settings and never kept anywhere", async ({
  page: target,
}) => {
  await open(target);
  await openSettings(target);
  // One provider, two ways in, each set up on its own.
  await expect(row(target, "Claude", "cli")).toBeVisible();
  const anthropic = row(target, "Claude", "api");
  await expect(anthropic).toContainText(
    label("desktop.providers.readiness_missing"),
  );
  // Save waits for a key, and the field offers none of its own.
  await anthropic
    .getByRole("button", { name: label("desktop.providers.add_key") })
    .click();
  const field = anthropic.getByLabel(/^Claude /);
  await expect(field).toHaveAttribute("type", "password");
  await expect(field).not.toHaveAttribute("placeholder", /.+/);
  await expect(
    anthropic.getByRole("button", { name: label("desktop.providers.save") }),
  ).toBeDisabled();
  await field.fill(FAKE_KEY);
  await anthropic
    .getByRole("button", { name: label("desktop.providers.save") })
    .click();

  await expect(anthropic).toContainText(
    label("desktop.providers.readiness_not_verified"),
  );
  await expect(anthropic).toContainText(
    label("desktop.providers.source_profile"),
  );
  await expect(
    anthropic.getByRole("button", {
      name: label("desktop.providers.replace_key"),
    }),
  ).toBeVisible();
  // Nowhere a key could be left behind holds it.
  const traces = await target.evaluate((key) => {
    const stored = (storage: Storage) =>
      Array.from({ length: storage.length }, (_, index) => {
        const name = storage.key(index) ?? "";
        return `${name}=${storage.getItem(name) ?? ""}`;
      }).join("\n");
    return {
      page: document.documentElement.outerHTML.includes(key),
      fields: [...document.querySelectorAll("input")].some((input) =>
        input.value.includes(key),
      ),
      local: stored(localStorage).includes(key),
      session: stored(sessionStorage).includes(key),
      address: location.href.includes(key),
      calls: (window.__scenarioHostCalls ?? []).join("\n").includes(key),
    };
  }, FAKE_KEY);
  expect(traces).toEqual({
    page: false,
    fields: false,
    local: false,
    session: false,
    address: false,
    calls: false,
  });
});

test("a key that is not one is refused, and says so", async ({
  page: target,
}) => {
  await open(target);
  await openSettings(target);
  await saveKey(target, "OpenAI", "api", "not a key");
  await expect(row(target, "OpenAI", "api").getByRole("alert")).toHaveText(
    label("desktop.providers.refused_invalid_key_format"),
  );
  await expect(row(target, "OpenAI", "api")).toContainText(
    label("desktop.providers.readiness_missing"),
  );
});

test("a gateway takes its address, and one with no default needs it", async ({
  page: target,
}) => {
  await open(target);
  await openSettings(target);
  // With a default, the address may be left empty.
  await expect(row(target, "DeepSeek", "cli")).toContainText(
    "https://deepseek.gateway.example/anthropic",
  );
  // Without one, Save waits for it too.
  const qwen = row(target, "Qwen", "cli");
  await qwen
    .getByRole("button", { name: label("desktop.providers.add_key") })
    .click();
  await qwen.getByLabel(/^Qwen /).fill(FAKE_KEY);
  const save = qwen.getByRole("button", {
    name: label("desktop.providers.save"),
  });
  await expect(save).toBeDisabled();
  await qwen
    .getByLabel(label("desktop.providers.base_url_label"))
    .fill("http://plain.gateway.example");
  await save.click();
  await expect(qwen.getByRole("alert")).toHaveText(
    label("desktop.providers.refused_base_url_rejected"),
  );
  await saveKey(
    target,
    "Qwen",
    "cli",
    FAKE_KEY,
    "https://qwen.gateway.example",
  );
  await expect(qwen).toContainText(
    label("desktop.providers.through", { url: "https://qwen.gateway.example" }),
  );
});

test("a provider is disabled and reset by the person alone", async ({
  page: target,
}) => {
  await open(target);
  await openSettings(target);
  const kimi = row(target, "Kimi", "cli");
  await kimi
    .getByRole("button", { name: label("desktop.providers.disable") })
    .click();
  await expect(kimi).toContainText(
    label("desktop.providers.readiness_disabled"),
  );
  await kimi
    .getByRole("button", { name: label("desktop.providers.reset") })
    .click();
  await expect(kimi).toContainText(
    label("desktop.providers.readiness_missing"),
  );
  // A provider that signs in on its own offers no key to change.
  await expect(row(target, "Codex", "cli").getByRole("button")).toHaveCount(0);
});

test("without a profile signed in here, the agent offers no settings and asks nothing", async ({
  page: target,
}) => {
  await open(target, "signed-out");
  await expect(settingsButton(target)).toHaveAttribute("aria-disabled", "true");
  await expect(settings(target)).toHaveCount(0);
  // Nothing of the agent's, and none of its settings, is asked of the host.
  const calls = await target.evaluate(() => window.__scenarioHostCalls ?? []);
  expect(calls.filter((call) => /^(agent|provider)/.test(call))).toEqual([]);
});
