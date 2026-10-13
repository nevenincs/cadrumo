import { expect, test, type Locator, type Page } from "@playwright/test";
import { DECLARED_SETTINGS_LANES } from "../../src/dev/fixtures/agentLanes.generated";
import { label } from "../support/strings";

// The agent's settings: the signed-in profile's model providers, one card
// for each lane cadrumo-agent has, named as the catalog names it and drawn
// with its provider's own mark, each lane set up on its own. They are opened
// from the agent's own header and only for a profile signed in here. A key is
// written, saved and forgotten; it is never shown again, and never left
// behind in the page, its storage, its address or what the host was asked.

const FAKE_KEY = "FAKE-KEY-not-a-real-key-0000";

const escaped = (text: string) => text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

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

/** One lane's card, by the lane's id. Two lanes of one provider carry the
 * same name, so the id is what tells their cards apart. */
const lane = (target: Page, id: string) =>
  settings(target).locator(`[data-lane="${id}"]`);

const nameOf = (id: string) =>
  DECLARED_SETTINGS_LANES.find((declared) => declared.id === id)
    ?.display_name ?? id;

async function openSettings(target: Page) {
  await settingsButton(target).click();
  await expect(settings(target)).toBeVisible();
}

/** Writes `secret` in a lane's key field and saves it. */
async function saveKey(
  target: Page,
  id: string,
  secret: string,
  baseUrl?: string,
) {
  const entry = lane(target, id);
  await entry
    .getByRole("button", { name: /^(Add|Replace) (key|token)$/ })
    .click();
  await entry.getByLabel(new RegExp(`^${escaped(nameOf(id))} `)).fill(secret);
  if (baseUrl !== undefined)
    await entry
      .getByLabel(label("desktop.providers.base_url_label"))
      .fill(baseUrl);
  await entry
    .getByRole("button", { name: label("desktop.providers.save") })
    .click();
}

/** Where a key could be left behind: the page, its fields, its storage, its
 * address and the calls made to the host. */
const traces = (target: Page, key: string) =>
  target.evaluate((secret) => {
    const stored = (storage: Storage) =>
      Array.from({ length: storage.length }, (_, index) => {
        const name = storage.key(index) ?? "";
        return `${name}=${storage.getItem(name) ?? ""}`;
      }).join("\n");
    return {
      page: document.documentElement.outerHTML.includes(secret),
      fields: [...document.querySelectorAll("input")].some((input) =>
        input.value.includes(secret),
      ),
      local: stored(localStorage).includes(secret),
      session: stored(sessionStorage).includes(secret),
      address: location.href.includes(secret),
      calls: (window.__scenarioHostCalls ?? []).join("\n").includes(secret),
    };
  }, key);

const NO_TRACE = {
  page: false,
  fields: false,
  local: false,
  session: false,
  address: false,
  calls: false,
};

test.beforeEach(async ({ page: target }) => {
  await target.addInitScript(() => {
    if (sessionStorage.getItem("layout-cleared")) return;
    localStorage.clear();
    sessionStorage.setItem("layout-cleared", "1");
  });
});

test("each lane is one card, named as the catalog names it, with its provider's own mark", async ({
  page: target,
}) => {
  await open(target);
  await openSettings(target);

  // One card for each lane cadrumo-agent has, and every one of them is its
  // provider's: its name is the catalog's and its mark is the provider's.
  await expect(settings(target).locator("[data-lane]")).toHaveCount(
    DECLARED_SETTINGS_LANES.length,
  );
  for (const declared of DECLARED_SETTINGS_LANES) {
    const card = lane(target, declared.id);
    await expect(card).toHaveCount(1);
    await expect(card.getByRole("heading", { level: 4 })).toHaveText(
      declared.display_name,
    );
    const mark = card.locator("[data-slot=provider-mark]");
    await expect(mark).toHaveCount(1);
    await expect(mark).toHaveAttribute("data-provider", declared.provider);
    await expect(mark).toHaveAttribute("data-mark", "own");
  }

  // Claude and Codex are each two cards of the same name. Neither is also
  // listed under the name of the company behind its API.
  for (const name of ["Claude", "Codex"])
    await expect(
      settings(target).getByRole("heading", { level: 4, name, exact: true }),
    ).toHaveCount(2);
  for (const name of ["Anthropic", "OpenAI"])
    await expect(settings(target).getByRole("heading", { name })).toHaveCount(
      0,
    );

  // Nothing here is a switch, a card of its own for a kind of access, or
  // words of ours about how a lane is reached: only what each lane is, where
  // it stands and what the person can do with it.
  await expect(settings(target).getByRole("heading", { level: 5 })).toHaveCount(
    0,
  );
  await expect(settings(target).getByRole("radio")).toHaveCount(0);
  const words = await settings(target).innerText();
  expect(words).not.toMatch(/\bCLI\b/i);
  expect(words).not.toMatch(/command[- ]line/i);
  expect(words).not.toMatch(/over the internet/i);
  expect(words).not.toMatch(/on this computer/i);
});

test("a lane with an app says in plain words where it stands, and the API lane says nothing of one", async ({
  page: target,
}) => {
  await open(target);
  await openSettings(target);
  await expect(settings(target).locator("[data-lane]")).toHaveCount(
    DECLARED_SETTINGS_LANES.length,
  );
  const cards = await settings(target)
    .locator("[data-lane]")
    .evaluateAll((nodes) =>
      nodes.map((node) => ({
        id: node.getAttribute("data-lane"),
        text: node.textContent ?? "",
      })),
    );
  // The backend has no safe check yet of a provider's app: it says so, and
  // never that an app is missing.
  for (const declared of DECLARED_SETTINGS_LANES) {
    const text = cards.find((card) => card.id === declared.id)?.text ?? "";
    if (declared.transport === "cli") {
      expect(text, declared.id).toContain(
        label("desktop.providers.cli_unknown"),
      );
      expect(text, declared.id).not.toContain(
        label("desktop.providers.cli_not_installed"),
      );
    } else {
      expect(text, declared.id).not.toContain(
        label("desktop.providers.cli_unknown"),
      );
    }
  }
  // Nothing says what an entry is used for: only the agent uses a key.
  await expect(settings(target)).not.toContainText("Reading documents");
});

test("a key is saved from the agent's settings and never kept anywhere", async ({
  page: target,
}) => {
  await open(target);
  await openSettings(target);
  const claude = lane(target, "claude_api");
  await expect(claude).toContainText(
    label("desktop.providers.readiness_missing"),
  );
  // Save waits for a key, and the field offers none of its own.
  await claude
    .getByRole("button", { name: label("desktop.providers.add_key") })
    .click();
  const field = claude.getByLabel(/^Claude /);
  await expect(field).toHaveAttribute("type", "password");
  await expect(field).not.toHaveAttribute("placeholder", /.+/);
  await expect(
    claude.getByRole("button", { name: label("desktop.providers.save") }),
  ).toBeDisabled();
  await field.fill(FAKE_KEY);
  await claude
    .getByRole("button", { name: label("desktop.providers.save") })
    .click();

  await expect(claude).toContainText(
    label("desktop.providers.readiness_not_verified"),
  );
  await expect(claude).toContainText(label("desktop.providers.source_profile"));
  await expect(
    claude.getByRole("button", {
      name: label("desktop.providers.replace_key"),
    }),
  ).toBeVisible();
  // The other lane of the same provider is not changed by it.
  await expect(lane(target, "claude_cli")).not.toContainText(
    label("desktop.providers.readiness_not_verified"),
  );
  // Nowhere a key could be left behind holds it.
  expect(await traces(target, FAKE_KEY)).toEqual(NO_TRACE);
});

test("a key that is refused or replaced is not kept either", async ({
  page: target,
}) => {
  await open(target);
  await openSettings(target);
  const refused = "not a key";
  await saveKey(target, "codex_api", refused);
  await expect(lane(target, "codex_api").getByRole("alert")).toHaveText(
    label("desktop.providers.refused_invalid_key_format"),
  );
  await expect(lane(target, "codex_api")).toContainText(
    label("desktop.providers.readiness_missing"),
  );
  expect(await traces(target, refused)).toEqual(NO_TRACE);

  await saveKey(target, "codex_api", FAKE_KEY);
  await expect(lane(target, "codex_api")).toContainText(
    label("desktop.providers.readiness_not_verified"),
  );
  const replacement = "FAKE-KEY-replacement-0001";
  await saveKey(target, "codex_api", replacement);
  await expect(
    lane(target, "codex_api").getByRole("button", {
      name: label("desktop.providers.replace_key"),
    }),
  ).toBeVisible();
  for (const key of [FAKE_KEY, replacement])
    expect(await traces(target, key)).toEqual(NO_TRACE);
});

test("a gateway takes its address, and one with no default needs it", async ({
  page: target,
}) => {
  await open(target);
  await openSettings(target);
  // With a default, the address may be left empty.
  const gateway = DECLARED_SETTINGS_LANES.find(
    (declared) => declared.provider === "deepseek",
  );
  expect(gateway?.default_base_url).toBeTruthy();
  await expect(lane(target, "deepseek_cli")).toContainText(
    gateway?.default_base_url ?? "",
  );
  // Without one, Save waits for it too.
  const qwenName = nameOf("qwen_cli");
  const qwen = lane(target, "qwen_cli");
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
  expect(qwenName).toBeTruthy();
  await saveKey(target, "qwen_cli", FAKE_KEY, "https://qwen.gateway.example");
  await expect(qwen).toContainText(
    label("desktop.providers.through", { url: "https://qwen.gateway.example" }),
  );
  expect(await traces(target, FAKE_KEY)).toEqual(NO_TRACE);
});

test("a lane is disabled and reset by the person alone", async ({
  page: target,
}) => {
  await open(target);
  await openSettings(target);
  const kimi = lane(target, "kimi_cli");
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
  // A lane that signs in on its own offers no key to change.
  await expect(lane(target, "codex_cli").getByRole("button")).toHaveCount(0);
});

test("without a profile signed in here, the agent and its settings are not offered and nothing is asked", async ({
  page: target,
}) => {
  await open(target, "signed-out");
  // The agent's place in the rail is held, and says why; its column is gone.
  const rail: Locator = target.locator("[data-rail=agent]");
  await expect(rail).toHaveAttribute("aria-disabled", "true");
  await expect(target.locator(".agent-column")).toBeHidden();
  await expect(settingsButton(target)).toHaveCount(0);
  await expect(settings(target)).toHaveCount(0);
  // Pressing the held place does not bring it back.
  await rail.click({ force: true });
  await expect(target.locator(".agent-column")).toBeHidden();
  // Nothing of the agent's, and none of its settings, is asked of the host.
  const calls = await target.evaluate(() => window.__scenarioHostCalls ?? []);
  expect(calls.filter((call) => /^(agent|provider)/.test(call))).toEqual([]);
});
